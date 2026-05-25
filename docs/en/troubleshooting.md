# Troubleshooting

## Tests

### `pytest` reports `OperationalError: Access denied for user 'cofrap'@'…'`

MariaDB is running but the credentials don't match. Check that `docker-compose.yml` started with the expected defaults:

```bash
docker compose down -v          # also removes the volume → clean recreation
docker compose up -d
```

The `mariadb_data` volume is persistent: if you change `MARIADB_PASSWORD` in `docker-compose.yml`, the application user keeps the old password until the volume is deleted.

### Integration tests are silently skipped

This is intentional. `tests/integration/conftest.py` detects whether MariaDB is unreachable (`connect_timeout=2`) and excludes the `tests/integration/` folder from collection. Run `docker compose up -d` then `pytest -m integration` to make them appear.

### `RuntimeError: encryption-key secret is missing`

The function finds neither the `/var/openfaas/secrets/encryption-key` file nor the `ENCRYPTION_KEY` environment variable. Locally:

```bash
python -c "from cryptography.fernet import Fernet; print('ENCRYPTION_KEY=' + Fernet.generate_key().decode())" >> .env
```

Then reload the env (`source .env` / `Get-Content .env | ...`).

## Build / Docker

### `faas-cli up` fails with `denied: requested access to the resource is denied`

Not authenticated to the registry. For GHCR:

```bash
echo $GHCR_PAT | docker login ghcr.io -u <your-handle> --password-stdin
```

