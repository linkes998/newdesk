"""
核心 Pipeline：RSS 抓取 → 评分 → LLM 重排 → 多风格多平台文案生成 → 审核队列 → 可选自动发布。

v0.4.0 变化：
- 引入 templates.StylePreset 替代旧的 style.Style
- 引入 review.ReviewQueue 管理人工审核
- 引入 publisher.PublisherHub 实现自动发布
- 新增 CLI 子命令：review / publish / list-styles
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .config import load_config, MAX_EVENTS, SCORE_THRESHOLD
from .models import Event, LLMClient
from .rss import fetch_rss
from .scoring import collect_events
from .ranker import rank_and_merge
from .llm import build_llm_client
from .templates import (
    STYLE_PRESETS, STYLE_MAP, PLATFORM_META,
    get_style, all_styles, styles_for_platform,
    build_draft_prompt,
)
from .review import ReviewItem, ReviewQueue, ReviewStatus
from .publisher import PublisherHub, PublishResult, PublisherError


# ---------------------------------------------------------------------------
# 文案生成（使用 templates.py 的新系统）
# ---------------------------------------------------------------------------

_TEMPLATE_DRAFTS = {
    "x": lambda title, why, tag: f"""{title}

{why}

我现在只盯两个验证点：
1）有没有可重复的数据，而不是单日情绪
2）讨论是在讲机制，还是只在讲价格

不是投资建议。""",
    "telegram": lambda title, why, tag: f"""📰 {title}

{why}

💡 以上为个人观察，不构成投资建议。{tag}""",
    "discord": lambda title, why, tag: f"""**{title}**

{why}

