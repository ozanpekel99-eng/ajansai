"""Google ve Apple ile giriş: istemcinin aldığı kimlik token'ı (JWT) burada doğrulanır.

İki sağlayıcı da token'ı kendi açık anahtarlarıyla imzalar; anahtarlar JWKS
adresinden alınır, imza + hedef kitle (bizim istemci kimliğimiz) + yayıncı
kontrol edilir. Şifre saklanmaz.
"""

import jwt
from jwt import PyJWKClient

from app import config

_clients: dict[str, PyJWKClient] = {}

PROVIDERS = {
    "google": {
        "jwks": "https://www.googleapis.com/oauth2/v3/certs",
        "issuers": ["https://accounts.google.com", "accounts.google.com"],
        "audience": lambda: config.GOOGLE_CLIENT_ID,
    },
    "apple": {
        "jwks": "https://appleid.apple.com/auth/keys",
        "issuers": ["https://appleid.apple.com"],
        "audience": lambda: config.APPLE_CLIENT_ID,
    },
}


class SocialAuthError(Exception):
    pass


def enabled(provider: str) -> bool:
    return bool(PROVIDERS[provider]["audience"]())


def _jwks(provider: str) -> PyJWKClient:
    if provider not in _clients:
        _clients[provider] = PyJWKClient(PROVIDERS[provider]["jwks"], cache_keys=True)
    return _clients[provider]


def verify(provider: str, token: str) -> dict:
    """Geçerli token'ın içeriğini döndürür: en az email ve sub."""
    p = PROVIDERS[provider]
    audience = p["audience"]()
    if not audience:
        raise SocialAuthError(f"{provider} ile giriş henüz açılmadı.")
    try:
        key = _jwks(provider).get_signing_key_from_jwt(token).key
        claims = jwt.decode(token, key, algorithms=["RS256"], audience=audience, issuer=p["issuers"])
    except jwt.PyJWTError as e:
        raise SocialAuthError("Giriş doğrulanamadı, tekrar dene.") from e
    email = (claims.get("email") or "").strip().lower()
    verified = claims.get("email_verified")
    if not email or verified in (False, "false"):
        raise SocialAuthError("Hesabının e-posta adresi doğrulanmamış.")
    return claims
