from flask import Flask, render_template, request, jsonify
import sqlite3
import json
from test import list_roles_and_users

app = Flask(__name__)
DB_FILE = "roles.db"

def get_roles_and_users():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    # گرفتن یوزرهای معتبر
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

@app.before_request
def sync_roles():
    # قبل از هر request، دیتابیس رو با endpoint سینک کن
    list_roles_and_users()

@app.route("/manage_permissions")
def manage_permissions():
    roles = get_roles_and_users()
    return render_template("manage_permissions.html", roles=roles)

@app.route("/update_permission", methods=["POST"])
def update_permission():
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

if __name__ == "__main__":
    app.run(debug=True, port=5002)
