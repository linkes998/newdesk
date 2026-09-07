// background.js — 完全离线，无 server 依赖
// Service Worker：闹钟定时抓取、通知、chrome.storage 读写
// 所有逻辑自包含，无需从 content scripts 导入

// ============================================================
// 1. RSS 抓取（来自 rss_fetcher.js）
// ============================================================
const RSS_PROXY = "https://api.rss2json.com/v1/api.json?rss_url=";

const RSS_FEEDS = [
  "https://www.coindesk.com/arc/outboundfeeds/rss/",
  "https://cointelegraph.com/rss",
  "https://www.theblock.co/rss.xml",
  "https://decrypt.co/feed",
  "https://openai.com/blog/rss.xml",
  "https://cryptonews.com/news/feed/",
  "https://www.coingecko.com/en/rss/news",
  "https://coinmarketcap.com/headlines/rss/",
];

async function fetchRSS(url, maxEntries = 25, timeoutMs = 15000) {
  const proxyUrl = RSS_PROXY + encodeURIComponent(url);
  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    const resp = await fetch(proxyUrl, { signal: controller.signal });
    clearTimeout(timer);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const json = await resp.json();
    if (json.status !== "ok") throw new Error(json.message || "rss2json error");
    return (json.items || [])
      .slice(0, maxEntries)
      .map((it) => ({
        title: (it.title || "").trim(),
        summary: cleanText(it.description || it.content || it.enclosure?.link || ""),
        url: it.link || "",
        pubDate: it.pubDate || it.isoDate || new Date().toISOString(),
        author: it.author || it.creator || "",
        thumbnail: it.thumbnail || it.image || "",
      }))
      .filter((it) => it.title && it.url);
  } catch (e) {
    console.warn("[NewsDesk] RSS fetch failed for", url, e.message);
    return [];
  }
}

function cleanText(text) {
  if (!text) return "";
  return text
    .replace(/<[^>]+>/g, " ")
    .replace(/&nbsp;/g, " ")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&#\d+;/g, "")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 500);
}

// ============================================================
// 2. 评分引擎（来自 scorer.js）
// ============================================================
const CRYPTO_KEYWORDS = [
  "bitcoin", "btc", "ethereum", "eth", "solana", "xrp", "ripple", "zcash",
  "litecoin", "cardano", "dogecoin", "defi", "etf", "clarity", "crypto",
  "blockchain", "rwa", "stablecoin", "nft", "layer2", "layer 2", "rollup",
  "zk", "zero-knowledge", "memecoin", "mempool", "sec", "regulation",
  "securities", "stock token", "synthetic", "tokenized", "payment",
  "banking", "exchange", "robinhood", "coinbase", "kraken", "bitget",
  "blackrock",
];
const AI_KEYWORDS = [
  "ai", "openai", "anthropic", "gpt", "claude", "llm", "agent", "model",
  "deepseek", "qwen", "gemini", "mistral",
  "cyber defense", "zero-day", "coding", "reasoning",
];
const SKIP_TERMS = [
  "giveaway", "airdrop code", "保证收益", "稳赚", "必涨", "100x", "moonshot",
];
const PREMIUM_TERMS = [
  "clarity", "etf", "regulation", "securities", "sec",
  "openai", "deepseek", "agent", "llm", "model",
  "payment", "banking", "blackrock", "robinhood", "coinbase",
  "tokenized", "rwa", "stablecoin", "memecoin", "reasoning", "cyber defense",
];
const SCORE_THRESHOLD = 2.0;
const MAX_AGE_HOURS = 48;
const MAX_ITEMS = 8;

function scoreArticle(title, summary) {
  const blob = (title + " " + summary).toLowerCase();
  for (const kw of SKIP_TERMS) {
    if (blob.includes(kw.toLowerCase())) {
      return { score: 0, tags: [], skipReason: `skip-term:${kw}` };
    }
  }
  const tags = [];
  let score = 0;
  const cryptoHits = CRYPTO_KEYWORDS.filter((w) => blob.includes(w.toLowerCase()));
  const aiHits = AI_KEYWORDS.filter((w) => blob.includes(w.toLowerCase()));
  if (cryptoHits.length) { tags.push("crypto"); score += cryptoHits.length; }
  if (aiHits.length)    { tags.push("ai");    score += aiHits.length; }
  if (tags.includes("crypto") && tags.includes("ai")) score += 2.5;
  for (const w of PREMIUM_TERMS) {
    if (blob.includes(w.toLowerCase())) { score += 1.5; break; }
  }
  return { score, tags, skipReason: null };
}

function freshnessBonus(pubDateStr) {
  if (!pubDateStr) return -1.5;
  const pub = new Date(pubDateStr);
  if (isNaN(pub.getTime())) return -1.5;
  const ageHours = (Date.now() - pub.getTime()) / 3600000;
  if (ageHours > MAX_AGE_HOURS) return -999;
  return Math.max(-1.0, 2.0 - (ageHours / MAX_AGE_HOURS) * 3.0);
}

