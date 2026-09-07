"""
短视频脚本生成器 —— 将新闻转化为 TikTok / YouTube Shorts 口播脚本。

输出结构（JSON + Markdown 双格式）：
{
  "hook":      "3 秒钩子 —— 一句话抓住注意力",
  "segments":  [
      {"time": "0:03-0:08", "visual": "画面描述", "voiceover": "口播文案"},
      ...
  ],
  "cta":       "行动号召（结尾引导关注）",
  "hashtags":  ["#Bitcoin", "#ETF", "#CryptoNews"],
  "duration_s": 28,
}

设计原则：
- 钩子在前 3 秒必须有"反常识"或"高收益暗示"
- 每 5 秒一个画面切换，适配短视频节奏
- 口播文案 150-200 字（正常语速 ≈ 30 秒）
- 兼容模板降级（LLM 不可用时用规则生成）
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, asdict
from typing import Optional

from .models import Event, LLMClient
from .templates import PLATFORM_META


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------

@dataclass
class VideoSegment:
    time: str                      # "0:03-0:08"
    visual: str                    # 画面描述
    voiceover: str                 # 口播文案


@dataclass
class VideoScript:
    hook: str                      # 钩子（前 3 秒）
    segments: list[VideoSegment] = field(default_factory=list)
    cta: str = ""                  # 结尾行动号召
    hashtags: list[str] = field(default_factory=list)
    duration_s: int = 30

    def to_dict(self) -> dict:
        return {
            "hook": self.hook,
            "segments": [asdict(s) for s in self.segments],
            "cta": self.cta,
            "hashtags": self.hashtags,
            "duration_s": self.duration_s,
        }

    def to_markdown(self) -> str:
        out: list[str] = [
            f"# 🎬 短视频脚本（≈ {self.duration_s}s）",
            "",
            f"**🎣 钩子（0:00-0:03）** {self.hook}",
            "",
        ]
        for seg in self.segments:
            out.append(f"**{seg.time}**")
            out.append(f"- 🖼️ 画面：{seg.visual}")
            out.append(f"- 🎙️ 口播：{seg.voiceover}")
            out.append("")
        if self.cta:
            out.append(f"**🎯 CTA** {self.cta}")
            out.append("")
        if self.hashtags:
            out.append(" ".join(self.hashtags))
        return "\n".join(out)


# ---------------------------------------------------------------------------
# LLM 生成
# ---------------------------------------------------------------------------

VIDEO_SYSTEM_PROMPT = (
    "你是一位短视频口播脚本编剧，擅长将新闻转化为 30 秒以内的 TikTok/YouTube Shorts 脚本。"
    "核心原则：前 3 秒必须用钩子抓住观众，每 5 秒切换画面，口播清晰有力。"
)

VIDEO_PROMPT_TEMPLATE = """\
{system}

为以下新闻生成一条短视频脚本：

【新闻】
标题：{title}
摘要：{summary}
标签：{tags}

【输出要求】
- 前 3 秒钩子（hook）必须是反常识、数字冲击、或高悬念
- 总时长约 30 秒，分 5-7 个画面段落
- 每段格式：时间段 / 画面描述 / 口播文案
- 结尾加 CTA（引导关注、点赞、评论）
- 加 3-5 个相关 hashtag

