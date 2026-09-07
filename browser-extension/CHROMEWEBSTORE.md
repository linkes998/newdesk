# CHROMEWEBSTORE.md — NewsDesk 商店提交元数据

> 由 Modern Web Guidance 自动生成 · 最后更新 2026-09-06
> 用于 Chrome Web Store 审核时快速填写"用途声明"和"权限说明"字段

---

## App 基本信息

| 字段 | 值 |
|------|-----|
| **名称（英文）** | NewsDesk — Crypto & AI News |
| **名称（中文）** | NewsDesk — 加密货币与 AI 新闻助手 |
| **版本** | 0.4.0 |
| **Manifest V3** | ✅ 是 |
| **Chrome Web Store ID** | （待发布后填入） |

---

## Single Purpose（单一用途声明）

**简短声明（≤50字，用于商店标题下方的说明文字）：**

> 在浏览器中实时嗅探加密货币和 AI 领域的重要新闻，离线评分并一键生成多平台文案草稿，支持 X、Telegram、Discord。

**完整用途描述（用于审核表单"Extension Purpose"字段，≤500字）：**

> NewsDesk 是一款面向加密货币和人工智能领域的新闻聚合与内容创作助手浏览器扩展。它在用户访问支持的信息站点（CoinDesk、Cointelegraph、The Block、Decrypt、OpenAI Blog 等）时自动检测新闻文章，使用本地关键词规则引擎对文章进行相关性和新鲜度评分，过滤低价值内容；评分合格的文章会自动生成针对 X (Twitter)、Telegram、Discord 三个平台的适配文案草稿（支持 10 种写作风格，中英双语）。用户通过扩展弹窗管理审核队列，对草稿进行编辑、批准或拒绝。所有数据处理均在本地完成，无需联网即可运行核心功能，仅在使用 RSS 抓取时会调用第三方代理 API（Google rss2json.com，不可追踪，不存储任何用户数据）。扩展不会读取、修改或上传用户的浏览历史、个人数据或任何不在白名单站点内的内容。

---

## Permissions Justification（权限声明）

Chrome Web Store 审核要求为每一项权限提供合理说明：

| 权限 | 是否必要 | 详细说明 |
|------|----------|----------|
| **`storage`** | ✅ 必要 | 用于在 `chrome.storage.local` 中持久化保存新闻审核队列（标题、链接、评分、草稿内容）和用户在设置面板中的偏好配置（风格、语言、目标平台、是否自动抓取）。数据仅存储在用户本地浏览器中，不上传至任何服务器。使用 `storage.sync` 存储跨设备同步的用户偏好。 |
| **`notifications`** | ✅ 必要 | 当后台自动抓取发现新的高分新闻时，通过系统通知告知用户。通知仅在用户已授予权限的前提下触发，且仅显示新闻标题和新增数量，不透露具体敏感内容。用户可随时在 Chrome 设置中关闭该权限。 |
| **`alarms`** | ✅ 必要 | 用于设置后台定时任务（每 30 分钟），在无用户打开页面的情况下持续运行 RSS 抓取和评分逻辑。这是 Service Worker 模式下维持周期性任务的关键机制，无此权限扩展无法在用户关闭标签页后继续工作。 |
| **`web_accessible_resources`** | ✅ 必要 | 允许 `inject-badge.js` 在匹配的新闻页面内注入悬浮按钮（"Send to NewsDesk"）。资源被限制在特定域名白名单内，不会暴露给其他网站。 |

**明确声明 NOT 使用的权限：**

- ❌ `activeTab` — 不读取当前标签页内容，仅通过 content script 在指定白名单域名运行
- ❌ `tabs` — 不操作或切换标签页
- ❌ `contextMenus` — 不添加右键菜单
- ❌ `cookies` — 不读取或写入 Cookie
- ❌ `webRequest` — 不拦截或修改网络请求（除内容脚本的 fetch 外）
- ❌ `proxy` — 不使用代理
- ❌ `privacy` — 不管理系统隐私设置
- ❌ `unlimitedStorage` — 不需要超出默认配额
- ❌ `nativeMessaging` — 不与本机程序通信
- ❌ `https://*/*` 等 host_permissions — 无外部服务依赖，无需额外主机权限

---

## Data Safety（数据安全声明）

**数据收集情况：**

| 数据类型 | 是否收集 | 存储位置 | 用途 | 是否上传 |
|----------|----------|----------|------|----------|
| 用户浏览历史记录 | ❌ 否 | — | — | ❌ 否 |
| 个人身份信息（姓名/邮箱/手机号） | ❌ 否 | — | — | ❌ 否 |
| 财务信息（信用卡/银行） | ❌ 否 | — | — | ❌ 否 |
| 浏览过的 URL 列表 | ⚠️ 部分 | 本地 storage | 仅当用户在白名单新闻站点手动点击"发送到 NewsDesk"时才记录当前 URL，用于生成新闻链接 | ❌ 否 |
| 生成的文案草稿 | ✅ 是 | 本地 storage | 存储在用户本地，供编辑和复制使用 | ❌ 否 |
| RSS 抓取的新闻标题/摘要 | ✅ 是 | 本地 storage | 存储在用户本地队列中，供审核和编辑 | ❌ 否 |
| 用户设置偏好（风格/语言/平台） | ✅ 是 | storage.sync（可选同步） | 跨设备同步用户偏好 | ❌ 否（同步仅由 Chrome 账户加密存储） |

