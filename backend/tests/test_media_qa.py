import io
import subprocess

import pytest
from PIL import Image, ImageDraw

from app.services import media_qa, video_upscale


def _png(w, h, bars=0, content=(200, 120, 40), bar=(0, 0, 0)):
    img = Image.new("RGB", (w, h), content)
    if bars:
        d = ImageDraw.Draw(img)
        d.rectangle((0, 0, w, bars - 1), fill=bar)
        d.rectangle((0, h - bars, w, h), fill=bar)
    out = io.BytesIO()
    img.save(out, "PNG")
    return out.getvalue()


def test_letterbox_detected_for_4x5_content_in_9x16():
    # 02.11 QA videosu: 1080x1920 içinde ortada 1080x1350 içerik, üst/alt ~285 px siyah
    assert media_qa.letterbox_problem(_png(1080, 1920, bars=285)).startswith("letterbox")


def test_full_frame_and_partial_dark_edges_pass():
    assert media_qa.letterbox_problem(_png(1080, 1920)) is None
    # yalnızca üstte koyu şerit (ör. gece gökyüzü) bant sayılmaz
    img = Image.open(io.BytesIO(_png(1080, 1920))).convert("RGB")
    ImageDraw.Draw(img).rectangle((0, 0, 1080, 250), fill=(0, 0, 0))
    out = io.BytesIO(); img.save(out, "PNG")
    assert media_qa.letterbox_problem(out.getvalue()) is None


def test_confetti_on_bars_does_not_hide_letterbox_but_dark_scene_passes():
    # bandın içine sarkan birkaç parlak kurdele ortalamayı eşiğin altında bırakır
    img = Image.open(io.BytesIO(_png(1080, 1920, bars=285))).convert("RGB")
    d = ImageDraw.Draw(img)
    for x in range(0, 1080, 270):
        d.rectangle((x, 150, x + 12, 284), fill=(230, 190, 60))
    out = io.BytesIO(); img.save(out, "PNG")
    assert media_qa.letterbox_problem(out.getvalue()) is not None
    # tamamen karanlık sahne: orta bölge de koyu → kusur değil
    assert media_qa.letterbox_problem(_png(1080, 1920, bars=285, content=(8, 8, 8))) is None


def _mp4(tmp_path, pad: bool) -> bytes:
    exe = video_upscale._ffmpeg()
    if not exe:
        pytest.skip("ffmpeg yok")
    vf = "pad=270:480:0:67:black" if pad else "scale=270:480"
    size = "270x346" if pad else "270x480"
    dst = tmp_path / "v.mp4"
    subprocess.run([exe, "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                    f"color=c=orange:s={size}:d=1", "-vf", vf, "-pix_fmt", "yuv420p", str(dst)],
                   check=True, timeout=60)
    return dst.read_bytes()


def test_check_video_end_to_end(tmp_path):
    assert media_qa.check_video(_mp4(tmp_path, pad=True))[0].startswith("letterbox")
    assert media_qa.check_video(_mp4(tmp_path, pad=False)) == []


def test_check_video_never_raises():
    assert media_qa.check_video(b"not a video") == []
    assert media_qa.check_video(b"") == []
