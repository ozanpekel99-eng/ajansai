import json

from app.services.llm_service import complete

SYSTEM_PROMPT = """Sen KOBİ'ler için sosyal medya içerik stratejisti olarak çalışan bir yapay zekasın.
Sana verilen işletme bilgilerine göre platform bazlı, uygulanabilir ve yaratıcı içerik fikirleri üretirsin.
Yanıtını SADECE aşağıdaki JSON şemasına uygun, başka hiçbir metin eklemeden döndür:

{
  "ideas": [
    {
      "platform": "instagram | tiktok | facebook",
      "format": "reels | görsel | carousel | story",
      "title": "kısa başlık",
      "concept": "görsel/video konseptinin 2-3 cümlelik açıklaması",
      "caption": "paylaşım için hazır caption metni",
      "hashtags": ["#ornek1", "#ornek2"]
    }
  ]
}
"""


def _extract_json(text: str) -> dict:
    """Model JSON'u kod bloğu içinde ya da önüne/arkasına metin ekleyerek
    döndürebilir; ilk '{' ile son '}' arasını alıp ayrıştırıyoruz."""
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("Yanıtta JSON bulunamadı")
    return json.loads(text[start : end + 1])


def generate_content_ideas(
    business_name: str,
    sector: str,
    target_audience: str,
    tone: str,
    topic: str,
    idea_count: int = 4,
) -> dict:
    """Verilen işletme bilgilerine göre içerik fikirleri üretir."""

    user_prompt = f"""İşletme adı: {business_name}
Sektör: {sector}
Hedef kitle: {target_audience}
Marka tonu: {tone}
Bu içerik neyle ilgili olmalı: {topic}

Lütfen {idea_count} adet farklı platform ve formatta içerik fikri üret."""

    raw_text, provider = complete(SYSTEM_PROMPT, user_prompt, max_tokens=2000)

    try:
        data = _extract_json(raw_text)
    except (ValueError, json.JSONDecodeError):
        return {"ideas": [], "error": "Yanıt ayrıştırılamadı", "provider": provider}

    ideas = data.get("ideas") if isinstance(data, dict) else None
    if not isinstance(ideas, list):
        return {"ideas": [], "error": "Yanıt beklenen biçimde değil", "provider": provider}

    return {"ideas": ideas, "provider": provider}
