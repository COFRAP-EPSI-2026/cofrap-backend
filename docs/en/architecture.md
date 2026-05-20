# Architecture

## Overview

The PoC implements the lifecycle of a COFRAP user account:

1. Account creation → 24-character password, transmitted **once** via QR code.
2. 2FA activation → TOTP secret, also transmitted via QR code.
3. Authentication → password + TOTP code, with **automatic 6-month expiry**.

Everything runs **serverless** (OpenFaaS Community) on Kubernetes, with MariaDB for persistence.

```
┌─────────────┐    HTTP/JSON    ┌──────────────────┐    SQL (optional TLS)    ┌────────────┐
│ Frontend    │ ───────────────►│ OpenFaaS Gateway │ ────────────────────────►│  MariaDB   │
│ (TypeScript)│                 │   (Kubernetes)   │                           │ StatefulSet│
└─────────────┘                 │                  │                           └────────────┘
                                │  ├─ generate-password
                                │  ├─ generate-2fa
                                │  └─ authenticate-user
                                └──────────────────┘
                                        ▲
                                        │  OpenFaaS secrets (/var/openfaas/secrets/)
                                        │   ├─ mariadb-password
                                        │   └─ encryption-key (Fernet)
```

## Technical choices

| Choice                   | Decision                              | Rationale                                                                                  |
|--------------------------|---------------------------------------|--------------------------------------------------------------------------------------------|
| Backend language         | **Python 3.12**                       | Recommended by the COFRAP brief; mature ecosystem for crypto/QR/TOTP                        |
| HTTP framework           | **FastAPI** + Uvicorn (ASGI)          | Free Pydantic validation, auto OpenAPI, ASGI performance                                   |
| Serverless runtime       | **OpenFaaS Community** + of-watchdog  | Mandated by the brief; `Scale to Zero` aligned with the cost-saving goal                   |
| Containers               | Slim Python image + of-watchdog HTTP  | Documented standard; lets FastAPI/Uvicorn run as the upstream                              |
| Database                 | **MariaDB 11** (K8s StatefulSet)      | SQL recommended by the client; simple, robust, flat single-table schema                    |
| Python driver            | **PyMySQL** (pure Python)             | No native dependency → slim Python image, fast CI build                                    |
| Application encryption   | **Fernet** (`cryptography`)           | Authenticated AES-128-CBC + HMAC-SHA256, simple API, multi-key rotation possible           |
| TOTP generation          | **pyotp**                             | RFC 6238 implementation compatible with Google Authenticator/Authy                         |
| QR code generation       | **qrcode** + PIL                      | base64 PNG returned in the JSON response — the frontend handles rendering                  |
| Frontend                 | **TypeScript** (separate repo)        | Requested choice; PoC: just enough UI to demonstrate the flow                              |

## Nominal flow for a new user

```
Frontend                generate-password           generate-2fa          authenticate-user           MariaDB
   │                          │                          │                          │                    │
   │── POST /username ───────►│                          │                          │                    │
   │                          │── INSERT user (enc pwd) ─────────────────────────────────────────────────►│
   │◄── QR PNG (24-char pwd) ─│                          │                          │                    │
   │                          │                          │                          │                    │
   │── POST /username ───────────────────────────────────►                          │                    │
   │                          │                          │── UPDATE mfa = enc(totp) ────────────────────►│
   │◄── QR PNG (otpauth:// ) ─────────────────────────────│                          │                    │
   │                          │                          │                          │                    │
   │── login + pwd + otp ─────────────────────────────────────────────────────────►│                    │
   │                          │                          │                          │── SELECT user ────►│
   │                          │                          │                          │◄── row ────────────│
   │◄── { authenticated: true } ──────────────────────────────────────────────────│                    │
```

## Expired account flow

```
... 6 months later ...
   │── login + pwd + otp ────────────────────────────────►│
   │                                                       │── SELECT user
   │                                                       │   now - gendate > 6 months → UPDATE expired = 1
   │◄── { authenticated: false, expired: true,             │
   │     action: "regenerate_password_and_2fa" } ─────────│
   │
   │── POST /username → generate-password ► restart the cycle
```

## Data model

A single table — `users` — strictly compliant with the brief's schema:

```sql
CREATE TABLE users (
    id       INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(255) NOT NULL UNIQUE,
    password TEXT NULL,        -- Fernet-encrypted (never plaintext)
    mfa      TEXT NULL,        -- Fernet-encrypted TOTP secret
    gendate  BIGINT NOT NULL,  -- Unix generation timestamp
    expired  TINYINT(1) NOT NULL DEFAULT 0,
    INDEX idx_username (username),
    INDEX idx_expired_gendate (expired, gendate)
);
```

Why no extra columns? The brief mandates this minimal schema. Any enrichment (last_login, fail_count, audit log) is out of the PoC's scope.

## Structural decisions

- **No 6-month rotation cron**. The `authenticate-user` function is the single control point: on every login it compares `now - gendate` against the 6-month window. Benefit: no dependency on an external scheduler, state is consistent at the moment it is consumed.
- **`generate-2fa` performs an UPDATE, not an INSERT**. A TOTP secret only makes sense for an existing account. If the user does not exist → explicit 404, the frontend must call `generate-password` first.
- **The plaintext password is exposed only once**, in the QR-scan response. No application log must ever contain it.
- **A copy of the shared modules (`db.py`, `crypto.py`, `qr.py`) in each function**, rather than a shared package. Reason: each OpenFaaS function builds its own image with its standalone `Dockerfile`. The duplication cost (≈ 40 lines × 3) is lower than managing a shared build context or a private package.

→ More details in [`adr/`](adr/).
