"""Videoyu hedef çözünürlüğe büyütür (ffmpeg, imageio-ffmpeg ile gelen ikili).

Veo, AI Gateway'in boyut sınırı yüzünden daha küçük üretilir; kullanıcının seçtiği
çözünürlük burada sağlanır. ffmpeg yoksa ya da hata verirse video olduğu gibi döner.
"""

import logging
import os
import subprocess
import tempfile

logger = logging.getLogger("ajansai.upscale")


def _ffmpeg() -> str | None:
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as e:  # noqa: BLE001
        logger.warning("ffmpeg bulunamadı: %s", e)
        return None


def upscale(data: bytes, size: str, timeout: float = 240) -> bytes:
    """size örn. "1920x1080". Başarısız olursa orijinal baytlar döner."""
    exe = _ffmpeg()
    if not exe or not data:
        return data
    w, h = size.split("x")
    with tempfile.TemporaryDirectory() as tmp:
        src, dst = os.path.join(tmp, "in.mp4"), os.path.join(tmp, "out.mp4")
        with open(src, "wb") as f:
            f.write(data)
        cmd = [exe, "-y", "-loglevel", "error", "-i", src,
               "-vf", f"scale={w}:{h}:flags=lanczos,unsharp=5:5:0.35:5:5:0",
               "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p",
               "-c:a", "copy", "-movflags", "+faststart", dst]
        try:
            subprocess.run(cmd, check=True, timeout=timeout, capture_output=True)
            with open(dst, "rb") as f:
                out = f.read()
            return out or data
        except (subprocess.SubprocessError, OSError) as e:
            logger.error("Video büyütülemedi (%s): %s", size, e)
            return data
