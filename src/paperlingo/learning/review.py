"""Review scheduler.

v1 uses a built-in simplified SM-2-style schedule (no external dependencies);
the Scheduler interface isolates it so a future FSRS implementation can replace
it without touching callers. The scheduler is fully decoupled from the UI: it
takes the current card state plus a rating and returns the next due time.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Protocol

from paperlingo.domain.learning import Rating

if TYPE_CHECKING:
    from paperlingo.database.repository import Repository


@dataclass
class CardState:
    """State of one learning card (persisted in the learning_items table)."""

    stability: float = 0.0  # memory stability (days)
    difficulty: float = 0.0  # difficulty 1-10
    reps: int = 0
    lapses: int = 0


@dataclass
class ScheduleResult:
    interval_days: float
    due_at: str  # "YYYY-MM-DD HH:MM:SS" local time
    stability: float
    difficulty: float


class Scheduler(Protocol):
    def next(self, state: CardState, rating: Rating, now: datetime | None = None) -> ScheduleResult: ...


class SimpleScheduler:
    """Simplified SM-2-style scheduler.

    - The first review grants 1-4 days depending on the rating;
    - stability grows with consecutive Good/Easy and resets on Again;
    - difficulty converges into [1, 10].
    """

    def next(self, state: CardState, rating: Rating, now: datetime | None = None) -> ScheduleResult:
        now = now or datetime.now()

        # Difficulty update: Again +1.5, Hard +0.5, Good -0.2, Easy -0.5,
        # converging into [1, 10].
        delta = {Rating.AGAIN: 1.5, Rating.HARD: 0.5, Rating.GOOD: -0.2, Rating.EASY: -0.5}[rating]
        difficulty = min(10.0, max(1.0, (state.difficulty or 5.0) + delta))

        if rating == Rating.AGAIN:
            stability = 0.5
            interval = 0.007  # try again in ~10 minutes
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
        # For sub-day intervals keep hour/minute precision.
        return ScheduleResult(
            interval_days=round(interval, 4),
            due_at=due.strftime("%Y-%m-%d %H:%M:%S"),
            stability=round(stability, 3),
            difficulty=round(difficulty, 2),
        )


#: Module-level default scheduler; replacing it with FSRS only requires
#: changing this reference.
_default_scheduler: Scheduler = SimpleScheduler()


def get_scheduler() -> Scheduler:
    return _default_scheduler


def set_scheduler(s: Scheduler) -> None:
    global _default_scheduler
    _default_scheduler = s


def review_item(repo: Repository, learning_item_id: int, rating: Rating) -> bool:
    """Load the card state from the database, schedule the next review, and
    write it back. Returns True on success."""
    state_row = repo.get_card_state(learning_item_id)
    if state_row is None:
        return False
    state = CardState(**state_row)
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
