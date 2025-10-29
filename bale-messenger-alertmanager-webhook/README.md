# Alert Webhook for Bale Messenger

This project is a **simple Alertmanager webhook** that sends alerts to a **Bale Messenger channel**.

The webhook handles both `firing` and `resolved` alerts, displays severity with emojis, and can be easily deployed on Kubernetes.

---

## Features

* Sends Prometheus Alertmanager alerts to Bale Messenger
* Handles `firing` and `resolved` statuses
* Severity displayed with emojis (Critical 🔴, Warning 🟡, Info 🔵, None ⚪)
* Dockerized for local execution
* Helm chart for easy Kubernetes deployment
* Secrets support (token and chat_id) in base64
* Configurable namespace, image, and resources via `values.yaml`

---

## Prerequisites

* Python 3.11+
* Kubernetes cluster with Helm installed
* Bale bot access and a channel
* Bale bot added to the channel with **send message permissions**

---

## Bale Bot Setup

1. Create a bot in Bale and get the **token**.
2. Add the bot to your target channel and grant **send message permissions**.
3. Get the **chat_id** of the channel.

> These values will be used in the Kubernetes Secret or `values.yaml`.

---

## Docker Usage

### Build Docker Image

```bash
docker build -t alert-webhook:latest .
```

### Run Locally

```bash
docker run -p 5000:5000 \
  -e BALE_TOKEN="your-bot-token" \
  -e BALE_CHANNEL="your-channel-chat-id" \
  alert-webhook:latest
```

> The `/alerting` endpoint only accepts **POST** requests.

---

## Kubernetes Deployment with Helm

### Navigate to Chart Directory

```bash
cd charts/
```

### Install Helm Chart

```bash
helm install alertmanager alert-webhook
```

### `values.yaml` Example

```yaml
namespace: default
image:
  repository: alert-webhook
  tag: latest
bale:
  token: "your-bot-token"
  channel: "your-channel-chat-id"
```

---

## Alertmanager Configuration

Add the following receiver to Alertmanager:

```yaml
receivers:
- name: 'bale-channel'
  webhook_configs:
  - url: 'http://alert-webhook.<namespace>.svc.<cluster_domain>/alerting'
```

Add a route to send alerts:

```yaml
route:
  group_by: ['namespace']
  group_wait: 5m
  group_interval: 30m
  repeat_interval: 12h
  receiver: 'bale-channel'
  routes:
  - receiver: 'bale-channel'
    matchers:
    - severity =~ "info|warning|critical"
```

Other `global` settings and `inhibit_rules` can be configured as needed.

---

## Project Structure

```text
.
├── charts/alert-webhook          # Helm chart
│   ├── Chart.yaml
│   ├── templates/
│   │   ├── deployment.yaml
│   │   ├── secret.yaml
│   │   └── service.yaml
│   └── values.yaml
├── Dockerfile
├── main.py                       # Main webhook script
├── requirements.txt
└── .dockerignore
```

---

## Notes

* `/alerting` endpoint only accepts **POST** requests.
* You can add a `/healthz` endpoint for Kubernetes liveness/readiness probes.
* Namespace and resource limits can be customized via `values.yaml`.

