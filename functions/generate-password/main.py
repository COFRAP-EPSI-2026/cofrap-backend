import os
import secrets
import string
import time

from crypto import encrypt
from db import get_connection
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from qr import make_qr_png_base64

PASSWORD_LENGTH = 24
SPECIALS = "!@#$%^&*()-_=+[]{};:,.<>?/"
ALPHABET = string.ascii_letters + string.digits + SPECIALS

app = FastAPI(
    title="cofrap-generate-password",
    version="2026.3.2",  # x-release-please-version
    summary="Génère un mot de passe à 24 caractères et le transmet via QR code.",
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


class GenerateRequest(BaseModel):
    username: str = Field(
        min_length=1, max_length=255, description="Identifiant utilisateur unique."
    )


class GenerateResponse(BaseModel):
    username: str = Field(description="Identifiant utilisateur traité.")
    gendate: int = Field(description="Timestamp Unix (secondes) de génération.")
    qrcode_png_base64: str = Field(
        description="QR code PNG encodé en base64, contenant le mot de passe en clair (transmission à usage unique).",
    )


class HealthResponse(BaseModel):
    status: str = Field(description="Statut de santé — toujours `ok` quand la fonction répond.")


def generate_password(length: int = PASSWORD_LENGTH) -> str:
    while True:
        pwd = "".join(secrets.choice(ALPHABET) for _ in range(length))
        if (
            any(c.islower() for c in pwd)
            and any(c.isupper() for c in pwd)
            and any(c.isdigit() for c in pwd)
            and any(c in SPECIALS for c in pwd)
        ):
            return pwd


@app.post(
    "/",
    response_model=GenerateResponse,
    operation_id="generatePassword",
    summary="Génère ou réinitialise le mot de passe d'un utilisateur",
    responses={
        500: {"description": "Erreur BDD — la transaction est rollback."},
    },
)
def handler(req: GenerateRequest) -> dict:
    password = generate_password()
    qr_b64 = make_qr_png_base64(password)
    encrypted = encrypt(password)
    gendate = int(time.time())

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO users (username, password, gendate, expired)
                VALUES (%s, %s, %s, 0)
                ON DUPLICATE KEY UPDATE
                    password = VALUES(password),
                    gendate = VALUES(gendate),
                    expired = 0
                """,
                (req.username, encrypted, gendate),
            )
        conn.commit()
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"database error: {exc}") from exc
    finally:
        conn.close()

    return {
        "username": req.username,
        "gendate": gendate,
        "qrcode_png_base64": qr_b64,
    }


@app.get(
    "/healthz",
    response_model=HealthResponse,
    operation_id="healthz",
    summary="Sonde de santé",
    tags=["health"],
)
def healthz() -> dict:
    return {"status": "ok"}
