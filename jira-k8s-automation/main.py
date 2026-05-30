import time

from services.exceptions import KubernetesError

from flask import (
    Flask,
    request,
    jsonify,
    abort
)

from kubernetes.client.rest import ApiException

from config import (
    WEBHOOK_SECRET,
    JIRA_FIELDS,
    KUBECTL_CLIENT_ADDRESS
)

from services.namespace_service import (
    generate_namespace_name,
    render_namespace_manifest,
    sanitize_name
)

from services.kubernetes_service import (
    apply_namespace_manifest,
    core_api
)

from services.jira_service import (
    add_comment,
    transition_issue,
    jira_health_check
)

from services.logger_service import logger

from services.metrics_service import (
    jira_requests_total,
    namespace_creation_success_total,
    namespace_creation_failed_total,
    kubernetes_api_errors_total,
    kubernetes_namespace_operations_total,
    request_processing_seconds,
    active_requests,
    namespace_info,
    last_namespace_creation_timestamp,
    jira_transition_total,
    jira_comments_total,
    duplicate_namespace_total,
    invalid_requests_total,
    webhook_auth_failures_total,
    metrics_response
)


app = Flask(__name__)


# -----------------------------------
# Metrics Endpoint
# -----------------------------------

@app.route("/metrics")
def metrics():

    return metrics_response()


# -----------------------------------
# Health Endpoint
# -----------------------------------

@app.route("/health")
def health():

    jira_ok = jira_health_check()

    if not jira_ok:
        return jsonify({
            "status": "not ready",
            "dependency": {
                "jira": "unreachable"
            },
            "message": "Cannot connect to Jira API"
        }), 503

    return jsonify({
        "status": "ready",
        "dependency": {
            "jira": "ok"
        }
    }), 200


# -----------------------------------
# Jira Webhook
# -----------------------------------

