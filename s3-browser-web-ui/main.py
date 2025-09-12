from flask import Flask, render_template_string, request, redirect, url_for, session
import boto3
from botocore.exceptions import NoCredentialsError, PartialCredentialsError, ClientError
from urllib.parse import urlparse

app = Flask(__name__)
app.secret_key = "super-secret-key"

login_page = """
<!DOCTYPE html>
<html>
<head>
    <title>AWS Login</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body class="bg-light">
<div class="container mt-5">
    <div class="card mx-auto" style="max-width: 500px;">
        <div class="card-body">
            <h3 class="card-title text-center mb-4">Login with AWS Credentials</h3>
            {% if error %}
                <div class="alert alert-danger" role="alert">{{ error }}</div>
            {% endif %}
            <form method="post">
                <div class="mb-3">
                    <label class="form-label">Access Key</label>
                    <input type="text" name="access_key" class="form-control" required>
                </div>
                <div class="mb-3">
                    <label class="form-label">Secret Key</label>
                    <input type="password" name="secret_key" class="form-control" required>
                </div>
                <div class="mb-3">
                    <label class="form-label">Endpoint URL</label>
                    <input type="text" name="endpoint_url" class="form-control" required placeholder="https://s3.example.com">
                </div>
                <button type="submit" class="btn btn-primary w-100">Login</button>
            </form>
        </div>
    </div>
</div>
</body>
</html>
"""

home_page = """
<!DOCTYPE html>
<html>
<head>
    <title>Home</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body class="bg-light">
<div class="container mt-5 text-center">
    <div class="card mx-auto" style="max-width: 500px;">
        <div class="card-body">
            <h3 class="text-success">✅ Login Successful!</h3>
            <p>Your AWS credentials are valid.</p>
            <a href="{{ url_for('logout') }}" class="btn btn-danger">Logout</a>
        </div>
    </div>
</div>
</body>
</html>
"""

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
            return redirect(url_for("home"))
        else:
            return render_template_string(login_page, error=error_msg)

    return render_template_string(login_page, error=None)

@app.route("/home")
def home():
    if session.get("logged_in"):
        return render_template_string(home_page)
    return redirect(url_for("login"))

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

if __name__ == "__main__":
    app.run(debug=True)
