"""Metin üreten yapay zeka çağrıları için tek giriş noktası.

Sırayla denenir, biri başarısız olursa sonrakine geçilir:
1. OmniRoute (OMNIROUTE_BASE_URL tanımlıysa): model, yedek sağlayıcı ve
   maliyet takibi OmniRoute panelinden yönetilir.
2. Vercel AI Gateway (Vercel'de çalışırken varsayılan olarak açık): API key
   gerektirmez, Vercel projesinin kimliğiyle (OIDC) doğrulanır.
3. Doğrudan Claude (ANTHROPIC_API_KEY tanımlıysa).

OmniRoute ve AI Gateway aynı OpenAI uyumlu /chat/completions biçimini kullanır.
"""

import contextvars
import logging
import os

import requests

from app import config

logger = logging.getLogger("ajansai.llm")

# Vercel, OIDC token'ını her isteğe `x-vercel-oidc-token` başlığı olarak ekler.
# main.py'deki ara katman bunu buraya yazar.
current_oidc_token: contextvars.ContextVar[str | None] = contextvars.ContextVar("oidc_token", default=None)


class LLMError(Exception):
    pass


def _call_openai_compatible(base_url: str, api_key: str | None, model: str, system: str, user: str,
                            max_tokens: int, timeout: float, label: str) -> str:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    response = requests.post(
        f"{base_url}/chat/completions",
        headers=headers,
        json={
            "model": model,
            "max_tokens": max_tokens,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        },
        timeout=timeout,
    )
    if response.status_code != 200:
        raise LLMError(f"{label} {response.status_code}: {response.text[:300]}")

    data = response.json()
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as e:
        raise LLMError(f"{label} beklenmeyen yanıt: {str(data)[:300]}") from e

    # Bazı sağlayıcılar içeriği parça listesi olarak döndürür.
    if isinstance(content, list):
        content = "".join(p.get("text", "") for p in content if isinstance(p, dict))
    if not content:
        raise LLMError(f"{label} boş yanıt döndürdü")
    return content


def _call_omniroute(system: str, user: str, max_tokens: int) -> str:
    return _call_openai_compatible(
        config.OMNIROUTE_BASE_URL, config.OMNIROUTE_API_KEY, config.OMNIROUTE_MODEL,
        system, user, max_tokens, config.OMNIROUTE_TIMEOUT, "OmniRoute",
    )


def _ai_gateway_token() -> str | None:
    return config.AI_GATEWAY_API_KEY or current_oidc_token.get() or os.environ.get("VERCEL_OIDC_TOKEN")


def _call_ai_gateway(system: str, user: str, max_tokens: int) -> str:
    token = _ai_gateway_token()
    if not token:
        raise LLMError("AI Gateway için kimlik bilgisi yok (OIDC token veya AI_GATEWAY_API_KEY)")
    return _call_openai_compatible(
        config.AI_GATEWAY_BASE_URL, token, config.AI_GATEWAY_MODEL,
        system, user, max_tokens, 90, "AI Gateway",
    )


_anthropic_client = None


def _call_anthropic(system: str, user: str, max_tokens: int) -> str:
    global _anthropic_client
    if _anthropic_client is None:
        import anthropic

        _anthropic_client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    response = _anthropic_client.messages.create(
        model=config.ANTHROPIC_MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    text = "".join(block.text for block in response.content if getattr(block, "type", "") == "text")
    if not text:
        raise LLMError("Claude boş yanıt döndürdü")
    return text


def available_providers() -> list[str]:
    providers = []
    if config.OMNIROUTE_BASE_URL:
        providers.append("omniroute")
    if config.AI_GATEWAY_ENABLED:
        providers.append("ai_gateway")
    if config.ANTHROPIC_API_KEY:
        providers.append("anthropic")
    return providers


def complete(system: str, user: str, max_tokens: int = 2000) -> tuple[str, str]:
    """Metin üretir. (metin, kullanılan_sağlayıcı) döndürür."""
    calls = {
        "omniroute": _call_omniroute,
        "ai_gateway": _call_ai_gateway,
        "anthropic": _call_anthropic,
    }
    providers = available_providers()
    if not providers:
        raise LLMError("Hiçbir yapay zeka sağlayıcısı yapılandırılmadı.")

    errors = []
    for name in providers:
        try:
            return calls[name](system, user, max_tokens), name
        except Exception as e:  # ağ, HTTP ve SDK hatalarının hepsi: sıradakine geç
            logger.warning("%s başarısız, sıradaki sağlayıcı deneniyor: %s", name, e)
            errors.append(f"{name}: {e}")
    raise LLMError("; ".join(errors))
