import os

from cryptography.fernet import Fernet


def _read_secret(name: str) -> str | None:
    path = f"/var/openfaas/secrets/{name}"
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            return fh.read().strip()
    return os.getenv(name.upper().replace("-", "_"))


def _cipher() -> Fernet:
    key = _read_secret("encryption-key")
    if not key:
        raise RuntimeError("encryption-key secret is missing")
    return Fernet(key.encode())


def encrypt(plaintext: str) -> str:
    return _cipher().encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    return _cipher().decrypt(ciphertext.encode()).decode()
