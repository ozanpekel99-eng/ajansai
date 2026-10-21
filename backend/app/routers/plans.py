from fastapi import APIRouter, Depends

from app.security import get_current_user
from app.services.plans import PLANS
from app.services.usage_service import get_usage

router = APIRouter()


@router.get("/")
def list_plans():
    """Fiyatlandırma sayfasında gösterilecek satın alınabilir paketler."""
    return {"plans": {pid: p for pid, p in PLANS.items() if p["purchasable"]}}


@router.get("/usage")
def usage(user: dict = Depends(get_current_user)):
    """Kullanıcının mevcut paketini ve kalan kotasını döndürür.

    Paket değişikliği artık yalnızca başarılı ödemeyle olur (/api/payments/checkout).
    """
    return get_usage(user["id"])
