"""Üretilen görselin otomatik kalite kontrolü (kullanıcıya göstermeden önce).

Güçlü bir görme modeli (Sonnet) görseli isteğe ve yüklenen ürün fotoğraflarına göre denetler:
eksik/yanlış yazı veya fiyat, kenarda kesilen yazı, uydurma bilgi, bozulan ürün, yanlış boyut oranı,
anatomi hataları. Somut bir kusur bulunursa görsel bir kez, kusurlar düzeltilerek yeniden üretilir.
"""

import base64
import io
import json
import logging
import re

from app import config
from app.services import gateway_media, llm_service

logger = logging.getLogger("ajansai.qa")

QA_SYSTEM = """You are a strict quality inspector for AI-generated advertising images, before they are shown to a
paying small-business customer. Compare the generated image (the LAST image) with the client's request and,
if given, the client's product photos (the images before it). Report ONLY clear, objective defects:
1. A text, price, date, product code or store name the client asked for is missing, misspelled, has wrong
   digits/currency, or is different from the request. Check every number character by character.
2. Any text cut off or touching the image edge.
3. Invented facts the client did not give: other prices or discounts, phone numbers, addresses, websites,
   guarantees, free delivery/installation, gifts, brand names/logos not in the request. (A short creative
   headline and generic labels such as "NAKİT", "TAKSİTLİ", "SATIŞ FİYATI", "SON GÜN", "+" are allowed.)
4. Products deformed, duplicated, missing, the wrong count, or clearly different from the product photos
   (shape, color, door/handle layout, display, logo), or wrong real-world relative size.
5. Physical/anatomy errors: extra or missing fingers, a utensil with two handles, melted or impossible objects.
6. Gibberish or garbled letters anywhere.
Ignore style and taste. Output JSON only: {"ok": true|false, "problems": ["short English description", ...]}"""


def _data_url(data: bytes, max_side: int = 1024) -> str:
    from PIL import Image

    img = Image.open(io.BytesIO(data)).convert("RGB")
    img.thumbnail((max_side, max_side))
    out = io.BytesIO()
    img.save(out, "JPEG", quality=88)
    return "data:image/jpeg;base64," + base64.b64encode(out.getvalue()).decode()


def check_image(data: bytes, request: str, product_urls: list[str] | None = None) -> list[str]:
    """Kusur listesi döndürür (boş liste = sorun yok). Denetim çalışmazsa boş liste (üretimi engellemez)."""
    if not config.IMAGE_QA:
        return []
    try:
        content = [{"type": "text", "text": f"Client request (Turkish): {request}\n"
                    f"{len(product_urls or [])} product photo(s) attached before the generated image."}]
        content += [{"type": "image_url", "image_url": {"url": u}} for u in (product_urls or [])[:4]]
        content.append({"type": "image_url", "image_url": {"url": _data_url(data)}})
        raw = llm_service.chat_completion(
            config.IMAGE_QA_MODEL,
            [{"role": "system", "content": QA_SYSTEM}, {"role": "user", "content": content}],
            max_tokens=3000,
        )
        m = re.search(r"\{.*\}", raw, re.S)
        verdict = json.loads(m.group(0)) if m else {}
        if verdict.get("ok", True):
            return []
        return [str(p) for p in verdict.get("problems") or []][:6]
    except Exception as e:  # noqa: BLE001
        logger.warning("Görsel denetimi çalışmadı: %s", e)
        return []


def generate_checked(prompt: str, aspect: str, refs: list[str] | None, request: str,
                     product_urls: list[str] | None = None) -> tuple[bytes, str]:
    """Görseli üretir, denetler; kusur varsa kusurları düzelterek bir kez yeniden üretir."""
    data, mime = gateway_media.generate_image(prompt, aspect, refs or None)
    problems = check_image(data, request, product_urls)
    if not problems:
        return data, mime
    logger.info("Görsel kusurlu, yeniden üretiliyor: %s", problems)
    fix = prompt + "\n\nThe previous attempt had these defects; avoid them this time: " + "; ".join(problems)
    try:
        data2, mime2 = gateway_media.generate_image(fix, aspect, refs or None)
    except gateway_media.MediaError:
        return data, mime
    return data2, mime2
