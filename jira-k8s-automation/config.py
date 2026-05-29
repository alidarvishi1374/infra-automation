import os
import json

JIRA_URL = os.getenv("JIRA_URL")
JIRA_TOKEN = os.getenv("JIRA_TOKEN")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")
KUBECONFIG_PATH = os.getenv("KUBECONFIG_PATH", ".kube/config")
KUBECTL_CLIENT_ADDRESS = os.getenv("KUBECTL_CLIENT_ADDRESS")
TEAM_PREFIXES = json.loads(os.getenv("TEAM_PREFIXES", "{}"))
JIRA_FIELDS = json.loads(os.getenv("JIRA_FIELDS", "{}"))