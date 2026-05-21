#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Désinstalle la stack COFRAP. Garde OpenFaaS en place par défaut.

.PARAMETER PurgeOpenFaaS
    Si présent, désinstalle aussi OpenFaaS et son namespace.
#>
[CmdletBinding()]
param(
    [string]$Namespace = "cofrap",
    [string]$ReleaseName = "cofrap",
    [string]$OpenFaaSNamespace = "openfaas",
    [string]$OpenFaaSFnNamespace = "openfaas-fn",
    [switch]$PurgeOpenFaaS
)

$ErrorActionPreference = "Continue"

function Write-Step ($msg) { Write-Host "▸ $msg" -ForegroundColor Cyan }
function Write-Ok ($msg)   { Write-Host $msg     -ForegroundColor Green }

Write-Step "Désinstallation du chart cofrap"
helm uninstall $ReleaseName -n $Namespace 2>$null

Write-Step "Nettoyage des secrets openfaas-fn"
kubectl -n $OpenFaaSFnNamespace delete secret mariadb-password encryption-key --ignore-not-found

Write-Step "Nettoyage des PVC MariaDB"
kubectl -n $Namespace delete pvc -l "app.kubernetes.io/instance=$ReleaseName" --ignore-not-found

if ($PurgeOpenFaaS) {
    Write-Step "Désinstallation d'OpenFaaS (-PurgeOpenFaaS)"
    helm uninstall openfaas -n $OpenFaaSNamespace 2>$null
    kubectl delete namespace $OpenFaaSNamespace $OpenFaaSFnNamespace --ignore-not-found
}

kubectl delete namespace $Namespace --ignore-not-found

Write-Ok "Désinstallation terminée"
