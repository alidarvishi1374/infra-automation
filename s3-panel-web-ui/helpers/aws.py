import boto3, json
from urllib.parse import urlparse
from botocore.exceptions import NoCredentialsError, PartialCredentialsError, ClientError
from flask import session

def is_valid_url(url):
    try:
        result = urlparse(url)
        return all([result.scheme in ("http", "https"), result.netloc])
    except:
        return False


def check_credentials(access_key=None, secret_key=None, endpoint_url=None, region_name=""):
    if endpoint_url and not is_valid_url(endpoint_url):
        return False, "Endpoint URL is invalid!, please use http or https"

    try:
        boto_sess = boto3.Session(
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
        ) if access_key and secret_key else boto3.Session()

        iam = boto_sess.client("iam", endpoint_url=endpoint_url, region_name=region_name)

        resp = iam.get_user()
        user = resp.get("User", {})
        return True, {
            "UserName": user.get("UserName"),
            "UserId": user.get("UserId"),
            "Arn": user.get("Arn"),
        }

    except NoCredentialsError:
        return False, "AWS credentials not found!"
    except PartialCredentialsError:
        return False, "Incomplete AWS credentials!"
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code")
        msg = e.response.get("Error", {}).get("Message", "Invalid AWS credentials or insufficient permissions.")
        if code == "AccessDenied":
            return False, "AccessDenied: Invalid AWS credentials or insufficient permissions"
        return False, msg
    except Exception as e:
        return False, f"Unexpected error: {str(e)}"


def get_s3_client():
    return boto3.client(
        "s3",
        aws_access_key_id=session.get("access_key"),
        aws_secret_access_key=session.get("secret_key"),
        endpoint_url=session.get("endpoint_url")
    )


def get_buckets_info():
    if session.get("buckets_info"):
        return session["buckets_info"]

    s3_client = get_s3_client()
    buckets_info = []
    response = s3_client.list_buckets()

    for bucket in response["Buckets"]:
        bucket_name = bucket["Name"]
        total_size = 0

        paginator = s3_client.get_paginator('list_objects_v2')
        for page in paginator.paginate(Bucket=bucket_name):
            if "Contents" in page:
                total_size += sum(obj["Size"] for obj in page["Contents"])

        bucket_data = {
            "Name": bucket_name,
            "CreationDate": bucket["CreationDate"].isoformat(),
            "Owner": response.get("Owner", {}).get("ID"),
            "Size": float(f"{total_size / (1024 * 1024):.3f}")
        }

        # Region
        try:
            location = s3_client.get_bucket_location(Bucket=bucket_name)
            bucket_data["Region"] = location.get("LocationConstraint")
        except:
            bucket_data["Region"] = None

        # Policy
        try:
            policy = s3_client.get_bucket_policy(Bucket=bucket_name)
            bucket_data["Policy"] = json.loads(policy["Policy"])
        except:
            bucket_data["Policy"] = None

        # ACL
        try:
            acl = s3_client.get_bucket_acl(Bucket=bucket_name)
            bucket_data["ACL"] = acl["Grants"][0]["Permission"]
        except:
            bucket_data["ACL"] = None

        # Tags
        try:
            tags = s3_client.get_bucket_tagging(Bucket=bucket_name)
            bucket_data["Tags"] = tags.get("TagSet", [])
        except:
            bucket_data["Tags"] = []

        # Versioning + MFA
        try:
            versioning = s3_client.get_bucket_versioning(Bucket=bucket_name)
            bucket_data["Versioning"] = versioning.get("Status") == "Enabled"
            bucket_data["MFADelete"] = versioning.get("MFADelete") == "Enabled"
        except:
            bucket_data["Versioning"] = False
            bucket_data["MFADelete"] = False

        # Replication
        try:
            replication = s3_client.get_bucket_replication(Bucket=bucket_name)
            bucket_data["Replication"] = replication.get("ReplicationConfiguration", {})
        except:
            bucket_data["Replication"] = None
        
        # Lifecycle

        try:
            lifecycle = s3_client.get_bucket_lifecycle_configuration(Bucket=bucket_name)
            bucket_data["Lifecycle"] = lifecycle.get("Rules", [])
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code")
            if code in ("NoSuchLifecycleConfiguration", "404"):
                bucket_data["Lifecycle"] = []
            else:
                bucket_data["Lifecycle"] = []

        buckets_info.append(bucket_data)

    session["buckets_info"] = buckets_info
    return buckets_info


