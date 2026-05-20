import os
import time

import pyotp
from crypto import encrypt
from db import get_connection
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from qr import make_qr_png_base64

ISSUER = os.getenv("TOTP_ISSUER", "COFRAP")

app = FastAPI(
    title="cofrap-generate-2fa",
    version="2026.1.1",
    summary="Génère un secret TOTP (RFC 6238) et son QR code otpauth:// pour un utilisateur existant.",
)


class GenerateRequest(BaseModel):
    username: str = Field(
        min_length=1, max_length=255, description="Identifiant utilisateur existant."
    )


class GenerateResponse(BaseModel):
    username: str = Field(description="Identifiant utilisateur traité.")
    gendate: int = Field(description="Timestamp Unix (secondes) de génération.")
    otpauth_uri: str = Field(
        description="URI `otpauth://totp/...` à importer dans une app authenticator.",
    )
    qrcode_png_base64: str = Field(description="QR code PNG (base64) encodant l'URI otpauth.")


class HealthResponse(BaseModel):
    status: str


@app.post(
    "/",
    response_model=GenerateResponse,
    operation_id="generate2FA",
    summary="Génère et stocke le secret TOTP d'un utilisateur existant",
    responses={
        404: {"description": "Utilisateur inconnu — appeler `generate-password` au préalable."},
        500: {"description": "Erreur BDD — la transaction est rollback."},
    },
)
def handler(req: GenerateRequest) -> dict:
    secret = pyotp.random_base32()
    uri = pyotp.TOTP(secret).provisioning_uri(name=req.username, issuer_name=ISSUER)
    qr_b64 = make_qr_png_base64(uri)
    encrypted = encrypt(secret)
    gendate = int(time.time())

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE users
                SET mfa = %s, gendate = %s, expired = 0
                WHERE username = %s
                """,
                (encrypted, gendate, req.username),
            )
            if cur.rowcount == 0:
                conn.rollback()
                raise HTTPException(
                    status_code=404,
                    detail="user not found, run generate-password first",
                )
        conn.commit()
    except HTTPException:
        raise
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"database error: {exc}") from exc
    finally:
        conn.close()

    return {
        "username": req.username,
        "gendate": gendate,
        "otpauth_uri": uri,
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
