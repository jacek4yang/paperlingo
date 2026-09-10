"""学习领域模型：知识点类型、掌握程度、复习相关枚举。"""

from __future__ import annotations

from enum import StrEnum


class ItemType(StrEnum):
    WORD = "word"
    PHRASE = "phrase"
    GRAMMAR = "grammar"
    SENTENCE_PATTERN = "sentence_pattern"
    EXPRESSION = "expression"
    CONCEPT = "concept"


ITEM_TYPE_LABELS: dict[ItemType, str] = {
    ItemType.WORD: "单词",
    ItemType.PHRASE: "短语",
    ItemType.GRAMMAR: "语法",
    ItemType.SENTENCE_PATTERN: "句型",
    ItemType.EXPRESSION: "学术表达",
    ItemType.CONCEPT: "概念",
}


class MasteryStatus(StrEnum):
    """用户对知识点的自评。只有"不熟/不会"进入学习队列。"""

    UNKNOWN = "unknown"  # 未标记
    KNOWN = "known"  # 认识
    UNFAMILIAR = "unfamiliar"  # 不熟
    HARD = "hard"  # 不会


MASTERY_LABELS: dict[MasteryStatus, str] = {
    MasteryStatus.UNKNOWN: "未标记",
    MasteryStatus.KNOWN: "认识",
    MasteryStatus.UNFAMILIAR: "不熟",
    MasteryStatus.HARD: "不会",
}

#: 需要进入学习队列的状态
LEARNING_STATUSES: frozenset[MasteryStatus] = frozenset(
    {MasteryStatus.UNFAMILIAR, MasteryStatus.HARD}
)


class Rating(StrEnum):
    """复习评分（对应 FSRS 四档）。"""

    AGAIN = "again"
    HARD = "hard"
    GOOD = "good"
    EASY = "easy"


RATING_LABELS: dict[Rating, str] = {
    Rating.AGAIN: "忘记",
    Rating.HARD: "困难",
    Rating.GOOD: "记得",
    Rating.EASY: "熟练",
}
