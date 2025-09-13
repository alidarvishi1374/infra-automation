from flask import Flask, render_template, request, redirect, url_for, session, flash, get_flashed_messages
import boto3
from botocore.exceptions import NoCredentialsError, PartialCredentialsError, ClientError
from urllib.parse import urlparse
from functools import wraps
import json

app = Flask(__name__)
app.secret_key = "super-secret-key"


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login", next=request.path))
        return f(*args, **kwargs)
    return decorated_function

def is_valid_url(url):
    try:
        result = urlparse(url)
        return all([result.scheme in ("http", "https"), result.netloc])
    except:
        return False

def check_credentials(access_key=None, secret_key=None, endpoint_url=None):
    if endpoint_url and not is_valid_url(endpoint_url):
        return False, "Endpoint URL is invalid!, please use http or https"

    try:
        if access_key and secret_key:
            boto_sess = boto3.Session(
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
            )
        else:
            boto_sess = boto3.Session()

        s3 = boto_sess.client("s3", endpoint_url=endpoint_url)
        s3.list_buckets()
        return True, None
    except NoCredentialsError:
        return False, "AWS credentials not found!"
    except PartialCredentialsError:
        return False, "Incomplete AWS credentials!"
    except ClientError as e:
        msg = e.response.get('Error', {}).get('Message')
        if not msg:
            msg = "Invalid AWS credentials or insufficient permissions."
        return False, msg
    except Exception as e:
        return False, f"Unexpected error: {str(e)}"

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        access_key = request.form.get("access_key")
        secret_key = request.form.get("secret_key")
        endpoint_url = request.form.get("endpoint_url")

        valid, error_msg = check_credentials(access_key, secret_key, endpoint_url)
        if valid:
            session["logged_in"] = True
            session["access_key"] = access_key
            session["secret_key"] = secret_key
            session["endpoint_url"] = endpoint_url
            return redirect(url_for("home", success="Login successful!"))
        else:
            flash(error_msg, "danger")
            return redirect(url_for("login"))

    return render_template("login.html", error=None)

def get_s3_client():
    return boto3.client(
        "s3",
        aws_access_key_id=session.get("access_key"),
        aws_secret_access_key=session.get("secret_key"),
        endpoint_url=session.get("endpoint_url")
    )


def get_buckets_info():

    if session.get("buckets_info"):
        return session["buckets_info"]
    s3_client = get_s3_client()
    buckets_info = []
    response = s3_client.list_buckets()

    for bucket in response["Buckets"]:

        bucket_name = bucket["Name"]

        # Size of ever bucket
        total_size = 0
        paginator = s3_client.get_paginator('list_objects_v2')
        page_iterator = paginator.paginate(Bucket=bucket_name)

        for page in page_iterator:
            if "Contents" in page:
                for obj in page["Contents"]:
                    total_size += obj["Size"]

        owner_info = response.get("Owner", {})
        bucket_data = {
            "Name": bucket_name,
            "CreationDate": bucket["CreationDate"].isoformat(),
            "Owner": owner_info.get("ID"),
            "Size": float(f"{total_size / (1024 * 1024):.3f}")

        }
        
        # Bucket Location
        try:
            location = s3_client.get_bucket_location(Bucket=bucket_name)
            bucket_data["Region"] = location.get("LocationConstraint")
        except Exception as e:
            bucket_data["Region"] = str(e)
        
        # Bucket Policy
        try:
            policy = s3_client.get_bucket_policy(Bucket=bucket_name)
            bucket_data["Policy"] = json.loads(policy["Policy"])
        except:
            bucket_data["Policy"] = None

        # Bucket ACL
        try:
            acl = s3_client.get_bucket_acl(Bucket=bucket_name)
            bucket_data["ACL"] = acl["Grants"][0]["Permission"]
        except:
            bucket_data["ACL"] = None

        # Bucket tagging
        try:
            tags = s3_client.get_bucket_tagging(Bucket=bucket_name)
            bucket_data["Tags"] = tags.get("TagSet", [])
        except:
            bucket_data["Tags"] = []
        
        # MFA + Versioning
        try:
            versioning = s3_client.get_bucket_versioning(Bucket=bucket_name)
            bucket_data["Versioning"] = versioning.get("Status") == "Enabled"
            bucket_data["MFADelete"] = versioning.get("MFADelete") == "Enabled"
        except:
            bucket_data["Versioning"] = False
            bucket_data["MFADelete"] = False

        # Replication
        try:
            replication = s3_client.get_bucket_replication(Bucket=bucket_name)
            replication_conf = replication.get("ReplicationConfiguration", {})
            bucket_data["Replication"] = bool(replication_conf.get("Role"))
        except s3_client.exceptions.ClientError:
            bucket_data["Replication"] = False
        except Exception:
            bucket_data["Replication"] = False


        # Encryption
        try:
            encryption = s3_client.get_bucket_encryption(Bucket=bucket_name)
            bucket_data["Encryption"] = encryption.get("ServerSideEncryptionConfiguration") is not None
        except:
            bucket_data["Encryption"] = False


        buckets_info.append(bucket_data)
        session["buckets_info"] = buckets_info
    return buckets_info

