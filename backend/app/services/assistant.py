"""ajansAI sohbet asistanı: tek metin kutusu + ekler (görsel, video, belge).

Kullanıcıdan form doldurması istenmez; işletme bilgisi gerekiyorsa asistan
sohbet içinde sorar. Ekler Blob'dan okunup modele uygun biçimde gönderilir:
görsel → image_url, PDF/video → file (data URL), DOCX/TXT/CSV → düz metin.
"""

import base64
import io
import logging
import re
import zipfile

from app import config
from app.services import storage
from app.services.llm_service import LLMError, chat_completion, smart_chat_completion

logger = logging.getLogger("ajansai.assistant")

SYSTEM_PROMPT = """Sen ajansAI'sın: her konuda sohbet edebilen, yardımsever ve zeki bir yapay zeka asistanı.
- Kullanıcı hangi dilde yazıyorsa o dilde yanıt ver (çoğunlukla Türkçe). Net ve doğal yaz; gereksiz giriş cümleleri kurma.
- Her türlü soruya yardımcı ol: genel bilgi, yazı, fikir, plan, analiz, kod, günlük konular. Pazarlama, sosyal medya ve reklam
  konularında özellikle uzmansın; bu konular açıldığında somut, kullanıma hazır öneriler ver (caption, hashtag, reklam metni, içerik planı).
- Meta reklam önerilerinde yerleşim yalnızca Instagram olsun (Facebook, Messenger, Audience Network, Threads önerme).
- Kullanıcı görsel, video veya belge eklerse onu dikkate alarak yanıt ver.
- Bilgi gerçekten eksikse kısa bir soru sor; yoksa makul varsayımla devam et.
- Önceki yanıtlarının sonundaki "[Sistem notu: ...]" satırlarını sistem ekler; o yanıtta yapılan web aramasını, üretilen
  görseli, dosyayı veya videoyu gösterir. Bunlara güven, önceki yanıtlarını gereksiz yere düzeltme ve kendin böyle not yazma.
- Yanıt uzunluğunu soruya göre ayarla: basit soruya kısa yanıt. Markdown kullanabilirsin; tablo kullanma (çoğu kullanıcı telefondan okur)."""

MAX_TEXT_CHARS = 30_000
# Maliyet sınırı: modele en fazla bu kadar geçmiş gider, yanıt bu uzunlukla sınırlı.
HISTORY_MESSAGES = 12
HISTORY_CHARS = 16_000
OLD_MESSAGE_CHARS = 4_000
MAX_REPLY_TOKENS = 4000  # Sonnet 5.5 düşünme token'ları da bu sınıra dahil
MAX_PDF_PAGES = 60


