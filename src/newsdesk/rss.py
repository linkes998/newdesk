from __future__ import annotations

import re
import time
from datetime import datetime, timezone
from typing import Optional

import feedparser

from .config import RSS_MAX_ITEMS, RSS_TIMEOUT_SECONDS
from .cache import RSSCache


def clean(text: str) -> str:
    """移除 HTML 标签和 URL。feedparser 已做大部分清洗，这里只做收尾。"""
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = re.sub(r"https?://\S+", "", text)
    return re.sub(r"\s+", " ", text).strip()


def _struct_to_utc(parsed) -> Optional[datetime]:
    """把 feedparser 返回的 time.struct_time 转成 UTC aware datetime。"""
    if parsed is None:
        return None
    return datetime(
        parsed.tm_year, parsed.tm_mon, parsed.tm_mday,
        parsed.tm_hour, parsed.tm_min, parsed.tm_sec,
        tzinfo=timezone.utc,
    )


def _age_hours(dt: Optional[datetime], now: Optional[datetime] = None) -> float:
    if dt is None:
        return 9999.0
    now = now or datetime.now(timezone.utc)
    return (now - dt).total_seconds() / 3600.0


_cache = RSSCache()


def fetch_rss(url: str) -> list[tuple[str, str, str, Optional[datetime]]]:
    """
    返回 [(title, summary, url, published_at_utc)] 列表。
    feedparser 自动处理 RSS 2.0 / Atom 1.0 / JSON Feed / RDF 等格式。

    summary 提取优先级：summary → description → content[0] → tags+author 拼接降级
    （很多站点如 Coindesk 的 summary/content 字段就是空的）
    """
    cached = _cache.get(url)
    if cached is not None:
        return cached

    # feedparser 自带 URL 抓取，但我们用自己的 User-Agent 和超时
    d = feedparser.parse(
        url,
        agent="content-desk/1.0",
    )

    rows: list[tuple[str, str, str, Optional[datetime]]] = []
    for entry in d.entries[:RSS_MAX_ITEMS]:
        title = clean(entry.get("title", ""))

        # --- summary 多级降级 ---
        summary = ""
        summary_raw = entry.get("summary", "") or entry.get("description", "")
        if summary_raw:
            summary = clean(summary_raw)
        if not summary and entry.get("content"):
            # Atom 格式常见
            try:
                summary = clean(entry["content"][0].get("value", ""))
            except Exception:
                pass
        if not summary:
            # 最终降级：拼接 tags + author
            tag_terms = [t.get("term", "") for t in (entry.get("tags") or []) if t.get("term")]
            author = entry.get("author", "")
            extras = [x for x in tag_terms + ([author] if author else []) if x]
            summary = " · ".join(extras) if extras else "(无摘要)"

        link = entry.get("link", "") or ""
        # published → published_parsed 自动解析 RFC 822 / ISO 8601 / W3CDTF 等 10+ 格式
        pub = _struct_to_utc(
            entry.get("published_parsed")
            or entry.get("updated_parsed")
            or entry.get("created_parsed")
        )
        rows.append((title, summary[:500], link, pub))

    _cache.set(url, rows)
    return rows
