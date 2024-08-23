{{- define "lpp_advanced_config.config_json_content" }}
nodePathMap:
{{- with .Values.path }}
  - node: DEFAULT_PATH_FOR_NON_LISTED_NODES
    paths:
      - {{ .default | toString | toYaml }}
{{- range .node_override }}
      - node: {{ .node_name | toString | toYaml }}
        paths:
          - {{ .path | toString | toYaml }}
{{- end }}
{{- end }}
{{- end }}
