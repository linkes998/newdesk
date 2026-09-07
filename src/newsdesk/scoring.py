from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from .config import KEYWORDS, MAX_AGE_HOURS, SCORE_THRESHOLD, SKIP
from .models import Event
from .rss import _age_hours, fetch_rss


def score_event(title: str, summary: str) -> tuple[float, list[str]]:
    blob = f"{title} {summary}".lower()
    if any(k in blob for k in SKIP):
        return 0, []
    tags = []
    score = 0.0
    for tag, words in KEYWORDS.items():
        hits = sum(1 for w in words if w in blob)
        if hits:
            tags.append(tag)
            score += hits
    # crypto + ai 交叉 +2.5（最有价值的"加密 × AI"交叉内容）
    if "crypto" in tags and "ai" in tags:
        score += 2.5
    # 高价值触发词 +1.5
    premium = [
        "clarity", "etf", "regulation", "securities", "sec",
        "openai", "deepseek", "agent", "llm", "model",
        "payment", "banking", "blackrock", "robinhood", "coinbase",
        "tokenized", "rwa", "stablecoin", "memecoin",
        "agent", "reasoning", "cyber defense",
    ]
    if any(w in blob for w in premium):
        score += 1.5
    return score, tags


def collect_events() -> list[Event]:
    events: list[Event] = []
    now = datetime.now(timezone.utc)

    from .config import NEWS_FEEDS
    for feed in NEWS_FEEDS:
        for title, summary, url, pub_at in fetch_rss(feed):
            age = _age_hours(pub_at, now=now)
            raw_score, tags = score_event(title, summary)

            # 时效过滤：超过 MAX_AGE_HOURS 直接丢弃
            if pub_at is not None and age > MAX_AGE_HOURS:
                continue

            if raw_score < SCORE_THRESHOLD:
                continue

            # 时效加权：越新分越高（0-6h 线性加成，+2.0 → -1.0）
            if pub_at is not None:
                freshness_bonus = max(-1.0, 2.0 - (age / MAX_AGE_HOURS) * 3.0)
            else:
                freshness_bonus = -1.5   # 无发布时间 → 强降权

            final_score = raw_score + freshness_bonus

            # 时效加权后再次检查阈值（防止"时效性太差的新闻"挤进来）
            if final_score < SCORE_THRESHOLD:
                continue

            events.append(Event(
                title=title,
                summary=summary[:280],
                url=url,
                score=final_score,
                tags=tags,
                published_at=pub_at,
                age_hours=age,
            ))

    # 先按分数，再按时效（降权后分数已带时效权重）
    events.sort(key=lambda e: e.score, reverse=True)

    seen, uniq = set(), []
    for e in events:
        key = e.title[:40]
        if key in seen:
            continue
        seen.add(key)
        uniq.append(e)

    from .config import MAX_EVENTS
    return uniq[:MAX_EVENTS]
