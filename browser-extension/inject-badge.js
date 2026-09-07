// inject-badge.js — runs inside the page context (web_accessible_resources)
// Adds a small "Detected" badge near the article title when the page loads
(function () {
  "use strict";
  const badge = document.createElement("div");
  badge.id = "newsdesk-badge";
  badge.textContent = "📰 NewsDesk Ready";
  Object.assign(badge.style, {
    position: "fixed",
    top: "12px",
    right: "12px",
    zIndex: "2147483647",
    background: "linear-gradient(135deg,#6366f1,#8b5cf6)",
    color: "#fff",
    fontSize: "11px",
    fontWeight: "700",
    padding: "4px 10px",
    borderRadius: "12px",
    boxShadow: "0 2px 8px rgba(99,102,241,.5)",
    pointerEvents: "none",
    opacity: "0",
    transition: "opacity .3s",
  });
  document.body.appendChild(badge);
  setTimeout(() => (badge.style.opacity = "1"), 500);
  setTimeout(() => (badge.style.opacity = "0"), 4000);
})();
