#!/usr/bin/env bash
# Désinstalle la stack COFRAP. Garde OpenFaaS en place par défaut.
#
# Usage :
#   ./scripts/prod/uninstall.sh                     # supprime cofrap + secrets + PVC
#   PURGE_OPENFAAS=1 ./scripts/prod/uninstall.sh    # supprime AUSSI OpenFaaS

set -euo pipefail

NAMESPACE="${NAMESPACE:-cofrap}"
RELEASE_NAME="${RELEASE_NAME:-cofrap}"
OPENFAAS_NAMESPACE="${OPENFAAS_NAMESPACE:-openfaas}"
OPENFAAS_FN_NAMESPACE="${OPENFAAS_FN_NAMESPACE:-openfaas-fn}"
PURGE_OPENFAAS="${PURGE_OPENFAAS:-0}"

red()    { printf '\033[31m%s\033[0m\n' "$*"; }
green()  { printf '\033[32m%s\033[0m\n' "$*"; }
blue()   { printf '\033[34m▸ %s\033[0m\n' "$*"; }

blue "Désinstallation du chart cofrap"
helm uninstall "$RELEASE_NAME" -n "$NAMESPACE" 2>/dev/null || red "Release $RELEASE_NAME absente"

blue "Nettoyage des secrets openfaas-fn (helm.sh/resource-policy=keep)"
kubectl -n "$OPENFAAS_FN_NAMESPACE" delete secret mariadb-password encryption-key --ignore-not-found

blue "Nettoyage des PVC MariaDB"
kubectl -n "$NAMESPACE" delete pvc -l "app.kubernetes.io/instance=$RELEASE_NAME" --ignore-not-found

if [ "$PURGE_OPENFAAS" = "1" ]; then
  blue "Désinstallation d'OpenFaaS (PURGE_OPENFAAS=1)"
  helm uninstall openfaas -n "$OPENFAAS_NAMESPACE" 2>/dev/null || true
  kubectl delete namespace "$OPENFAAS_NAMESPACE" "$OPENFAAS_FN_NAMESPACE" --ignore-not-found
fi

kubectl delete namespace "$NAMESPACE" --ignore-not-found

green "✓ Désinstallation terminée"
