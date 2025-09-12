from flask import Flask, render_template, request, redirect, url_for, session, flash, get_flashed_messages
import boto3
from botocore.exceptions import NoCredentialsError, PartialCredentialsError, ClientError
from urllib.parse import urlparse
from functools import wraps

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
            return redirect(url_for("home", success="Login successful!"))
        else:
            flash(error_msg, "danger")
            return redirect(url_for("login"))

    return render_template("login.html", error=None)

@app.route("/cards")
@login_required
def cards():
    return render_template("cards.html")

@app.route("/charts")
@login_required
def charts():
    return render_template("charts.html")

@app.route("/tables")
@login_required
def tables():
    return render_template("tables.html")

@app.route("/animation")
@login_required
def animation():
    return render_template("animation.html")

@app.route("/not_found")
@login_required
def not_found():
    return render_template("404.html")

@app.route("/home")
@login_required
def home():
    if session.get("logged_in"):
        success_msg = request.args.get("success")
        return render_template("index.html", success=success_msg)
    return redirect(url_for("login"))

@app.route("/logout")
@login_required
def logout():
    session.clear()
    return redirect(url_for("login"))

if __name__ == "__main__":
    app.run(debug=True)
