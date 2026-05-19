"""Tests unitaires de la fonction generate-password."""

from __future__ import annotations

import base64
import string

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.unit


def test_password_meets_complexity(load_function):
    main = load_function("generate-password")
    for _ in range(50):
        pwd = main.generate_password()
        assert len(pwd) == main.PASSWORD_LENGTH == 24
        assert any(c.islower() for c in pwd)
        assert any(c.isupper() for c in pwd)
        assert any(c.isdigit() for c in pwd)
        assert any(c in main.SPECIALS for c in pwd)
        assert all(c in string.ascii_letters + string.digits + main.SPECIALS for c in pwd)


def test_passwords_are_random(load_function):
    main = load_function("generate-password")
    samples = {main.generate_password() for _ in range(30)}
    # 30 tirages 24-chars dans un alphabet de ~89 caractères : collisions virtuellement impossibles.
    assert len(samples) == 30


def test_handler_returns_qrcode_and_persists_user(load_function, mock_pymysql):
    main = load_function("generate-password")
    conn, cursor = mock_pymysql

    client = TestClient(main.app)
    response = client.post("/", json={"username": "michel.ranu"})

    assert response.status_code == 200
    body = response.json()
    assert body["username"] == "michel.ranu"
    assert isinstance(body["gendate"], int)
    assert body["gendate"] > 1_700_000_000

    # QR code = PNG base64, doit commencer par les bytes magiques PNG après décodage
    raw = base64.b64decode(body["qrcode_png_base64"])
    assert raw.startswith(b"\x89PNG\r\n\x1a\n")

    # BDD : un INSERT a été appelé avec le username
    cursor.execute.assert_called_once()
    args, _ = cursor.execute.call_args
    sql, params = args
    assert "INSERT INTO users" in sql
    assert "ON DUPLICATE KEY UPDATE" in sql
    assert params[0] == "michel.ranu"
    assert isinstance(params[1], str) and params[1] != "michel.ranu"  # chiffré, pas le username
    conn.commit.assert_called_once()


def test_handler_encrypts_password_before_storage(load_function, mock_pymysql):
    main = load_function("generate-password")
    _, cursor = mock_pymysql

    client = TestClient(main.app)
    client.post("/", json={"username": "alice"})

    _, params = cursor.execute.call_args[0]
    encrypted_password = params[1]
    # Fernet : token base64 url-safe, commence toujours par 'gAAAAA' (version 0x80 + timestamp).
    assert encrypted_password.startswith("gAAAAA")


def test_handler_rolls_back_on_db_error(load_function, mock_pymysql):
    main = load_function("generate-password")
    conn, cursor = mock_pymysql
    cursor.execute.side_effect = RuntimeError("BDD down")

    client = TestClient(main.app)
    response = client.post("/", json={"username": "bob"})

    assert response.status_code == 500
    conn.rollback.assert_called_once()
    conn.commit.assert_not_called()


def test_handler_rejects_empty_username(load_function):
    main = load_function("generate-password")
    client = TestClient(main.app)
    response = client.post("/", json={"username": ""})
    assert response.status_code == 422


def test_healthz(load_function):
    main = load_function("generate-password")
    client = TestClient(main.app)
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
