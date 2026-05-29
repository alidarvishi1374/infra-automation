import yaml
import logging

from kubernetes import client, config

from kubernetes.client.rest import ApiException

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

    metadata = body.get(
        "metadata",
        {}
    )

    name = metadata.get("name")

    try:

        core_api.read_namespace(name)

        raise Exception(
            f"Namespace '{name}' already exists"
        )

    except ApiException as e:

        if e.status != 404:
            raise

    core_api.create_namespace(
        body=body
    )

    logger.info(
        f"Namespace created: {name}"
    )