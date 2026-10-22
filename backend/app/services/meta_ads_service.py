import base64
import json
import logging
import time as _time
from urllib.parse import urlencode

import requests

from app import config

# v20.0 24 Eylül 2026'da kapandı; güncel sürüm (Temmuz 2026).
META_API_VERSION = config.META_API_VERSION
META_BASE_URL = f"https://graph.facebook.com/{META_API_VERSION}"


logger = logging.getLogger("ajansai.meta")


class MetaError(Exception):
    pass


def get_oauth_url(redirect_uri: str, state: str) -> str:
    """Kullanıcıyı Meta'nın izin ekranına yönlendirecek URL'yi üretir.

    `state`, CSRF'e karşı imzalı ve kısa ömürlü bir değerdir; callback'te
    doğrulanır. ads_management izni Meta App Review onayı gerektirir.
    """
    params = {"client_id": config.META_APP_ID, "redirect_uri": redirect_uri, "state": state}
    if config.META_CONFIG_ID:
        # Facebook Login for Business: izinler Meta panelindeki yapılandırmadan gelir.
        params["config_id"] = config.META_CONFIG_ID
        params["response_type"] = "code"
        params["override_default_response_type"] = "true"
    else:
        params["scope"] = "ads_management,ads_read,business_management,pages_show_list,pages_read_engagement,pages_manage_ads,instagram_basic"
    query = urlencode(params)
    return f"https://www.facebook.com/{META_API_VERSION}/dialog/oauth?{query}"


def _meta_error(response) -> str:
    """Meta'nın hata mesajını (token/secret içermeden) döndürür."""
    try:
        err = response.json().get("error") or {}
        return f"{response.status_code} {err.get('type', '')} {err.get('code', '')}: {err.get('message', '')}"
    except ValueError:
        return f"{response.status_code}: {response.text[:200]}"


def exchange_code_for_token(code: str, redirect_uri: str) -> str:
    """OAuth kodunu uzun ömürlü erişim token'ına çevirir."""
    secret = (config.META_APP_SECRET or "").strip()
    app_id = (config.META_APP_ID or "").strip()
    try:
        short = requests.get(
            f"{META_BASE_URL}/oauth/access_token",
            params={"client_id": app_id, "client_secret": secret, "redirect_uri": redirect_uri, "code": code},
            timeout=30,
        )
        if short.status_code != 200:
            logger.error("Meta kod değişimi başarısız: %s", _meta_error(short))
            raise MetaError("Meta hesabı bağlanamadı: " + _meta_error(short).split(": ", 1)[-1])
        short_token = short.json()["access_token"]

        # Kısa ömürlü (1-2 saat) token'ı ~60 günlük token'a çeviriyoruz.
        long = requests.get(
            f"{META_BASE_URL}/oauth/access_token",
            params={
                "grant_type": "fb_exchange_token",
                "client_id": app_id,
                "client_secret": secret,
                "fb_exchange_token": short_token,
            },
            timeout=30,
        )
        if long.status_code != 200:
            # Uzun ömürlüye çevrilemezse kısa ömürlü token ile devam edilir.
            logger.warning("Uzun ömürlü token alınamadı: %s", _meta_error(long))
            return short_token
        return long.json()["access_token"]
    except (requests.RequestException, KeyError, ValueError) as e:
        logger.error("Meta token isteği hatası: %s", type(e).__name__)
        raise MetaError("Meta hesabı bağlanamadı.") from e


_ACC_CACHE: dict[str, tuple[float, list[dict]]] = {}


def list_ad_accounts(access_token: str) -> list[dict]:
    hit = _ACC_CACHE.get(access_token[-24:])
    if hit and _time.time() - hit[0] < 120:
        return hit[1]
    rows = _list_ad_accounts(access_token)
    _ACC_CACHE[access_token[-24:]] = (_time.time(), rows)
    return rows


def _list_ad_accounts(access_token: str) -> list[dict]:
    try:
        response = requests.get(
            f"{META_BASE_URL}/me/adaccounts",
            params={"fields": "account_id,name,currency,account_status,balance", "access_token": access_token, "limit": 200},
            timeout=30,
        )
        response.raise_for_status()
        rows = [describe_account(a) for a in response.json().get("data", [])]
        # Önce aktif, sonra kullanılabilir (bakiyeli vb.), en sonda kapalı hesaplar
        rows.sort(key=lambda a: (a["account_status"] != 1, not a["usable"], a.get("name", "").lower()))
        return rows
    except (requests.RequestException, ValueError) as e:
        raise MetaError("Reklam hesapları alınamadı.") from e


