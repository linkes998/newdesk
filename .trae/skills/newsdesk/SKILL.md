---
name: "newsdesk"
description: "Crypto & AI 多平台内容自动化流水线：RSS 抓取 → LLM 评分重排 → 多风格文案生成 → 人工审核 → 一键发布/导出。Invoke when user asks to fetch crypto/AI news, generate social media posts, review content pipeline, or publish to X/Telegram/Discord."
---

# NewsDesk — Crypto & AI 多平台内容自动化

## 项目概述

NewsDesk 是一个加密货币和 AI 领域的新闻-to-内容自动化流水线，支持：
- **RSS 抓取**：8 个主流源（CoinDesk、Cointelegraph、TheBlock、Decrypt、OpenAI Blog 等）
- **智能评分**：关键词匹配 + 时效加权 + LLM 重排（可选）
- **多风格文案生成**：10 种预设风格 × 3 个平台（X/Twitter、Telegram、Discord）
- **人工审核队列**：pending → approved/rejected → published
- **多格式导出**：Markdown、HTML（Beehiiv/Substack）、JSON、RSS 2.0
- **短视频脚本**：TikTok/YouTube Shorts 格式（~30s）
- **自动发布**：Twitter API v2、Telegram Bot、Discord Webhook

---

## 快速启动

```bash
# 开发模式（GUI）
python run_gui.py

# 开发模式（CLI）
python run.py

# 或打包后的 EXE
.\dist\NewsDesk.exe
```

---

## CLI 命令

| 命令 | 说明 |
|------|------|
| `newsdesk run` | 运行完整流水线（抓取 → 评分 → 生成 → 审核） |
| `newsdesk run --platforms x,telegram` | 指定平台 |
| `newsdesk run --style professional` | 指定风格（见下方风格列表） |
| `newsdesk run --lang en` | 英文输出 |
| `newsdesk run --auto-publish` | 跳过审核直接发布 |
| `newsdesk run --no-llm` | 不使用 LLM 重排 |
| `newsdesk review` | 交互式审核中心 |
| `newsdesk publish` | 发布所有 approved 条目 |
| `newsdesk export --format markdown` | 导出为 Markdown |
| `newsdesk export --format html` | 导出为 HTML（Beehiiv/Substack） |
| `newsdesk export --format json` | 导出为 JSON |
| `newsdesk export --format rss` | 导出 RSS 2.0 |
| `newsdesk video` | 生成短视频脚本 |
| `newsdesk list-styles` | 查看所有风格预设 |
| `newsdesk list-exports` | 查看可用导出格式 |

### 风格预设（--style）

| Key | 名称 | 特点 |
|-----|------|------|
| `professional` | 分析师专业风 | 结论先行、分点论述，适合币安广场/OKX星球 |
| `casual` | 口语化快评 | 像跟朋友聊天，适合 Telegram 群组 |
| `emoji_heavy` | Emoji 丰富风 | 大量 emoji 分隔，适合 X/Discord |
| `minimal` | 极简短句 | ≤100字，只给事实+一句话评论 |
| `thread` | X Thread 深度 | X 平台专用 thread 格式 |
| `newsletter` | Newsletter 摘要 | 带标题、要点列表、深度链接 |
| `tech_deep` | 技术深度解读 | 解释机制原理，可能含代码片段 |
| `quick_hit` | 快讯快评 | <80字，信息密度高，适合高频推送 |
| `story` | 叙事故事风 | 讲成有前因后果的小故事 |
| `price_focus` | 价格聚焦风 | 先讲价格表现，再讲催化剂 |

---

## 配置

主配置文件 `config.yaml`，支持环境变量覆盖：

```yaml
# 新闻源
feeds:
  - "https://www.coindesk.com/arc/outboundfeeds/rss/"
  - "https://cointelegraph.com/rss"
  # ...（共 8 个源）

# 关键词（粗筛）
keywords:
  crypto: [bitcoin, btc, ethereum, eth, solana, xrp, ...]
  ai: [ai, openai, anthropic, gpt, claude, llm, ...]

# 阈值
threshold:
  score_min: 2.0
  max_age_hours: 48
  max_items: 8

# LLM（可选重排）
llm_ranker:
  enabled: true
  weight_keywords: 0.4
  weight_llm: 0.6

# LLM API
llm:
  api_key: "your-key"
  base_url: "https://api.agnes-ai.cn/v1"
  model: "agnes-2.5-flash"
```

