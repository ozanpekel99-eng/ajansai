"""Metin üreten yapay zeka çağrıları için tek giriş noktası.

Sıra:
1. OMNIROUTE_BASE_URL tanımlıysa istek OmniRoute'a (OpenAI uyumlu
   /chat/completions) gider. Model, yedek model ve maliyet takibi OmniRoute
   panelinden yönetilir; kod değişmeden model değiştirilebilir.
2. OmniRoute yoksa ya da hata verirse ve ANTHROPIC_API_KEY tanımlıysa istek
   doğrudan Claude'a gider. Böylece OmniRoute çökse bile uygulama çalışmaya
   devam eder.
"""

import logging

import requests

from app import config

logger = logging.getLogger("ajansai.llm")


class LLMError(Exception):
    pass


def _call_omniroute(system: str, user: str, max_tokens: int) -> str:
    headers = {"Content-Type": "application/json"}
    if config.OMNIROUTE_API_KEY:
        headers["Authorization"] = f"Bearer {config.OMNIROUTE_API_KEY}"

    response = requests.post(
        f"{config.OMNIROUTE_BASE_URL}/chat/completions",
        headers=headers,
        json={
            "model": config.OMNIROUTE_MODEL,
            "max_tokens": max_tokens,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        },
        timeout=config.OMNIROUTE_TIMEOUT,
    )
    if response.status_code != 200:
        raise LLMError(f"OmniRoute {response.status_code}: {response.text[:300]}")

    data = response.json()
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as e:
        raise LLMError(f"OmniRoute beklenmeyen yanıt: {str(data)[:300]}") from e

    # Bazı sağlayıcılar içeriği parça listesi olarak döndürür.
    if isinstance(content, list):
        content = "".join(p.get("text", "") for p in content if isinstance(p, dict))
    if not content:
        raise LLMError("OmniRoute boş yanıt döndürdü")
    return content


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


def complete(system: str, user: str, max_tokens: int = 2000) -> tuple[str, str]:
    """Metin üretir. (metin, kullanılan_sağlayıcı) döndürür."""
    errors = []

    if config.OMNIROUTE_BASE_URL:
        try:
            return _call_omniroute(system, user, max_tokens), "omniroute"
        except (requests.RequestException, LLMError, ValueError) as e:
            logger.warning("OmniRoute başarısız, doğrudan Claude'a geçiliyor: %s", e)
            errors.append(f"omniroute: {e}")

    if config.ANTHROPIC_API_KEY:
        try:
            return _call_anthropic(system, user, max_tokens), "anthropic"
        except Exception as e:  # SDK'nın tüm hata türleri
            logger.error("Claude çağrısı başarısız: %s", e)
            errors.append(f"anthropic: {e}")

    if not errors:
        raise LLMError("Ne OMNIROUTE_BASE_URL ne de ANTHROPIC_API_KEY tanımlı.")
    raise LLMError("; ".join(errors))
