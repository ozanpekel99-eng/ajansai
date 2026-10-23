"""Sağlık ve kalite denetimi uçları (zamanlanmış görevler ve Vercel Cron için).

- GET  /api/health          → sistem ayakta mı (veritabanı, AI Gateway ayarı)
- POST /api/health/qa-run   → sabit Türkçe istek setiyle görsel (haftalık ise bir de video) üretir,
                              her görseli kalite denetiminden geçirir, sonucu saklar ve yöneticiye e-postalar.
                              Kimlik gerektirmez ama maliyeti sınırlamak için 20 saatte bir çalışır.
- GET  /api/health/qa       → son kalite raporu (video işi bitmediyse durumunu yeniler)

Rapor gizli bilgi içermez: istekler, üretilen test görsellerinin adresleri, bulunan kusurlar ve süreler.
"""

import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from sqlalchemy import select, text

from app import config
from app.db import app_settings, get_engine
from app.services import gateway_media, media_planner, media_qa, storage

router = APIRouter()
logger = logging.getLogger("ajansai.health")

REPORT_KEY = "qa_latest"
MIN_INTERVAL_S = 20 * 3600

# Basit Türkçe istekler (gerçek kullanıcıların yazacağı gibi); sektörler dönüşümlü kalır.
QA_PROMPTS = [
    ("mobilya", "Mobilya mağazası için kampanya görseli: Tüm ürünlerde %40 indirim, ücretsiz teslimat ve montaj", "4:5"),
    ("beyaz_esya", "Beyaz eşya mağazası için kampanya görseli: Çamaşır makinesi ve kurutma makinesi ikili alımda 10.000 TL indirim, peşin fiyatına 9 taksit", "9:16"),
    ("kafe", "Kafem için Instagram gönderisi: Yeni sezon kabak baharatlı latte, 120 TL", "1:1"),
    ("guzellik", "Güzellik merkezi için kampanya: Lazer epilasyonda 6 seans alana 2 seans hediye", "4:5"),
]
QA_VIDEO = ("Bu kampanya görselinden Instagram reklam videosu yap", 6)


def _get(key: str) -> str | None:
    with get_engine().connect() as conn:
        return conn.execute(select(app_settings.c.value).where(app_settings.c.key == key)).scalar()


def _set(key: str, value: str) -> None:
    with get_engine().begin() as conn:
        if conn.execute(select(app_settings.c.key).where(app_settings.c.key == key)).first():
            conn.execute(app_settings.update().where(app_settings.c.key == key).values(value=value))
        else:
            conn.execute(app_settings.insert().values(key=key, value=value))


@router.get("")
def health():
    db_ok = True
    try:
        with get_engine().connect() as conn:
            conn.execute(text("select 1"))
    except Exception:  # noqa: BLE001
        db_ok = False
    return {"ok": db_ok, "db": db_ok, "ai_gateway": gateway_media.is_enabled(), "storage": storage.is_enabled(),
            "time": datetime.now(timezone.utc).isoformat()}


def _one_image(name: str, request: str, aspect: str) -> dict:
    t = time.time()
    try:
        # Üretimdeki akışın aynısı: istem yazımı → üretim → denetim (kusurluysa bir kez yeniden üretim).
        prompt = media_planner.direct_ad_prompt(request, aspect, False, 0, None)
        data, mime = media_qa.generate_checked(prompt, aspect, None, request)
        problems = media_qa.check_image(data, request, None)  # kullanıcının göreceği son görselin denetimi
        url = storage.save(data, mime, "qa")
        return {"name": name, "request": request, "aspect": aspect, "url": url, "problems": problems,
                "ok": not problems, "seconds": round(time.time() - t, 1)}
    except Exception as e:  # noqa: BLE001
        return {"name": name, "request": request, "aspect": aspect, "url": None, "problems": [f"Üretim hatası: {str(e)[:300]}"],
                "ok": False, "seconds": round(time.time() - t, 1)}


def _email(report: dict) -> None:
    try:
        from app.services import support

        lines = [f"ajansAI kalite raporu — {report['finished_at'][:16].replace('T', ' ')} UTC",
                 f"Görsel: {report['passed']}/{report['total']} sorunsuz", ""]
        for r in report["images"]:
            lines.append(f"• {r['name']}: {'TAMAM' if r['ok'] else 'SORUN'} ({r['seconds']} sn)")
            for p in r["problems"]:
                lines.append(f"   - {p}")
            if r["url"]:
                lines.append(f"   {r['url']}")
        if report.get("video"):
            lines += ["", f"Video: {report['video'].get('status')} (sonuç: {config.PUBLIC_API_URL}/api/health/qa)"]
        support.send_email(sorted(config.ADMIN_EMAILS), f"ajansAI kalite: {report['passed']}/{report['total']} sorunsuz", "\n".join(lines))
    except Exception as e:  # noqa: BLE001
        logger.warning("Kalite raporu e-postası gönderilemedi: %s", e)