function collectEvents(rawItems) {
  const events = [];
  for (const item of rawItems) {
    const { score: rawScore, tags, skipReason } = scoreArticle(item.title, item.summary);
    if (skipReason) continue;
    if (rawScore < SCORE_THRESHOLD) continue;
    const fresh = freshnessBonus(item.pubDate);
    if (fresh <= -999) continue;
    const finalScore = rawScore + fresh;
    if (finalScore < SCORE_THRESHOLD) continue;
    events.push({
      ...item,
      score: parseFloat(finalScore.toFixed(2)),
      tags,
      rawScore: parseFloat(rawScore.toFixed(2)),
    });
  }
  const seen = new Set();
  const uniq = [];
  for (const e of events.sort((a, b) => b.score - a.score)) {
    const key = e.title.slice(0, 40);
    if (seen.has(key)) continue;
    seen.add(key);
    uniq.push(e);
  }
  return uniq.slice(0, MAX_ITEMS);
}

// ============================================================
// 3. 草稿生成引擎（来自 generate_drafts.js）
// ============================================================
const PLATFORM_META = {
  x: { display: "X (Twitter)", maxChars: 280, threadSupported: true },
  telegram: { display: "Telegram", maxChars: 4096, threadSupported: false },
  discord: { display: "Discord", maxChars: 2000, threadSupported: true },
};

const STYLE_PRESETS = {
  professional: { label: "分析师专业风", targetLen: 400, emojiRate: 0.05, hasTicker: true, interactive: false, toneTag: "professional" },
  casual:       { label: "口语化快评",   targetLen: 250, emojiRate: 0.3,  hasTicker: true, interactive: true,  toneTag: "casual" },
  emoji_heavy:  { label: "Emoji 丰富风", targetLen: 300, emojiRate: 0.6,  hasTicker: true, interactive: true,  toneTag: "hype" },
  minimal:      { label: "极简短句",     targetLen: 100, emojiRate: 0.1,  hasTicker: false, interactive: false, toneTag: "minimal" },
  thread:       { label: "X Thread 深度", targetLen: 250, emojiRate: 0.15, hasTicker: true, interactive: true,  toneTag: "deep", platforms: ["x"] },
  newsletter:   { label: "Newsletter 摘要", targetLen: 600, emojiRate: 0.0, hasTicker: true, interactive: false, toneTag: "professional", platforms: ["telegram", "discord"] },
  tech_deep:    { label: "技术深度解读",   targetLen: 450, emojiRate: 0.05, hasTicker: false, interactive: false, toneTag: "deep" },
  quick_hit:    { label: "快讯快评",     targetLen: 80, emojiRate: 0.2,  hasTicker: true, interactive: false, toneTag: "minimal", platforms: ["telegram", "discord"] },
  story:        { label: "叙事故事风",   targetLen: 350, emojiRate: 0.15, hasTicker: false, interactive: true,  toneTag: "deep" },
  price_focus:  { label: "价格聚焦风",   targetLen: 300, emojiRate: 0.2,  hasTicker: true, interactive: true,  toneTag: "casual" },
};

function generateDraft(title, summary, url, styleKey = "professional", platform = "x", language = "zh") {
  const style = STYLE_PRESETS[styleKey] || STYLE_PRESETS.professional;
  const meta = PLATFORM_META[platform] || PLATFORM_META.x;
  const maxLen = Math.min(style.targetLen, meta.maxChars);
  const blob = (title + " " + summary).toLowerCase();
  const tags = [];
  for (const w of [...CRYPTO_KEYWORDS, ...AI_KEYWORDS]) {
    if (blob.includes(w)) tags.push(w);
  }
  const tagSymbols = tags.slice(0, 3).map((t) => "$" + t.toUpperCase());

  // 从 summary 提取要点：按句号/换行分句，取前3个
  const sentences = splitSentences(summary).slice(0, 3);

  let text;
  if (language === "zh") {
    text = buildZHDraft(title, summary, sentences, tagSymbols, style);
  } else {
    text = buildENDraft(title, summary, sentences, tagSymbols, style);
  }
  // 截断到平台限制
  return { text: text.slice(0, maxLen), style: style.label };
}

function splitSentences(text) {
  if (!text) return [];
  // 按中英文句号、问号、感叹号换行分句
  return text
    .replace(/([。！？!?])/g, "$1\n")
    .split(/\n+/)
    .map((s) => s.trim())
    .filter((s) => s.length > 10);
}

