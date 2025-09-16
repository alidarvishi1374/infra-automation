from flask import Blueprint, render_template, session, redirect, url_for, flash, request, jsonify
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

    result = create_bucket(
        session["endpoint_url"],
        session["access_key"],
        session["secret_key"],
        bucket_name,
        region
    )
    return jsonify(result)


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
        # اگر هیچ تگی وجود نداشت S3 خطای NoSuchTagSet می‌دهد
        if e.response.get("Error", {}).get("Code") in ("NoSuchTagSet", "404"):
            return jsonify({"success": True, "tags": []})
        return jsonify({"success": False, "message": str(e)}), 400
