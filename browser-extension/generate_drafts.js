// generate_drafts.js — 纯前端文案生成引擎（不依赖 LLM API）
// 替代 Python templates.py + LLM 的逻辑

// ---------- 平台元信息 ----------
const PLATFORM_META = {
  x: {
    display: "X (Twitter)",
    maxChars: 280,
    threadSupported: true,
  },
  telegram: {
    display: "Telegram",
    maxChars: 4096,
    threadSupported: false,
  },
  discord: {
    display: "Discord",
    maxChars: 2000,
    threadSupported: true,
  },
};

// ---------- 10 种风格预设 ----------
const STYLE_PRESETS = {
  professional: {
    label: "分析师专业风",
    targetLen: 400,
    emojiRate: 0.05,
    hasTicker: true,
    interactive: false,
    toneTag: "professional",
  },
  casual: {
    label: "口语化快评",
    targetLen: 250,
    emojiRate: 0.3,
    hasTicker: true,
    interactive: true,
    toneTag: "casual",
  },
  emoji_heavy: {
    label: "Emoji 丰富风",
    targetLen: 300,
    emojiRate: 0.6,
    hasTicker: true,
    interactive: true,
    toneTag: "hype",
  },
  minimal: {
    label: "极简短句",
    targetLen: 100,
    emojiRate: 0.1,
    hasTicker: false,
    interactive: false,
    toneTag: "minimal",
  },
  thread: {
    label: "X Thread 深度",
    targetLen: 250,
    emojiRate: 0.15,
    hasTicker: true,
    interactive: true,
    toneTag: "deep",
    platforms: ["x"],
  },
  newsletter: {
    label: "Newsletter 摘要",
    targetLen: 600,
    emojiRate: 0.0,
    hasTicker: true,
    interactive: false,
    toneTag: "professional",
    platforms: ["telegram", "discord"],
  },
  tech_deep: {
    label: "技术深度解读",
    targetLen: 450,
    emojiRate: 0.05,
    hasTicker: false,
    interactive: false,
    toneTag: "deep",
  },
  quick_hit: {
    label: "快讯快评",
    targetLen: 80,
    emojiRate: 0.2,
    hasTicker: true,
    interactive: false,
    toneTag: "minimal",
    platforms: ["telegram", "discord"],
  },
  story: {
    label: "叙事故事风",
    targetLen: 350,
    emojiRate: 0.15,
    hasTicker: false,
    interactive: true,
    toneTag: "deep",
  },
  price_focus: {
    label: "价格聚焦风",
    targetLen: 300,
    emojiRate: 0.2,
    hasTicker: true,
    interactive: true,
    toneTag: "casual",
  },
};

// ---------- LLM 文案生成（纯模板降级模式）----------
function generateDraft(title, summary, url, styleKey = "professional", platform = "x", language = "zh") {
  const style = STYLE_PRESETS[styleKey] || STYLE_PRESETS.professional;
  const meta = PLATFORM_META[platform] || PLATFORM_META.x;
  const maxLen = Math.min(style.targetLen, meta.maxChars);

  // 提取关键词标签
  const blob = (title + " " + summary).toLowerCase();
  const tags = [];
  for (const w of [...CRYPTO_KEYWORDS || [], ...AI_KEYWORDS || []]) {
    if (blob.includes(w)) tags.push(w);
  }
  const tagSymbols = tags.slice(0, 3).map((t) => "$" + t.toUpperCase());

  // ---- 中文模板 ----
  if (language === "zh") {
    const templates = getZHTemplates(style, tagSymbols, title);
    return { text: templates.main.slice(0, maxLen), style: style.label };
  }
  // ---- 英文模板 ----
  return { text: getENTemplates(style, tagSymbols, title, summary), style: style.label };
}

function getZHTemplates(style, tagSymbols, title) {
  const ticker = style.hasTicker ? " " + tagSymbols.join(" ") : "";
  const q = style.interactive
    ? "\n你怎么看？"
    : "";
  const extras = style.emojiRate >= 0.4
    ? " 🚀\n📊 "
    : style.emojiRate <= 0.1
      ? ""
      : " ";

  switch (style.toneTag) {
    case "minimal":
      return {
        main: `${title.slice(0, 50)}…${extras}${q}`,
      };
    case "casual":
      return {
        main: `刚刷到这条 📰\n\n${summary.slice(0, 120)}\n\n我觉得挺有意思的，#${tagsStr(style)}${ticker}${q}`,
      };
    case "hype":
      return {
        main: `🔥 ${title.slice(0, 40)}…\n\n💡 ${summary.slice(0, 100)}\n\n👇 你怎么看？${ticker}`,
      };
    case "deep":
      return {
        main: `## ${title}\n\n${summary.slice(0, 150)}\n\n这个信号值得注意——${q}${ticker}`,
      };
    default: // professional
      return {
        main: `【${title.slice(0, 35)}…】\n\n${summary.slice(0, 180)}\n${ticker}${q}`,
      };
  }
}

function getENTemplates(style, tagSymbols, title, summary) {
  const ticker = style.hasTicker ? " " + tagSymbols.join(" ") : "";
  const q = style.interactive ? "\nWhat do you think?" : "";

  switch (style.toneTag) {
    case "minimal":
      return `${title.slice(0, 50)}…${q}`;
    case "casual":
      return `Just saw this 📰\n\n${summary.slice(0, 120)}\n\nMy take:${ticker}${q}`;
    case "hype":
      return `🔥 ${title.slice(0, 40)}\n\n💡 ${summary.slice(0, 100)}\n\n👇 ${ticker}`;
    case "deep":
      return `## ${title}\n\n${summary.slice(0, 150)}\n\nWorth watching closely${ticker}${q}`;
    default:
      return `【${title.slice(0, 35)}】\n\n${summary.slice(0, 180)}${ticker}${q}`;
  }
}

function tagsStr(style) {
  return style.toneTag || "news";
}
