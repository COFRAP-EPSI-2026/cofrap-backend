# Chart Helm `cofrap`

Chart unique qui déploie l'intégralité de la stack backend COFRAP sur un cluster Kubernetes ayant **OpenFaaS Community** déjà installé.

## Contenu déployé

| Ressource                                      | Namespace                              | Rôle                                              |
|------------------------------------------------|----------------------------------------|---------------------------------------------------|
| `Secret` `<release>-mariadb-credentials`       | `<release.namespace>`                  | Credentials root/applicatif MariaDB               |
| `ConfigMap` `<release>-mariadb-init`           | `<release.namespace>`                  | Script SQL d'initialisation (table `users`)       |
| `Service` `<release>-mariadb` (headless)       | `<release.namespace>`                  | Expose MariaDB en interne                         |
| `StatefulSet` `<release>-mariadb`              | `<release.namespace>`                  | Instance MariaDB persistante                      |
| `Secret` `mariadb-password`                    | `openfaas-fn`                          | Lu via `/var/openfaas/secrets/` par les fonctions |
| `Secret` `encryption-key`                      | `openfaas-fn`                          | Clé Fernet, idem                                  |
| `Function` `generate-password` / `generate-2fa` / `authenticate-user` | `openfaas-fn`           | Les 3 fonctions du PoC (CRD `openfaas.com/v1`)    |

## Pré-requis

1. Un cluster Kubernetes (K3s, minikube, K8s managé…).
2. `helm` ≥ 3.x et `kubectl` configurés sur ce cluster.
3. **OpenFaaS Community** installé (chart `openfaas/openfaas`) — ce chart-ci ne l'inclut pas pour rester découpé.

## Installation rapide

Voir [`docs/installation.md`](../../../docs/installation.md) à la racine du dépôt pour le guide complet (K3s/minikube/cluster existant, Windows + Linux).

```bash
# Générer les secrets nécessaires (une fois)
ENCRYPTION_KEY="$(python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"
MARIADB_PASSWORD="$(openssl rand -hex 16)"
MARIADB_ROOT_PASSWORD="$(openssl rand -hex 16)"

# Installer
helm install cofrap ./deploy/helm/cofrap \
  --namespace cofrap --create-namespace \
  --set secrets.encryptionKey="$ENCRYPTION_KEY" \
  --set secrets.mariadbPassword="$MARIADB_PASSWORD" \
  --set secrets.mariadbRootPassword="$MARIADB_ROOT_PASSWORD"
```

> Plus simple : les scripts [`install.sh`](../../../scripts/install.sh) (Linux/macOS) et [`install.ps1`](../../../scripts/install.ps1) (Windows) s'occupent de tout.

## Valeurs surchargeables

Voir [`values.yaml`](values.yaml) — commenté. Les plus utiles :

| Clé                          | Défaut                      | Description                                       |
|------------------------------|-----------------------------|---------------------------------------------------|
| `functions.registry`         | `ghcr.io/cofrap-epsi-2026`  | Préfixe registry pour les 3 images                |
| `functions.version`          | `0.1.0`                     | Tag des images                                    |
| `functions.totpIssuer`       | `COFRAP`                    | Issuer affiché dans Google Authenticator          |
| `functions.expirySeconds`    | `15552000` (6 mois)         | Fenêtre de validité — réduire pour démo expiry    |
| `mariadb.persistence.size`   | `2Gi`                       | Taille du PVC                                     |
| `mariadb.persistence.storageClassName` | `""` (auto)       | Préciser si le cluster n'a pas de SC par défaut   |

## Désinstallation

```bash
helm uninstall cofrap -n cofrap
# Les secrets dans openfaas-fn ont `helm.sh/resource-policy: keep` :
# à supprimer manuellement si tu veux tout nettoyer.
kubectl -n openfaas-fn delete secret mariadb-password encryption-key
kubectl delete pvc -n cofrap -l app.kubernetes.io/instance=cofrap
```
