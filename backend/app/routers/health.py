"""Sağlık ve kalite denetimi uçları (zamanlanmış görevler ve Vercel Cron için).

- GET  /api/health          → sistem ayakta mı (veritabanı, AI Gateway ayarı)
- POST /api/health/qa-run   → sabit Türkçe istek setiyle görsel (haftalık ise bir de video) üretir,
                              her görseli kalite denetiminden geçirir, sonucu saklar ve yöneticiye e-postalar.
                              Kimlik gerektirmez ama maliyeti sınırlamak için 20 saatte bir çalışır.
- GET  /api/health/qa       → son kalite raporu (video işi bitmediyse durumunu yeniler) ve
                              gerçek kullanıcı üretimlerinde son 24 saatin hata sayıları (`production_errors`)

Rapor gizli bilgi içermez: istekler, üretilen test görsellerinin adresleri, bulunan kusurlar ve süreler.
Üretim hata özeti yalnızca sayılar ve kısaltılmış hata metinleri içerir (kullanıcı kimliği/e-posta/istem yok).
"""

import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from collections import Counter
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException
from sqlalchemy import and_, func, select, text

from app import config
from app.db import app_settings, credit_events, get_engine, utcnow, video_tasks
from app.services import gateway_media, media_planner, media_qa, storage

router = APIRouter()
logger = logging.getLogger("ajansai.health")

REPORT_KEY = "qa_latest"
MIN_INTERVAL_S = 20 * 3600
STUCK_VIDEO_S = 30 * 60  # bu süreden uzun "pending" kalan video işi takılmış sayılır

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


def _short_error(err: str | None) -> str:
    """Hata metnini gruplamak için kısaltır (adres ve uzun ayrıntılar atılır)."""
    msg = " ".join((err or "Bilinmeyen hata").split())
    for cut in (" http", " {"):
        i = msg.find(cut)
        if i > 0:
            msg = msg[:i]
    return msg[:120]


def production_errors(hours: int = 24) -> dict:
    """Gerçek kullanıcı üretimlerinde son `hours` saatin hata sayıları.

    - video: `video_tasks` durumlarına göre; 30 dk'dan uzun bekleyen işler "stuck";
      hiç başlatılamayan videolar (iade edilmiş ama işi olmayan kredi kaydı) "start_failed".
    - image: kredili görsel üretimleri (`credit_events` action=image); iade edilenler başarısız sayılır
      (görsel sayfası, sohbet görseli ve video açılış karesi dahil).
    """
    now = utcnow()
    since = now - timedelta(hours=hours)
    stuck_before = now - timedelta(seconds=STUCK_VIDEO_S)
    with get_engine().connect() as conn:
        rows = conn.execute(
            select(video_tasks.c.status, video_tasks.c.error, video_tasks.c.created_at)
            .where(video_tasks.c.created_at >= since)
        ).all()
        img_total, img_failed = conn.execute(
            select(func.count(), func.coalesce(func.sum(credit_events.c.refunded), 0))
            .where(and_(credit_events.c.action == "image", credit_events.c.created_at >= since))
        ).one()
        start_failed = conn.execute(
            select(func.count()).select_from(credit_events).where(and_(
                credit_events.c.action == "video", credit_events.c.refunded == 1,
                credit_events.c.created_at >= since,
                credit_events.c.id.not_in(select(video_tasks.c.credit_event_id)),
            ))
        ).scalar()
    by_status = Counter(r.status for r in rows)
    stuck = sum(1 for r in rows if r.status == "pending" and r.created_at < stuck_before)
    errors = Counter(_short_error(r.error) for r in rows if r.status == "failed")
    video_failed = by_status.get("failed", 0) + int(start_failed or 0)
    return {
        "hours": hours,
        "video": {
            "total": len(rows) + int(start_failed or 0),
            "completed": by_status.get("completed", 0),
            "pending": by_status.get("pending", 0) - stuck,
            "stuck": stuck,
            "failed": by_status.get("failed", 0),
            "start_failed": int(start_failed or 0),
            "top_errors": [{"error": e, "count": n} for e, n in errors.most_common(5)],
        },
        "image": {"total": int(img_total or 0), "failed": int(img_failed or 0)},
        "failed_total": video_failed + int(img_failed or 0),
    }


def _safe_production_errors() -> dict | None:
    try:
        return production_errors()
    except Exception as e:  # noqa: BLE001 — rapor üretim özeti yüzünden düşmesin
        logger.warning("Üretim hata özeti alınamadı: %s", e)
        return None


def _production_lines(pe: dict | None) -> list[str]:
    if not pe:
        return []
    v, i = pe["video"], pe["image"]
    lines = ["", f"Gerçek üretimler (son {pe['hours']} saat):",
             f"• Görsel: {i['total']} üretim, {i['failed']} hata",
             f"• Video: {v['total']} iş, {v['completed']} tamam, {v['failed']} hata, "
             f"{v['start_failed']} başlatılamadı, {v['stuck']} takılı (30 dk+), {v['pending']} sürüyor"]
    for e in v["top_errors"]:
        lines.append(f"   - {e['count']}× {e['error']}")
    return lines


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
        lines += _production_lines(report.get("production_errors"))
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
              "images": images, "passed": sum(1 for r in images if r["ok"]), "total": len(images),
              "production_errors": _safe_production_errors()}

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
        return {"status": "none", "production_errors": _safe_production_errors()}
    report = json.loads(raw)
    v = report.get("video")
    if v and v.get("status") == "pending" and v.get("job"):
        try:
            res = gateway_media.video_status(v["job"])
            if res["status"] == "completed":
                from app.services import video_upscale

                data = gateway_media.fetch_video(res["video"])
                if v["job"].get("upscale_to"):
                    data = video_upscale.upscale(data, v["job"]["upscale_to"])
                v.update(status="completed", url=storage.save(data, "video/mp4", "qa"))
            elif res["status"] == "error":
                v.update(status="error", error=str(res.get("error"))[:300])
            _set(REPORT_KEY, json.dumps(report))
        except Exception as e:  # noqa: BLE001
            logger.warning("QA video durumu alınamadı: %s", e)
    public = dict(report)
    if public.get("video"):
        public["video"] = {k: v for k, v in public["video"].items() if k != "job"}
    # Rapor anındaki değil, şu anki son 24 saat (rapor 20 saatte bir üretilir)
    public["production_errors"] = _safe_production_errors()
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


CLEANUP_KEY = "retention_cleanup_at"


@router.api_route("/cleanup", methods=["GET", "POST"])
def cleanup(dry_run: bool = False):
    """Ücretsiz kullanıcı dosyalarını saklama süresi dolunca siler (Vercel Cron, günde bir)."""
    if not storage.is_enabled():
        return {"deleted": 0, "reason": "Blob deposu bağlı değil."}
    if not dry_run:
        last = _get(CLEANUP_KEY)
        if last and (datetime.now(timezone.utc) - datetime.fromisoformat(last)).total_seconds() < MIN_INTERVAL_S:
            return {"deleted": 0, "reason": "Son 20 saatte çalıştı."}
    from app.services import retention

    try:
        result = retention.run(dry_run=dry_run)
    except storage.StorageError as e:
        logger.error("Saklama temizliği başarısız: %s", e)
        return {"deleted": 0, "reason": "Depoya ulaşılamadı."}
    if not dry_run:
        _set(CLEANUP_KEY, datetime.now(timezone.utc).isoformat())
    return result
