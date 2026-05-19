"""Test d'intégration end-to-end : password → 2FA → authentication.

Utilise une vraie MariaDB. Skip auto si la BDD n'est pas joignable
(cf. `conftest.py` → `_is_mariadb_reachable`).
"""

from __future__ import annotations

import time
from urllib.parse import parse_qs, urlparse

import pyotp
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


def test_complete_onboarding_and_auth(load_function, db_row, fernet_key):
    # --- 1. Génération du mot de passe ---
    gen_pwd = load_function("generate-password")
    pwd_client = TestClient(gen_pwd.app)
    pwd_response = pwd_client.post("/", json={"username": "michel.ranu"})
    assert pwd_response.status_code == 200

    row = db_row("michel.ranu")
    assert row is not None
    username, enc_password, enc_mfa, gendate, expired = row
    assert username == "michel.ranu"
    assert enc_password is not None and enc_password.startswith("gAAAAA")
    assert enc_mfa is None
    assert expired == 0
    assert abs(time.time() - gendate) < 5

    # Le mot de passe en clair est récupérable via la clé Fernet (qui sert ici de "scan QR")
    plain_password = Fernet(fernet_key.encode()).decrypt(enc_password.encode()).decode()
    assert len(plain_password) == 24

    # --- 2. Génération du secret TOTP ---
    gen_2fa = load_function("generate-2fa")
    mfa_client = TestClient(gen_2fa.app)
    mfa_response = mfa_client.post("/", json={"username": "michel.ranu"})
    assert mfa_response.status_code == 200

    uri = mfa_response.json()["otpauth_uri"]
    totp_secret = parse_qs(urlparse(uri).query)["secret"][0]

    row = db_row("michel.ranu")
    assert row is not None
    _, _, enc_mfa, _, _ = row
    assert enc_mfa is not None and enc_mfa.startswith("gAAAAA")
    assert Fernet(fernet_key.encode()).decrypt(enc_mfa.encode()).decode() == totp_secret

    # --- 3. Authentification succès ---
    auth = load_function("authenticate-user")
    auth_client = TestClient(auth.app)
    valid_otp = pyotp.TOTP(totp_secret).now()
    auth_response = auth_client.post(
        "/",
        json={
            "username": "michel.ranu",
            "password": plain_password,
            "otp": valid_otp,
        },
    )
    assert auth_response.status_code == 200
    assert auth_response.json() == {
        "authenticated": True,
        "expired": False,
        "username": "michel.ranu",
    }


def test_authentication_fails_with_wrong_password(load_function, fernet_key):
    # Setup complet : password puis 2FA, sinon la fonction répond 409 ("account incomplete")
    TestClient(load_function("generate-password").app).post("/", json={"username": "alice"})
    TestClient(load_function("generate-2fa").app).post("/", json={"username": "alice"})

    response = TestClient(load_function("authenticate-user").app).post(
        "/",
        json={
            "username": "alice",
            "password": "definitely-not-the-right-pwd",
            "otp": "000000",
        },
    )
    assert response.status_code == 401


def test_authentication_409_when_2fa_missing(load_function):
    """User qui a fait generate-password mais pas generate-2fa → compte incomplet."""
    TestClient(load_function("generate-password").app).post("/", json={"username": "dave"})

    response = TestClient(load_function("authenticate-user").app).post(
        "/",
        json={"username": "dave", "password": "x", "otp": "000000"},
    )
    assert response.status_code == 409


def test_authentication_returns_expired_for_old_account(load_function, db_row, fernet_key):
    """Compte créé puis vieilli artificiellement via UPDATE direct."""
    gen_pwd = load_function("generate-password")
    TestClient(gen_pwd.app).post("/", json={"username": "bob"})

    gen_2fa = load_function("generate-2fa")
    TestClient(gen_2fa.app).post("/", json={"username": "bob"})

    # Vieillit gendate de 7 mois en direct dans la BDD
    import os

    import pymysql

    conn = pymysql.connect(
        host=os.getenv("DB_HOST", "127.0.0.1"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER", "cofrap"),
        password=os.getenv("MARIADB_PASSWORD", "cofrap_dev"),
        database=os.getenv("DB_NAME", "cofrap"),
        autocommit=True,
    )
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE users SET gendate = %s WHERE username = %s",
            (int(time.time()) - 60 * 60 * 24 * 30 * 7, "bob"),
        )
    conn.close()

    auth = load_function("authenticate-user")
    response = TestClient(auth.app).post(
        "/",
        json={"username": "bob", "password": "anything", "otp": "000000"},
    )
    assert response.status_code == 200
    assert response.json() == {
        "authenticated": False,
        "expired": True,
        "action": "regenerate_password_and_2fa",
    }

    # Le flag expired a été basculé en BDD
    row = db_row("bob")
    assert row[-1] == 1  # expired column


def test_generate_2fa_404_when_no_user(load_function):
    gen_2fa = load_function("generate-2fa")
    response = TestClient(gen_2fa.app).post("/", json={"username": "ghost"})
    assert response.status_code == 404


def test_generate_password_can_reset_existing_account(load_function, db_row):
    gen_pwd = load_function("generate-password")
    client = TestClient(gen_pwd.app)

    first = client.post("/", json={"username": "carol"})
    first_gendate = first.json()["gendate"]
    first_password_enc = db_row("carol")[1]

    time.sleep(1.1)  # garantir un gendate différent
    second = client.post("/", json={"username": "carol"})

    assert second.json()["gendate"] >= first_gendate + 1
    second_password_enc = db_row("carol")[1]
    assert first_password_enc != second_password_enc
