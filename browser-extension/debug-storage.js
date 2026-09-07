// debug-storage.js — 在 Chrome 控制台运行，检查 storage 数据
(function() {
  chrome.storage.local.get(["newsdesk_queue", "newsdesk_queue_stats"], function(s) {
    console.log("=== Storage Contents ===");
    console.log("queue key:", s["newsdesk_queue"]);
    console.log("stats key:", s["newsdesk_queue_stats"]);
    console.log("=== Debug Info ===");
    const queue = s["newsdesk_queue"] || {};
    console.log("queue.items type:", typeof queue.items);
    console.log("queue.items is array:", Array.isArray(queue.items));
    console.log("queue.items length:", queue.items ? queue.items.length : "undefined");
    if (queue.items && queue.items.length > 0) {
      console.log("First item:", JSON.stringify(queue.items[0], null, 2));
    }
  });
})();
