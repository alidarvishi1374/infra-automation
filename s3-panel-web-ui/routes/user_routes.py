from flask import Blueprint, render_template, session, jsonify, request, flash, redirect, url_for
from helpers.auth import login_required
from helpers.aws import get_user_type, list_iam_users, create_iam_user, list_access_keys, create_access_key, delete_iam_user, disable_access_key, delete_access_key
import boto3, json
from botocore.exceptions import ClientError


user_bp = Blueprint("user", __name__)

@user_bp.route("/profile")
@login_required
def profile():
    user_info = get_user_type(session["access_key"], session["secret_key"], session["endpoint_url"])
    show_alert = not any(user_info.get(k) for k in user_info if k != "type")
    return render_template("profile.html", user_info=user_info, show_alert=show_alert)


@user_bp.route("/iam_users")
@login_required
def iam_users():
    user_info = get_user_type(session["access_key"], session["secret_key"], session["endpoint_url"])
    iam_users_list = list_iam_users(session["access_key"], session["secret_key"], session["endpoint_url"])

    enriched_users = []
    for u in iam_users_list:
        username = u.get("UserName")
        active_count = None
        active_error = None

        try:
            keys_resp = list_access_keys(session["access_key"], session["secret_key"], session["endpoint_url"], username)
            if isinstance(keys_resp, dict) and keys_resp.get("success") is not None:
                if keys_resp.get("success"):
                    keys = keys_resp.get("keys", [])
                    active_count = sum(1 for k in keys if k.get("Status") == "Active")
                else:
                    active_error = keys_resp.get("message") or "Error"
            else:
                keys = keys_resp or []
                active_count = sum(1 for k in keys if k.get("Status") == "Active")
        except Exception as e:
            active_error = str(e)

        user_copy = u.copy()
        user_copy["ActiveKeysCount"] = active_count
        user_copy["ActiveKeysError"] = active_error
        
        try:
            iam = boto3.client(
                "iam",
                aws_access_key_id=session["access_key"],
                aws_secret_access_key=session["secret_key"],
                endpoint_url=session["endpoint_url"],
                region_name="default"
            )
            groups_response = iam.list_groups_for_user(UserName=username)
            user_copy["Groups"] = [g['GroupName'] for g in groups_response['Groups']]
        except Exception as e:
            user_copy["Groups"] = []
        
        enriched_users.append(user_copy)

    return render_template("iam_users.html", user_info=user_info, iam_users=enriched_users)

@user_bp.route("/create_user", methods=["POST"])
@login_required
def create_user():
    user_name = request.form.get("username")
    enable_panel_access = request.form.get("enable_panel_access") == 'true'
    endpoint = session.get("endpoint_url")
    access_key = session.get("access_key")
    secret_key = session.get("secret_key")
    region = "default"

    result = create_iam_user(endpoint, access_key, secret_key, user_name, region)
    
    if result.get("success") and enable_panel_access:
        try:
            policy_result = attach_getuser_policy(access_key, secret_key, endpoint, user_name, region)
            if not policy_result.get("ok"):
                result["message"] += f" But failed to attach panel access policy: {policy_result.get('error', 'Unknown error')}"
            else:
                result["message"] += " with panel access enabled"
        except Exception as e:
            result["message"] += f" But failed to attach panel access policy: {str(e)}"
    
    return jsonify(result)


def attach_getuser_policy(root_access_key, root_secret_key, endpoint_url, target_username, region_name=""):
    try:
        iam = boto3.client(
            "iam",
            aws_access_key_id=root_access_key,
            aws_secret_access_key=root_secret_key,
            endpoint_url=endpoint_url,
            region_name=region_name
        )

        policy_document = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": "iam:GetUser",
                    "Resource": f"arn:aws:iam::*:user/{target_username}"
                }
            ]
        }

        policy_name = f"AllowGetUserOnly-{target_username}"

        iam.put_user_policy(
            UserName=target_username,
            PolicyName=policy_name,
            PolicyDocument=json.dumps(policy_document)
        )
        return {
            "ok": True,
            "message": f"Inline policy '{policy_name}' attached to user '{target_username}'."
        }
    except ClientError as e:
        return {"ok": False, "error": e.response['Error']['Message']}
    except Exception as e:
        return {"ok": False, "error": str(e)}
    
