"""Fixtures partagées : isolation des imports par fonction OpenFaaS + secrets de test."""

from __future__ import annotations

import importlib
import os
import sys
from collections.abc import Callable
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from cryptography.fernet import Fernet

ROOT = Path(__file__).resolve().parents[1]
FUNCTIONS = ROOT / "functions"
SHARED_MODULES = ("main", "db", "crypto", "qr")

# Valeurs par défaut alignées sur docker-compose.yml local. La CI / un `.env`
# peuvent les écraser en exportant les variables avant `pytest`.
_DEFAULT_ENV = {
    "MARIADB_PASSWORD": "cofrap_dev",
    "DB_HOST": "127.0.0.1",
    "DB_PORT": "3306",
    "DB_NAME": "cofrap",
    "DB_USER": "cofrap",
    "RATE_LIMIT_ENABLED": "0",
}


@pytest.fixture(scope="session")
def fernet_key() -> str:
    """Clé Fernet stable pour toute la session — évite de régénérer à chaque test.
    Si ENCRYPTION_KEY est déjà dans l'env, on l'utilise pour rester cohérent.
    """
    return os.getenv("ENCRYPTION_KEY") or Fernet.generate_key().decode()


@pytest.fixture(autouse=True)
def base_env(monkeypatch: pytest.MonkeyPatch, fernet_key: str) -> None:
    """Fournit les secrets via env vars (fallback de `_read_secret`).

    Ne touche pas une variable déjà définie : la CI et `.env` priment.
    """
    if not os.getenv("ENCRYPTION_KEY"):
        monkeypatch.setenv("ENCRYPTION_KEY", fernet_key)
    for key, value in _DEFAULT_ENV.items():
        if not os.getenv(key):
            monkeypatch.setenv(key, value)


@pytest.fixture
def load_function(monkeypatch: pytest.MonkeyPatch) -> Callable[[str], object]:
    """Charge le module `main` d'une fonction OpenFaaS en isolant les noms partagés.

    Comme les 3 fonctions ont chacune un fichier `main.py`/`db.py`/`crypto.py`/`qr.py`,
    on purge `sys.modules` et on prepend le path de la fonction demandée avant import.
    `monkeypatch.syspath_prepend` nettoie le path à la fin du test.
    """

    def _load(function_name: str):
        function_dir = FUNCTIONS / function_name
        if not function_dir.is_dir():
            raise FileNotFoundError(function_dir)
        monkeypatch.syspath_prepend(str(function_dir))
        for mod_name in SHARED_MODULES:
            monkeypatch.delitem(sys.modules, mod_name, raising=False)
        return importlib.import_module("main")

    return _load


@pytest.fixture
def mock_pymysql(monkeypatch: pytest.MonkeyPatch) -> tuple[MagicMock, MagicMock]:
    """Patch `pymysql.connect` pour renvoyer une connexion/cursor mockés.

    Retourne `(connection_mock, cursor_mock)`. Le cursor supporte le context manager.
    """
    import pymysql  # noqa: F401  (s'assurer qu'il est importable)

    cursor = MagicMock(name="cursor")
    cursor.__enter__ = MagicMock(return_value=cursor)
    cursor.__exit__ = MagicMock(return_value=False)
    cursor.rowcount = 1

    conn = MagicMock(name="connection")
    conn.cursor.return_value = cursor

    monkeypatch.setattr("pymysql.connect", lambda *args, **kwargs: conn)
    return conn, cursor
