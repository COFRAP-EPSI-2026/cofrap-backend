#!/usr/bin/env bash
# Build les 3 images des fonctions et les rend disponibles dans le cluster local
# sans passer par un registry distant.
#
# Auto-détecte minikube / K3s / kind. Pour les autres clusters, builde + push
# sur le registry de ton choix (passer REGISTRY=... PUSH=1).
#
# Usage :
#   ./scripts/build-images.sh                          # auto-détection
#   REGISTRY=ghcr.io/mon-org PUSH=1 ./scripts/build-images.sh   # build + push
#   TAG=dev ./scripts/build-images.sh                  # tag custom

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${SCRIPT_DIR}/.."

REGISTRY="${REGISTRY:-ghcr.io/cofrap-epsi-2026}"
TAG="${TAG:-2026.3.1}"  # x-release-please-version
PUSH="${PUSH:-0}"
CLUSTER_TYPE="${CLUSTER_TYPE:-auto}"

FUNCTIONS=(generate-password generate-2fa authenticate-user)

red()    { printf '\033[31m%s\033[0m\n' "$*"; }
green()  { printf '\033[32m%s\033[0m\n' "$*"; }
yellow() { printf '\033[33m%s\033[0m\n' "$*"; }
blue()   { printf '\033[34m▸ %s\033[0m\n' "$*"; }

# ─── Détection du cluster ───────────────────────────────────────────────────
detect_cluster() {
  if [ "$CLUSTER_TYPE" != "auto" ]; then
    echo "$CLUSTER_TYPE"
    return
  fi
  if command -v minikube >/dev/null 2>&1 && minikube status >/dev/null 2>&1; then
    echo "minikube"; return
  fi
  local ctx
  ctx="$(kubectl config current-context 2>/dev/null || true)"
  case "$ctx" in
    *kind*)  echo "kind"; return ;;
    *k3d*)   echo "k3d"; return ;;
    *)
      if command -v k3s >/dev/null 2>&1; then echo "k3s"; return; fi
      ;;
  esac
  echo "generic"
}

CLUSTER="$(detect_cluster)"
blue "Cluster détecté : $CLUSTER"

# ─── Configuration du daemon Docker selon le cluster ────────────────────────
case "$CLUSTER" in
  minikube)
    yellow "Pointage du Docker CLI vers le daemon de minikube"
    eval "$(minikube -p minikube docker-env --shell bash)"
    ;;
  generic)
    if [ "$PUSH" != "1" ]; then
      red "Cluster non local détecté. Pour pousser sur un registry :"
      red "  REGISTRY=ghcr.io/mon-org PUSH=1 $0"
      exit 1
    fi
    ;;
esac

# ─── Build des images ───────────────────────────────────────────────────────
for fn in "${FUNCTIONS[@]}"; do
  IMAGE="${REGISTRY}/${fn}:${TAG}"
  blue "Build $IMAGE"
  docker build -t "$IMAGE" "${ROOT}/functions/${fn}"
done

# ─── Distribution selon le cluster ──────────────────────────────────────────
case "$CLUSTER" in
  minikube)
    green "✓ Images disponibles dans le daemon minikube (pas de push nécessaire)."
    ;;
  k3s)
    blue "Import des images dans containerd (K3s)"
    for fn in "${FUNCTIONS[@]}"; do
      IMAGE="${REGISTRY}/${fn}:${TAG}"
      docker save "$IMAGE" | sudo k3s ctr images import -
    done
    green "✓ Images importées dans K3s."
    ;;
  k3d)
    blue "Import des images dans K3d"
    for fn in "${FUNCTIONS[@]}"; do
      IMAGE="${REGISTRY}/${fn}:${TAG}"
      k3d image import "$IMAGE" -c "$(kubectl config current-context | sed 's/^k3d-//')"
    done
    green "✓ Images importées dans K3d."
    ;;
  kind)
    blue "Import des images dans KinD"
    for fn in "${FUNCTIONS[@]}"; do
      IMAGE="${REGISTRY}/${fn}:${TAG}"
      kind load docker-image "$IMAGE"
    done
    green "✓ Images importées dans KinD."
    ;;
  generic)
    if [ "$PUSH" = "1" ]; then
      blue "Push vers $REGISTRY"
      for fn in "${FUNCTIONS[@]}"; do
        IMAGE="${REGISTRY}/${fn}:${TAG}"
        docker push "$IMAGE"
      done
      green "✓ Images poussées."
    fi
    ;;
esac

echo
echo "Pour redéployer les fonctions avec ces images :"
echo "  helm upgrade cofrap ./deploy/helm/cofrap -n cofrap --reuse-values \\"
echo "    --set functions.registry=$REGISTRY \\"
echo "    --set functions.version=$TAG \\"
echo "    --set functions.pullPolicy=IfNotPresent"
echo
echo "Puis forcer le redéploiement (sinon K8s garde les anciens pods sans pull) :"
echo "  kubectl -n openfaas-fn rollout restart deployment -l 'faas_function'"
