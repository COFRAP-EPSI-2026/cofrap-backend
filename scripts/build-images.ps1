#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Build les 3 images des fonctions et les rend disponibles dans le cluster local.

.DESCRIPTION
    Auto-détecte minikube / K3s / kind / Docker Desktop. Pour les clusters distants,
    push sur le registry de ton choix avec -Push.

.EXAMPLE
    ./scripts/build-images.ps1
    ./scripts/build-images.ps1 -Registry "ghcr.io/mon-org" -Push
    ./scripts/build-images.ps1 -Tag dev
#>
[CmdletBinding()]
param(
    [string]$Registry = "ghcr.io/cofrap-epsi-2026",
    [string]$Tag = "0.1.0",
    [ValidateSet("auto", "minikube", "kind", "k3d", "k3s", "generic")]
    [string]$ClusterType = "auto",
    [switch]$Push
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Join-Path $ScriptDir ".."

$Functions = @("generate-password", "generate-2fa", "authenticate-user")

function Write-Step ($msg) { Write-Host "▸ $msg" -ForegroundColor Cyan }
function Write-Ok ($msg)   { Write-Host $msg     -ForegroundColor Green }
function Write-Warn2 ($msg){ Write-Host $msg     -ForegroundColor Yellow }
function Write-Err ($msg)  { Write-Host $msg     -ForegroundColor Red }

# ─── Détection du cluster ───────────────────────────────────────────────────
function Detect-Cluster {
    if ($ClusterType -ne "auto") { return $ClusterType }
    if (Get-Command minikube -ErrorAction SilentlyContinue) {
        & minikube status *> $null
        if ($LASTEXITCODE -eq 0) { return "minikube" }
    }
    $ctx = (kubectl config current-context 2>$null)
    if ($ctx -like "*kind*") { return "kind" }
    if ($ctx -like "*k3d*")  { return "k3d" }
    if (Get-Command k3s -ErrorAction SilentlyContinue) { return "k3s" }
    return "generic"
}

$Cluster = Detect-Cluster
Write-Step "Cluster détecté : $Cluster"

# ─── Configuration du daemon Docker ─────────────────────────────────────────
switch ($Cluster) {
    "minikube" {
        Write-Warn2 "Pointage du Docker CLI vers le daemon minikube"
        & minikube -p minikube docker-env --shell powershell | Invoke-Expression
    }
    "generic" {
        if (-not $Push) {
            Write-Err "Cluster non local détecté. Pour pousser sur un registry :"
            Write-Err "  ./scripts/build-images.ps1 -Registry ghcr.io/mon-org -Push"
            exit 1
        }
    }
}

# ─── Build ──────────────────────────────────────────────────────────────────
foreach ($fn in $Functions) {
    $image = "${Registry}/${fn}:${Tag}"
    Write-Step "Build $image"
    docker build -t $image (Join-Path $Root "functions" $fn)
    if ($LASTEXITCODE -ne 0) { Write-Err "Build $fn échoué"; exit 1 }
}

# ─── Distribution ───────────────────────────────────────────────────────────
switch ($Cluster) {
    "minikube" {
        Write-Ok "Images disponibles dans le daemon minikube (pas de push nécessaire)."
    }
    "k3s" {
        Write-Step "Import des images dans containerd (K3s)"
        foreach ($fn in $Functions) {
            $image = "${Registry}/${fn}:${Tag}"
            docker save $image | sudo k3s ctr images import -
        }
        Write-Ok "Images importées dans K3s."
    }
    "k3d" {
        Write-Step "Import des images dans K3d"
        $clusterName = (kubectl config current-context) -replace "^k3d-", ""
        foreach ($fn in $Functions) {
            $image = "${Registry}/${fn}:${Tag}"
            & k3d image import $image -c $clusterName
        }
        Write-Ok "Images importées dans K3d."
    }
    "kind" {
        Write-Step "Import des images dans KinD"
        foreach ($fn in $Functions) {
            $image = "${Registry}/${fn}:${Tag}"
            & kind load docker-image $image
        }
        Write-Ok "Images importées dans KinD."
    }
    "generic" {
        if ($Push) {
            Write-Step "Push vers $Registry"
            foreach ($fn in $Functions) {
                $image = "${Registry}/${fn}:${Tag}"
                docker push $image
            }
            Write-Ok "Images poussées."
        }
    }
}

Write-Host ""
Write-Host "Pour redéployer les fonctions avec ces images :"
Write-Host "  helm upgrade cofrap ./deploy/helm/cofrap -n cofrap --reuse-values ``"
Write-Host "    --set functions.registry=$Registry ``"
Write-Host "    --set functions.version=$Tag ``"
Write-Host "    --set functions.pullPolicy=IfNotPresent"
Write-Host ""
Write-Host "Puis forcer le redéploiement (sinon K8s garde les anciens pods sans pull) :"
Write-Host "  kubectl -n openfaas-fn rollout restart deployment -l 'faas_function'"
