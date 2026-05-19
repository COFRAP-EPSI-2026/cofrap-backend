{{/*
Nom court (utilisé pour les ressources créées).
*/}}
{{- define "cofrap.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Nom complet (release + chart). 63 chars max.
*/}}
{{- define "cofrap.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- $name := default .Chart.Name .Values.nameOverride -}}
{{- if contains $name .Release.Name -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{/*
Labels standard Kubernetes.
*/}}
{{- define "cofrap.labels" -}}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
app.kubernetes.io/name: {{ include "cofrap.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: cofrap
{{- end -}}

{{/*
Vérifie la présence des secrets obligatoires.
*/}}
{{- define "cofrap.requireSecrets" -}}
{{- if not .Values.secrets.encryptionKey -}}
{{- fail "secrets.encryptionKey est obligatoire — générer avec: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"" -}}
{{- end -}}
{{- if not .Values.secrets.mariadbPassword -}}
{{- fail "secrets.mariadbPassword est obligatoire" -}}
{{- end -}}
{{- if not .Values.secrets.mariadbRootPassword -}}
{{- fail "secrets.mariadbRootPassword est obligatoire" -}}
{{- end -}}
{{- end -}}
