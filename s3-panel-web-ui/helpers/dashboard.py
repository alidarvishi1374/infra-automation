# helpers/dashboard.py
import boto3
import os
from botocore.client import Config
from flask import session

def get_s3_client(access_key=None, secret_key=None, endpoint_url=None):

    if access_key is None:
        try:
            access_key = session.get("access_key")
            secret_key = session.get("secret_key")
            endpoint_url = session.get("endpoint_url")
        except RuntimeError:
            access_key = os.getenv('AWS_ACCESS_KEY_ID')
            secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
            endpoint_url = os.getenv('AWS_ENDPOINT_URL')
    
    if not access_key or not secret_key:
        raise ValueError("AWS credentials not available")
    
    return boto3.client(
        "s3",
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        endpoint_url=endpoint_url,
        config=Config(signature_version="s3v4"),
        region_name="us-east-1"
    )

def get_bucket_size_and_count(bucket_name, access_key=None, secret_key=None, endpoint_url=None):
    s3 = get_s3_client(access_key, secret_key, endpoint_url)
    total_size = 0
    total_objects = 0
    continuation_token = None
    
    try:
        while True:
            list_params = {'Bucket': bucket_name}
            if continuation_token:
                list_params['ContinuationToken'] = continuation_token
            
            response = s3.list_objects_v2(**list_params)
            
            if 'Contents' in response:
                for obj in response['Contents']:
                    total_size += obj.get("Size", 0)
                    total_objects += 1
            
            if response.get("IsTruncated"):
                continuation_token = response["NextContinuationToken"]
            else:
                break
                
    except Exception as e:
        print(f"Error processing bucket {bucket_name}: {e}")
    
    return total_size, total_objects

def get_bucket_data(search_filter=""):
    try:
        s3 = get_s3_client()
        all_buckets = s3.list_buckets().get("Buckets", [])
        bucket_data = []
        
        for bucket in all_buckets:
            name = bucket["Name"]
            
            if search_filter and search_filter.lower() not in name.lower():
                continue
                
            size_bytes, object_count = get_bucket_size_and_count(name)
            size_gb = size_bytes / (1024 ** 3)
            
            bucket_data.append({
                "Bucket": name, 
                "Size_Bytes": size_bytes, 
                "Size_GB": round(size_gb, 2),
                "Object_Count": object_count
            })
        
        if not search_filter:
            bucket_data.sort(key=lambda x: x["Size_Bytes"], reverse=True)
            bucket_data = bucket_data[:5]
            
        return bucket_data
        
    except Exception as e:
        print(f"Error in get_bucket_data: {e}")
        return []

def get_all_buckets_stats():
    try:
        s3 = get_s3_client()
        all_buckets = s3.list_buckets().get("Buckets", [])
        bucket_data = []
        
        for bucket in all_buckets:
            name = bucket["Name"]
            size_bytes, object_count = get_bucket_size_and_count(name)
            size_gb = size_bytes / (1024 ** 3)
            
            bucket_data.append({
                "Bucket": name, 
                "Size_Bytes": size_bytes, 
                "Size_GB": round(size_gb, 2),
                "Object_Count": object_count
            })
            
        return bucket_data
        
    except Exception as e:
        print(f"Error in get_all_buckets_stats: {e}")
        return []
    
def get_object_count_data(search_filter=""):
    bucket_data = get_bucket_data(search_filter)
    object_count_data = []
    for bucket in bucket_data:
        object_count_data.append({
            "Bucket": bucket["Bucket"],
            "Object_Count": bucket["Object_Count"]
        })
    
    return object_count_data

