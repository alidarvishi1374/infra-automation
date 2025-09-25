from flask import Blueprint, render_template, session, redirect, url_for, flash, request, jsonify, json
from helpers.auth import login_required
from helpers.aws import get_buckets_info, get_user_type, create_bucket
from helpers.aws import get_s3_client
from botocore.exceptions import ClientError

bucket_bp = Blueprint("bucket", __name__)

@bucket_bp.route("/home")
@login_required
def home():
    buckets_info = get_buckets_info()
    bucket_count = len(buckets_info)
    total_size = sum(bucket["Size"] for bucket in buckets_info)
    user_info = get_user_type(session["access_key"], session["secret_key"], session["endpoint_url"])
    return render_template("index.html", bucket_count=bucket_count, total_size=total_size, user_info=user_info)


@bucket_bp.route("/buckets")
@login_required
def buckets():
    session.pop("buckets_info", None)
    buckets_info = get_buckets_info()
    user_info = get_user_type(session["access_key"], session["secret_key"], session["endpoint_url"])
    return render_template("tables.html", buckets=buckets_info, user_info=user_info)


@bucket_bp.route("/charts")
@login_required
def charts():
    user_info = get_user_type(session["access_key"], session["secret_key"], session["endpoint_url"])
    return render_template("charts.html", user_info=user_info)


@bucket_bp.route("/tables")
@login_required
def tables():
    return redirect(url_for("bucket.buckets"))


@bucket_bp.route("/not_found")
@login_required
def not_found():
    user_info = get_user_type(session["access_key"], session["secret_key"], session["endpoint_url"])
    return render_template("404.html", user_info=user_info)

@bucket_bp.route("/create_bucket", methods=["POST"])
@login_required
def create_bucket_route():
    data = request.get_json()
    bucket_name = data.get("bucket_name")
    region = data.get("region", "us-east-1")
    enable_locking = data.get("enable_locking", False)

    endpoint = session.get("endpoint_url")
    access_key = session.get("access_key")
    secret_key = session.get("secret_key")

    # صدا زدن تابع موجود در aws.py
    response = create_bucket(endpoint, access_key, secret_key, bucket_name, region, enable_locking)
    
    return jsonify(response)



@bucket_bp.route("/delete_bucket", methods=["POST"])
@login_required
def delete_bucket_route():
    """
    Delete an S3 bucket by name.
    Expects JSON: { "bucket_name": "example-bucket" }
    """
    data = request.get_json()
    bucket_name = data.get("bucket_name")

    if not bucket_name:
        return jsonify({"success": False, "message": "❌ Bucket name is required."}), 400

    s3 = get_s3_client()

    try:
        # Check if bucket is empty
        objects = s3.list_objects_v2(Bucket=bucket_name)
        if objects.get("KeyCount", 0) > 0:
            return jsonify({
                "success": False,
                "message": f"❌ Bucket '{bucket_name}' is not empty. Please empty it before deletion."
            }), 400

        # Delete bucket
        s3.delete_bucket(Bucket=bucket_name)
        # Refresh session cache if needed
        session.pop("buckets_info", None)
        return jsonify({"success": True, "message": f"✅ Bucket '{bucket_name}' deleted successfully!"})

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        error_msg = e.response.get("Error", {}).get("Message", str(e))
        return jsonify({
            "success": False,
            "message": f"❌ {error_code}: {error_msg}"
        }), 400

    except Exception as e:
        return jsonify({"success": False, "message": f"❌ Unexpected error: {str(e)}"}), 500


@bucket_bp.route("/toggle_versioning", methods=["POST"])
@login_required
def toggle_versioning():
    """
    Enable or disable versioning for a bucket.
    Expects JSON: {
        "bucket_name": "example-bucket",
        "action": "enable" or "disable"
    }
    """
    data = request.get_json()
    bucket_name = data.get("bucket_name")
    action = data.get("action", "").lower()

    if not bucket_name:
        return jsonify({"success": False, "message": "❌ Bucket name is required."}), 400
    if action not in ["enable", "disable"]:
        return jsonify({"success": False, "message": "❌ Action must be 'enable' or 'disable'."}), 400

    s3 = get_s3_client()
    try:
        status = "Enabled" if action == "enable" else "Suspended"
        s3.put_bucket_versioning(
            Bucket=bucket_name,
            VersioningConfiguration={"Status": status}
        )
        # Refresh cache
        session.pop("buckets_info", None)
        return jsonify({
            "success": True,
            "message": f"✅ Versioning for bucket '{bucket_name}' set to '{status}'."
        })
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        error_msg = e.response.get("Error", {}).get("Message", str(e))
        return jsonify({
            "success": False,
            "message": f"❌ {error_code}: {error_msg}"
        }), 400
    except Exception as e:
        return jsonify({"success": False, "message": f"❌ Unexpected error: {str(e)}"}), 500