def create_campaign_draft(
    ad_account_id: str,
    access_token: str,
    campaign_name: str,
    objective: str = "OUTCOME_ENGAGEMENT",
) -> dict:
    """PAUSED durumda bir kampanya taslağı oluşturur.

    Kampanya otomatik yayına alınmaz; kullanıcı Meta Ads Manager'da son onayı
    kendisi verir. Bu, yanlışlıkla bütçe harcanmasını önler.
    """
    ad_account_id = ad_account_id.removeprefix("act_")
    try:
        response = requests.post(
            f"{META_BASE_URL}/act_{ad_account_id}/campaigns",
            data={
                "name": campaign_name,
                "objective": objective,
                "status": "PAUSED",
                "special_ad_categories": "[]",
                # Kampanya bütçesi kullanılmadığında yeni API sürümleri bu alanı zorunlu tutuyor.
                "is_adset_budget_sharing_enabled": "false",
                "access_token": access_token,
            },
            timeout=30,
        )
    except requests.RequestException as e:
        raise MetaError("Meta'ya ulaşılamadı.") from e

    data = response.json() if response.content else {}
    if response.status_code != 200:
        message = (data.get("error") or {}).get("message", "Kampanya oluşturulamadı.")
        raise MetaError(message)
    return data


# ---------------- Uçtan uca reklam oluşturma ----------------
# Akış: kampanya → reklam seti (yalnızca Instagram yerleşimleri) → medya
# yükleme → kreatif → reklam. Hepsi DURAKLATILMIŞ oluşturulur; kullanıcı
# "Yayına al" deyince aktifleşir. Herhangi bir adım hata verirse oluşturulan
# kampanya silinir, hesapta yarım kayıt kalmaz.


INSTAGRAM_POSITIONS = ["stream", "story", "reels", "explore"]

# Arayüzdeki yerleşim seçenekleri → Meta yerleşimleri
PLACEMENTS = {
    "instagram_feed": ("instagram", "stream"),
    "instagram_story": ("instagram", "story"),
    "instagram_reels": ("instagram", "reels"),
    "instagram_explore": ("instagram", "explore"),
    "facebook_feed": ("facebook", "feed"),
    "facebook_story": ("facebook", "story"),
    "facebook_reels": ("facebook", "facebook_reels"),
}
DEFAULT_PLACEMENTS = ["instagram_feed", "instagram_story", "instagram_reels", "instagram_explore"]
VERTICAL = {"story", "reels", "facebook_reels"}  # 9:16 dikey görsel kullanılan yerleşimler

OBJECTIVES = {
    # amaç: (kampanya objective, reklam seti optimization_goal, destination_type)
    "profile": ("OUTCOME_TRAFFIC", "VISIT_INSTAGRAM_PROFILE", "INSTAGRAM_PROFILE"),
    "traffic": ("OUTCOME_TRAFFIC", "LINK_CLICKS", "WEBSITE"),
    "whatsapp": ("OUTCOME_ENGAGEMENT", "CONVERSATIONS", "WHATSAPP"),
    "instagram_dm": ("OUTCOME_ENGAGEMENT", "CONVERSATIONS", "INSTAGRAM_DIRECT"),
    "awareness": ("OUTCOME_AWARENESS", "REACH", None),
}


def _graph(method: str, path: str, token: str, **data) -> dict:
    params = {"access_token": token, "locale": "tr_TR"}
    try:
        if method == "GET":
            response = requests.get(f"{META_BASE_URL}/{path}", params={**params, **data}, timeout=60)
        elif method == "DELETE":
            response = requests.delete(f"{META_BASE_URL}/{path}", params=params, timeout=60)
        else:
            body = {k: (json.dumps(v) if isinstance(v, (dict, list)) else v) for k, v in data.items()}
            response = requests.post(f"{META_BASE_URL}/{path}", params=params, data=body, timeout=120)
    except requests.RequestException as e:
        raise MetaError("Meta'ya ulaşılamadı, tekrar dene.") from e
    try:
        payload = response.json()
    except ValueError:
        payload = {}
    if response.status_code != 200 or "error" in payload:
        err = payload.get("error") or {}
        logger.error("Meta %s %s: %s", method, path.split("?")[0], _meta_error(response))
        message = err.get("error_user_msg") or err.get("message") or "Meta isteği başarısız oldu."
        if err.get("code") in (4, 17, 32, 613) or "request limit" in message.lower():
            message = "Meta kısa süreliğine istek sınırına ulaştı; birkaç dakika sonra tekrar dene."
        raise MetaError(message)
    return payload


# Meta reklam hesabı durum kodları → kullanıcıya açıklama; usable: reklam oluşturulabilir mi
ACCOUNT_STATUS = {
    1: ("Aktif", True),
    3: ("Ödenmemiş bakiye var: Meta, bakiye ödenene kadar reklamları yayınlamaz", True),
    9: ("Ödeme ek süresinde: bakiyeyi kısa sürede öde", True),
    7: ("Meta incelemesinde", True),
    8: ("Ödeme bekleniyor", True),
    2: ("Devre dışı (Meta tarafından kapatıldı)", False),
    100: ("Kapanıyor", False),
    101: ("Kapalı", False),
}


# Meta tutarları kuruş cinsinden döndürür; bu para birimlerinde küsurat yoktur
ZERO_DECIMAL = {"JPY", "KRW", "CLP", "COP", "HUF", "ISK", "TWD", "VND", "IDR", "PYG", "CRC"}


def _money(value, currency: str | None) -> float:
    try:
        n = int(value or 0)
    except (TypeError, ValueError):
        return 0.0
    return float(n) if (currency or "").upper() in ZERO_DECIMAL else n / 100


