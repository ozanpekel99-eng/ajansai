"""Görsel denetimine giden görselin çözünürlüğü ve Türkçe harf kuralı (29.10 yanlış "CILT" alarmı)."""

import base64
import io

from PIL import Image, ImageDraw

from app import config
from app.services import llm_service, media_qa


def _png(w: int, h: int, noisy: bool = False) -> bytes:
    if noisy:
        import os
        img = Image.frombytes("RGB", (w, h), os.urandom(w * h * 3))
    else:
        img = Image.new("RGB", (w, h), (10, 10, 10))
        ImageDraw.Draw(img).text((20, 20), "PÜRÜZSÜZ CİLT", fill=(255, 255, 255))
    out = io.BytesIO()
    img.save(out, "PNG")
    return out.getvalue()


def _decode(url: str) -> tuple[str, Image.Image]:
    head, b64 = url.split(",", 1)
    return head, Image.open(io.BytesIO(base64.b64decode(b64)))


def test_qa_image_keeps_high_resolution_png():
    head, img = _decode(media_qa._data_url(_png(1080, 1350)))
    # Önceden 1024 px JPEG'e küçültülüyordu; artık 1080x1350 olduğu gibi, kayıpsız gidiyor.
    assert head == "data:image/png;base64"
    assert img.size == (1080, 1350)


def test_qa_image_downscales_large_to_max_side():
    head, img = _decode(media_qa._data_url(_png(2160, 3840)))
    assert head == "data:image/png;base64"
    assert max(img.size) == media_qa.QA_MAX_SIDE >= 1536
    assert img.size == (882, 1568)  # 9:16 oranı korunuyor


def test_qa_image_falls_back_to_jpeg_when_png_too_big(monkeypatch):
    monkeypatch.setattr(media_qa, "QA_PNG_MAX_BYTES", 10_000)
    head, img = _decode(media_qa._data_url(_png(1200, 1500, noisy=True)))
    assert head == "data:image/jpeg;base64"
    assert img.size == (1200, 1500)


def test_check_image_sends_high_res_image_and_turkish_rule(monkeypatch):
    seen = {}

    def fake(model, messages, max_tokens=0):
        seen["system"] = messages[0]["content"]
        seen["last"] = messages[1]["content"][-1]["image_url"]["url"]
        return '{"ok": true, "problems": []}'

    monkeypatch.setattr(config, "IMAGE_QA", True)
    monkeypatch.setattr(llm_service, "chat_completion", fake)
    assert media_qa.check_image(_png(1080, 1920), "Pürüzsüz cilt kampanyası") == []
    head, img = _decode(seen["last"])
    assert head == "data:image/png;base64" and img.size == (882, 1568)
    assert "İ" in seen["system"] and "CİLT" in seen["system"] and "certain" in seen["system"]
