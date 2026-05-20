# ☸️ Kubespray Kubernetes Automation

Infrastructure automation for deploying and customizing Kubernetes clusters using Kubespray and Ansible.

This project contains custom roles, network configurations, and CI/CD integration for Kubernetes cluster provisioning.

---

## 📁 Project Structure

```text
k8s-kubespray-automation/
├── k8s-net/
│   └── group_vars/
│       ├── all/
│       └── k8s_cluster/
├── roles/
│   ├── etcd/
│   │   └── tasks/
│   └── network_plugin/
│       └── cilium/
│           ├── tasks/
│           └── templates/
└── .gitlab-ci.yml