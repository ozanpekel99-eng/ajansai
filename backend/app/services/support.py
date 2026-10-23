"""support@ajansai.tr: gelen e-postayı okur, Claude ile yanıt yazar, gönderir ve kopyasını iletir.

Akış: Resend gelen e-postayı alır → `email.received` webhook'u /api/support/inbound'a gelir →
e-postanın içeriği Resend API'den çekilir → otomatik/toplu e-postalar ve kendi gönderdiklerimiz
elenir → Claude, ajansAI bilgi tabanıyla yanıt yazar → yanıt aynı konuşma zincirinde gönderilir →
gelen e-posta ve yanıt SUPPORT_FORWARD_TO adresine iletilir (oradan doğrudan müşteriye
cevap verilebilir). Para iadesi, ödeme itirazı, hukuki konu, hesap güvenliği gibi durumlarda
yanıt yalnızca talebin alındığını söyler ve ileti "İnsan gerekli" diye işaretlenir.
"""

import base64
import hashlib
import hmac
import html as html_lib
import json
import logging
import re
import time
import uuid
from datetime import datetime, timedelta, timezone
from email.utils import parseaddr

import requests
from sqlalchemy import and_, func, insert, select, update
from sqlalchemy.exc import IntegrityError

from app import config
from app.db import get_engine, support_tickets
from app.services import llm_service
from app.services.plans import CREDIT_COSTS, CREDIT_PACKS, PLANS, VAT_RATE

logger = logging.getLogger(__name__)

RESEND_API = "https://api.resend.com"


class SupportError(Exception):
    pass


# ---------------------------------------------------------------- webhook doğrulama (Svix)


def verify_signature(headers: dict, body: bytes, secret: str | None = None, tolerance: int = 300) -> bool:
    """Resend webhook imzası (Svix şeması): HMAC-SHA256(`id.timestamp.body`), base64."""
    secret = secret if secret is not None else config.RESEND_WEBHOOK_SECRET
    if not secret:
        return False
    h = {k.lower(): v for k, v in headers.items()}
    msg_id, ts, sigs = h.get("svix-id"), h.get("svix-timestamp"), h.get("svix-signature")
    if not (msg_id and ts and sigs):
        return False
    try:
        if abs(time.time() - int(ts)) > tolerance:
            return False
        key = base64.b64decode(secret.removeprefix("whsec_"))
    except (ValueError, TypeError):
        return False
    expected = base64.b64encode(
        hmac.new(key, f"{msg_id}.{ts}.".encode() + body, hashlib.sha256).digest()
    ).decode()
    for part in sigs.split():
        _, _, sig = part.partition(",")
        if sig and hmac.compare_digest(sig, expected):
            return True
    return False


# ---------------------------------------------------------------- Resend API


def _resend(method: str, path: str, **kwargs) -> dict:
    if not config.RESEND_API_KEY:
        raise SupportError("RESEND_API_KEY tanımlı değil.")
    try:
        r = requests.request(
            method, RESEND_API + path,
            headers={"Authorization": f"Bearer {config.RESEND_API_KEY}"},
            timeout=30, **kwargs,
        )
    except requests.RequestException as e:
        raise SupportError(f"Resend'e ulaşılamadı: {e}") from e
    if r.status_code >= 300:
        raise SupportError(f"Resend {r.status_code}: {r.text[:300]}")
    return r.json() if r.content else {}


def fetch_email(email_id: str) -> dict:
    return _resend("GET", f"/emails/receiving/{email_id}")


def send_email(to: list[str], subject: str, text: str, reply_to: str | None = None,
               headers: dict | None = None) -> dict:
    payload = {
        "from": config.SUPPORT_FROM,
        "to": to,
        "subject": subject[:300],
        "text": text,
        "html": _to_html(text),
    }
    if reply_to:
        payload["reply_to"] = reply_to
    if headers:
        payload["headers"] = headers
    return _resend("POST", "/emails", json=payload, headers={"Idempotency-Key": str(uuid.uuid4())})


# ---------------------------------------------------------------- metin işleme


def _decode_html(value: str | None) -> str:
    if not value:
        return ""
    if value.startswith("data:"):  # html_format: data_uri
        head, _, data = value.partition(",")
        try:
            value = base64.b64decode(data).decode("utf-8", "replace") if ";base64" in head else requests.utils.unquote(data)
        except (ValueError, TypeError):
            return ""
    return value


def html_to_text(value: str) -> str:
    value = re.sub(r"(?is)<(script|style|head)[^>]*>.*?</\1>", " ", value)
    value = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</li>|</tr>|</h\d>", "\n", value)
    value = re.sub(r"(?s)<[^>]+>", " ", value)
    value = html_lib.unescape(value)
    value = re.sub(r"[ \t\xa0]+", " ", value)
    return re.sub(r"\n\s*\n+", "\n\n", value).strip()


