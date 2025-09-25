from flask import Flask, render_template, request
import sqlite3
import boto3
from botocore.exceptions import ClientError
import json
import datetime
from zoneinfo import ZoneInfo

app = Flask(__name__)
DB_FILE = "roles.db"
TEHRAN_TZ = ZoneInfo("Asia/Tehran")

# -----------------------------
# گرفتن ARN یوزر از Access/Secret
# -----------------------------
def get_user_arn(access_key, secret_key, endpoint_url, region_name="us-east-1"):
    iam_client = boto3.client(
        "iam",
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        endpoint_url=endpoint_url,
        region_name=region_name
    )
    try:
        response = iam_client.get_user()
        user = response['User']
        return user.get('Arn', '')
    except ClientError:
        return None

# -----------------------------
# بررسی اینکه ARN یوزر داخل principal هست
# -----------------------------
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

# -----------------------------
# گرفتن رول‌هایی که user می‌تواند assume کند
# -----------------------------
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

# -----------------------------
# Assume Role با boto3
# -----------------------------
def assume_role(access_key, secret_key, endpoint, role_arn, session_name, duration_seconds):
    client = boto3.client(
        'sts',
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        endpoint_url=endpoint,
        region_name='us-east-1'
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

# -----------------------------
# ثبت یوزر و تاریخ assume در دیتابیس (با expiration per-user به وقت تهران)
# -----------------------------
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

        # اضافه کردن یوزر به لیست assumed_users
        if user_arn not in assumed_users_list:
            assumed_users_list.append(user_arn)

        now = datetime.datetime.now(TEHRAN_TZ)
        expiration_time = now + datetime.timedelta(seconds=duration_seconds)

        assume_history_list.append({
            "user": user_arn,
            "timestamp": now.isoformat(),
            "expiration": expiration_time.isoformat()
        })

        # وقتی توکن جدید ساخته شد، assume_permission برای اون یوزر به no برمی‌گردد
        assume_perm[user_arn] = "no"

        cur.execute("""
            UPDATE roles 
            SET assumed_users = ?, assume_history = ?, assume_permission = ?
            WHERE role_arn = ?
        """, (json.dumps(assumed_users_list), json.dumps(assume_history_list), json.dumps(assume_perm), role_arn))
        conn.commit()
    conn.close()

# -----------------------------
# چک کردن expiration قبل از assume
# -----------------------------
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

    # بررسی expiration
    user_history = [h for h in assume_history_list if h.get("user") == user_arn]
    now = datetime.datetime.now(TEHRAN_TZ)

    if user_history:
        latest = user_history[-1]
        expiration = datetime.datetime.fromisoformat(latest["expiration"])
        if now < expiration:
            return "active", False  # هنوز اعتبار دارد → اجازه نده
        else:
            expired = True
    else:
        expired = True  # اگر قبلا توکنی نساخته

    # بررسی permission
    perm = assume_perm.get(user_arn, "no")
    return ("not_exists" if not user_history else "expired"), (perm == "yes")

# -----------------------------
# روت اصلی
# -----------------------------
@app.route("/", methods=["GET", "POST"])
def index():
    roles = []
    assumed_creds = None
    error = None

    if request.method == "POST":
        access_key = request.form.get("access_key")
        secret_key = request.form.get("secret_key")
        endpoint = request.form.get("endpoint")
        role_arn = request.form.get("role_arn")
        action = request.form.get("action")
        duration_seconds = request.form.get("duration_seconds")

        try:
            duration_seconds = int(duration_seconds) if duration_seconds else None
        except ValueError:
            duration_seconds = None

        user_arn = get_user_arn(access_key, secret_key, endpoint)
        if not user_arn:
            error = "Cannot fetch user ARN. Check credentials or permissions."
        else:
            roles = get_roles_for_user(user_arn)

        if action == "assume_role" and role_arn:
            max_duration = next((r['max_session_duration'] for r in roles if r['role_arn'] == role_arn), 3600)
            duration = duration_seconds if duration_seconds else max_duration

            status, has_permission = check_expiration_before_assume(role_arn, user_arn)

            if status == "active":
                error = "توکن شما هنوز منقضی نشده و نمی‌توانید مجدد توکن بگیرید."
            elif not has_permission:
                error = "شما اجازه ساخت توکن ندارید. لطفا از ادمین درخواست کنید."
            else:
                # اجازه ساخت توکن صادر شد
                assumed_creds = assume_role(access_key, secret_key, endpoint, role_arn, "temp-session", duration)
                register_assume(role_arn, user_arn, duration)

    return render_template("test.html", roles=roles, error=error, assumed_creds=assumed_creds)

# -----------------------------
# اجرای برنامه
# -----------------------------
if __name__ == "__main__":
    app.run(debug=True, port=5001)