def describe_account(a: dict) -> dict:
    label, usable = ACCOUNT_STATUS.get(a.get("account_status"), ("Durum bilinmiyor", True))
    a = {**a, "balance_due": _money(a.pop("balance", 0), a.get("currency"))}
    return {**a, "status_label": label, "usable": usable,
            "billing_url": f"https://business.facebook.com/billing_hub/payment_activity/?asset_id={a.get('account_id')}"}


def _page_row(p: dict, source: str) -> dict:
    ig = p.get("instagram_business_account") or p.get("connected_instagram_account") or {}
    return {"id": p["id"], "name": p.get("name", ""), "instagram_id": ig.get("id"),
            "instagram_username": ig.get("username"), "source": source}


PAGE_FIELDS = "id,name,instagram_business_account{id,username},connected_instagram_account{id,username}"


def _all(path: str, token: str, **params) -> list[dict]:
    """Sayfalı Graph listesini (en fazla 5 sayfa) toplar."""
    out: list[dict] = []
    params.setdefault("limit", 100)
    after = None
    for _ in range(5):
        if after:
            params["after"] = after
        data = _graph("GET", path, token, **params)
        out.extend(data.get("data", []))
        after = ((data.get("paging") or {}).get("cursors") or {}).get("after")
        if not after or not (data.get("paging") or {}).get("next"):
            break
    return out


_PAGES_CACHE: dict[tuple, tuple[float, list[dict]]] = {}
PAGES_TTL = 180  # sn; Meta'nın uygulama başı istek sınırını korumak için


def list_pages(token: str, ad_account_id: str | None = None, fresh: bool = False) -> list[dict]:
    """Kullanıcının erişebildiği tüm Facebook sayfaları ve her birine bağlı Instagram hesabı.

    Kaynaklar (en fazla 3 istek): reklam hesabının tanıtabildiği sayfalar, kullanıcının yönettiği
    sayfalar ve işletme portföylerinin (Business Manager) sahip olduğu / erişebildiği sayfalar.
    Sonuç kısa süre önbellekte tutulur.
    """
    key = (token[-24:], ad_account_id or "")
    hit = _PAGES_CACHE.get(key)
    if hit and not fresh and _time.time() - hit[0] < PAGES_TTL:
        return hit[1]

    found: dict[str, dict] = {}
    biz_ig: dict[str, str] = {}

    def add(rows, source):
        for p in rows or []:
            row = _page_row(p, source)
            cur = found.get(p["id"])
            if not cur:
                found[p["id"]] = row
            elif not cur.get("instagram_id") and row.get("instagram_id"):
                cur.update(instagram_id=row["instagram_id"], instagram_username=row["instagram_username"])

    errors = []
    if ad_account_id:
        try:
            add(_graph("GET", f"act_{ad_account_id.removeprefix('act_')}/promote_pages", token, fields=PAGE_FIELDS, limit=100).get("data"), "ad_account")
        except MetaError as e:
            errors.append(e)
    try:
        add(_graph("GET", "me/accounts", token, fields=PAGE_FIELDS, limit=100).get("data"), "user")
    except MetaError as e:
        errors.append(e)
    try:
        sub = f"{{{PAGE_FIELDS}}}"
        biz = _graph("GET", "me/businesses", token, limit=25,
                     fields=f"id,owned_pages.limit(100){sub},client_pages.limit(100){sub},"
                            "owned_instagram_accounts.limit(100){id,username},instagram_accounts.limit(100){id,username}").get("data", [])
        for b in biz:
            add((b.get("owned_pages") or {}).get("data"), "business")
            add((b.get("client_pages") or {}).get("data"), "business")
            for edge in ("owned_instagram_accounts", "instagram_accounts"):
                for ig in (b.get(edge) or {}).get("data", []):
                    if ig.get("id"):
                        biz_ig.setdefault(ig["id"], ig.get("username") or "")
    except MetaError:
        pass
    if not found and errors:
        raise errors[0]
    _match_instagram(found, biz_ig)
    rows = sorted(found.values(), key=lambda r: (r["source"] != "ad_account", not r.get("instagram_id"), r["name"].lower()))
    _PAGES_CACHE[key] = (_time.time(), rows)
    _BIZ_IG[token[-24:]] = biz_ig
    return rows


_BIZ_IG: dict[str, dict[str, str]] = {}

_TR = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")


def _norm(t: str) -> str:
    return "".join(ch for ch in (t or "").translate(_TR).lower() if ch.isalnum())