**第三方服务：**

| 服务 | 用途 | 数据共享范围 |
|------|------|------------|
| Google rss2json.com API | RSS → JSON 格式转换（绕过 CORS） | 仅发送公开 RSS feed URL，不发送用户身份信息 |
| 无 LLM API | 所有文案生成均为本地模板规则引擎，不调用任何外部 AI API | 无数据外传 |

**隐私政策链接：**

> https://newsdesk-official.github.io/privacy-policy

（请将上述链接替换为实际部署的隐私政策页面 URL）

---

## Required Prompts / Flows（必要交互流程）

以下用户交互流程是扩展正常运行的必要组成部分：

1. **首次安装后的配置引导**
   - 弹窗展示欢迎界面，引导用户选择写作风格、语言和目标平台
   - 请求通知权限（如尚未授权）

2. **新闻页面的"发送到 NewsDesk"按钮**
   - 在白名单新闻站点加载完成后，右下角自动出现悬浮按钮
   - 点击后自动评分，生成草稿并加入审核队列，按钮显示反馈状态

3. **后台自动抓取**
   - 每 30 分钟自动抓取 8 个预设 RSS feed
   - 新发现高分文章时弹出系统通知
   - 用户可在设置面板关闭自动抓取

4. **审核队列管理（弹窗）**
   - 显示所有待审核新闻条目，包含标题、来源、评分、草稿内容
   - 支持批准、拒绝、编辑草稿、复制链接等操作
   - 支持清空队列、刷新抓取

5. **设置面板**
   - 调整写作风格（10 种可选）
   - 切换语言（中文/英文）
   - 选择目标平台（X / Telegram / Discord）
   - 开关自动抓取，调整分数阈值和最大年龄

---

## Store Listing Metadata（商店列表元数据）

### 截图建议（5 张，按推荐顺序）

| 编号 | 场景 | 尺寸 | 内容说明 |
|------|------|------|----------|
| 1 | 扩展弹窗主界面 | 1280×800 | 深色主题队列管理页面，展示多条新闻卡片及"批准"/"拒绝"操作按钮 |
| 2 | 新闻页面悬浮按钮 | 1280×800 | CoinDesk 文章页右下角的"Send to NewsDesk"按钮高亮状态 |
| 3 | 设置面板 | 1280×800 | 弹窗右侧"设置"标签页，展示风格下拉框、语言选择、平台勾选 |
| 4 | 统计面板 | 1280×800 | 弹窗"统计"标签页，展示待处理/已批准/已拒绝数量 |
| 5 | 多平台草稿预览 | 1280×800 | 队列中一条新闻展开后显示 X / Telegram / Discord 三个平台的草稿对比 |

### 分类

- **主要类别**：生产力工具（Productivity）
- **次要类别**：新闻与杂志（News & Magazines）

### 标签（Tags）

```
news, crypto, bitcoin, ai, article, content, creator, social media, telegram, twitter, discord, newsletter, automation, rss, writer, editor, productivity
```

### 语言

- 主要语言：英语
- 支持语言：简体中文

---

## Review Considerations（审核注意事项）

| 审核要点 | 状态 | 说明 |
|----------|------|------|
| Manifest V3 合规 | ✅ 符合 | 使用 Service Worker，无旧式 background page |
| 无远程代码执行 | ✅ 符合 | 所有 JS 文件打包在扩展内，无 dynamic script eval |
| 权限最小化 | ✅ 符合 | 仅使用 storage/notifications/alarms，无敏感权限 |
| 无恶意行为 | ✅ 符合 | 不注入广告、不重定向、不窃取数据 |
| 单一用途清晰 | ✅ 符合 | 新闻聚合 + 内容生成，目的明确 |
| 隐私政策链接 | ⚠️ 待完成 | 需部署实际隐私政策页面，更新本文件中的链接 |
| 无外部 LLM 调用 | ✅ 符合 | 全部使用本地模板规则引擎 |
| 无 native messaging | ✅ 符合 | 不连接本机应用 |

---

## 生成命令

```bash
# 打包扩展（用于上传至 Chrome Web Store）
cd browser-extension
zip -r ../newsdesk-extension-0.4.0.zip .

# 验证 Manifest V3 合规
python -m json.tool manifest.json > /dev/null && echo "✅ manifest.json 格式正确"
```
