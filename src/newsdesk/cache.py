from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


def _encode_row(row):
    """把 fetch_rss 的 row (title, summary, url, pub_at) 序列化为 JSON 安全格式。"""
    title, summary, url, pub_at = row
    pub_iso = pub_at.isoformat() if pub_at else None
    return [title, summary, url, pub_iso]


def _decode_row(raw):
    """把 JSON 行还原为 (title, summary, url, datetime|None)。"""
    # 兼容旧缓存格式：3-tuple 无日期
    if len(raw) == 3:
        title, summary, url = raw
        return (title, summary, url, None)
    title, summary, url, pub_iso = raw
    pub_at = None
    if pub_iso:
        try:
            pub_at = datetime.fromisoformat(pub_iso)
            if pub_at.tzinfo is None:
                pub_at = pub_at.replace(tzinfo=timezone.utc)
        except ValueError:
            pub_at = None
    return (title, summary, url, pub_at)


class RSSCache:
    """简单的文件级缓存，按 URL 哈希存储 RSS 响应。"""

    def __init__(self, cache_dir: Path = Path(".cache/rss"), ttl_seconds: int = 3600):
        self._dir = cache_dir
        self._ttl = ttl_seconds
        self._dir.mkdir(parents=True, exist_ok=True)

    def get(self, url: str):
        key = self._key(url)
        meta_path = self._dir / f"{key}.meta"
        data_path = self._dir / f"{key}.json"
        if not meta_path.exists() or not data_path.exists():
            return None
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            if time.time() - meta["ts"] > self._ttl:
                return None
            raw_rows = json.loads(data_path.read_text(encoding="utf-8"))
            return [_decode_row(r) for r in raw_rows]
        except Exception:
            return None

    def set(self, url: str, data) -> None:
        key = self._key(url)
        meta_path = self._dir / f"{key}.meta"
        data_path = self._dir / f"{key}.json"
        meta_path.write_text(json.dumps({"ts": time.time()}, ensure_ascii=False), encoding="utf-8")
        encoded = [_encode_row(r) for r in data]
        data_path.write_text(json.dumps(encoded, ensure_ascii=False), encoding="utf-8")

    @staticmethod
    def _key(url: str) -> str:
        return hashlib.sha256(url.encode()).hexdigest()[:16]