def _match_instagram(pages: dict[str, dict], biz_ig: dict[str, str]) -> None:
    """Meta sayfa–Instagram bağını vermediğinde, işletmedeki Instagram hesaplarını sayfa adına göre eşler.

    Yalnızca tek ve belirgin eşleşme kabul edilir; böyle satırlar instagram_guess=True ile işaretlenir.
    """
    used = {p["instagram_id"] for p in pages.values() if p.get("instagram_id")}
    free = {i: u for i, u in biz_ig.items() if i not in used and u}
    for p in pages.values():
        if p.get("instagram_id") or not free:
            continue
        full = _norm(p["name"])
        words = [w for w in (_norm(x) for x in p["name"].split()) if len(w) >= 4]
        hits = [i for i, u in free.items() if _norm(u) == full or (full and full in _norm(u))]
        if not hits:
            scored = [(sum(w in _norm(u) for w in words), i) for i, u in free.items()]
            best = max((sc for sc, _ in scored), default=0)
            need = 2 if len(words) >= 2 else 1
            hits = [i for sc, i in scored if sc == best and sc >= need]
        if len(hits) == 1:
            i = hits[0]
            p.update(instagram_id=i, instagram_username=free.pop(i), instagram_guess=True)
_IG_CACHE: dict[tuple, tuple[float, list[dict]]] = {}


def page_instagram(token: str, page_id: str) -> dict | None:
    """Tek bir sayfanın bağlı Instagram hesabı (sayfa jetonuyla; liste bulamazsa seçimde sorulur)."""
    try:
        p = _graph("GET", page_id, token, fields="access_token,instagram_business_account{id,username},connected_instagram_account{id,username}")
    except MetaError:
        return None
    ig = p.get("instagram_business_account") or p.get("connected_instagram_account")
    if not ig and p.get("access_token"):
        try:
            igs = _graph("GET", f"{page_id}/instagram_accounts", p["access_token"], fields="id,username").get("data", [])
            ig = igs[0] if igs else None
        except MetaError:
            ig = None
    if ig and ig.get("id"):
        for _, rows in _PAGES_CACHE.values():
            for r in rows:
                if r["id"] == page_id:
                    r.update(instagram_id=ig["id"], instagram_username=ig.get("username"))
        return {"id": ig["id"], "username": ig.get("username") or ""}
    return None


def granted_permissions(token: str) -> list[str]:
    try:
        return [p["permission"] for p in _graph("GET", "me/permissions", token).get("data", []) if p.get("status") == "granted"]
    except MetaError:
        return []


def list_instagram_accounts(ad_account_id: str, token: str) -> list[dict]:
    """Reklamda kullanılabilecek Instagram hesapları: reklam hesabına atananlar +
    kullanıcının sayfalarına bağlı işletme hesapları."""
    ckey = (token[-24:], ad_account_id)
    hit = _IG_CACHE.get(ckey)
    if hit and _time.time() - hit[0] < PAGES_TTL:
        return hit[1]
    found: dict[str, dict] = {}
    act = ad_account_id.removeprefix("act_")
    try:
        data = _graph("GET", f"act_{act}/instagram_accounts", token, fields="id,username", limit=100)
        for a in data.get("data", []):
            found[a["id"]] = {"id": a["id"], "username": a.get("username", ""), "page_id": None}
    except MetaError:
        pass
    try:
        for p in list_pages(token, ad_account_id):
            if p.get("instagram_id"):
                row = found.setdefault(p["instagram_id"], {"id": p["instagram_id"], "username": p.get("instagram_username") or "", "page_id": None})
                row["page_id"] = row["page_id"] or p["id"]
                row["username"] = row["username"] or p.get("instagram_username") or ""
    except MetaError:
        pass
    # İşletme portföyündeki Instagram hesapları (sayfa eşleşmesi arayüzde ada göre yapılır)
    for ig_id, username in _BIZ_IG.get(token[-24:], {}).items():
        found.setdefault(ig_id, {"id": ig_id, "username": username, "page_id": None})
    out = list(found.values())
    _IG_CACHE[ckey] = (_time.time(), out)
    return out


def recent_posts(token: str, page_id: str, instagram_user_id: str | None, limit: int = 18) -> list[dict]:
    """Reklamda kullanılabilecek son gönderiler: seçili Instagram hesabı ve Facebook sayfası."""
    out: list[dict] = []
    if instagram_user_id:
        try:
            data = _graph(
                "GET", f"{instagram_user_id}/media", token, limit=limit,
                fields="id,caption,media_type,media_product_type,media_url,thumbnail_url,permalink,timestamp,"
                       "children{media_type,media_url,thumbnail_url}",
            ).get("data", [])
            for m in data:
                kids = (m.get("children") or {}).get("data") or []
                thumb = m.get("thumbnail_url") or m.get("media_url") or (
                    (kids[0].get("thumbnail_url") or kids[0].get("media_url")) if kids else None)
                kind = ("carousel" if m.get("media_type") == "CAROUSEL_ALBUM" else
                        "reel" if m.get("media_product_type") == "REELS" else (m.get("media_type") or "IMAGE").lower())
                out.append({"platform": "instagram", "id": m["id"], "caption": (m.get("caption") or "")[:300],
                            "type": kind, "thumbnail": thumb, "permalink": m.get("permalink"),
                            "time": m.get("timestamp"), "count": len(kids) or 1})
        except MetaError as e:
            logger.info("Instagram gönderileri alınamadı: %s", e)
    try:
        page_token = _graph("GET", page_id, token, fields="access_token").get("access_token") or token
        data = _graph("GET", f"{page_id}/published_posts", page_token, limit=limit,
                      fields="id,message,full_picture,created_time,permalink_url,"
                             "attachments{media_type,subattachments}").get("data", [])
        for post in data:
            if not post.get("full_picture"):
                continue  # yalnızca görselli/videolu gönderiler
            att = ((post.get("attachments") or {}).get("data") or [{}])[0]
            subs = (att.get("subattachments") or {}).get("data") or []
            kind = "carousel" if len(subs) > 1 else ("video" if "video" in (att.get("media_type") or "") else "image")
            out.append({"platform": "facebook", "id": post["id"], "caption": (post.get("message") or "")[:300],
                        "type": kind, "thumbnail": post.get("full_picture"), "permalink": post.get("permalink_url"),
                        "time": post.get("created_time"), "count": len(subs) or 1})
    except MetaError as e:
        logger.info("Facebook gönderileri alınamadı: %s", e)
    out.sort(key=lambda x: x.get("time") or "", reverse=True)
    return out