> 💭 个人观点，不构成投资建议。""",
}


def _pick_why(tags: list[str]) -> str:
    if "ai" in tags and "crypto" in tags:
        return "这条新闻的交叉点在于：AI 能力变化，会不会改变链上交易、支付或安全假设。"
    if "ai" in tags:
        return "先看它对加密行业的外溢：交易执行、代理支付、还是攻击面变大。"
    if "crypto" in tags:
        return '先把"已发生的事实"和"市场正在定价的预期"分开。'
    return "值得看的不是标题本身，而是它会不会改变资金、监管预期或产品形态。"


def _build_tag_line(tags: list[str]) -> str:
    if "crypto" in tags:
        return "\n$BTC $ETH"
    return ""


def _template_fallback(event: Event, platform: str) -> str:
    """LLM 不可用时的模板降级。"""
    why = _pick_why(event.tags)
    tag = _build_tag_line(event.tags)
    fn = _TEMPLATE_DRAFTS.get(platform, _TEMPLATE_DRAFTS["x"])
    return fn(event.title, why, tag)


def _truncate_to_platform(text: str, platform: str) -> str:
    """按平台限制截断。"""
    max_chars = PLATFORM_META.get(platform, {}).get("max_chars", 5000)
    if len(text) > max_chars:
        text = text[: max_chars - 8] + "\n\n…（已截断）"
    return text.strip()


def generate_drafts(
    event: Event,
    *,
    llm_client: Optional[LLMClient] = None,
    style_key: str = "professional",
    language: str = "zh",
    platforms: list[str] | None = None,
    user_hint: str = "",
) -> dict[str, str]:
    """为一条事件生成多平台文案。

    返回 {platform_key: text} dict。
    """
    style = get_style(style_key) or STYLE_MAP.get("professional")
    if style is None:
        # 兜底
        from .templates import StylePreset
        style = StylePreset("professional", "默认", "", 400, 0.1, True, False, "professional")

    target_platforms = platforms or list(style.platforms)

    drafts: dict[str, str] = {}
    for platform in target_platforms:
        if llm_client is not None:
            prompt = build_draft_prompt(
                event.title, event.summary, event.url,
                style=style,
                platform=platform,
                language=language,
                user_hint=user_hint,
            )
            try:
                raw = llm_client.generate(prompt)
            except Exception as exc:
                print(f"  LLM 生成失败 [{platform}]：{exc}，回退模板")
                raw = _template_fallback(event, platform)
        else:
            raw = _template_fallback(event, platform)

        drafts[platform] = _truncate_to_platform(raw, platform)

    return drafts


# ---------------------------------------------------------------------------
# ReviewItem 工厂（从 Event 构建审核条目）
# ---------------------------------------------------------------------------

def make_review_item(event: Event, drafts: dict[str, str]) -> ReviewItem:
    """从 Event + 文案集合构造 ReviewItem。"""
    import hashlib
    item_id = hashlib.sha256(f"{event.title}|{event.url}".encode()).hexdigest()[:16]
    return ReviewItem(
        item_id=item_id,
        event_title=event.title,
        event_url=event.url,
        event_summary=event.summary,
        event_score=event.score,
        event_tags=event.tags.copy(),
        drafts=dict(drafts),
    )


# ---------------------------------------------------------------------------
# 主 Pipeline
# ---------------------------------------------------------------------------

def run_pipeline(
    *,
    llm_mode: bool = True,
    style_key: str | None = None,
    language: str | None = None,
    platforms: list[str] | None = None,
    auto_publish: bool | None = None,
) -> list[ReviewItem]:
    """执行完整流水线，返回 ReviewItem 列表。"""
    cfg = load_config()
    content_cfg = cfg.get("content", {})

    style_key = style_key or content_cfg.get("default_style", "professional")
    language = language or content_cfg.get("language", "zh")
    target_platforms = platforms or content_cfg.get("target_platforms", ["x", "telegram", "discord"])
    user_hint = content_cfg.get("user_hint", "")
    auto_publish = auto_publish if auto_publish is not None else content_cfg.get("auto_publish", False)

    print(f"\n{'='*60}")
    print(f"📰 NewsDesk Pipeline — {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}")
    print(f"{'='*60}")
    print(f"  风格: {style_key}  语言: {language}  平台: {target_platforms}")
    print(f"  自动发布: {'是' if auto_publish else '否（进审核队列）'}")

    # --- Step 1: 抓取 ---
    print(f"\n[1/4] 抓取 RSS 源...")
    feeds = cfg["feeds"]
    all_raw: list[tuple[str, str, str, object]] = []
    for feed_url in feeds:
        try:
            rows = fetch_rss(feed_url)
            all_raw.extend(rows)
            print(f"  ✓ {feed_url[:50]}... → {len(rows)} 条")
        except Exception as exc:
            print(f"  ✗ {feed_url[:50]}... 失败: {exc}")

    print(f"  共抓到 {len(all_raw)} 条原始文章")

    # --- Step 2: 评分 + LLM 重排 ---
    print(f"\n[2/4] 评分 + 重排...")
    events = collect_events()
    events = rank_and_merge(events)

    events = events[:MAX_EVENTS]
    print(f"  筛选后 {len(events)} 条（评分≥{SCORE_THRESHOLD}）")

    if not events:
        print("  ⚠️  没有符合条件的新闻，本轮结束")
        return []

    # --- Step 3: 生成文案 ---
    print(f"\n[3/4] 生成文案（{'LLM' if llm_mode else '模板'}模式）...")
    llm_client = build_llm_client() if llm_mode else None
    if llm_mode and llm_client is None:
        print("  ⚠️  LLM 未配置，降级到模板模式")

    review_items: list[ReviewItem] = []
    for i, ev in enumerate(events):
        print(f"  [{i+1}/{len(events)}] {ev.title[:60]}")
        drafts = generate_drafts(
            ev,
            llm_client=llm_client,
            style_key=style_key,
            language=language,
            platforms=target_platforms,
            user_hint=user_hint,
        )
        item = make_review_item(ev, drafts)
        review_items.append(item)

    # --- Step 4: 审核/发布 ---
    print(f"\n[4/4] 进入审核流程...")
    queue = ReviewQueue(path=cfg.get("paths", {}).get("data_dir", "data") + "/review_queue.json")
    queue.add_batch(review_items)
    queue.save()
    print(f"  ✓ {len(review_items)} 条已加入审核队列")

    # 自动发布（如果配置了）
    if auto_publish:
        _auto_publish_approved(review_items, cfg)

    # 输出摘要
    _print_summary(review_items)
    return review_items


def _auto_publish_approved(items: list[ReviewItem], cfg: dict) -> None:
    """自动发布所有已批准（或直接通过）的条目。"""
    hub = PublisherHub.from_config(cfg.get("publisher", {}))
    available = hub.available_platforms()
    if not available:
        print("  ⚠️  auto_publish=True 但未配置任何发布凭证，跳过")
        return

    print(f"\n  🚀 自动发布到: {available}")
    for item in items:
        for platform, text in item.drafts.items():
            if platform not in available:
                continue
            result = hub.publish_to(platform, text)
            if result.success:
                item.mark_published(platform, result.__dict__)
                print(f"    ✓ [{platform}] {item.item_id[:8]} → {result.external_id}")
            else:
                print(f"    ✗ [{platform}] {item.item_id[:8]} → {result.error}")
        # 自动批准（跳过人工审核）
        if item.status == ReviewStatus.PENDING.value:
            try:
                item.approve(note="auto_publish")
            except ValueError:
                pass


def _print_summary(items: list[ReviewItem]) -> None:
    print(f"\n{'='*60}")
    print(f"📋 本轮摘要（{len(items)} 条）")
    print(f"{'='*60}")
    for i, item in enumerate(items, 1):
        platforms = ", ".join(item.drafts.keys())
        print(f"  {i}. [{item.status.upper()}] {item.event_title[:55]}")
        print(f"     平台: {platforms}")
    print(f"\n💡 提示：运行 `newsdesk review` 进入交互式审核中心")


# ---------------------------------------------------------------------------
# 向后兼容层 —— 旧函数名 / 旧平台名（v0.3 → v0.4）
# ---------------------------------------------------------------------------

def _template_draft(event: Event, platform: str) -> str:
    """旧版模板降级函数 —— 兼容旧测试（必须保留 binance/okx 旧模板）。"""
    fact = event.title
    why = _pick_why(event.tags)

    if platform == "x":
        return f"""{fact}

