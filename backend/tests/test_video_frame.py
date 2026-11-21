"""Video açılış karesinin orana genişletilmesi ve genişletilen karenin denetimi."""

from app.services import gateway_media, media_qa, storage, video_frame

from .conftest import auth
from .test_api import BLOB_URL, _enable_media, register_paid

SRC = "https://x.public.blob.vercel-storage.com/gorsel/afis.png"


def _setup(monkeypatch, verdicts, ratio=4 / 5):
    """Her genişletme için sırayla bir denetim sonucu döner; çağrılar kaydedilir."""
    calls = {"gen": [], "qa": [], "saved": 0}
    monkeypatch.setattr(video_frame, "image_aspect", lambda url: ratio)
    monkeypatch.setattr(video_frame.gateway_media, "generate_image",
                        lambda prompt, aspect, refs=None, **k: calls["gen"].append((prompt, aspect, refs))
                        or (b"png%d" % len(calls["gen"]), "image/png"))
    it = iter(verdicts)
    monkeypatch.setattr(video_frame.media_qa, "check_image",
                        lambda data, request, product_urls=None: calls["qa"].append((data, request, product_urls))
                        or next(it))

    def save(data, mime, folder, filename=None):
        calls["saved"] += 1
        return f"https://x.public.blob.vercel-storage.com/{folder}/{data.decode()}.png"

    monkeypatch.setattr(video_frame.storage, "save", save)
    return calls


def test_clean_extension_is_used(monkeypatch):
    calls = _setup(monkeypatch, [[]])
    r = video_frame.fit_frame_checked(SRC, "9:16", "gorsel/1", "kahve videosu")
    assert r.fitted and r.url.endswith("gorsel/1/png1.png") and r.note == "" and r.attempts == 1
    # Denetim orijinal kareyle karşılaştırarak yapılır; istek metni bağlam olarak eklenir
    data, request, refs = calls["qa"][0]
    assert data == b"png1" and refs == [SRC]
    assert "extended to a 9:16" in request and "kahve videosu" in request


def test_defective_extension_is_retried_with_problems(monkeypatch):
    calls = _setup(monkeypatch, [["Price '1.299 TL' garbled"], []])
    r = video_frame.fit_frame_checked(SRC, "9:16", "qa")
    assert r.fitted and r.url.endswith("qa/png2.png") and r.attempts == 2 and r.note == ""
    assert len(calls["gen"]) == 2 and calls["saved"] == 1  # kusurlu kare kaydedilmez
    assert "Price '1.299 TL' garbled" in calls["gen"][1][0]
    assert "Price" not in calls["gen"][0][0]


def test_twice_defective_falls_back_to_original_with_note(monkeypatch):
    calls = _setup(monkeypatch, [["Text garbled"], ["Logo missing"]])
    r = video_frame.fit_frame_checked(SRC, "9:16", "qa")
    assert r.url == SRC and not r.fitted and r.attempts == 2 and calls["saved"] == 0
    assert r.problems == ["Logo missing"]
    assert "yazılar bozuldu" in r.note and "siyah bant" in r.note and "9:16" in r.note


def test_generation_error_falls_back_with_note(monkeypatch):
    monkeypatch.setattr(video_frame, "image_aspect", lambda url: 1.0)

    def boom(*a, **k):
        raise gateway_media.MediaError("kapalı")

    monkeypatch.setattr(video_frame.gateway_media, "generate_image", boom)
    monkeypatch.setattr(video_frame.media_qa, "check_image",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("üretilmeyen kare denetlenmez")))
    r = video_frame.fit_frame_checked(SRC, "9:16", "qa")
    assert r.url == SRC and r.attempts == 1 and r.problems == []
    assert "uyarlanamadı" in r.note
    assert video_frame.fit_frame(SRC, "9:16", "qa") == SRC


def test_storage_error_falls_back_with_note(monkeypatch):
    _setup(monkeypatch, [[]])

    def fail(*a, **k):
        raise storage.StorageError("blob kapalı")

    monkeypatch.setattr(video_frame.storage, "save", fail)
    r = video_frame.fit_frame_checked(SRC, "9:16", "qa")
    assert r.url == SRC and "uyarlanamadı" in r.note


def test_frame_in_ratio_needs_no_extension_or_check(monkeypatch):
    calls = _setup(monkeypatch, [], ratio=9 / 16)
    r = video_frame.fit_frame_checked(SRC, "9:16", "qa")
    assert r.url == SRC and r.note == "" and r.attempts == 0
    assert calls["gen"] == [] and calls["qa"] == []


def test_video_endpoint_returns_frame_note(client, monkeypatch):
    """Genişletme iki kez kusurluysa video orijinal kareyle başlar ve kullanıcı açıklamayı görür."""
    _enable_media(monkeypatch)
    started = {}
    monkeypatch.setattr(gateway_media, "start_video",
                        lambda prompt, d, r, image_url, *a, **k: started.update(image=image_url) or {"model": "m", "operation": {}})
    monkeypatch.setattr(video_frame, "image_aspect", lambda url: 4 / 5)
    monkeypatch.setattr(gateway_media, "generate_image", lambda *a, **k: (b"png", "image/png"))
    monkeypatch.setattr(media_qa, "check_image", lambda *a, **k: ["Headline garbled"])
    token = register_paid(client, plan="pro")
    src = BLOB_URL + "afis.png"
    r = client.post("/api/content/video", json={"concept": "afiş hareketlensin", "image_url": src}, headers=auth(token))
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["job_id"] and started["image"] == src and data["start_frame"] == src
    assert "yazılar bozuldu" in data["note"]
