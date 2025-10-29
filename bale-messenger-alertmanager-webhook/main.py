#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from flask import Flask, request
from gevent.pywsgi import WSGIServer
import json
import socket
import requests
from datetime import datetime, timezone, timedelta
import logging
import os
# ===============================
# 🔹 Bale Configuration
# ===============================

TOKEN = os.getenv("BALE_TOKEN", "")
CHANNEL = os.getenv("BALE_CHAT_ID", "")
BALE_URL = f"https://tapi.bale.ai/bot{TOKEN}/sendMessage"

if not TOKEN or not CHANNEL:
    logger.error("Missing Bale configuration (BALE_TOKEN or BALE_CHAT_ID)")

# ===============================
# 🔹 Logging Setup
# ===============================
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("alert-webhook")

app = Flask(__name__)

# Temporary memory for holding message_id of alerts
alert_messages = {}

# Tehran timezone (UTC+3:30)
TEHRAN = timezone(timedelta(hours=3, minutes=30))


def format_time_tehran(iso_time):
    """Convert ISO time to Tehran local time"""
    try:
        dt = datetime.fromisoformat(iso_time.replace("Z", "+00:00"))
        dt_tehran = dt.astimezone(TEHRAN)
        return dt_tehran.strftime("%Y-%m-%d %H:%M:%S IRST")
    except Exception:
        return "N/A"


def get_severity_emoji(severity, status):
    """Choose emoji color based on severity and status"""
    severity = (severity or "").lower()
    status = (status or "").lower()

    if status == "resolved":
        return "🟢"
    if severity == "critical":
        return "🔴"
    elif severity == "warning":
        return "🟡"
    elif severity == "info":
        return "🔵"
    elif severity == "none":
        return "⚪"
    else:
        return "⚫"


def send_to_bale(alert):
    """Send alert message to Bale and handle replies on resolve"""
    labels = alert.get("labels", {})
    annotations = alert.get("annotations", {})

    alertname = labels.get("alertname", "N/A")
    namespace = labels.get("namespace", "N/A")
    pod = labels.get("pod", "N/A")
    severity = labels.get("severity", "none")
    status = alert.get("status", "N/A")

    starts_at = format_time_tehran(alert.get("startsAt", ""))
    ends_at = format_time_tehran(alert.get("endsAt", ""))

    # If still firing, clear the end time
    if status.lower() == "firing" or ends_at in [
        "1970-01-01 00:00:00 IRST",
        "0001-01-01 00:00:00 IRST",
        "N/A",
    ]:
        ends_at = "-"

    emoji = get_severity_emoji(severity, status)
    summary = annotations.get("summary", "No summary provided")
    description = annotations.get("description", "No description provided")

    fingerprint = alert.get("fingerprint", f"{alertname}-{namespace}-{pod}")

    if status.lower() == "firing":
        text = (
            f"{emoji} ALERT: {alertname}\n"
            f"🧩 Namespace: {namespace}\n"
            f"📦 Pod: {pod}\n"
            f"⚙️ Severity: {severity.upper()}\n"
            f"⚡ Status: {status.upper()}\n"
            f"🕒 Started: {starts_at}\n"
            f"🕒 Ended: {ends_at}\n\n"
            f"📝 Summary: {summary}\n"
            f"💬 Description: {description}"
        )

        payload = {"chat_id": CHANNEL, "text": text}

        try:
            resp = requests.post(BALE_URL, json=payload)
            data = resp.json()
            logger.info(f"Sent FIRING alert [{alertname}] - Status: {resp.status_code}")

            msg_id = data.get("result", {}).get("message_id")
            if msg_id:
                alert_messages[fingerprint] = msg_id
                logger.debug(f"Stored message_id for {fingerprint}")
        except Exception as e:
            logger.error(f"Error sending alert to Bale: {e}")

    elif status.lower() == "resolved":
        msg_id = alert_messages.get(fingerprint)
        if not msg_id:
            logger.warning(
                f"No message_id found for resolved alert {alertname}, skipping reply."
            )
            return

        text = (
            f"🟢 ALERT RESOLVED: {alertname}\n"
            f"🕒 Started: {starts_at}\n"
            f"🕒 Ended: {ends_at}\n"
            f"✅ Status: {status.upper()}"
        )

        payload = {"chat_id": CHANNEL, "text": text, "reply_to_message_id": msg_id}

        try:
            resp = requests.post(BALE_URL, json=payload)
            logger.info(f"Sent RESOLVED reply for {alertname}")
        except Exception as e:
            logger.error(f"Error sending resolved reply: {e}")

        del alert_messages[fingerprint]


@app.route("/alerting", methods=["POST"])
def webhook():
    """Receive alert from Alertmanager"""
    try:
        prometheus_data = json.loads(request.data)
        logger.info("Received new alert batch")
        logger.debug(json.dumps(prometheus_data, indent=4))

        for alert in prometheus_data.get("alerts", []):
            send_to_bale(alert)

        return "OK", 200
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return "Error", 500


if __name__ == "__main__":
    hostname = socket.gethostname()
    IP = socket.gethostbyname(hostname)
    PORT = 5000
    logger.info(f"Webhook running on http://{IP}:{PORT}/alerting")
    WSGIServer(("0.0.0.0", PORT), app).serve_forever()

