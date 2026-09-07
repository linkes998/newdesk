"""
导出模块 —— 将审核好的文案导出为 Newsletter / Markdown / JSON 格式。

支持格式：
- beehiiv  / substack  : HTML（粘贴到编辑器）
- quaily  : Markdown（适配社区格式）
- markdown : 通用 Markdown
- json   : 结构化 JSON，供外部程序消费
- rss    : RSS 2.0 XML（可自托管 feed）
"""
from __future__ import annotations

import json
import html
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .review import ReviewItem, ReviewQueue, ReviewStatus


# ---------------------------------------------------------------------------
# 内部工具
# ---------------------------------------------------------------------------

def _escape(text: str) -> str:
    return html.escape(text or "", quote=False)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _now_rfc822() -> str:
    return datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")


# ---------------------------------------------------------------------------
# Markdown（通用 + Newsletter 风格）
# ---------------------------------------------------------------------------

def export_markdown(items: list[ReviewItem], *, style: str = "newsletter", title: str = "") -> str:
    """导出 Markdown。style 可选 newsletter / minimal / thread。"""
    now = datetime.now(timezone.utc)
    out: list[str] = [
        f"# {title or 'NewsDesk 每日精选'} — {now:%Y-%m-%d}",
        "",
        f"> 自动生成 · {now:%H:%M UTC} · 共 {len(items)} 条",
        "",
    ]

    for i, item in enumerate(items, 1):
        if item.status == ReviewStatus.REJECTED.value:
            continue
        out.append(f"## {i}. {item.event_title}")
        out.append(f"*分数: {item.event_score:.1f} ｜ 标签: {', '.join(item.event_tags[:3])} ｜ [原文]({item.event_url})*")
        out.append("")

        if style == "newsletter":
            out.append(f"**摘要：** {item.event_summary[:200]}")
            out.append("")

        # 取 telegram 平台的文案作为 Newsletter 主体（通常长度最合适）
        draft = item.drafts.get("telegram") or item.drafts.get("discord") or item.drafts.get("x", "")
        if draft:
            out.append(draft)
            out.append("")

        # 附加其他平台
        other_plats = [p for p in item.drafts if p not in ("telegram", "discord")]
        if other_plats and style != "minimal":
            out.append("<details><summary>其他平台文案</summary>")
            out.append("")
            for p in other_plats:
                out.append(f"**{p}**: {item.drafts[p][:150]}...")
            out.append("")
            out.append("</details>")

        out.append("---")
        out.append("")

    return "\n".join(out)


# ---------------------------------------------------------------------------
# HTML（Beehiiv / Substack 粘贴式）
# ---------------------------------------------------------------------------

def export_html(items: list[ReviewItem], *, title: str = "") -> str:
    """导出 HTML，可直接粘贴到 Beehiiv / Substack 编辑器。"""
    now = datetime.now(timezone.utc)
    body: list[str] = [
        f"""<div style="max-width:640px;margin:0 auto;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
<h2 style="color:#1a1a1a;border-bottom:2px solid #58a6ff;padding-bottom:8px;">
{_escape(title or 'NewsDesk 每日精选')}
</h2>
<p style="color:#666;font-size:13px;">
自动生成 · {now:%Y-%m-%d %H:%M UTC} · 共 {len(items)} 条
</p>""",
    ]

    for i, item in enumerate(items, 1):
        if item.status == ReviewStatus.REJECTED.value:
            continue
        draft = item.drafts.get("telegram") or item.drafts.get("discord") or item.drafts.get("x", "")
        body.append(f"""
<article style="margin:24px 0;padding:16px;background:#f6f8fa;border-radius:8px;">
<h3 style="margin:0 0 8px 0;color:#0969da;font-size:16px;">
{i}. {_escape(item.event_title)}
</h3>
<p style="color:#666;font-size:12px;margin:4px 0 12px 0;">
分数 {item.event_score:.1f} ｜ {', '.join(item.event_tags[:3])} ｜ 
<a href="{_escape(item.event_url)}" style="color:#0969da;">原文</a>
</p>
<div style="white-space:pre-wrap;line-height:1.7;color:#1a1a1a;font-size:14px;">
{_escape(draft)}
</div>
</article>""")

    body.append("</div>")
    return "\n".join(body)


# ---------------------------------------------------------------------------
# Quaily Markdown（适配社区格式）
# ---------------------------------------------------------------------------