_QUOTE_MARKERS = [
    r"^On .+ wrote:\s*$",
    r"^.+ tarihinde .+ şunu yazdı:\s*$",
    r"^.+ tarihinde .+ yazdı:\s*$",
    r"^-{2,}\s*Original Message\s*-{2,}",
    r"^-{2,}\s*Orijinal [İI]leti\s*-{2,}",
    r"^From: .+$",
    r"^Kimden: .+$",
]


def strip_quoted(text: str) -> str:
    """Yanıt zincirinde alıntılanan eski mesajları atar."""
    out = []
    for line in text.splitlines():
        if any(re.match(p, line.strip(), re.I) for p in _QUOTE_MARKERS):
            break
        if line.lstrip().startswith(">"):
            continue
        out.append(line)
    return "\n".join(out).strip()


def message_text(email: dict) -> str:
    text = email.get("text") or html_to_text(_decode_html(email.get("html")))
    return strip_quoted(text or "")[:8000]


def _to_html(text: str) -> str:
    paras = [html_lib.escape(p).replace("\n", "<br>") for p in text.strip().split("\n\n")]
    body = "".join(f'<p style="margin:0 0 14px">{p}</p>' for p in paras)
    return f'<div style="font-family:Arial,Helvetica,sans-serif;font-size:15px;line-height:1.55;color:#1a1a1a">{body}</div>'


# ---------------------------------------------------------------- eleme


def sender_address(email: dict) -> str:
    return parseaddr(email.get("from") or "")[1].lower()


def skip_reason(email: dict) -> str | None:
    """Otomatik yanıt verilmemesi gereken e-postalar (döngü ve spam koruması)."""
    addr = sender_address(email)
    if not addr or "@" not in addr:
        return "gönderen okunamadı"
    domain = addr.split("@", 1)[1]
    own = config.SUPPORT_ADDRESS.split("@", 1)[-1].lower()
    if domain == own or domain.endswith("." + own):
        return "kendi alan adımızdan"
    local = addr.split("@", 1)[0]
    if re.match(r"^(no-?reply|do-?not-?reply|mailer-daemon|postmaster|bounce|bounces|notifications?|noreply-.*)$", local):
        return "otomatik gönderici"
    headers = {str(k).lower(): str(v).lower() for k, v in (email.get("headers") or {}).items()}
    if headers.get("auto-submitted", "no") not in ("no", ""):
        return "otomatik e-posta (Auto-Submitted)"
    if headers.get("precedence") in ("bulk", "list", "junk", "auto_reply"):
        return "toplu e-posta"
    if any(k in headers for k in ("list-id", "list-unsubscribe", "x-autoreply", "x-autorespond", "x-auto-response-suppress")):
        return "liste/otomatik yanıt e-postası"
    auth = email.get("authentication") or {}
    if auth and all(str((auth.get(k) or {}).get("result") if isinstance(auth.get(k), dict) else auth.get(k)).lower() == "fail"
                    for k in ("spf", "dkim")):
        return "SPF ve DKIM doğrulanamadı"
    return None


def replies_today(addr: str) -> int:
    since = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=1)
    with get_engine().connect() as conn:
        return conn.execute(
            select(func.count()).select_from(support_tickets).where(
                and_(support_tickets.c.from_addr == addr, support_tickets.c.created_at >= since,
                     support_tickets.c.status.in_(["replied", "escalated"]))
            )
        ).scalar_one()


def claim(email_id: str) -> bool:
    """E-postayı işlemek için sahiplenir; webhook tekrar gelirse ikinci kez işlenmez."""
    try:
        with get_engine().begin() as conn:
            conn.execute(insert(support_tickets).values(
                id=email_id, from_addr="", subject="", body="", status="processing",
                created_at=datetime.now(timezone.utc).replace(tzinfo=None),
            ))
        return True
    except IntegrityError:
        return False


def record(email_id: str, addr: str, subject: str, body: str, reply: str | None, status: str, note: str | None = None) -> None:
    with get_engine().begin() as conn:
        conn.execute(update(support_tickets).where(support_tickets.c.id == email_id).values(
            from_addr=addr[:320], subject=(subject or "")[:500], body=body, reply=reply,
            status=status, note=(note or "")[:300] or None,
        ))


# ---------------------------------------------------------------- yanıt üretimi