def get_user_type(access_key, secret_key, endpoint_url, region_name=""):

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
        arn = user.get('Arn', '')

        if ":root" in arn:
            user_type = "Root Account"
        else:
            user_type = "IAM User"

        return {
            "type": user_type,
            "UserName": user.get('UserName'),
            "UserId": user.get('UserId'),
            "Arn": arn,
            "CreateDate": str(user.get('CreateDate'))
        }

    except ClientError as e:
        code = e.response['Error']['Code']
        if code == "MethodNotAllowed":
            return {"type": "System User"}
        elif code == "AccessDenied":
            return {"type": "IAM User"}
        else:
            return {"type": "Unknown", "error": str(e)}


def list_iam_users(access_key_id, secret_access_key, endpoint_url, session_token=None):
    users_info = []
    try:
        client = boto3.client(
            "iam",
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            aws_session_token=session_token,
            endpoint_url=endpoint_url,
            region_name="us-east-1"
        )

        paginator = client.get_paginator("list_users")
        for page in paginator.paginate():
            for u in page.get("Users", []):
                username = u.get("UserName")
                arn = u.get("Arn")
                created = u.get("CreateDate")

                try:
                    groups_resp = client.list_groups_for_user(UserName=username)
                    groups = [g["GroupName"] for g in groups_resp.get("Groups", [])]
                except ClientError:
                    groups = []

                users_info.append({
                    "UserName": username,
                    "Arn": arn,
                    "Created": str(created),
                    "Groups": groups if groups else ["No Groups"]
                })

    except NoCredentialsError:
        return [{"Error": "Credentials not found or invalid."}]
    except ClientError as e:
        return [{"Error": f"AWS client error: {str(e)}"}]

    return users_info





@app.route("/profile")
@login_required
def profile():
    access_key = session.get("access_key")
    secret_key = session.get("secret_key")
    endpoint_url = session.get("endpoint_url")



    if not all([access_key, secret_key, endpoint_url]):
        flash("AWS credentials missing!", "danger")
        return redirect(url_for("login"))

    user_info = get_user_type(access_key, secret_key, endpoint_url)

    show_alert = False
    for key, value in user_info.items():
        if key != "type" and value:
            show_alert = False
            break
        else:
            show_alert = True

    return render_template("profile.html", user_info=user_info, show_alert=show_alert)


@app.route("/buckets")
@login_required
def buckets():
    buckets_info = get_buckets_info()
    access_key = session.get("access_key")
    secret_key = session.get("secret_key")
    endpoint_url = session.get("endpoint_url")
    user_info = get_user_type(access_key, secret_key, endpoint_url)
    return render_template("tables.html", buckets=buckets_info, user_info=user_info)

@app.route("/charts")
@login_required
def charts():
    access_key = session.get("access_key")
    secret_key = session.get("secret_key")
    endpoint_url = session.get("endpoint_url")
    user_info = get_user_type(access_key, secret_key, endpoint_url)
    return render_template("charts.html", user_info=user_info)

@app.route("/tables")
@login_required
def tables():
    return redirect(url_for("buckets"))

@app.route("/iam_users")
@login_required
def iam_users():
    access_key = session.get("access_key")
    secret_key = session.get("secret_key")
    endpoint_url = session.get("endpoint_url")

    user_info = get_user_type(access_key, secret_key, endpoint_url)
    iam_users_list = list_iam_users(access_key, secret_key, endpoint_url)

    return render_template("iam_users.html", user_info=user_info, iam_users=iam_users_list)


@app.route("/not_found")
@login_required
def not_found():
    access_key = session.get("access_key")
    secret_key = session.get("secret_key")
    endpoint_url = session.get("endpoint_url")
    user_info = get_user_type(access_key, secret_key, endpoint_url)
    return render_template("404.html", user_info=user_info)

@app.route("/home")
@login_required
def home():
    buckets_info = get_buckets_info()
    bucket_count = len(buckets_info)
    total_size = sum(bucket["Size"] for bucket in buckets_info) 
    access_key = session.get("access_key")
    secret_key = session.get("secret_key")
    endpoint_url = session.get("endpoint_url")
    user_info = get_user_type(access_key, secret_key, endpoint_url)
    return render_template("index.html", bucket_count=bucket_count, total_size=total_size, user_info=user_info)

@app.route("/logout")
@login_required
def logout():
    session.clear()
    return redirect(url_for("login"))

if __name__ == "__main__":
    app.run(debug=True)
