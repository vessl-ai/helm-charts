{{/*
Truncate and clean image name for use in container names
*/}}

{{- define "imagePrepull.truncateImageName" -}}
{{- $parts := splitList "/" . -}}
{{- $name := last $parts -}}
{{- $truncated := trunc 40 $name -}}
{{- $cleaned := regexReplaceAll "[^a-zA-Z0-9-]" $truncated "-" -}}
{{- $cleaned | lower -}}
{{- end -}}
