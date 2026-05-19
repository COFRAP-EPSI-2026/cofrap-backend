"""Fixtures pour les tests d'intégration.

Ces tests requièrent une MariaDB accessible. En local :

    docker compose up -d mariadb

En CI, GitHub Actions monte un service `mariadb:11` via le workflow.

Variables d'env attendues (toutes fournies par défaut par la fixture `base_env`) :

- DB_HOST, DB_PORT, DB_NAME, DB_USER (cf. tests/conftest.py)
- MARIADB_PASSWORD (mot de passe de l'utilisateur applicatif)
"""

from __future__ import annotations

import os
from pathlib import Path

import pymysql
import pytest

ROOT = Path(__file__).resolve().parents[2]


def _conn_kwargs() -> dict:
    return dict(
        host=os.getenv("DB_HOST", "127.0.0.1"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER", "cofrap"),
        password=os.getenv("MARIADB_PASSWORD", "cofrap_dev"),
        database=os.getenv("DB_NAME", "cofrap"),
    )


def _is_mariadb_reachable() -> bool:
    try:
        conn = pymysql.connect(connect_timeout=2, **_conn_kwargs())
    except Exception:
        return False
    conn.close()
    return True


# Skip global si MariaDB n'est pas joignable — évite de casser le run unitaire local.
collect_ignore_glob = []
if not _is_mariadb_reachable():
    collect_ignore_glob = ["test_*.py"]


@pytest.fixture(scope="session", autouse=True)
def db_schema():
    """Crée la table `users` au début de la session d'intégration, et la vide à la fin."""
    conn = pymysql.connect(autocommit=True, **_conn_kwargs())
    init_sql = (ROOT / "deploy" / "init.sql").read_text(encoding="utf-8")
    with conn.cursor() as cur:
        for statement in init_sql.split(";"):
            stmt = statement.strip()
            if stmt and not stmt.upper().startswith(("USE ", "CREATE DATABASE")):
                cur.execute(stmt)
    yield
    with conn.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS users")
    conn.close()


@pytest.fixture(autouse=True)
def truncate_users():
    """Avant chaque test, on repart d'une table vide."""
    conn = pymysql.connect(autocommit=True, **_conn_kwargs())
    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE users")
    conn.close()
    yield


@pytest.fixture
def db_row():
    """Retourne une fonction qui lit une ligne `users` par username."""

    def _read(username: str) -> tuple | None:
        conn = pymysql.connect(**_conn_kwargs())
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT username, password, mfa, gendate, expired FROM users WHERE username = %s",
                    (username,),
                )
                return cur.fetchone()
        finally:
            conn.close()

    return _read