def get_user_type(access_key, secret_key, endpoint_url, region_name=""):
    iam_client = boto3.client(
        "iam",
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        endpoint_url=endpoint_url,
        region_name=region_name
    )
    try:
        response = iam_client.get_user()
        user = response['User']
        arn = user.get('Arn', '')
        return {
            "type": "Root Account" if ":root" in arn else "IAM User",
            "UserName": user.get('UserName'),
            "UserId": user.get('UserId'),
            "Arn": arn,
            "CreateDate": str(user.get('CreateDate'))
        }
    except ClientError as e:
        code = e.response['Error']['Code']
        if code == "MethodNotAllowed":
            return {"type": "System User"}
        elif code == "AccessDenied":
            return {"type": "IAM User"}
        return {"type": "Unknown", "error": str(e)}


def list_iam_users(access_key_id, secret_access_key, endpoint_url, session_token=None):
    users_info = []
    try:
        client = boto3.client(
            "iam",
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            aws_session_token=session_token,
            endpoint_url=endpoint_url,
            region_name="us-east-1"
        )

        paginator = client.get_paginator("list_users")
        for page in paginator.paginate():
            for u in page.get("Users", []):
                username = u.get("UserName")
                arn = u.get("Arn")
                created = u.get("CreateDate")

                try:
                    groups_resp = client.list_groups_for_user(UserName=username)
                    groups = [g["GroupName"] for g in groups_resp.get("Groups", [])]
                except ClientError:
                    groups = []

                users_info.append({
                    "UserName": username,
                    "Arn": arn,
                    "Created": str(created),
                    "Groups": groups if groups else ["No Groups"]
                })

    except NoCredentialsError:
        return [{"Error": "Credentials not found or invalid."}]
    except ClientError as e:
        return [{"Error": f"AWS client error: {str(e)}"}]

    return users_info


def create_iam_user(endpoint, access_key, secret_key, user_name, region=None):
    session = boto3.session.Session(
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=region
    )

    iam = session.client("iam", endpoint_url=endpoint)

    try:
        response = iam.create_user(UserName=user_name)

        return {
            "success": True,
            "message": f"✅ User '{user_name}' created successfully!",
            "user": response.get("User", {}),
        }

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_message = e.response["Error"]["Message"]

        return {
            "success": False,
            "message": f"❌ {error_code}: {error_message}"
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"❌ Unexpected error: {str(e)}"
        }

def _iam_client(access_key, secret_key, endpoint_url, region="us-east-1"):
    """Internal helper to create IAM client"""
    return boto3.client(
        "iam",
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        endpoint_url=endpoint_url,
        region_name=region
    )

def list_access_keys(access_key, secret_key, endpoint_url, username, region="us-east-1"):
    """List all access keys for a given IAM user"""
    iam = _iam_client(access_key, secret_key, endpoint_url, region)
    try:
        resp = iam.list_access_keys(UserName=username)
        return {"success": True, "keys": resp.get("AccessKeyMetadata", [])}
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code == "NoSuchEntity":
            return {"success": False, "message": f"User '{username}' does not exist."}
        return {"success": False, "message": str(e)}

def create_access_key(access_key, secret_key, endpoint_url, username, region="us-east-1"):
    """Create a new access key for IAM user (up to 2 active keys allowed)"""
    iam = _iam_client(access_key, secret_key, endpoint_url, region)
    try:
        # check how many active keys already exist
        existing = iam.list_access_keys(UserName=username).get("AccessKeyMetadata", [])
        active_keys = [k for k in existing if k.get("Status") == "Active"]

        if len(active_keys) >= 2:
            return {
                "success": False,
                "message": f"User '{username}' already has 2 active access keys. Please delete or deactivate one first."
            }

        new_key = iam.create_access_key(UserName=username)
        return {
            "success": True,
            "message": f"Access key created successfully for user '{username}'.",
            "AccessKeyId": new_key["AccessKey"]["AccessKeyId"],
            "SecretAccessKey": new_key["AccessKey"]["SecretAccessKey"],
            "CreateDate": str(new_key["AccessKey"]["CreateDate"])
        }
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code == "NoSuchEntity":
            return {"success": False, "message": f"User '{username}' does not exist."}
        return {"success": False, "message": str(e)}

