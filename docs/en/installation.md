# Step-by-step installation

Complete guide to deploy the COFRAP stack on **K3s**, **minikube** or an **existing K8s cluster**, reproducible on **Linux** and **Windows**.

Installation is orchestrated by a single Helm chart ([`deploy/helm/cofrap`](../../deploy/helm/cofrap)) and two bootstrap scripts: [`scripts/prod/install.sh`](../../scripts/prod/install.sh) (bash) and [`scripts/prod/install.ps1`](../../scripts/prod/install.ps1) (PowerShell). Both do exactly the same thing.

---

## Table of contents

- [Common prerequisites](#common-prerequisites)
- [Variant A — minikube (Windows or Linux)](#variant-a--minikube-windows-or-linux)
- [Variant B — K3s (Linux)](#variant-b--k3s-linux)
- [Variant C — Existing Kubernetes cluster](#variant-c--existing-kubernetes-cluster)
- [Verification](#verification)
- [Testing the API](#testing-the-api)
- [Uninstall](#uninstall)
- [What does the script actually do?](#what-does-the-script-actually-do)

---

## Common prerequisites

Install on your workstation, in this order:

| Tool        | Linux                                  | Windows                                                                 |
|-------------|----------------------------------------|-------------------------------------------------------------------------|
| `kubectl`   | `curl -LO https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl && sudo install kubectl /usr/local/bin/` | `winget install -e --id Kubernetes.kubectl` or via [chocolatey](https://chocolatey.org/) |
| `helm` ≥ 3  | `curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 \| bash` | `winget install -e --id Helm.Helm` |
| `python` 3.10+ (with `cryptography`) or `openssl` | already present on most distros | `winget install -e --id Python.Python.3.12` then `pip install cryptography` |
| A K8s cluster (see variants below) | -                                  | -                                                                       |

Verify:

```bash
kubectl version --client
helm version --short
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

---

## Variant A — minikube (Windows or Linux)

minikube is the fastest way to get a local cluster, identical on Windows and Linux.

### Installing minikube

| OS                | Command                                                                                 |
|-------------------|-----------------------------------------------------------------------------------------|
| **Linux**         | `curl -LO https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64 && sudo install minikube-linux-amd64 /usr/local/bin/minikube` |
| **Windows**       | `winget install -e --id Kubernetes.minikube`                                            |
| **macOS**         | `brew install minikube`                                                                 |

### Start the cluster

```bash
minikube start --cpus=2 --memory=4096 --disk-size=20g
kubectl get nodes   # should show 1 Ready node
```

> On Windows, if Docker Desktop is not installed, minikube uses Hyper-V or VirtualBox. For Hyper-V:
> ```powershell
> minikube start --driver=hyperv --memory=4096 --cpus=2
> ```

### Installing the stack

```bash
# Clone the repo if not done already
git clone https://github.com/COFRAP-EPSI-2026/cofrap-backend.git
cd cofrap-backend

# Linux / macOS / WSL / Git Bash
./scripts/prod/install.sh

# Windows PowerShell
./scripts/prod/install.ps1
```

The script:
1. Checks `kubectl` + `helm` + cluster access.
2. Installs OpenFaaS Community via Helm in the `openfaas` namespace.
3. Generates a Fernet key + two random MariaDB passwords.
4. Installs the `cofrap` chart (MariaDB + secrets + 3 OpenFaaS functions).
5. Prints the credentials and useful commands.

**Keep the script output** (the secrets will not be shown again).

---

## Variant B — K3s (Linux)

K3s is a lightweight Kubernetes distribution, ideal for a homelab or a VM.

### Installing K3s

```bash
# Install K3s + retrieve the kubeconfig
curl -sfL https://get.k3s.io | sh -

# Give your user access to the kubeconfig
sudo cp /etc/rancher/k3s/k3s.yaml ~/.kube/config
sudo chown $USER:$USER ~/.kube/config
chmod 600 ~/.kube/config

kubectl get nodes   # should show 1 Ready node
```

K3s already ships:
- a load balancer (`svclb`)
- a Traefik ingress
- a `local-path` storage provisioner (used automatically by the MariaDB PVC)

### Installing the stack

```bash
git clone https://github.com/COFRAP-EPSI-2026/cofrap-backend.git
cd cofrap-backend
./scripts/prod/install.sh
```

---

## Variant C — Existing Kubernetes cluster

For an already-provisioned K8s cluster (GKE/AKS/EKS/Kapsule, homelab, kubeadm…):

```bash
# If OpenFaaS is ALREADY installed, skip its install:
SKIP_OPENFAAS=1 ./scripts/prod/install.sh
# or with PowerShell
./scripts/prod/install.ps1 -SkipOpenFaaS

# Otherwise, the script handles OpenFaaS too:
./scripts/prod/install.sh
```

To customise:

```bash
NAMESPACE=cofrap-prod RELEASE_NAME=cofrap-prod ./scripts/prod/install.sh
```

Or directly with Helm for full control:

```bash
# Generate the secrets yourself
ENCRYPTION_KEY="$(python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"
MARIADB_PASSWORD="$(openssl rand -hex 16)"
MARIADB_ROOT_PASSWORD="$(openssl rand -hex 16)"

helm upgrade --install cofrap deploy/helm/cofrap \
  --namespace cofrap --create-namespace \
  --set secrets.encryptionKey="$ENCRYPTION_KEY" \
  --set secrets.mariadbPassword="$MARIADB_PASSWORD" \
  --set secrets.mariadbRootPassword="$MARIADB_ROOT_PASSWORD" \
  --set functions.registry=ghcr.io/<your-org> \
  --set functions.version=2026.2.0 \
  --set mariadb.persistence.storageClassName=longhorn \
  --wait
```

---

## Building images locally (if no release is published)

The chart points to `ghcr.io/cofrap-epsi-2026/<function>:<version>`, where `<version>` is `functions.version` from `values.yaml`. Those images only exist **once a git tag `vX.Y.Z` has been pushed** (the [`release.yml`](../../.github/workflows/release.yml) workflow builds and pushes them on that tag).

If you work on a fork or without having pushed a tag, you must build the images locally and make them available to the cluster. A script auto-detects your cluster type (minikube / K3s / K3d / KinD) and does the right import:

```bash
# Linux / macOS / WSL / Git Bash
./scripts/prod/build-images.sh

# Windows PowerShell
./scripts/prod/build-images.ps1
```

The script:
- detects the active local cluster,
- for **minikube**: points the Docker CLI at minikube's daemon before building,
- for **K3s**: `docker save | k3s ctr images import`,
- for **K3d**: `k3d image import`,
- for **KinD**: `kind load docker-image`,
- for a **remote cluster**: requires `-Push` + a reachable `-Registry ghcr.io/your-org`.

Once the build is done:

```bash
helm upgrade cofrap ./deploy/helm/cofrap -n cofrap --reuse-values \
  --set functions.pullPolicy=IfNotPresent
kubectl -n openfaas-fn rollout restart deployment -l faas_function
```

> `IfNotPresent` prevents K8s from trying to re-pull the image from GHCR (which doesn't exist) once it is in the local cluster.

## Verification

```bash
# cofrap pods (MariaDB)
kubectl -n cofrap get pods,svc,pvc

# OpenFaaS functions — Deployments + Services labelled `faas_function`
kubectl -n openfaas-fn get deploy,svc -l 'faas_function'
kubectl -n openfaas-fn get pods -l 'faas_function'
# NAME                                READY   STATUS    RESTARTS   AGE
# generate-password-xxxx-yyyy         1/1     Running   0          1m
# generate-2fa-xxxx-yyyy              1/1     Running   0          1m
# authenticate-user-xxxx-yyyy         1/1     Running   0          1m

# The gateway sees them too
curl -s -u admin:$OF_PASS http://127.0.0.1:8080/system/functions | jq '.[].name'
```

Expected state: one MariaDB pod `Running` + one pod per function `Running`.

---

## Testing the API

### Step 1 — port-forward the OpenFaaS gateway

```bash
kubectl -n openfaas port-forward svc/gateway 8080:8080
```

Leave it running in a separate terminal. The gateway is now reachable at `http://127.0.0.1:8080`.

### Step 2 — call the functions

```bash
# Healthcheck
curl -s http://127.0.0.1:8080/function/generate-password/healthz
# {"status":"ok"}

# Create an account
curl -s -X POST http://127.0.0.1:8080/function/generate-password \
     -H 'Content-Type: application/json' \
     -d '{"username":"michel.ranu"}' | jq

# Generate 2FA
curl -s -X POST http://127.0.0.1:8080/function/generate-2fa \
     -H 'Content-Type: application/json' \
     -d '{"username":"michel.ranu"}' | jq
```

Simpler: use the [Bruno collection](../../bruno/) with the `Local OpenFaaS Gateway` environment selected.

---

## Uninstall

```bash
# Linux / macOS / WSL
./scripts/prod/uninstall.sh                       # keeps OpenFaaS
PURGE_OPENFAAS=1 ./scripts/prod/uninstall.sh      # removes everything, OpenFaaS included

# Windows
./scripts/prod/uninstall.ps1
./scripts/prod/uninstall.ps1 -PurgeOpenFaaS
```

The script:
1. `helm uninstall cofrap`
2. Deletes the `mariadb-password` and `encryption-key` Secrets in `openfaas-fn`.
3. Deletes the MariaDB PVCs (otherwise the data persists).
4. Deletes the `cofrap` namespace.

---

## What does the script actually do?

Step by step, to understand what happens under the hood and be able to replay it by hand if needed:

### 1. Install OpenFaaS

```bash
helm repo add openfaas https://openfaas.github.io/faas-netes/
helm repo update
kubectl create namespace openfaas
kubectl create namespace openfaas-fn
helm upgrade --install openfaas openfaas/openfaas \
  --namespace openfaas \
  --set functionNamespace=openfaas-fn \
  --set generateBasicAuth=true \
  --wait --timeout 5m
```

> ℹ️ **Why not `operator.create=true`?** That option is reserved for OpenFaaS Pro since 2023 (the chart refuses the install with `enabling 'operator.create' is only supported for OpenFaaS Pro`). In Community, the `cofrap` chart deploys the functions as **plain Kubernetes Deployments + Services** labelled `faas_function=<name>` — the Community gateway discovers them automatically.

### 2. Secret generation

```bash
ENCRYPTION_KEY="$(python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"
MARIADB_PASSWORD="$(openssl rand -hex 16)"
MARIADB_ROOT_PASSWORD="$(openssl rand -hex 16)"
```

### 3. Install the `cofrap` chart

```bash
helm upgrade --install cofrap deploy/helm/cofrap \
  --namespace cofrap --create-namespace \
  --set secrets.encryptionKey="$ENCRYPTION_KEY" \
  --set secrets.mariadbPassword="$MARIADB_PASSWORD" \
  --set secrets.mariadbRootPassword="$MARIADB_ROOT_PASSWORD" \
  --wait --timeout 5m
```

The chart creates:
- In `cofrap`: Secret + ConfigMap + Service + StatefulSet for MariaDB.
- In `openfaas-fn`: the `mariadb-password` and `encryption-key` Secrets (used by the functions), then 1 Deployment + 1 Service per function (with the `faas_function=<name>` label for gateway discovery).

### 4. Preview / debug

To see what Helm will create **without applying**:

```bash
helm template cofrap deploy/helm/cofrap \
  --set secrets.encryptionKey=dummy --set secrets.mariadbPassword=dummy --set secrets.mariadbRootPassword=dummy
```

To validate the chart without touching the cluster:

```bash
helm lint deploy/helm/cofrap
```

---

## Troubleshooting

Common cases and resolutions: [`troubleshooting.md`](troubleshooting.md).

A few quick pointers:

| Symptom                                               | Solution                                                    |
|-------------------------------------------------------|-------------------------------------------------------------|
| MariaDB PVC stuck `Pending`                           | The cluster has no default storageClass. See [`troubleshooting.md`](troubleshooting.md). |
| Functions in `ErrImagePull` / `ImagePullBackOff`      | The images don't exist on GHCR (no git tag pushed). Build locally with [`./scripts/prod/build-images.sh`](../../scripts/prod/build-images.sh) (or `.ps1` on Windows), then `helm upgrade --reuse-values --set functions.pullPolicy=IfNotPresent` + `kubectl -n openfaas-fn rollout restart deployment -l faas_function`. |
| Gateway replies `error finding function <name>.openfaas-fn` (404) | The functions are not (yet) deployed as labelled Deployments+Services. Reinstall via `./scripts/prod/install.sh` or `helm upgrade --install cofrap deploy/helm/cofrap ...`. Check: `kubectl -n openfaas-fn get deploy -l faas_function`. |
| Helm error `enabling 'operator.create' is only supported for OpenFaaS Pro` | Expected — `operator.create` requires OpenFaaS Pro. The `cofrap` chart uses plain Deployments and does NOT need the operator. Don't pass that flag to `openfaas/openfaas`. |
| `secrets.encryptionKey is required`                   | Run via the script, or pass the 3 `--set secrets.*` by hand. |
| OpenFaaS gateway unreachable via port-forward          | Check that the `gateway` pod is `Running` in `openfaas`.    |
