import logging

import requests

from app import config

# MVP'de Ideogram API kullanıyoruz. Alternatif: OpenAI Images, Flux (bfl.ai).
# Sağlayıcıyı değiştirmek isterseniz sadece bu dosyayı güncellemeniz yeterli.
IDEOGRAM_ENDPOINT = "https://api.ideogram.ai/generate"

logger = logging.getLogger("ajansai.image")


def generate_image(prompt: str, aspect_ratio: str = "ASPECT_1_1") -> dict:
    """Konsept metninden görsel üretir. {"image_url", "error"} döndürür.

    Hata durumunda image_url None olur; çağıran taraf kotayı iade eder.
    """
    if not config.IDEOGRAM_API_KEY:
        return {"error": "Görsel üretimi henüz yapılandırılmadı (IDEOGRAM_API_KEY).", "image_url": None}

    payload = {
        "image_request": {
            "prompt": prompt,
            "aspect_ratio": aspect_ratio,
            "model": "V_2",
            "magic_prompt_option": "AUTO",
        }
    }
    headers = {"Api-Key": config.IDEOGRAM_API_KEY, "Content-Type": "application/json"}

    try:
        response = requests.post(IDEOGRAM_ENDPOINT, json=payload, headers=headers, timeout=90)
        response.raise_for_status()
        data = response.json()
        image_url = (data.get("data") or [{}])[0].get("url")
    except (requests.RequestException, ValueError) as e:
        logger.error("Ideogram hatası: %s", e)
        return {"error": "Görsel üretilemedi, lütfen tekrar dene.", "image_url": None}

    if not image_url:
        return {"error": "Görsel üretilemedi, lütfen tekrar dene.", "image_url": None}
    return {"image_url": image_url, "error": None}
