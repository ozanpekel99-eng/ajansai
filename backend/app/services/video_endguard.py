"""Video son-kare güvencesi: kapanışta bozulan kareleri son sağlam kareyle değiştirir.

Veo bazen videonun son ~0,5 sn'sinde afişteki yazıları küçültüp kaydırıyor ya da okunamaz harf
yığınına çeviriyor (09.11 kalite denetimi). Bu modül ek üretim maliyeti olmadan bunu yakalar:

1. ffmpeg ile videodan saniyede 12 küçük gri kare çıkarılır.
2. Videonun gövdesindeki "olağan değişim" (0,6 sn arayla iki kare arasındaki ortalama piksel farkı)
   ölçülür; yavaş kamera yaklaşması, ışık oynaması gibi hareketler burada zaten vardır.
3. Son 0,6 sn'deki kareler, o pencerenin hemen önündeki sağlam kareyle karşılaştırılır. Fark olağan
   değişimin belirgin biçimde üstündeyse kapanışta bozulma var sayılır.
4. Video bozulmanın başladığı yerde kesilir ve son sağlam kare tutularak (``tpad=stop_mode=clone``)
   özgün süreye tamamlanır. Ses varsa olduğu gibi kopyalanır.

ffmpeg yoksa, video okunamazsa ya da şüpheli bir durum varsa video olduğu gibi döner (asla bozmaz).
"""

import logging
import os
import re
import subprocess
import tempfile

from app.services.video_upscale import _ffmpeg

logger = logging.getLogger("ajansai.endguard")

FPS = 12  # analiz karesi sıklığı
SIDE = 64  # analiz karesi boyutu (SIDE x SIDE gri)
WINDOW_S = 0.6  # kapanışta denetlenen süre
MIN_DIFF = 6.0  # 0-255 ölçeğinde: bundan küçük fark hiçbir zaman bozulma sayılmaz
RATIO = 2.5  # kapanış farkı olağan değişimin kaç katını aşarsa bozulma sayılır
MAX_CUT_S = 1.0  # en fazla bu kadar kapanış süresi dondurulur; daha fazlası şüpheli, dokunulmaz


def _frames(exe: str, src: str, timeout: float) -> list[bytes]:
    cmd = [exe, "-loglevel", "error", "-i", src, "-an",
           "-vf", f"fps={FPS},scale={SIDE}:{SIDE},format=gray", "-f", "rawvideo", "-"]
    out = subprocess.run(cmd, check=True, timeout=timeout, capture_output=True).stdout
    size = SIDE * SIDE
    return [out[i:i + size] for i in range(0, len(out) - size + 1, size)]


def _diff(a: bytes, b: bytes) -> float:
    return sum(abs(x - y) for x, y in zip(a, b)) / len(a)


def _duration(exe: str, src: str) -> float | None:
    r = subprocess.run([exe, "-hide_banner", "-i", src], capture_output=True, text=True, timeout=30)
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", r.stderr or "")
    if not m:
        return None
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))


def find_cut(frames: list[bytes], fps: int = FPS) -> tuple[float | None, dict]:
    """Kapanışta bozulma varsa kesilecek saniyeyi döndürür (yoksa None) ve ölçümleri verir."""
    w = max(2, round(WINDOW_S * fps))
    n = len(frames)
    info: dict = {"frames": n}
    if n < 3 * w:
        return None, info
    # Olağan değişim: gövdede w kare arayla fark (kapanış penceresi hariç).
    body = sorted(_diff(frames[i], frames[i - w]) for i in range(w, n - w))
    normal = body[len(body) // 2]
    anchor = n - w - 1  # kapanış penceresinden hemen önceki kare
    end = [_diff(frames[k], frames[anchor]) for k in range(anchor + 1, n)]
    threshold = max(MIN_DIFF, RATIO * normal)
    info.update(normal=round(normal, 2), end_max=round(max(end), 2), threshold=round(threshold, 2))
    if max(end) <= threshold:
        return None, info
    # Bozulmanın başladığı kare: farkın eşiğin yarısını ilk aştığı yer (bozulma kademeli büyür).
    # Analiz kareleri arasında kalan kısa ara da şüpheli sayılır: kesim, son sağlam analiz karesinde yapılır.
    first = next(i for i, d in enumerate(end) if d > threshold / 2)
    return (anchor + first) / fps, info


def guard(data: bytes, timeout: float = 120) -> tuple[bytes, dict]:
    """Bozuk kapanışı son sağlam kareyle değiştirir. (video, rapor) döner; rapor ``trimmed`` içerir."""
    report: dict = {"trimmed": False}
    exe = _ffmpeg()
    if not exe or not data:
        return data, report
    with tempfile.TemporaryDirectory() as tmp:
        src, dst = os.path.join(tmp, "in.mp4"), os.path.join(tmp, "out.mp4")
        with open(src, "wb") as f:
            f.write(data)
        try:
            cut, info = find_cut(_frames(exe, src, timeout))
            report.update(info)
            if cut is None:
                return data, report
            duration = _duration(exe, src)
            if not duration or cut <= 0 or duration - cut > MAX_CUT_S:
                logger.warning("Kapanış bozulması şüpheli, dokunulmadı (kesim %.2f / süre %s)", cut, duration)
                report["skipped"] = True
                return data, report
            vf = (f"trim=end={cut:.3f},setpts=PTS-STARTPTS,"
                  f"tpad=stop_mode=clone:stop_duration={duration - cut + 0.2:.3f}")
            cmd = [exe, "-y", "-loglevel", "error", "-i", src, "-vf", vf, "-t", f"{duration:.3f}",
                   "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p",
                   "-c:a", "copy", "-movflags", "+faststart", dst]
            subprocess.run(cmd, check=True, timeout=timeout, capture_output=True)
            with open(dst, "rb") as f:
                out = f.read()
            if not out:
                return data, report
            report.update(trimmed=True, cut_at=round(cut, 2), duration=round(duration, 2))
            logger.info("Video kapanışı bozuk: %.2f sn'den sonrası son sağlam kareyle dolduruldu (%s)", cut, info)
            return out, report
        except (subprocess.SubprocessError, OSError, ValueError) as e:
            logger.error("Son-kare denetimi yapılamadı: %s", e)
            return data, report
