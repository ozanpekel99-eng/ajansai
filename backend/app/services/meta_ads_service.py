import logging
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
        params["scope"] = "ads_management,ads_read,business_management,pages_show_list"
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


def list_ad_accounts(access_token: str) -> list[dict]:
    try:
        response = requests.get(
            f"{META_BASE_URL}/me/adaccounts",
            params={"fields": "account_id,name,currency,account_status", "access_token": access_token},
            timeout=30,
        )
        response.raise_for_status()
        return response.json().get("data", [])
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
