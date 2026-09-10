"""复习调度器。

v1 使用内置的简化 SM-2 风格调度（无外部依赖）；
通过 Scheduler 接口隔离，未来可无痛替换为 FSRS 官方实现。
调度器与 UI 完全解耦：输入当前状态 + 评分，输出下一次到期时间。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol

from paperlingo.domain.learning import Rating


@dataclass
class CardState:
    """一张学习卡片的状态（持久化在 learning_items 表）。"""

    stability: float = 0.0  # 记忆稳定度（天）
    difficulty: float = 0.0  # 难度 1-10
    reps: int = 0
    lapses: int = 0


@dataclass
class ScheduleResult:
    interval_days: float
    due_at: str  # "YYYY-MM-DD HH:MM:SS" 本地时间
    stability: float
    difficulty: float


class Scheduler(Protocol):
    def next(self, state: CardState, rating: Rating, now: datetime | None = None) -> ScheduleResult: ...


class SimpleScheduler:
    """SM-2 风格的简易调度器。

    - 首次复习按评分给 1~4 天；
    - 稳定度随连续 Good/Easy 增长，Again 重置；
    - 难度向 [1, 10] 收敛。
    """

    def next(self, state: CardState, rating: Rating, now: datetime | None = None) -> ScheduleResult:
        now = now or datetime.now()

        # 难度更新：Again +1.5，Hard +0.5，Good -0.2，Easy -0.5，收敛到 [1,10]
        delta = {Rating.AGAIN: 1.5, Rating.HARD: 0.5, Rating.GOOD: -0.2, Rating.EASY: -0.5}[rating]
        difficulty = min(10.0, max(1.0, (state.difficulty or 5.0) + delta))

        if rating == Rating.AGAIN:
            stability = 0.5
            interval = 0.007  # 10 分钟后重来
        else:
            factor = {Rating.HARD: 1.2, Rating.GOOD: 2.3, Rating.EASY: 3.2}[rating]
            if state.stability <= 0:
                base = {Rating.HARD: 1.0, Rating.GOOD: 2.0, Rating.EASY: 4.0}[rating]
                stability = base
            else:
                penalty = 1.0 - min(0.3, difficulty / 33.0)
                stability = state.stability * factor * penalty
            interval = max(0.02, stability * (0.6 if rating == Rating.HARD else 1.0))

        stability = max(0.1, min(stability, 365.0 * 2))
        due = now + timedelta(days=interval)
        # 秒级精度下，不足 1 天的间隔保留小时/分钟
        return ScheduleResult(
            interval_days=round(interval, 4),
            due_at=due.strftime("%Y-%m-%d %H:%M:%S"),
            stability=round(stability, 3),
            difficulty=round(difficulty, 2),
        )


#: 模块级默认调度器；未来替换 FSRS 时只需改变这里
_default_scheduler: Scheduler = SimpleScheduler()


def get_scheduler() -> Scheduler:
    return _default_scheduler


def set_scheduler(s: Scheduler) -> None:
    global _default_scheduler
    _default_scheduler = s


def review_item(repo, learning_item_id: int, rating: Rating) -> bool:
    """从数据库取卡片状态，调度下一次复习并写回。成功返回 True。"""
    from paperlingo.database.repository import Repository  # 局部导入避免循环

    assert isinstance(repo, Repository)
    row = repo.db.conn.execute(
        "SELECT stability, difficulty, reps, lapses FROM learning_items WHERE id = ?",
        (learning_item_id,),
    ).fetchone()
    if row is None:
        return False
    state = CardState(
        stability=float(row["stability"] or 0.0),
        difficulty=float(row["difficulty"] or 0.0),
        reps=int(row["reps"] or 0),
        lapses=int(row["lapses"] or 0),
    )
    result = get_scheduler().next(state, rating)
    repo.log_review(
        learning_item_id,
        rating,
        {
            "stability": result.stability,
            "difficulty": result.difficulty,
            "due_at": result.due_at,
        },
    )
    return True
