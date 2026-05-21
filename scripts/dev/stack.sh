#!/usr/bin/env bash
# Pilote la stack de DEV LOCAL (docker-compose) du backend COFRAP :
# MariaDB + les 3 fonctions + Traefik (gateway sur :8080).
#
# Usage :
#   ./scripts/dev/stack.sh up        # build + démarre la stack
#   ./scripts/dev/stack.sh down      # arrête la stack
#   ./scripts/dev/stack.sh logs      # suit les logs
#   ./scripts/dev/stack.sh ps        # état des conteneurs
#
# Prérequis : un fichier .env à la racine (cf. .env.example) avec ENCRYPTION_KEY.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

case "${1:-up}" in
  up)   docker compose up -d --build ;;
  down) docker compose down ;;
  logs) docker compose logs -f ;;
  ps)   docker compose ps ;;
  *)    echo "Usage: $0 {up|down|logs|ps}" >&2; exit 1 ;;
esac
