# Chart Helm `cofrap`

Chart unique qui déploie l'intégralité de la stack backend COFRAP sur un cluster Kubernetes ayant **OpenFaaS Community** déjà installé.

Ce README documente le déploiement **100 % manuel** (juste `helm` + `kubectl`, sans les scripts `install.sh`/`install.ps1`). Pour la version scriptée et les variantes K3s/minikube, voir [`docs/fr/installation.md`](../../../docs/fr/installation.md) · [`docs/en/installation.md`](../../../docs/en/installation.md).

## Contenu déployé

| Ressource                                      | Namespace                              | Rôle                                              |
|------------------------------------------------|----------------------------------------|---------------------------------------------------|
| `Secret` `<release>-mariadb-credentials`       | `<release.namespace>`                  | Credentials root/applicatif MariaDB               |
| `ConfigMap` `<release>-mariadb-init`           | `<release.namespace>`                  | Script SQL d'initialisation (table `users`)       |
| `Service` `<release>-mariadb` (headless)       | `<release.namespace>`                  | Expose MariaDB en interne                         |
| `StatefulSet` `<release>-mariadb`              | `<release.namespace>`                  | Instance MariaDB persistante                      |
| `Secret` `mariadb-password`                    | `openfaas-fn`                          | Lu via `/var/openfaas/secrets/` par les fonctions |
| `Secret` `encryption-key`                      | `openfaas-fn`                          | Clé Fernet, idem                                  |
| `Deployment` + `Service` `generate-password` / `generate-2fa` / `authenticate-user` | `openfaas-fn` | Les 3 fonctions, labellisées `faas_function=<name>` |

> Les fonctions sont des `Deployment` + `Service` Kubernetes classiques (pas des CRD `openfaas.com/v1`). Le gateway OpenFaaS Community les découvre via le label `faas_function`. La CRD `Function` exigerait l'operator OpenFaaS Pro.

## Pré-requis

1. Un cluster Kubernetes (K3s, minikube, K8s managé…).
2. `helm` ≥ 3.x et `kubectl` configurés sur ce cluster.
3. **OpenFaaS Community** installé — ce chart ne l'inclut pas (séparation des responsabilités).

---

## Déploiement manuel pas-à-pas

### 1. Installer OpenFaaS Community (si absent)

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

> Ne **pas** passer `operator.create=true` : cette option est réservée à OpenFaaS Pro et fait échouer l'install.

### 2. Générer les 3 secrets

```bash
# Clé Fernet (chiffrement password + mfa)
ENCRYPTION_KEY="$(python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"
# Mots de passe MariaDB
MARIADB_PASSWORD="$(openssl rand -hex 16)"
MARIADB_ROOT_PASSWORD="$(openssl rand -hex 16)"

# ⚠ Sauvegarder ces 3 valeurs hors du cluster — la clé Fernet est irremplaçable.
echo "ENCRYPTION_KEY=$ENCRYPTION_KEY"
echo "MARIADB_PASSWORD=$MARIADB_PASSWORD"
echo "MARIADB_ROOT_PASSWORD=$MARIADB_ROOT_PASSWORD"
```

Sous PowerShell :

```powershell
$ENCRYPTION_KEY = python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
$MARIADB_PASSWORD = -join ((48..57)+(65..90)+(97..122) | Get-Random -Count 24 | % {[char]$_})
$MARIADB_ROOT_PASSWORD = -join ((48..57)+(65..90)+(97..122) | Get-Random -Count 24 | % {[char]$_})
```

### 3. Valider le chart sans rien appliquer (optionnel mais conseillé)

```bash
helm lint deploy/helm/cofrap

helm template cofrap deploy/helm/cofrap \
  --set secrets.encryptionKey="$ENCRYPTION_KEY" \
  --set secrets.mariadbPassword="$MARIADB_PASSWORD" \
  --set secrets.mariadbRootPassword="$MARIADB_ROOT_PASSWORD" \
  | less   # inspecter les 12 ressources générées
```

### 4. Installer le chart `cofrap`

```bash
helm upgrade --install cofrap deploy/helm/cofrap \
  --namespace cofrap --create-namespace \
  --set secrets.encryptionKey="$ENCRYPTION_KEY" \
  --set secrets.mariadbPassword="$MARIADB_PASSWORD" \
  --set secrets.mariadbRootPassword="$MARIADB_ROOT_PASSWORD" \
  --wait --timeout 5m
```

> Préférer un fichier de values plutôt que `--set` répétés : copier les 3 valeurs dans un `values-secrets.yaml` (non commité) et passer `-f values-secrets.yaml`.

### 5. Vérifier

```bash
kubectl -n cofrap get pods,svc,pvc
kubectl -n openfaas-fn get deploy,svc,pods -l faas_function

# Le gateway doit lister les 3 fonctions
PASS=$(kubectl -n openfaas get secret basic-auth -o jsonpath='{.data.basic-auth-password}' | base64 -d)
kubectl -n openfaas port-forward svc/gateway 8080:8080 &
curl -s -u "admin:$PASS" http://127.0.0.1:8080/system/functions | jq '.[].name'
curl -s http://127.0.0.1:8080/function/generate-password/healthz
```

### 6. Mettre à jour (nouvelle version d'image, nouvelle valeur)

```bash
# Réutilise les secrets déjà fournis, change juste ce qui doit l'être
helm upgrade cofrap deploy/helm/cofrap -n cofrap --reuse-values \
  --set functions.version=2026.1.1

kubectl -n openfaas-fn rollout status deployment -l faas_function
```

### 7. Désinstaller

```bash
helm uninstall cofrap -n cofrap
kubectl -n openfaas-fn delete secret mariadb-password encryption-key --ignore-not-found
kubectl -n cofrap delete pvc -l app.kubernetes.io/instance=cofrap   # supprime les données
kubectl delete namespace cofrap --ignore-not-found
```

---

## Images des fonctions

Le chart pointe par défaut sur `ghcr.io/cofrap-epsi-2026/<function>:2026.1.1`. Ces images n'existent qu'après un tag git `v2026.1.1` (workflow `release.yml`). Sur un fork ou sans release publiée, builder localement avec [`scripts/build-images.sh`](../../../scripts/build-images.sh) / `.ps1`, puis :

```bash
helm upgrade cofrap deploy/helm/cofrap -n cofrap --reuse-values \
  --set functions.pullPolicy=IfNotPresent
kubectl -n openfaas-fn rollout restart deployment -l faas_function
```

## Valeurs surchargeables

Voir [`values.yaml`](values.yaml) — commenté. Les plus utiles :

| Clé                          | Défaut                      | Description                                       |
|------------------------------|-----------------------------|---------------------------------------------------|
| `functions.registry`         | `ghcr.io/cofrap-epsi-2026`  | Préfixe registry pour les 3 images                |
| `functions.version`          | `2026.1.1`                  | Tag des images                                    |
| `functions.pullPolicy`       | `IfNotPresent`              | Mettre `IfNotPresent` pour des images locales     |
| `functions.totpIssuer`       | `COFRAP`                    | Issuer affiché dans Google Authenticator          |
| `functions.expirySeconds`    | `15552000` (6 mois)         | Fenêtre de validité — réduire pour démo expiry    |
| `mariadb.persistence.size`   | `2Gi`                       | Taille du PVC                                     |
| `mariadb.persistence.storageClassName` | `""` (auto)       | Préciser si le cluster n'a pas de SC par défaut   |
