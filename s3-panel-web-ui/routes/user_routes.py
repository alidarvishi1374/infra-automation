from flask import Blueprint, render_template, session,jsonify,request, flash, redirect, url_for
from helpers.auth import login_required
from helpers.aws import get_user_type, list_iam_users, create_iam_user, list_access_keys, create_access_key, delete_iam_user
import boto3

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
    # get caller info
    user_info = get_user_type(session["access_key"], session["secret_key"], session["endpoint_url"])

    # list basic IAM users
    iam_users_list = list_iam_users(session["access_key"], session["secret_key"], session["endpoint_url"])

    # enrich each user with count of ACTIVE access keys
    enriched_users = []
    for u in iam_users_list:
        username = u.get("UserName")
        active_count = None
        active_error = None

        try:
            keys_resp = list_access_keys(session["access_key"], session["secret_key"], session["endpoint_url"], username)
            if isinstance(keys_resp, dict) and keys_resp.get("success") is not None:
                # helper returned {"success": True, "keys": [...] } style
                if keys_resp.get("success"):
                    keys = keys_resp.get("keys", [])
                    active_count = sum(1 for k in keys if k.get("Status") == "Active")
                else:
                    # service-level error (e.g. user not found)
                    active_error = keys_resp.get("message") or "Error"
            else:
                # in case your helper returns raw list (backward-compat)
                keys = keys_resp or []
                active_count = sum(1 for k in keys if k.get("Status") == "Active")
        except Exception as e:
            active_error = str(e)

        # copy user dict and attach new fields (so original structure untouched)
        user_copy = u.copy()
        user_copy["ActiveKeysCount"] = active_count
        user_copy["ActiveKeysError"] = active_error
        enriched_users.append(user_copy)

    return render_template("iam_users.html", user_info=user_info, iam_users=enriched_users)


@user_bp.route("/create_user", methods=["POST"])
@login_required
def create_user():
    user_name = request.form.get("username")
    endpoint = session.get("endpoint_url")
    access_key = session.get("access_key")
    secret_key = session.get("secret_key")
    region = "us-east-1"

    result = create_iam_user(endpoint, access_key, secret_key, user_name, region)
    return jsonify(result)

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
        region_name="us-east-1" 
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

    import boto3
    iam = boto3.client(
        "iam",
        aws_access_key_id=session["access_key"],
        aws_secret_access_key=session["secret_key"],
        endpoint_url=session["endpoint_url"],
        region_name="us-east-1" 
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