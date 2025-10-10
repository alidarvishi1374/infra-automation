from flask import Blueprint, render_template, request, jsonify, session
from helpers.auth import login_required
from helpers.aws import get_user_type
import boto3

s3_select_bp = Blueprint("s3_select", __name__)

def get_s3_client():
    return boto3.client(
        "s3",
        aws_access_key_id=session.get("access_key"),
        aws_secret_access_key=session.get("secret_key"),
        endpoint_url=session.get("endpoint_url"),
        region_name="default"
    )

@s3_select_bp.route("/s3_select")
@login_required
def s3_select_page():
    user_info = get_user_type(
        session["access_key"],
        session["secret_key"],
        session["endpoint_url"]
    )
    return render_template("s3_select.html", user_info=user_info)

@s3_select_bp.route("/list-buckets")
@login_required
def list_buckets():
    s3 = get_s3_client()
    try:
        response = s3.list_buckets()
        buckets = [b["Name"] for b in response.get("Buckets", [])]
        return jsonify(buckets)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@s3_select_bp.route("/list-objects")
@login_required
def list_objects():
    bucket = request.args.get("bucket")
    if not bucket:
        return jsonify({"error": "Bucket parameter is required"}), 400

    s3 = get_s3_client()
    try:
        response = s3.list_objects_v2(Bucket=bucket)
        objects = [o["Key"] for o in response.get("Contents", [])]
        return jsonify(objects)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@s3_select_bp.route("/run-query", methods=["POST"])
@login_required
def run_query():
    data = request.json
    bucket = data.get("bucket")
    key = data.get("key")
    expression = data.get("expression")
    delimiter = data.get("delimiter", ",")

    if not bucket or not key or not expression:
        return "Error: bucket, key, and expression are required!", 400

    s3 = get_s3_client()
    try:
        response = s3.select_object_content(
            Bucket=bucket,
            Key=key,
            Expression=expression,
            ExpressionType="SQL",
            InputSerialization={
                "CSV": {
                    "FileHeaderInfo": "USE",
                    "RecordDelimiter": "\n",
                    "FieldDelimiter": delimiter
                },
                "CompressionType": "NONE"
            },
            OutputSerialization={
                "CSV": {
                    "RecordDelimiter": "\n",
                    "FieldDelimiter": delimiter
                }
            }
        )

        output = ""
        for event in response["Payload"]:
            if "Records" in event:
                output += event["Records"]["Payload"].decode("utf-8")

        return output
    except Exception as e:
        return f"Error: {str(e)}", 500
