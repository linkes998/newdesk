"""
LLM Ranker 端到端测试脚本 —— Agnes AI + newsdesk 完整流水线对比。

用法 1：从 config.yaml 读取 api_key（直接填到文件里）
  python scripts/test_ranker.py

用法 2：命令行传 key（不写进文件）
  python scripts/test_ranker.py --key sk-your-agnes-key

用法 3：先测连通性再跑 ranker（推荐）
  python scripts/test_ranker.py --ping
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone

# 确保 src/ 在路径
from pathlib import Path
_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from newsdesk.config import load_config  # noqa
from newsdesk.llm import OpenAIClient  # noqa
from newsdesk.models import Event  # noqa
from newsdesk.ranker import rank_batch, rank_and_merge, _build_batch_prompt  # noqa
from newsdesk.scoring import collect_events, score_event  # noqa


def test_ping(api_key: str, base_url: str, model: str) -> None:
    """连通性测试：发一个极小请求验证 key/URL/model 都对。"""
    print(f"📡 连通性测试")
    print(f"   Base URL : {base_url}")
    print(f"   Model    : {model}")
    print(f"   API Key  : {api_key[:6]}...{api_key[-4:] if len(api_key) > 10 else ''}")
    try:
        client = OpenAIClient(api_key=api_key, base_url=base_url, model=model)
        start = datetime.now(timezone.utc)
        reply = client.generate("Reply with exactly: OK", model=model)
        elapsed = (datetime.now(timezone.utc) - start).total_seconds()
        print(f"   ✅ 连通！回复：{reply.strip()[:50]}   ⏱ {elapsed:.2f}s")
    except Exception as exc:
        print(f"   ❌ 失败：{exc}")
        sys.exit(1)


def test_prompt_smoke(api_key: str, base_url: str, model: str) -> None:
    """给 4 条假新闻，看 ranker prompt 输出格式对不对。"""
    print(f"\n🧪 Prompt smoke test（4 条假新闻）")
    fake = [
        Event(title="Bitcoin ETF approved, SEC clears final hurdle", summary="", url="", score=6.5, tags=["crypto"], age_hours=2.1, published_at=None),
        Event(title="New open-source AI agent framework released on GitHub", summary="", url="", score=4.2, tags=["ai"], age_hours=0.8, published_at=None),
        Event(title="Local bakery opens second location downtown", summary="", url="", score=2.0, tags=[], age_hours=5.5, published_at=None),
        Event(title="Major exchange announces RWA tokenization partnership", summary="", url="", score=7.0, tags=["crypto", "ai"], age_hours=1.2, published_at=None),
    ]
    client = OpenAIClient(api_key=api_key, base_url=base_url, model=model)
    prompt = _build_batch_prompt(fake)
    print(f"   Prompt 长度：{len(prompt)} chars")
    start = datetime.now(timezone.utc)
    result = rank_batch(fake, client)
    elapsed = (datetime.now(timezone.utc) - start).total_seconds()
    if result is None:
        print(f"   ❌ 解析失败，LLM 原始输出已打印在上方日志里，{elapsed:.1f}s")
    else:
        print(f"   ✅ 成功解析！scores = {[round(s,1) for s in result]}   ⏱ {elapsed:.1f}s")
        for i, ev in enumerate(fake):
            print(f"   [{i+1}] kw_score={ev.score:4.1f} → llm_relevance={result[i]:.1f} | {ev.title[:55]}")


def test_full_pipeline(api_key: str, base_url: str, model: str) -> None:
    """真实抓取 → 对比有/无 ranker 的分数差异。"""
    print(f"\n🚀 完整流水线测试")

    from newsdesk.rss import fetch_rss, _age_hours
    from newsdesk.config import NEWS_FEEDS, MAX_AGE_HOURS, SCORE_THRESHOLD

    print("   Step 1: RSS 抓取 + 关键词评分...")
    events_kw_only = collect_events()
    if not events_kw_only:
        print("   ⚠️  没抓到任何时效内的新闻，跳过完整测试")
        return

    print(f"   关键词粗筛结果：{len(events_kw_only)} 条")
    for i, ev in enumerate(events_kw_only, 1):
        pub = ev.published_at.strftime('%m-%d %H:%M') if ev.published_at else '未知'
        print(f"     [{i}] kw={ev.score:4.1f} [{ev.age_hours:.1f}h] [{pub}] {ev.title[:55]}")

    # 做一份副本跑 ranker（避免修改原对象）
    from dataclasses import replace
    events_with_rank = [replace(ev) for ev in events_kw_only]

    print(f"\n   Step 2: LLM ranker（{len(events_with_rank)} 条，batch=4）...")
    client = OpenAIClient(api_key=api_key, base_url=base_url, model=model)

    # 手动调 rank_batch 看过程
    batch_size = 4
    llm_scores: list[float | None] = [None] * len(events_with_rank)
    for offset in range(0, len(events_with_rank), batch_size):
        batch = events_with_rank[offset:offset + batch_size]
        print(f"     batch [{offset+1}:{offset+len(batch)}] ...", end=" ", flush=True)
        scores = rank_batch(batch, client)
        if scores is None:
            print("❌ 降级（解析失败）")
        else:
            for j, s in enumerate(scores):
                llm_scores[offset + j] = s
            print(f"✅ {[f'{x:.1f}' for x in scores]}")

    weight_kw = 0.4
    weight_llm = 0.6
    print(f"\n   Step 3: 加权混合（kw={weight_kw}, llm={weight_llm}）+ 排序")
    print(f"   {'#':>3}  {'kw_score':>8}  {'llm_rel':>8}  {'final':>8}  {'标题'}")
    print(f"   {'─'*3}  {'─'*8}  {'─'*8}  {'─'*8}  {'─'*55}")

    for i, ev in enumerate(events_with_rank):
        llm_s = llm_scores[i]
        if llm_s is not None:
            ev.score = ev.score * weight_kw + llm_s * weight_llm
        print(f"   [{i+1:>2}]  {events_kw_only[i].score:>8.2f}  {(llm_s if llm_s is not None else '—'):>8}  {ev.score:>8.2f}  {ev.title[:55]}")

    events_with_rank.sort(key=lambda e: e.score, reverse=True)

    print(f"\n   🏁 重排后顺序变化：")
    orig_order = [e.title[:40] for e in events_kw_only]
    new_order = [e.title[:40] for e in events_with_rank]
    changed = [(i + 1, orig, new) for i, (orig, new) in enumerate(zip(orig_order, new_order)) if orig != new]
    if not changed:
        print("      与 kw-only 排序相同（说明关键词分已经很准，或 ranker 打平）")
    else:
        for pos, o, n in changed:
            print(f"      #{pos}: 原来是 '{o}' → 现在是 '{n}'")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--key", help="Agnes AI API Key（如果 config.yaml 里已填可省略）")
    ap.add_argument("--ping", action="store_true", help="只测连通性，不跑完整流水线")
    ap.add_argument("--prompt", action="store_true", help="只测 ranker prompt 格式")
    ap.add_argument("--full", action="store_true", help="跑完整流水线对比")
    args = ap.parse_args()

    cfg = load_config()
    api_key = args.key or cfg["llm"]["api_key"]
    base_url = cfg["llm"]["base_url"]
    model = cfg["llm"]["model"]

    if not api_key:
        print("❌ API Key 缺失。要么填在 config.yaml 的 llm.api_key，要么用 --key 参数传。")
        sys.exit(1)

    if args.ping:
        test_ping(api_key, base_url, model)
        return

    if args.prompt:
        test_ping(api_key, base_url, model)
        test_prompt_smoke(api_key, base_url, model)
        return

    # 默认：先 ping，再完整
    test_ping(api_key, base_url, model)
    test_prompt_smoke(api_key, base_url, model)
    test_full_pipeline(api_key, base_url, model)


if __name__ == "__main__":
    main()