严格以 JSON 格式输出（不要 markdown 代码块）：
{{
  "hook": "一句话钩子",
  "segments": [
    {{"time": "0:00-0:03", "visual": "画面描述", "voiceover": "口播文案"}},
    ...
  ],
  "cta": "行动号召",
  "hashtags": ["#tag1", "#tag2", "#tag3"]
}}
"""


def _parse_script_json(raw: str) -> Optional[VideoScript]:
    """从 LLM 输出解析脚本。"""
    raw = raw.strip()
    # 去除 markdown 代码块
    if raw.startswith("```"):
        raw = re.sub(r"^```[\w]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)
    raw = raw.strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start < 0 or end < 0:
            return None
        try:
            data = json.loads(raw[start:end + 1])
        except json.JSONDecodeError:
            return None

    hook = data.get("hook", "")
    cta = data.get("cta", "关注我，每天一条加密快讯！")
    hashtags = data.get("hashtags", [])
    segments_raw = data.get("segments", [])

    if not hook or not segments_raw:
        return None

    segments = []
    for seg in segments_raw:
        segments.append(VideoSegment(
            time=seg.get("time", ""),
            visual=seg.get("visual", ""),
            voiceover=seg.get("voiceover", ""),
        ))

    return VideoScript(hook=hook, segments=segments, cta=cta, hashtags=hashtags)


# ---------------------------------------------------------------------------
# 模板降级
# ---------------------------------------------------------------------------

_HOOK_TEMPLATES = [
    "重磅突发！{topic}刚刚发生了这件事...",
    "{topic}突然爆了，所有人都在问：现在上车还来得及吗？",
    "30秒看懂：{topic}为什么突然上热搜？",
    "别划走！{topic}的这个细节99%的人都忽略了",
    "如果你还没关注{topic}，这条视频可能帮你省一笔",
]

_VISUAL_TEMPLATES = {
    "intro": "新闻标题大字屏，配合新闻网站截图快速切换",
    "explain": "信息图表动画 / 关键数据高亮弹出",
    "analyze": "口播特写 + 背景行情走势图 / K线图",
    "impact": "资金流向动画 / 监管文件截图",
    "cta": "文字引导屏幕 + 博主口播特写",
}


def _template_hook(event: Event) -> str:
    topic = event.title[:30]
    for t in _HOOK_TEMPLATES:
        if "topic" in t:
            return t.format(topic=topic)
    return f"🔥 {event.title}"


def _template_hashtags(event: Event) -> list[str]:
    tags = []
    if "crypto" in event.tags:
        tags.extend(["#Crypto", "#Bitcoin", "#Web3"])
    if "ai" in event.tags:
        tags.extend(["#AI", "#LLM", "#TechNews"])
    return tags[:5] or ["#CryptoNews", "#DailyNews"]


def generate_video_script_template(event: Event) -> VideoScript:
    """纯规则生成的降级脚本（LLM 不可用时使用）。"""
    hook = _template_hook(event)
    title_short = event.title[:40]
    summary_short = event.summary[:60] if event.summary else ""

    segments = [
        VideoSegment("0:00-0:03", f"文字大字：{title_short}", hook),
        VideoSegment("0:03-0:10", f"新闻网站截图快速切换：{_VISUAL_TEMPLATES['intro']}",
                     f"刚刚，{title_short}。{summary_short}"),
        VideoSegment("0:10-0:18", _VISUAL_TEMPLATES["explain"],
                     "这件事的关键变化在于：它可能影响整个市场接下来的走势。"),
        VideoSegment("0:18-0:25", _VISUAL_TEMPLATES["impact"],
                     "不管你是交易者还是长期持有者，都需要关注这个信号。"),
        VideoSegment("0:25-0:30", _VISUAL_TEMPLATES["cta"],
                     "点个赞，关注我，每天 30 秒掌握加密前沿！"),
    ]

    return VideoScript(
        hook=hook,
        segments=segments,
        cta="关注我，每天 30 秒掌握加密前沿！",
        hashtags=_template_hashtags(event),
        duration_s=30,
    )


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

def generate_video_script(
    event: Event,
    *,
    llm_client: Optional[LLMClient] = None,
    language: str = "zh",
) -> VideoScript:
    """为一条新闻生成短视频脚本。"""
    if llm_client is not None:
        prompt = VIDEO_PROMPT_TEMPLATE.format(
            system=VIDEO_SYSTEM_PROMPT,
            title=event.title,
            summary=event.summary[:300],
            tags=", ".join(event.tags),
        )
        try:
            raw = llm_client.generate(prompt)
            script = _parse_script_json(raw)
            if script is not None:
                return script
        except Exception as exc:
            print(f"  LLM 短视频脚本生成失败：{exc}，回退模板")

    return generate_video_script_template(event)
