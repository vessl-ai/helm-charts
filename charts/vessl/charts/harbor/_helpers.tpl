{{- define "harbor.labels" -}}
heritage: {{ .Release.Service }}
release: {{ .Release.Name }}
chart: {{ .Chart.Name }}
app: "harbor"
{{- end -}}

{{- define "harbor.matchLabels" -}}
release: {{ .Release.Name }}
app: "harbor"
{{- end -}}

{{- define "harbor.admin.password" -}}
  {{- .Values.harborAdminPassword | nospace | b64enc | quote -}}
{{- end -}}

{{- define "harbor.registry.rawPassword" -}}
  {{- .Values.registryPassword | nospace -}}
{{- end -}}

{{- define "harbor.registry.password" -}}
  {{- include "harbor.registry.rawPassword" . | nospace | b64enc | quote -}}
{{- end -}}

{{- define "harbor.database.rawPassword" -}}
  {{- .Values.databasePassword | nospace -}}
{{- end -}}

{{- define "harbor.database.escapedRawPassword" -}}
  {{- include "harbor.database.rawPassword" . | urlquery | replace "+" "%20" -}}
{{- end -}}

{{- define "harbor.database.encryptedPassword" -}}
  {{- include "harbor.database.rawPassword" . | b64enc | quote -}}
{{- end -}}

{{- define "vessl.image.sourceType" -}}
  {{- .Values.mirrorSourceType | default "quay" -}}
{{- end -}}

{{- define "vessl.image.source" -}}
  {{- if eq (include "vessl.image.sourceType" .) "quay" -}}
    {{- if .Values.enabled -}}
      {{- .Values.clusterIP -}}/quay/vessl-ai
    {{- else -}}
      quay.io/vessl-ai
    {{- end -}}
  {{- else -}}
    {{- fail "Unsupported imageSourceType" -}}
  {{- end -}}
{{- end -}}
