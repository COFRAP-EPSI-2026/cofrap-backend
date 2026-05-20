# Deployment

> **Quickstart**: the recommended procedure (a script orchestrating OpenFaaS + the `cofrap` Helm chart) lives in [`installation.md`](installation.md). This document details the manual steps for when you want to understand / customise / debug what the script does.

## Prerequisites

- Kubernetes cluster (K3s, minikube, KinD or cloud GKE/AKS/EKS/Kapsule)
- [Helm](https://helm.sh/docs/intro/install/) (to install OpenFaaS)
- [`faas-cli`](https://docs.openfaas.com/cli/install/)
- `kubectl` configured against the target cluster

## 1. Install OpenFaaS Community

```bash
# via Helm:
helm repo add openfaas https://openfaas.github.io/faas-netes/
kubectl create namespace openfaas
kubectl create namespace openfaas-fn
helm install openfaas openfaas/openfaas --namespace openfaas --set functionNamespace=openfaas-fn

# Retrieve the admin password and log faas-cli in
PASSWORD=$(kubectl -n openfaas get secret basic-auth -o jsonpath='{.data.basic-auth-password}' | base64 -d)
kubectl port-forward -n openfaas svc/gateway 8080:8080 & echo "$PASSWORD" | faas-cli login -u admin --password-stdin
```

## 2. Deploy the stack (recommended: Helm chart)

A single Helm chart — [`deploy/helm/cofrap`](../../deploy/helm/cofrap) — deploys MariaDB, creates the OpenFaaS secrets in `openfaas-fn` and the 3 functions (Deployment + Service each). Full procedure: [`installation.md`](installation.md).

```bash
ENCRYPTION_KEY="$(python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"
MARIADB_PASSWORD="$(openssl rand -hex 16)"
MARIADB_ROOT_PASSWORD="$(openssl rand -hex 16)"

helm upgrade --install cofrap deploy/helm/cofrap \
  --namespace cofrap --create-namespace \
  --set secrets.encryptionKey="$ENCRYPTION_KEY" \
  --set secrets.mariadbPassword="$MARIADB_PASSWORD" \
  --set secrets.mariadbRootPassword="$MARIADB_ROOT_PASSWORD" \
  --wait
```

Verification:

```bash
kubectl -n cofrap get pods,svc,pvc
kubectl -n openfaas-fn get deploy,svc -l faas_function
curl -s http://127.0.0.1:8080/function/generate-password/healthz   # after port-forward
```

## 2b. Alternative: manual deployment without Helm

If you prefer plain `kubectl apply` (or you don't have Helm), the raw manifests live in [`deploy/mariadb/`](../../deploy/mariadb/):

```bash
kubectl apply -f deploy/mariadb/namespace.yaml
# Edit secret.yaml BEFOREHAND to set real passwords
kubectl apply -f deploy/mariadb/secret.yaml
kubectl apply -f deploy/mariadb/configmap-init.yaml
kubectl apply -f deploy/mariadb/service.yaml
kubectl apply -f deploy/mariadb/statefulset.yaml
```

Then create the OpenFaaS secrets and deploy the functions via `faas-cli`:

```bash
faas-cli secret create mariadb-password --from-literal "$MARIADB_PASSWORD"
faas-cli secret create encryption-key   --from-literal "$ENCRYPTION_KEY"
faas-cli up -f stack.yml
```

> **Keep `ENCRYPTION_KEY` safe**: if it is lost, every password and TOTP secret encrypted in the DB becomes unreadable. Store it in a vault (Vault, Doppler, AWS Secrets Manager, etc.).

## Deployment variants

### Baremetal cluster with K3s

K3s ships a load balancer (`svclb`) and a Traefik ingress out of the box.

```bash
curl -sfL https://get.k3s.io | sh -
sudo cat /etc/rancher/k3s/k3s.yaml > ~/.kube/config  # adjust permissions
arkade install openfaas
```

On the MariaDB side, the `StatefulSet` uses the `local-path` `StorageClass` provided by K3s by default, so no extra config is needed for a PoC.

### Managed cloud (GKE/AKS/EKS)

- Provision a minimal cluster (2 nodes, 2 vCPU / 4 GB each is enough)
- `arkade install openfaas`
- To expose the gateway over HTTPS: `arkade install openfaas-ingress` (cert-manager + Let's Encrypt)

### No cluster: minikube or Docker

The PoC also runs on minikube. For the DB, either MariaDB via `StatefulSet` (same manifests), or the root `docker-compose.yml` if you run the functions outside Kubernetes (for debugging).

## Environment variables

Everything that is not a secret is set in `stack.yml` (`environment:` per function):

| Variable           | Default                             | Effect                                              |
|--------------------|-------------------------------------|-----------------------------------------------------|
| `DB_HOST`          | `mariadb.cofrap.svc.cluster.local`  | MariaDB hostname                                    |
| `DB_PORT`          | `3306`                              | Port                                                |
| `DB_NAME`          | `cofrap`                            | Database                                            |
| `DB_USER`          | `cofrap`                            | Application user (not root!)                        |
| `TOTP_ISSUER`      | `COFRAP`                            | Name shown in Google Authenticator                  |
| `EXPIRY_SECONDS`   | `15552000` (6 months)               | Validity window — lower it to test expiry           |
| `CORS_ALLOW_ORIGINS` | `*`                               | Origins allowed to call the API from a browser — `*` or a comma-separated list |
| `read_timeout`/`write_timeout`/`exec_timeout` | `30s`     | of-watchdog limits                                  |

## Updates

- **Hotfix a single function**: `faas-cli up --filter generate-password` (build + push + deploy of one function only).
- **`ENCRYPTION_KEY` rotation**: Fernet supports multi-key rotation. For the current PoC this is a manual operation (decrypt with the old key, re-encrypt with the new one, overwrite the OpenFaaS secret). To be industrialised if the product goes to production.
- **DB schema**: no migrations for this PoC (a single frozen table). If it evolves, add [Alembic](https://alembic.sqlalchemy.org/) or versioned SQL scripts.

## CI/CD

→ The GitHub Actions pipeline is documented in the CI/CD section of the [root README](../../README.md#cicd) and coded in [`.github/workflows/`](../../.github/workflows/).

On a `v*.*.*` tag, the `release.yml` workflow:
1. Replays the full CI suite (lint + tests)
2. Builds the 3 multi-arch images (amd64 + arm64)
3. Pushes to `ghcr.io/<org>/<function>:<version>` with SBOM and provenance attestation

Deployment to the cluster stays **manual** (`faas-cli up` or `helm upgrade`) — consistent with a PoC where each release is validated by the team before going live.
