# NewsDesk — Crypto & AI News

## Chrome 应用商店发布文档

***

## 一、基础信息

### 应用名称（英文）

**NewsDesk — Crypto & AI News**

### 应用名称（中文）

**NewsDesk — 加密货币 & AI 新闻助手**

### 短描述（≤132 字符）

Browser extension that tracks crypto & AI news, scores relevance, and generates multi-platform drafts — fully offline, no server needed.

### 长描述（≤4000 字符）

NewsDesk is a Chrome extension that helps content creators, marketers, and crypto/AI enthusiasts stay on top of the latest news in cryptocurrency and artificial intelligence. It automatically fetches RSS feeds from top industry sources, scores articles by relevance, and generates platform-ready draft posts — all running entirely in your browser with zero server dependency.

**Key Features:**

- **Automatic News Discovery**: Pulls from 8+ top crypto and AI news sources including CoinDesk, Cointelegraph, The Block, Decrypt, CoinGecko, OpenAI Blog, CryptoNews, and CoinMarketCap.

- **Smart Relevance Scoring**: Algorithms score each article based on keyword matches (33 crypto terms, 16 AI terms), freshness, exclusivity, and premium signals — filtering out spam, giveaways, and low-value content.

- **10 Writing Styles**: Generate drafts in professional analyst tone, casual commentary, emoji-rich style, minimalist, X Thread format, newsletter summary, tech deep-dive, quick hit, narrative storytelling, or price-focused — all available in both Chinese and English.

- **Multi-Platform Output**: Automatically formats drafts for X/Twitter, Telegram, and Discord with appropriate character limits and structural conventions.

- **Fully Offline**: All data lives in your browser's local storage. No accounts, no servers, no data collection. Works without internet after first load.

- **Scheduled Auto-Fetch**: Background service checks for new news every 30 minutes (configurable) and notifies you of breaking stories.

- **Content Queue**: Review, approve, reject, and edit drafts before publishing. History tracks every action.

- **Cross-Device Sync**: Settings sync via chrome.storage.sync so your preferences follow you across browsers.

**Supported Sources:**
CoinDesk, Cointelegraph, The Block, Decrypt, OpenAI Blog, CryptoNews, CoinGecko News, CoinMarketCap

**Privacy:**
NewsDesk collects zero personal data. All news items, drafts, and settings remain stored locally in your browser. No analytics, no telemetry, no third-party tracking.

***

## 二、分类与标签

### 主要分类

\*\* productivity \*\*（生产力工具）

### 次要分类

\*\* news **（新闻）、** developer tools \*\*（开发者工具）

### 关键词标签（可选填）

crypto, bitcoin, ethereum, AI, artificial intelligence, news, RSS, content creation, social media, Twitter, Telegram, Discord, marketing, copywriting, automation

***

## 三、截图建议（至少需 2 张，推荐 5 张）

| 序号 | 用途      | 建议内容                                    |
| -- | ------- | --------------------------------------- |
| 1  | 主图/商店封面 | 扩展图标 + 深色背景，突出"离线模式"徽章                  |
| 2  | 队列面板    | 展示待审核新闻卡片，含评分标签和批准/拒绝按钮                 |
| 3  | 草稿编辑    | 展示多平台草稿对比（X / Telegram / Discord 三个文本框） |
| 4  | 设置面板    | 展示文案风格选择器和平台开关                          |
| 5  | 统计面板    | 展示待审核/已批准/已拒绝计数卡片                       |

**截图尺寸要求：**

- 最小：1280×800 像素

- 推荐：1920×1080 像素

- 格式：PNG 或 JPEG

- 不超过 4MB 每张

***

## 四、功能图标

- **默认图标尺寸**：16×16、48×48、128×128（已内置）

- **商店图标要求**：512×512 PNG，无透明通道

- **建议**：上传与扩展内图标同风格的 512×512 紫色渐变版本

***

## 五、隐私政策 URL

> ⚠️ Chrome 应用商店要求提供隐私政策 URL。
>
> 如暂无独立页面，可在 GitHub 仓库 README 中声明，或创建简单的隐私政策页面托管在 GitHub Pages。

**建议文案（可直接放入 README 或独立页面）：**

