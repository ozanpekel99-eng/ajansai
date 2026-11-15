"""Video son-kare güvencesi: kapanışta yazı bozulursa son sağlam kare tutulur."""

import os
import subprocess
import tempfile

import pytest

from app.services import video_endguard

EXE = video_endguard._ffmpeg()
pytestmark = pytest.mark.skipif(not EXE, reason="ffmpeg yok")

W, H, FPS, SECONDS = 360, 640, 24, 6


def _poster(push: float = 0.0, broken: float = 0.0):
    """Siyah zeminde indigo ürün kutusu + beyaz "yazı" blokları.

    push: yavaş kamera yaklaşması (0-1); broken: kapanış bozulması (0-1) — yazı küçülüp aşağı kayar.
    """
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (W, H), (0, 0, 0))
    d = ImageDraw.Draw(img)
    z = 1 + 0.05 * push
    cx, cy = W / 2, H / 2
    d.rectangle([cx - 90 * z, cy - 60 * z, cx + 90 * z, cy + 120 * z], fill=(65, 63, 245))
    for row in range(3):  # yazı satırları
        y = 80 + row * 50 + broken * 260
        s = 1 - 0.6 * broken
        for col in range(8):
            x = 40 + col * 36 * s + broken * 60
            d.rectangle([x, y, x + 26 * s, y + 30 * s], fill=(255, 255, 255))
    return img


def _video(broken_from: float | None) -> bytes:
    n = FPS * SECONDS
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "v.mp4")
        p = subprocess.Popen([EXE, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                              "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264",
                              "-pix_fmt", "yuv420p", out], stdin=subprocess.PIPE)
        for i in range(n):
            t = i / FPS
            broken = 0.0
            if broken_from is not None and t >= broken_from:
                broken = min(1.0, (t - broken_from) / (SECONDS - broken_from))
            p.stdin.write(_poster(push=t / SECONDS, broken=broken).tobytes())
        p.stdin.close()
        assert p.wait() == 0
        with open(out, "rb") as f:
            return f.read()


def _last_frame(data: bytes) -> bytes:
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "v.mp4")
        with open(src, "wb") as f:
            f.write(data)
        return video_endguard._frames(EXE, src, 60)[-1]


def test_healthy_video_is_untouched():
    data = _video(None)
    out, report = video_endguard.guard(data)
    assert out is data and report["trimmed"] is False
    assert report["end_max"] <= report["threshold"]


def test_broken_ending_is_replaced_with_last_good_frame():
    data = _video(broken_from=5.6)
    out, report = video_endguard.guard(data)
    assert report["trimmed"] is True
    assert 5.0 <= report["cut_at"] <= 5.6
    # Süre korunur, son kare bozulma öncesindeki sağlam kareye yakındır.
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "o.mp4")
        with open(src, "wb") as f:
            f.write(out)
        assert abs(video_endguard._duration(EXE, src) - SECONDS) < 0.2
    good = _last_frame(_video(None))
    assert video_endguard._diff(_last_frame(out), good) < video_endguard._diff(_last_frame(data), good) / 3


def test_long_breakdown_is_left_alone():
    # Bozulma 2 sn'den başlıyorsa kapanışı dondurmak videonun yarısını siler: dokunulmaz.
    data = _video(broken_from=2.0)
    out, report = video_endguard.guard(data)
    assert out is data and report["trimmed"] is False


def test_invalid_bytes_return_original():
    out, report = video_endguard.guard(b"not a video")
    assert out == b"not a video" and report["trimmed"] is False


def test_store_video_runs_guard_before_upscale(monkeypatch):
    from app.routers import content

    calls = []
    monkeypatch.setattr(content.storage, "is_enabled", lambda: True)
    monkeypatch.setattr(content.gateway_media, "fetch_video", lambda v: b"raw")
    monkeypatch.setattr(content.video_endguard, "guard", lambda d: calls.append(("guard", d)) or (b"fixed", {}))
    monkeypatch.setattr(content.video_upscale, "upscale", lambda d, s: calls.append(("upscale", d)) or b"big")
    monkeypatch.setattr(content.storage, "save", lambda d, *a: calls.append(("save", d)) or "https://blob/v.mp4")
    assert content._store_video({"type": "url", "url": "x"}, "u1", {"upscale_to": "1080x1920"}) == "https://blob/v.mp4"
    assert calls == [("guard", b"raw"), ("upscale", b"fixed"), ("save", b"big")]


def test_steady_camera_move_is_not_flagged():
    # Baştan sona aynı hızda süren belirgin kamera hareketi bozulma değildir.
    frames = []
    for i in range(72):
        img = _poster(push=i / 72 * 8).convert("L").resize((video_endguard.SIDE, video_endguard.SIDE))
        frames.append(img.tobytes())
    cut, info = video_endguard.find_cut(frames)
    assert cut is None and info["normal"] > 0
