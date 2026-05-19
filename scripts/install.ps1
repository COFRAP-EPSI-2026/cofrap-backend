#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Installe la stack COFRAP (OpenFaaS + chart cofrap) sur un cluster Kubernetes.

.DESCRIPTION
    Équivalent PowerShell de scripts/install.sh — compatible Windows natif (PowerShell 5.1+ ou PS Core 7+).
    Vérifie les prérequis, installe OpenFaaS via Helm, génère les secrets, déploie le chart cofrap.

.PARAMETER Namespace
    Namespace cible pour la BDD et les ressources internes. Défaut : cofrap.

.PARAMETER ReleaseName
    Nom de la release Helm. Défaut : cofrap.

.PARAMETER OpenFaaSNamespace
    Namespace OpenFaaS. Défaut : openfaas.

.PARAMETER OpenFaaSFnNamespace
    Namespace des fonctions OpenFaaS. Défaut : openfaas-fn.

.PARAMETER SkipOpenFaaS
    Skip l'install OpenFaaS si le cluster en a déjà un.

.EXAMPLE
    ./scripts/install.ps1
    ./scripts/install.ps1 -Namespace demo -SkipOpenFaaS
#>
[CmdletBinding()]
param(
    [string]$Namespace = "cofrap",
    [string]$ReleaseName = "cofrap",
    [string]$OpenFaaSNamespace = "openfaas",
    [string]$OpenFaaSFnNamespace = "openfaas-fn",
    [switch]$SkipOpenFaaS
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ChartPath = Join-Path $ScriptDir ".." "deploy" "helm" "cofrap"

# ─── helpers ────────────────────────────────────────────────────────────────
function Write-Step ($msg)  { Write-Host "▸ $msg" -ForegroundColor Cyan }
function Write-Ok ($msg)    { Write-Host $msg     -ForegroundColor Green }
function Write-Warn2 ($msg) { Write-Host $msg     -ForegroundColor Yellow }
function Write-Err ($msg)   { Write-Host $msg     -ForegroundColor Red }

function Require-Cmd($name) {
    if (-not (Get-Command $name -ErrorAction SilentlyContinue)) {
        Write-Err "Manquant : $name"
        exit 1
    }
}

function New-FernetKey {
    # 1) Python + cryptography (canonique)
    $py = Get-Command python -ErrorAction SilentlyContinue
    if (-not $py) { $py = Get-Command python3 -ErrorAction SilentlyContinue }
    if ($py) {
        $hasCrypto = & $py.Source -c "import cryptography" 2>$null
        if ($LASTEXITCODE -eq 0) {
            return (& $py.Source -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())").Trim()
        }
    }
    # 2) .NET natif (32 bytes random → base64 URL-safe)
    Add-Type -AssemblyName System.Security
    $bytes = New-Object byte[] 32
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    $b64 = [Convert]::ToBase64String($bytes)
    return ($b64 -replace '\+','-' -replace '/','_')
}

function New-Hex16 {
    $bytes = New-Object byte[] 16
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    return -join ($bytes | ForEach-Object { '{0:x2}' -f $_ })
}

# ─── 1. Vérification prérequis ──────────────────────────────────────────────
Write-Step "Vérification des prérequis"
Require-Cmd kubectl
Require-Cmd helm
kubectl cluster-info *> $null
if ($LASTEXITCODE -ne 0) { Write-Err "kubectl ne peut pas joindre le cluster"; exit 1 }
Write-Ok "kubectl + helm OK, cluster joignable."

# ─── 2. Install OpenFaaS ────────────────────────────────────────────────────
if ($SkipOpenFaaS) {
    Write-Warn2 "-SkipOpenFaaS → on suppose qu'OpenFaaS est déjà installé"
} else {
    Write-Step "Installation d'OpenFaaS Community via Helm"
    helm repo add openfaas https://openfaas.github.io/faas-netes/ 2>$null | Out-Null
    helm repo update openfaas | Out-Null

    kubectl create namespace $OpenFaaSNamespace --dry-run=client -o yaml | kubectl apply -f -
    kubectl create namespace $OpenFaaSFnNamespace --dry-run=client -o yaml | kubectl apply -f -

    # NB : `operator.create=true` est réservé à OpenFaaS Pro depuis 2023.
    # En Community, on déploie les fonctions comme Deployments + Services classiques
    # labellisés `faas_function=<name>` — le gateway les découvre automatiquement.
    helm upgrade --install openfaas openfaas/openfaas `
        --namespace $OpenFaaSNamespace `
        --set "functionNamespace=$OpenFaaSFnNamespace" `
        --set "generateBasicAuth=true" `
        --set "basic_auth=true" `
        --wait --timeout 5m

    if ($LASTEXITCODE -ne 0) { Write-Err "Échec install OpenFaaS"; exit 1 }
    Write-Ok "OpenFaaS installé."
}

# ─── 3. Génération des secrets ──────────────────────────────────────────────
Write-Step "Génération des secrets applicatifs"
$EncryptionKey       = if ($env:ENCRYPTION_KEY)        { $env:ENCRYPTION_KEY }        else { New-FernetKey }
$MariadbPassword     = if ($env:MARIADB_PASSWORD)      { $env:MARIADB_PASSWORD }      else { New-Hex16 }
$MariadbRootPassword = if ($env:MARIADB_ROOT_PASSWORD) { $env:MARIADB_ROOT_PASSWORD } else { New-Hex16 }
Write-Ok "Secrets générés."

# ─── 4. Install du chart cofrap ─────────────────────────────────────────────
Write-Step "Installation du chart cofrap"
helm upgrade --install $ReleaseName $ChartPath `
    --namespace $Namespace --create-namespace `
    --set "openfaas.functionNamespace=$OpenFaaSFnNamespace" `
    --set "secrets.encryptionKey=$EncryptionKey" `
    --set "secrets.mariadbPassword=$MariadbPassword" `
    --set "secrets.mariadbRootPassword=$MariadbRootPassword" `
    --wait --timeout 5m

if ($LASTEXITCODE -ne 0) { Write-Err "Échec install chart cofrap"; exit 1 }

# ─── 5. Affichage final ─────────────────────────────────────────────────────
Write-Host ""
Write-Ok "============================================================"
Write-Ok "  Stack COFRAP installee"
Write-Ok "============================================================"
Write-Host ""
Write-Host "Namespace cofrap          : $Namespace"
Write-Host "Namespace OpenFaaS        : $OpenFaaSNamespace"
Write-Host "Namespace fonctions       : $OpenFaaSFnNamespace"
Write-Host ""
Write-Host "Mot de passe MariaDB (root)  : $MariadbRootPassword"
Write-Host "Mot de passe MariaDB (app)   : $MariadbPassword"
Write-Host "Cle Fernet (encryption-key)  : $EncryptionKey"
Write-Host ""
Write-Warn2 "Sauvegarder ces valeurs hors du cluster. La cle Fernet ne peut PAS"
Write-Warn2 "etre regeneree sans perdre les comptes existants."
Write-Host ""
Write-Host "Mot de passe admin OpenFaaS :"
Write-Host "  kubectl -n $OpenFaaSNamespace get secret basic-auth -o jsonpath='{.data.basic-auth-password}' | base64 -d"
Write-Host ""
Write-Host "Pour acceder au gateway en local :"
Write-Host "  kubectl -n $OpenFaaSNamespace port-forward svc/gateway 8080:8080"
Write-Host "  -> http://127.0.0.1:8080"
Write-Host ""
