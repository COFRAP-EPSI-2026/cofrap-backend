# Déploiement

> **Quickstart** : la procédure recommandée (un script qui orchestre OpenFaaS + chart Helm `cofrap`) vit dans [`installation.md`](installation.md). Ce document-ci détaille les étapes manuelles pour les cas où tu veux comprendre / personnaliser / dépanner ce que fait le script.

## Pré-requis

- Cluster Kubernetes (K3S, minikube, KinD ou cloud GKE/AKS/EKS/Kapsule)
- [Helm](https://helm.sh/docs/intro/install/) (pour installer OpenFaaS)
- [`faas-cli`](https://docs.openfaas.com/cli/install/)
- `kubectl` configuré sur le cluster cible

## 1. Installer OpenFaaS Community

```bash
# via Helm :
helm repo add openfaas https://openfaas.github.io/faas-netes/
kubectl create namespace openfaas
kubectl create namespace openfaas-fn
helm install openfaas openfaas/openfaas --namespace openfaas --set functionNamespace=openfaas-fn

# Récupérer le mot de passe admin et logger faas-cli
PASSWORD=$(kubectl -n openfaas get secret basic-auth -o jsonpath='{.data.basic-auth-password}' | base64 -d)
kubectl port-forward -n openfaas svc/gateway 8080:8080 & echo "$PASSWORD" | faas-cli login -u admin --password-stdin
```

## 2. Déployer la stack (recommandé : chart Helm)

Un seul chart Helm — [`deploy/helm/cofrap`](../../deploy/helm/cofrap) — déploie MariaDB, crée les secrets OpenFaaS dans `openfaas-fn` et les 3 fonctions (1 Deployment + 1 Service chacune). Procédure complète : [`installation.md`](installation.md).

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

Vérification :

```bash
kubectl -n cofrap get pods,svc,pvc
kubectl -n openfaas-fn get deploy,svc -l faas_function
curl -s http://127.0.0.1:8080/function/generate-password/healthz   # après port-forward
```

## 2bis. Alternative : déploiement manuel sans Helm

Si tu préfères `kubectl apply` direct (ou si tu n'as pas Helm), les manifestes bruts existent dans [`deploy/mariadb/`](../../deploy/mariadb/) :

```bash
kubectl apply -f deploy/mariadb/namespace.yaml
# Éditer secret.yaml AVANT pour mettre des vrais mots de passe
kubectl apply -f deploy/mariadb/secret.yaml
kubectl apply -f deploy/mariadb/configmap-init.yaml
kubectl apply -f deploy/mariadb/service.yaml
kubectl apply -f deploy/mariadb/statefulset.yaml
```

Puis créer les secrets OpenFaaS et déployer les fonctions via `faas-cli` :

```bash
faas-cli secret create mariadb-password --from-literal "$MARIADB_PASSWORD"
faas-cli secret create encryption-key   --from-literal "$ENCRYPTION_KEY"
faas-cli up -f stack.yml
```

> **Garder `ENCRYPTION_KEY` précieusement** : si elle est perdue, tous les mots de passe et secrets TOTP chiffrés en BDD deviennent illisibles. Sauvegarder dans un vault (Vault, Doppler, AWS Secrets Manager, etc.).

## Variantes de déploiement

### Cluster baremetal avec K3S

K3S inclut un load-balancer (`svclb`) et un ingress Traefik prêts à l'emploi.

```bash
curl -sfL https://get.k3s.io | sh -
sudo cat /etc/rancher/k3s/k3s.yaml > ~/.kube/config  # ajuster les permissions
arkade install openfaas
```

Côté MariaDB, le `StatefulSet` utilise par défaut le `StorageClass` `local-path` fourni par K3S, donc aucune config supplémentaire n'est nécessaire pour un PoC.

### Cloud managé (GKE/AKS/EKS)

- Provisionner un cluster minimal (2 nodes, 2 vCPU / 4 Go chacun suffisent)
- `arkade install openfaas`
- Pour exposer le gateway en HTTPS : `arkade install openfaas-ingress` (cert-manager + Let's Encrypt)

### Sans cluster : minikube ou Docker

Le PoC fonctionne aussi sur minikube. Pour la BDD, soit MariaDB via `StatefulSet` (mêmes manifestes), soit le `docker-compose.yml` à la racine si on déploie les fonctions hors Kubernetes (pour debug).

## Variables d'environnement

Tout ce qui n'est pas un secret se règle dans `stack.yml` (`environment:` par fonction) :

| Variable           | Défaut                              | Effet                                               |
|--------------------|-------------------------------------|-----------------------------------------------------|
| `DB_HOST`          | `mariadb.cofrap.svc.cluster.local`  | Hostname MariaDB                                    |
| `DB_PORT`          | `3306`                              | Port                                                |
| `DB_NAME`          | `cofrap`                            | Base de données                                     |
| `DB_USER`          | `cofrap`                            | Utilisateur applicatif (pas root !)                 |
| `TOTP_ISSUER`      | `COFRAP`                            | Nom affiché dans Google Authenticator               |
| `EXPIRY_SECONDS`   | `15552000` (6 mois)                 | Fenêtre de validité — réduire pour tester l'expiry  |
| `CORS_ALLOW_ORIGINS` | `*`                               | Origines autorisées à appeler l'API depuis un navigateur — `*` ou liste séparée par virgules |
| `read_timeout`/`write_timeout`/`exec_timeout` | `30s`     | Limites of-watchdog                                 |

## Mises à jour

- **Hotfix d'une fonction** : `faas-cli up --filter generate-password` (build + push + deploy d'une seule fonction).
- **Rotation `ENCRYPTION_KEY`** : Fernet supporte la rotation multi-clés. Pour le PoC actuel, c'est une opération manuelle (déchiffrer avec l'ancienne clé, rechiffrer avec la nouvelle, écraser le secret OpenFaaS). À industrialiser si le produit passe en prod.
- **Schéma de BDD** : pas de migrations pour ce PoC (une seule table figée). Si évolution, ajouter [Alembic](https://alembic.sqlalchemy.org/) ou des scripts SQL versionnés.

## CI/CD

→ Pipeline GitHub Actions codé dans [`.github/workflows/`](../../.github/workflows/).

> **Prérequis Release Please** (une seule fois) : `Settings → Actions → General → Workflow permissions` → cocher **« Allow GitHub Actions to create and approve pull requests »**. Sans ça : erreur `GitHub Actions is not permitted to create or approve pull requests`. Sur un repo d'organisation, activer d'abord ce réglage au niveau de l'org.

Les releases sont automatisées par **Release Please** (workflow `release-please.yml`) :
1. Les commits Conventional (`feat:`, `fix:`) poussés sur `main` alimentent une « Release PR ».
2. Le merge de cette PR crée le tag `vX.Y.Z` + la GitHub Release et bumpe tous les fichiers de version.
3. Le même workflow build les 3 images multi-arch (amd64 + arm64) et les pousse sur `ghcr.io/<org>/<function>:<version>` avec SBOM et attestation de provenance.

Le workflow `release.yml` reste disponible pour un tag `v*.*.*` posé à la main (filet de secours).

Le déploiement sur le cluster reste **manuel** (`faas-cli up` ou `helm upgrade`) — c'est cohérent avec un PoC où chaque release est validée par l'équipe avant mise en service.
