// scorer.js — 关键词评分引擎（Python scoring.py 的等价实现）
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

/**
 * 评分一篇文章，返回 {score, tags, skipReason}
 */
function scoreArticle(title, summary) {
  const blob = (title + " " + summary).toLowerCase();

  // skip list
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

/**
 * 计算时效加分（0-6h 线性 +2.0→-1.0）
 */
function freshnessBonus(pubDateStr) {
  if (!pubDateStr) return -1.5;
  const pub = new Date(pubDateStr);
  if (isNaN(pub.getTime())) return -1.5;
  const ageHours = (Date.now() - pub.getTime()) / 3600000;
  if (ageHours > MAX_AGE_HOURS) return -999; // 丢弃
  return Math.max(-1.0, 2.0 - (ageHours / MAX_AGE_HOURS) * 3.0);
}

/**
 * 过滤并排序事件列表，返回 top N
 */
function collectEvents(rawItems) {
  const events = [];
  for (const item of rawItems) {
    const { score: rawScore, tags, skipReason } = scoreArticle(item.title, item.summary);
    if (skipReason) continue;
    if (rawScore < SCORE_THRESHOLD) continue;

    const fresh = freshnessBonus(item.pubDate);
    if (fresh <= -999) continue; // 过期

    const finalScore = rawScore + fresh;
    if (finalScore < SCORE_THRESHOLD) continue;

    events.push({
      ...item,
      score: parseFloat(finalScore.toFixed(2)),
      tags,
      rawScore: parseFloat(rawScore.toFixed(2)),
    });
  }

  // 去重（按标题前 40 字符）
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
