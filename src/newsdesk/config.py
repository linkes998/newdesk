"""
配置加载器 —— 从 config.yaml + 环境变量读取。
兼容原有 `from .config import NEWS_FEEDS` 用法。

优先级：环境变量 > config.yaml > 内置默认值
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # 打包进 EXE 时确保可用
    yaml = None  # type: ignore


# ---------------------------------------------------------------------------
# 内置默认值（作为 config.yaml 缺失/字段缺失时的 fallback）
# ---------------------------------------------------------------------------
_DEFAULTS: dict[str, Any] = {
    "feeds": [
        "https://www.coindesk.com/arc/outboundfeeds/rss/",
        "https://cointelegraph.com/rss",
        "https://www.theblock.co/rss.xml",
        "https://decrypt.co/feed",
        "https://openai.com/blog/rss.xml",
        "https://cryptonews.com/news/feed/",
        "https://www.coingecko.com/en/rss/news",
        "https://coinmarketcap.com/headlines/rss/",
    ],
    "keywords": {
        "crypto": [
            # 核心币种
            "bitcoin", "btc", "ethereum", "eth", "solana", "xrp", "ripple", "zcash",
            "litecoin", "cardano", "dogecoin",
            # 核心赛道
            "defi", "etf", "clarity", "crypto", "blockchain", "rwa", "stablecoin", "nft",
            "layer2", "layer 2", "rollup", "zk", "zero-knowledge", "memecoin", "mempool",
            # 监管/政策
            "sec", "regulation", "securities", "stock token", "synthetic", "tokenized",
            # 机构/基础设施
            "payment", "banking", "exchange", "robinhood", "coinbase", "kraken",
            "bitget", "blackrock",
        ],
        "ai": [
            # 模型/公司
            "ai", "openai", "anthropic", "gpt", "claude", "llm", "agent", "model",
            "deepseek", "qwen", "gemini", "mistral",
            # AI 应用方向
            "cyber defense", "zero-day", "coding", "reasoning",
        ],
    },
    "skip": ["giveaway", "airdrop code", "保证收益", "稳赚", "必涨", "100x", "moonshot"],
    "threshold": {
        "score_min": 2.0,
        "max_age_hours": 48,        # RSS 新闻 48h 内都算新鲜，时效加权让新的排最前
        "max_items": 8,
        "rss_timeout_seconds": 20,
        "rss_max_entries": 25,
    },
    "paths": {
        "samples": "samples",
        "output_dir": "output",
        "output_file": "output/three_platforms.md",
        "data_dir": "data",
    },
    "llm_ranker": {
        "enabled": False,
        "weight_keywords": 0.4,
        "weight_llm": 0.6,
        "batch_size": 4,
    },
    "llm": {
        "api_key": "",
        "base_url": "",
        "model": "",
    },
    "llm_fallback": [],   # [{api_key, base_url, model}, ...]
    "content": {
        "language": "zh",          # zh / en / auto
        "default_style": "professional",
        "target_platforms": ["x", "telegram", "discord"],
        "user_hint": "",            # 用户自定义的附加 prompt
        "auto_publish": False,      # True = 直接发布，False = 进入审核队列
    },
    "publisher": {
        "twitter": {"bearer_token": "", "api_key": "", "api_secret": "", "oauth_token": "", "oauth_secret": ""},
        "telegram": {"bot_token": "", "chat_id": "", "parse_mode": "HTML"},
        "discord": {"webhook_url": "", "username": "NewsDesk", "avatar_url": ""},
    },
    "cache": {
        "ttl_seconds": 3600,
    },
    "scheduler": {
        "interval_minutes": 30,
        "timezone": "UTC",
    },
}


def _deep_merge(base: dict, override: dict) -> dict:
    """递归合并两个 dict，override 覆盖 base。"""
    result = base.copy()
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(result.get(k), dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def load_config(path: Path | str | None = None) -> dict[str, Any]:
    """加载 YAML 配置，叠加默认值。"""
    if path is None:
        # 搜索顺序：项目根目录 → 当前工作目录
        candidates = [
            Path(__file__).resolve().parent.parent.parent / "config.yaml",
            Path.cwd() / "config.yaml",
        ]
        path = next((p for p in candidates if p.exists()), candidates[0])
    else:
        path = Path(path)

    loaded = {}
    if yaml is not None and path.exists():
        try:
            loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception as exc:
            print(f"⚠️  配置文件解析失败 {path}：{exc}，使用默认值")
            loaded = {}

    merged = _deep_merge(_DEFAULTS, loaded)

    # ---- 环境变量覆盖（LLM 部分保持向后兼容）----
    env_map = {
        "NEWSDESK_LLM_API_KEY": ("llm", "api_key"),
        "NEWSDESK_LLM_BASE_URL": ("llm", "base_url"),
        "NEWSDESK_LLM_MODEL": ("llm", "model"),
    }
    for env_name, (section, key) in env_map.items():
        val = os.environ.get(env_name, "").strip()
        if val:
            merged.setdefault(section, {})[key] = val

    return merged


# ---------------------------------------------------------------------------
# 兼容层 —— 让 `from .config import NEWS_FEEDS` 继续工作
# ---------------------------------------------------------------------------
_cfg = load_config()

NEWS_FEEDS = _cfg["feeds"]
KEYWORDS = _cfg["keywords"]
SKIP = _cfg["skip"]
SAMPLES_DIR = _cfg["paths"]["samples"]
OUTPUT_DIR = _cfg["paths"]["output_dir"]
OUTPUT_FILE = _cfg["paths"]["output_file"]
DATA_DIR = _cfg["paths"]["data_dir"]
MAX_EVENTS = _cfg["threshold"]["max_items"]
SCORE_THRESHOLD = _cfg["threshold"]["score_min"]
MAX_AGE_HOURS = _cfg["threshold"]["max_age_hours"]
RSS_TIMEOUT_SECONDS = _cfg["threshold"]["rss_timeout_seconds"]
RSS_MAX_ITEMS = _cfg["threshold"]["rss_max_entries"]
CACHE_TTL = _cfg["cache"]["ttl_seconds"]
RANKER_ENABLED = _cfg["llm_ranker"]["enabled"]
RANKER_W_KW = _cfg["llm_ranker"]["weight_keywords"]
RANKER_W_LLM = _cfg["llm_ranker"]["weight_llm"]
SCHEDULER_INTERVAL = _cfg["scheduler"]["interval_minutes"]


def reload() -> dict[str, Any]:
    """热重载配置（GUI 保存后可调用）。"""
    global _cfg
    _cfg = load_config()
    # 同步到模块级常量（Python 会重新绑定）
    globals().update({
        "NEWS_FEEDS": _cfg["feeds"],
        "KEYWORDS": _cfg["keywords"],
        "SKIP": _cfg["skip"],
        "MAX_EVENTS": _cfg["threshold"]["max_items"],
        "SCORE_THRESHOLD": _cfg["threshold"]["score_min"],
        "MAX_AGE_HOURS": _cfg["threshold"]["max_age_hours"],
        "RSS_TIMEOUT_SECONDS": _cfg["threshold"]["rss_timeout_seconds"],
        "RSS_MAX_ITEMS": _cfg["threshold"]["rss_max_entries"],
    })
    return _cfg


def get_raw() -> dict[str, Any]:
    """获取完整配置 dict（给 GUI / scheduler 等高级用）。"""
    return _cfg
