import os

import pymysql


def _read_secret(name: str) -> str | None:
    path = f"/var/openfaas/secrets/{name}"
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            return fh.read().strip()
    return os.getenv(name.upper().replace("-", "_"))


def get_connection() -> pymysql.connections.Connection:
    password = _read_secret("mariadb-password")
    if password is None:
        raise RuntimeError("mariadb-password secret is missing")
    return pymysql.connect(
        host=os.getenv("DB_HOST", "mariadb"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER", "cofrap"),
        password=password,
        database=os.getenv("DB_NAME", "cofrap"),
        charset="utf8mb4",
        autocommit=False,
    )
