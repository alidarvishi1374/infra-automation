import re

from jinja2 import (
    Environment,
    FileSystemLoader
)

from config import TEAM_PREFIXES


env = Environment(
    loader=FileSystemLoader("templates"),
    trim_blocks=True,
    lstrip_blocks=True
)


def sanitize_name(value: str):

    if not value:
        return ""

    value = value.lower()

    value = value.replace(" ", "-")

    value = re.sub(
        r"[^a-z0-9-]",
        "-",
        value
    )

    value = re.sub(
        r"-+",
        "-",
        value
    )

    value = value.strip("-")

    return value


def generate_namespace_name(
    team: str,
    project: str,
    app: str
):

    prefix = TEAM_PREFIXES.get(team)

    if not prefix:

        raise Exception(
            f"Invalid team: {team}"
        )

    namespace = f"{prefix}-{project}-{app}"

    if len(namespace) > 63:

        raise Exception(
            "Namespace exceeds 63 chars"
        )

    return namespace


def render_namespace_manifest(
    namespace: str,
    team: str,
    project: str,
    app: str,
    site: str,
    request_number: str
):

    template = env.get_template(
        "namespace.yaml.j2"
    )

    rendered = template.render(
        namespace=namespace,
        team=team,
        project=project,
        app=app,
        site=site,
        request_number=request_number
    )

    return rendered