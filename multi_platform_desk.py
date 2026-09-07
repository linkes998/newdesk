#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
热点事件 -> X / 币安广场 / OKX星球 三套文案
新闻来源：公开 RSS
风格来源：samples/ 下你保存的热门账号文本
"""

from __future__ import annotations

import re
import statistics
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

import requests

NEWS_FEEDS = [
    "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "https://cointelegraph.com/rss",
    "https://www.theblock.co/rss.xml",
    "https://decrypt.co/feed",
    "https://openai.com/blog/rss.xml",
]

KEYWORDS = {
    "crypto": ["bitcoin", "btc", "ethereum", "eth", "solana", "defi", "etf", "clarity", "crypto", "blockchain", "rwa"],
    "ai": ["ai", "openai", "anthropic", "gpt", "claude", "llm", "agent", "model"],
}

SKIP = ["giveaway", "airdrop code", "保证收益", "稳赚", "必涨"]


@dataclass
class Event:
    title: str
    summary: str
    url: str
    score: float
    tags: list[str]


@dataclass
class Style:
    name: str
    avg_len: int
    emoji_rate: float
    ticker_rate: float
    question_rate: float
    first_lines: list[str]


def clean(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = re.sub(r"https?://\S+", "", text)
    return re.sub(r"\s+", " ", text).strip()


def fetch_rss(url: str) -> list[tuple[str, str, str]]:
    try:
        r = requests.get(url, timeout=20, headers={"User-Agent": "content-desk/1.0"})
        r.raise_for_status()
        root = ET.fromstring(r.content)
    except Exception as exc:
        print(f"RSS 失败 {url}: {exc}")
        return []
    rows = []
    nodes = root.findall(".//item") or root.findall(".//{http://www.w3.org/2005/Atom}entry")
    for node in nodes[:25]:
        title = node.findtext("title") or node.findtext("{http://www.w3.org/2005/Atom}title") or ""
        desc = node.findtext("description") or node.findtext("{http://www.w3.org/2005/Atom}summary") or ""
        link = node.findtext("link") or ""
        if not link:
            n = node.find("{http://www.w3.org/2005/Atom}link")
            link = n.attrib.get("href", "") if n is not None else ""
        rows.append((clean(title), clean(desc), link))
    return rows


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
    if "crypto" in tags and "ai" in tags:
        score += 2.5
    if any(w in blob for w in ["clarity", "etf", "agent", "regulation", "payment"]):
        score += 1.5
    return score, tags


def collect_events() -> list[Event]:
    events = []
    for feed in NEWS_FEEDS:
        for title, summary, url in fetch_rss(feed):
            score, tags = score_event(title, summary)
            if score >= 2:
                events.append(Event(title, summary[:280], url, score, tags))
    events.sort(key=lambda e: e.score, reverse=True)
    # 标题去重
    seen, uniq = set(), []
    for e in events:
        key = e.title[:40]
        if key in seen:
            continue
        seen.add(key)
        uniq.append(e)
    return uniq[:8]


def parse_samples(path: Path) -> list[str]:
    if not path.exists():
        return []
    raw = path.read_text(encoding="utf-8")
    parts = re.split(r"\n\s*\n", raw)
    return [clean(p) for p in parts if len(clean(p)) > 20]


def analyze_style(name: str, posts: list[str]) -> Style:
    if not posts:
        return Style(name, 180, 0.1, 0.3, 0.2, [])
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


def drafts_for(event: Event, styles: dict[str, Style]) -> dict[str, str]:
    fact = event.title
    why = "值得看的不是标题本身，而是它会不会改变资金、监管预期或产品形态。"
    if "ai" in event.tags and "crypto" in event.tags:
        why = "这条新闻的交叉点在于：AI 能力变化，会不会改变链上交易、支付或安全假设。"
    elif "ai" in event.tags:
        why = "先看它对加密行业的外溢：交易执行、代理支付、还是攻击面变大。"
    elif "crypto" in event.tags:
        why = "先把“已发生的事实”和“市场正在定价的预期”分开。"

    x = f"""{fact}

{why}

我现在只盯两个验证点：
1）有没有可重复的数据，而不是单日情绪
2）讨论是在讲机制，还是只在讲价格

不是投资建议。"""

    bn = f"""先说结论：{fact}

对交易者更有用的问题不是“看涨还是看跌”，而是这件事改变了哪一层：
- 监管清晰度
- 资金准入
- 还是产品叙事

{why}

我会继续跟踪原新闻里的关键变量，而不是追一条标题。
数据来源：公开报道。以上为个人观察，不构成投资建议。
$BTC $ETH"""

    okx = f"""刚刷到：{fact}

星球里这类消息最容易被做成口号。我更想先问一句：
盘面上有没有同步变化，还是只有社交热度？

{why}

我先观察，不急着加仓或改方向。
#OKX星球话题来啦
$BTC"""

    return {
        "x": adapt_to_style(x, styles["x"], "x"),
        "binance": adapt_to_style(bn, styles["binance"], "binance"),
        "okx": adapt_to_style(okx, styles["okx"], "okx"),
    }


def main() -> None:
    styles = {
        "x": analyze_style("x", parse_samples(Path("samples/x.txt"))),
        "binance": analyze_style("binance", parse_samples(Path("samples/binance.txt"))),
        "okx": analyze_style("okx", parse_samples(Path("samples/okx.txt"))),
    }
    events = collect_events()
    out = [f"# 三平台选题台 {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}", ""]
    if not events:
        out.append("今天没有抓到足够相关的新闻，检查网络或 RSS。")
    for i, ev in enumerate(events, 1):
        packs = drafts_for(ev, styles)
        out += [
            f"## {i}. {ev.title}",
            f"- 分数：{ev.score} ｜ 标签：{', '.join(ev.tags)}",
            f"- 链接：{ev.url}",
            "",
            "### X",
            packs["x"],
            "",
            "### 币安广场",
            packs["binance"],
            "",
            "### OKX星球",
            packs["okx"],
            "",
            "---",
            "",
        ]
    Path("output").mkdir(exist_ok=True)
    Path("output/three_platforms.md").write_text("\n".join(out), encoding="utf-8")
    print("已生成 output/three_platforms.md")
    print("风格样本：", {k: v.avg_len for k, v in styles.items()})


if __name__ == "__main__":
    main()