@router.api_route("/qa-run", methods=["GET", "POST"])
def qa_run(video: str = "auto"):
    if not gateway_media.is_enabled():
        raise HTTPException(status_code=503, detail="AI Gateway kapalı.")
    last = _get(REPORT_KEY)
    if last:
        try:
            started = datetime.fromisoformat(json.loads(last)["started_at"])
            if (datetime.now(timezone.utc) - started).total_seconds() < MIN_INTERVAL_S:
                return {"skipped": True, "reason": "Son 20 saatte zaten çalıştı.", "report": json.loads(last)}
        except Exception:  # noqa: BLE001
            pass
    started_at = datetime.now(timezone.utc).isoformat()
    _set(REPORT_KEY, json.dumps({"started_at": started_at, "status": "running", "images": []}))

    with ThreadPoolExecutor(max_workers=4) as pool:
        images = list(pool.map(lambda p: _one_image(*p), QA_PROMPTS))

    report = {"started_at": started_at, "finished_at": datetime.now(timezone.utc).isoformat(), "status": "done",
              "images": images, "passed": sum(1 for r in images if r["ok"]), "total": len(images)}

    # Haftalık: ilk sorunsuz görselden video (ana model; Kling yalnızca Veo başlamazsa)
    want_video = video in ("1", "true") or (video == "auto" and datetime.now(timezone.utc).weekday() == 0)
    if want_video:
        src = next((r for r in images if r["url"] and r["ok"]), None) or next((r for r in images if r["url"]), None)
        if src:
            try:
                plan = media_planner.plan_video(QA_VIDEO[0], "9:16", QA_VIDEO[1], has_start_frame=True, audio=False,
                                                start_image_url=src["url"])
                job = gateway_media.start_video(plan["prompt"], QA_VIDEO[1], "1080p", src["url"], None, False, "9:16")
                report["video"] = {"status": "pending", "from": src["name"], "job": job, "model": job.get("model"),
                                   "fallback": bool(job.get("fallback"))}
            except Exception as e:  # noqa: BLE001
                report["video"] = {"status": "error", "error": str(e)[:300]}

    _set(REPORT_KEY, json.dumps(report))
    _email(report)
    return report


@router.get("/qa")
def qa_report():
    raw = _get(REPORT_KEY)
    if not raw:
        return {"status": "none"}
    report = json.loads(raw)
    v = report.get("video")
    if v and v.get("status") == "pending" and v.get("job"):
        try:
            res = gateway_media.video_status(v["job"])
            if res["status"] == "completed":
                vid = res["video"]
                if vid.get("type") == "url":
                    import requests

                    data = requests.get(vid["url"], timeout=120).content
                else:
                    import base64

                    data = base64.b64decode(vid.get("data", ""))
                v.update(status="completed", url=storage.save(data, "video/mp4", "qa"))
            elif res["status"] == "error":
                v.update(status="error", error=str(res.get("error"))[:300])
            _set(REPORT_KEY, json.dumps(report))
        except Exception as e:  # noqa: BLE001
            logger.warning("QA video durumu alınamadı: %s", e)
    public = dict(report)
    if public.get("video"):
        public["video"] = {k: v for k, v in public["video"].items() if k != "job"}
    return public


DAILY_KEY = "daily_report_at"


def _daily_text(st: dict, day: dict) -> str:
    lines = [f"ajansAI günlük kullanım raporu ({datetime.now(timezone.utc).strftime('%d.%m.%Y')})", ""]
    lines.append(f"Son 24 saat: {day['real_signups_in_period']} yeni üye, {day['guest_unique_total']} farklı misafir ziyaretçi "
                 f"(misafir kullanımı: {day['guest_events_by_kind'] or 'yok'}), {day['real_member_free_events']} ücretsiz üye kullanımı.")
    paid = [p for p in day["payments"] if not p["test"] and not p["sandbox"]]
    ok = [p for p in paid if p["status"] == "success"]
    lines.append(f"Ödeme: {len(ok)} başarılı, {len(paid) - len(ok)} başarısız/yarım (test hariç).")
    lines.append("")
    lines.append(f"Toplam gerçek üye: {st['users_real']} (son 30 günde {st['real_signups_in_period']} kayıt). "
                 f"30 günde farklı misafir: {st['guest_unique_total']}.")
    if st["real_users"]:
        lines += ["", "Son üyeler:"]
        for u in st["real_users"][:15]:
            lines.append(f"• {u['email']} — {u['plan']}, kayıt {u['created_at'][:10]}, {u['chats']} sohbet, "
                         f"{u['media']} görsel/video, {u['credits_used']} kredi")
    if st["guest_unique_visitors_by_day"]:
        lines += ["", "Günlük misafir (farklı kişi): " + ", ".join(f"{d[5:]}: {n}" for d, n in list(st["guest_unique_visitors_by_day"].items())[-10:])]
    return "\n".join(lines)


@router.api_route("/daily-report", methods=["GET", "POST"])
def daily_report():
    """Yöneticiye günlük kullanım raporu e-postası (veri yanıtta dönmez). 20 saatte bir."""
    last = _get(DAILY_KEY)
    if last and (datetime.now(timezone.utc) - datetime.fromisoformat(last)).total_seconds() < MIN_INTERVAL_S:
        return {"sent": False, "reason": "Son 20 saatte gönderildi."}
    from app.routers.admin import usage_stats
    from app.services import support

    text_body = _daily_text(usage_stats(30), usage_stats(1))
    try:
        support.send_email(sorted(config.ADMIN_EMAILS), "ajansAI günlük kullanım raporu", text_body)
    except Exception as e:  # noqa: BLE001
        logger.error("Günlük rapor gönderilemedi: %s", e)
        return {"sent": False, "reason": "E-posta gönderilemedi."}
    _set(DAILY_KEY, datetime.now(timezone.utc).isoformat())
    return {"sent": True}
