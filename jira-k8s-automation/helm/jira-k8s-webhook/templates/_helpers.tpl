{{- define "jira-k8s-automation.name" -}}
{{ .Chart.Name }}
{{- end }}

{{- define "jira-k8s-automation.fullname" -}}
{{ printf "%s-%s" .Release.Name .Chart.Name }}
{{- end }}