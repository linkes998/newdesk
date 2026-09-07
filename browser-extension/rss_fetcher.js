// rss_fetcher.js
// 通过 Google RSS-to-JSON 公共接口绕过 CORS 抓取 RSS
// 备用：支持直接 fetch（开发环境 / 已配置 CORS 的服务器）
const RSS_PROXY = "https://api.rss2json.com/v1/api.json?rss_url=";

/**
 * 抓取单条 RSS feed，返回 [{title, summary, url, pubDate}] 列表
 * 超时 15s，失败自动重试一次
 */
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