function buildZHDraft(title, summary, sentences, tagSymbols, style) {
  const ticker = style.hasTicker ? " " + tagSymbols.join(" ") : "";
  const points = sentences.map((s, i) => `${i + 1}. ${s}`).join("\n");
  const fullSummary = summary && summary.length > 20 ? summary : "";

  switch (style.toneTag) {
    case "minimal":
      // 极简：标题 + 1句话
      return `📰 ${title}\n\n${sentences[0] || fullSummary.slice(0, 80)}${ticker}`;

    case "casual":
      // 口语化：标题 + 详情 + 个人观点
      return `📰 ${title}\n\n${fullSummary}\n\n我的看法：这条新闻信息量不小，值得持续关注。${ticker}`;

    case "hype":
      // hype风：大标题 + 核心点 + 号召
      return `🔥 ${title}\n\n✨ 核心要点：\n${points}\n\n🚀 这件事的影响可能比想象中更大！${ticker}`;

    case "deep":
      // 深度分析：标题 + 要点 + 影响 + 展望
      return `📊 【深度】${title}\n\n🔍 关键事实：\n${points}\n\n💡 分析：这条新闻反映的趋势值得重点跟踪，后续发展可能对市场产生连锁反应。${ticker}`;

    default: // professional
      // 专业风：标题 + 摘要 + 要点 + 小结
      let body = `📋 ${title}\n\n${fullSummary}\n`;
      if (points) body += `\n📌 核心要点：\n${points}\n`;
      body += `\n${ticker}`;
      return body;
  }
}

function buildENDraft(title, summary, sentences, tagSymbols, style) {
  const ticker = style.hasTicker ? " " + tagSymbols.join(" ") : "";
  const points = sentences.map((s, i) => `${i + 1}. ${s}`).join("\n");
  const fullSummary = summary && summary.length > 20 ? summary : "";

  switch (style.toneTag) {
    case "minimal":
      return `📰 ${title}\n\n${sentences[0] || fullSummary.slice(0, 80)}${ticker}`;

    case "casual":
      return `📰 ${title}\n\n${fullSummary}\n\nMy take: This one's worth watching closely.${ticker}`;

    case "hype":
      return `🔥 ${title}\n\n✨ Key Points:\n${points}\n\n🚀 This could be bigger than it looks!${ticker}`;

    case "deep":
      return `📊 ${title}\n\n🔍 Key Facts:\n${points}\n\n💡 Analysis: The implications of this development could ripple through the market.${ticker}`;

    default:
      let body = `📋 ${title}\n\n${fullSummary}\n`;
      if (points) body += `\n📌 Key Points:\n${points}\n`;
      body += `\n${ticker}`;
      return body;
  }
}

// ============================================================
// 4. Service Worker 生命周期 & 消息处理
// ============================================================
const QUEUE_KEY = "newsdesk_queue";
const CONFIG_KEY = "newsdesk_config";

chrome.runtime.onInstalled.addListener(() => {
  chrome.storage.sync.get(CONFIG_KEY, (s) => {
    if (!s[CONFIG_KEY]) {
      chrome.storage.sync.set({
        [CONFIG_KEY]: {
          style: "professional",
          language: "zh",
          platforms: ["x", "telegram", "discord"],
          autoGenerate: true,
          scoreThreshold: SCORE_THRESHOLD,
          maxAgeHours: MAX_AGE_HOURS,
        },
      });
    }
  });
  chrome.alarms.create("autoFetch", { periodInMinutes: 30 });
});

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === "autoFetch") runAutoFetch();
});

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === "FETCH_AND_SCORE") { runAutoFetch().then(sendResponse); return true; }
  if (msg.type === "GET_QUEUE") { chrome.storage.local.get(QUEUE_KEY, (s) => sendResponse(s[QUEUE_KEY] || { items: [], stats: {} })); return true; }
  if (msg.type === "SUBMIT_ITEM") { addItemToQueue(msg.item).then(sendResponse); return true; }
  if (msg.type === "APPROVE_ITEM") { updateItemStatus(msg.itemId, "approved").then(sendResponse); return true; }
  if (msg.type === "REJECT_ITEM") { updateItemStatus(msg.itemId, "rejected").then(sendResponse); return true; }
  if (msg.type === "MODIFY_DRAFT") { modifyDraft(msg.itemId, msg.platform, msg.text).then(sendResponse); return true; }
  if (msg.type === "GET_CONFIG") { chrome.storage.sync.get(CONFIG_KEY, (s) => sendResponse(s[CONFIG_KEY] || {})); return true; }
  if (msg.type === "SAVE_CONFIG") { chrome.storage.sync.set({ [CONFIG_KEY]: msg.config }).then(() => sendResponse({ ok: true })); return true; }
  if (msg.type === "CONFIG_UPDATED") {
    // 响应配置变更：更新 alarms 等
    const cfg = msg.cfg || {};
    chrome.alarms.clear("autoFetch", () => {
      if (cfg.autoGenerate !== false) {
        chrome.alarms.create("autoFetch", { periodInMinutes: 30 });
      }
    });
    sendResponse({ ok: true });
    return true;
  }
});

