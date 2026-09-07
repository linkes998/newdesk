# NewsDesk — Crypto & AI News
> 浏览器端加密货币 & AI 新闻嗅探 + 多平台文案生成扩展，完全离线运行。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Chrome Web Store](https://img.shields.io/badge/Chrome-Extension-blue?logo=google-chrome)](https://chrome.google.com/webstore)
[![Version](https://img.shields.io/badge/version-0.4.0-purple)](#)

---

## 📰 简介

NewsDesk 是一个 Chrome 浏览器扩展，帮助内容创作者、营销人员和 crypto/AI 爱好者实时追踪行业动态，自动生成多平台文案草稿——**全程离线，无需任何本地服务器**。

### 核心能力

| 功能 | 说明 |
|------|------|
| 🤖 **智能嗅探** | 每 30 分钟自动抓取 8+ 顶级 Crypto & AI 新闻源 |
| ⭐ **精准评分** | 33 个加密货币关键词 + 16 个 AI 关键词双重过滤，自动识别高质量内容 |
| ✍️ **10 种文案风格** | 分析师专业风、口语化快评、Emoji 丰富风、X Thread、Newsletter、技术深度解读等 |
| 📱 **多平台适配** | 自动适配 X/Twitter（280字）、Telegram（4096字）、Discord（2000字）格式 |
| 🔒 **完全离线** | 数据存储在浏览器本地，零服务端依赖，零用户数据收集 |
| ⏰ **定时任务** | 后台定时抓取 + 桌面通知，不错过任何重要资讯 |

---

## 🚀 安装

### 方式一：Chrome 应用商店（推荐）
> 正在申请上架中，敬请期待。

### 方式二：开发者模式手动安装

```bash
# 1. 克隆仓库
git clone https://github.com/YOUR_USERNAME/news-setup.git
cd news-setup/browser-extension

# 2. 打开 Chrome，访问 chrome://extensions/
# 3. 开启右上角「开发者模式」
# 4. 点击「加载已解压的扩展程序」
# 5. 选择 browser-extension/ 目录
```

### 方式三：打包发布

```bash
tar -czf newsdesk-extension-v0.4.0.tar.gz \
  manifest.json background.js content.js popup.html popup.js \
  rss_fetcher.js scorer.js generate_drafts.js inject-badge.js icons/
```

---

## 📡 支持的数据源

### 加密货币
- CoinDesk (`coindesk.com`)
- Cointelegraph (`cointelegraph.com`)
- The Block (`theblock.co`)
- Decrypt (`decrypt.co`)
- CryptoNews (`cryptonews.com`)
- CoinGecko News (`coingecko.com/en/news`)
- CoinMarketCap (`coinmarketcap.com`)

### AI / 技术
- OpenAI Blog (`openai.com/blog`)

---

## ✍️ 支持的文案风格

| 风格键 | 名称 | 适用场景 |
|--------|------|---------|
| `professional` | 分析师专业风 | 机构级内容产出 |
| `casual` | 口语化快评 | 个人社交媒体 |
| `emoji_heavy` | Emoji 丰富风 | 吸引眼球的内容 |
| `minimal` | 极简短句 | 快讯类推送 |
| `thread` | X Thread 深度 | Twitter 长文 thread |
| `newsletter` | Newsletter 摘要 | 邮件通讯 |
| `tech_deep` | 技术深度解读 | 技术向读者 |
| `quick_hit` | 快讯快评 | 快速响应市场 |
| `story` | 叙事故事风 | 深度故事类内容 |
| `price_focus` | 价格聚焦风 | 行情分析类 |

---

## 🔧 使用流程

### 1. 自动模式（推荐）
扩展安装后，每 30 分钟自动抓取新闻。新内容会自动进入审核队列，并弹出桌面通知。

### 2. 主动抓取
点击扩展图标 → 点击「🔄 抓取新闻」按钮，立即触发全网扫描。

### 3. 页面注入
访问支持站点（如 coindesk.com）时，页面右下角会自动出现「Send to NewsDesk」按钮，一键将当前文章加入队列。

### 4. 编辑与发布
- **待审核**：查看评分、修改草稿、选择平台
- **批准**：草稿状态标记为已审核通过，可复制到目标平台
- **拒绝**：从队列中移除该条目

---

## 🛡️ 隐私与安全

- ✅ **零数据收集**：不采集任何个人信息
- ✅ **本地存储**：所有数据存储在 `chrome.storage.local`
- ✅ **无需账号**：不需要注册或登录
- ✅ **无遥测**：不发送使用统计或崩溃报告
- ✅ **开源**：代码完全公开，可自行审计

扩展仅通过 Google 公共 API（rss2json.com）获取 RSS 数据，该 API 不记录个人身份信息。

---

## 📂 项目结构

```
news-setup/
├── browser-extension/
│   ├── manifest.json          # Manifest V3 配置
│   ├── background.js          # Service Worker（定时抓取、消息路由）
│   ├── content.js             # 页面内容脚本（文章检测、一键提交）
│   ├── popup.html             # 弹出面板界面
│   ├── popup.js               # 弹出面板交互逻辑
│   ├── rss_fetcher.js         # RSS 抓取（rss2json.com 代理）
│   ├── scorer.js              # 文章评分引擎
│   ├── generate_drafts.js     # 文案生成引擎（10 种风格）
│   ├── inject-badge.js        # 页面徽章注入
│   └── icons/                 # 扩展图标（16/48/128）
├── src/newsdesk/              # Python CLI 后端（可选）
│   ├── config.py
│   ├── scoring.py
│   ├── templates.py
│   └── ...
└── tests/                     # 27 个单元测试（全绿）
```

---

## 🧪 开发

### 运行测试
```bash
cd d:\AI-auto\news-setup
python -m pytest tests/ -x -q
# 27 passed ✅
```

### 本地调试扩展
```bash
# 1. 加载到 Chrome
chrome://extensions/ → 开发者模式 → 加载已解压的扩展程序
# 2. 打开 background.js 对应的 Service Worker 调试页
# 3. 在支持站点测试 content.js 注入效果
```

### 打包发布
```bash
# 生成 CRX 文件（需要私钥）
# 参考：https://developer.chrome.com/docs/webstore/package
```

---

## 📝 许可证

[MIT License](LICENSE) — 免费使用、修改、分发。

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/xxx`)
3. 提交变更 (`git commit -am 'Add xxx'`)
4. 推送到分支 (`git push origin feature/xxx`)
5. 创建 Pull Request

---

## 📧 联系方式

- GitHub Issues：提交功能建议或 bug 反馈
- 邮箱：your-email@example.com
- 中文文档：[STORE_LANDING.md](browser-extension/STORE_LANDING.md)（Chrome 商店发布文档）