{why}

我现在只盯两个验证点：
1）有没有可重复的数据，而不是单日情绪
2）讨论是在讲机制，还是只在讲价格

不是投资建议。"""

    if platform == "binance":
        return f"""先说结论：{fact}

对交易者更有用的问题不是"看涨还是看跌"，而是这件事改变了哪一层：
- 监管清晰度
- 资金准入
- 还是产品叙事

{why}

我会继续跟踪原新闻里的关键变量，而不是追一条标题。
数据来源：公开报道。以上为个人观察，不构成投资建议。
$BTC $ETH"""

    if platform == "okx":
        return f"""刚刷到：{fact}

星球里这类消息最容易被做成口号。我更想先问一句：
盘面上有没有同步变化，还是只有社交热度？

{why}

我先观察，不急着加仓或改方向。
#OKX星球话题来啦
$BTC"""

    # 其他平台走新模板
    return _template_fallback(event, platform)


def drafts_for(event, styles, *, llm_client=None):
    """旧版 drafts_for —— 兼容旧测试。"""
    # 旧平台名映射到新平台
    platform_map = {
        "x": "x",
        "binance": "telegram",
        "okx": "discord",
    }
    # 反过来把新平台结果再映射回去
    result_new = generate_drafts(event, llm_client=llm_client, platforms=list(platform_map.values()))
    result = {}
    for old_plat, new_plat in platform_map.items():
        result[old_plat] = result_new.get(new_plat, "")
    return result


# ---------------------------------------------------------------------------
# CLI 入口
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="newsdesk",
        description="NewsDesk · 加密/AI 新闻 → 多平台文案自动化",
    )
    sub = parser.add_subparsers(dest="command")

    # --- run ---
    p_run = sub.add_parser("run", help="执行完整流水线")
    p_run.add_argument("--cli", action="store_true", help="命令行模式（跳过 GUI）")
    p_run.add_argument("--no-llm", action="store_true", help="禁用 LLM，只用模板")
    p_run.add_argument("--style", default=None, help="风格 key（运行 `list-styles` 查看）")
    p_run.add_argument("--lang", default=None, choices=["zh", "en", "auto"], help="输出语言")
    p_run.add_argument("--platforms", default=None, help="目标平台，逗号分隔")
    p_run.add_argument("--auto-publish", action="store_true", help="直接发布（跳过审核）")

    # --- list-styles ---
    sub.add_parser("list-styles", help="列出所有预置风格")

    # --- review ---
    sub.add_parser("review", help="进入交互式审核中心")

    # --- publish ---
    p_pub = sub.add_parser("publish", help="立即发布所有已批准条目")
    p_pub.add_argument("--platforms", default=None, help="指定平台，逗号分隔")

    # --- export ---
    p_exp = sub.add_parser("export", help="导出审核队列为 Newsletter / Markdown / JSON / RSS")
    p_exp.add_argument("--format", default="markdown",
                       choices=["markdown", "html", "beehiiv", "substack", "quaily", "json", "rss"],
                       help="导出格式")
    p_exp.add_argument("--status", default=None, help="按状态过滤（approved/pending/rejected）")
    p_exp.add_argument("--output", default=None, help="输出文件路径（否则打印到屏幕）")
    p_exp.add_argument("--title", default=None, help="Newsletter 标题")

    # --- video ---
    p_vid = sub.add_parser("video", help="为已抓取新闻生成短视频脚本（JSON）")
    p_vid.add_argument("--count", type=int, default=3, help="生成多少条视频脚本")
    p_vid.add_argument("--output", default=None, help="输出文件路径")
    p_vid.add_argument("--no-llm", action="store_true", help="禁用 LLM，只用模板")

    # --- list-exports ---
    sub.add_parser("list-exports", help="列出所有可用的导出格式")

    args = parser.parse_args()

    if args.command is None:
        # 默认启动 GUI
        try:
            from .gui import NewsDeskApp
            print("启动 GUI... (传 --cli 走命令行)")
            app = NewsDeskApp()
            app.mainloop()
            return
        except ImportError:
            print("GUI 不可用，回退到 CLI。使用 `newsdesk run`")
            args.command = "run"
            args.cli = True
            # fallback 补齐 run 子命令的默认属性（argparse 只在显式 parse run 时创建这些属性）
            for _attr, _default in [
                ("cli", True), ("no_llm", False), ("style", None),
                ("lang", None), ("platforms", None), ("auto_publish", False),
            ]:
                if not hasattr(args, _attr):
                    setattr(args, _attr, _default)

    if args.command == "run":
        # 全部用 getattr 安全取值，兼容 fallback 路径
        _platforms_raw = getattr(args, "platforms", None)
        platforms = _platforms_raw.split(",") if _platforms_raw else None
        run_pipeline(
            llm_mode=not getattr(args, "no_llm", False),
            style_key=getattr(args, "style", None),
            language=getattr(args, "lang", None),
            platforms=platforms,
            auto_publish=getattr(args, "auto_publish", False),
        )

    elif args.command == "list-styles":
        print("\n📚 NewsDesk 预置风格（10 种）\n")
        for s in STYLE_PRESETS:
            platforms = ", ".join(s.platforms)
            print(f"  {s.key:20s} {s.label:16s}  len={s.target_len}  emoji={s.emoji_rate}  [{platforms}]")
            print(f"    {s.description}")
            print()

    elif args.command == "review":
        from .review import run_interactive_review
        run_interactive_review()

    elif args.command == "publish":
        cfg = load_config()
        queue = ReviewQueue(path=cfg.get("paths", {}).get("data_dir", "data") + "/review_queue.json")
        queue.load()
        approved = queue.by_status(ReviewStatus.APPROVED)
        if not approved:
            print("没有已批准的条目可以发布")
            return
        hub = PublisherHub.from_config(cfg.get("publisher", {}))
        available = hub.available_platforms()
        if not available:
            print("未配置任何发布凭证")
            return

        target = args.platforms.split(",") if args.platforms else available
        print(f"\n🚀 发布 {len(approved)} 条到 {target}")
        for item in approved:
            for platform, text in item.drafts.items():
                if platform not in target:
                    continue
                result = hub.publish_to(platform, text)
                if result.success:
                    item.mark_published(platform, result.__dict__)
                    print(f"  ✓ [{platform}] {item.item_id[:8]} → {result.external_id}")
                else:
                    print(f"  ✗ [{platform}] {item.item_id[:8]} → {result.error}")
        queue.save()

    elif args.command == "export":
        from .export import export_queue
        cfg = load_config()
        queue_path = cfg.get("paths", {}).get("data_dir", "data") + "/review_queue.json"
        result = export_queue(
            fmt=args.format,
            queue_path=queue_path,
            status=args.status,
            output_path=args.output,
            title=args.title or "NewsDesk 每日精选",
        )
        if args.output is None:
            print(result[:500] + ("..." if len(result) > 500 else ""))

    elif args.command == "list-exports":
        print("""
