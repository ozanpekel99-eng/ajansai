"""Video açılış karesini videonun en-boy oranına uyarlar.

Veo, açılış karesi videonun oranında değilse kareyi ortalayıp üstte/altta siyah bant bırakır
(ör. 4:5 görselden 9:16 video → ~285 px bant). Bu yüzden oran farklıysa sahne o orana genişletilir.
Hem kullanıcı videosu (`/api/content/video`) hem kalite denetimi (`/api/health/qa-run`) bu fonksiyonu
kullanır; böylece denetim gerçek üretim akışını test eder.

Genişletme tüm afişi yeniden çizdirdiği için yazı/fiyat/ürün bozulabilir. Bu yüzden genişletilmiş kare
orijinal kareyle karşılaştırılarak denetlenir; kusurluysa bir kez yeniden denenir, yine kusurluysa
bozuk kare yerine orijinal kare kullanılır ve kullanıcıya not düşülür (video bozuk yazıyla başlamasın).
"""
import logging
from io import BytesIO

from dataclasses import dataclass, field

from app.services import gateway_media, media_qa, storage

logger = logging.getLogger("ajansai.video_frame")

TARGETS = {"9:16": 9 / 16, "16:9": 16 / 9}
TOLERANCE = 0.06  # %6'ya kadar fark bant oluşturmaz, genişletmeye gerek yok

EXTEND_PROMPT = (
    "Extend this exact photo to a {aspect} frame by naturally continuing the background and surface "
    "around it. Keep every product, food, person and object exactly as it is (same shape, colors, "
    "position relative to each other). No text, no borders, no new objects."
)

# Denetimde "istek" yerine geçen açıklama: kare yeni bir reklam değil, mevcut afişin genişletilmiş hâli.
QA_REQUEST = (
    "This is NOT a new ad. The generated image must be the reference image (the first image) extended to a "
    "{aspect} frame. Every text, price, badge, logo and product of the reference must appear exactly the same "
    "(same spelling, digits and position relative to each other); nothing may be added, removed or garbled. "
    "Only the newly added background area may differ.{extra}"
)

NOTE_FAILED = ("Açılış karesi videonun oranına uyarlanamadı; videoda üstte ve altta boşluk (siyah bant) "
               "görülebilir. Görseli {aspect} oranında yükleyerek tekrar deneyebilirsin.")
NOTE_DEFECT = ("Açılış karesi {aspect} oranına genişletilirken yazılar bozuldu, bu yüzden orijinal görsel "
               "kullanıldı; videoda üstte ve altta boşluk (siyah bant) görülebilir. Görseli {aspect} "
               "oranında yükleyerek tekrar deneyebilirsin.")


@dataclass
class FitResult:
    url: str  # videoya verilecek açılış karesi
    fitted: bool = False  # kare genişletildi mi
    note: str = ""  # kullanıcıya gösterilecek açıklama (boşsa sorun yok)
    problems: list[str] = field(default_factory=list)  # son denetimin kusurları (rapor için)
    attempts: int = 0  # genişletme denemesi sayısı


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


def fit_frame_checked(url: str, aspect: str, folder: str, request: str = "") -> FitResult:
    """Kareyi videonun oranına genişletir ve sonucu denetler.

    Kusurlu genişletme bir kez, kusurlar belirtilerek yeniden denenir. İkinci deneme de kusurluysa ya da
    genişletme hiç yapılamazsa orijinal kare döner ve `note` doldurulur.
    """
    if not needs_fit(image_aspect(url), aspect):
        return FitResult(url)
    extra = f" Client's video request (Turkish, for context only): {request[:300]}" if request else ""
    qa_request = QA_REQUEST.format(aspect=aspect, extra=extra)
    prompt = EXTEND_PROMPT.format(aspect=aspect)
    problems: list[str] = []
    attempts = 0
    for attempt in range(2):
        if problems:
            prompt += "\n\nThe previous attempt had these defects; avoid them this time: " + "; ".join(problems)
        try:
            attempts += 1
            data, mime = gateway_media.generate_image(prompt, aspect, [url])
        except gateway_media.MediaError as e:
            logger.warning("Açılış karesi orana uyarlanamadı (deneme %d): %s", attempt + 1, e)
            break
        problems = media_qa.check_image(data, qa_request, [url])
        if problems:
            logger.info("Genişletilmiş açılış karesi kusurlu (deneme %d): %s", attempt + 1, problems)
            continue
        try:
            return FitResult(storage.save(data, mime, folder), fitted=True, attempts=attempts)
        except storage.StorageError as e:
            logger.warning("Genişletilmiş açılış karesi kaydedilemedi: %s", e)
            problems = []
            break
    note = (NOTE_DEFECT if problems else NOTE_FAILED).format(aspect=aspect)
    return FitResult(url, note=note, problems=problems, attempts=attempts)


def fit_frame(url: str, aspect: str, folder: str, request: str = "") -> str:
    """Yalnızca adres gerektiğinde: genişletilmiş (ve denetlenmiş) karenin adresi ya da orijinal adres."""
    return fit_frame_checked(url, aspect, folder, request).url
