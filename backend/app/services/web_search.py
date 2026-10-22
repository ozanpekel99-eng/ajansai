"""Sohbette canlı web araması.

Model güncel bilgiye ihtiyaç duyduğunda yanıtı yerine [[ARA: sorgu]] satırı yazar
(veya kullanıcı + menüsünden "Web'de ara"yı seçer). Arama şu sırayla yapılır:

1. Tavily (TAVILY_API_KEY varsa): sonuçlar alınır, model bu sonuçlara dayanarak yanıtlar.
2. Groq yerleşik web araması (gpt-oss + browser_search, GROQ_API_KEY ile): arama ve
   yanıt tek istekte.

Yanıtla birlikte kaynak bağlantıları döndürülür.
"""

import logging
import re
from datetime import datetime, timedelta, timezone

import requests

from app import config
from app.services.llm_service import LLMError, free_chat_completion

logger = logging.getLogger("ajansai.search")

SEARCH_TAG = re.compile(r"\[\[\s*ARA\s*:\s*(.+?)\]\]", re.IGNORECASE | re.DOTALL)
CITATION = re.compile(r"【[^】]*】")
MONTHS = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
DAYS = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]


def today_line() -> str:
    """Modelin bugünün tarihini bilmesi için sistem mesajına eklenir (Türkiye saati)."""
    now = datetime.now(timezone(timedelta(hours=3)))
    return f"\n- Bugünün tarihi: {now.day} {MONTHS[now.month - 1]} {now.year}, {DAYS[now.weekday()]} (Türkiye saati {now:%H:%M})."


SEARCH_NOTE = (
    "\n- İnternette arama yapabilirsin. Soru güncel veya canlı bilgi gerektiriyorsa (haberler, son gelişmeler, döviz/altın/"
    "borsa, fiyatlar, hava durumu, maç sonuçları, seçimler, bir kişinin/şirketin güncel durumu, yeni çıkan ürünler, "
    "belirli bir web sitesinin içeriği ya da bilgi kesim tarihinden sonraki her şey), yanıt verme; yalnızca tek satır "
    "yaz: [[ARA: <kısa arama sorgusu>]]. Sistem aramayı yapıp sonuçları sana verecek. Genel bilgi, yazı, fikir veya "
    "hesap için arama yapma."
)


def enabled() -> bool:
    return bool(config.TAVILY_API_KEY or config.GROQ_API_KEY)


def split_search_request(text: str) -> str | None:
    m = SEARCH_TAG.search(text or "")
    return m.group(1).strip()[:300] if m else None


def _text_messages(messages: list[dict]) -> list[dict]:
    """Görsel/dosya parçaları olan mesajları düz metne indirger."""
    out = []
    for m in messages:
        c = m["content"]
        if isinstance(c, list):
            c = "\n".join(p.get("text", "") for p in c if p.get("type") == "text")
        out.append({"role": m["role"], "content": c})
    return out


def _clean(text: str) -> str:
    text = CITATION.sub("", text or "")
    text = SEARCH_TAG.sub("", text)
    return re.sub(r"[ \t]+\n", "\n", text).strip()


# ---------------- Tavily ----------------

def _tavily(query: str) -> list[dict]:
    r = requests.post(
        "https://api.tavily.com/search",
        headers={"Authorization": f"Bearer {config.TAVILY_API_KEY}"},
        json={"query": query, "max_results": 6, "search_depth": "basic", "include_answer": False},
        timeout=20,
    )
    if r.status_code != 200:
        raise LLMError(f"Tavily {r.status_code}: {r.text[:200]}")
    return [
        {"title": x.get("title") or x.get("url"), "url": x.get("url"), "content": (x.get("content") or "")[:1200]}
        for x in r.json().get("results", [])
        if x.get("url")
    ]


def _answer_from_results(messages: list[dict], query: str, results: list[dict]) -> str:
    context = "\n\n".join(f"[{i + 1}] {r['title']} ({r['url']})\n{r['content']}" for i, r in enumerate(results))
    msgs = _text_messages(messages) + [
        {
            "role": "system",
            "content": f"'{query}' için web arama sonuçları:\n\n{context}\n\n"
            "Kullanıcının son sorusunu bu sonuçlara dayanarak, kullanıcının dilinde yanıtla. Bilgiyi aldığın sonucu [1] gibi "
            "numarayla belirt. Sonuçlarda olmayan şeyi uydurma; emin değilsen söyle.",
        }
    ]
    text, _ = free_chat_completion(msgs, max_tokens=1500)
    return text


# ---------------- Groq yerleşik web araması ----------------

def _groq_search(messages: list[dict], query: str) -> tuple[str, list[dict]]:
    msgs = _text_messages(messages) + [
        {
            "role": "system",
            "content": f"Web'de şunu ara ve kullanıcının son sorusunu güncel bilgilerle, kullanıcının dilinde yanıtla: {query}",
        }
    ]
    r = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {config.GROQ_API_KEY}", "Content-Type": "application/json"},
        json={
            "model": config.SEARCH_MODEL,
            "messages": msgs,
            "tools": [{"type": "browser_search"}],
            "tool_choice": "required",
            "reasoning_effort": "low",
            "max_completion_tokens": 2000,
        },
        timeout=60,
    )
    if r.status_code != 200:
        raise LLMError(f"Groq arama {r.status_code}: {r.text[:300]}")
    msg = (r.json().get("choices") or [{}])[0].get("message") or {}
    text = msg.get("content") or ""
    if not text.strip():
        raise LLMError("Groq arama boş yanıt")
    sources = []
    for tool in msg.get("executed_tools") or []:
        results = (tool.get("search_results") or {}).get("results") or []
        for x in results:
            if x.get("url"):
                sources.append({"title": x.get("title") or x["url"], "url": x["url"]})
    return text, sources


def answer(messages: list[dict], query: str) -> tuple[str, list[dict]]:
    """Web'de arayıp yanıtlar. (metin, [{"title","url"}]) döndürür."""
    errors = []
    if config.TAVILY_API_KEY:
        try:
            results = _tavily(query)
            if results:
                text = _answer_from_results(messages, query, results)
                return _clean(text), [{"title": x["title"], "url": x["url"]} for x in results]
        except (LLMError, requests.RequestException) as e:
            errors.append(str(e))
            logger.warning("Tavily araması olmadı: %s", e)
    if config.GROQ_API_KEY:
        try:
            text, sources = _groq_search(messages, query)
            seen, unique = set(), []
            for s in sources:
                if s["url"] not in seen:
                    seen.add(s["url"])
                    unique.append(s)
            return _clean(text), unique[:8]
        except (LLMError, requests.RequestException) as e:
            errors.append(str(e))
            logger.warning("Groq araması olmadı: %s", e)
    raise LLMError("Web araması yapılamadı: " + "; ".join(errors))
