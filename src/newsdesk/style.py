from __future__ import annotations

import re
import statistics
from pathlib import Path

from .config import SAMPLES_DIR
from .models import Style
from .rss import clean


def parse_samples(path: Path) -> list[str]:
    if not path.exists():
        return []
    raw = path.read_text(encoding="utf-8")
    parts = re.split(r"\n\s*\n", raw)
    return [clean(p) for p in parts if len(clean(p)) > 20]


def load_all_styles() -> dict[str, Style]:
    samples_path = Path(SAMPLES_DIR)
    return {
        "x": _analyze_from_file("x", samples_path / "x.txt"),
        "binance": _analyze_from_file("binance", samples_path / "biance.txt"),
        "okx": _analyze_from_file("okx", samples_path / "okx.txt"),
    }


def _analyze_from_file(name: str, path: Path) -> Style:
    posts = parse_samples(path)
    return analyze_style(name, posts)


def analyze_style(name: str, posts: list[str]) -> Style:
    if not posts:
        return Style.default(name)
    lengths = [len(p) for p in posts]
    emoji = sum(len(re.findall(r"[\U0001F300-\U0001FAFF]", p)) > 0 for p in posts) / len(posts)
    ticker = sum(("$" in p or "＃" in p or "#" in p) for p in posts) / len(posts)
    question = sum("？" in p or "?" in p for p in posts) / len(posts)
    first_lines = [p.split("。")[0][:40] for p in posts[:8]]
    return Style(name, int(statistics.median(lengths)), emoji, ticker, question, first_lines)


def adapt_to_style(base: str, style: Style, platform: str) -> str:
    text = base
    if style.ticker_rate > 0.4 and "$BTC" not in text and "$" not in text:
        text += "\n$BTC $ETH"
    if style.question_rate > 0.3 and "？" not in text:
        text += "\n你怎么看？"
    if platform == "x":
        text = "\n".join(text.split("\n")[:8])
    if platform == "okx" and len(text) > 480:
        text = text[:470] + "…"
    return text.strip()
