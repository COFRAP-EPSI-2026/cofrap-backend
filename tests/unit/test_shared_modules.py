"""Tests des modules partagés (db, crypto, qr) — appliqués sur la copie de generate-password.

Les 3 fonctions hébergent une copie identique de ces utilitaires ;
les tester via une fonction suffit à valider le contrat.
"""

from __future__ import annotations

import base64

import pytest

pytestmark = pytest.mark.unit


def test_crypto_roundtrip(load_function):
    load_function("generate-password")
    import crypto

    cipher_text = crypto.encrypt("hello world")
    assert cipher_text.startswith("gAAAAA")
    assert crypto.decrypt(cipher_text) == "hello world"


def test_crypto_missing_key_raises(monkeypatch, load_function):
    monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
    load_function("generate-password")
    import crypto

    with pytest.raises(RuntimeError, match="encryption-key"):
        crypto.encrypt("x")


def test_qr_make_returns_png_base64(load_function):
    load_function("generate-password")
    import qr

    encoded = qr.make_qr_png_base64("hello")
    raw = base64.b64decode(encoded)
    assert raw.startswith(b"\x89PNG\r\n\x1a\n")


def test_secret_file_takes_precedence_over_env(tmp_path, monkeypatch, load_function):
    """Quand `/var/openfaas/secrets/<name>` existe, sa valeur écrase la variable d'env."""
    load_function("generate-password")
    import crypto

    secret_file = tmp_path / "encryption-key"
    secret_file.write_text("file-value", encoding="utf-8")

    real_open = open
    real_exists = crypto.os.path.exists
    target_path = "/var/openfaas/secrets/encryption-key"

    def fake_exists(path: str) -> bool:
        return True if path == target_path else real_exists(path)

    def fake_open(path, *args, **kwargs):
        if path == target_path:
            return real_open(secret_file, *args, **kwargs)
        return real_open(path, *args, **kwargs)

    monkeypatch.setattr(crypto.os.path, "exists", fake_exists)
    monkeypatch.setattr("builtins.open", fake_open)

    assert crypto._read_secret("encryption-key") == "file-value"


def test_read_secret_falls_back_to_env(monkeypatch, load_function):
    monkeypatch.setenv("ENCRYPTION_KEY", "env-value")
    load_function("generate-password")
    import crypto

    # Pas de fichier dans /var/openfaas/secrets/, donc fallback env var.
    assert crypto._read_secret("encryption-key") == "env-value"


def test_read_secret_returns_none_when_missing(monkeypatch, load_function):
    monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
    load_function("generate-password")
    import crypto

    assert crypto._read_secret("encryption-key") is None
