"""Video açılış karesini videonun en-boy oranına uyarlar.

Veo, açılış karesi videonun oranında değilse kareyi ortalayıp üstte/altta siyah bant bırakır
(ör. 4:5 görselden 9:16 video → ~285 px bant). Bu yüzden oran farklıysa sahne o orana genişletilir.
Hem kullanıcı videosu (`/api/content/video`) hem kalite denetimi (`/api/health/qa-run`) bu fonksiyonu
kullanır; böylece denetim gerçek üretim akışını test eder.
"""
import logging
from io import BytesIO

from app.services import gateway_media, storage

logger = logging.getLogger("ajansai.video_frame")

TARGETS = {"9:16": 9 / 16, "16:9": 16 / 9}
TOLERANCE = 0.06  # %6'ya kadar fark bant oluşturmaz, genişletmeye gerek yok

EXTEND_PROMPT = (
    "Extend this exact photo to a {aspect} frame by naturally continuing the background and surface "
    "around it. Keep every product, food, person and object exactly as it is (same shape, colors, "
    "position relative to each other). No text, no borders, no new objects."
)


def image_aspect(url: str) -> float | None:
    """Görselin genişlik/yükseklik oranı; okunamazsa None."""
    try:
        from PIL import Image

        w, h = Image.open(BytesIO(storage.fetch(url))).size
        return w / h if h else None
    except Exception:  # noqa: BLE001
        return None


def needs_fit(ratio: float | None, aspect: str) -> bool:
    target = TARGETS.get(aspect, 9 / 16)
    return bool(ratio) and abs(ratio - target) / target >= TOLERANCE


def fit_frame(url: str, aspect: str, folder: str) -> str:
    """Kare videonun oranında değilse genişletilmiş karenin adresini, değilse aynı adresi döndürür."""
    if not needs_fit(image_aspect(url), aspect):
        return url
    try:
        data, mime = gateway_media.generate_image(EXTEND_PROMPT.format(aspect=aspect), aspect, [url])
        return storage.save(data, mime, folder)
    except (gateway_media.MediaError, storage.StorageError) as e:
        logger.warning("Açılış karesi orana uyarlanamadı: %s", e)
        return url
