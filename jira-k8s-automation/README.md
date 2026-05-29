# ⚙️ Jira Kubernetes Automation

An event-driven automation service that integrates Jira workflows with Kubernetes clusters to dynamically provision infrastructure resources.

This service acts as a bridge between Jira and Kubernetes, enabling automatic infrastructure provisioning based on Jira events (webhooks).

---

## 🚀 Overview

When a Jira event is triggered, this service processes the payload and translates it into Kubernetes actions such as:

- Namespace provisioning
- RBAC and access configuration
- Team-based resource mapping
- Extensible automation workflows (future-ready for user provisioning and advanced access control)

---

## 🧠 Architecture

Jira Webhook  
→ Flask API (main.py)  
→ Business Logic (services/)  
→ Kubernetes API  
→ Helm-based Deployment / Config-driven execution  

---

## 📁 Project Structure

.
├── argocd/                # ArgoCD manifests (GitOps integration)
├── helm/                  # Helm chart for deployment
├── templates/             # Kubernetes manifests (legacy / helpers)
├── services/              # Core business logic (K8s + Jira integration)
├── main.py                # Entry point (Flask app)
├── config.py              # Environment-based configuration loader
├── Dockerfile
├── requirements.txt
└── .gitlab-ci.yml         # CI/CD pipeline

---

## ⚙️ Configuration

Environment variables injected via ConfigMap + Secret:

- JIRA_URL
- JIRA_TOKEN
- WEBHOOK_SECRET
- KUBECONFIG_PATH
- KUBECTL_CLIENT_ADDRESS
- TEAM_PREFIXES (JSON)
- JIRA_FIELDS (JSON)

---

## 🧩 Key Features

- Event-driven Jira webhook processing
- Kubernetes namespace provisioning
- Team-based namespace mapping
- Secure secret handling
- Helm-based deployment
- GitOps-ready (ArgoCD support)

---

## 🔐 Security Model

- Secrets via Kubernetes Secret
- Config via ConfigMap
- RBAC-based access control
- No hardcoded credentials

---

## 🚀 Current Capabilities

- Namespace provisioning from Jira events
- Team mapping to namespaces
- Webhook authentication
- Kubernetes API integration

---

## 🧰 Tech Stack

- Python (Flask)
- Kubernetes API
- Helm
- Docker
- ArgoCD
- GitLab CI/CD

---

## 📦 Deployment

docker build -t jira-k8s-automation .
docker run -p 5000:5000 jira-k8s-automation

helm install jira-k8s-automation ./helm

---

## 👤 Maintainer

Ali Darvishi — DevOps Engineer

