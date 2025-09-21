from flask import Flask, request, render_template_string, redirect, url_for, flash
import boto3
import json

app = Flask(__name__)
app.secret_key = "supersecretkey"  # برای flash messages

# ===============================
# تنظیمات اتصال به Ceph S3
# ===============================
AWS_ACCESS_KEY_ID = "SX8V1T2RJ5S3Q8JREF3V"
AWS_SECRET_ACCESS_KEY = "69R2Npx6sEHlQQEg64ZyJAlyxqfX45ImwfwYvuEP"
ENDPOINT_URL = "http://192.168.112.113"

# ===============================
# ایجاد client S3 با boto3
# ===============================
def get_s3_client():
    return boto3.client(
        's3',
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        endpoint_url=ENDPOINT_URL,
        region_name="default"
    )

# ===============================
# صفحه اصلی HTML
# ===============================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Ceph S3 Replication UI</title>
<script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-100 p-6">
    <div class="max-w-3xl mx-auto bg-white p-6 rounded shadow">
        <h1 class="text-2xl font-bold mb-4">Enable S3 Replication</h1>

        {% with messages = get_flashed_messages() %}
          {% if messages %}
            <div class="mb-4">
            {% for message in messages %}
              <div class="bg-green-100 border border-green-400 text-green-700 px-4 py-2 rounded mb-2">
                {{ message }}
              </div>
            {% endfor %}
            </div>
          {% endif %}
        {% endwith %}

        <form method="post" action="{{ url_for('apply_replication') }}">
            <label class="block font-semibold mb-1">Source Bucket:</label>
            <input type="text" name="source_bucket" class="w-full border p-2 rounded mb-4" required>

            <label class="block font-semibold mb-1">Replication JSON:</label>
            <textarea name="replication_json" class="w-full border p-2 rounded mb-4" rows="10" required placeholder='{
    "Role": "your-role",
    "Rules": [
        {
            "ID": "replicate-example",
            "Priority": 1,
            "Status": "Enabled",
            "Filter": {"Prefix": "example/"},
            "Destination": {"Bucket": "dest-bucket"}
        }
    ]
}'></textarea>

            <button type="submit" class="bg-blue-500 text-white px-4 py-2 rounded hover:bg-blue-600">Apply Replication</button>
        </form>
    </div>
</body>
</html>
"""

@app.route("/", methods=["GET"])
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route("/apply", methods=["POST"])
def apply_replication():
    source_bucket = request.form.get("source_bucket")
    replication_json = request.form.get("replication_json")

    try:
        replication_config = json.loads(replication_json)
    except json.JSONDecodeError as e:
        flash(f"Invalid JSON: {e}")
        return redirect(url_for('index'))

    s3_client = get_s3_client()
    try:
        s3_client.put_bucket_replication(
            Bucket=source_bucket,
            ReplicationConfiguration=replication_config
        )
        flash(f"Replication for bucket '{source_bucket}' applied successfully!")
    except Exception as e:
        flash(f"Error applying replication: {e}")

    return redirect(url_for('index'))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