// ============================================================
// 5. 核心业务逻辑
// ============================================================
async function runAutoFetch() {
  try {
    const rawItems = [];
    for (const feedUrl of RSS_FEEDS) {
      const items = await fetchRSS(feedUrl, 25, 10000) || [];
      if (Array.isArray(items)) {
        rawItems.push(...items.map((it) => ({ ...it, source: feedUrl })));
      }
    }
    const events = collectEvents(rawItems);
    const config = (await new Promise((r) => chrome.storage.sync.get(CONFIG_KEY, r)))[CONFIG_KEY] || {};
    const platforms = config.platforms || ["x", "telegram", "discord"];
    const style = config.style || "professional";
    const lang = config.language || "zh";

    const queueItems = events.map((ev) => {
      const drafts = {};
      for (const plat of platforms) {
        const gen = generateDraft(ev.title, ev.summary, ev.url, style, plat, lang);
        drafts[plat] = gen.text;
      }
      return {
        item_id: hashId(ev.title, ev.url),
        event_title: ev.title,
        event_url: ev.url,
        event_summary: ev.summary,
        event_score: ev.score,
        event_tags: ev.tags,
        event_source: ev.source,
        drafts,
        status: "pending",
        history: [],
        created_at: new Date().toISOString(),
      };
    });

    const existingItems = await _readQueue();
    const existingIds = new Set(existingItems.map((it) => it.item_id));
    const newItems = queueItems.filter((it) => !existingIds.has(it.item_id));
    const finalItems = dedupeQueue([...queueItems, ...existingItems]);
    await _writeQueue(finalItems);
    const stats = computeStats(finalItems);
    await chrome.storage.local.set({ [`${QUEUE_KEY}_stats`]: stats });

    if (newItems.length > 0) {
      chrome.notifications.create({
        type: "basic",
        iconUrl: "icons/icon48.png",
        title: "NewsDesk",
        message: `新增 ${newItems.length} 条新闻`,
      });
    }
    return { ok: true, fetched: rawItems.length, scored: events.length, newItems: newItems.length };
  } catch (e) {
    console.error("[NewsDesk] Auto fetch failed:", e);
    return { ok: false, error: e.message };
  }
}

function dedupeQueue(items) {
  const seen = new Set();
  return items.filter((it) => {
    if (seen.has(it.item_id)) return false;
    seen.add(it.item_id);
    return true;
  });
}

function computeStats(items) {
  const counts = { pending: 0, approved: 0, rejected: 0, published: 0 };
  for (const it of items) counts[it.status] = (counts[it.status] || 0) + 1;
  return counts;
}

// 辅助函数：从 storage 读取并兼容两种格式
async function _readQueue() {
  const raw = (await new Promise((r) => chrome.storage.local.get(QUEUE_KEY, r)))[QUEUE_KEY];
  if (Array.isArray(raw)) return raw;
  if (raw && Array.isArray(raw.items)) return raw.items;
  return [];
}
// 辅助函数：写入纯数组格式
async function _writeQueue(items) {
  await chrome.storage.local.set({ [QUEUE_KEY]: items });
}

async function addItemToQueue(item) {
  const items = await _readQueue();
  if (items.some((it) => it.item_id === item.item_id)) return { ok: true, duplicated: true };
  items.unshift(item);
  await _writeQueue(items);
  return { ok: true, item_id: item.item_id };
}

async function updateItemStatus(itemId, status) {
  const items = await _readQueue();
  const item = items.find((it) => it.item_id === itemId);
  if (!item) return { ok: false, error: "not found" };
  const now = new Date().toISOString();
  item.status = status;
  item.history = item.history || [];
  item.history.push({ timestamp: now, action: status });
  item.updated_at = now;
  await _writeQueue(items);
  const stats = computeStats(items);
  await chrome.storage.local.set({ [`${QUEUE_KEY}_stats`]: stats });
  return { ok: true, item_id: itemId, status };
}

async function modifyDraft(itemId, platform, text) {
  const items = await _readQueue();
  const item = items.find((it) => it.item_id === itemId);
  if (!item) return { ok: false, error: "not found" };
  item.drafts = item.drafts || {};
  item.drafts[platform] = text;
  item.status = "modified";
  item.updated_at = new Date().toISOString();
  item.history = item.history || [];
  item.history.push({ timestamp: item.updated_at, action: "modify", platform });
  await _writeQueue(items);
  return { ok: true, item_id: itemId };
}

function hashId(title, url) {
  const str = `${title.slice(0, 60)}|${url}`;
  let h = 0;
  for (let i = 0; i < str.length; i++) {
    h = ((h << 5) - h + str.charCodeAt(i)) | 0;
  }
  return Math.abs(h).toString(36);
}
