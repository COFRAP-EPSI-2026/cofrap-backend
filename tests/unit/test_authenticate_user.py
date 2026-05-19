"""Tests unitaires de la fonction authenticate-user."""

from __future__ import annotations

import time

import pyotp
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

pytestmark = pytest.mark.unit


def _encrypted(value: str, fernet_key: str) -> str:
    return Fernet(fernet_key.encode()).encrypt(value.encode()).decode()


def test_404_for_unknown_user(load_function, mock_pymysql):
    main = load_function("authenticate-user")
    _, cursor = mock_pymysql
    cursor.fetchone.return_value = None

    client = TestClient(main.app)
    response = client.post("/", json={"username": "ghost", "password": "whatever", "otp": "000000"})

    assert response.status_code == 404


def test_expired_account_returns_action(load_function, mock_pymysql, fernet_key):
    main = load_function("authenticate-user")
    conn, cursor = mock_pymysql
    cursor.fetchone.return_value = (
        _encrypted("password", fernet_key),
        _encrypted("AAAA2222", fernet_key),
        1,  # gendate très ancien
        0,  # flag expired pas encore positionné
    )

    client = TestClient(main.app)
    response = client.post("/", json={"username": "alice", "password": "password", "otp": "000000"})

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "authenticated": False,
        "expired": True,
        "action": "regenerate_password_and_2fa",
    }
    # La fonction a basculé expired=1 en BDD.
    update_calls = [c for c in cursor.execute.call_args_list if "UPDATE" in c.args[0]]
    assert len(update_calls) == 1
    assert "expired = 1" in update_calls[0].args[0]
    conn.commit.assert_called_once()


def test_expired_flag_already_set(load_function, mock_pymysql, fernet_key):
    main = load_function("authenticate-user")
    _, cursor = mock_pymysql
    cursor.fetchone.return_value = (
        _encrypted("password", fernet_key),
        _encrypted("AAAA2222", fernet_key),
        int(time.time()),
        1,  # déjà marqué expired
    )

    client = TestClient(main.app)
    response = client.post("/", json={"username": "alice", "password": "password", "otp": "000000"})

    body = response.json()
    assert body["expired"] is True
    # Pas besoin de re-UPDATE car déjà à 1.
    update_calls = [c for c in cursor.execute.call_args_list if "UPDATE" in c.args[0]]
    assert update_calls == []


def test_invalid_password(load_function, mock_pymysql, fernet_key):
    main = load_function("authenticate-user")
    _, cursor = mock_pymysql
    cursor.fetchone.return_value = (
        _encrypted("real-password", fernet_key),
        _encrypted("AAAA2222", fernet_key),
        int(time.time()),
        0,
    )

    client = TestClient(main.app)
    response = client.post(
        "/", json={"username": "alice", "password": "wrong-password", "otp": "000000"}
    )

    assert response.status_code == 401
    assert "invalid credentials" in response.json()["detail"]


def test_invalid_otp(load_function, mock_pymysql, fernet_key):
    main = load_function("authenticate-user")
    _, cursor = mock_pymysql
    secret = pyotp.random_base32()
    cursor.fetchone.return_value = (
        _encrypted("real-password", fernet_key),
        _encrypted(secret, fernet_key),
        int(time.time()),
        0,
    )

    client = TestClient(main.app)
    response = client.post(
        "/", json={"username": "alice", "password": "real-password", "otp": "000000"}
    )

    assert response.status_code == 401
    assert "invalid otp" in response.json()["detail"]


def test_success_with_valid_credentials(load_function, mock_pymysql, fernet_key):
    main = load_function("authenticate-user")
    _, cursor = mock_pymysql
    secret = pyotp.random_base32()
    cursor.fetchone.return_value = (
        _encrypted("real-password", fernet_key),
        _encrypted(secret, fernet_key),
        int(time.time()),
        0,
    )

    valid_otp = pyotp.TOTP(secret).now()

    client = TestClient(main.app)
    response = client.post(
        "/", json={"username": "alice", "password": "real-password", "otp": valid_otp}
    )

    assert response.status_code == 200
    assert response.json() == {"authenticated": True, "expired": False, "username": "alice"}


def test_409_when_password_or_mfa_missing(load_function, mock_pymysql):
    main = load_function("authenticate-user")
    _, cursor = mock_pymysql
    cursor.fetchone.return_value = (None, None, int(time.time()), 0)

    client = TestClient(main.app)
    response = client.post("/", json={"username": "alice", "password": "x", "otp": "000000"})

    assert response.status_code == 409


@pytest.mark.parametrize("bad_otp", ["12345", "1234567", "abcdef", ""])
def test_otp_validation(load_function, bad_otp):
    main = load_function("authenticate-user")
    client = TestClient(main.app)
    response = client.post("/", json={"username": "alice", "password": "x", "otp": bad_otp})
    assert response.status_code == 422


def test_healthz(load_function):
    main = load_function("authenticate-user")
    client = TestClient(main.app)
    assert client.get("/healthz").json() == {"status": "ok"}