@user_bp.route("/user_keys/<username>", methods=["GET"])
@login_required
def user_keys(username):
    from helpers.aws import list_access_keys
    keys = list_access_keys(session["access_key"], session["secret_key"], session["endpoint_url"], username)
    return jsonify(keys)


@user_bp.route("/user_keys/<username>/create", methods=["POST"])
@login_required
def create_key(username):
    from helpers.aws import create_access_key
    result = create_access_key(session["access_key"], session["secret_key"], session["endpoint_url"], username)
    return jsonify(result)


@user_bp.route("/user_keys/<username>/disable", methods=["POST"])
@login_required
def disable_key(username):
    key_id = request.json.get("AccessKeyId")
    from helpers.aws import disable_access_key
    result = disable_access_key(session["access_key"], session["secret_key"], session["endpoint_url"], username, key_id)
    return jsonify(result)


@user_bp.route("/user_keys/<username>/delete", methods=["POST"])
@login_required
def delete_key(username):
    key_id = request.json.get("AccessKeyId")
    from helpers.aws import delete_access_key
    result = delete_access_key(session["access_key"], session["secret_key"], session["endpoint_url"], username, key_id)
    return jsonify(result)


@user_bp.route("/get_keys", methods=["POST"])
@login_required
def get_keys():
    username = request.form.get("username")
    import boto3

    iam = boto3.client(
        "iam",
        aws_access_key_id=session["access_key"],
        aws_secret_access_key=session["secret_key"],
        endpoint_url=session["endpoint_url"],
        region_name="default" 
    )

    keys = iam.list_access_keys(UserName=username).get("AccessKeyMetadata", [])
    formatted_keys = [{
        "AccessKeyId": k["AccessKeyId"],
        "Status": k["Status"],
        "CreateDate": k["CreateDate"].strftime("%Y-%m-%d %H:%M:%S")
    } for k in keys]
    return jsonify(keys=formatted_keys)


@user_bp.route("/modify_key", methods=["POST"])
@login_required
def modify_key():
    username = request.form.get("username")
    key_id = request.form.get("key_id")
    action = request.form.get("action")

    iam = boto3.client(
        "iam",
        aws_access_key_id=session["access_key"],
        aws_secret_access_key=session["secret_key"],
        endpoint_url=session["endpoint_url"],
        region_name="default" 
    )

    try:
        if action == "disable":
            iam.update_access_key(UserName=username, AccessKeyId=key_id, Status="Inactive")

        elif action == "enable":
            keys = iam.list_access_keys(UserName=username).get("AccessKeyMetadata", [])
            active_keys = [k for k in keys if k["Status"] == "Active"]

            if len(active_keys) >= 2:
                return jsonify(success=False, message=f"Cannot enable key: user '{username}' already has 2 active keys.")

            iam.update_access_key(UserName=username, AccessKeyId=key_id, Status="Active")

        elif action == "delete":
            iam.delete_access_key(UserName=username, AccessKeyId=key_id)

        else:
            return jsonify(success=False, message="Invalid action")

        return jsonify(success=True)

    except Exception as e:
        return jsonify(success=False, message=str(e))
   

@user_bp.route("/create-access-key", methods=["POST"])
@login_required
def create_access_key_route():
    username = request.json.get("username")
    access_key = session.get("access_key")
    secret_key = session.get("secret_key")
    endpoint_url = session.get("endpoint_url")

    result = create_access_key(access_key, secret_key, endpoint_url, username)
    return jsonify(result)

@user_bp.route("/delete_user", methods=["POST"])
@login_required
def delete_user():
    user_name = request.json.get("username")
    endpoint = session.get("endpoint_url")
    access_key = session.get("access_key")
    secret_key = session.get("secret_key")

    result = delete_iam_user(endpoint, access_key, secret_key, user_name)
    return jsonify(result)

# ========== USER POLICY MANAGEMENT ==========