def export_quaily(items: list[ReviewItem], *, title: str = "") -> str:
    """Quaily 格式：短标题 + 核心要点 + 深度链接。"""
    now = datetime.now(timezone.utc)
    out: list[str] = [
        f"# {title or '📰 今日加密/AI 精选'}",
        f"> 自动生成 · {now:%Y-%m-%d %H:%M UTC}",
        "",
        "---",
        "",
    ]

    for i, item in enumerate(items, 1):
        if item.status == ReviewStatus.REJECTED.value:
            continue
        draft = item.drafts.get("telegram") or item.drafts.get("discord") or item.drafts.get("x", "")
        # 提取核心要点（取前 2 行）
        lines = [l for l in draft.split("\n") if l.strip()]
        key_points = lines[:3] if len(lines) >= 3 else lines

        out.append(f"## {i}. {item.event_title}")
        out.append("")
        out.append(f"**标签**：{', '.join(item.event_tags[:3])}")
        out.append("")
        out.append("**核心要点**：")
        for kp in key_points:
            out.append(f"- {kp}")
        out.append("")
        out.append(f"**深度阅读**：[{item.event_title}]({item.event_url})")
        out.append("")
        out.append("---")
        out.append("")

    return "\n".join(out)


# ---------------------------------------------------------------------------
# JSON（结构化）
# ---------------------------------------------------------------------------

def export_json(items: list[ReviewItem], *, indent: int = 2) -> str:
    """导出结构化 JSON，外部程序可直接消费。"""
    data = {
        "generated_at": _now_iso(),
        "total": len(items),
        "items": [
            {
                "item_id": it.item_id,
                "title": it.event_title,
                "url": it.event_url,
                "score": it.event_score,
                "tags": it.event_tags,
                "status": it.status,
                "drafts": it.drafts,
                "history": it.history[-5:],
                "publish_results": it.publish_results,
            }
            for it in items if it.status != ReviewStatus.REJECTED.value
        ],
    }
    return json.dumps(data, ensure_ascii=False, indent=indent)


# ---------------------------------------------------------------------------
# RSS 2.0 XML
# ---------------------------------------------------------------------------

def export_rss(items: list[ReviewItem], *, feed_url: str = "", channel_title: str = "NewsDesk") -> str:
    """生成 RSS 2.0 XML。可自托管供下游订阅。"""
    pub_date = _now_rfc822()
    item_xml_parts: list[str] = []
    for it in items:
        if it.status == ReviewStatus.REJECTED.value:
            continue
        draft = it.drafts.get("telegram") or it.drafts.get("discord") or ""
        item_xml_parts.append(f"""
  <item>
    <title>{_escape(it.event_title)}</title>
    <link>{_escape(it.event_url)}</link>
    <guid isPermaLink="true">{_escape(it.event_url)}</guid>
    <pubDate>{pub_date}</pubDate>
    <description><![CDATA[{_escape(draft or it.event_summary)}]]></description>
    <category>{', '.join(it.event_tags[:3])}</category>
  </item>""")

    items_xml = "".join(item_xml_parts)

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>{_escape(channel_title)}</title>
    <link>{_escape(feed_url)}</link>
    <description>NewsDesk 自动生成：加密货币 / AI 领域每日精选</description>
    <language>zh-cn</language>
    <lastBuildDate>{pub_date}</lastBuildDate>
{items_xml}
  </channel>
</rss>"""


# ---------------------------------------------------------------------------
# 统一入口
# ---------------------------------------------------------------------------

_FORMATTERS = {
    "markdown": export_markdown,
    "html": export_html,
    "beehiiv": export_html,   # Beehiiv 粘贴格式
    "substack": export_html,  # Substack 粘贴格式
    "quaily": export_quaily,
    "json": export_json,
    "rss": export_rss,
}


def export(
    fmt: str,
    items: list[ReviewItem],
    *,
    output_path: str | Path | None = None,
    **kw,
) -> str:
    """统一导出入口。

    参数：
        fmt: markdown / html / beehiiv / substack / quaily / json / rss
        items: ReviewItem 列表
        output_path: 指定则写文件，否则返回字符串
    """
    fmt = fmt.lower()
    if fmt not in _FORMATTERS:
        raise ValueError(f"未知导出格式 '{fmt}'，可选：{list(_FORMATTERS.keys())}")

    content = _FORMATTERS[fmt](items, **kw)

    if output_path is not None:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        print(f"  ✓ 导出 {fmt} → {path} ({len(content)} 字节)")

    return content


def export_queue(
    fmt: str,
    queue_path: str | Path,
    *,
    status: str | None = None,
    output_path: str | Path | None = None,
    **kw,
) -> str:
    """从审核队列文件直接导出。"""
    queue = ReviewQueue(path=queue_path)
    queue.load()
    if status:
        items = queue.by_status(status)
    else:
        items = queue.all()
    return export(fmt, items, output_path=output_path, **kw)
