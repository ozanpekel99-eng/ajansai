"""ajansAI sohbet asistanı: tek metin kutusu + ekler (görsel, video, belge).

Kullanıcıdan form doldurması istenmez; işletme bilgisi gerekiyorsa asistan
sohbet içinde sorar. Ekler Blob'dan okunup modele uygun biçimde gönderilir:
görsel → image_url, PDF/video → file (data URL), DOCX/TXT/CSV → düz metin.
"""

import base64
import io
import re
import zipfile

from app import config
from app.services import storage
from app.services.llm_service import chat_completion

SYSTEM_PROMPT = """Sen ajansAI'sın: Türkiye'deki küçük ve orta ölçekli işletmeler için sosyal medya ve reklam asistanı.
- Her zaman Türkçe, samimi ve net yaz. Gereksiz giriş cümleleri kurma, doğrudan işe yarayan içerik ver.
- İçerik fikri isteyenlere her fikir için: başlık, format (Reels, gönderi, carousel, hikâye), sahne/konsept, paylaşıma hazır caption ve 5-10 hashtag ver.
- Instagram önceliklidir. Meta reklam önerilerinde yerleşim yalnızca Instagram olsun (Facebook, Messenger, Audience Network, Threads önerme).
- Kullanıcı görsel, video veya belge eklerse önce ondan ne anladığını tek cümleyle söyle, sonra o materyale dayanarak örnekler üret (benzer içerikler, caption, kurgu, reklam metni).
- İşletme adı, sektör veya hedef kitle gibi bir bilgi gerçekten eksikse kısa bir soru sor; yoksa makul varsayımla devam et ve varsayımını belirt.
- Görsel veya video üretilmesi uygun olduğunda, kullanıcı doğrudan kullanabilsin diye kısa bir "Görsel/Video konsepti:" satırı ekle.
- Markdown kullan: başlıklar, kalın yazı ve listeler serbest."""

MAX_TEXT_CHARS = 30_000
# Maliyet sınırı: modele en fazla bu kadar geçmiş gider, yanıt bu uzunlukla sınırlı.
HISTORY_MESSAGES = 12
HISTORY_CHARS = 16_000
OLD_MESSAGE_CHARS = 4_000
MAX_REPLY_TOKENS = 1800
MAX_PDF_PAGES = 60


def _docx_text(data: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        xml = z.read("word/document.xml").decode("utf-8", "ignore")
    xml = re.sub(r"</w:p>", "\n", xml)
    return re.sub(r"<[^>]+>", "", xml)


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


def reply(history: list[dict]) -> tuple[str, str]:
    """Sohbet geçmişine yanıt verir. (metin, kullanılan_model) döndürür.

    Geçmişteki eski eklerin yalnızca adı gönderilir; dosyaların kendisi son mesajla gider.
    """
    history = _trim_history(history)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    has_video = False
    last = len(history) - 1
    for i, msg in enumerate(history):
        attachments = msg.get("attachments") or []
        if msg["role"] == "assistant" or not attachments:
            messages.append({"role": msg["role"], "content": msg["content"]})
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

    model = config.CHAT_VIDEO_MODEL if has_video else config.CHAT_MODEL
    return chat_completion(model, messages, max_tokens=MAX_REPLY_TOKENS), model


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
