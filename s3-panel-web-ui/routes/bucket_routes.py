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