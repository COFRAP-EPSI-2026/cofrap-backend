# Pilote la stack de DEV LOCAL (docker-compose) du backend COFRAP :
# MariaDB + les 3 fonctions + Traefik (gateway sur :8080).
#
# Usage :
#   ./scripts/dev/stack.ps1 up        # build + démarre la stack
#   ./scripts/dev/stack.ps1 down      # arrête la stack
#   ./scripts/dev/stack.ps1 logs      # suit les logs
#   ./scripts/dev/stack.ps1 ps        # état des conteneurs
#
# Prérequis : un fichier .env à la racine (cf. .env.example) avec ENCRYPTION_KEY.

[CmdletBinding()]
param(
    [ValidateSet('up', 'down', 'logs', 'ps')]
    [string]$Command = 'up'
)

$ErrorActionPreference = 'Stop'
$Root = Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) ".." ".."
Set-Location $Root

switch ($Command) {
    'up'   { docker compose up -d --build }
    'down' { docker compose down }
    'logs' { docker compose logs -f }
    'ps'   { docker compose ps }
}
