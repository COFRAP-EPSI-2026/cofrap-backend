# Installation pas-à-pas

Guide complet pour déployer la stack COFRAP sur **K3s**, **minikube** ou un **cluster K8s existant**, reproductible sur **Linux** et **Windows**.

L'installation est orchestrée par un chart Helm unique ([`deploy/helm/cofrap`](../deploy/helm/cofrap)) et deux scripts d'amorçage : [`scripts/install.sh`](../scripts/install.sh) (bash) et [`scripts/install.ps1`](../scripts/install.ps1) (PowerShell). Les deux font exactement la même chose.

---

## Sommaire

- [Pré-requis communs](#pré-requis-communs)
- [Variante A — minikube (Windows ou Linux)](#variante-a--minikube-windows-ou-linux)
- [Variante B — K3s (Linux)](#variante-b--k3s-linux)
- [Variante C — Cluster Kubernetes existant](#variante-c--cluster-kubernetes-existant)
- [Vérification](#vérification)
- [Tester l'API](#tester-lapi)
- [Désinstallation](#désinstallation)
- [Que fait le script exactement ?](#que-fait-le-script-exactement-)

---

## Pré-requis communs

À installer sur ton poste de travail, dans cet ordre :

| Outil       | Linux                                  | Windows                                                                 |
|-------------|----------------------------------------|-------------------------------------------------------------------------|
| `kubectl`   | `curl -LO https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl && sudo install kubectl /usr/local/bin/` | `winget install -e --id Kubernetes.kubectl` ou via [chocolatey](https://chocolatey.org/) |
| `helm` ≥ 3  | `curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 \| bash` | `winget install -e --id Helm.Helm` |
| `python` 3.10+ (avec `cryptography`) ou `openssl` | déjà présent dans la plupart des distros | `winget install -e --id Python.Python.3.12` puis `pip install cryptography` |
| Un cluster K8s (voir variantes ci-dessous) | -                                  | -                                                                       |

Vérifier :

```bash
kubectl version --client
helm version --short
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

---

## Variante A — minikube (Windows ou Linux)

minikube est le moyen le plus rapide d'avoir un cluster local, identique sur Windows et Linux.

### Installation de minikube

| OS                | Commande                                                                                |
|-------------------|-----------------------------------------------------------------------------------------|
| **Linux**         | `curl -LO https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64 && sudo install minikube-linux-amd64 /usr/local/bin/minikube` |
| **Windows**       | `winget install -e --id Kubernetes.minikube`                                            |
| **macOS**         | `brew install minikube`                                                                 |

### Démarrer le cluster

```bash
minikube start --cpus=2 --memory=4096 --disk-size=20g
kubectl get nodes   # doit afficher 1 node Ready
```

> Sur Windows, si Docker Desktop n'est pas installé, minikube utilisera Hyper-V ou VirtualBox. Pour Hyper-V :
> ```powershell
> minikube start --driver=hyperv --memory=4096 --cpus=2
> ```

### Installation de la stack

```bash
# Cloner le dépôt si pas déjà fait
git clone https://github.com/COFRAP-EPSI-2026/cofrap-backend.git
cd cofrap-backend

# Linux / macOS / WSL / Git Bash
./scripts/install.sh

# Windows PowerShell
./scripts/install.ps1
```

Le script :
1. Vérifie `kubectl` + `helm` + l'accès au cluster.
2. Installe OpenFaaS Community via Helm dans le namespace `openfaas`.
3. Génère une clé Fernet + deux mots de passe MariaDB aléatoires.
4. Installe le chart `cofrap` (MariaDB + secrets + 3 fonctions OpenFaaS).
5. Affiche les credentials et les commandes utiles.

**Conserve la sortie du script** (les secrets ne seront pas re-affichés).

---

## Variante B — K3s (Linux)

K3s est une distribution Kubernetes légère, idéale pour un homelab ou une VM.

### Installation de K3s

```bash
# Install K3s + récupérer le kubeconfig
curl -sfL https://get.k3s.io | sh -

# Donner accès au kubeconfig à ton user
sudo cp /etc/rancher/k3s/k3s.yaml ~/.kube/config
sudo chown $USER:$USER ~/.kube/config
chmod 600 ~/.kube/config

kubectl get nodes   # doit afficher 1 node Ready
```

K3s embarque déjà :
- un load-balancer (`svclb`)
- un ingress Traefik
- un storage provisioner `local-path` (utilisé automatiquement par le PVC MariaDB)

### Installation de la stack

```bash
git clone https://github.com/COFRAP-EPSI-2026/cofrap-backend.git
cd cofrap-backend
./scripts/install.sh
```

---

## Variante C — Cluster Kubernetes existant

Pour un cluster K8s déjà provisionné (GKE/AKS/EKS/Kapsule, homelab, kubeadm…) :

```bash
# Si OpenFaaS est DÉJÀ installé, skipper son install :
SKIP_OPENFAAS=1 ./scripts/install.sh
# ou avec PowerShell
./scripts/install.ps1 -SkipOpenFaaS

# Sinon, le script s'occupe d'OpenFaaS aussi :
./scripts/install.sh
```

Pour personnaliser :

```bash
NAMESPACE=cofrap-prod RELEASE_NAME=cofrap-prod ./scripts/install.sh
```

Ou directement en Helm pour un contrôle total :

```bash
# Générer les secrets toi-même
ENCRYPTION_KEY="$(python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"
MARIADB_PASSWORD="$(openssl rand -hex 16)"
MARIADB_ROOT_PASSWORD="$(openssl rand -hex 16)"

helm upgrade --install cofrap deploy/helm/cofrap \
  --namespace cofrap --create-namespace \
  --set secrets.encryptionKey="$ENCRYPTION_KEY" \
  --set secrets.mariadbPassword="$MARIADB_PASSWORD" \
  --set secrets.mariadbRootPassword="$MARIADB_ROOT_PASSWORD" \
  --set functions.registry=ghcr.io/<votre-org> \
  --set functions.version=0.2.0 \
  --set mariadb.persistence.storageClassName=longhorn \
  --wait
```

---

## Vérification

```bash
# Pods cofrap (MariaDB)
kubectl -n cofrap get pods,svc,pvc

# Fonctions OpenFaaS — Deployments + Services labellisés `faas_function`
kubectl -n openfaas-fn get deploy,svc -l 'faas_function'
kubectl -n openfaas-fn get pods -l 'faas_function'
# NAME                                READY   STATUS    RESTARTS   AGE
# generate-password-xxxx-yyyy         1/1     Running   0          1m
# generate-2fa-xxxx-yyyy              1/1     Running   0          1m
# authenticate-user-xxxx-yyyy         1/1     Running   0          1m

# Le gateway les voit aussi
curl -s -u admin:$OF_PASS http://127.0.0.1:8080/system/functions | jq '.[].name'
```

État attendu : un pod MariaDB `Running` + un pod par fonction `Running`.

---

## Tester l'API

### Étape 1 — port-forwarder le gateway OpenFaaS

```bash
kubectl -n openfaas port-forward svc/gateway 8080:8080
```

Laisser tourner dans un terminal séparé. Le gateway est maintenant joignable sur `http://127.0.0.1:8080`.

### Étape 2 — appeler les fonctions

```bash
# Healthcheck
curl -s http://127.0.0.1:8080/function/generate-password/healthz
# {"status":"ok"}

# Créer un compte
curl -s -X POST http://127.0.0.1:8080/function/generate-password \
     -H 'Content-Type: application/json' \
     -d '{"username":"michel.ranu"}' | jq

# Générer le 2FA
curl -s -X POST http://127.0.0.1:8080/function/generate-2fa \
     -H 'Content-Type: application/json' \
     -d '{"username":"michel.ranu"}' | jq
```

Plus simple : utiliser la [collection Bruno](../bruno/) en sélectionnant l'environnement `Local OpenFaaS Gateway`.

---

## Désinstallation

```bash
# Linux / macOS / WSL
./scripts/uninstall.sh                       # garde OpenFaaS
PURGE_OPENFAAS=1 ./scripts/uninstall.sh      # supprime tout, OpenFaaS inclus

# Windows
./scripts/uninstall.ps1
./scripts/uninstall.ps1 -PurgeOpenFaaS
```

Le script :
1. `helm uninstall cofrap`
2. Supprime les `Secret`s `mariadb-password` et `encryption-key` dans `openfaas-fn` (marqués `helm.sh/resource-policy: keep` pour éviter une suppression accidentelle pendant un `helm upgrade`).
3. Supprime les PVC MariaDB (sinon les données restent).
4. Supprime le namespace `cofrap`.

---

## Que fait le script exactement ?

Étape par étape, pour comprendre ce qui se passe sous le capot et pouvoir le rejouer à la main si besoin :

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

> ℹ️ **Pourquoi pas `operator.create=true` ?** Cette option est réservée à OpenFaaS Pro depuis 2023 (le chart refuse l'install avec `enabling 'operator.create' is only supported for OpenFaaS Pro`). En Community, le chart `cofrap` déploie les fonctions comme des **Deployments + Services Kubernetes classiques** labellisés `faas_function=<name>` — le gateway Community les découvre automatiquement.

### 2. Génération des secrets

```bash
ENCRYPTION_KEY="$(python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"
MARIADB_PASSWORD="$(openssl rand -hex 16)"
MARIADB_ROOT_PASSWORD="$(openssl rand -hex 16)"
```

### 3. Install du chart `cofrap`

```bash
helm upgrade --install cofrap deploy/helm/cofrap \
  --namespace cofrap --create-namespace \
  --set secrets.encryptionKey="$ENCRYPTION_KEY" \
  --set secrets.mariadbPassword="$MARIADB_PASSWORD" \
  --set secrets.mariadbRootPassword="$MARIADB_ROOT_PASSWORD" \
  --wait --timeout 5m
```

Le chart crée :
- Dans `cofrap` : Secret + ConfigMap + Service + StatefulSet pour MariaDB.
- Dans `openfaas-fn` : Secrets `mariadb-password` et `encryption-key` (utilisés par les fonctions), puis 1 Deployment + 1 Service par fonction (avec label `faas_function=<name>` pour la découverte par le gateway).

### 4. Préview / debug

Pour voir ce que Helm va créer **sans appliquer** :

```bash
helm template cofrap deploy/helm/cofrap \
  --set secrets.encryptionKey=dummy --set secrets.mariadbPassword=dummy --set secrets.mariadbRootPassword=dummy
```

Pour valider le chart sans toucher au cluster :

```bash
helm lint deploy/helm/cofrap
```

---

## Troubleshooting

Cas fréquents et résolution : [`troubleshooting.md`](troubleshooting.md).

Quelques pointeurs rapides :

| Symptôme                                              | Solution                                                    |
|-------------------------------------------------------|-------------------------------------------------------------|
| PVC MariaDB en `Pending`                              | Le cluster n'a pas de storageClass par défaut. Voir [`troubleshooting.md`](troubleshooting.md). |
| Fonctions en `ErrImagePull` / `ImagePullBackOff`      | Les images n'existent pas sur GHCR (aucun tag git poussé). Builder localement avec [`./scripts/build-images.sh`](../scripts/build-images.sh) (ou `.ps1` sur Windows), puis `helm upgrade --reuse-values --set functions.pullPolicy=IfNotPresent` + `kubectl -n openfaas-fn rollout restart deployment -l faas_function`. |
| Gateway répond `error finding function <name>.openfaas-fn` (404) | Les fonctions ne sont pas (encore) déployées comme Deployments+Services labellisés. Réinstaller via `./scripts/install.sh` ou `helm upgrade --install cofrap deploy/helm/cofrap ...`. Vérifier : `kubectl -n openfaas-fn get deploy -l faas_function`. |
| Erreur Helm `enabling 'operator.create' is only supported for OpenFaaS Pro` | C'est attendu — `operator.create` exige OpenFaaS Pro. Le chart `cofrap` utilise des Deployments classiques et ne nécessite PAS l'operator. Ne pas passer ce flag à `openfaas/openfaas`. |
| `secrets.encryptionKey est obligatoire`               | Lancer via le script ou passer les 3 `--set secrets.*` à la main. |
| Gateway OpenFaaS inaccessible en port-forward         | Vérifier que le pod `gateway` est `Running` dans `openfaas`. |
