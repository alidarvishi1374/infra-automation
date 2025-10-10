from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from helpers.aws import check_credentials
from helpers.auth import login_required

auth_bp = Blueprint("auth", __name__)

@auth_bp.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        access_key = request.form.get("access_key")
        secret_key = request.form.get("secret_key")
        endpoint_url = request.form.get("endpoint_url")

        valid, error_msg = check_credentials(access_key, secret_key, endpoint_url)
        if valid:
            session.update({
                "logged_in": True,
                "access_key": access_key,
                "secret_key": secret_key,
                "endpoint_url": endpoint_url
            })
            return redirect(url_for("bucket.buckets", success="Login successful!"))
        flash(error_msg, "danger")
        return redirect(url_for("auth.login"))

    return render_template("login.html", error=None)


@auth_bp.route("/logout")
@login_required
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