def _docx_text(data: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        xml = z.read("word/document.xml").decode("utf-8", "ignore")
    xml = re.sub(r"</w:p>", "\n", xml)
    return re.sub(r"<[^>]+>", "", xml)


def _pdf_text(data: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    return "\n".join((p.extract_text() or "") for p in reader.pages[:MAX_PDF_PAGES])


def document_text(data: bytes, ctype: str) -> str:
    """Belgeyi düz metne çevirir (PDF, DOCX, TXT, CSV, MD)."""
    try:
        if ctype == "application/pdf":
            return _pdf_text(data)
        if ctype.endswith("wordprocessingml.document"):
            return _docx_text(data)
    except Exception:
        return "(belge okunamadı)"
    return data.decode("utf-8", "ignore")


def _attachment_part(att: dict) -> tuple[dict, bool]:
    """(mesaj parçası, video_mu) döndürür."""
    url, ctype, name = att["url"], att["content_type"], att.get("name") or "dosya"
    kind = storage.kind_of(ctype)
    data = storage.fetch(url)
    if kind == "image":
        b64 = base64.b64encode(data).decode()
        return {"type": "image_url", "image_url": {"url": f"data:{ctype};base64,{b64}"}}, False
    if kind == "video" or ctype == "application/pdf":
        b64 = base64.b64encode(data).decode()
        return {"type": "file", "file": {"filename": name, "file_data": f"data:{ctype};base64,{b64}"}}, kind == "video"
    if ctype.endswith("wordprocessingml.document"):
        text = _docx_text(data)
    else:
        text = data.decode("utf-8", "ignore")
    return {"type": "text", "text": f"--- Ek belge: {name} ---\n{text[:MAX_TEXT_CHARS]}\n--- Belge sonu ---"}, False


def pdf_pages(data: bytes) -> int:
    """PDF sayfa sayısını kabaca sayar (her sayfa nesnesi bir '/Type /Page' içerir).

    Sıkıştırılmış nesne akışlarında sayfalar görünmeyebilir; o durumda dosya
    boyutundan tahmin edilir (~150 KB / sayfa).
    """
    counted = len(re.findall(rb"/Type\s*/Page(?![a-zA-Z])", data))
    return max(1, counted, -(-len(data) // 150_000))


def _trim_history(history: list[dict]) -> list[dict]:
    """Son mesajlar korunur; eski mesajlar kısaltılır, toplam karakter bütçesi aşılmaz."""
    recent = history[-HISTORY_MESSAGES:]
    kept: list[dict] = []
    budget = HISTORY_CHARS
    for i, msg in enumerate(reversed(recent)):
        content = msg.get("content") or ""
        if i > 0:
            content = content[:OLD_MESSAGE_CHARS]
            if len(content) > budget:
                break
            budget -= len(content)
        kept.append({**msg, "content": content})
    kept.reverse()
    # Model geçmişin kullanıcı mesajıyla başlamasını bekler.
    while len(kept) > 1 and kept[0]["role"] != "user":
        kept.pop(0)
    return kept


def reply(history: list[dict], force_image: bool = False, force_search: bool = False, force_file: bool = False,
          video_enabled: bool = False):
    """Sohbet geçmişine yanıt verir.

    (metin, model, görsel istemi, kaynaklar, dosya isteği, model mesajları, video isteği) döndürür.

    Geçmişteki eski eklerin yalnızca adı gönderilir; dosyaların kendisi son mesajla gider.
    """
    from app.services import free_tier  # döngüsel içe aktarmayı önlemek için burada

    history = _trim_history(history)
    from app.services import web_search

    system = SYSTEM_PROMPT + web_search.today_line() + free_tier.IMAGE_TOOL_NOTE + free_tier.MEDIA_NOTE + (free_tier.FORCE_IMAGE_NOTE if force_image else "")
    from app.services import documents

    if web_search.enabled():
        system += web_search.SEARCH_NOTE
    system += documents.FILE_NOTE + (documents.FORCE_FILE_NOTE if force_file else "")
    system += free_tier.VIDEO_TOOL_NOTE
    if not video_enabled:
        system += " Kullanıcının paketinde video yok; video için paketini yükseltebileceğini de belirt."
    messages = [{"role": "system", "content": system}]
    has_video = False
    last = len(history) - 1
    for i, msg in enumerate(history):
        attachments = msg.get("attachments") or []
        if msg["role"] == "assistant" or not attachments:
            messages.append({"role": msg["role"], "content": msg["content"] + (msg.get("_note") or "")})
            continue
        if i != last:
            names = ", ".join(a.get("name") or "dosya" for a in attachments)
            messages.append({"role": "user", "content": f"{msg['content']}\n[Bu mesajda eklenen dosyalar: {names}]"})
            continue
        parts = [{"type": "text", "text": msg["content"] or "Bu materyale bak ve üzerinden örnekler üret."}]
        for att in attachments:
            part, is_video = _attachment_part(att)
            parts.append(part)
            has_video = has_video or is_video
        messages.append({"role": "user", "content": parts})

    if force_search and web_search.enabled():
        text, model = f"[[ARA: {(history[-1].get('content') or '')[:300]}]]", "web"
    elif has_video:
        model = config.CHAT_VIDEO_MODEL
        text = chat_completion(model, messages, max_tokens=MAX_REPLY_TOKENS)
    else:
        model = config.CHAT_MODEL
        try:
            text = chat_completion(model, messages, max_tokens=MAX_REPLY_TOKENS)
        except LLMError as e:
            # Sonnet olmazsa Haiku, o da olmazsa ücretsiz zincir (yalnızca metin mesajlarında işe yarar)
            logger.warning("%s olmadı, yedeğe geçiliyor: %s", model, e)
            text, model = smart_chat_completion(messages, max_tokens=MAX_REPLY_TOKENS, paid=True, skip=(model,))
    text, video_request = free_tier.split_video_request(text)
    text, image_prompt, sources, file_request = free_tier.finish_reply(text, messages, paid=True)
    return text, (model if not sources else "web"), image_prompt, sources, file_request, messages, video_request


DESCRIBE_PROMPT = {
    "video": "Bu örnek materyale bakarak, aynı tarzda yeni bir dikey sosyal medya videosu üretmek için tek paragraflık, "
    "Türkçe bir video konsepti yaz: sahne, hareket, kamera açısı, ışık ve atmosfer. Sadece konsepti yaz.",
    "image": "Bu örnek materyale bakarak, aynı tarzda yeni bir sosyal medya görseli üretmek için tek paragraflık, Türkçe bir "
    "görsel konsepti yaz: kompozisyon, ürün, arka plan, ışık, renkler ve stil. Sadece konsepti yaz.",
}


def describe_for_generation(att: dict, target: str, note: str = "") -> str:
    """Örnek görsel/videoyu inceleyip yeni üretim için konsept metni yazar."""
    part, is_video = _attachment_part(att)
    text = DESCRIBE_PROMPT[target] + (f"\nKullanıcının notu: {note}" if note else "")
    messages = [{"role": "user", "content": [{"type": "text", "text": text}, part]}]
    model = config.CHAT_VIDEO_MODEL if is_video else config.CHAT_MODEL
    return chat_completion(model, messages, max_tokens=600).strip()
