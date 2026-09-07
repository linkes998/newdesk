"""
多风格模板系统 —— 10 种预置写作风格 + 平台专属 prompt 模板。

设计思路：
- 每种风格是一个 StylePreset，包含：tone、目标长度、emoji_rate、是否适合 thread、语言
- 不同平台（X/Telegram/Discord/Newsletter/LinkedIn）有独立的 prompt 模板
- 用户可以组合：风格 × 平台 得到最终 prompt
- 支持自定义追加 prompt（用户在 config 里写 "我希望风格更幽默" 会被拼入）
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# 风格预设
# ---------------------------------------------------------------------------

@dataclass
class StylePreset:
    """一个完整的写作风格配置。"""
    key: str                          # 内部标识符
    label: str                         # 给用户看的名字
    description: str                   # 一句话描述
    target_len: int                    # 目标字符数
    emoji_rate: float                  # 0-1，建议 emoji 密度
    has_ticker: bool = True            # 是否包含 $BTC 等
    interactive: bool = True           # 是否有互动（问句/投票）
    tone_tag: str = "neutral"          # professional / casual / hype / deep / minimal
    platforms: list[str] = field(default_factory=lambda: ["x", "telegram", "discord"])

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "label": self.label,
            "description": self.description,
            "target_len": self.target_len,
            "emoji_rate": self.emoji_rate,
            "has_ticker": self.has_ticker,
            "interactive": self.interactive,
            "tone_tag": self.tone_tag,
            "platforms": self.platforms,
        }


# ---------------------------------------------------------------------------
# 10 种预置风格
# ---------------------------------------------------------------------------

STYLE_PRESETS: list[StylePreset] = [
    StylePreset(
        key="professional",
        label="分析师专业风",
        description="结论先行、分点论述、数据导向，适合币安广场/OKX星球等专业社区",
        target_len=400,
        emoji_rate=0.05,
        has_ticker=True,
        interactive=False,
        tone_tag="professional",
    ),
    StylePreset(
        key="casual",
        label="口语化快评",
        description="像跟朋友聊天一样，用『刚刷到』『我觉得』开头，适合 Telegram 群组",
        target_len=250,
        emoji_rate=0.3,
        has_ticker=True,
        interactive=True,
        tone_tag="casual",
    ),
    StylePreset(
        key="emoji_heavy",
        label="Emoji 丰富风",
        description="用大量 emoji 分隔信息点，视觉冲击力强，适合 X/Twitter 和 Discord",
        target_len=300,
        emoji_rate=0.6,
        has_ticker=True,
        interactive=True,
        tone_tag="hype",
    ),
    StylePreset(
        key="minimal",
        label="极简短句",
        description="只有事实 + 一句话评论，不超过 100 字，适合 X/Twitter thread 开头",
        target_len=100,
        emoji_rate=0.1,
        has_ticker=False,
        interactive=False,
        tone_tag="minimal",
    ),
    StylePreset(
        key="thread",
        label="X Thread 深度",
        description="X 平台专用 thread 格式，1 主帖 + N 个连续回复，每个独立完整",
        target_len=250,
        emoji_rate=0.15,
        has_ticker=True,
        interactive=True,
        tone_tag="deep",
        platforms=["x"],
    ),
    StylePreset(
        key="newsletter",
        label="Newsletter 摘要",
        description="长文摘要风格，带标题、要点列表、深度链接，适合 Beehiiv/Substack",
        target_len=600,
        emoji_rate=0.0,
        has_ticker=True,
        interactive=False,
        tone_tag="professional",
        platforms=["telegram", "discord"],
    ),
    StylePreset(
        key="tech_deep",
        label="技术深度解读",
        description="适合 AI/加密技术更新，解释机制原理，可能包含简短代码或架构描述",
        target_len=450,
        emoji_rate=0.05,
        has_ticker=False,
        interactive=False,
        tone_tag="deep",
    ),
    StylePreset(
        key="quick_hit",
        label="快讯快评",
        description="超短（<80字）、节奏快、信息密度高，适合 Telegram 频道高频推送",
        target_len=80,
        emoji_rate=0.2,
        has_ticker=True,
        interactive=False,
        tone_tag="minimal",
        platforms=["telegram", "discord"],
    ),
    StylePreset(
        key="story",
        label="叙事故事风",
        description="把新闻讲成一个有前因后果的小故事，开头吸引人，结尾有思考点",
        target_len=350,
        emoji_rate=0.15,
        has_ticker=False,
        interactive=True,
        tone_tag="deep",
    ),
    StylePreset(
        key="price_focus",
        label="价格聚焦风",
        description="先讲价格表现，再讲催化剂事件，适合对交易敏感的社区",
        target_len=300,
        emoji_rate=0.2,
        has_ticker=True,
        interactive=True,
        tone_tag="casual",
    ),
]


STYLE_MAP: dict[str, StylePreset] = {s.key: s for s in STYLE_PRESETS}


def get_style(key: str) -> Optional[StylePreset]:
    return STYLE_MAP.get(key)


def all_styles() -> list[dict]:
    return [s.to_dict() for s in STYLE_PRESETS]


def styles_for_platform(platform: str) -> list[dict]:
    return [s.to_dict() for s in STYLE_PRESETS if platform in s.platforms]


# ---------------------------------------------------------------------------
# 平台元信息（用于构建 prompt 和截断）
# ---------------------------------------------------------------------------

PLATFORM_META: dict[str, dict] = {
    "x": {
        "display": "X (Twitter)",
        "max_chars": 280,
        "thread_supported": True,
        "supports_hashtag": False,
        "api": "twitter",
    },
    "telegram": {
        "display": "Telegram",
        "max_chars": 4096,
        "thread_supported": False,
        "supports_hashtag": True,
        "api": "telegram",
    },
    "discord": {
        "display": "Discord",
        "max_chars": 2000,
        "thread_supported": True,
        "supports_hashtag": True,
        "api": "discord",
    },
    "linkedin": {
        "display": "LinkedIn",
        "max_chars": 3000,
        "thread_supported": False,
        "supports_hashtag": True,
        "api": None,  # 暂未实现发布
    },
    "newsletter": {
        "display": "Newsletter",
        "max_chars": 5000,
        "thread_supported": False,
        "supports_hashtag": False,
        "api": None,  # 导出为文件
    },
}


# ---------------------------------------------------------------------------
# Prompt 构建器 —— 风格 × 平台 混合 prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT_BASE = (
    "你是一位加密货币和 AI 领域的资深内容创作者。"
    "你的任务是将一条新闻转化为适合特定平台和风格的文案。"
    "输出必须是纯文案，不要任何标记、JSON、说明文字或注释。"
)

LANG_HINTS = {
    "zh": "全部使用简体中文写作",
    "en": "Write entirely in English",
    "auto": "根据新闻标题和摘要的语言自动选择合适的语言",
}


def build_draft_prompt(
    event_title: str,
    event_summary: str,
    event_url: str,
    *,
    style: StylePreset,
    platform: str,
    language: str = "zh",
    user_hint: str = "",
) -> str:
    """构造完整的 LLM prompt。

    参数：
        event_title: 新闻标题
        event_summary: 新闻摘要
        event_url: 新闻链接
        style: 风格预设
        platform: 目标平台 key
        language: zh / en / auto
        user_hint: 用户自定义的附加提示（来自 config）
    """
    meta = PLATFORM_META.get(platform, {})
    max_chars = meta.get("max_chars", 500)
    platform_name = meta.get("display", platform)
    lang_hint = LANG_HINTS.get(language, LANG_HINTS["zh"])

    # 风格具体约束
    style_rules: list[str] = []
    style_rules.append(f"- 目标字数：{style.target_len}字（平台上限 {max_chars} 字）")
    if style.emoji_rate >= 0.4:
        style_rules.append("- 要求：多使用 emoji 分隔段落和情绪")
    elif style.emoji_rate <= 0.1:
        style_rules.append("- 要求：尽量少用或不用 emoji，保持严肃")
    if style.has_ticker:
        style_rules.append("- 要求：文末加入相关代币符号，如 $BTC $ETH 等")
    if style.interactive:
        style_rules.append("- 要求：结尾加入一个简短的互动问句")
    if style.tone_tag == "minimal":
        style_rules.append("- 要求：极简，不要超过 100 字，只给事实和一句话评论")
    if style.tone_tag == "deep":
        style_rules.append("- 要求：深度分析，不要停留在表面事实，揭示背后的逻辑或影响链")
    if style.tone_tag == "hype":
        style_rules.append("- 要求：情绪饱满，有冲击力，适合快节奏传播")
    if platform == "x":
        style_rules.append("- 要求：X 平台格式，单条不超 280 字符，用分段替代标点")
    elif platform == "telegram":
        style_rules.append("- 要求：Telegram 风格，可以用加粗标记 **重点**")
    elif platform == "discord":
        style_rules.append("- 要求：Discord 简洁风格，清晰易读")
    elif platform == "newsletter":
        style_rules.append("- 要求：Newsletter 摘要格式，带短标题、核心要点、深度链接")

    user_hint_block = f"\n【用户自定义提示】\n{user_hint}\n" if user_hint else ""

    prompt = f"""{SYSTEM_PROMPT_BASE}

你现在要为 **{platform_name}** 平台写一条文案，风格：**{style.label}**

{lang_hint}

【原始信息】
标题：{event_title}
摘要：{event_summary}
链接：{event_url}

【风格约束】
{chr(10).join(style_rules)}

【硬性要求】
1. 不要复制原始标题作为开头
2. 不要给出投资建议
3. 不要出现"以下是"、"综上所述"等机械性过渡词
4. 输出纯文案，不要任何注释、标记、JSON 或解释{user_hint_block}

现在直接输出文案：
"""
    return prompt
