"""Tests unitaires de la fonction generate-2fa."""

from __future__ import annotations

import base64
import re
from urllib.parse import parse_qs, urlparse

import pyotp
import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.unit


def test_handler_returns_otpauth_uri_and_qrcode(load_function, mock_pymysql):
    main = load_function("generate-2fa")
    conn, cursor = mock_pymysql

    client = TestClient(main.app)
    response = client.post("/", json={"username": "alice"})

    assert response.status_code == 200
    body = response.json()
    assert body["username"] == "alice"

    uri = body["otpauth_uri"]
    parsed = urlparse(uri)
    assert parsed.scheme == "otpauth"
    assert parsed.netloc == "totp"
    assert "alice" in parsed.path
    query = parse_qs(parsed.query)
    assert query["issuer"] == ["COFRAP"]
    secret = query["secret"][0]
    assert re.fullmatch(r"[A-Z2-7]+", secret)
    # On doit pouvoir consommer le secret avec pyotp directement.
    code = pyotp.TOTP(secret).now()
    assert re.fullmatch(r"\d{6}", code)

    # QR PNG valide
    raw = base64.b64decode(body["qrcode_png_base64"])
    assert raw.startswith(b"\x89PNG\r\n\x1a\n")

    cursor.execute.assert_called_once()
    sql, _ = cursor.execute.call_args[0]
    assert "UPDATE users" in sql
    assert "SET mfa" in sql
    conn.commit.assert_called_once()


def test_handler_encrypts_secret_before_storage(load_function, mock_pymysql):
    main = load_function("generate-2fa")
    _, cursor = mock_pymysql

    client = TestClient(main.app)
    client.post("/", json={"username": "alice"})

    _, params = cursor.execute.call_args[0]
    encrypted_secret = params[0]
    assert encrypted_secret.startswith("gAAAAA")  # Fernet


def test_handler_returns_404_when_user_missing(load_function, mock_pymysql):
    main = load_function("generate-2fa")
    conn, cursor = mock_pymysql
    cursor.rowcount = 0  # aucun utilisateur mis à jour

    client = TestClient(main.app)
    response = client.post("/", json={"username": "ghost"})

    assert response.status_code == 404
    assert "generate-password" in response.json()["detail"]
    conn.commit.assert_not_called()
    conn.rollback.assert_called_once()


def test_handler_uses_custom_issuer(load_function, mock_pymysql, monkeypatch):
    monkeypatch.setenv("TOTP_ISSUER", "ACME")
    main = load_function("generate-2fa")

    client = TestClient(main.app)
    response = client.post("/", json={"username": "bob"})

    assert response.status_code == 200
    parsed = urlparse(response.json()["otpauth_uri"])
    assert parse_qs(parsed.query)["issuer"] == ["ACME"]


def test_healthz(load_function):
    main = load_function("generate-2fa")
    client = TestClient(main.app)
    assert client.get("/healthz").json() == {"status": "ok"}
