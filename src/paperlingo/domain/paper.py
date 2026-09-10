"""论文信息领域模型。"""

from __future__ import annotations

from pydantic import BaseModel

#: 研究领域下拉框的固定选项（"自动判断" 表示交给 AI）
DOMAINS: list[str] = [
    "自动判断",
    "计算机科学",
    "人工智能",
    "网络",
    "网络安全",
    "软件工程",
    "系统",
    "密码学",
    "数据库",
    "其他",
]


class PaperInfo(BaseModel):
    """用户可选补充的论文元信息。"""

    title: str = ""
    doi_or_url: str = ""
    authors: str = ""
    domain: str = DOMAINS[0]

    def is_empty(self) -> bool:
        return not (self.title.strip() or self.doi_or_url.strip() or self.authors.strip())

    def domain_specified(self) -> bool:
        return bool(self.domain) and self.domain != DOMAINS[0]
