# API Reference

Each function is invoked through the OpenFaaS gateway at `POST /function/<name>`. All responses are JSON, UTF-8 encoded.

Base URL: `{{gateway}}/function/`

> **Machine-readable contract**: [`openapi.yaml`](../openapi.yaml) (OpenAPI 3.1) — generated automatically from the FastAPI apps by [`scripts/generate-openapi.py`](../../scripts/generate-openapi.py). Open it in [Swagger Editor](https://editor.swagger.io/), [Redocly](https://redocly.github.io/redoc/) or any API client (Bruno, Postman, Insomnia) that supports OpenAPI import.

---

## `generate-password`

Generates a 24-character password (uppercase, lowercase, digits, special characters), encrypts it with Fernet and stores it in MariaDB. Returns the PNG QR code (base64) to be scanned to retrieve the plaintext password — **single-use transmission**.

If the user already exists (`ON DUPLICATE KEY UPDATE`), their password is regenerated and `expired` is reset to 0.

### Request

```
POST /function/generate-password
Content-Type: application/json

{
  "username": "michel.ranu"
}
```

### 200 Response

```json
{
  "username": "michel.ranu",
  "gendate": 1721916574,
  "qrcode_png_base64": "iVBORw0KGgoAAAANSUhEUg..."
}
```

| Code | Case                                               |
|------|----------------------------------------------------|
| 200  | OK                                                 |
| 422  | `username` empty or missing (Pydantic validation)  |
| 500  | DB error — the transaction is rolled back          |

### curl example

```bash
curl -s -X POST $GATEWAY/function/generate-password \
     -H 'Content-Type: application/json' \
     -d '{"username":"michel.ranu"}' \
  | jq -r .qrcode_png_base64 \
  | base64 -d > qr.png
```

---

## `generate-2fa`

Generates a base32 TOTP secret, encrypts it, associates it with the **existing** user, and returns the `otpauth://` URI + the QR code to scan with an authenticator app.

### Request

```
POST /function/generate-2fa
Content-Type: application/json

{
  "username": "michel.ranu"
}
```

### 200 Response

```json
{
  "username": "michel.ranu",
  "gendate": 1721916600,
  "otpauth_uri": "otpauth://totp/COFRAP:michel.ranu?secret=JBSWY3DPEHPK3PXP&issuer=COFRAP",
  "qrcode_png_base64": "iVBORw0KGgoAAAANSUhEUg..."
}
```

| Code | Case                                                                               |
|------|------------------------------------------------------------------------------------|
| 200  | OK                                                                                 |
| 404  | Unknown user (`generate-password` was not called first)                            |
| 422  | `username` empty or missing                                                        |
| 500  | DB error — the transaction is rolled back                                          |

The `issuer` shown in the authenticator app is configurable via the `TOTP_ISSUER` environment variable (default `COFRAP`).

---

## `authenticate-user`

Authenticates a user. Checks the account age before validating the password and the TOTP code.

### Request

```
POST /function/authenticate-user
Content-Type: application/json

{
  "username": "michel.ranu",
  "password": "p<...24 chars...>",
  "otp": "123456"
}
```

`otp` must match `^\d{6}$` — the check happens before any DB access.

### 200 Response — success

```json
{
  "authenticated": true,
  "expired": false,
  "username": "michel.ranu"
}
```

### 200 Response — expired account

Returns a 200 (not an error) with an explicit instruction for the frontend:

```json
{
  "authenticated": false,
  "expired": true,
  "action": "regenerate_password_and_2fa"
}
```

The `expired` flag is set to 1 in the DB in the process. The frontend must then chain `generate-password` followed by `generate-2fa`.

### Other codes

| Code | Case                                                             |
|------|------------------------------------------------------------------|
| 401  | Invalid password or OTP (`detail` indicates which)               |
| 404  | Unknown user                                                     |
| 409  | Incomplete account (`password` or `mfa` `NULL` in the DB)        |
| 422  | Pydantic validation (OTP < 6 digits or non-numeric, etc.)        |
| 500  | Internal error                                                   |

---

## Cross-cutting endpoints

Each function exposes `GET /healthz` returning `{"status": "ok"}`. This is the probe used by the Docker healthcheck in the `Dockerfile`.

---

## Testing the API

A complete Bruno collection is provided in [`bruno/`](../../bruno/) — nominal flow and error cases ready to use, with client-side TOTP computation to automate the authentication test.
