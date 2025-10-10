from flask import Blueprint, render_template, request, session
from helpers.auth import login_required
import sqlite3
import boto3
from botocore.exceptions import ClientError
import json
import datetime
from zoneinfo import ZoneInfo
from helpers.aws import get_user_type


assume_bp = Blueprint("assume_roles", __name__)
DB_FILE = "database/roles.db"
TEHRAN_TZ = ZoneInfo("Asia/Tehran")


def get_user_arn_from_session():
    access_key = session.get("access_key")
    secret_key = session.get("secret_key")
    endpoint = session.get("endpoint_url")
    if not access_key or not secret_key or not endpoint:
        return None

    iam_client = boto3.client(
        "iam",
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        endpoint_url=endpoint,
        region_name="default"
    )
    try:
        response = iam_client.get_user()
        user = response['User']
        return user.get('Arn', '')
    except ClientError:
        return None


def user_in_principal(user_arn, principal_json):
    try:
        statements = json.loads(principal_json)
        for stmt in statements:
            aws_principal = stmt.get("Principal", {}).get("AWS")
            if isinstance(aws_principal, list):
                if any(user_arn in arn for arn in aws_principal):
                    return True
            elif isinstance(aws_principal, str):
                if user_arn in aws_principal:
                    return True
        return False
    except json.JSONDecodeError:
        return False


def get_roles_for_user(user_arn):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT role_name, role_arn, create_date, max_session_duration, principal, assumed_users, assume_history, assume_permission FROM roles")
    roles = []
    for row in cur.fetchall():
        role_name, role_arn, create_date, max_duration, principal_json, assumed_users_json, assume_history_json, assume_perm_json = row
        if user_in_principal(user_arn, principal_json):
            roles.append({
                "role_name": role_name,
                "role_arn": role_arn,
                "create_date": create_date,
                "max_session_duration": max_duration,
                "assumed_users": json.loads(assumed_users_json) if assumed_users_json else [],
                "assume_history": json.loads(assume_history_json) if assume_history_json else [],
                "assume_permission": json.loads(assume_perm_json) if assume_perm_json else {}
            })
    conn.close()
    return roles


def check_expiration_before_assume(role_arn, user_arn):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT assume_history, assume_permission FROM roles WHERE role_arn = ?", (role_arn,))
    row = cur.fetchone()
    conn.close()

    if not row:
        return "not_exists", False

    assume_history_json, assume_perm_json = row
    assume_history_list = json.loads(assume_history_json) if assume_history_json else []
    assume_perm = json.loads(assume_perm_json) if assume_perm_json else {}

    user_history = [h for h in assume_history_list if h.get("user") == user_arn]
    now = datetime.datetime.now(TEHRAN_TZ)

    if user_history:
        latest = user_history[-1]
        expiration = datetime.datetime.fromisoformat(latest["expiration"])
        if now < expiration:
            return "active", False
        else:
            expired = True
    else:
        expired = True

    perm = assume_perm.get(user_arn, "no")
    return ("not_exists" if not user_history else "expired"), (perm == "yes")



def assume_role(role_arn, session_name, duration_seconds):
    access_key = session.get("access_key")
    secret_key = session.get("secret_key")
    endpoint = session.get("endpoint_url")
    client = boto3.client(
        'sts',
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        endpoint_url=endpoint,
        region_name='default'
    )
    response = client.assume_role(
        RoleArn=role_arn,
        RoleSessionName=session_name,
        DurationSeconds=duration_seconds
    )
    credentials = response['Credentials']
    return {
        'AccessKeyId': credentials['AccessKeyId'],
        'SecretAccessKey': credentials['SecretAccessKey'],
        'SessionToken': credentials['SessionToken'],
        'Expiration': str(credentials['Expiration'])
    }


def register_assume(role_arn, user_arn, duration_seconds):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT assumed_users, assume_history, assume_permission FROM roles WHERE role_arn = ?", (role_arn,))
    row = cur.fetchone()
    if row:
        assumed_users_json, assume_history_json, assume_perm_json = row
        assumed_users_list = json.loads(assumed_users_json) if assumed_users_json else []
        assume_history_list = json.loads(assume_history_json) if assume_history_json else []
        assume_perm = json.loads(assume_perm_json) if assume_perm_json else {}

        if user_arn not in assumed_users_list:
            assumed_users_list.append(user_arn)

        now = datetime.datetime.now(TEHRAN_TZ)
        expiration_time = now + datetime.timedelta(seconds=duration_seconds)

        assume_history_list.append({
            "user": user_arn,
            "timestamp": now.isoformat(),
            "expiration": expiration_time.isoformat()
        })

        assume_perm[user_arn] = "no"

        cur.execute("""
            UPDATE roles 
            SET assumed_users = ?, assume_history = ?, assume_permission = ?
            WHERE role_arn = ?
        """, (json.dumps(assumed_users_list), json.dumps(assume_history_list), json.dumps(assume_perm), role_arn))
        conn.commit()
    conn.close()


@assume_bp.route("/assume_roles", methods=["GET", "POST"])
@login_required
def assume_roles_page():
    assumed_creds = None
    error = None

    user_info = get_user_type(
        session.get("access_key"),
        session.get("secret_key"),
        session.get("endpoint_url")
    )

    user_arn = get_user_arn_from_session()
    if not user_arn:
        error = "User information not found in session."
        roles = []
    else:
        roles = get_roles_for_user(user_arn)

    if request.method == "POST":
        role_arn = request.form.get("role_arn")
        duration_seconds = request.form.get("duration_seconds")
        try:
            duration_seconds = int(duration_seconds) if duration_seconds else None
        except ValueError:
            duration_seconds = None

        max_duration = next((r['max_session_duration'] for r in roles if r['role_arn'] == role_arn), 3600)
        duration = duration_seconds if duration_seconds else max_duration

        status, has_permission = check_expiration_before_assume(role_arn, user_arn)

        if status == "active":
            error = "Your token is still active and cannot be requested again."
        elif not has_permission:
            error = "You do not have permission to create a token. Please contact an admin."
        else:
            assumed_creds = assume_role(role_arn, "temp-session", duration)
            register_assume(role_arn, user_arn, duration)

    return render_template("assume_roles.html", roles=roles, error=error, assumed_creds=assumed_creds, user_info=user_info)
