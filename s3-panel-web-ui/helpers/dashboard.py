# helpers/dashboard.py
import boto3, sqlite3, pandas as pd, threading, time, json
from botocore.client import Config
from datetime import datetime, timedelta
from flask import session

DB_FILE = "bucket_history.db"

# S3 client
def get_s3_client():
    return boto3.client(
        "s3",
        aws_access_key_id=session.get("access_key"),
        aws_secret_access_key=session.get("secret_key"),
        endpoint_url=session.get("endpoint_url"),
        config=Config(signature_version="s3v4"),
        region_name="us-east-1"
    )

# ======================
# DB init
# ======================
def init_db():
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
init_db()

# ======================
# Bucket & rate funcs
# ======================
def get_bucket_size(bucket_name):
    s3 = get_s3_client()
    total_size = 0
    continuation_token = None
    while True:
        if continuation_token:
            response = s3.list_objects_v2(Bucket=bucket_name, ContinuationToken=continuation_token)
        else:
            response = s3.list_objects_v2(Bucket=bucket_name)
        for obj in response.get("Contents", []):
            total_size += obj["Size"]
        if response.get("IsTruncated"):
            continuation_token = response["NextContinuationToken"]
        else:
            break
    return total_size

def get_bucket_data(search_filter=""):
    s3 = get_s3_client()
    all_buckets = s3.list_buckets()["Buckets"]
    bucket_sizes = []
    for bucket in all_buckets:
        name = bucket["Name"]
        if not search_filter or search_filter.lower() in name.lower():
            size_bytes = get_bucket_size(name)
            size_gb = size_bytes / (1024**3)
            bucket_sizes.append({"Bucket": name, "Size_Bytes": size_bytes, "Size_GB": size_gb})
    if not search_filter:
        bucket_sizes.sort(key=lambda x: x["Size_Bytes"], reverse=True)
        bucket_sizes = bucket_sizes[:5]
    return bucket_sizes

def update_database():
    s3 = get_s3_client()
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    now = datetime.now()
    for bucket in s3.list_buckets()["Buckets"]:
        name = bucket["Name"]
        size_gb = get_bucket_size(name) / (1024**3)
        cursor.execute("INSERT INTO bucket_history (time, bucket, size_gb) VALUES (?, ?, ?)", (now, name, size_gb))
    cursor.execute("DELETE FROM bucket_history WHERE time < ?", (now - timedelta(days=7),))
    conn.commit()
    conn.close()

def get_rate_data(start_dt, end_dt, search_filter=""):
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    if search_filter:
        hist = pd.read_sql_query(
            "SELECT * FROM bucket_history WHERE time BETWEEN ? AND ? AND bucket LIKE ? ORDER BY time",
            conn, parse_dates=["time"], params=[start_dt, end_dt, f"%{search_filter}%"]
        )
    else:
        hist = pd.read_sql_query(
            "SELECT * FROM bucket_history WHERE time BETWEEN ? AND ? ORDER BY time",
            conn, parse_dates=["time"], params=[start_dt, end_dt]
        )
    conn.close()
    if hist.empty:
        return []
    hist = hist.sort_values(["bucket","time"]).reset_index(drop=True)
    hist["Rate_MB_min"] = hist.groupby("bucket")["size_gb"].diff() * 1024
    hist["Rate_MB_min"] = hist["Rate_MB_min"].fillna(0)
    return hist.to_dict("records")

# Background thread
def start_background_thread():
    def loop():
        while True:
            try:
                update_database()
                time.sleep(30)
            except Exception as e:
                print(f"Background thread error: {e}")
                time.sleep(30)
    t = threading.Thread(target=loop, daemon=True)
    t.start()
start_background_thread()