@app.route("/webhook", methods=["POST"])
def jira_webhook():

    start_time = time.time()

    active_requests.inc()

    team = "unknown"
    project = "unknown"
    app_name = "unknown"
    creator = "unknown"
    approved_by = "unknown"
    namespace = "unknown"

    try:

        # --------------------------------
        # Validate webhook token
        # --------------------------------

        token = request.args.get("token")

        if token != WEBHOOK_SECRET:

            webhook_auth_failures_total.inc()

            abort(401)

        data = request.json

        # --------------------------------
        # Ignore bot events
        # --------------------------------

        webhook_user = (
            data.get("user", {})
            .get("name", "unknown")
        )

        approved_by = webhook_user

        logger.info(
            f"Webhook user={webhook_user}"
        )

        if webhook_user == "k8s_auto":

            invalid_requests_total.labels(
                reason="bot_request"
            ).inc()

            logger.info(
                "Ignoring bot webhook"
            )

            return jsonify({
                "message": "ignored bot"
            }), 200

        # --------------------------------
        # Jira issue data
        # --------------------------------

        issue = data.get("issue", {})

        issue_key = issue.get("key")

        request_number = issue_key

        issue_fields = issue.get(
            "fields",
            {}
        )

        creator = (
            issue_fields
            .get("creator", {})
            .get("name", "unknown")
        )

        # --------------------------------
        # Current Jira status
        # --------------------------------

        status_name = (
            issue_fields
            .get("status", {})
            .get("name")
        )

        logger.info(
            f"Issue={issue_key} "
            f"Status={status_name}"
        )

        # --------------------------------
        # Run only when approved
        # --------------------------------

        if status_name != "تایید شده توسط ادمین کوبرنتیز":

            invalid_requests_total.labels(
                reason="status_not_approved"
            ).inc()

            logger.info(
                "Ignoring issue"
            )

            return jsonify({
                "message": "ignored"
            }), 200

        # --------------------------------
        # Read Jira custom fields
        # --------------------------------

        site = issue_fields[
            JIRA_FIELDS["site"]
        ]["value"]

        team = issue_fields[
            JIRA_FIELDS["team"]
        ]["value"]

        project = issue_fields[
            JIRA_FIELDS["project"]
        ]

        app_name = issue_fields[
            JIRA_FIELDS["application"]
        ]

        # --------------------------------
        # Sanitize values
        # --------------------------------

        site = sanitize_name(site)

        team = sanitize_name(team)

        project = sanitize_name(project)

        app_name = sanitize_name(app_name)

        logger.info(
            f"site={site} "
            f"team={team} "
            f"project={project} "
            f"app={app_name} "
            f"creator={creator} "
            f"approved_by={approved_by} "
            f"request_number={request_number}"
        )

        # --------------------------------
        # Request Metrics
        # --------------------------------

        jira_requests_total.labels(
            team=team,
            project=project,
            app=app_name,
            creator=creator,
            approved_by=approved_by,
            status="approved"
        ).inc()

        # --------------------------------
        # Generate namespace name
        # --------------------------------

        namespace = generate_namespace_name(
            team=team,
            project=project,
            app=app_name
        )

        logger.info(
            f"Namespace={namespace}"
        )

        # --------------------------------
        # Prevent duplicate namespace
        # --------------------------------

        try:

            core_api.read_namespace(
                namespace
            )

            duplicate_namespace_total.labels(
                namespace=namespace,
                team=team,
                project=project,
                app=app_name,
                creator=creator
            ).inc()

            logger.error(
                f"Namespace already exists: "
                f"{namespace}"
            )

            raise KubernetesError(
                f"Namespace '{namespace}' already exists",
                error_type="AlreadyExists"
            )

        except ApiException as e:

            if e.status != 404:

                kubernetes_api_errors_total.labels(
                    operation="read_namespace",
                    error_type=str(e.status),
                    team=team,
                    project=project,
                    app=app_name
                ).inc()

                raise

        # --------------------------------
        # Render namespace manifest
        # --------------------------------

        namespace_manifest = (
            render_namespace_manifest(
                namespace=namespace,
                team=team,
                project=project,
                app=app_name,
                site=site,
                request_number=request_number
            )
        )

        logger.info(
            "Namespace manifest rendered"
        )

        # --------------------------------
        # Apply namespace
        # --------------------------------

        apply_namespace_manifest(
            namespace_manifest
        )

        kubernetes_namespace_operations_total.labels(
            operation="create",
            namespace=namespace,
            team=team,
            project=project,
            app=app_name,
            result="success"
        ).inc()

        logger.info(
            "Namespace created successfully"
        )

        # --------------------------------
        # Namespace Metadata Metric
        # --------------------------------

        namespace_info.labels(
            namespace=namespace,
            team=team,
            project=project,
            app=app_name,
            site=site,
            creator=creator,
            approved_by=approved_by,
            request_number=request_number
        ).set(1)

        # --------------------------------
        # Last Success Timestamp
        # --------------------------------

        last_namespace_creation_timestamp.labels(
            namespace=namespace,
            team=team,
            project=project,
            app=app_name
        ).set(time.time())

        # --------------------------------
        # Success Metrics
        # --------------------------------

        namespace_creation_success_total.labels(
            team=team,
            project=project,
            app=app_name,
            creator=creator,
            approved_by=approved_by
        ).inc()

        # --------------------------------
        # Processing Duration Metric
        # --------------------------------

        request_processing_seconds.labels(
            team=team,
            project=project,
            app=app_name,
            status="success"
        ).observe(
            time.time() - start_time
        )

        # --------------------------------
        # Jira success comment
        # --------------------------------

        try:

            add_comment(
                issue_key,
                (
                    "Namespace created successfully\n\n"
                    f"Namespace: {namespace}\n"
                    f"Client: "
                    f"{KUBECTL_CLIENT_ADDRESS}"
                )
            )

            jira_comments_total.labels(
                team=team,
                project=project,
                app=app_name,
                result="success"
            ).inc()

        except Exception:

            jira_comments_total.labels(
                team=team,
                project=project,
                app=app_name,
                result="failed"
            ).inc()

        # --------------------------------
        # Jira success transition
        # --------------------------------

        try:

            transition_issue(
                issue_key,
                "تایید درخواست"
            )

            jira_transition_total.labels(
                transition_name="approve",
                team=team,
                project=project,
                app=app_name,
                approved_by=approved_by,
                result="success"
            ).inc()

        except Exception:

            jira_transition_total.labels(
                transition_name="approve",
                team=team,
                project=project,
                app=app_name,
                approved_by=approved_by,
                result="failed"
            ).inc()

            raise

        logger.info(
            "Issue transitioned successfully"
        )

        return jsonify({
            "status": "success",
            "namespace": namespace
        }), 200

    except Exception as e:

        logger.exception(e)

        error_message = str(e)

        if isinstance(e, KubernetesError):
            error_type = e.error_type
        elif isinstance(e, ApiException):
            error_type = f"ApiException_{e.status}"
        else:
            error_type = type(e).__name__

        # --------------------------------
        # Failure Metrics
        # --------------------------------

        namespace_creation_failed_total.labels(
            team=team,
            project=project,
            app=app_name,
            creator=creator,
            approved_by=approved_by,
            error_type=error_type
        ).inc()

        # --------------------------------
        # Kubernetes Errors Metrics
        # --------------------------------

        if isinstance(e, ApiException):

            kubernetes_api_errors_total.labels(
                operation="create_namespace",
                error_type=str(e.status),
                team=team,
                project=project,
                app=app_name
            ).inc()

        kubernetes_namespace_operations_total.labels(
            operation="create",
            namespace=namespace,
            team=team,
            project=project,
            app=app_name,
            result="failed"
        ).inc()

        # --------------------------------
        # Processing Duration Metric
        # --------------------------------

        request_processing_seconds.labels(
            team=team,
            project=project,
            app=app_name,
            status="failed"
        ).observe(
            time.time() - start_time
        )

        # --------------------------------
        # Jira failure transition
        # --------------------------------

        try:

            transition_issue(
                issue_key,
                "رد شدن درخواست"
            )

            jira_transition_total.labels(
                transition_name="reject",
                team=team,
                project=project,
                app=app_name,
                approved_by=approved_by,
                result="success"
            ).inc()

        except Exception as jira_error:

            logger.exception(
                jira_error
            )

            jira_transition_total.labels(
                transition_name="reject",
                team=team,
                project=project,
                app=app_name,
                approved_by=approved_by,
                result="failed"
            ).inc()

        return jsonify({
            "status": "error",
            "message": error_message
        }), 500

    finally:

        active_requests.dec()


# -----------------------------------
# Main
# -----------------------------------

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000
    )