def knowledge_base() -> str:
    plans = "\n".join(
        f"- {p['name']}: aylık {p['price']} $ + %{VAT_RATE} KDV, ayda {p['credits']} kredi"
        f"{', video üretimi' if p['video_enabled'] else ''}{', Meta (Instagram/Facebook) reklam yönetimi' if p['ads_enabled'] else ''}"
        for k, p in PLANS.items() if p["purchasable"]
    )
    packs = ", ".join(f"{v['name']} {v['price']} $" for v in CREDIT_PACKS.values())
    c = CREDIT_COSTS
    return f"""ajansAI (www.ajansai.tr): Türkiye'deki KOBİ'ler için yapay zekâ destekli sosyal medya ve reklam platformu.
Özellikler: sohbet asistanı (fikir, metin, veri analizi, sunum/belge/tablo dosyası üretme, web araması),
görsel üretimi, video üretimi (Video sayfasında, birden fazla görsel yüklenebilir), kütüphane (üretilenler, indirme),
sesli konuşma (gerçek zamanlı), Meta reklamları (Instagram ve Facebook; reklam bütçesi kullanıcının kendi Meta reklam
hesabından ve kartından harcanır, ajansAI kredisi harcamaz; reklamlar duraklatılmış oluşturulur, "Yayına al" ile başlar).

Paketler (ödeme iyzico ile, ABD doları; otomatik yenilenmez):
- Ücretsiz: kredisiz sohbet (günlük mesaj sınırı), ayda {config.FREE_IMAGES_PER_MONTH} ücretsiz görsel; video ve reklam yok.
{plans}
- Yıllık ödemede %20 indirim; yıllık pakette 12 aylık kredi tek seferde hesaba yüklenir.
- Aylık pakette krediler 30 günde bir yenilenir, kullanılmayan kredi devretmez.
- Ek kredi paketleri (ücretli paket gerekir, dönem bitince silinmez): {packs} (+KDV).
Kredi maliyetleri: sohbet mesajı {c['chat_message']}, mesaja eklenen dosya {c['chat_attachment']}, görsel {c['image']},
dosya (sunum/belge/tablo) {c['file']}, video 1080p 4 sn {c['video']['1080p']['4']} kredi'den başlar; sesli konuşma dakikada 3 kredi.
Teknik hatayla başarısız olan üretimin kredisi otomatik iade edilir.

Sık sorulanlar:
- Meta bağlama: Araçlar > Reklamlar > "Meta ile bağlan"; izin ekranında reklam hesabı, Facebook sayfası ve Instagram
  hesabını işaretle. Sayfa veya Instagram görünmüyorsa "Meta bağlantısını kaldır" deyip yeniden bağlanırken hepsini seç.
  Instagram'ın profesyonel hesap olması ve Facebook sayfasına bağlı olması gerekir. Kart, Meta'nın kendi ödeme sayfasında eklenir.
- Faturalandırma ve kullanım: panelde "Faturalandırma" ve "Kullanım" sayfaları.
- Hesap/veri silme: www.ajansai.tr/veri-silme. Gizlilik: www.ajansai.tr/gizlilik. Koşullar: www.ajansai.tr/kosullar.
- İade ve cayma talepleri ekip tarafından mevzuata uygun değerlendirilir (kullanılmamış paketler)."""


SYSTEM_PROMPT = """Sen ajansAI'ın destek ekibisin ve support@ajansai.tr adresine gelen e-postaları yanıtlıyorsun.

Kurallar:
- Müşterinin yazdığı dilde yanıt ver (çoğunlukla Türkçe). Sıcak, kısa ve net ol; "sen" diye hitap et.
- Yalnızca aşağıdaki bilgi tabanına dayan. Bilmediğin bir şeyi uydurma, söz verme, tarih/indirim/iade taahhüdü verme.
- Adım gerekiyorsa numaralı kısa adımlar yaz. Markdown kullanma (düz metin e-posta).
- İmza: "ajansAI Destek Ekibi".
- Şu durumlarda escalate=true yap ve yanıtta yalnızca talebin alındığını, ekibin en geç 1 iş günü içinde döneceğini söyle
  (gerekirse hangi bilgiyi göndermesi gerektiğini ekle): para iadesi, cayma, ödeme itirazı / çift çekim, fatura düzeltme,
  hukuki konu, hesap güvenliği veya ele geçirilmiş hesap, kişisel veri talebi, şikâyet/öfkeli müşteri, iş birliği veya
  satış teklifi, teknik hata bildirimi (ekranda hata, çalışmayan özellik) ya da bilgi tabanında cevabı olmayan soru.
- Spam, reklam veya anlamsız içerikse spam=true yap.

Sadece şu JSON ile yanıt ver:
{"reply": "<e-posta metni>", "escalate": true|false, "spam": true|false, "reason": "<kısa gerekçe>"}

Bilgi tabanı:
"""


