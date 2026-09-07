from __future__ import annotations

import os
import time
from typing import Optional

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover
    OpenAI = None  # type: ignore

from .models import LLMClient


def _cfg_llm() -> dict:
    """从 config.yaml 读取 llm section（环境变量覆盖链在各 resolve 里处理）。"""
    try:
        from .config import get_raw
        return get_raw().get("llm", {}) or {}
    except Exception:
        return {}


def _cfg_fallback_providers() -> list[dict]:
    """从 config.yaml 读取 llm_fallback section（多模型 fallback 链）。"""
    try:
        from .config import get_raw
        return get_raw().get("llm_fallback", []) or []
    except Exception:
        return []


def _resolve_api_key() -> str:
    env_key = os.environ.get("NEWSDESK_LLM_API_KEY", "").strip()
    if env_key:
        return env_key
    return _cfg_llm().get("api_key", "").strip()


def _resolve_base_url() -> Optional[str]:
    url = os.environ.get("NEWSDESK_LLM_BASE_URL", "").strip()
    if url:
        return url
    url = _cfg_llm().get("base_url", "").strip()
    return url or None


def _resolve_model() -> Optional[str]:
    m = os.environ.get("NEWSDESK_LLM_MODEL", "").strip()
    if m:
        return m or None
    m = _cfg_llm().get("model", "").strip()
    return m or None


def build_llm_client() -> Optional[LLMClient]:
    """构建 LLM 客户端，支持主模型 + fallback 链。"""
    api_key = _resolve_api_key()
    if not api_key:
        return None
    if OpenAI is None:
        print("警告：openai 包未安装，安装后使用 `pip install newsdesk[llm]`")
        return None

    primary_kwargs: dict[str, str] = {"api_key": api_key}
    base_url = _resolve_base_url()
    model = _resolve_model()
    if base_url:
        primary_kwargs["base_url"] = base_url

    primary = OpenAIClient(model=model, **primary_kwargs)

    # Fallback 链
    fallback_clients: list[LLMClient] = []
    for provider in _cfg_fallback_providers():
        fb_api_key = provider.get("api_key", "").strip()
        fb_base_url = provider.get("base_url", "").strip() or None
        fb_model = provider.get("model", "").strip() or None
        if not fb_api_key:
            continue
        fb_kwargs: dict[str, str] = {"api_key": fb_api_key}
        if fb_base_url:
            fb_kwargs["base_url"] = fb_base_url
        fb_client = OpenAIClient(model=fb_model, **fb_kwargs)
        fallback_clients.append(fb_client)
        print(f"  LLM fallback: {fb_model or 'default'} @ {fb_base_url or 'default'} 已注册")

    if fallback_clients:
        return FallbackLLMClient(primary=primary, fallbacks=fallback_clients)
    return primary


class OpenAIClient(LLMClient):
    def __init__(self, *, api_key: str, base_url: Optional[str] = None, model: Optional[str] = None):
        client_kwargs: dict[str, str] = {"api_key": api_key}
        if base_url:
            client_kwargs["base_url"] = base_url
        self._client = OpenAI(**client_kwargs)
        self._default_model = model

    def generate(self, prompt: str, model: Optional[str] = None) -> str:
        effective_model = model or self._default_model or "default"
        response = self._client.chat.completions.create(
            model=effective_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=600,
        )
        return response.choices[0].message.content or ""


class FallbackLLMClient(LLMClient):
    """主模型失败时自动降级到备用模型链。"""

    def __init__(self, primary: OpenAIClient, fallbacks: list[LLMClient]):
        self._primary = primary
        self._fallbacks = fallbacks
        self._default_model = primary._default_model

    def generate(self, prompt: str, model: Optional[str] = None) -> str:
        # 先试主模型
        try:
            result = self._primary.generate(prompt, model=model)
            if result.strip():
                return result
        except Exception as exc:
            print(f"  LLM 主模型失败：{exc}，尝试 fallback...")

        # 逐个试 fallback
        for fb in self._fallbacks:
            try:
                result = fb.generate(prompt, model=model)
                if result.strip():
                    print(f"  ✓ Fallback 成功")
                    return result
            except Exception as exc:
                print(f"  Fallback 也失败：{exc}")
                time.sleep(0.5)
                continue

        # 全部失败
        raise RuntimeError("所有 LLM 模型（主 + fallback）均不可用")