def disable_access_key(access_key, secret_key, endpoint_url, username, key_id, region="us-east-1"):
    """Disable (deactivate) an access key"""
    iam = _iam_client(access_key, secret_key, endpoint_url, region)
    try:
        iam.update_access_key(UserName=username, AccessKeyId=key_id, Status="Inactive")
        return {"success": True, "message": f"AccessKey '{key_id}' disabled for user '{username}'."}
    except ClientError as e:
        return {"success": False, "message": str(e)}

def delete_access_key(access_key, secret_key, endpoint_url, username, key_id, region="us-east-1"):
    """Delete an access key"""
    iam = _iam_client(access_key, secret_key, endpoint_url, region)
    try:
        iam.delete_access_key(UserName=username, AccessKeyId=key_id)
        return {"success": True, "message": f"AccessKey '{key_id}' deleted for user '{username}'."}
    except ClientError as e:
        return {"success": False, "message": str(e)}

def delete_iam_user(endpoint, access_key, secret_key, user_name, region="us-east-1"):
    """Delete an IAM user"""
    iam = boto3.client(
        "iam",
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        endpoint_url=endpoint,
        region_name=region
    )
    try:
        iam.delete_user(UserName=user_name)
        return {
            "success": True,
            "message": f"✅ User '{user_name}' deleted successfully!"
        }
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_message = e.response["Error"]["Message"]
        return {
            "success": False,
            "message": f"❌ {error_code}: {error_message}"
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"❌ Unexpected error: {str(e)}"
        }

def create_bucket(endpoint, access_key, secret_key, bucket_name, region="us-east-1", enable_locking=False):
    """
    Create a new S3 bucket with optional Object Lock enabled.
    
    :param endpoint: S3 endpoint URL
    :param access_key: AWS access key
    :param secret_key: AWS secret key
    :param bucket_name: Name of the bucket to create
    :param region: Bucket region (default: us-east-1)
    :param enable_locking: If True, enables Object Lock on bucket creation
    :return: dict with success status and message
    """
    s3 = boto3.client(
        "s3",
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        endpoint_url=endpoint,
        region_name=region
    )

    try:
        # Pre-check: verify bucket doesn't already exist
        try:
            s3.head_bucket(Bucket=bucket_name)
            return {
                "success": False,
                "message": f"❌ Bucket '{bucket_name}' already exists."
            }
        except ClientError as e:
            if e.response["Error"]["Code"] not in ["404", "NoSuchBucket"]:
                return {"success": False, "message": f"❌ Pre-check failed: {e}"}

        # Create bucket with optional Object Lock
        if region in [None, "", "us-east-1", "default"]:
            if enable_locking:
                response = s3.create_bucket(
                    Bucket=bucket_name,
                    ObjectLockEnabledForBucket=True
                )
            else:
                response = s3.create_bucket(Bucket=bucket_name)
        else:
            if enable_locking:
                response = s3.create_bucket(
                    Bucket=bucket_name,
                    CreateBucketConfiguration={"LocationConstraint": region},
                    ObjectLockEnabledForBucket=True
                )
            else:
                response = s3.create_bucket(
                    Bucket=bucket_name,
                    CreateBucketConfiguration={"LocationConstraint": region}
                )

        status_code = response.get("ResponseMetadata", {}).get("HTTPStatusCode")
        if status_code == 200:
            msg = f"✅ Bucket '{bucket_name}' created successfully!"
            if enable_locking:
                msg += " Object Locking is enabled."
            return {"success": True, "message": msg}

        return {
            "success": False,
            "message": f"❌ Failed to create bucket '{bucket_name}' (HTTP {status_code})."
        }

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_message = e.response["Error"]["Message"]
        return {"success": False, "message": f"❌ {error_code}: {error_message}"}
    except Exception as e:
        return {"success": False, "message": f"❌ Unexpected error: {str(e)}"}


def get_iam_client(access_key=None, secret_key=None, endpoint_url=None, region_name="us-east-1"):
    """Return a boto3 IAM client, using given credentials or default ones."""
    return boto3.client(
        "iam",
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        endpoint_url=endpoint_url,
        region_name=region_name
    )