def search_locations(query: str, token: str) -> list[dict]:
    data = _graph(
        "GET",
        "search",
        token,
        type="adgeolocation",
        q=query,
        location_types=json.dumps(["country", "region", "city"]),
        limit=10,
    )
    return [
        {
            "key": loc["key"],
            "name": loc["name"],
            "type": loc["type"],
            "country_code": loc.get("country_code"),
            "region": loc.get("region"),
        }
        for loc in data.get("data", [])
    ]


def _positions(placements: list[str] | None) -> dict:
    platforms, ig, fb = [], [], []
    for key in placements or DEFAULT_PLACEMENTS:
        if key not in PLACEMENTS:
            continue
        platform, position = PLACEMENTS[key]
        if platform not in platforms:
            platforms.append(platform)
        (ig if platform == "instagram" else fb).append(position)
    out = {"publisher_platforms": platforms or ["instagram"]}
    if ig:
        out["instagram_positions"] = ig
    if fb:
        out["facebook_positions"] = fb
    if not platforms:
        out["instagram_positions"] = INSTAGRAM_POSITIONS
    return out


def _targeting(locations: list[dict], age_min: int, age_max: int, gender: str, placements: list[str] | None = None) -> dict:
    geo: dict = {}
    for loc in locations or [{"type": "country", "key": "TR"}]:
        if loc["type"] == "country":
            geo.setdefault("countries", []).append(loc.get("country_code") or loc["key"])
        elif loc["type"] == "region":
            geo.setdefault("regions", []).append({"key": loc["key"]})
        else:
            geo.setdefault("cities", []).append({"key": loc["key"], "radius": 10, "distance_unit": "kilometer"})
    targeting = {
        "geo_locations": geo,
        "age_min": age_min,
        "age_max": age_max,
        # Yerleşimler kullanıcının seçtikleri (varsayılan yalnızca Instagram). Messenger, Audience Network ve Threads yok.
        **_positions(placements),
        "targeting_automation": {"advantage_audience": 0},
    }
    if gender in ("male", "female"):
        targeting["genders"] = [1 if gender == "male" else 2]
    return targeting


def _upload_media(act: str, token: str, media: dict, fetch_bytes) -> dict:
    """Görseli image_hash'e, videoyu video_id + kapak görseline çevirir."""
    if media["kind"] == "image":
        data = base64.b64encode(fetch_bytes(media["url"])).decode()
        res = _graph("POST", f"act_{act}/adimages", token, bytes=data)
        images = res.get("images") or {}
        first = next(iter(images.values()), {})
        if not first.get("hash"):
            raise MetaError("Görsel Meta'ya yüklenemedi.")
        return {"image_hash": first["hash"]}

    res = _graph("POST", f"act_{act}/advideos", token, file_url=media["url"], name="ajansAI video")
    video_id = res.get("id")
    if not video_id:
        raise MetaError("Video Meta'ya yüklenemedi.")
    # Meta videoyu işlerken kapak görseli hazır olana kadar bekle (en fazla ~2 dk).
    for _ in range(24):
        info = _graph("GET", video_id, token, fields="status,picture")
        status = (info.get("status") or {}).get("video_status")
        if status == "error":
            raise MetaError("Meta videoyu işleyemedi; farklı bir video dene.")
        if status == "ready" and info.get("picture"):
            return {"video_id": video_id, "thumbnail": info["picture"]}
        _time.sleep(5)
    raise MetaError("Meta videoyu zamanında işleyemedi; birkaç dakika sonra tekrar dene.")