def draft_reply(subject: str, body: str, sender: str) -> dict:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT + knowledge_base()},
        {"role": "user", "content": f"Gönderen: {sender}\nKonu: {subject}\n\n{body}"},
    ]
    try:
        raw = llm_service.chat_completion(config.CHAT_MODEL, messages, max_tokens=1200)
    except Exception:  # noqa: BLE001
        raw, _ = llm_service.smart_chat_completion(messages, max_tokens=1200, paid=True)
    return parse_reply(raw)


def parse_reply(raw: str) -> dict:
    m = re.search(r"\{.*\}", raw or "", re.S)
    try:
        data = json.loads(m.group(0)) if m else {}
    except json.JSONDecodeError:
        data = {}
    reply = str(data.get("reply") or "").strip()
    if not reply:
        # Model JSON dışında yazdıysa: güvenli tarafta kal, insana yönlendir
        return {"reply": "", "escalate": True, "spam": False, "reason": "yanıt ayrıştırılamadı"}
    return {"reply": reply, "escalate": bool(data.get("escalate")), "spam": bool(data.get("spam")),
            "reason": str(data.get("reason") or "")[:200]}


ESCALATION_FALLBACK = (
    "Merhaba,\n\nMesajın bize ulaştı, teşekkürler. Ekibimiz talebini inceleyip en geç 1 iş günü içinde sana dönüş yapacak.\n\n"
    "ajansAI Destek Ekibi"
)


# ---------------------------------------------------------------- ana akış


def _reply_subject(subject: str) -> str:
    subject = (subject or "").strip() or "Destek talebin"
    return subject if re.match(r"^(re|ynt|yanıt)\s*:", subject, re.I) else f"Re: {subject}"


def handle_inbound(email_id: str) -> dict:
    """Webhook'tan gelen bir e-postayı işler. Aynı e-posta iki kez işlenmez."""
    if not claim(email_id):
        return {"status": "duplicate"}
    try:
        email = fetch_email(email_id)
    except SupportError as e:
        record(email_id, "", "", "", None, "error", str(e))
        raise
    addr = sender_address(email)
    subject = email.get("subject") or ""
    body = message_text(email)

    reason = skip_reason(email)
    if not reason and not body.strip():
        reason = "boş e-posta"
    if not reason and replies_today(addr) >= config.SUPPORT_REPLIES_PER_SENDER_PER_DAY:
        reason = "günlük otomatik yanıt sınırı"
    if reason or not config.SUPPORT_AUTO_REPLY:
        record(email_id, addr, subject, body, None, "skipped", reason or "otomatik yanıt kapalı")
        _forward(addr, subject, body, None, label="Otomatik yanıt verilmedi: " + (reason or "kapalı"))
        return {"status": "skipped", "reason": reason}

    try:
        draft = draft_reply(subject, body, email.get("from") or addr)
    except Exception as e:  # noqa: BLE001
        logger.exception("Destek yanıtı üretilemedi")
        draft = {"reply": "", "escalate": True, "spam": False, "reason": f"model hatası: {e}"[:200]}

    if draft["spam"]:
        record(email_id, addr, subject, body, None, "skipped", "spam: " + draft["reason"])
        return {"status": "spam"}

    reply = draft["reply"] or ESCALATION_FALLBACK
    msg_id = email.get("message_id")
    thread = {"In-Reply-To": msg_id, "References": msg_id} if msg_id else None
    status = "escalated" if draft["escalate"] else "replied"
    try:
        send_email([addr], _reply_subject(subject), reply, reply_to=config.SUPPORT_ADDRESS, headers=thread)
    except SupportError as e:
        record(email_id, addr, subject, body, reply, "error", str(e))
        _forward(addr, subject, body, reply, label="Yanıt GÖNDERİLEMEDİ")
        raise
    record(email_id, addr, subject, body, reply, status, draft["reason"])
    _forward(addr, subject, body, reply, label="İnsan gerekli" if draft["escalate"] else "Otomatik yanıtlandı")
    return {"status": status}


def _forward(addr: str, subject: str, body: str, reply: str | None, label: str) -> None:
    """Gelen e-postayı ve verilen yanıtı sahibine iletir; 'Yanıtla' doğrudan müşteriye gider."""
    if not config.SUPPORT_FORWARD_TO:
        return
    text = f"{label}\nGönderen: {addr}\nKonu: {subject}\n\n--- Müşterinin mesajı ---\n{body}\n"
    if reply:
        text += f"\n--- Gönderilen yanıt ---\n{reply}\n"
    text += "\nBu e-postayı yanıtlarsan cevabın doğrudan müşteriye gider."
    try:
        send_email([config.SUPPORT_FORWARD_TO], f"[Destek · {label}] {subject or '(konu yok)'}", text, reply_to=addr)
    except SupportError:
        logger.exception("Destek e-postası iletilemedi")
