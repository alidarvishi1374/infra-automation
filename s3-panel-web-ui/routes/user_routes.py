from flask import Blueprint, render_template, session,jsonify,request, flash, redirect, url_for
from helpers.auth import login_required
from helpers.aws import get_user_type, list_iam_users, create_iam_user

user_bp = Blueprint("user", __name__)

@user_bp.route("/profile")
@login_required
def profile():
    user_info = get_user_type(session["access_key"], session["secret_key"], session["endpoint_url"])
    show_alert = not any(user_info.get(k) for k in user_info if k != "type")
    return render_template("profile.html", user_info=user_info, show_alert=show_alert)


@user_bp.route("/iam_users")
@login_required
def iam_users():
    user_info = get_user_type(session["access_key"], session["secret_key"], session["endpoint_url"])
    iam_users_list = list_iam_users(session["access_key"], session["secret_key"], session["endpoint_url"])
    return render_template("iam_users.html", user_info=user_info, iam_users=iam_users_list)

@user_bp.route("/create_user", methods=["POST"])
@login_required
def create_user():
    user_name = request.form.get("username")
    endpoint = session.get("endpoint_url")
    access_key = session.get("access_key")
    secret_key = session.get("secret_key")
    region = "us-east-1"

    result = create_iam_user(endpoint, access_key, secret_key, user_name, region)
    return jsonify(result)
