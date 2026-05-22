#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Build les 3 images des fonctions COFRAP.

.DESCRIPTION
    Deux modes :
      - LOCAL : build mono-architecture + import dans le cluster local
                (auto-détecte minikube / K3s / k3d / kind).
      - PUSH  : build MULTI-architecture (buildx) + push sur un registry (-Push).

.EXAMPLE
    ./scripts/prod/build-images.ps1
    ./scripts/prod/build-images.ps1 -Registry "ghcr.io/mon-org" -Push
    ./scripts/prod/build-images.ps1 -Tag dev -Push
    ./scripts/prod/build-images.ps1 -Platforms "linux/amd64,linux/arm64,linux/arm/v7" -Push
#>
[CmdletBinding()]
param(
    [string]$Registry = "ghcr.io/cofrap-epsi-2026",
    [string]$Tag = "latest",  # x-release-please-version
    [string]$Platforms = "linux/amd64,linux/arm64",
    [ValidateSet("auto", "minikube", "kind", "k3d", "k3s", "generic")]
    [string]$ClusterType = "auto",
    [switch]$Push
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Join-Path $ScriptDir ".." ".."

$Functions = @("generate-password", "generate-2fa", "authenticate-user")

function Write-Step ($msg) { Write-Host "▸ $msg" -ForegroundColor Cyan }
function Write-Ok ($msg)   { Write-Host $msg     -ForegroundColor Green }
function Write-Warn2 ($msg){ Write-Host $msg     -ForegroundColor Yellow }
function Write-Err ($msg)  { Write-Host $msg     -ForegroundColor Red }

# ─── Mode PUSH : build multi-architecture + push (buildx) ────────────────────
if ($Push) {
    Write-Step "Build multi-architecture [$Platforms] + push vers $Registry"
    # Le multi-plateforme exige un builder buildx « docker-container ».
    docker buildx inspect cofrap-builder *> $null
    if ($LASTEXITCODE -ne 0) {
        docker buildx create --name cofrap-builder --driver docker-container | Out-Null
    }
    foreach ($fn in $Functions) {
        $image = "${Registry}/${fn}:${Tag}"
        Write-Step "  $image"
        docker buildx build --builder cofrap-builder `
            --platform $Platforms `
            --provenance=false `
            --push `
            -t $image (Join-Path $Root "functions" $fn)
        if ($LASTEXITCODE -ne 0) { Write-Err "Build $fn échoué"; exit 1 }
    }
    Write-Ok "3 images multi-arch poussées [$Platforms]."
    Write-Host ""
    Write-Host "(Re)déployer les fonctions :"
    Write-Host "  helm upgrade cofrap ./deploy/helm/cofrap -n cofrap --reuse-values ``"
    Write-Host "    --set functions.registry=$Registry --set functions.version=$Tag"
    exit 0
}

# ─── Mode LOCAL : build mono-arch + import dans le cluster ───────────────────
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

switch ($Cluster) {
    "minikube" {
        Write-Warn2 "Pointage du Docker CLI vers le daemon minikube"
        & minikube -p minikube docker-env --shell powershell | Invoke-Expression
    }
    "generic" {
        Write-Err "Cluster non local. Pour publier les images, utilise -Push :"
        Write-Err "  ./scripts/prod/build-images.ps1 -Push"
        exit 1
    }
}

foreach ($fn in $Functions) {
    $image = "${Registry}/${fn}:${Tag}"
    Write-Step "Build $image"
    docker build -t $image (Join-Path $Root "functions" $fn)
    if ($LASTEXITCODE -ne 0) { Write-Err "Build $fn échoué"; exit 1 }
}

switch ($Cluster) {
    "minikube" {
        Write-Ok "Images disponibles dans le daemon minikube (pas de push nécessaire)."
    }
    "k3s" {
        Write-Step "Import des images dans containerd (K3s)"
        foreach ($fn in $Functions) {
            docker save "${Registry}/${fn}:${Tag}" | sudo k3s ctr images import -
        }
        Write-Ok "Images importées dans K3s."
    }
    "k3d" {
        Write-Step "Import des images dans K3d"
        $clusterName = (kubectl config current-context) -replace "^k3d-", ""
        foreach ($fn in $Functions) {
            & k3d image import "${Registry}/${fn}:${Tag}" -c $clusterName
        }
        Write-Ok "Images importées dans K3d."
    }
    "kind" {
        Write-Step "Import des images dans KinD"
        foreach ($fn in $Functions) {
            & kind load docker-image "${Registry}/${fn}:${Tag}"
        }
        Write-Ok "Images importées dans KinD."
    }
}

Write-Host ""
Write-Host "(Re)déployer les fonctions :"
Write-Host "  helm upgrade cofrap ./deploy/helm/cofrap -n cofrap --reuse-values ``"
Write-Host "    --set functions.registry=$Registry --set functions.version=$Tag --set functions.pullPolicy=IfNotPresent"
Write-Host "  kubectl -n openfaas-fn rollout restart deployment -l 'faas_function'"
