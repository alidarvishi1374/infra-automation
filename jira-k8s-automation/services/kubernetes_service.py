import yaml
import logging

from kubernetes import client, config

from kubernetes.client.rest import ApiException
from services.exceptions import KubernetesError

from config import KUBECONFIG_PATH


logger = logging.getLogger(__name__)


# -----------------------------------
# Kubernetes Authentication
# -----------------------------------

def load_kubernetes_config():

    try:

        config.load_incluster_config()

        logger.info(
            "Using in-cluster Kubernetes config"
        )

    except Exception:

        logger.info(
            "In-cluster config not found"
        )

        try:

            config.load_kube_config(
                config_file=KUBECONFIG_PATH
            )

            logger.info(
                "Using kubeconfig file"
            )

        except Exception as e:

            logger.exception(e)

            raise Exception(
                "Failed to load Kubernetes config"
            )


load_kubernetes_config()

core_api = client.CoreV1Api()


# -----------------------------------
# Apply Namespace Manifest
# -----------------------------------

def apply_namespace_manifest(
    manifest: str
):

    docs = list(
        yaml.safe_load_all(manifest)
    )

    for doc in docs:

        if not doc:
            continue

        kind = doc.get("kind")

        logger.info(
            f"Processing resource kind={kind}"
        )

        if kind == "Namespace":

            create_namespace(doc)

        else:

            logger.warning(
                f"Unsupported kind: {kind}"
            )


# -----------------------------------
# Namespace
# -----------------------------------

def create_namespace(body: dict):

    metadata = body.get("metadata", {})
    name = metadata.get("name")

    try:
        core_api.read_namespace(name)

        raise KubernetesError(
            message=f"Namespace '{namespace}' already exists",
            error_type="AlreadyExists"
        )

    except ApiException as e:

        if e.status == 404:
            pass
        else:
            raise KubernetesError(
                f"Kubernetes API error: {str(e)}",
                error_type=f"ApiException_{e.status}"
            )

    except Exception as e:
        raise KubernetesError(
            str(e),
            error_type=type(e).__name__
        )

    try:
        core_api.create_namespace(body=body)

    except ApiException as e:
        raise KubernetesError(
            str(e),
            error_type=f"CreateFailed_{e.status}"
        )