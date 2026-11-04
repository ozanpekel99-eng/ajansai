"""Üretilen görselin otomatik kalite kontrolü (kullanıcıya göstermeden önce).

Güçlü bir görme modeli (Sonnet) görseli isteğe ve yüklenen ürün fotoğraflarına göre denetler:
eksik/yanlış yazı veya fiyat, kenarda kesilen yazı, uydurma bilgi, bozulan ürün, yanlış boyut oranı,
anatomi hataları. Somut bir kusur bulunursa görsel bir kez, kusurlar düzeltilerek yeniden üretilir.
"""

import base64
import io
import json
import logging
import os
import re
import subprocess
import tempfile

from app import config
from app.services import gateway_media, llm_service, video_upscale

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
                     product_urls: list[str] | None = None, quality: str = "standard") -> tuple[bytes, str]:
    """Görseli üretir, denetler; kusur varsa kusurları düzelterek bir kez yeniden üretir."""
    data, mime = gateway_media.generate_image(prompt, aspect, refs or None, quality)
    problems = check_image(data, request, product_urls)
    if not problems:
        return data, mime
    logger.info("Görsel kusurlu, yeniden üretiliyor: %s", problems)
    fix = prompt + "\n\nThe previous attempt had these defects; avoid them this time: " + "; ".join(problems)
    try:
        data2, mime2 = gateway_media.generate_image(fix, aspect, refs or None, quality)
    except gateway_media.MediaError:
        return data, mime
    return data2, mime2


# --- Video denetimi -------------------------------------------------------------------------------
# 1. adım: siyah bant (letterbox) tespiti. `ffmpeg cropdetect` konfeti/kurdele gibi koyu-açık
# karışık kenarlarda yanılıyor; bunun yerine ilk karenin üst ve alt şeritlerinin ortalama
# parlaklığına bakılır (1080x1920'de 200 px). Orta bölge de koyuysa (gece sahnesi) kusur sayılmaz.

LETTERBOX_STRIP = 200 / 1920   # şerit yüksekliği / kare yüksekliği
LETTERBOX_DARK = 10            # 0–255 gri tonda "siyah" eşiği
LETTERBOX_CONTENT_MIN = 25     # orta bölge bundan parlaksa şeritler gerçekten bant demektir


def video_frame(video: bytes, at: float = 0.0, timeout: float = 30) -> bytes | None:
    """Videodan `at` saniyedeki kareyi PNG olarak döndürür; ffmpeg yoksa/başarısızsa None."""
    exe = video_upscale._ffmpeg()
    if not exe or not video:
        return None
    with tempfile.TemporaryDirectory() as tmp:
        src, dst = os.path.join(tmp, "in.mp4"), os.path.join(tmp, "frame.png")
        with open(src, "wb") as f:
            f.write(video)
        cmd = [exe, "-y", "-loglevel", "error", "-ss", f"{at:.2f}", "-i", src,
               "-frames:v", "1", dst]
        try:
            subprocess.run(cmd, check=True, timeout=timeout, capture_output=True)
            with open(dst, "rb") as f:
                return f.read() or None
        except (subprocess.SubprocessError, OSError) as e:
            logger.warning("Video karesi çıkarılamadı: %s", e)
            return None


def letterbox_problem(frame_png: bytes) -> str | None:
    """Karenin üstünde ve altında siyah bant varsa kusur metni, yoksa None."""
    from PIL import Image, ImageStat

    img = Image.open(io.BytesIO(frame_png)).convert("L")
    w, h = img.size
    strip = max(1, round(h * LETTERBOX_STRIP))
    if h < strip * 3:
        return None
    top = ImageStat.Stat(img.crop((0, 0, w, strip))).mean[0]
    bottom = ImageStat.Stat(img.crop((0, h - strip, w, h))).mean[0]
    middle = ImageStat.Stat(img.crop((0, strip, w, h - strip))).mean[0]
    if top < LETTERBOX_DARK and bottom < LETTERBOX_DARK and middle >= LETTERBOX_CONTENT_MIN:
        return (f"letterbox: black bars at top and bottom of the first frame "
                f"(top {top:.0f}, bottom {bottom:.0f}, content {middle:.0f} brightness)")
    return None


def check_video(video: bytes) -> list[str]:
    """Videonun kusur listesi (boş = sorun yok). Denetim çalışmazsa boş liste (üretimi engellemez).

    Şimdilik yalnızca siyah bant; görme modeliyle yazı/ürün denetimi sonraki adımda eklenecek.
    """
    try:
        frame = video_frame(video, 0.0)
        if not frame:
            return []
        problem = letterbox_problem(frame)
        return [problem] if problem else []
    except Exception as e:  # noqa: BLE001
        logger.warning("Video denetimi çalışmadı: %s", e)
        return []
