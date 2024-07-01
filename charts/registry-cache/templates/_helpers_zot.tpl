{{- define "registry_cache.zot_config_yaml" -}}
storage:
  rootDirectory: "/var/lib/registry"
http:
  address: "0.0.0.0"
  port: "5000"
log:
  level: info
extensions:
  sync:
    enable: true
    registries:
{{- if .Values.registryCache.caches }}
{{- range .Values.registryCache.caches }}
      - urls:
          - {{ .remoteUrl | toYaml }}
        content:
          - prefix: {{ .allowedPrefix | toYaml }}
            destination: {{ .serveUnder | toYaml }}
        onDemand: true
{{- end }}
{{- else }}[]
{{- end }}
  metrics:
    enable: true
    prometheus:
      path: "/metrics"
  search:
    enable: true
  ui:
    enable: true
{{ end }}
