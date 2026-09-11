"""Paper metadata domain model."""

from __future__ import annotations

from pydantic import BaseModel

#: Fixed options for the research-field combo box as (stable English value,
#: Simplified Chinese display label) pairs. "auto" means the AI decides the field.
DOMAIN_OPTIONS: list[tuple[str, str]] = [
    ("auto", "自动判断"),
    ("computer_science", "计算机科学"),
    ("artificial_intelligence", "人工智能"),
    ("networking", "计算机网络"),
    ("cybersecurity", "网络安全"),
    ("software_engineering", "软件工程"),
    ("systems", "计算机系统"),
    ("cryptography", "密码学"),
    ("databases", "数据库"),
    ("other", "其他"),
]

DOMAIN_VALUES: list[str] = [value for value, _ in DOMAIN_OPTIONS]

DEFAULT_DOMAIN = DOMAIN_VALUES[0]


class PaperInfo(BaseModel):
    """Optional paper metadata supplied by the user."""

    title: str = ""
    doi_or_url: str = ""
    authors: str = ""
    domain: str = DEFAULT_DOMAIN

    def is_empty(self) -> bool:
        return not (self.title.strip() or self.doi_or_url.strip() or self.authors.strip())

    def domain_specified(self) -> bool:
        return bool(self.domain) and self.domain != DEFAULT_DOMAIN
