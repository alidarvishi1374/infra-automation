from flask import Blueprint, render_template, session, redirect, url_for, flash
from helpers.auth import login_required
from helpers.aws import get_buckets_info, get_user_type

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