The PAT must have the `write:packages` scope (classic PAT or fine-grained with "Packages: read & write"). On the CI side, the workflows use a `GHCR_PAT_TOKEN` secret (a custom PAT — not `GITHUB_TOKEN`, refused by some orgs' GHCR policy and blocked anyway: GitHub forbids creating secrets prefixed with `GITHUB_`).

### GHCR: `denied` / `unauthorized` on `docker pull` even though the release succeeded

The repo can be public while the OCI **package** is not. Go to `https://github.com/orgs/<org>/packages/container/<function>/settings` → **Change package visibility** → Public. Do this for each of the 3 functions after the **first push**.

### Image too large

The `slim` Python image + dependencies weighs ~150 MB. To go further: switch to `python:3.12-alpine` (but beware deps with C extensions, e.g. `cryptography` needs alpine wheels or a long build).

## Kubernetes deployment

### Functions in `ErrImagePull` / `ImagePullBackOff`

The `ghcr.io/cofrap-epsi-2026/<function>:<version>` images are only published on a **git tag `v*.*.*`** (via the [`release.yml`](../../.github/workflows/release.yml) workflow). On a fork, or before pushing a tag, those images don't exist → ImagePullBackOff when the pods start.

Build locally and load into the cluster:

```bash
# Linux / WSL / Git Bash
./scripts/prod/build-images.sh

# Windows PowerShell
./scripts/prod/build-images.ps1
```

The script auto-detects minikube / K3s / K3d / KinD and uses the right mechanism (`docker-env` for minikube, `k3s ctr images import` for K3s, `kind load`, etc.).

Then apply the new image policy:

```bash
helm upgrade cofrap ./deploy/helm/cofrap -n cofrap --reuse-values \
  --set functions.pullPolicy=IfNotPresent
kubectl -n openfaas-fn rollout restart deployment -l 'faas_function'
```

For a remote cluster, push to your own registry:

```bash
REGISTRY=ghcr.io/my-org PUSH=1 ./scripts/prod/build-images.sh
# then
helm upgrade cofrap ./deploy/helm/cofrap -n cofrap --reuse-values \
  --set functions.registry=ghcr.io/my-org
```

### The MariaDB pod stays `Pending`

Likely a `StorageClass` issue. On a custom cluster:

```bash
kubectl get sc
# If none is marked (default), create a PV manually or install local-path-provisioner
kubectl apply -f https://raw.githubusercontent.com/rancher/local-path-provisioner/master/deploy/local-path-storage.yaml
kubectl patch storageclass local-path -p '{"metadata": {"annotations":{"storageclass.kubernetes.io/is-default-class":"true"}}}'
```

### A function returns 502 / `failed to read upstream`

The function pod takes time to start (cold start). Raise the timeouts in `stack.yml`:

```yaml
environment:
  read_timeout: 60s
  write_timeout: 60s
  exec_timeout: 60s
```

On the OpenFaaS gateway side, check `gateway.upstreamTimeout` (Helm value).

### Gateway replies `error finding function <name>.openfaas-fn` (404)

The functions are not discovered by the gateway. In OpenFaaS Community, discovery happens via Deployments + Services in `openfaas-fn` labelled `faas_function=<name>`.

Check the resources:

```bash
kubectl -n openfaas-fn get deploy,svc,pods -l 'faas_function'
# If empty → the cofrap chart was not (correctly) applied.
```

Re-deploy the chart:

```bash
./scripts/prod/install.sh                     # Linux / WSL / Git Bash
./scripts/prod/install.ps1                    # Windows PowerShell

# or directly:
helm upgrade --install cofrap deploy/helm/cofrap \
  --namespace cofrap --reuse-values --wait
```

Once the pods are `Running`, the gateway lists them automatically:

```bash
PASSWORD=$(kubectl -n openfaas get secret basic-auth -o jsonpath='{.data.basic-auth-password}' | base64 -d)
curl -s -u admin:$PASSWORD http://127.0.0.1:8080/system/functions | jq '.[].name'
# "generate-password"
# "generate-2fa"
# "authenticate-user"
```

> **Healthcheck path**: it is `/healthz` (with `z`, defined on the FastAPI side), not `/health`. The internal of-watchdog path `/_/health` is exposed internally for K8s probes, not via the gateway.

```bash
curl -s http://127.0.0.1:8080/function/generate-password/healthz
# {"status":"ok"}
```

### Helm error `enabling 'operator.create' is only supported for OpenFaaS Pro`

The `operator.create=true` option of the `openfaas/openfaas` chart is reserved for the Pro version. **Do not pass it in Community.**

The `cofrap` chart does not depend on the operator — it deploys functions as plain K8s Deployments with the `faas_function=<name>` label, the native mechanism of the Community gateway.

If a previous `helm upgrade ... --set operator.create=true` failed, the existing OpenFaaS install is intact. To cleanly reinstall the functions, just rerun the script:

```bash
./scripts/prod/install.sh -SkipOpenFaaS    # Windows: ./scripts/prod/install.ps1 -SkipOpenFaaS
```

### `pymysql.err.OperationalError: (2003, "Can't connect to MySQL server")`

The cluster's internal DNS is not reachable from the `openfaas-fn` namespace. Check:

```bash
kubectl -n openfaas-fn run debug --rm -it --image=busybox -- sh
# Inside the pod:
nslookup mariadb.cofrap.svc.cluster.local
```

If resolution fails, check that CoreDNS is running (`kubectl -n kube-system get pods -l k8s-app=kube-dns`).

## API

### `422 Unprocessable Entity` on every request

Pydantic validation rejected the payload. The response contains the detail:

```json
{"detail": [{"loc": ["body", "otp"], "msg": "String should match pattern '^\\d{6}$'", "type": "string_pattern_mismatch"}]}
```

Check that `Content-Type: application/json` is sent and that the JSON is valid.

### `429 Too Many Requests` — `{"detail":"rate limit exceeded"}`

The slowapi rate-limit (see [`security.md`](security.md)) kicked in. Default quota: `120/minute` per IP. Three knobs:

```bash
# Raise the quota (e.g. 600/minute)
helm upgrade cofrap deploy/helm/cofrap --reuse-values \
  --set functions.env.RATE_LIMIT="600/minute"

# Disable entirely (handy for load tests)
helm upgrade cofrap deploy/helm/cofrap --reuse-values \
  --set functions.env.RATE_LIMIT_ENABLED=false

# Locally (docker-compose): add to .env
RATE_LIMIT=600/minute
```

If the `429` actually comes from **of-watchdog** (not slowapi), it means `max_inflight` (default `10`) was reached — the function is saturated by concurrent requests. Telltale: no `detail: "rate limit exceeded"` in the body (of-watchdog returns a plaintext response). Fixes: scale the Deployment (`kubectl -n openfaas-fn scale deploy <fn> --replicas=3`) or raise `max_inflight` (at the cost of more open MariaDB connections).

### The generated QR code yields an unreadable password / decryption fails

Most likely `ENCRYPTION_KEY` changed between insertion and reading. Check:

```bash
faas-cli secret list   # last update date
```

If the key was regenerated by mistake, every existing account must be recreated (`generate-password` + `generate-2fa`).

### `authenticate-user` returns `expired` although the account was just created

Check the cluster clock vs the client machine. The TOTP validity window is 30 s ± 1 (see `valid_window=1` in `pyotp.TOTP.verify`). A clock drift over 30 s makes the TOTP code fail. Common causes: paused VM, NTP not configured on the nodes.

## GitHub Actions CI

### The `release.yml` workflow fails with `Resource not accessible by integration`

Missing GHCR permissions. Check the top of the workflow:

```yaml
permissions:
  contents: read
  packages: write
```

And that the repo has `Settings → Actions → Workflow permissions: Read and write`.

### Buildx cache invalidated on every run

`cache-from: type=gha,scope=<function>` must use the same `scope` value between runs. Check there is no interpolated variable (e.g. `${{ github.run_id }}`) in the scope.
