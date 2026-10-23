"""Dolar/TL kuru: ödeme TL ile alınırken USD fiyatlar o günkü TCMB döviz satış kuruyla çevrilir.

Kur bir saat önbellekte tutulur. TCMB'ye ulaşılamazsa son bilinen kur, o da yoksa
USD_TRY_RATE ortam değişkeni kullanılır.
"""

import logging
import time
import xml.etree.ElementTree as ET
from decimal import ROUND_HALF_UP, Decimal

import requests

from app import config

logger = logging.getLogger("ajansai.fx")

TCMB_URL = "https://www.tcmb.gov.tr/kurlar/today.xml"
_cache: dict = {"rate": None, "at": 0.0}


class FxError(Exception):
    pass


def _fetch_tcmb() -> Decimal:
    r = requests.get(TCMB_URL, timeout=10)
    r.raise_for_status()
    root = ET.fromstring(r.content)
    for cur in root.iter("Currency"):
        if cur.get("CurrencyCode") == "USD":
            value = (cur.findtext("ForexSelling") or "").strip()
            if value:
                return Decimal(value)
    raise FxError("TCMB yanıtında USD kuru yok.")


def usd_try_rate() -> Decimal:
    if _cache["rate"] and time.time() - _cache["at"] < 3600:
        return _cache["rate"]
    try:
        rate = _fetch_tcmb()
        _cache.update(rate=rate, at=time.time())
        return rate
    except Exception as e:  # noqa: BLE001
        logger.warning("TCMB kuru alınamadı: %s", e)
    if _cache["rate"]:
        return _cache["rate"]
    if config.USD_TRY_RATE:
        return Decimal(str(config.USD_TRY_RATE))
    raise FxError("Döviz kuru alınamadı, lütfen biraz sonra tekrar dene.")


def to_try(usd: Decimal | float) -> Decimal:
    return (Decimal(str(usd)) * usd_try_rate()).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