@bucket_bp.route("/api/get_bucket_versioning")
@login_required
def get_bucket_versioning():
    bucket_name = request.args.get("bucket_name")
    s3 = get_s3_client()
    try:
        versioning = s3.get_bucket_versioning(Bucket=bucket_name)
        return jsonify({"success": True, "versioning_enabled": versioning.get("Status") == "Enabled"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})
    

@bucket_bp.route("/add_bucket_tag", methods=["POST"])
@login_required
def add_bucket_tag():
    data = request.get_json(silent=True) or {}
    # پشتیبانی از چند نام فیلد (fallback)
    bucket_name = data.get("bucket_name") or data.get("BucketName") or data.get("bucket")
    tag_key = data.get("tag_key") or data.get("key") or data.get("TagKey")
    tag_value = data.get("tag_value") or data.get("value") or data.get("TagValue")

    if not bucket_name or not tag_key or not tag_value:
        return jsonify({"success": False, "message": "❌ Bucket name, key and value are required."}), 400

    s3 = get_s3_client()

    try:
        # تلاش برای گرفتن تگ‌های موجود (تا جایگزین نشه، ولی به لیست اضافه کنیم)
        existing = []
        try:
            resp = s3.get_bucket_tagging(Bucket=bucket_name)
            existing = resp.get("TagSet", [])
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code", "")
            # اگر هیچ تگی وجود نداشته باشه بعضی سرویس‌ها NoSuchTagSet میدن
            if code not in ("NoSuchTagSet", "404", "NoSuchTagSetError", "NoSuchTagSetFault"):
                raise

        # حذف تگ قدیمی با همون Key در صورت وجود و اضافه کردن مقدار جدید
        new_tags = [t for t in existing if t.get("Key") != tag_key]
        new_tags.append({"Key": tag_key, "Value": tag_value})

        s3.put_bucket_tagging(Bucket=bucket_name, Tagging={"TagSet": new_tags})

        session.pop("buckets_info", None)

        return jsonify({"success": True, "message": f"✅ Tag ({tag_key}={tag_value}) added to {bucket_name}."})
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        error_msg = e.response.get("Error", {}).get("Message", str(e))
        return jsonify({"success": False, "message": f"❌ {error_code}: {error_msg}"}), 400
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@bucket_bp.route("/delete_bucket_tag", methods=["POST"])
@login_required
def delete_bucket_tag():
    data = request.get_json(silent=True) or {}
    bucket_name = data.get("bucket_name")
    tag_key = data.get("tag_key") or data.get("key")

    if not bucket_name or not tag_key:
        return jsonify({"success": False, "message": "❌ Bucket name and tag_key are required."}), 400

    s3 = get_s3_client()
    try:
        # گرفتن تگ‌های موجود
        resp = s3.get_bucket_tagging(Bucket=bucket_name)
        existing = resp.get("TagSet", [])

        # فیلتر کردن تگ مورد نظر
        new_tags = [t for t in existing if t.get("Key") != tag_key]

        if len(new_tags) == len(existing):
            return jsonify({"success": False, "message": f"❌ Tag '{tag_key}' not found."}), 404

        # ست کردن تگ‌های جدید (بدون اون تگ)
        if new_tags:
            s3.put_bucket_tagging(Bucket=bucket_name, Tagging={"TagSet": new_tags})
        else:
            # اگر هیچ تگی باقی نموند → باید کل تگ‌ها حذف بشن
            s3.delete_bucket_tagging(Bucket=bucket_name)

        session.pop("buckets_info", None)

        return jsonify({"success": True, "message": f"✅ Tag '{tag_key}' deleted from {bucket_name}."})

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        error_msg = e.response.get("Error", {}).get("Message", str(e))
        return jsonify({"success": False, "message": f"❌ {error_code}: {error_msg}"}), 400
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@bucket_bp.route("/get_bucket_tags", methods=["POST", "GET"])
@login_required
def get_bucket_tags():
    if request.method == "POST":
        data = request.get_json() or {}
        bucket_name = data.get("bucket_name")
    else:  # GET
        bucket_name = request.args.get("bucket_name")

    if not bucket_name:
        return jsonify({"success": False, "message": "Bucket name required"}), 400

    s3 = get_s3_client()
    try:
        resp = s3.get_bucket_tagging(Bucket=bucket_name)
        tags = resp.get("TagSet", [])
        return jsonify({"success": True, "tags": tags})
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") in ("NoSuchTagSet", "404"):
            return jsonify({"success": True, "tags": []})
        return jsonify({"success": False, "message": str(e)}), 400


