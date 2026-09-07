// content.js — 新闻站点检测文章并注入"发送到 NewsDesk"按钮
(function () {
  "use strict";

  const TITLE_SELECTORS = [
    'h1.article-title', 'h1.post-title', 'h1.entry-title',
    'h1[data-testid="article-title"]',
    'meta[property="og:title"]',
  ];
  const SUMMARY_SELECTORS = [
    'meta[property="og:description"]',
    'meta[name="description"]',
    '.article-summary', '.excerpt', '.post-excerpt',
  ];

  function getMeta(prop) {
    const el = document.querySelector(`meta[property="${prop}"]`);
    return el ? el.getAttribute("content") : null;
  }

  function getText(selList) {
    for (const sel of selList) {
      const el = document.querySelector(sel);
      if (el && el.textContent.trim()) return el.textContent.trim();
    }
    return null;
  }

  function extractArticle() {
    const title = getText(TITLE_SELECTORS) || getMeta("og:title") || document.title;
    const summary = getText(SUMMARY_SELECTORS) || getMeta("og:description") || "";
    const url = window.location.href;
    const source = new URL(url).hostname.replace("www.", "");
    return { title: title.trim(), url, summary: summary.trim(), source };
  }

  function injectButton(article) {
    // 已存在则不重复注入
    if (document.getElementById("newsdesk-inject-btn")) return;

    const btn = document.createElement("button");
    btn.id = "newsdesk-inject-btn";
    btn.innerHTML = "📰 Send to NewsDesk";
    Object.assign(btn.style, {
      position: "fixed",
      bottom: "24px",
      right: "24px",
      zIndex: "2147483647",
      padding: "10px 16px",
      fontSize: "13px",
      fontFamily: "-apple-system, sans-serif",
      background: "linear-gradient(135deg,#6366f1,#8b5cf6)",
      color: "#fff",
      border: "none",
      borderRadius: "24px",
      boxShadow: "0 4px 16px rgba(99,102,241,.4)",
      cursor: "pointer",
      transition: "transform .15s, box-shadow .15s",
      display: "flex",
      alignItems: "center",
      gap: "6px",
    });
    btn.addEventListener("mouseenter", () => {
      btn.style.transform = "scale(1.05)";
      btn.style.boxShadow = "0 6px 24px rgba(99,102,241,.6)";
    });
    btn.addEventListener("mouseleave", () => {
      btn.style.transform = "scale(1)";
      btn.style.boxShadow = "0 4px 16px rgba(99,102,241,.4)";
    });
    btn.addEventListener("click", () => handleSend(article, btn));
    document.body.appendChild(btn);
  }

  async function handleSend(article, btn) {
    btn.disabled = true;
    btn.innerHTML = "⏳ 评分中…";

    try {
      // 1. 评分
      const { score, tags, skipReason } = scoreArticle(article.title, article.summary);
      if (skipReason) {
        btn.innerHTML = "⚠️ 未命中关键词";
        setTimeout(() => resetBtn(btn, article), 2000);
        return;
      }

      // 2. 生成草稿
      const config = await getConfig();
      const platforms = config.platforms || ["x", "telegram", "discord"];
      const style = config.style || "professional";
      const lang = config.language || "zh";
      const drafts = {};
      for (const plat of platforms) {
        const gen = generateDraft(article.title, article.summary, article.url, style, plat, lang);
        drafts[plat] = gen.text;
      }

      // 3. 提交到本地队列
      const item = {
        item_id: hashId(article.title, article.url),
        event_title: article.title,
        event_url: article.url,
        event_summary: article.summary,
        event_score: score,
        event_tags: tags,
        event_source: article.source,
        drafts,
        status: "pending",
        history: [{ timestamp: new Date().toISOString(), action: "submit" }],
        created_at: new Date().toISOString(),
      };

      const resp = await new Promise((resolve) => {
        chrome.runtime.sendMessage({ type: "SUBMIT_ITEM", item }, resolve);
      });

      if (resp && resp.ok) {
        btn.innerHTML = `✅ 已保存 (score ${score.toFixed(1)})`;
        showNotification(article.title, `评分 ${score.toFixed(1)}，已加入审核队列`);
      } else {
        btn.innerHTML = "❌ 保存失败";
      }
    } catch (e) {
      console.error("[NewsDesk] handleSend error:", e);
      btn.innerHTML = "❌ 出错";
    }

    setTimeout(() => resetBtn(btn, article), 3000);
  }

  function resetBtn(btn, article) {
    btn.disabled = false;
    btn.innerHTML = "📰 Send to NewsDesk";
  }

  function showNotification(title, body) {
    chrome.notifications.create({
      type: "basic",
      iconUrl: "icons/icon48.png",
      title: "NewsDesk",
      message: body,
    });
  }

  function getConfig() {
    return new Promise((resolve) => {
      chrome.runtime.sendMessage({ type: "GET_CONFIG" }, (r) => resolve(r || {}));
    });
  }

  function hashId(title, url) {
    const str = `${title.slice(0, 60)}|${url}`;
    let h = 0;
    for (let i = 0; i < str.length; i++) {
      h = ((h << 5) - h + str.charCodeAt(i)) | 0;
    }
    return Math.abs(h).toString(36);
  }

  function init() {
    const article = extractArticle();
    if (!article.title || article.title.length < 10) return;
    injectButton(article);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
