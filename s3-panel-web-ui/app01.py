from flask import Flask, render_template, request, jsonify
import boto3
import pandas as pd
import plotly.express as px
import plotly.utils
import json
from datetime import datetime, timedelta
from botocore.client import Config
import sqlite3
import threading
import time

app = Flask(__name__)

# ======================
# Connection details
# ======================
ACCESS_KEY = "BTTREFVTW2CVI837BXAL"
SECRET_KEY = "Mk5SLqCyCpIIZ0IAq6NNqK4tucXLAVCS7jWdwS0T"
ENDPOINT = "http://192.168.112.113"

# Initialize S3 client
try:
    s3 = boto3.client(
        "s3",
        endpoint_url=ENDPOINT,
        aws_access_key_id=ACCESS_KEY,
        aws_secret_access_key=SECRET_KEY,
        config=Config(signature_version="s3v4"),
        region_name="us-east-1"
    )
    # Test connection
    s3.list_buckets()
    print("S3 connection successful")
except Exception as e:
    print(f"S3 connection error: {e}")
    s3 = None

DB_FILE = "bucket_history.db"

# ======================
# SQLite setup
# ======================
def init_db():
    try:
        conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS bucket_history (
            time TIMESTAMP,
            bucket TEXT,
            size_gb REAL
        )
        """)
        conn.commit()
        conn.close()
        print("Database initialized successfully")
    except Exception as e:
        print(f"Database initialization error: {e}")

init_db()

# ======================
# Function to calculate bucket size
# ======================
def get_bucket_size(bucket_name):
    if not s3:
        return 0
        
    total_size = 0
    continuation_token = None
    try:
        while True:
            if continuation_token:
                response = s3.list_objects_v2(Bucket=bucket_name, ContinuationToken=continuation_token)
            else:
                response = s3.list_objects_v2(Bucket=bucket_name)

            if "Contents" in response:
                for obj in response.get("Contents", []):
                    total_size += obj["Size"]

            if response.get("IsTruncated"):
                continuation_token = response["NextContinuationToken"]
            else:
                break
    except Exception as e:
        print(f"Error getting size for bucket {bucket_name}: {e}")
    return total_size

# ======================
# Fetch bucket data
# ======================
def get_bucket_data(search_filter=""):
    if not s3:
        return []
        
    try:
        all_buckets = s3.list_buckets()["Buckets"]
        bucket_sizes = []
        
        for bucket in all_buckets:
            bucket_name = bucket["Name"]
            if not search_filter or search_filter.lower() in bucket_name.lower():
                size_bytes = get_bucket_size(bucket_name)
                size_gb = size_bytes / (1024**3)
                bucket_sizes.append({
                    "Bucket": bucket_name,
                    "Size_Bytes": size_bytes,
                    "Size_GB": size_gb
                })
        
        # Sort by size and limit to top 5 if no search filter
        if not search_filter:
            bucket_sizes.sort(key=lambda x: x["Size_Bytes"], reverse=True)
            bucket_sizes = bucket_sizes[:5]
        
        return bucket_sizes
    except Exception as e:
        print(f"Error fetching bucket data: {e}")
        return []

# ======================
# Update database with current data
# ======================
def update_database():
    if not s3:
        return
        
    try:
        conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        cursor = conn.cursor()
        
        all_buckets = s3.list_buckets()["Buckets"]
        now = datetime.now()
        
        for bucket in all_buckets:
            bucket_name = bucket["Name"]
            size_bytes = get_bucket_size(bucket_name)
            size_gb = size_bytes / (1024**3)
            
            cursor.execute(
                "INSERT INTO bucket_history (time, bucket, size_gb) VALUES (?, ?, ?)",
                (now, bucket_name, size_gb)
            )
        
        # Remove records older than 7 days
        cursor.execute("DELETE FROM bucket_history WHERE time < ?", (now - timedelta(days=7),))
        conn.commit()
        conn.close()
        print(f"Database updated at {now}")
    except Exception as e:
        print(f"Error updating database: {e}")

# ======================
# Get rate data
# ======================
def get_rate_data(start_dt, end_dt, search_filter=""):
    try:
        conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        
        if search_filter:
            query = "SELECT * FROM bucket_history WHERE time BETWEEN ? AND ? AND bucket LIKE ? ORDER BY time"
            params = [start_dt, end_dt, f"%{search_filter}%"]
        else:
            query = "SELECT * FROM bucket_history WHERE time BETWEEN ? AND ? ORDER BY time"
            params = [start_dt, end_dt]
        
        hist = pd.read_sql_query(query, conn, parse_dates=["time"], params=params)
        conn.close()
        
        if hist.empty:
            return []
        
        # Calculate rate
        hist = hist.sort_values(["bucket", "time"]).reset_index(drop=True)
        hist["Rate_MB_min"] = hist.groupby("bucket")["size_gb"].diff() * 1024
        hist["Rate_MB_min"] = hist["Rate_MB_min"].fillna(0)
        
        # Convert to list of dictionaries
        result = []
        for _, row in hist.iterrows():
            result.append({
                "time": row["time"].strftime("%Y-%m-%d %H:%M:%S"),
                "bucket": row["bucket"],
                "size_gb": row["size_gb"],
                "Rate_MB_min": row["Rate_MB_min"]
            })
        
        return result
    except Exception as e:
        print(f"Error getting rate data: {e}")
        return []

# ======================
# Routes
# ======================
@app.route('/', methods=['POST'])
def index():
    return render_template('dashboard.html')

@app.route('/api/bucket_data', methods=['GET'])
def api_bucket_data():
    search_filter = request.args.get('search', '').strip()
    bucket_data = get_bucket_data(search_filter)
    return jsonify(bucket_data)

@app.route('/api/rate_data', methods=['GET'])
def api_rate_data():
    try:
        start_date = request.args.get('start_date')
        start_time = request.args.get('start_time')
        end_date = request.args.get('end_date')
        end_time = request.args.get('end_time')
        search_filter = request.args.get('search', '').strip()
        
        if not all([start_date, start_time, end_date, end_time]):
            return jsonify({"error": "All datetime parameters are required"}), 400
        
        start_dt = datetime.strptime(f"{start_date} {start_time}", "%Y-%m-%d %H:%M")
        end_dt = datetime.strptime(f"{end_date} {end_time}", "%Y-%m-%d %H:%M")
        
        rate_data = get_rate_data(start_dt, end_dt, search_filter)
        return jsonify(rate_data)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/api/update_database', methods=['GET'])
def api_update_database():
    update_database()
    return jsonify({"status": "success"})

# ======================
# Background auto-update
# ======================
def background_update():
    while True:
        try:
            update_database()
            time.sleep(30)  # Update every 30 seconds
        except Exception as e:
            print(f"Background update error: {e}")
            time.sleep(30)

# Start background thread
if s3:
    update_thread = threading.Thread(target=background_update, daemon=True)
    update_thread.start()
    print("Background update thread started")
else:
    print("S3 not available, background update disabled")

@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Endpoint not found"}), 404

@app.errorhandler(405)
def method_not_allowed(e):
    return jsonify({"error": "Method not allowed"}), 405

@app.errorhandler(500)
def internal_error(e):
    return jsonify({"error": "Internal server error"}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)