def create_instagram_ad(
    *,
    token: str,
    ad_account_id: str,
    page_id: str,
    instagram_user_id: str | None,
    name: str,
    objective: str,
    daily_budget: float,
    start_time: str | None,
    end_time: str | None,
    locations: list[dict],
    age_min: int,
    age_max: int,
    gender: str,
    media: dict,
    primary_text: str,
    headline: str,
    link: str | None,
    call_to_action: str,
    fetch_bytes,
    placements: list[str] | None = None,
    story_media: dict | None = None,
    source_post: dict | None = None,
    carousel: list[dict] | None = None,
) -> dict:
    """Seçilen yerleşimlerde (varsayılan Instagram) duraklatılmış bir reklam oluşturur.

    story_media verilirse hikâye/Reels yerleşimlerinde dikey (9:16) görsel, akışta ana görsel
    kullanılır (yerleşime göre görsel özelleştirme).
    """
    act = ad_account_id.removeprefix("act_")
    camp_objective, optimization_goal, destination = OBJECTIVES[objective]

    campaign = _graph(
        "POST",
        f"act_{act}/campaigns",
        token,
        name=name,
        objective=camp_objective,
        status="PAUSED",
        special_ad_categories=[],
        is_adset_budget_sharing_enabled="false",
    )
    campaign_id = campaign["id"]
    try:
        adset_body = {
            "name": f"{name} - Instagram",
            "campaign_id": campaign_id,
            "daily_budget": int(round(daily_budget * 100)),  # TRY ve USD'de en küçük birim 1/100
            "billing_event": "IMPRESSIONS",
            "optimization_goal": optimization_goal,
            "bid_strategy": "LOWEST_COST_WITHOUT_CAP",
            "targeting": _targeting(locations, age_min, age_max, gender, placements),
            "status": "PAUSED",
        }
        if destination:
            adset_body["destination_type"] = destination
        if objective in ("whatsapp", "instagram_dm", "profile"):
            adset_body["promoted_object"] = {"page_id": page_id}
        if start_time:
            adset_body["start_time"] = start_time
        if end_time:
            adset_body["end_time"] = end_time
        adset = _graph("POST", f"act_{act}/adsets", token, **adset_body)

        if objective == "whatsapp":
            cta = {"type": "WHATSAPP_MESSAGE", "value": {"app_destination": "WHATSAPP"}}
            target_link = "https://api.whatsapp.com/send"
        elif objective == "instagram_dm":
            cta = {"type": "INSTAGRAM_MESSAGE", "value": {"app_destination": "INSTAGRAM_DIRECT"}}
            target_link = "https://www.instagram.com/"
        elif objective == "profile":
            target_link = link or "https://www.instagram.com/"
            cta = {"type": "VIEW_INSTAGRAM_PROFILE", "value": {"link": target_link}}
        else:
            target_link = link
            cta = {"type": call_to_action, "value": {"link": target_link}}

        if source_post:
            creative_body = _post_creative(name, page_id, instagram_user_id, source_post, cta, objective)
        elif carousel:
            creative_body = _carousel_creative(act, token, name, page_id, instagram_user_id, carousel,
                                               primary_text, target_link, cta, fetch_bytes)
        else:
            creative_body = _single_creative(act, token, name, page_id, instagram_user_id, media, story_media,
                                             placements, primary_text, headline, target_link, cta, fetch_bytes)
        creative = _graph("POST", f"act_{act}/adcreatives", token, **creative_body)
        ad = _graph(
            "POST",
            f"act_{act}/ads",
            token,
            name=name,
            adset_id=adset["id"],
            creative={"creative_id": creative["id"]},
            status="PAUSED",
        )
    except MetaError:
        try:
            _graph("DELETE", campaign_id, token)
        except MetaError:
            logger.warning("Yarım kalan kampanya silinemedi: %s", campaign_id)
        raise
    return {"campaign_id": campaign_id, "adset_id": adset["id"], "ad_id": ad["id"]}


def _single_creative(act, token, name, page_id, instagram_user_id, media, story_media, placements,
                     primary_text, headline, target_link, cta, fetch_bytes) -> dict:
    """Tek görsel/video (isteğe bağlı hikâye görseliyle) kreatifi."""
    uploaded = _upload_media(act, token, media, fetch_bytes)
    if "image_hash" in uploaded:
        story = {
            "page_id": page_id,
            "link_data": {
                "image_hash": uploaded["image_hash"],
                "link": target_link,
                "message": primary_text,
                "name": headline,
                "call_to_action": cta,
            },
        }
    else:
        story = {
            "page_id": page_id,
            "video_data": {
                "video_id": uploaded["video_id"],
                "image_url": uploaded["thumbnail"],
                "message": primary_text,
                "title": headline,
                "call_to_action": cta,
            },
        }
    if instagram_user_id:
        story["instagram_user_id"] = instagram_user_id
    creative_body = {"name": f"{name} - kreatif", "object_story_spec": story}
    pos = _positions(placements)
    vertical = [p for p in pos.get("instagram_positions", []) + pos.get("facebook_positions", []) if p in VERTICAL]
    if story_media and vertical and story_media.get("kind") == media.get("kind"):
        creative_body = _customized_creative(
            act, token, name, page_id, instagram_user_id, uploaded, _upload_media(act, token, story_media, fetch_bytes),
            pos, primary_text, headline, target_link, cta,
        )
    return creative_body


