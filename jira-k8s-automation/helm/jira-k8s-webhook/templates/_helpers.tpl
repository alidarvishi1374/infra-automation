{{/*
Return app name
*/}}
{{- define "jira.name" -}}
{{ .Release.Name }}
{{- end }}