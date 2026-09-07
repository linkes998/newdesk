"""
LLM relevance ranker —— 借鉴 PyPush curation/ranker 设计。

在关键词粗筛 + 时效过滤之后，用 LLM 对候选事件做二次 relevance 评分。
关键词匹配能命中"有 crypto/ai 字样"的新闻，但无法区分"值得跟"和"标题党/水稿"。

工作方式：
  1. 批处理（默认 batch_size=4）—— 一次喂 N 条给 LLM，返回 N 个 0-10 分
  2. 降级安全 —— 任何异常自动跳过 rank，回退到纯关键词分
  3. 加权混合 —— final_score = kw_score * W_KW + llm_score * W_LLM
"""
from __future__ import annotations

import json
from typing import Optional

from .config import RANKER_W_KW, RANKER_W_LLM, get_raw
from .llm import build_llm_client
from .models import Event, LLMClient


RANKER_SYSTEM = (
    "你是一位加密货币和 AI 领域的资深编辑。"
    "任务：对一组新闻条目分别打 relevance 分数 0-10。"
    "10 = 重大事件，值得认真生成深度文案；"
    "5 = 有相关性但影响有限；"
    "0 = 标题党、重复旧闻、或与 crypto/ai 无关。"
    "考虑事件的影响力（监管/资金/技术/市场）、时效性、独特性。"
)

RANKER_PROMPT_TEMPLATE = """\
{system}

请为以下 {n} 条新闻分别打 0-10 的 relevance 分数。

{items_text}

严格以 JSON 数组输出，例如：[8, 5, 9, 3]
只输出 JSON，不要任何其他文字。
"""


def _build_batch_prompt(events: list[Event]) -> str:
    lines = []
    for i, ev in enumerate(events, 1):
        age_h = ev.age_hours
        age_str = f"{age_h:.1f}h前" if age_h < 9999 else "时间未知"
        lines.append(f"[{i}] (relevance=?) [{age_str}] score_keywords={ev.score:.1f} tags={ev.tags} | {ev.title[:100]}")
    items_text = "\n".join(lines)
    return RANKER_PROMPT_TEMPLATE.format(
        system=RANKER_SYSTEM,
        n=len(events),
        items_text=items_text,
    )


def _parse_scores(raw: str, expected_n: int) -> Optional[list[float]]:
    """从 LLM 输出中解析出 N 个 0-10 的分数。"""
    raw = raw.strip()
    # 直接尝试 JSON 数组
    try:
        scores = json.loads(raw)
        if isinstance(scores, list) and len(scores) == expected_n:
            return [max(0.0, min(10.0, float(s))) for s in scores]
    except (json.JSONDecodeError, TypeError, ValueError):
        pass
    # 兜底：找 [ ... ] 再试
    try:
        start = raw.find("[")
        end = raw.rfind("]")
        if start >= 0 and end > start:
            scores = json.loads(raw[start:end + 1])
            if isinstance(scores, list) and len(scores) == expected_n:
                return [max(0.0, min(10.0, float(s))) for s in scores]
    except Exception:
        pass
    return None


def rank_batch(events: list[Event], llm_client: LLMClient) -> Optional[list[float]]:
    """给一批事件打分。失败返回 None（由调用方降级）。"""
    if not events:
        return []
    prompt = _build_batch_prompt(events)
    try:
        raw = llm_client.generate(prompt)
    except Exception as exc:
        print(f"  ⚠️  LLM rank batch 失败：{exc}，降级到关键词分")
        return None
    scores = _parse_scores(raw, len(events))
    if scores is None:
        print(f"  ⚠️  LLM rank 输出解析失败：{raw[:80]}...，降级到关键词分")
        return None
    return scores


def _topic_adaptive_weights(events: list[Event], w_kw: float, w_llm: float) -> tuple[float, float]:
    """根据事件类型自适应调整权重。

    思路：
    - 监管/政策类（regulation / SEC / CLARITY）→ LLM 相关性稍降（关键词已足够可靠）
    - 技术更新类（zk / rollup / agent）→ LLM 相关性稍提（技术深度需要 LLM 理解）
    - 价格类（ETF / inflows / price）→ 均衡
    """
    has_tech = any("ai" in e.tags and any(k in e.title.lower() + e.summary.lower()
                                           for k in ["agent", "model", "protocol", "upgrade", "launch", "release", "zk", "rollup"])
                   for e in events)
    has_regulation = any(any(k in e.title.lower() + e.summary.lower()
                            for k in ["sec", "regulation", "clarity", "etf", "approval", "lawsuit", "mica"])
                         for e in events)

    # 轻微调整：±0.1 范围
    if has_tech and not has_regulation:
        return w_kw - 0.1, w_llm + 0.1   # 技术主导 → LLM 权更高
    if has_regulation and not has_tech:
        return w_kw + 0.1, w_llm - 0.1   # 监管主导 → 关键词权更高
    return w_kw, w_llm


def rank_and_merge(events: list[Event]) -> list[Event]:
    """
    主入口。如果配置启用 LLM ranker + LLM 可用，就重排；否则原样返回。
    加权公式：final_score = kw_score * W_KW + (llm_score/10)*10 * W_LLM
    （llm 0-10，关键词 0-10 量级，归一后加权）
    """
    cfg = get_raw()
    if not cfg["llm_ranker"]["enabled"]:
        return events

    client = build_llm_client()
    if client is None:
        print("⚠️  LLM ranker 已启用但无 API Key，降级")
        return events

    batch_size = cfg["llm_ranker"]["batch_size"]
    weight_kw = cfg["llm_ranker"]["weight_keywords"]
    weight_llm = cfg["llm_ranker"]["weight_llm"]

    # 话题自适应权重
    weight_kw, weight_llm = _topic_adaptive_weights(events, weight_kw, weight_llm)

    print(f"🧠 LLM ranker 启用（batch={batch_size}, kw_w={weight_kw:.2f}, llm_w={weight_llm:.2f}）")

    llm_scores: list[Optional[float]] = [None] * len(events)
    for offset in range(0, len(events), batch_size):
        batch = events[offset:offset + batch_size]
        scores = rank_batch(batch, client)
        if scores is not None:
            for j, s in enumerate(scores):
                llm_scores[offset + j] = s
            print(f"  batch [{offset}:{offset + len(batch)}] ✅ {[f'{x:.1f}' for x in scores]}")
        else:
            # 整个 batch 降级
            pass

    for i, ev in enumerate(events):
        llm_s = llm_scores[i]
        if llm_s is not None:
            ev.score = ev.score * weight_kw + llm_s * weight_llm
            print(f"  [{i+1}] {ev.title[:40]} | kw→rank 后 score={ev.score:.2f}")

    events.sort(key=lambda e: e.score, reverse=True)
    return events
