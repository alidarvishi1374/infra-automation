# ☸️ Kubespray Kubernetes Automation

Infrastructure automation for provisioning, configuring, and operating Kubernetes clusters using Kubespray, Ansible, and GitLab CI/CD.

This repository extends Kubespray with custom automation for cluster bootstrap, application deployment, certificate distribution, and GitOps integration.

---

## 🚀 Features

* Automated Kubernetes cluster deployment using Kubespray
* Modular GitLab CI/CD pipelines with reusable includes
* ArgoCD deployment and management via Helm
* Harbor CA certificate distribution across cluster nodes
* Custom Helm-based application deployment framework
* Additional operational playbooks for cluster lifecycle management
* Centralized cluster configuration through Ansible group variables
* Support for custom networking and CNI configuration

---

## 📁 Project Structure

```text
k8s-kubespray-automation/
├── ci/                         # Modular GitLab CI jobs and templates
│
├── custom-files/               # Custom manifests, Helm values and application resources
│
├── extra_playbooks/            # Additional operational playbooks
│
├── k8s-net/
│   ├── inventory/
│   └── group_vars/
│       ├── all/
│       └── k8s_cluster/
│
├── roles/
│   ├── harbor_ca/              # Harbor CA certificate distribution
│   ├── custom-helm-apps/       # Custom Helm application deployments
│   ├── etcd/
│   └── network_plugin/
│       └── cilium/
│
├── .gitlab-ci.yml              # Main GitLab CI entrypoint
└── README.md
```

---

## ⚙️ CI/CD Workflow

The GitLab CI pipeline is organized into reusable modules using `include` directives.

Typical workflow:

1. Validate inventory and cluster configuration
2. Provision or upgrade Kubernetes clusters with Kubespray
3. Distribute Harbor CA certificates to cluster nodes
4. Deploy ArgoCD via Helm
5. Deploy custom applications through Helm-based automation
6. Execute operational and maintenance playbooks

---

## 🔐 Secrets Management

Sensitive configuration is stored separately from the main repository configuration.

Examples:

* Harbor credentials
* ArgoCD credentials
* Registry authentication
* Application secrets

Secrets can be encrypted and managed using Ansible Vault.

---

## 🎯 Goals

This project aims to provide a repeatable and production-ready Kubernetes platform with:

* Infrastructure as Code (IaC)
* GitOps-ready application deployment
* Automated cluster lifecycle management
* Consistent security and certificate distribution
* Reusable CI/CD automation
