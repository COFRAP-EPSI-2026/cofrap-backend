#!/usr/bin/env bash
# Installe la stack COFRAP (OpenFaaS + chart cofrap) sur un cluster Kubernetes.
#
# Usage :
#   ./scripts/prod/install.sh                       # défauts (namespace cofrap, release cofrap)
#   NAMESPACE=demo ./scripts/prod/install.sh        # override
#   SKIP_OPENFAAS=1 ./scripts/prod/install.sh       # cluster qui a déjà OpenFaaS
#
# Pré-requis : kubectl + helm configurés sur le cluster cible, python (avec cryptography) ou openssl.
#
# Compatible Linux, macOS, WSL et Git Bash sur Windows.

set -euo pipefail

NAMESPACE="${NAMESPACE:-cofrap}"
RELEASE_NAME="${RELEASE_NAME:-cofrap}"
OPENFAAS_NAMESPACE="${OPENFAAS_NAMESPACE:-openfaas}"
OPENFAAS_FN_NAMESPACE="${OPENFAAS_FN_NAMESPACE:-openfaas-fn}"
SKIP_OPENFAAS="${SKIP_OPENFAAS:-0}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHART_PATH="${SCRIPT_DIR}/../../deploy/helm/cofrap"

# ─── helpers ────────────────────────────────────────────────────────────────
red()    { printf '\033[31m%s\033[0m\n' "$*"; }
green()  { printf '\033[32m%s\033[0m\n' "$*"; }
yellow() { printf '\033[33m%s\033[0m\n' "$*"; }
blue()   { printf '\033[34m▸ %s\033[0m\n' "$*"; }

require() {
  command -v "$1" >/dev/null 2>&1 || { red "Manquant : $1"; exit 1; }
}

gen_fernet_key() {
  # Tente Python d'abord (le plus portable), retombe sur openssl si pas dispo.
  if command -v python >/dev/null 2>&1 && python -c "import cryptography" >/dev/null 2>&1; then
    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
  elif command -v python3 >/dev/null 2>&1 && python3 -c "import cryptography" >/dev/null 2>&1; then
    python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
  elif command -v openssl >/dev/null 2>&1; then
    # Fernet attend du base64 URL-safe, openssl produit du standard b64 → on remplace.
    openssl rand 32 | base64 | tr '+/' '-_' | tr -d '\n='
    echo "="  # padding final
  else
    red "Impossible de générer une clé Fernet : ni python+cryptography ni openssl trouvés."
    exit 1
  fi
}

gen_random_hex() {
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -hex 16
  else
    python -c "import secrets; print(secrets.token_hex(16))"
  fi
}

# ─── 1. Vérification prérequis ──────────────────────────────────────────────
blue "Vérification des prérequis"
require kubectl
require helm
kubectl cluster-info >/dev/null || { red "kubectl ne peut pas joindre le cluster"; exit 1; }
green "kubectl + helm OK, cluster joignable."

# ─── 2. Install OpenFaaS (skip si demandé) ──────────────────────────────────
if [ "$SKIP_OPENFAAS" = "1" ]; then
  yellow "SKIP_OPENFAAS=1 → on suppose qu'OpenFaaS est déjà installé"
else
  blue "Installation d'OpenFaaS Community via Helm"
  helm repo add openfaas https://openfaas.github.io/faas-netes/ 2>/dev/null || true
  helm repo update openfaas

  kubectl create namespace "$OPENFAAS_NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -
  kubectl create namespace "$OPENFAAS_FN_NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -

  # NB : `operator.create=true` est réservé à OpenFaaS Pro depuis 2023.
  # En Community, on déploie les fonctions comme Deployments + Services classiques
  # labellisés `faas_function=<name>` — le gateway les découvre automatiquement.
  helm upgrade --install openfaas openfaas/openfaas \
    --namespace "$OPENFAAS_NAMESPACE" \
    --set functionNamespace="$OPENFAAS_FN_NAMESPACE" \
    --set generateBasicAuth=true \
    --set basic_auth=true \
    --wait --timeout 5m

  green "OpenFaaS installé."
fi

# ─── 3. Génération des secrets ──────────────────────────────────────────────
blue "Génération des secrets applicatifs"
ENCRYPTION_KEY="${ENCRYPTION_KEY:-$(gen_fernet_key)}"
MARIADB_PASSWORD="${MARIADB_PASSWORD:-$(gen_random_hex)}"
MARIADB_ROOT_PASSWORD="${MARIADB_ROOT_PASSWORD:-$(gen_random_hex)}"
green "Secrets générés (longueurs : key=${#ENCRYPTION_KEY}, mariadb=${#MARIADB_PASSWORD})"

# ─── 4. Install du chart cofrap ─────────────────────────────────────────────
blue "Installation du chart cofrap"
helm upgrade --install "$RELEASE_NAME" "$CHART_PATH" \
  --namespace "$NAMESPACE" --create-namespace \
  --set "openfaas.functionNamespace=$OPENFAAS_FN_NAMESPACE" \
  --set "secrets.encryptionKey=$ENCRYPTION_KEY" \
  --set "secrets.mariadbPassword=$MARIADB_PASSWORD" \
  --set "secrets.mariadbRootPassword=$MARIADB_ROOT_PASSWORD" \
  --wait --timeout 5m

# ─── 5. Affichage des credentials et next steps ─────────────────────────────
echo
green "============================================================"
green "  ✓ Stack COFRAP installée"
green "============================================================"
echo
echo "Namespace cofrap          : $NAMESPACE"
echo "Namespace OpenFaaS        : $OPENFAAS_NAMESPACE"
echo "Namespace fonctions       : $OPENFAAS_FN_NAMESPACE"
echo
echo "Mot de passe MariaDB (root)   : $MARIADB_ROOT_PASSWORD"
echo "Mot de passe MariaDB (app)    : $MARIADB_PASSWORD"
echo "Clé Fernet (encryption-key)   : $ENCRYPTION_KEY"
echo
yellow "⚠ Sauvegarder ces valeurs hors du cluster. La clé Fernet ne peut PAS"
yellow "  être régénérée sans perdre les comptes existants."
echo
echo "Mot de passe admin OpenFaaS :"
echo "  kubectl -n $OPENFAAS_NAMESPACE get secret basic-auth -o jsonpath='{.data.basic-auth-password}' | base64 -d"
echo
echo "Pour accéder au gateway en local :"
echo "  kubectl -n $OPENFAAS_NAMESPACE port-forward svc/gateway 8080:8080"
echo "  → http://127.0.0.1:8080"
echo
