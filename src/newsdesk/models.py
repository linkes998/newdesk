from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol, Optional


@dataclass
class Event:
    title: str
    summary: str
    url: str
    score: float
    tags: list[str] = field(default_factory=list)
    published_at: Optional[datetime] = None   # UTC，无时区标记时当作 UTC
    age_hours: float = 0.0                   # 抓取时计算的时效


@dataclass
class Style:
    name: str
    avg_len: int
    emoji_rate: float
    ticker_rate: float
    question_rate: float
    first_lines: list[str] = field(default_factory=list)

    @classmethod
    def default(cls, name: str) -> "Style":
        return cls(name, 180, 0.1, 0.3, 0.2, [])


class LLMClient(Protocol):
    def generate(self, prompt: str, model: str | None = None) -> str: ...
