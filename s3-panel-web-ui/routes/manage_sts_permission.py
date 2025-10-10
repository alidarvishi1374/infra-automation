# routes /manage_sts_permissions.py
from flask import Blueprint, render_template, request, jsonify, session, current_app
from helpers.auth import login_required
import sqlite3
import json
import boto3
from helpers.aws import get_user_type


manage_bp = Blueprint("manage", __name__)
DB_FILE = "database/roles.db"

# --- Database init ---
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS roles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role_name TEXT,
            role_arn TEXT UNIQUE,
            create_date TEXT,
            max_session_duration INTEGER,
            principal TEXT,
            assume_permission TEXT,
            assumed_users TEXT,
            assume_history TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_name TEXT,
            user_arn TEXT UNIQUE
        )
    """)
    conn.commit()
    conn.close()


# --- Helper to get boto3 client using session ---
def get_iam_client():
    return boto3.client(
        "iam",
        aws_access_key_id=session.get("access_key"),
        aws_secret_access_key=session.get("secret_key"),
        endpoint_url=session.get("endpoint_url"),
        region_name="us-east-1"
    )


# --- Sync roles & users from AWS ---
def list_roles_and_users():
    client = get_iam_client()

    # --- Users ---
    users = []
    paginator = client.get_paginator('list_users')
    for page in paginator.paginate():
        users.extend(page.get("Users", []))

    valid_users = {}
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    for u in users:
        cur.execute("""
            INSERT OR REPLACE INTO users (user_name, user_arn)
            VALUES (?, ?)
        """, (u["UserName"], u["Arn"]))
        valid_users[u["Arn"]] = u["UserName"]
    conn.commit()

    # --- Roles ---
    roles = []
    paginator = client.get_paginator('list_roles')
    for page in paginator.paginate():
        roles.extend(page.get("Roles", []))

    db_roles = {r[0] for r in cur.execute("SELECT role_arn FROM roles").fetchall()}
    fetched_roles = set()

    for role in roles:
        role_name = role["RoleName"]
        role_arn = role["Arn"]
        create_date = role["CreateDate"]
        max_duration = role.get("MaxSessionDuration", 3600)
        statements = role.get("AssumeRolePolicyDocument", {}).get("Statement", [])
        principal_json = json.dumps(statements)

        # extract user ARNs
        user_list = []
        for stmt in statements:
            aws_principal = stmt.get("Principal", {}).get("AWS")
            if isinstance(aws_principal, list):
                user_list.extend(aws_principal)
            elif isinstance(aws_principal, str):
                user_list.append(aws_principal)

        user_list = [u for u in user_list if not u.lower().endswith(":root")]

        if not user_list:
            continue

        # previous permissions
        cur.execute("SELECT assume_permission, assumed_users, assume_history FROM roles WHERE role_arn = ?", (role_arn,))
        row = cur.fetchone()
        if row:
            prev_perm_json, prev_assumed_json, prev_history_json = row
            prev_perm = json.loads(prev_perm_json) if prev_perm_json else {}
            prev_assumed = json.loads(prev_assumed_json) if prev_assumed_json else []
            prev_history = json.loads(prev_history_json) if prev_history_json else []
        else:
            prev_perm = {}
            prev_assumed = []
            prev_history = []

        assume_perm = {**{u: "no" for u in user_list}, **prev_perm}
        assume_perm = {u: assume_perm[u] for u in user_list}

        cur.execute("""
            INSERT INTO roles (role_name, role_arn, create_date, max_session_duration, principal, assume_permission, assumed_users, assume_history)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(role_arn) DO UPDATE SET
                role_name=excluded.role_name,
                create_date=excluded.create_date,
                max_session_duration=excluded.max_session_duration,
                principal=excluded.principal,
                assume_permission=excluded.assume_permission
        """, (
            role_name,
            role_arn,
            create_date,
            max_duration,
            principal_json,
            json.dumps(assume_perm),
            json.dumps(prev_assumed),
            json.dumps(prev_history)
        ))
        fetched_roles.add(role_arn)

    # delete removed roles
    to_delete = db_roles - fetched_roles
    for r in to_delete:
        cur.execute("DELETE FROM roles WHERE role_arn = ?", (r,))

    conn.commit()
    conn.close()


# --- Utility to get roles & users for template ---
def get_roles_and_users():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute("SELECT user_arn FROM users")
    valid_users = {row[0] for row in cur.fetchall()}

    cur.execute("SELECT role_arn, role_name, principal, assume_permission FROM roles")
    roles = []
    for row in cur.fetchall():
        role_arn, role_name, principal_json, assume_perm_json = row
        assume_perm = json.loads(assume_perm_json) if assume_perm_json else {}
        users = [u for u in assume_perm.keys() if u in valid_users]

        if not users:
            continue

        roles.append({
            "role_arn": role_arn,
            "role_name": role_name,
            "users": users,
            "assume_permission": {u: assume_perm[u] for u in users}
        })
    conn.close()
    return roles


# --- Routes ---
@manage_bp.before_app_request
def sync_roles_before_request():
    if session.get("logged_in"):
        try:
            list_roles_and_users()
        except Exception as e:
            current_app.logger.error(f"Failed to sync roles: {e}")


@manage_bp.route("/manage_sts_permissions")
@login_required
def manage_sts_permissions():

    user_info = get_user_type(
        session.get("access_key"),
        session.get("secret_key"),
        session.get("endpoint_url")
    )
    roles = get_roles_and_users()
    return render_template("manage_sts_permissions.html", roles=roles, user_info=user_info)


@manage_bp.route("/update_permission", methods=["POST"])
@login_required
def update_permission_route():
    data = request.json
    role_arn = data.get("role_arn")
    user_arn = data.get("user_arn")
    value = data.get("value")

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT assume_permission, assumed_users, assume_history FROM roles WHERE role_arn = ?", (role_arn,))
    row = cur.fetchone()
    if not row:
        return jsonify({"status": "error", "message": "Role not found"}), 404

    assume_perm_json, assumed_users_json, assume_history_json = row
    assume_perm = json.loads(assume_perm_json) if assume_perm_json else {}
    assumed_users_list = json.loads(assumed_users_json) if assumed_users_json else []
    assume_history_list = json.loads(assume_history_json) if assume_history_json else []

    assume_perm[user_arn] = value

    if value.lower() == "yes":
        if user_arn in assumed_users_list:
            assumed_users_list.remove(user_arn)
        assume_history_list = [h for h in assume_history_list if h.get("user") != user_arn]

    cur.execute("""
        UPDATE roles
        SET assume_permission = ?, assumed_users = ?, assume_history = ?
        WHERE role_arn = ?
    """, (
        json.dumps(assume_perm),
        json.dumps(assumed_users_list),
        json.dumps(assume_history_list),
        role_arn
    ))

    conn.commit()
    conn.close()
    return jsonify({"status": "success"})


# --- Initialize DB on import ---
init_db()