@user_bp.route("/get_user_inline_policies", methods=["GET"])
@login_required
def get_user_inline_policies():
    username = request.args.get("username")
    iam_client = boto3.client(
        "iam",
        aws_access_key_id=session["access_key"],
        aws_secret_access_key=session["secret_key"],
        endpoint_url=session["endpoint_url"],
        region_name="default"
    )
    try:
        resp = iam_client.list_user_policies(UserName=username)
        policies = []
        for pname in resp.get("PolicyNames", []):
            p = iam_client.get_user_policy(UserName=username, PolicyName=pname)
            policies.append({
                "PolicyName": pname,
                "PolicyDocument": p["PolicyDocument"]
            })
        return jsonify(success=True, policies=policies)
    except Exception as e:
        return jsonify(success=False, message=str(e))

@user_bp.route("/delete_user_inline_policy", methods=["POST"])
@login_required
def delete_user_inline_policy():
    data = request.get_json()
    username = data.get("username")
    policy_name = data.get("policy_name")
    iam_client = boto3.client(
        "iam",
        aws_access_key_id=session["access_key"],
        aws_secret_access_key=session["secret_key"],
        endpoint_url=session["endpoint_url"],
        region_name="default"
    )
    try:
        iam_client.delete_user_policy(UserName=username, PolicyName=policy_name)
        return jsonify(success=True)
    except Exception as e:
        return jsonify(success=False, message=str(e))

@user_bp.route("/add_user_inline_policy", methods=["POST"])
@login_required
def add_user_inline_policy():
    data = request.get_json()
    username = data.get("username")
    policy_name = data.get("policy_name")
    policy_document = data.get("policy_document")

    iam_client = boto3.client(
        "iam",
        aws_access_key_id=session["access_key"],
        aws_secret_access_key=session["secret_key"],
        endpoint_url=session["endpoint_url"],
        region_name="default"
    )

    try:
        iam_client.put_user_policy(
            UserName=username,
            PolicyName=policy_name,
            PolicyDocument=json.dumps(policy_document)
        )
        return jsonify(success=True)
    except Exception as e:
        return jsonify(success=False, message=str(e))

@user_bp.route("/update_user_inline_policy", methods=["POST"])
@login_required
def update_user_inline_policy():
    data = request.get_json()
    username = data.get("username")
    policy_name = data.get("policy_name")
    policy_document = data.get("policy_document")
    iam_client = boto3.client(
        "iam",
        aws_access_key_id=session["access_key"],
        aws_secret_access_key=session["secret_key"],
        endpoint_url=session["endpoint_url"],
        region_name="default"
    )
    try:
        iam_client.put_user_policy(
            UserName=username,
            PolicyName=policy_name,
            PolicyDocument=json.dumps(policy_document)
        )
        return jsonify(success=True)
    except Exception as e:
        return jsonify(success=False, message=str(e))

@user_bp.route("/get_attached_user_policies", methods=["GET"])
@login_required
def get_attached_user_policies():
    username = request.args.get("username")
    iam_client = boto3.client(
        "iam",
        aws_access_key_id=session["access_key"],
        aws_secret_access_key=session["secret_key"],
        endpoint_url=session["endpoint_url"],
        region_name="default"
    )
    try:
        attached_policies = iam_client.list_attached_user_policies(UserName=username).get("AttachedPolicies", [])
        return jsonify(success=True, policies=attached_policies)
    except Exception as e:
        return jsonify(success=False, message=str(e))

@user_bp.route("/attach_user_policy", methods=["POST"])
@login_required
def attach_user_policy():
    data = request.get_json()
    username = data.get("username")
    policy_arn = data.get("policy_arn")

    iam_client = boto3.client(
        "iam",
        aws_access_key_id=session["access_key"],
        aws_secret_access_key=session["secret_key"],
        endpoint_url=session["endpoint_url"],
        region_name="default"
    )
    try:
        iam_client.attach_user_policy(UserName=username, PolicyArn=policy_arn)
        return jsonify(success=True)
    except Exception as e:
        return jsonify(success=False, message=str(e))

@user_bp.route("/detach_user_policy", methods=["POST"])
@login_required
def detach_user_policy():
    data = request.get_json()
    username = data.get("username")
    policy_arn = data.get("policy_arn")

    iam_client = boto3.client(
        "iam",
        aws_access_key_id=session["access_key"],
        aws_secret_access_key=session["secret_key"],
        endpoint_url=session["endpoint_url"],
        region_name="default"
    )
    try:
        iam_client.detach_user_policy(UserName=username, PolicyArn=policy_arn)
        return jsonify(success=True)
    except Exception as e:
        return jsonify(success=False, message=str(e))