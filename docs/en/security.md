# Security

## Threat model (summary)

The COFRAP brief was explicitly reworked because of **compromised accounts caused by weak passwords and the absence of 2FA**. The design therefore targets:

1. Prevent weak passwords → mandatory 24-character random generation.
2. Enforce 2FA → activation in the same flow as account creation.
3. Limit the compromise window → automatic 6-month expiry.
4. Protect credentials at rest → Fernet encryption in the DB.
5. Reduce the network attack surface → functions invoked only through the OpenFaaS gateway.

Implemented on top of the brief, to stay healthy under load:
- **Application-level rate limiting** (slowapi, per-IP) on the 3 functions
- **`max_inflight` of-watchdog** (concurrent-request cap per pod)
- **DB timeouts** (connect / read / write) so stuck connections are released quickly

Out of PoC scope (handled by another team per the brief):
- Brute-force protection (server-side account lock-out after N failures — the frontend does a local lock-out)
- Anomaly detection (geo-IP, device fingerprint, etc.)
- WAF / anti-spam at the edge (Cloudflare, NGINX `limit_req`)

## Password generation

- **Fixed** length of 24 characters (per the brief).
- Alphabet: `string.ascii_letters + string.digits + "!@#$%^&*()-_=+[]{};:,.<>?/"` (≈ 89 symbols).
- Entropy source: [`secrets.choice`](https://docs.python.org/3/library/secrets.html) — CSPRNG (`os.urandom` underneath), not `random`.
- Complexity guarantee: reject and re-draw until all 4 classes (lower, upper, digit, special) are represented.

Effective entropy: ≈ 24 × log₂(89) ≈ **155 bits** — far beyond the 80 bits recommended by NIST SP 800-63B for a random secret.

## Encryption at rest

The two sensitive fields of the `users` table are encrypted with **Fernet** (`cryptography.fernet`):

- `password`: plaintext password (before single-use QR transmission) → Fernet token.
- `mfa`: base32 TOTP secret → Fernet token.

Fernet under the hood:
- AES-128-CBC for confidentiality
- HMAC-SHA256 for authenticity
- Embedded timestamp — useful to detect replays/suspicious decryptions (not exploited here).

The key (32 url-safe base64 bytes) lives only in the `encryption-key` OpenFaaS secret, read at runtime from `/var/openfaas/secrets/encryption-key` (tmpfs mount by OpenFaaS).

> **Losing the key = losing every account** encrypted with it. Back it up outside the cluster (corporate vault).

## Transmission of user secrets

- The **plaintext password** is never persisted nor logged. It leaves `generate-password` exactly once, encoded in a base64 PNG QR. The frontend must display it and prompt the user to scan it immediately, without showing it again.
- The **TOTP secret** leaves `generate-2fa` in two redundant forms (`otpauth://` URI + PNG QR). The URI contains the secret in clear text (base32) — that is the standard; security relies on the gateway's TLS channel.
- **TLS mandatory in production** on the OpenFaaS gateway (cert-manager + Let's Encrypt via `arkade install openfaas-ingress`).

## Rate limiting (slowapi)

Each function wires a [slowapi](https://github.com/laurentS/slowapi) `Limiter` + `SlowAPIMiddleware`. Past the per-IP quota the API answers `429 Too Many Requests` with `{"detail":"rate limit exceeded"}`.

Configured via environment variables (overridable without rebuilding the image):

| Variable             | Default      | Effect                                                                            |
|----------------------|--------------|-----------------------------------------------------------------------------------|
| `RATE_LIMIT`         | `120/minute` | Per-IP quota. slowapi syntax: `"<n>/<period>"` (`second`, `minute`, `hour`, `day`). |
| `RATE_LIMIT_ENABLED` | `true`       | Set to `false` to disable the middleware entirely (useful in tests).              |

Counting key: the IP is read primarily from the `X-Forwarded-For` header (first hop), otherwise via `slowapi.util.get_remote_address`. In-cluster, that means the **real client IP** is throttled even behind the OpenFaaS gateway and an NGINX/Traefik Ingress — provided the upstream reverse-proxy fills `X-Forwarded-For` (the standard case).

The `/healthz` endpoint is annotated `@limiter.exempt` — Kubernetes probes keep reaching it even under attack.

> **Limits of the implementation**: slowapi keeps the counter **in-memory per pod**. With multiple replicas, the effective quota is *(replicas) × RATE_LIMIT*. For a strict global quota, plug slowapi into a shared backend (Redis) or move the limit onto the Ingress / gateway.

## of-watchdog `max_inflight`

Each `Dockerfile` sets `ENV max_inflight="10"`: this is the **hard cap** on concurrent requests per pod. Beyond it, of-watchdog itself answers `429` — the Python function is not even called, which keeps the uvicorn queue from blowing up and the MariaDB connections from saturating.

Combined with the slowapi limit, you get two layers of protection:

1. **slowapi** filters bursts from a single IP (HTTP application layer).
2. **max_inflight** caps the actual load regardless of how many clients are involved.

## MariaDB timeouts

`db.py` passes the following three timeouts to `pymysql.connect()` (overridable via env, values in seconds):

| Variable             | Default | Effect                                                       |
|----------------------|---------|--------------------------------------------------------------|
| `DB_CONNECT_TIMEOUT` | `5`     | Max time to establish the TCP/SSL connection                 |
| `DB_READ_TIMEOUT`    | `10`    | Max time to receive a query response                         |
| `DB_WRITE_TIMEOUT`   | `10`    | Max time to send a query                                     |

Practical effect: if MariaDB is slow, frozen or loses the connection, the function returns an error **within seconds** instead of waiting forever and blocking a `max_inflight` slot.

## CORS

All 3 functions enable FastAPI's `CORSMiddleware` so the frontend (served from a different origin) can call them from the browser. Origins are driven by `CORS_ALLOW_ORIGINS` (`*` by default, or an explicit comma-separated list).

- The API **uses no cookies**: authentication goes through the JSON body. `allow_credentials` is therefore disabled — which avoids the "`*` + credentials" pitfall forbidden by the CORS spec.
- In **production**, restrict `CORS_ALLOW_ORIGINS` to the real frontend origin (e.g. `https://app.cofrap.example.com`) rather than `*`.
- CORS is a **browser-side** protection, not a server access control: it replaces neither authentication nor rate limiting. A non-browser client (curl, script) ignores CORS entirely.

## 6-month rotation

Implemented inside the `authenticate-user` function, not via a cron job:

```python
SIX_MONTHS_SECONDS = 60 * 60 * 24 * 30 * 6  # ≈ 15,552,000 s

if now - gendate > SIX_MONTHS_SECONDS or expired:
    UPDATE users SET expired = 1 WHERE username = ...
    return { authenticated: false, expired: true, action: "regenerate_password_and_2fa" }
```

Benefits:
- No dependency on an external scheduler.
- The check is *effective at the moment it is consumed*: an expired account that is never used stays at `expired = 0`, which is consistent (nothing to regenerate if the user never logs in again).

The `EXPIRY_SECONDS` environment variable overrides the window for testing (useful to demonstrate the expired scenario without waiting 6 months).

## Secret storage and access

| Secret              | Target storage                              | Read by                          |
|---------------------|----------------------------------------------|-----------------------------------|
| `encryption-key`    | OpenFaaS secret (mounted at `/var/openfaas/secrets/`) | `crypto.py` at the start of a request |
| `mariadb-password`  | OpenFaaS secret                              | `db.py` on every connection       |
| MariaDB credentials | Kubernetes `Secret` `mariadb-credentials`    | The MariaDB pod (`envFrom`)       |

No secret is committed — see [`deploy/mariadb/secret.yaml`](../../deploy/mariadb/secret.yaml) which contains **placeholders to edit** before `kubectl apply`.

The `_read_secret(name)` pattern (see `functions/*/crypto.py`):
1. Reads `/var/openfaas/secrets/<name>` if present (OpenFaaS prod case).
2. Otherwise falls back to the `<NAME_IN_SNAKE_UPPER>` environment variable (local dev or CI case).

## Containers

- Minimal `slim` Python image.
- Non-root user (UID `10001`) — created in the `Dockerfile`, declared numerically so Kubelet can enforce `runAsNonRoot`.
- Docker `HEALTHCHECK` on `/healthz` (not used by Kubernetes but handy with a direct `docker run`).
- of-watchdog in HTTP mode — no fork-exec per request, better performance and easier to audit.

## Libraries

Versions are pinned in each `requirements.txt`. To audit periodically:

```bash
pip-audit -r functions/generate-password/requirements.txt
```

`pip-audit` is not in the CI yet — an improvement point documented in [`adr/`](adr/).

## Recommendations for production

Beyond the PoC scope:

1. Back slowapi with a **shared store** (Redis) so the rate-limit becomes global across replicas, or move the limit onto the Ingress / OpenFaaS gateway.
2. Enable mTLS between the functions and MariaDB.
3. Move the Fernet key into a **managed KMS** (AWS KMS, GCP KMS, Azure Key Vault, HashiCorp Vault) rather than a K8s secret.
4. Application audit log (who authenticated, success/failure, IP) with appropriate retention.
5. Adversarial testing (OWASP ZAP, Burp) on the exposed gateway.
6. Re-enable supply-chain attestations (`provenance: true` + `sbom: true`) once a registry that supports OCI attestations is in place — currently disabled on GHCR because they introduce `unknown/unknown` entries in the architecture list (see [`deployment.md`](deployment.md)).
