from prometheus_client import Counter
from prometheus_client import Histogram
from prometheus_client import Gauge
from prometheus_client import Info
from prometheus_client import generate_latest
from prometheus_client import CONTENT_TYPE_LATEST


# -----------------------------------
# Total Jira webhook requests
# -----------------------------------

jira_requests_total = Counter(
    "jira_requests_total",
    "Total Jira webhook requests",
    [
        "team",
        "project",
        "app",
        "creator",
        "approved_by",
        "status"
    ]
)


# -----------------------------------
# Namespace creation success
# -----------------------------------

namespace_creation_success_total = Counter(
    "namespace_creation_success_total",
    "Successful namespace creations",
    [
        "team",
        "project",
        "app",
        "creator",
        "approved_by"
    ]
)


# -----------------------------------
# Namespace creation failures
# -----------------------------------

namespace_creation_failed_total = Counter(
    "namespace_creation_failed_total",
    "Failed namespace creations",
    [
        "team",
        "project",
        "app",
        "creator",
        "approved_by",
        "error_type"
    ]
)


# -----------------------------------
# Kubernetes API errors
# -----------------------------------

kubernetes_api_errors_total = Counter(
    "kubernetes_api_errors_total",
    "Kubernetes API errors",
    [
        "operation",
        "error_type",
        "team",
        "project",
        "app"
    ]
)


# -----------------------------------
# Kubernetes namespace operations
# -----------------------------------

kubernetes_namespace_operations_total = Counter(
    "kubernetes_namespace_operations_total",
    "Kubernetes namespace operations",
    [
        "operation",
        "namespace",
        "team",
        "project",
        "app",
        "result"
    ]
)


# -----------------------------------
# Request processing duration
# -----------------------------------

request_processing_seconds = Histogram(
    "request_processing_seconds",
    "Webhook processing duration in seconds",
    [
        "team",
        "project",
        "app",
        "status"
    ],
    buckets=(
        0.1,
        0.3,
        0.5,
        1,
        2,
        5,
        10,
        20,
        30,
        60
    )
)


# -----------------------------------
# Active requests
# -----------------------------------

active_requests = Gauge(
    "active_requests",
    "Currently processing webhook requests"
)


# -----------------------------------
# Namespace info metric
# -----------------------------------

namespace_info = Gauge(
    "namespace_info",
    "Namespace metadata information",
    [
        "namespace",
        "team",
        "project",
        "app",
        "site",
        "creator",
        "approved_by",
        "request_number"
    ]
)


# -----------------------------------
# Last namespace creation timestamp
# -----------------------------------

last_namespace_creation_timestamp = Gauge(
    "last_namespace_creation_timestamp",
    "Unix timestamp of last successful namespace creation",
    [
        "namespace",
        "team",
        "project",
        "app"
    ]
)


# -----------------------------------
# Jira transition operations
# -----------------------------------

jira_transition_total = Counter(
    "jira_transition_total",
    "Jira workflow transitions",
    [
        "transition_name",
        "team",
        "project",
        "app",
        "approved_by",
        "result"
    ]
)


# -----------------------------------
# Jira comments operations
# -----------------------------------

jira_comments_total = Counter(
    "jira_comments_total",
    "Jira comment operations",
    [
        "team",
        "project",
        "app",
        "result"
    ]
)


# -----------------------------------
# Duplicate namespace detection
# -----------------------------------

duplicate_namespace_total = Counter(
    "duplicate_namespace_total",
    "Duplicate namespace requests",
    [
        "namespace",
        "team",
        "project",
        "app",
        "creator"
    ]
)


# -----------------------------------
# Invalid requests
# -----------------------------------

invalid_requests_total = Counter(
    "invalid_requests_total",
    "Invalid or ignored requests",
    [
        "reason"
    ]
)


# -----------------------------------
# Webhook authentication failures
# -----------------------------------

webhook_auth_failures_total = Counter(
    "webhook_auth_failures_total",
    "Webhook authentication failures"
)


# -----------------------------------
# Flask app info
# -----------------------------------

application_info = Info(
    "application_info",
    "Application information"
)

application_info.info({
    "application": "jira-kubernetes-namespace-automation",
    "environment": "production"
})


# -----------------------------------
# Metrics endpoint helper
# -----------------------------------

def metrics_response():

    return (
        generate_latest(),
        200,
        {
            "Content-Type": CONTENT_TYPE_LATEST
        }
    )