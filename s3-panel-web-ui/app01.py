from flask import Flask, render_template, request
import boto3
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from botocore.client import Config
import sqlite3
import os

# ======================
# Flask setup
# ======================
app = Flask(__name__)

# ======================
# S3 Connection
# ======================
ACCESS_KEY = "BTTREFVTW2CVI837BXAL"
SECRET_KEY = "Mk5SLqCyCpIIZ0IAq6NNqK4tucXLAVCS7jWdwS0T"
ENDPOINT = "http://192.168.112.113"

s3 = boto3.client(
    "s3",
    endpoint_url=ENDPOINT,
    aws_access_key_id=ACCESS_KEY,
    aws_secret_access_key=SECRET_KEY,
    config=Config(signature_version="s3v4"),
    region_name="us-east-1"
)

DB_FILE = "bucket_history.db"

# ======================
# SQLite setup
# ======================
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

# ======================
# Function to calculate bucket size
# ======================
def get_bucket_size(bucket_name):
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

# ======================
# Update DB with current bucket sizes
# ======================
def update_bucket_history():
    all_buckets = s3.list_buckets()["Buckets"]
    bucket_sizes = [(b["Name"], get_bucket_size(b["Name"])) for b in all_buckets]
    df_all = pd.DataFrame(bucket_sizes, columns=["Bucket", "Size (Bytes)"])
    df_all["Size (GB)"] = df_all["Size (Bytes)"] / (1024**3)

    now = datetime.now()
    for _, row in df_all.iterrows():
        cursor.execute(
            "INSERT INTO bucket_history (time, bucket, size_gb) VALUES (?, ?, ?)",
            (now, row["Bucket"], row["Size (GB)"])
        )
    conn.commit()
    cursor.execute("DELETE FROM bucket_history WHERE time < ?", (now - timedelta(days=7),))
    conn.commit()
    return df_all

# ======================
# Flask routes
# ======================
@app.route("/", methods=["GET", "POST"])
def dashboard():
    df_all = update_bucket_history()
    hist = pd.read_sql_query("SELECT * FROM bucket_history", conn, parse_dates=["time"])

    # Default values
    now = datetime.now()
    default_start = now - timedelta(hours=1)
    default_end = now
    search_bucket = ""
    start_dt = default_start
    end_dt = default_end

    if request.method == "POST":
        start_date = request.form.get("start_date")
        start_time = request.form.get("start_time")
        end_date = request.form.get("end_date")
        end_time = request.form.get("end_time")
        search_bucket = request.form.get("search_bucket", "")

        start_dt = datetime.strptime(f"{start_date} {start_time}", "%Y-%m-%d %H:%M")
        end_dt = datetime.strptime(f"{end_date} {end_time}", "%Y-%m-%d %H:%M")
        if end_dt < start_dt:
            end_dt = start_dt + timedelta(hours=1)

    # Filter data for charts
    if search_bucket:
        df = df_all[df_all["Bucket"].str.contains(search_bucket, case=False, na=False)].reset_index(drop=True)
    else:
        df = df_all.sort_values("Size (Bytes)", ascending=False).head(5).reset_index(drop=True)

    hist_rate = hist[(hist["time"] >= start_dt) & (hist["time"] <= end_dt)].copy()
    if search_bucket:
        hist_rate = hist_rate[hist_rate["bucket"].str.contains(search_bucket, case=False, na=False)]

    # Calculate ingestion rate (MB/min)
    hist_rate = hist_rate.sort_values(["bucket", "time"]).reset_index(drop=True)
    hist_rate["Rate (MB/min)"] = hist_rate.groupby("bucket")["size_gb"].diff() * 1024
    hist_rate["Rate (MB/min)"] = hist_rate["Rate (MB/min)"].fillna(0)

    # ======================
    # Create charts
    # ======================
    fig_bar = px.bar(df, x="Bucket", y="Size (GB)", color="Bucket", text_auto=".2f",
                    title="Bucket Sizes (Bar Chart)", template="plotly_dark")
    fig_bar.update_layout(
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(showgrid=True, gridcolor="gray"),
        yaxis=dict(showgrid=True, gridcolor="gray")
    )
    fig_bar.update_traces(marker_line_width=1.5, marker_line_color="white", selector=dict(type="bar"))

    fig_pie = px.pie(df, names="Bucket", values="Size (GB)", hole=0.4,
                    title="Bucket Sizes (Pie Chart)", template="plotly_dark",
                    color_discrete_sequence=px.colors.qualitative.Vivid)

    fig_rate = px.line(hist_rate, x="time", y="Rate (MB/min)", color="bucket", markers=True,
                    title=f"Bucket Ingestion Rate ({start_dt.strftime('%Y-%m-%d %H:%M')} to {end_dt.strftime('%Y-%m-%d %H:%M')})",
                    template="plotly_dark")
    fig_rate.update_traces(mode='lines+markers', line=dict(width=3), marker=dict(size=8))
    # Convert plots to HTML
    bar_html = fig_bar.to_html(full_html=False)
    pie_html = fig_pie.to_html(full_html=False)
    rate_html = fig_rate.to_html(full_html=False)

    return render_template("dashboard.html",
                           bar_html=bar_html,
                           pie_html=pie_html,
                           rate_html=rate_html,
                           search_bucket=search_bucket,
                           start_dt=start_dt,
                           end_dt=end_dt)

# ======================
# Run app
# ======================
if __name__ == "__main__":
    # Make sure templates folder exists
    if not os.path.exists("templates"):
        os.mkdir("templates")
    app.run(debug=True)