环境变量覆盖：
- `NEWSDESK_LLM_API_KEY` → `llm.api_key`
- `NEWSDESK_LLM_BASE_URL` → `llm.base_url`
- `NEWSDESK_LLM_MODEL` → `llm.model`

---

## 项目结构

```
news-setup/
├── src/newsdesk/
│   ├── config.py          # 配置加载（YAML + 环境变量）
│   ├── rss.py             # RSS 抓取（feedparser + 文件缓存）
│   ├── scoring.py         # 关键词评分 + 时效加权
│   ├── ranker.py          # LLM 相关性重排
│   ├── llm.py             # OpenAI 兼容客户端 + fallback 链
│   ├── templates.py       # 10 种风格预设 + 平台 prompt 模板
│   ├── pipeline.py        # 流水线编排 + CLI 入口
│   ├── review.py          # 审核队列（状态机 + JSON 持久化）
│   ├── publisher.py       # X/Telegram/Discord 发布适配器
│   ├── export.py          # 多格式导出（MD/HTML/JSON/RSS）
│   ├── video.py           # 短视频脚本生成
│   ├── gui.py             # CustomTkinter 桌面 GUI
│   └── scheduler.py       # APScheduler 后台守护
├── tests/                 # pytest 测试套件（27 tests）
├── samples/               # 三平台风格样本
├── data/                  # 流水线断点 + 审核队列（JSON）
├── output/                # 生成的内容
├── config.yaml            # 主配置
├── run.py                 # CLI 入口（带 UTF-8 修复）
├── run_gui.py             # GUI 入口
└── dist/NewsDesk.exe      # 打包后的 Windows 应用（120MB）
```

---

## 流水线数据流

```
RSS Feeds (8 sources)
    │
    ▼
[scoring.py] 关键词评分 + 时效加权（-1.0 ~ +2.0，基于 48h 内衰减）
    │
    ▼
[ranker.py]   LLM 相关性重排（可选，默认开启）
    │
    ▼
[templates.py] LLM 文案生成（style × platform × language）
    │
    ▼
[review.py]   人工审核队列（pending → approved/rejected）
    │
    ├─► [publisher.py] 自动发布到 X/Telegram/Discord
    └─► [export.py] 导出为 MD/HTML/JSON/RSS
```

---

## 浏览器插件（Browser Extension）

位于 `browser-extension/` 目录，为 Chrome/Edge 扩展，在支持的新闻网站上注入浮窗按钮：

```
browser-extension/
├── manifest.json          # Manifest V3
├── background.js          # Service Worker（消息路由 + 健康检查）
├── content.js             # 注入到新闻站点，检测文章并显示"Send to NewsDesk"按钮
├── popup.html             # 插件弹窗（队列管理 + 统计 + 设置）
├── popup.js               # 弹窗逻辑
├── inject-badge.js        # 页面内浮动提示
├── browser_extension_server.py  # 本地 API 服务器（:18923）
└── icons/                 # 扩展图标（需自行添加 PNG）
```

安装步骤：
1. 启动 API 服务器：`python browser-extension/browser_extension_server.py`
2. Chrome：`chrome://extensions/` → 开发者模式 → 加载已解压的扩展 → 选择 `browser-extension/`
3. 访问 CoinDesk/Cointelegraph 等站点，页面右下角出现"📰 Send to NewsDesk"按钮

---

## 测试

```bash
pytest tests/ -v
# 预期：27 passed
```

---

## 常见问题

**Q: 抓取返回 0 条？**
A: 检查 `max_age_hours`（默认 48h），如果设为 6h 会过滤掉大部分新闻。检查关键词是否覆盖目标词汇。

**Q: LLM 生成失败？**
A: 检查 `config.yaml` 中 `llm.api_key` 是否正确，或设置 `--no-llm` 使用模板降级模式。

**Q: 发布失败？**
A: Twitter 需要 Bearer Token + API Key/Secret + OAuth Token/Secret；Telegram 需要 Bot Token + Chat ID；Discord 需要 Webhook URL。
