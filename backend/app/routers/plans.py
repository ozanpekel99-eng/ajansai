from fastapi import APIRouter, Depends

from app.security import get_current_user
from app import config
from app.services.plans import CREDIT_COSTS, PLANS, public_plan
from app.services.usage_service import get_usage, list_events

router = APIRouter()


@router.get("/")
def list_plans():
    """Paketler sayfası: satın alınabilir paketler, deneme paketi ve işlem başına kredi maliyetleri."""
    return {
        "plans": {pid: public_plan(pid) for pid, p in PLANS.items() if p["purchasable"]},
        "trial": public_plan("deneme"),
        "costs": CREDIT_COSTS,
        "free": {
            "chat_per_day": config.FREE_CHAT_PER_DAY_USER,
            "chat_per_day_guest": config.FREE_CHAT_PER_DAY_ANON,
            "images_per_month": config.FREE_IMAGES_PER_MONTH,
        },
    }


@router.get("/usage")
def usage(user: dict = Depends(get_current_user)):
    """Kullanıcının paketi, kredi bakiyesi ve bu dönemki kullanımı."""
    return get_usage(user["id"])


@router.get("/history")
def history(user: dict = Depends(get_current_user)):
    """Son kredi hareketleri: hangi işleme kaç kredi harcandı, iade edildi mi."""
    return {"events": list_events(user["id"])}
