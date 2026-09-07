"""
NewsDesk Browser Extension API Server
======================================
轻量 HTTP 服务器（port 18923），供浏览器插件读写审核队列和提交文章。

依赖：仅 Python stdlib（http.server + json + pathlib）

用法：
    python browser_extension_server.py          # 默认 :18923
    python browser_extension_server.py 8080     # 自定义端口
"""
from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# 加载本地 NewsDesk 审核队列
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from newsdesk.review import ReviewQueue, ReviewStatus, ReviewItem  # noqa: E402
from newsdesk.config import load_config  # noqa: E402

QUEUE_PATH = PROJECT_ROOT / "data" / "review_queue.json"
_cfg = load_config()
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 18923


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------

class Handler(BaseHTTPRequestHandler):
    """极简 JSON API handler。"""

    def log_message(self, fmt, *args):
        pass  # silence access logs

    def _send_json(self, code: int, data: Any) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    # ---- Health ----

    def do_GET(self):
        if self.path == "/health":
            self._send_json(200, {"ok": True, "port": PORT, "items": len(_queue.all())})
            return

        # GET /api/v1/queue/pending — 返回待审核列表
        if self.path == "/api/v1/queue/pending":
            items = _queue.pending()
            self._send_json(200, {
                "items": [
                    {
                        "item_id": it.item_id,
                        "event_title": it.event_title,
                        "event_url": it.event_url,
                        "event_summary": it.event_summary,
                        "event_score": it.event_score,
                        "event_tags": it.event_tags,
                        "drafts": it.drafts,
                        "status": it.status,
                    }
                    for it in items
                ],
                "stats": _queue.stats(),
            })
            return

        # GET /api/v1/queue/<id> — 返回单条详情
        if self.path.startswith("/api/v1/queue/"):
            item_id = self.path.split("/")[-1]
            item = _queue.find(item_id)
            if item is None:
                self._send_json(404, {"error": "not found"})
                return
            self._send_json(200, {
                "item_id": item.item_id,
                "event_title": item.event_title,
                "event_url": item.event_url,
                "event_summary": item.event_summary,
                "event_score": item.event_score,
                "event_tags": item.event_tags,
                "drafts": item.drafts,
                "status": item.status,
            })
            return

        self._send_json(404, {"error": "not found"})

    # ---- POST ----

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length else b"{}"
        try:
            data: dict = json.loads(body) if body else {}
        except json.JSONDecodeError:
            data = {}

        # POST /api/v1/articles/detect — 检测文章（返回是否命中关键词）
        if self.path == "/api/v1/articles/detect":
            title = (data.get("title") or "").lower()
            summary = (data.get("summary") or "").lower()
            blob = f"{title} {summary}"
            score = _score_blob(blob)
            self._send_json(200, {"ok": score >= 2.0, "score": round(score, 2)})
            return

        # POST /api/v1/articles/submit — 提交文章到审核队列
        if self.path == "/api/v1/articles/submit":
            title = data.get("title", "")
            url = data.get("url", "")
            summary = data.get("summary", "")
            if not title or not url:
                self._send_json(400, {"error": "title and url required"})
                return
            score = _score_blob(f"{title} {summary}")
            item = ReviewItem(
                item_id=_hash(title, url),
                event_title=title,
                event_url=url,
                event_summary=summary,
                event_score=score,
                event_tags=_detect_tags(f"{title} {summary}"),
            )
            _queue.add(item)
            _queue.save()
            self._send_json(200, {"ok": True, "item_id": item.item_id, "score": round(score, 2)})
            return

        # POST /api/v1/queue/<id>/approve
        if self.path.startswith("/api/v1/queue/") and self.path.endswith("/approve"):
            item_id = self.path.split("/")[-2]
            item = _queue.approve(item_id)
            if item is None:
                self._send_json(404, {"error": "not found"})
            else:
                self._send_json(200, {"ok": True, "item_id": item.item_id})
            return

        # POST /api/v1/queue/<id>/reject
        if self.path.startswith("/api/v1/queue/") and self.path.endswith("/reject"):
            item_id = self.path.split("/")[-2]
            item = _queue.reject(item_id)
            if item is None:
                self._send_json(404, {"error": "not found"})
            else:
                self._send_json(200, {"ok": True, "item_id": item.item_id})
            return

        self._send_json(404, {"error": "not found"})


# ---------------------------------------------------------------------------
# Helpers（复用 NewsDesk scoring 逻辑）
# ---------------------------------------------------------------------------

_KEYWORDS = _cfg.get("keywords", {})
_SKIP = _cfg.get("skip", [])
_SCORE_THRESHOLD = _cfg.get("threshold", {}).get("score_min", 2.0)


def _score_blob(blob: str) -> float:
    blob_lower = blob.lower()
    score = 0.0
    crypto_hits = [w for w in _KEYWORDS.get("crypto", []) if w in blob_lower]
    ai_hits = [w for w in _KEYWORDS.get("ai", []) if w in blob_lower]
    if crypto_hits:
        score += len(crypto_hits)
    if ai_hits:
        score += len(ai_hits)
    if crypto_hits and ai_hits:
        score += 2.5
    # skip list → zero out
    for kw in _SKIP:
        if kw.lower() in blob_lower:
            return 0.0
    return score


def _detect_tags(blob: str) -> list[str]:
    tags = []
    blob_lower = blob.lower()
    if any(w in blob_lower for w in _KEYWORDS.get("crypto", [])):
        tags.append("crypto")
    if any(w in blob_lower for w in _KEYWORDS.get("ai", [])):
        tags.append("ai")
    return tags


def _hash(title: str, url: str) -> str:
    import hashlib
    raw = f"{title[:60]}|{url}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Init queue & run
# ---------------------------------------------------------------------------

_queue = ReviewQueue(path=str(QUEUE_PATH))
_queue.load()

if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"NewsDesk Browser API  listening on http://127.0.0.1:{PORT}")
    print(f"Queue file: {QUEUE_PATH}")
    print("Press Ctrl+C to stop\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.server_close()