def _carousel_creative(act, token, name, page_id, ig_id, cards, primary_text, target_link, cta, fetch_bytes) -> dict:
    """Kaydırmalı karusel: 2-10 kart, her kartta görsel/video, başlık ve bağlantı."""
    children = []
    for card in cards[:10]:
        up = _upload_media(act, token, card["media"], fetch_bytes)
        item = {"link": card.get("link") or target_link, "name": (card.get("headline") or "")[:80], "call_to_action": cta}
        if "image_hash" in up:
            item["image_hash"] = up["image_hash"]
        else:
            item.update(video_id=up["video_id"], picture=up["thumbnail"])
        children.append(item)
    story = {"page_id": page_id, "link_data": {
        "link": target_link, "message": primary_text, "child_attachments": children,
        "multi_share_optimized": True, "multi_share_end_card": False, "call_to_action": cta,
    }}
    if ig_id:
        story["instagram_user_id"] = ig_id
    return {"name": f"{name} - karusel", "object_story_spec": story}


def _post_creative(name, page_id, ig_id, source_post, cta, objective) -> dict:
    """Mevcut bir gönderiyi (Instagram veya Facebook) reklam olarak kullanan kreatif."""
    if source_post["platform"] == "instagram":
        body = {"name": f"{name} - gönderi", "object_id": page_id, "instagram_user_id": ig_id,
                "source_instagram_media_id": source_post["id"]}
        if objective != "awareness":
            body["call_to_action"] = cta
        return body
    post_id = source_post["id"] if "_" in source_post["id"] else f"{page_id}_{source_post['id']}"
    body = {"name": f"{name} - gönderi", "object_story_id": post_id}
    if ig_id:
        body["instagram_user_id"] = ig_id
    return body


def _customized_creative(act, token, name, page_id, ig_id, feed, story, pos, text, headline, link, cta) -> dict:
    """Yerleşime göre görsel: akışta kare/4:5, hikâye ve Reels'te dikey görsel (asset_feed_spec)."""
    is_image = "image_hash" in feed
    key = "images" if is_image else "videos"

    def asset(up, label):
        if is_image:
            return {"hash": up["image_hash"], "adlabels": [{"name": label}]}
        return {"video_id": up["video_id"], "thumbnail_url": up["thumbnail"], "adlabels": [{"name": label}]}

    label_key = "image_label" if is_image else "video_label"
    feed_spec: dict = {"publisher_platforms": pos["publisher_platforms"]}
    vert_spec: dict = {"publisher_platforms": pos["publisher_platforms"]}
    ig, fb = pos.get("instagram_positions", []), pos.get("facebook_positions", [])
    if [p for p in ig if p not in VERTICAL]:
        feed_spec["instagram_positions"] = [p for p in ig if p not in VERTICAL]
    if [p for p in fb if p not in VERTICAL]:
        feed_spec["facebook_positions"] = [p for p in fb if p not in VERTICAL]
    if [p for p in ig if p in VERTICAL]:
        vert_spec["instagram_positions"] = [p for p in ig if p in VERTICAL]
    if [p for p in fb if p in VERTICAL]:
        vert_spec["facebook_positions"] = [p for p in fb if p in VERTICAL]
    rules = [{"customization_spec": vert_spec, label_key: {"name": "dikey"}}]
    if len(feed_spec) > 1:
        rules.append({"customization_spec": feed_spec, label_key: {"name": "akis"}})
    spec = {
        key: [asset(feed, "akis"), asset(story, "dikey")],
        "bodies": [{"text": text}],
        "titles": [{"text": headline}] if headline else [],
        "link_urls": [{"website_url": link}],
        "call_to_action_types": [cta["type"]],
        "ad_formats": ["SINGLE_IMAGE" if is_image else "SINGLE_VIDEO"],
        "asset_customization_rules": rules,
        "optimization_type": "PLACEMENT",
    }
    oss = {"page_id": page_id}
    if ig_id:
        oss["instagram_user_id"] = ig_id
    return {"name": f"{name} - kreatif", "object_story_spec": oss, "asset_feed_spec": spec}


def set_status(token: str, ids: list[str], status: str) -> None:
    """Kampanya, reklam seti ve reklamı birlikte aktifleştirir veya duraklatır."""
    for object_id in ids:
        _graph("POST", object_id, token, status=status)


def campaign_insights(token: str, campaign_id: str) -> dict:
    data = _graph(
        "GET",
        f"{campaign_id}/insights",
        token,
        fields="spend,impressions,reach,clicks,ctr,cpc,actions",
        date_preset="maximum",
    )
    rows = data.get("data") or []
    if not rows:
        return {"spend": 0, "impressions": 0, "reach": 0, "clicks": 0, "ctr": 0, "cpc": 0, "conversations": 0}
    r = rows[0]
    conversations = sum(
        int(float(a.get("value", 0)))
        for a in r.get("actions") or []
        if "messaging_conversation_started" in a.get("action_type", "")
    )
    return {
        "spend": float(r.get("spend", 0)),
        "impressions": int(r.get("impressions", 0)),
        "reach": int(r.get("reach", 0)),
        "clicks": int(r.get("clicks", 0)),
        "ctr": float(r.get("ctr", 0)),
        "cpc": float(r.get("cpc", 0)) if r.get("cpc") else 0,
        "conversations": conversations,
    }


def object_status(token: str, campaign_id: str) -> str:
    return _graph("GET", campaign_id, token, fields="effective_status").get("effective_status", "UNKNOWN")


_SETUP_CACHE: dict[str, tuple[float, dict]] = {}


