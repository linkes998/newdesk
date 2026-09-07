from src.newsdesk.cache import RSSCache, _encode_row, _decode_row
from pathlib import Path
import tempfile
import time
from datetime import datetime, timezone


def test_cache_miss():
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = RSSCache(cache_dir=Path(tmpdir), ttl_seconds=60)
        assert cache.get("https://example.com/rss") is None


def test_cache_set_and_get():
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = RSSCache(cache_dir=Path(tmpdir), ttl_seconds=60)
        pub = datetime.now(timezone.utc)
        data = [("Title 1", "Desc 1", "https://ex.com/1", pub)]
        cache.set("https://example.com/rss", data)
        result = cache.get("https://example.com/rss")
        assert result is not None
        assert len(result) == 1
        assert result[0][0] == "Title 1"
        assert result[0][1] == "Desc 1"
        assert result[0][2] == "https://ex.com/1"
        assert isinstance(result[0][3], datetime)
        assert result[0][3].tzinfo is not None


def test_cache_ttl_expiry():
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = RSSCache(cache_dir=Path(tmpdir), ttl_seconds=0.1)
        pub = datetime.now(timezone.utc)
        cache.set("https://example.com/rss", [("T", "D", "U", pub)])
        time.sleep(0.2)
        assert cache.get("https://example.com/rss") is None


def test_cache_different_urls():
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = RSSCache(cache_dir=Path(tmpdir), ttl_seconds=60)
        now = datetime.now(timezone.utc)
        cache.set("https://a.com/rss", [("A", "D", "U", now)])
        cache.set("https://b.com/rss", [("B", "D", "U", now)])
        a = cache.get("https://a.com/rss")
        b = cache.get("https://b.com/rss")
        assert a and b
        assert a[0][0] != b[0][0]


def test_roundtrip_without_pub_date():
    """无日期的条目也能正确往返。"""
    row = ("T", "D", "U", None)
    encoded = _encode_row(row)
    assert encoded[3] is None
    decoded = _decode_row(encoded)
    assert decoded == row


def test_backward_compat_3tuple():
    """旧的 3-tuple 缓存格式能被读取（pub_at=None）。"""
    raw = ["OldTitle", "OldDesc", "https://old.com"]
    decoded = _decode_row(raw)
    assert decoded[0] == "OldTitle"
    assert decoded[3] is None


def test_encode_decode_roundtrip():
    pub = datetime.now(timezone.utc).replace(microsecond=0)
    row = ("T", "D", "U", pub)
    assert _decode_row(_encode_row(row)) == row
