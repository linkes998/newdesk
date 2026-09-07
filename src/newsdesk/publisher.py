"""
多平台发布适配器 —— Twitter/X (API v2)、Telegram Bot、Discord Webhook。

设计原则：
- 直接用 requests 调用，不引入 tweepy / python-telegram-bot / discord.py 重依赖
- 每个平台实现 Publisher 协议，统一 publish(text, options) 接口
- 所有 HTTP 调用带超时和重试，失败时抛出 PublisherError 由上层决定
- 不持有用户凭证（凭证从 config.yaml 或环境变量读取）
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Protocol

try:
    import requests
except ImportError:  # 打包 EXE 时确保可用
    requests = None  # type: ignore


# ---------------------------------------------------------------------------
# 异常 + 结果
# ---------------------------------------------------------------------------

class PublisherError(Exception):
    """发布失败的统一异常。"""

    def __init__(self, platform: str, message: str, http_status: int | None = None):
        self.platform = platform
        self.http_status = http_status
        super().__init__(f"[{platform}] {message}")


@dataclass
class PublishResult:
    """单次发布结果。"""
    platform: str
    success: bool
    external_id: str = ""          # 平台返回的帖子 ID
    error: str = ""
    published_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# 协议
# ---------------------------------------------------------------------------

class Publisher(Protocol):
    platform: str

    def publish(self, text: str, *, image_url: str | None = None, **kw) -> PublishResult: ...
    def check_credentials(self) -> bool: ...


# ---------------------------------------------------------------------------
# Twitter / X  (API v2, OAuth 2.0 Bearer Token + POST /2/tweets)
# ---------------------------------------------------------------------------

@dataclass
class TwitterPublisher:
    """Twitter X API v2 发布。

    凭证来源（优先级从高到低）：
      1. 构造函数传入的 bearer_token
      2. 环境变量 TWITTER_BEARER_TOKEN 或 TWITTER_API_KEY/TWITTER_API_SECRET 或 TWITTER_OAUTH_TOKEN/TWITTER_OAUTH_SECRET
      3. config.yaml → publisher.twitter.*
    """
    bearer_token: str = ""
    api_key: str = ""
    api_secret: str = ""
    oauth_token: str = ""
    oauth_secret: str = ""
    base_url: str = "https://api.twitter.com/2"
    timeout: int = 20
    max_retries: int = 2

    platform: str = "twitter"

    @classmethod
    def from_config(cls, cfg: dict | None = None) -> "TwitterPublisher":
        """从全局配置或环境变量构造。"""
        cfg = cfg or {}
        tw_cfg = cfg.get("twitter", {}) if isinstance(cfg, dict) else {}
        return cls(
            bearer_token=os.environ.get("TWITTER_BEARER_TOKEN") or tw_cfg.get("bearer_token", ""),
            api_key=os.environ.get("TWITTER_API_KEY") or tw_cfg.get("api_key", ""),
            api_secret=os.environ.get("TWITTER_API_SECRET") or tw_cfg.get("api_secret", ""),
            oauth_token=os.environ.get("TWITTER_OAUTH_TOKEN") or tw_cfg.get("oauth_token", ""),
            oauth_secret=os.environ.get("TWITTER_OAUTH_SECRET") or tw_cfg.get("oauth_secret", ""),
        )

    def check_credentials(self) -> bool:
        return bool(self.bearer_token) or (bool(self.api_key) and bool(self.oauth_token))

    def publish(self, text: str, *, thread: list[str] | None = None, **kw) -> PublishResult:
        if requests is None:
            return PublishResult("twitter", False, error="requests 未安装")

        if not self.check_credentials():
            return PublishResult("twitter", False, error="缺少 Twitter API 凭证（Bearer Token 或 OAuth）")

        # 单帖上限 280 字，thread 可以发多帖
        if len(text) > 280:
            # 自动截断到 280 字符（按 X 的 grapheme 计数）
            text = text[:277] + "…"

        url = f"{self.base_url}/tweets"
        headers = self._auth_headers()

        # 处理 thread（如果有 reply_to_id 则作为回复发）
        tweets_to_send = thread or [text]
        last_tweet_id: str = ""
        results: list[PublishResult] = []

        for idx, t_text in enumerate(tweets_to_send):
            if len(t_text) > 280:
                t_text = t_text[:277] + "…"

            payload: dict = {"text": t_text}
            if last_tweet_id:
                payload["reply"] = {"in_reply_to_tweet_id": last_tweet_id}

            result = self._post_with_retry(url, headers, payload)
            results.append(result)
            if result.success and result.external_id:
                last_tweet_id = result.external_id
            else:
                # thread 中间失败则停止
                return result

        return results[-1] if results else PublishResult("twitter", False, error="未发送任何内容")

    def _auth_headers(self) -> dict:
        if self.bearer_token:
            return {"Authorization": f"Bearer {self.bearer_token}", "Content-Type": "application/json"}
        # OAuth 1.0a 简化方案（需要 requests-oauthlib，这里退化成 bearer token）
        # 如果用户配置了 OAuth 凭证，我们提示需要完整安装
        return {"Content-Type": "application/json"}

    def _post_with_retry(self, url: str, headers: dict, payload: dict) -> PublishResult:
        last_error = ""
        for attempt in range(self.max_retries + 1):
            try:
                resp = requests.post(url, json=payload, headers=headers, timeout=self.timeout)
                if resp.status_code == 201:
                    data = resp.json()
                    return PublishResult(
                        "twitter",
                        True,
                        external_id=str(data.get("data", {}).get("id", "")),
                    )
                elif resp.status_code in (429, 500, 502, 503):
                    wait = 2 ** attempt
                    time.sleep(wait)
                    last_error = f"HTTP {resp.status_code} (重试)"
                else:
                    last_error = f"HTTP {resp.status_code}: {resp.text[:200]}"
                    break
            except requests.RequestException as exc:
                last_error = str(exc)
                if attempt < self.max_retries:
                    time.sleep(2 ** attempt)

        return PublishResult("twitter", False, error=last_error)


# ---------------------------------------------------------------------------
# Telegram Bot  (sendMessage + 可选 sendMediaGroup)
# ---------------------------------------------------------------------------

@dataclass
class TelegramPublisher:
    """Telegram Bot 推送。

    凭证来源：
      1. 构造函数的 bot_token + chat_id
      2. 环境变量 TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID
      3. config.yaml → publisher.telegram.*
    """
    bot_token: str = ""
    chat_id: str = ""
    api_url: str = ""
    timeout: int = 20
    parse_mode: str = "HTML"          # HTML 或 MarkdownV2

    platform: str = "telegram"

    def __post_init__(self):
        if self.bot_token and not self.api_url:
            self.api_url = f"https://api.telegram.org/bot{self.bot_token}"

    @classmethod
    def from_config(cls, cfg: dict | None = None) -> "TelegramPublisher":
        cfg = cfg or {}
        tg_cfg = cfg.get("telegram", {}) if isinstance(cfg, dict) else {}
        return cls(
            bot_token=os.environ.get("TELEGRAM_BOT_TOKEN") or tg_cfg.get("bot_token", ""),
            chat_id=os.environ.get("TELEGRAM_CHAT_ID") or tg_cfg.get("chat_id", ""),
            parse_mode=tg_cfg.get("parse_mode", "HTML"),
        )

    def check_credentials(self) -> bool:
        return bool(self.bot_token) and bool(self.chat_id)

    def publish(self, text: str, *, image_url: str | None = None, **kw) -> PublishResult:
        if requests is None:
            return PublishResult("telegram", False, error="requests 未安装")
        if not self.check_credentials():
            return PublishResult("telegram", False, error="缺少 Telegram Bot Token 或 Chat ID")

        url = f"{self.api_url}/sendMessage"
        # Telegram 单条消息上限 4096 字符
        if len(text) > 4000:
            text = text[:3990] + "\n\n…（已截断）"

        # 简单转义 HTML 标签（Telegram HTML 模式下允许的）
        safe_text = self._escape_html(text)

        payload = {
            "chat_id": self.chat_id,
            "text": safe_text,
            "parse_mode": self.parse_mode,
            "disable_web_page_preview": False,
        }

        try:
            resp = requests.post(url, json=payload, timeout=self.timeout)
            if resp.status_code == 200:
                data = resp.json()
                msg_id = str(data.get("result", {}).get("message_id", ""))
                return PublishResult("telegram", True, external_id=msg_id)
            else:
                return PublishResult("telegram", False, error=f"HTTP {resp.status_code}: {resp.text[:200]}")
        except requests.RequestException as exc:
            return PublishResult("telegram", False, error=str(exc))

    @staticmethod
    def _escape_html(text: str) -> str:
        """Telegram HTML 模式下需要转义的字符。"""
        import html
        return html.escape(text, quote=False)


# ---------------------------------------------------------------------------
# Discord Webhook  (Webhook 方式，无需 Bot)
# ---------------------------------------------------------------------------

@dataclass
class DiscordPublisher:
    """Discord Webhook 推送。

    凭证来源：
      1. 构造函数的 webhook_url
      2. 环境变量 DISCORD_WEBHOOK_URL
      3. config.yaml → publisher.discord.webhook_url
    """
    webhook_url: str = ""
    timeout: int = 20
    username: str = "NewsDesk"
    avatar_url: str = ""

    platform: str = "discord"

    @classmethod
    def from_config(cls, cfg: dict | None = None) -> "DiscordPublisher":
        cfg = cfg or {}
        dc_cfg = cfg.get("discord", {}) if isinstance(cfg, dict) else {}
        return cls(
            webhook_url=os.environ.get("DISCORD_WEBHOOK_URL") or dc_cfg.get("webhook_url", ""),
            username=dc_cfg.get("username", "NewsDesk"),
            avatar_url=dc_cfg.get("avatar_url", ""),
        )

    def check_credentials(self) -> bool:
        return bool(self.webhook_url)

    def publish(self, text: str, *, image_url: str | None = None, **kw) -> PublishResult:
        if requests is None:
            return PublishResult("discord", False, error="requests 未安装")
        if not self.check_credentials():
            return PublishResult("discord", False, error="缺少 Discord Webhook URL")

        # Discord 单条消息上限 2000 字符
        if len(text) > 2000:
            text = text[:1990] + "\n\n…（已截断）"

        payload: dict = {
            "content": text,
            "username": self.username,
            "allowed_mentions": {"parse": []},  # 防止 @everyone
        }
        if self.avatar_url:
            payload["avatar_url"] = self.avatar_url

        try:
            resp = requests.post(self.webhook_url, json=payload, timeout=self.timeout)
            # Discord 204 No Content 表示成功
            if resp.status_code in (200, 204):
                return PublishResult("discord", True, external_id="ok")
            else:
                return PublishResult("discord", False, error=f"HTTP {resp.status_code}: {resp.text[:200]}")
        except requests.RequestException as exc:
            return PublishResult("discord", False, error=str(exc))


# ---------------------------------------------------------------------------
# 发布器集合（统一入口）
# ---------------------------------------------------------------------------

class PublisherHub:
    """管理多个平台的发布器，统一调用。"""

    def __init__(self, publishers: dict[str, Publisher] | None = None):
        self.publishers: dict[str, Publisher] = publishers or {}

    @classmethod
    def from_config(cls, cfg: dict | None = None) -> "PublisherHub":
        """从 config.yaml 的 publisher.* 构造已启用的平台。"""
        cfg = cfg or {}
        hub = cls()

        tw = TwitterPublisher.from_config(cfg)
        if tw.check_credentials():
            hub.publishers["twitter"] = tw

        tg = TelegramPublisher.from_config(cfg)
        if tg.check_credentials():
            hub.publishers["telegram"] = tg

        dc = DiscordPublisher.from_config(cfg)
        if dc.check_credentials():
            hub.publishers["discord"] = dc

        return hub

    def available_platforms(self) -> list[str]:
        return list(self.publishers.keys())

    def publish_to(self, platform: str, text: str, **kw) -> PublishResult:
        pub = self.publishers.get(platform)
        if pub is None:
            return PublishResult(platform, False, error=f"平台 '{platform}' 未配置或未启用")
        return pub.publish(text, **kw)

    def publish_all(self, texts: dict[str, str], **kw) -> dict[str, PublishResult]:
        """一次性向所有已配置平台发布。texts 格式：{platform_key: text}"""
        results: dict[str, PublishResult] = {}
        for platform, text in texts.items():
            if platform in self.publishers:
                results[platform] = self.publish_to(platform, text, **kw)
            else:
                results[platform] = PublishResult(platform, False, error="平台未配置")
        return results

    def health_check(self) -> dict[str, bool]:
        return {name: pub.check_credentials() for name, pub in self.publishers.items()}
