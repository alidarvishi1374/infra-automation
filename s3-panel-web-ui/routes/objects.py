from flask import Blueprint, render_template, session, jsonify, request, flash, redirect, url_for, send_file, abort
from helpers.auth import login_required
import boto3
from io import BytesIO
from helpers.aws import get_user_type
import botocore.exceptions


object_bp = Blueprint("objects", __name__) 

def get_s3_client():
    """Return boto3 client configured with current session credentials"""
    return boto3.client(
        "s3",
        aws_access_key_id=session.get("access_key"),
        aws_secret_access_key=session.get("secret_key"),
        endpoint_url=session.get("endpoint_url"),
        region_name="us-east-1"
    )

@object_bp.route("/objects", methods=["GET"])
@login_required
def all_buckets():
    s3 = get_s3_client()
    user_info = get_user_type(session["access_key"], session["secret_key"], session["endpoint_url"])
    try:
        response = s3.list_buckets()
        buckets = response.get("Buckets", [])
    except botocore.exceptions.ClientError as e:
        code = e.response["Error"]["Code"]
        if code == "AccessDenied":
            abort(403)  # ⛔ مستقیم برو صفحه 403
        flash(f"Error listing buckets: {e.response['Error']['Message']}", "danger")
        buckets = []
    except Exception as e:
        flash(f"Unexpected error: {str(e)}", "danger")
        buckets = []

    return render_template(
        "objects.html",
        buckets=buckets,
        bucket_name=None,
        files=[],
        folders=[],
        prefix="",
        user_info=user_info
    )

@object_bp.route("/buckets/<bucket_name>/objects", methods=["GET", "POST"])
@login_required
def list_objects(bucket_name):
    s3 = get_s3_client()
    prefix = request.args.get("prefix") or request.form.get("prefix", "").strip()
    user_info = get_user_type(session["access_key"], session["secret_key"], session["endpoint_url"])

    # --- آپلود فایل ---
    if request.method == "POST" and "file" in request.files:
        file = request.files["file"]
        folder = request.form.get("folder", "").strip().strip("/")

        # بررسی نام فایل
        if not file.filename:
            flash("❌ File name is empty", "danger")
            return redirect(url_for("objects.list_objects", bucket_name=bucket_name, prefix=prefix))

        # بررسی کاراکترهای معتبر برای فولدر
        import re
        if folder and not re.match(r'^[\w\-\./]*$', folder):
            flash("❌ Folder name contains invalid characters", "danger")
            return redirect(url_for("objects.list_objects", bucket_name=bucket_name, prefix=prefix))

        # ساخت کلید (Key) صحیح
        key_parts = []
        if prefix:
            key_parts.append(prefix.rstrip("/"))
        if folder:
            key_parts.append(folder)
        key_parts.append(file.filename)
        key = "/".join(key_parts)

        try:
            # آپلود فایل
            s3.upload_fileobj(file, bucket_name, key)
            flash(f"✅ '{file.filename}' uploaded successfully to '{key}'", "success")
        except botocore.exceptions.ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code == "AccessDenied":
                abort(403)  # 🔥 مستقیماً به صفحه 403 می‌ره
            else:
                flash(f"❌ Upload failed: {e.response['Error']['Message']}", "danger")
        except Exception as e:
            flash(f"❌ Upload failed: {str(e)}", "danger")

        return redirect(url_for("objects.list_objects", bucket_name=bucket_name, prefix=prefix))

    # --- گرفتن لیست فایل‌ها و فولدرها ---
    files, folders = [], set()
    try:
        response = s3.list_objects_v2(Bucket=bucket_name, Prefix=prefix, Delimiter="/")

        # فولدرها
        for folder_prefix in response.get("CommonPrefixes", []):
            folder_name = folder_prefix.get("Prefix", "").rstrip("/").split("/")[-1]
            if folder_name:
                folders.add(folder_name)

        # فایل‌ها
        for obj in response.get("Contents", []):
            key = obj["Key"]
            rest = key[len(prefix):] if prefix else key
            if rest and "/" not in rest:
                files.append(obj)

    except botocore.exceptions.ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code == "AccessDenied":
            abort(403)  # 🔥 مستقیم به صفحه Access Denied
        else:
            flash(f"Error listing objects: {e.response['Error']['Message']}", "danger")

    # --- رندر صفحه ---
    return render_template(
        "objects.html",
        bucket_name=bucket_name,
        files=files,
        folders=list(folders),
        prefix=prefix,
        user_info=user_info
    )


# دانلود آبجکت
@object_bp.route("/buckets/<bucket_name>/objects/download/<path:key>")
@login_required
def download_object(bucket_name, key):
    s3 = get_s3_client()
    try:
        obj = s3.get_object(Bucket=bucket_name, Key=key)
        return send_file(
            BytesIO(obj["Body"].read()),
            download_name=key.split("/")[-1],
            as_attachment=True
        )
    except Exception as e:
        flash(f"Download failed: {str(e)}", "danger")
        return redirect(url_for("objects.list_objects", bucket_name=bucket_name))

# حذف آبجکت
@object_bp.route("/buckets/<bucket_name>/objects/delete/<path:key>", methods=["POST"])
@login_required
def delete_object(bucket_name, key):
    s3 = get_s3_client()
    prefix = request.args.get("prefix", "")
    try:
        s3.delete_object(Bucket=bucket_name, Key=key)
        flash(f"🗑️ {key} deleted successfully from '{bucket_name}'", "danger")
    except Exception as e:
        flash(f"❌ Delete failed: {str(e)}", "danger")
    return redirect(url_for("objects.list_objects", bucket_name=bucket_name, prefix=prefix))

# رفتن به فولدر
@object_bp.route("/buckets/<bucket_name>/objects/folders/<path:folder>")
@login_required
def view_folder(bucket_name, folder):
    return redirect(url_for("objects.list_objects", bucket_name=bucket_name, prefix=folder.strip("/") + "/"))