> **NewsDesk Privacy Policy**
>
> NewsDesk does not collect, transmit, or store any personal data. All news items, scores, drafts, and user settings are stored exclusively in your browser's local storage (chrome.storage.local). No network requests are made to any server other than the public Google rss2json.com API (used solely to fetch RSS feeds; no personal data is transmitted). We do not use analytics, crash reporting, or any form of telemetry. You may uninstall NewsDesk at any time and all stored data will be removed.

**隐私政策 URL 示例**（托管在 GitHub Pages）：
`https://<your-username>.github.io/newsdesk-privacy/`

***

## 六、官网/支持页面 URL（可选）

- **官方网站**：留空或在 README 中说明

- **支持邮箱**：建议提供一个用于处理用户反馈的邮箱

- **问题反馈**：可指向项目的 GitHub Issues 页面

***

## 七、Chrome Web Store 上传清单

上传前请确认以下文件完整：

```
browser-extension/
├── manifest.json          ✅ Manifest V3
├── background.js          ✅ Service Worker
├── content.js             ✅ 内容脚本
├── popup.html             ✅ 弹出面板 HTML
├── popup.js               ✅ 弹出面板逻辑
├── rss_fetcher.js         ✅ RSS 抓取（rss2json 代理）
├── scorer.js              ✅ 文章评分引擎
├── generate_drafts.js     ✅ 文案生成引擎
├── inject-badge.js        ✅ 页面徽章注入
├── icons/
│   ├── icon16.png         ✅
│   ├── icon48.png         ✅
│   └── icon128.png        ✅
└── .gitignore
```

**压缩打包命令：**

```bash
cd d:\AI-auto\news-setup\browser-extension
tar -czf newsdesk-extension-v0.4.0.tar.gz \
  manifest.json background.js content.js popup.html popup.js \
  rss_fetcher.js scorer.js generate_drafts.js inject-badge.js \
  icons/ .gitignore
```

**上传步骤：**

1. 打开 [Chrome Developer Dashboard](https://chrome.google.com/webstore/devconsole)
2. 点击「新增项目」→ 填写应用名称、分类、描述
3. 上传 `newsdesk-extension-v0.4.0.crx` 或拖入目录
4. 上传 512×512 图标
5. 上传截图
6. 填写隐私政策 URL
7. 提交审核

***

## 八、常见问题（FAQ，供商店页面使用）

**Q: NewsDesk 需要联网吗？**
A: 首次加载扩展时需要联网以获取 RSS 数据。之后所有数据存储在浏览器本地，关闭标签页后仍保留。

**Q: 我的数据安全吗？**
A: 完全安全。所有数据仅存储在您的浏览器本地，不上传至任何服务器，无需注册账号。

**Q: 支持哪些新闻源？**
A: 目前支持 8 个顶级来源：CoinDesk、Cointelegraph、The Block、Decrypt、OpenAI Blog、CryptoNews、CoinGecko News、CoinMarketCap。我们会持续添加新源。

**Q: 能否自定义新闻源？**
A: 当前版本不支持自定义 RSS 源，后续版本将开放配置。

**Q: 文案可以修改吗？**
A: 可以。每篇新闻生成后，您可以在队列中点击「批准」前的任意时刻修改草稿内容，支持逐平台单独编辑。

**Q: 发布到 X / Telegram 需要额外授权吗？**
A: 当前版本仅生成草稿供您复制粘贴使用。自动发布功能计划在未来版本中支持 OAuth 授权接入。

***

## 九、开源信息（可选推荐）

- **GitHub 仓库**：`d:\AI-auto\news-setup`

- **许可证**：建议 MIT License

- **变更日志**：已在项目 CHANGELOG.md 中维护

***

## 十、审核注意事项

Chrome 应用商店审核时可能关注以下问题，请提前准备：

| 审核关注点       | 应对说明                                    |
| ----------- | --------------------------------------- |
| 数据收集        | 明确声明零数据收集，仅使用本地存储                       |
| 网络权限        | 仅访问 rss2json.com 公共 API 获取 RSS，无其他外部请求  |
| 内容安全        | 所有内容由用户本地生成，无用户生成内容托管                   |
| 权限最小化       | 仅请求 storage、notifications、alarms 三项必要权限 |
| Manifest V3 | 已使用最新 Manifest V3 规范，无 deprecated API   |

