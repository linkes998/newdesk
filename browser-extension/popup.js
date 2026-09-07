// popup.js — NewsDesk 离线模式面板逻辑

(function () {
  const QUEUE_KEY = "newsdesk_queue";
  const CONFIG_KEY = "newsdesk_config";

  // ── Tab 切换 ────────────────────────────────────────────────────────────────
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
      document.querySelectorAll(".panel").forEach((p) => p.classList.remove("active"));
      tab.classList.add("active");
      const target = document.getElementById("panel-" + tab.dataset.tab);
      if (target) target.classList.add("active");
      if (tab.dataset.tab === "queue") loadQueue();
      if (tab.dataset.tab === "stats") loadStats();
      if (tab.dataset.tab === "config") loadConfig();
    });
  });

  // ── 加载队列 ────────────────────────────────────────────────────────────────
  function loadQueue() {
    chrome.storage.local.get(QUEUE_KEY, (s) => {
      const raw = s[QUEUE_KEY];
      const items = Array.isArray(raw) ? raw : Array.isArray(raw?.items) ? raw.items : [];
      const pending = items.filter((it) => it.status === "pending" || it.status === "modified");
      document.getElementById("queueCount").textContent = `(${pending.length})`;
      renderQueue(pending);
    });
  }

  function renderQueue(items) {
    const container = document.getElementById("queueList");
    if (!items || items.length === 0) {
      container.innerHTML = `<div class="empty-state">
        <div class="icon">📭</div>
        <div>暂无新闻</div>
        <div style="margin-top:4px;font-size:11px;">点击「抓取新闻」开始</div>
      </div>`;
      return;
    }
    container.innerHTML = "";
    for (const item of items) {
      const card = document.createElement("div");
      card.className = "queue-item";
      const scoreColor = item.event_score >= 5 ? "var(--green)" : item.event_score >= 3 ? "var(--yellow)" : "var(--text-dim)";
      const drafts = item.drafts || {};
      const platKeys = Object.keys(drafts);

      let draftsHtml = "";
      if (platKeys.length > 0) {
        draftsHtml = '<div class="draft-editor">';
        for (const plat of platKeys) {
          draftsHtml += `<div class="plat-label">${platDisplay(plat)}</div>`;
          draftsHtml += `<textarea data-item="${item.item_id}" data-plat="${plat}">${escapeHtml(drafts[plat] || "")}</textarea>`;
        }
        draftsHtml += '</div>';
      }

      card.innerHTML = `
        <div class="qi-title">${escapeHtml(item.event_title)}</div>
        <div class="qi-meta">
          <span style="color:${scoreColor};font-weight:700;">★ ${item.event_score.toFixed(1)}</span>
          <span style="margin:0 6px;">·</span>
          ${(item.event_tags || []).map((t) => `<span class="tag">${t}</span>`).join("")}
          <span style="margin-left:6px;opacity:.6;">${timeAgo(item.created_at)}</span>
        </div>
        ${draftsHtml}
        <div class="qi-actions">
          <button class="btn-open" data-action="open" data-url="${escapeAttr(item.event_url)}">🔗 原文</button>
          <button class="btn-approve" data-id="${item.item_id}">✓ 批准</button>
          <button class="btn-reject" data-id="${item.item_id}">✗ 拒绝</button>
        </div>`;
      container.appendChild(card);
    }

    // 绑定修改草稿事件
    container.querySelectorAll("textarea").forEach((ta) => {
      ta.addEventListener("blur", (e) => {
        const id = e.target.dataset.item;
        const plat = e.target.dataset.plat;
        const text = e.target.value;
        chrome.runtime.sendMessage({ type: "MODIFY_DRAFT", itemId: id, platform: plat, text }, () => {});
      });
      // 自动展开高度
      ta.addEventListener("input", function () {
        this.style.height = "auto";
        this.style.height = this.scrollHeight + "px";
      });
      // 初始展开
      requestAnimationFrame(() => {
        ta.style.height = "auto";
        ta.style.height = ta.scrollHeight + "px";
      });
    });

    // 绑定按钮事件（使用事件委托）
    container.addEventListener("click", (e) => {
      const btn = e.target.closest("button");
      if (!btn) return;
      if (btn.classList.contains("btn-approve")) {
        approveItem(btn.dataset.id);
      } else if (btn.classList.contains("btn-reject")) {
        rejectItem(btn.dataset.id);
      } else if (btn.dataset.action === "open") {
        const url = btn.dataset.url;
        if (url) chrome.tabs.create({ url });
      }
    });
  }

  function approveItem(itemId) {
    chrome.runtime.sendMessage({ type: "APPROVE_ITEM", itemId }, (res) => {
      if (chrome.runtime.lastError) {
        console.error("APPROVE error:", chrome.runtime.lastError);
        alert("批准失败: " + chrome.runtime.lastError.message);
        return;
      }
      if (res?.ok) loadQueue();
      else alert("批准失败: " + (res?.error || "未知错误"));
    });
  }

  function rejectItem(itemId) {
    chrome.runtime.sendMessage({ type: "REJECT_ITEM", itemId }, (res) => {
      if (chrome.runtime.lastError) {
        console.error("REJECT error:", chrome.runtime.lastError);
        alert("拒绝失败: " + chrome.runtime.lastError.message);
        return;
      }
      if (res?.ok) loadQueue();
      else alert("拒绝失败: " + (res?.error || "未知错误"));
    });
  }

  // ── 加载统计 ────────────────────────────────────────────────────────────────
  function loadStats() {
    chrome.storage.local.get([QUEUE_KEY, QUEUE_KEY + "_stats"], (s) => {
      const raw = s[QUEUE_KEY];
      const allItems = Array.isArray(raw) ? raw : Array.isArray(raw?.items) ? raw.items : [];
      const counts = { pending: 0, approved: 0, rejected: 0, total: allItems.length };
      for (const it of allItems) {
        if (it.status === "pending" || it.status === "modified") counts.pending++;
        else if (it.status === "approved") counts.approved++;
        else if (it.status === "rejected") counts.rejected++;
      }
      document.getElementById("statPending").textContent = counts.pending;
      document.getElementById("statApproved").textContent = counts.approved;
      document.getElementById("statRejected").textContent = counts.rejected;
      document.getElementById("statTotal").textContent = counts.total;
    });
  }

  document.getElementById("clearAllBtn")?.addEventListener("click", () => {
    if (!confirm("确定要清空所有数据？此操作不可恢复。")) return;
    chrome.storage.local.remove([QUEUE_KEY, QUEUE_KEY + "_stats"], () => {
      alert("已清空全部数据。");
      loadQueue();
      loadStats();
    });
  });

  // ── 加载配置 ────────────────────────────────────────────────────────────────
  let _cfgCache = {}; // 缓存当前配置，避免闭包问题
  function loadConfig() {
    chrome.storage.sync.get(CONFIG_KEY, (s) => {
      const cfg = s[CONFIG_KEY] || {};
      _cfgCache = cfg;
      const el = (id) => document.getElementById(id);
      if (el("cfgStyle")) el("cfgStyle").value = cfg.style || "professional";
      if (el("cfgLang")) el("cfgLang").value = cfg.language || "zh";
      // LLM 配置
      if (el("cfgLLMEnabled")) el("cfgLLMEnabled").checked = !!cfg.llmEnabled;
      if (el("cfgLLMProvider")) el("cfgLLMProvider").value = cfg.llmProvider || "openai";
      if (el("cfgLLMKey")) el("cfgLLMKey").value = cfg.llmApiKey || "";
      if (el("cfgLLMBase")) el("cfgLLMBase").value = cfg.llmBaseUrl || "";
      if (el("cfgLLMModel")) el("cfgLLMModel").value = cfg.llmModel || "gpt-3.5-turbo";
      // toggles — 直接设置 class，不重复绑定事件
      const autoFetchEl = el("cfgAutoFetch");
      if (autoFetchEl) {
        autoFetchEl.classList.toggle("on", cfg.autoGenerate !== false);
      }
      const notifEl = el("cfgNotif");
      if (notifEl) {
        notifEl.classList.toggle("on", cfg.notifications !== false);
      }
      // platform toggles
      const platforms = cfg.platforms || ["x", "telegram", "discord"];
      document.querySelectorAll('[data-key]').forEach((tog) => {
        tog.classList.toggle("on", platforms.includes(tog.dataset.key));
      });
    });
  }

  // 给所有 toggle 元素绑定一次性点击事件（通过事件委托）
  document.addEventListener("click", (e) => {
    const tog = e.target.closest(".toggle");
    if (!tog) return;
    tog.classList.toggle("on");
  });

  document.getElementById("saveCfgBtn")?.addEventListener("click", () => {
    const cfg = {
      style: document.getElementById("cfgStyle")?.value || "professional",
      language: document.getElementById("cfgLang")?.value || "zh",
      autoGenerate: document.getElementById("cfgAutoFetch")?.classList.contains("on") ?? true,
      notifications: document.getElementById("cfgNotif")?.classList.contains("on") ?? true,
      platforms: [],
      // LLM 配置
      llmEnabled: document.getElementById("cfgLLMEnabled")?.checked ?? false,
      llmProvider: document.getElementById("cfgLLMProvider")?.value || "openai",
      llmApiKey: document.getElementById("cfgLLMKey")?.value || "",
      llmBaseUrl: document.getElementById("cfgLLMBase")?.value || "",
      llmModel: document.getElementById("cfgLLMModel")?.value || "gpt-3.5-turbo",
    };
    document.querySelectorAll('[data-key].on').forEach((t) => cfg.platforms.push(t.dataset.key));
    if (cfg.platforms.length === 0) cfg.platforms = ["x", "telegram", "discord"];
    chrome.storage.sync.set({ [CONFIG_KEY]: cfg }, () => {
      const btn = document.getElementById("saveCfgBtn");
      const orig = btn.textContent;
      btn.textContent = "✅ 已保存";
      setTimeout(() => (btn.textContent = orig), 1500);
      // 通知 background 更新 alarms / 配置
      chrome.runtime.sendMessage({ type: "CONFIG_UPDATED", cfg }, () => {});
    });
  });

  // ── 手动抓取按钮 ────────────────────────────────────────────────────────────
  document.getElementById("refreshBtn")?.addEventListener("click", () => {
    const btn = document.getElementById("refreshBtn");
    btn.disabled = true;
    btn.textContent = "⏳ 抓取中…";
    chrome.runtime.sendMessage({ type: "FETCH_AND_SCORE" }, (res) => {
      btn.disabled = false;
      btn.textContent = "🔄 抓取新闻";
      if (chrome.runtime.lastError) {
        alert("抓取失败: " + chrome.runtime.lastError.message);
        return;
      }
      if (res?.ok) {
        alert(`抓取完成！\n获取 ${res.fetched} 条，评分 ${res.scored} 条，新增 ${res.newItems} 条`);
        loadQueue();
        loadStats();
      } else {
        alert("抓取失败：" + (res?.error || "未知错误"));
      }
    });
  });

  // ── 初始化 ──────────────────────────────────────────────────────────────────
  loadQueue();

  // ── 工具函数 ────────────────────────────────────────────────────────────────
  function escapeHtml(str) {
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function escapeAttr(str) {
    return String(str).replace(/'/g, "&#39;").replace(/"/g, "&quot;");
  }

  function timeAgo(isoStr) {
    if (!isoStr) return "";
    const diff = (Date.now() - new Date(isoStr).getTime()) / 1000;
    if (diff < 60) return "刚刚";
    if (diff < 3600) return Math.floor(diff / 60) + "分钟前";
    if (diff < 86400) return Math.floor(diff / 3600) + "小时前";
    return Math.floor(diff / 86400) + "天前";
  }

  function platDisplay(key) {
    const map = { x: "X / Twitter", telegram: "Telegram", discord: "Discord" };
    return map[key] || key;
  }
})();