def setup_status(token: str) -> dict:
    hit = _SETUP_CACHE.get(token[-24:])
    if hit and _time.time() - hit[0] < 120:
        return hit[1]
    out = _setup_status(token)
    _SETUP_CACHE[token[-24:]] = (_time.time(), out)
    return out


def _setup_status(token: str) -> dict:
    """Reklam vermeye hazır mı? Reklam hesabı, ödeme yöntemi, Facebook sayfası ve Instagram kontrolü.

    Eksik adımlar için Meta'nın ilgili sayfasına giden bağlantılar döndürülür (kart bilgisi
    Meta'nın kendi sayfasında girilir; API ile kart eklenemez).
    """
    accounts = _graph(
        "GET", "me/adaccounts", token,
        fields="account_id,name,currency,account_status,disable_reason,funding_source,funding_source_details{display_string}",
        limit=50,
    ).get("data", [])
    active = [a for a in accounts if a.get("account_status") == 1]
    unsettled = [a for a in accounts if a.get("account_status") in (3, 9)]
    paid = [a for a in active if a.get("funding_source") or (a.get("funding_source_details") or {}).get("display_string")]
    first = (paid or active or unsettled or accounts or [{}])[0].get("account_id")
    pages = list_pages(token, first) if first else list_pages(token)
    try:
        instagram = list_instagram_accounts(first, token) if first else []
    except MetaError:
        instagram = []
    instagram = instagram or [{"id": p["instagram_id"], "username": p["instagram_username"]} for p in pages if p.get("instagram_id")]
    steps = [
        {
            "key": "ad_account", "done": bool(active), "title": "Reklam hesabı",
            "text": "Meta'da bir reklam hesabın olmalı; yoksa 1 dakikada oluşturulur." if not accounts
            else (f"Hesaplarında ödenmemiş bakiye var ({unsettled[0].get('name')}); ödeyince reklamlar yayına girer." if not active and unsettled
                  else ("Reklam hesabın devre dışı; Meta'dan aktifleştirmen gerekiyor." if not active else f"{len(active)} aktif reklam hesabın var.")),
            "action": "Bakiyeyi öde" if (not active and unsettled) else "Reklam hesabı oluştur",
            "url": f"https://business.facebook.com/billing_hub/payment_activity/?asset_id={unsettled[0].get('account_id')}" if (not active and unsettled)
            else "https://business.facebook.com/latest/settings/ad_accounts",
        },
        {
            "key": "payment", "done": bool(paid), "title": "Ödeme yöntemi (kart)",
            "text": "Reklam bütçesi kartından Meta tarafından çekilir. Kartını Meta'nın güvenli sayfasında eklersin."
            if not paid else (paid[0].get("funding_source_details") or {}).get("display_string") or "Kart tanımlı.",
            "action": "Kart ekle",
            "url": f"https://business.facebook.com/billing_hub/payment_settings/?asset_id={first}" if first
            else "https://business.facebook.com/billing_hub/payment_settings/",
        },
        {
            "key": "page", "done": bool(pages), "title": "Facebook sayfası",
            "text": "Meta, reklamın kimin adına gösterileceğini sayfadan alır (reklam yalnızca Instagram'da çıksa da). 1 dakikada açılır."
            if not pages else f"{pages[0].get('name')} hazır.",
            "action": "Sayfa oluştur", "url": "https://www.facebook.com/pages/create",
        },
        {
            "key": "instagram", "done": bool(instagram), "title": "Instagram hesabı",
            "text": "Instagram hesabını profesyonel hesaba çevirip Facebook sayfana bağla (Instagram > Ayarlar > Hesap Merkezi)."
            if not instagram else f"@{instagram[0].get('username')} bağlı.",
            "action": "Instagram'ı bağla", "url": "https://business.facebook.com/latest/settings/instagram_account",
        },
    ]
    return {"ready": all(s["done"] for s in steps), "steps": steps}


def page_whatsapp(token: str, page_id: str) -> dict:
    """Sayfaya bağlı WhatsApp numarası.

    Meta bu alanı çoğu uygulamaya göstermez (numara bağlı olsa da boş döner). Numara okunamazsa
    known=False döner; arayüz uyarı yerine bilgi gösterir ve devam etmeye izin verir.
    """
    number = None
    for use_page_token in (False, True):
        try:
            tok = token
            if use_page_token:
                tok = _graph("GET", page_id, token, fields="access_token").get("access_token") or ""
                if not tok:
                    break
            number = _graph("GET", page_id, tok, fields="whatsapp_number").get("whatsapp_number") or None
        except MetaError as e:
            logger.info("WhatsApp numarası okunamadı (%s): %s", page_id, e)
        if number:
            break
    return {
        "number": number,
        "known": bool(number),
        # asset_id ile Business Suite, sayfanın kendi portföyünde açılır
        "connect_url": f"https://business.facebook.com/latest/settings/whatsapp_account?asset_id={page_id}",
        "help": "Sayfanın ayarlarında Bağlı hesaplar > WhatsApp bölümünden numaranı bağlayabilirsin; doğrulama kodu WhatsApp'a gelir.",
    }
