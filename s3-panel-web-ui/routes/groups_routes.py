# iam_groups.py
from flask import Blueprint, render_template, session, jsonify, request, json
from helpers.auth import login_required
from helpers.aws import get_iam_client, get_user_type

iam_groups_bp = Blueprint("iam_groups", __name__)

@iam_groups_bp.route("/iam_groups")
@login_required
def iam_groups():
    user_info = get_user_type(session["access_key"], session["secret_key"], session["endpoint_url"])

    iam_client = get_iam_client(
        session["access_key"],
        session["secret_key"],
        session["endpoint_url"]
    )

    try:
        groups_resp = iam_client.list_groups()
        groups_list = groups_resp.get("Groups", [])
    except Exception as e:
        return render_template("iam_groups.html", user_info=user_info, iam_groups=[], error=str(e))

    try:
        users_resp = iam_client.list_users()
        all_users = users_resp.get("Users", [])
    except Exception as e:
        all_users = []
        print(f"Failed to list users: {e}")

    enriched_groups = []
    for g in groups_list:
        group_name = g.get("GroupName")
        members = []
        error = None

        for user in all_users:
            username = user["UserName"]
            try:
                user_groups = iam_client.list_groups_for_user(UserName=username).get("Groups", [])
                group_names = [grp["GroupName"] for grp in user_groups]
                if group_name in group_names:
                    members.append(username)
            except Exception as e:
                error = str(e)

        group_copy = g.copy()
        group_copy["Members"] = members
        group_copy["UserCount"] = len(members)
        group_copy["Error"] = error
        enriched_groups.append(group_copy)

    return render_template("iam_groups.html", user_info=user_info, iam_groups=enriched_groups, all_users=all_users)


@iam_groups_bp.route("/create_group", methods=["POST"])
@login_required
def create_group():
    data = request.get_json()
    group_name = data.get("group_name")

    iam_client = get_iam_client(
        access_key=session["access_key"],
        secret_key=session["secret_key"],
        endpoint_url=session["endpoint_url"]
    )

    try:
        resp = iam_client.create_group(GroupName=group_name)
        return jsonify(success=True, group=resp.get("Group"))
    except Exception as e:
        return jsonify(success=False, message=str(e))



@iam_groups_bp.route("/delete_group", methods=["POST"])
@login_required
def delete_group():
    group_name = request.json.get("group_name")
    iam_client = get_iam_client(
        access_key=session["access_key"],
        secret_key=session["secret_key"],
        endpoint_url=session["endpoint_url"]
    )

    try:
        iam_client.delete_group(GroupName=group_name)
        return jsonify(success=True)
    except Exception as e:
        return jsonify(success=False, message=str(e))


@iam_groups_bp.route("/add_user_to_group", methods=["POST"])
@login_required
def add_user_to_group():
    group_name = request.json.get("group_name")
    username = request.json.get("username")

    iam_client = get_iam_client(
        access_key=session["access_key"],
        secret_key=session["secret_key"],
        endpoint_url=session["endpoint_url"]
    )

    try:
        iam_client.add_user_to_group(GroupName=group_name, UserName=username)
        return jsonify(success=True)
    except Exception as e:
        return jsonify(success=False, message=str(e))


@iam_groups_bp.route("/remove_user_from_group", methods=["POST"])
@login_required
def remove_user_from_group():
    group_name = request.json.get("group_name")
    username = request.json.get("username")

    iam_client = get_iam_client(
        access_key=session["access_key"],
        secret_key=session["secret_key"],
        endpoint_url=session["endpoint_url"]
    )

    try:
        iam_client.remove_user_from_group(GroupName=group_name, UserName=username)
        return jsonify(success=True)
    except Exception as e:
        return jsonify(success=False, message=str(e))
    
