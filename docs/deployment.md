# Déploiement

## Pré-requis

- Cluster Kubernetes (K3S, minikube, KinD ou cloud GKE/AKS/EKS/Kapsule)
- [Helm](https://helm.sh/docs/intro/install/) (pour installer OpenFaaS)
- [`faas-cli`](https://docs.openfaas.com/cli/install/)
- `kubectl` configuré sur le cluster cible

## 1. Installer OpenFaaS Community

```bash
arkade install openfaas
# OU via Helm :
# helm repo add openfaas https://openfaas.github.io/faas-netes/
# kubectl create namespace openfaas
# kubectl create namespace openfaas-fn
# helm install openfaas openfaas/openfaas --namespace openfaas --set functionNamespace=openfaas-fn

# Récupérer le mot de passe admin et logger faas-cli
PASSWORD=$(kubectl -n openfaas get secret basic-auth -o jsonpath='{.data.basic-auth-password}' | base64 -d)
kubectl port-forward -n openfaas svc/gateway 8080:8080 &
echo "$PASSWORD" | faas-cli login -u admin --password-stdin
```

## 2. Déployer MariaDB

Les manifestes vivent dans [`deploy/mariadb/`](../deploy/mariadb/) :

```bash
kubectl apply -f deploy/mariadb/namespace.yaml
# Éditer secret.yaml AVANT pour mettre des vrais mots de passe
kubectl apply -f deploy/mariadb/secret.yaml
kubectl apply -f deploy/mariadb/configmap-init.yaml
kubectl apply -f deploy/mariadb/service.yaml
kubectl apply -f deploy/mariadb/statefulset.yaml

# Vérifier
kubectl -n cofrap get pods,svc,pvc
kubectl -n cofrap exec -it mariadb-0 -- mariadb -ucofrap -p cofrap -e "SHOW TABLES;"
```

La table `users` est créée automatiquement par le `ConfigMap` `mariadb-init` (entrypoint MariaDB).

## 3. Créer les secrets OpenFaaS

Deux secrets sont attendus par les 3 fonctions :

```bash
export MARIADB_PASSWORD="<le mdp défini dans secret.yaml côté MariaDB>"
export ENCRYPTION_KEY="$(python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"

bash deploy/openfaas-secrets.example.sh
# ou en direct :
faas-cli secret create mariadb-password --from-literal "$MARIADB_PASSWORD"
faas-cli secret create encryption-key   --from-literal "$ENCRYPTION_KEY"
```

> **Garder `ENCRYPTION_KEY` précieusement** : si elle est perdue, tous les mots de passe et secrets TOTP chiffrés en BDD deviennent illisibles. Sauvegarder dans un vault (Vault, Doppler, AWS Secrets Manager, etc.).

## 4. Déployer les fonctions

```bash
# Éditer stack.yml si nécessaire (préfixe d'image, gateway, DB_HOST)
faas-cli up -f stack.yml
```

Cela enchaîne build → push → deploy pour les 3 fonctions. Vérification :

```bash
faas-cli list
# generate-password   1/1
# generate-2fa        1/1
# authenticate-user   1/1

curl -s $OPENFAAS_URL/function/generate-password/healthz
# {"status":"ok"}
```

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
| `read_timeout`/`write_timeout`/`exec_timeout` | `30s`     | Limites of-watchdog                                 |

## Mises à jour

- **Hotfix d'une fonction** : `faas-cli up --filter generate-password` (build + push + deploy d'une seule fonction).
- **Rotation `ENCRYPTION_KEY`** : Fernet supporte la rotation multi-clés. Pour le PoC actuel, c'est une opération manuelle (déchiffrer avec l'ancienne clé, rechiffrer avec la nouvelle, écraser le secret OpenFaaS). À industrialiser si le produit passe en prod.
- **Schéma de BDD** : pas de migrations pour ce PoC (une seule table figée). Si évolution, ajouter [Alembic](https://alembic.sqlalchemy.org/) ou des scripts SQL versionnés.

## CI/CD

→ Pipeline GitHub Actions documenté dans la section CI/CD du [README racine](../README.md#cicd) et codé dans [`.github/workflows/`](../.github/workflows/).

Sur un tag `v*.*.*`, le workflow `release.yml` :
1. Rejoue la suite CI complète (lint + tests)
2. Build les 3 images multi-arch (amd64 + arm64)
3. Push sur `ghcr.io/<org>/<function>:<version>` avec SBOM et attestation de provenance

Le déploiement sur le cluster reste **manuel** (`faas-cli up`) — c'est cohérent avec un PoC où chaque release est validée par l'équipe avant mise en service.