📦 NewsDesk 支持的导出格式：

  markdown    — 通用 Markdown，适合本地阅读
  html        — 粘贴式 HTML，Beehiiv / Substack 直接可用
  beehiiv     — 同 html（别名，语义更清晰）
  substack    — 同 html（别名，语义更清晰）
  quaily      — Quaily 社区格式（要点 + 深度链接）
  json        — 结构化 JSON，外部程序可消费
  rss         — RSS 2.0 XML，可自托管供下游订阅

用法：
  newsdesk export --format quaily --output today.md
  newsdesk export --format beehiiv --output newsletter.html
  newsdesk export --format json --status approved --output drafts.json
        """.strip())

    elif args.command == "video":
        from .video import generate_video_script, generate_video_script_template
        cfg = load_config()
        queue_path = cfg.get("paths", {}).get("data_dir", "data") + "/review_queue.json"
        queue = ReviewQueue(path=queue_path)
        queue.load()

        approved = queue.by_status(ReviewStatus.APPROVED) or queue.pending()
        if not approved:
            print("审核队列为空，先运行 `newsdesk run`")
            return

        client = build_llm_client() if not args.no_llm else None

        scripts_json = []
        scripts_md_parts = [f"# 🎬 短视频脚本集\n自动生成 · {len(approved)} 条\n"]

        for item in approved[:args.count]:
            # ReviewItem → Event
            ev = Event(
                title=item.event_title,
                summary=item.event_summary,
                url=item.event_url,
                score=item.event_score,
                tags=item.event_tags,
            )
            script = generate_video_script(ev, llm_client=client)
            scripts_json.append({
                "event": item.event_title,
                "script": script.to_dict(),
            })
            scripts_md_parts.append(script.to_markdown())
            scripts_md_parts.append("---\n")

        output_md = "\n".join(scripts_md_parts)
        if args.output:
            out_path = args.output
            Path(out_path).parent.mkdir(parents=True, exist_ok=True)
            if out_path.endswith(".json"):
                import json as _json
                Path(out_path).write_text(_json.dumps(scripts_json, ensure_ascii=False, indent=2), encoding="utf-8")
            else:
                Path(out_path).write_text(output_md, encoding="utf-8")
            print(f"✓ 短视频脚本已生成 → {out_path}")
        else:
            print(output_md[:1500] + ("..." if len(output_md) > 1500 else ""))


if __name__ == "__main__":
    main()