@iam_groups_bp.route("/get_inline_policies", methods=["GET"])
@login_required
def get_inline_policies():
    group_name = request.args.get("group_name")
    iam_client = get_iam_client(
        access_key=session["access_key"],
        secret_key=session["secret_key"],
        endpoint_url=session["endpoint_url"]
    )
    try:
        resp = iam_client.list_group_policies(GroupName=group_name)
        policies = []
        for pname in resp.get("PolicyNames", []):
            p = iam_client.get_group_policy(GroupName=group_name, PolicyName=pname)
            policies.append({
                "PolicyName": pname,
                "PolicyDocument": p["PolicyDocument"]
            })
        return jsonify(success=True, policies=policies)
    except Exception as e:
        return jsonify(success=False, message=str(e))

@iam_groups_bp.route("/delete_inline_policy", methods=["POST"])
@login_required
def delete_inline_policy():
    data = request.get_json()
    group_name = data.get("group_name")
    policy_name = data.get("policy_name")
    iam_client = get_iam_client(
        access_key=session["access_key"],
        secret_key=session["secret_key"],
        endpoint_url=session["endpoint_url"]
    )
    try:
        iam_client.delete_group_policy(GroupName=group_name, PolicyName=policy_name)
        return jsonify(success=True)
    except Exception as e:
        return jsonify(success=False, message=str(e))

@iam_groups_bp.route("/add_inline_policy", methods=["POST"])
@login_required
def add_inline_policy():
    data = request.get_json()
    group_name = data.get("group_name")
    policy_name = data.get("policy_name")
    policy_document = data.get("policy_document")

    iam_client = get_iam_client(
        access_key=session["access_key"],
        secret_key=session["secret_key"],
        endpoint_url=session["endpoint_url"]
    )

    try:
        iam_client.put_group_policy(
            GroupName=group_name,
            PolicyName=policy_name,
            PolicyDocument=json.dumps(policy_document)
        )
        return jsonify(success=True)
    except Exception as e:
        return jsonify(success=False, message=str(e))


@iam_groups_bp.route("/update_inline_policy", methods=["POST"])
@login_required
def update_inline_policy():
    data = request.get_json()
    group_name = data.get("group_name")
    policy_name = data.get("policy_name")
    policy_document = data.get("policy_document")
    iam_client = get_iam_client(
        access_key=session["access_key"],
        secret_key=session["secret_key"],
        endpoint_url=session["endpoint_url"]
    )
    try:
        iam_client.put_group_policy(
            GroupName=group_name,
            PolicyName=policy_name,
            PolicyDocument=json.dumps(policy_document)
        )
        return jsonify(success=True)
    except Exception as e:
        return jsonify(success=False, message=str(e))



@iam_groups_bp.route("/get_attached_group_policies", methods=["GET"])
@login_required
def get_attached_group_policies():
    group_name = request.args.get("group_name")
    iam_client = get_iam_client(
        access_key=session["access_key"],
        secret_key=session["secret_key"],
        endpoint_url=session["endpoint_url"]
    )
    try:
        attached_policies = iam_client.list_attached_group_policies(GroupName=group_name).get("AttachedPolicies", [])
        return jsonify(success=True, policies=attached_policies)
    except Exception as e:
        return jsonify(success=False, message=str(e))

# attach policy
@iam_groups_bp.route("/attach_group_policy", methods=["POST"])
@login_required
def attach_group_policy():
    data = request.get_json()
    group_name = data.get("group_name")
    policy_arn = data.get("policy_arn")

    iam_client = get_iam_client(
        access_key=session["access_key"],
        secret_key=session["secret_key"],
        endpoint_url=session["endpoint_url"]
    )
    try:
        iam_client.attach_group_policy(GroupName=group_name, PolicyArn=policy_arn)
        return jsonify(success=True)
    except Exception as e:
        return jsonify(success=False, message=str(e))


# detach policy
@iam_groups_bp.route("/detach_group_policy", methods=["POST"])
@login_required
def detach_group_policy():
    data = request.get_json()
    group_name = data.get("group_name")
    policy_arn = data.get("policy_arn")

    iam_client = get_iam_client(
        access_key=session["access_key"],
        secret_key=session["secret_key"],
        endpoint_url=session["endpoint_url"]
    )
    try:
        iam_client.detach_group_policy(GroupName=group_name, PolicyArn=policy_arn)
        return jsonify(success=True)
    except Exception as e:
        return jsonify(success=False, message=str(e))