@bucket_bp.route("/get_bucket_policies", methods=["POST", "GET"])
@login_required
def get_bucket_policies():
    bucket_name = request.get_json().get("bucket_name") if request.method=="POST" else request.args.get("bucket_name")
    if not bucket_name:
        return jsonify({"success": False, "message": "Bucket name required"}), 400

    s3 = get_s3_client()
    try:
        resp = s3.get_bucket_policy(Bucket=bucket_name)
        policy_json = resp.get("Policy")
        return jsonify({"success": True, "policies": [policy_json] if policy_json else []})
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code")
        if code in ("NoSuchBucketPolicy", "404"):
            return jsonify({"success": True, "policies": []})
        return jsonify({"success": False, "message": str(e)}), 400

@bucket_bp.route("/set_bucket_policy", methods=["POST"])
@login_required
def add_bucket_policy():
    data = request.get_json(silent=True) or {}
    bucket_name = data.get("bucket_name")
    policy = data.get("policy")
    if not bucket_name or not policy:
        return jsonify({"success": False, "message": "Bucket name and policy required"}), 400

    s3 = get_s3_client()
    try:
        s3.put_bucket_policy(Bucket=bucket_name, Policy=policy)
        session.pop("buckets_info", None)
        return jsonify({"success": True, "message": f"✅ Policy added to {bucket_name}"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 400

@bucket_bp.route("/delete_bucket_policy", methods=["POST"])
@login_required
def delete_bucket_policy():
    data = request.get_json(silent=True) or {}
    bucket_name = data.get("bucket_name")

    if not bucket_name:
        return jsonify({"success": False, "message": "Bucket name required"}), 400

    s3 = get_s3_client()
    try:
        s3.delete_bucket_policy(Bucket=bucket_name)
        session.pop("buckets_info", None)
        return jsonify({"success": True, "message": f"✅ Policy deleted from {bucket_name}"})
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code")
        if code in ("NoSuchBucketPolicy", "NoSuchBucket"):
            return jsonify({"success": True, "message": "Policy does not exist"})
        return jsonify({"success": False, "message": str(e)}), 400


@bucket_bp.route("/get_bucket_lifecycle", methods=["POST", "GET"])
@login_required
def get_bucket_lifecycle():
    bucket_name = request.get_json().get("bucket_name") if request.method == "POST" else request.args.get("bucket_name")
    if not bucket_name:
        return jsonify({"success": False, "message": "Bucket name required"}), 400

    s3 = get_s3_client()
    try:
        resp = s3.get_bucket_lifecycle_configuration(Bucket=bucket_name)
        lifecycle = resp.get("Rules", [])
        return jsonify({"success": True, "lifecycle": lifecycle})
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code")
        if code in ("NoSuchLifecycleConfiguration", "404"):
            return jsonify({"success": True, "lifecycle": []})
        return jsonify({"success": False, "message": str(e)}), 400


@bucket_bp.route("/set_bucket_lifecycle", methods=["POST"])
@login_required
def set_bucket_lifecycle():
    data = request.get_json(silent=True) or {}
    bucket_name = data.get("bucket_name")
    lifecycle = data.get("lifecycle")

    if not bucket_name or not lifecycle:
        return jsonify({"success": False, "message": "Bucket name and lifecycle required"}), 400

    s3 = get_s3_client()
    try:
        # اطمینان از اینکه همیشه یه لیست از Ruleها داریم
        if isinstance(lifecycle, str):
            lifecycle = json.loads(lifecycle)
        if isinstance(lifecycle, dict):
            lifecycle = [lifecycle]
        lifecycle_dict = {"Rules": lifecycle}

        s3.put_bucket_lifecycle_configuration(Bucket=bucket_name, LifecycleConfiguration=lifecycle_dict)
        session.pop("buckets_info", None)
        return jsonify({"success": True, "message": f"✅ Lifecycle added to {bucket_name}"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 400


@bucket_bp.route("/delete_bucket_lifecycle", methods=["POST"])
@login_required
def delete_bucket_lifecycle():
    data = request.get_json(silent=True) or {}
    bucket_name = data.get("bucket_name")
    if not bucket_name:
        return jsonify({"success": False, "message": "Bucket name required"}), 400

    s3 = get_s3_client()
    try:
        s3.delete_bucket_lifecycle(Bucket=bucket_name) 
        session.pop("buckets_info", None)
        return jsonify({"success": True, "message": f"✅ Lifecycle deleted from {bucket_name}"})
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code")
        if code in ("NoSuchLifecycleConfiguration", "NoSuchBucket"):
            return jsonify({"success": True, "message": "Lifecycle does not exist"})
        return jsonify({"success": False, "message": str(e)}), 400
    

@bucket_bp.route("/apply_replication_rule", methods=["POST"])
@login_required
def apply_replication_rule():
    """
    Apply replication configuration to a bucket.
    Expects JSON: {
        "bucket_name": "example-bucket",
        "replication": { ... }   # full replication configuration JSON
    }
    """
    data = request.get_json(silent=True) or {}
    bucket_name = data.get("bucket_name")
    replication_config = data.get("replication")

    if not bucket_name or not replication_config:
        return jsonify({"success": False, "message": "❌ bucket_name and replication config are required."}), 400

    s3 = get_s3_client()
    try:
        s3.put_bucket_replication(
            Bucket=bucket_name,
            ReplicationConfiguration=replication_config
        )
        # refresh cache
        session.pop("buckets_info", None)
        return jsonify({"success": True, "message": f"✅ Replication rule applied to {bucket_name}"})
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        error_msg = e.response.get("Error", {}).get("Message", str(e))
        return jsonify({"success": False, "message": f"❌ {error_code}: {error_msg}"}), 400
    except Exception as e:
        return jsonify({"success": False, "message": f"❌ Unexpected error: {str(e)}"}), 500


@bucket_bp.route("/get_bucket_replication", methods=["POST", "GET"])
@login_required
def get_bucket_replication():
    """
    Get replication configuration of a bucket.
    Supports both GET (query param) and POST (json body).
    """
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        bucket_name = data.get("bucket_name")
    else:
        bucket_name = request.args.get("bucket_name")

    if not bucket_name:
        return jsonify({"success": False, "message": "❌ Bucket name is required."}), 400

    s3 = get_s3_client()
    try:
        resp = s3.get_bucket_replication(Bucket=bucket_name)
        replication = resp.get("ReplicationConfiguration", {})
        return jsonify({"success": True, "replication": replication})
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "")
        if code in ("ReplicationConfigurationNotFoundError", "NoSuchReplicationConfiguration", "404"):
            return jsonify({"success": True, "replication": {}})
        return jsonify({"success": False, "message": str(e)}), 400
    except Exception as e:
        return jsonify({"success": False, "message": f"❌ Unexpected error: {str(e)}"}), 500
@bucket_bp.route("/configure_locking", methods=["POST"])
@login_required
def configure_locking():
    """
    Configure object lock for an existing bucket.
    Expects JSON: {
        "bucket": "example-bucket",
        "mode": "GOVERNANCE" or "COMPLIANCE",
        "days": 30
    }
    """
    data = request.get_json(silent=True) or {}
    bucket = data.get("bucket")
    mode = data.get("mode")
    days = data.get("days")

    if not bucket or not mode or not days:
        return jsonify({"success": False, "message": "Bucket name, mode and days are required."}), 400

    try:
        days = int(days)
    except (TypeError, ValueError):
        return jsonify({"success": False, "message": "Days must be a valid integer."}), 400

    s3 = get_s3_client()

    try:
        # ساخت dictionary برای retention configuration
        lock_config = {
            "ObjectLockEnabled": "Enabled",
            "Rule": {
                "DefaultRetention": {
                    "Mode": mode,
                    "Days": days
                }
            }
        }

        s3.put_object_lock_configuration(
            Bucket=bucket,
            ObjectLockConfiguration=lock_config
        )

        # پاک کردن cache session
        session.pop("buckets_info", None)

        return jsonify({
            "success": True,
            "message": f"✅ Locking configured: {mode} for {days} days on {bucket}"
        })

    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "Unknown")
        msg = e.response.get("Error", {}).get("Message", str(e))
        return jsonify({"success": False, "message": f"❌ {code}: {msg}"}), 400
    except Exception as e:
        return jsonify({"success": False, "message": f"❌ Unexpected error: {str(e)}"}), 500
