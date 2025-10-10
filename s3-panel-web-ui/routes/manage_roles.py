# routes/manage_iam_roles.py
from flask import Blueprint, render_template, request, jsonify, session, current_app
from helpers.auth import login_required
import boto3
from botocore.exceptions import ClientError
import json
from helpers.aws import get_user_type


manage_iam_bp = Blueprint("manage_iam", __name__)

# --- Helpers ---
def get_iam_client():
    """Return a boto3 IAM client using credentials from session."""
    access_key = session.get("access_key")
    secret_key = session.get("secret_key")
    endpoint_url = session.get("endpoint_url")
    region_name = session.get("region_name", "us-east-1")

    if not access_key or not secret_key:
        raise ValueError("AWS credentials not found in session")

    return boto3.client(
        "iam",
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        endpoint_url=endpoint_url,
        region_name=region_name
    )

def get_s3_client():
    """Return a boto3 S3 client using credentials from session."""
    access_key = session.get("access_key")
    secret_key = session.get("secret_key")
    endpoint_url = session.get("endpoint_url")
    region_name = session.get("region_name", "default")

    if not access_key or not secret_key:
        raise ValueError("AWS credentials not found in session")

    return boto3.client(
        "s3",
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        endpoint_url=endpoint_url,
        region_name=region_name
    )

# --- Routes ---
@manage_iam_bp.route("/manage_roles")
@login_required
def manage_roles_page():
    user_info = get_user_type(
        session.get("access_key"),
        session.get("secret_key"),
        session.get("endpoint_url")
    )
    return render_template("role_management.html", user_info=user_info)


@manage_iam_bp.route("/api/roles", methods=["GET"])
@login_required
def list_roles():
    try:
        client = get_iam_client()
        roles = []
        paginator = client.get_paginator("list_roles")
        for page in paginator.paginate():
            for r in page.get("Roles", []):
                roles.append({
                    "RoleName": r.get("RoleName"),
                    "Arn": r.get("Arn"),
                    "CreateDate": r.get("CreateDate").isoformat() if r.get("CreateDate") else None
                })
        return jsonify({"roles": roles})
    except (ClientError, ValueError) as e:
        return jsonify({"error": str(e)}), 500


@manage_iam_bp.route("/api/role/<role_name>", methods=["GET"])
@login_required
def get_role(role_name):
    try:
        client = get_iam_client()
        resp = client.get_role(RoleName=role_name)
        role = resp.get("Role")
        return jsonify({"role": role, "assumeRolePolicy": role.get("AssumeRolePolicyDocument")})
    except (ClientError, ValueError) as e:
        return jsonify({"error": str(e)}), 400


@manage_iam_bp.route("/api/role/create", methods=["POST"])
@login_required
def create_role():
    data = request.json
    name = data.get("roleName")
    trust = data.get("trustJson")
    if not name or not trust:
        return jsonify({"error": "roleName and trustJson required"}), 400
    try:
        client = get_iam_client()
        trust_doc = trust if isinstance(trust, str) else json.dumps(trust)
        resp = client.create_role(
            RoleName=name,
            AssumeRolePolicyDocument=trust_doc,
            Description=data.get("description", "Created via web UI")
        )
        return jsonify({"created": resp.get("Role")}), 201
    except (ClientError, ValueError) as e:
        return jsonify({"error": str(e)}), 400


@manage_iam_bp.route("/api/role/update_assume", methods=["POST"])
@login_required
def update_assume():
    data = request.json
    name = data.get("roleName")
    trust = data.get("trustJson")
    if not name or not trust:
        return jsonify({"error": "roleName and trustJson required"}), 400
    try:
        client = get_iam_client()
        trust_doc = trust if isinstance(trust, str) else json.dumps(trust)
        client.update_assume_role_policy(RoleName=name, PolicyDocument=trust_doc)
        return jsonify({"ok": True})
    except (ClientError, ValueError) as e:
        return jsonify({"error": str(e)}), 400


@manage_iam_bp.route("/api/role/delete/<role_name>", methods=["DELETE"])
@login_required
def delete_role(role_name):
    try:
        client = get_iam_client()
        client.delete_role(RoleName=role_name)
        return jsonify({"ok": True})
    except (ClientError, ValueError) as e:
        return jsonify({"error": str(e)}), 400


@manage_iam_bp.route("/api/role/<role_name>/policies", methods=["GET"])
@login_required
def list_role_policies(role_name):
    try:
        client = get_iam_client()
        resp = client.list_role_policies(RoleName=role_name)
        return jsonify({"policies": resp.get("PolicyNames", [])})
    except (ClientError, ValueError) as e:
        return jsonify({"error": str(e)}), 400


@manage_iam_bp.route("/api/role/<role_name>/policy/<policy_name>", methods=["GET"])
@login_required
def get_role_policy(role_name, policy_name):
    try:
        client = get_iam_client()
        resp = client.get_role_policy(RoleName=role_name, PolicyName=policy_name)
        return jsonify({"policy": resp})
    except (ClientError, ValueError) as e:
        return jsonify({"error": str(e)}), 400


@manage_iam_bp.route("/api/role/<role_name>/policy/<policy_name>", methods=["POST"])
@login_required
def put_role_policy(role_name, policy_name):
    data = request.json
    doc = data.get("policyDocument")
    if not doc:
        return jsonify({"error": "policyDocument required"}), 400
    try:
        client = get_iam_client()
        client.put_role_policy(RoleName=role_name, PolicyName=policy_name, PolicyDocument=json.dumps(doc))
        return jsonify({"ok": True})
    except (ClientError, ValueError) as e:
        return jsonify({"error": str(e)}), 400


@manage_iam_bp.route("/api/role/<role_name>/policy/<policy_name>", methods=["DELETE"])
@login_required
def delete_role_policy(role_name, policy_name):
    try:
        client = get_iam_client()
        client.delete_role_policy(RoleName=role_name, PolicyName=policy_name)
        return jsonify({"ok": True})
    except (ClientError, ValueError) as e:
        return jsonify({"error": str(e)}), 400


@manage_iam_bp.route("/api/s3/put", methods=["POST"])
@login_required
def s3_put_object():
    data = request.json
    bucket = data.get("bucket")
    key = data.get("key")
    content = data.get("content", "hello")
    if not bucket or not key:
        return jsonify({"error": "bucket and key required"}), 400
    try:
        client = get_s3_client()
        client.put_object(Bucket=bucket, Key=key, Body=content.encode("utf-8"))
        return jsonify({"ok": True})
    except (ClientError, ValueError) as e:
        return jsonify({"error": str(e)}), 400
