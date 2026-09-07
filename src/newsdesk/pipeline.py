"""
流水线断点持久化 —— 借鉴 Sumbird 的 9 步断点设计。
每一步的输出都存为 data/*.json，可独立加载/跳过，LLM 中断后恢复不用重新爬。

目录结构：
data/
├── 01_fetched.json      ← RSS 原始抓取结果（含发布时间）
├── 02_scored.json       ← 评分 + 时效过滤后的 Event 列表
├── 03_drafts.json       ← 三平台文案草稿（可能部分由 LLM 生成）
└── state.json           ← 最近一次运行的 fetch hash，避免重复处理
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .config import DATA_DIR
from .models import Event


_DATA = Path(DATA_DIR)
_FETCHED = _DATA / "01_fetched.json"
_SCORED = _DATA / "02_scored.json"
_DRAFTS = _DATA / "03_drafts.json"
_STATE = _DATA / "state.json"


def _ensure_dir() -> None:
    _DATA.mkdir(parents=True, exist_ok=True)


def _event_to_dict(e: Event) -> dict:
    return {
        "title": e.title,
        "summary": e.summary,
        "url": e.url,
        "score": e.score,
        "tags": e.tags,
        "published_at": e.published_at.isoformat() if e.published_at else None,
        "age_hours": e.age_hours,
    }


def _dict_to_event(d: dict) -> Event:
    pub = d.get("published_at")
    if pub:
        pub = datetime.fromisoformat(pub)
        if pub.tzinfo is None:
            pub = pub.replace(tzinfo=timezone.utc)
    return Event(
        title=d["title"],
        summary=d["summary"],
        url=d["url"],
        score=d["score"],
        tags=d.get("tags", []),
        published_at=pub,
        age_hours=d.get("age_hours", 0.0),
    )


def save_step(step: str, data: Any) -> Path:
    """保存一步的输出。step ∈ {'fetched', 'scored', 'drafts'}。"""
    _ensure_dir()
    mapping = {
        "fetched": _FETCHED,
        "scored": _SCORED,
        "drafts": _DRAFTS,
    }
    target = mapping.get(step)
    if target is None:
        raise ValueError(f"Unknown step: {step}")

    serializable = data
    if step == "scored" and isinstance(data, list) and data and isinstance(data[0], Event):
        serializable = [_event_to_dict(e) for e in data]

    payload = {
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "step": step,
        "count": len(data) if hasattr(data, "__len__") else None,
        "data": serializable,
    }
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def load_step(step: str) -> Optional[Any]:
    """加载某一步的中间产物，不存在返回 None。"""
    mapping = {"fetched": _FETCHED, "scored": _SCORED, "drafts": _DRAFTS}
    target = mapping.get(step)
    if target is None or not target.exists():
        return None
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    data = payload.get("data")
    if step == "scored" and isinstance(data, list):
        return [_dict_to_event(d) for d in data]
    return data


def fetch_hash(title: str, url: str) -> str:
    """为一条新闻生成稳定 hash，用于重复检测。"""
    return hashlib.sha256(f"{title[:60]}|{url}".encode()).hexdigest()[:16]


def load_state() -> dict:
    if _STATE.exists():
        try:
            return json.loads(_STATE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"last_fetch_hashes": [], "last_run": None}


def save_state(state: dict) -> None:
    _ensure_dir()
    _STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def save_drafts(drafts_map: dict[int, dict[str, str]]) -> Path:
    """drafts 持久化：{idx: {platform: text}}"""
    return save_step("drafts", drafts_map)


def load_drafts() -> Optional[dict[int, dict[str, str]]]:
    raw = load_step("drafts")
    if raw is None:
        return None
    # JSON keys are strings，转回 int
    return {int(k): v for k, v in raw.items()}
