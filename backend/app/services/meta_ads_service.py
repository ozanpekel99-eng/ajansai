from urllib.parse import urlencode

import requests

from app import config

META_API_VERSION = "v20.0"
META_BASE_URL = f"https://graph.facebook.com/{META_API_VERSION}"


class MetaError(Exception):
    pass


def get_oauth_url(redirect_uri: str, state: str) -> str:
    """Kullanıcıyı Meta'nın izin ekranına yönlendirecek URL'yi üretir.

    `state`, CSRF'e karşı imzalı ve kısa ömürlü bir değerdir; callback'te
    doğrulanır. ads_management izni Meta App Review onayı gerektirir.
    """
    query = urlencode(
        {
            "client_id": config.META_APP_ID,
            "redirect_uri": redirect_uri,
            "scope": "ads_management,pages_show_list",
            "state": state,
        }
    )
    return f"https://www.facebook.com/{META_API_VERSION}/dialog/oauth?{query}"


def exchange_code_for_token(code: str, redirect_uri: str) -> str:
    """OAuth kodunu uzun ömürlü erişim token'ına çevirir."""
    try:
        short = requests.get(
            f"{META_BASE_URL}/oauth/access_token",
            params={
                "client_id": config.META_APP_ID,
                "client_secret": config.META_APP_SECRET,
                "redirect_uri": redirect_uri,
                "code": code,
            },
            timeout=30,
        )
        short.raise_for_status()
        short_token = short.json()["access_token"]

        # Kısa ömürlü (1-2 saat) token'ı ~60 günlük token'a çeviriyoruz.
        long = requests.get(
            f"{META_BASE_URL}/oauth/access_token",
            params={
                "grant_type": "fb_exchange_token",
                "client_id": config.META_APP_ID,
                "client_secret": config.META_APP_SECRET,
                "fb_exchange_token": short_token,
            },
            timeout=30,
        )
        long.raise_for_status()
        return long.json()["access_token"]
    except (requests.RequestException, KeyError, ValueError) as e:
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
