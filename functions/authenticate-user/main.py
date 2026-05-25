import os
import time

import pyotp
from crypto import decrypt
from db import get_connection
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

SIX_MONTHS_SECONDS = int(os.getenv("EXPIRY_SECONDS", str(60 * 60 * 24 * 30 * 6)))

app = FastAPI(
    title="cofrap-authenticate-user",
    version="2026.3.2",  # x-release-please-version
    summary="Authentifie un utilisateur (login + password + TOTP), contrôle l'expiration à 6 mois.",
)


def _cors_origins() -> list[str]:
    """Origines autorisées (CORS). `CORS_ALLOW_ORIGINS` = `*` (défaut) ou liste séparée par virgules."""
    raw = os.getenv("CORS_ALLOW_ORIGINS", "*").strip()
    if raw == "*":
        return ["*"]
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Rate limiting (slowapi) --------------------------------------------------
# Protège l'API : au-delà de RATE_LIMIT requêtes par IP → HTTP 429. Combiné à
# `max_inflight` (of-watchdog) et aux timeouts BDD, borne la charge et évite de
# saturer MariaDB. RATE_LIMIT_ENABLED=0 désactive (utile en test).
def _client_ip(request: Request) -> str:
    """Clé de rate-limit : vraie IP client (X-Forwarded-For) ou IP directe."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return get_remote_address(request)


limiter = Limiter(
    key_func=_client_ip,
    default_limits=[os.getenv("RATE_LIMIT", "120/minute")],
    enabled=os.getenv("RATE_LIMIT_ENABLED", "true").lower() not in ("0", "false", "no"),
)


def _rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(status_code=429, content={"detail": "rate limit exceeded"})


app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)
app.add_middleware(SlowAPIMiddleware)


class AuthRequest(BaseModel):
    username: str = Field(min_length=1, max_length=255, description="Identifiant utilisateur.")
    password: str = Field(min_length=1, description="Mot de passe en clair (24 caractères).")
    otp: str = Field(
        min_length=6,
        max_length=6,
        pattern=r"^\d{6}$",
        description="Code TOTP à 6 chiffres généré par l'app authenticator.",
    )


class AuthSuccessResponse(BaseModel):
    authenticated: bool = Field(description="`true` si toutes les vérifications passent.")
    expired: bool = Field(
        description="`true` si le compte est expiré (>6 mois ou flag positionné)."
    )
    username: str | None = Field(
        default=None,
        description="Présent uniquement quand `authenticated == true`.",
    )
    action: str | None = Field(
        default=None,
        description="Présent quand `expired == true` : indique au frontend l'action requise.",
        examples=["regenerate_password_and_2fa"],
    )


class HealthResponse(BaseModel):
    status: str


def _mark_expired(conn, username: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE users SET expired = 1 WHERE username = %s",
            (username,),
        )
    conn.commit()


@app.post(
    "/",
    response_model=AuthSuccessResponse,
    response_model_exclude_none=True,
    operation_id="authenticateUser",
    summary="Authentifie un utilisateur",
    responses={
        401: {"description": "Mot de passe ou code TOTP invalide."},
        404: {"description": "Utilisateur inconnu."},
        409: {"description": "Compte incomplet (password ou mfa NULL en BDD)."},
        429: {"description": "Trop de requêtes — rate limit dépassé."},
        500: {"description": "Erreur interne."},
    },
)
def handler(req: AuthRequest) -> dict:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT password, mfa, gendate, expired
                FROM users
                WHERE username = %s
                """,
                (req.username,),
            )
            row = cur.fetchone()

        if row is None:
            raise HTTPException(status_code=404, detail="user not found")

        enc_password, enc_mfa, gendate, expired = row
        now = int(time.time())

        is_expired = bool(expired) or (now - int(gendate) > SIX_MONTHS_SECONDS)
        if is_expired:
            if not expired:
                _mark_expired(conn, req.username)
            return {
                "authenticated": False,
                "expired": True,
                "action": "regenerate_password_and_2fa",
            }

        if enc_password is None or enc_mfa is None:
            raise HTTPException(
                status_code=409,
                detail="account incomplete, finish password and 2fa setup",
            )

        if decrypt(enc_password) != req.password:
            raise HTTPException(status_code=401, detail="invalid credentials")

        totp = pyotp.TOTP(decrypt(enc_mfa))
        if not totp.verify(req.otp, valid_window=1):
            raise HTTPException(status_code=401, detail="invalid otp")

        return {"authenticated": True, "expired": False, "username": req.username}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"database error: {exc}") from exc
    finally:
        conn.close()


@app.get(
    "/healthz",
    response_model=HealthResponse,
    operation_id="healthz",
    summary="Sonde de santé",
    tags=["health"],
)
@limiter.exempt
def healthz() -> dict:
    return {"status": "ok"}
