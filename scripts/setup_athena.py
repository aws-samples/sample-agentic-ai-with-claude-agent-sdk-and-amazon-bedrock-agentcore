#!/usr/bin/env python3
"""
Setup script to create Athena database and tables.
Uploads demo CSV data to S3 and creates Athena tables.
"""

import boto3
import os
from pathlib import Path
import argparse


def upload_data_to_s3(data_dir: Path, bucket_name: str, prefix: str):
    """Upload CSV files to S3."""
    s3_client = boto3.client('s3')

    csv_files = list(data_dir.glob('*.csv'))
    print(f"Uploading {len(csv_files)} CSV files to s3://{bucket_name}/{prefix}/")

    for csv_file in csv_files:
        s3_key = f"{prefix}/data/{csv_file.stem}/{csv_file.name}"
        print(f"  Uploading {csv_file.name} → s3://{bucket_name}/{s3_key}")
        s3_client.upload_file(str(csv_file), bucket_name, s3_key)

    print("Upload complete!\n")


def create_athena_database(database_name: str, bucket_name: str, region: str):
    """Create Athena database."""
    athena_client = boto3.client('athena', region_name=region)

    query = f"CREATE DATABASE IF NOT EXISTS {database_name}"

    print(f"Creating database: {database_name}")
    response = athena_client.start_query_execution(
        QueryString=query,
        ResultConfiguration={
            'OutputLocation': f's3://{bucket_name}/athena-results/'
        }
    )

    query_execution_id = response['QueryExecutionId']

    # Wait for query to complete
    import time
    while True:
        status_response = athena_client.get_query_execution(
            QueryExecutionId=query_execution_id
        )
        status = status_response['QueryExecution']['Status']['State']

        if status in ['SUCCEEDED', 'FAILED', 'CANCELLED']:
            break
        time.sleep(1)

    if status == 'SUCCEEDED':
        print(f"✓ Database {database_name} created successfully\n")
    else:
        print(f"✗ Database creation failed: {status}\n")


def create_table(
    table_name: str,
    columns: str,
    database_name: str,
    bucket_name: str,
    prefix: str,
    region: str
):
    """Create an Athena table from S3 CSV data."""
    athena_client = boto3.client('athena', region_name=region)

    s3_location = f"s3://{bucket_name}/{prefix}/data/{table_name}/"

    query = f"""
    CREATE EXTERNAL TABLE IF NOT EXISTS {database_name}.{table_name} (
        {columns}
    )
    ROW FORMAT DELIMITED
    FIELDS TERMINATED BY ','
    STORED AS TEXTFILE
    LOCATION '{s3_location}'
    TBLPROPERTIES ('skip.header.line.count'='1')
    """

    print(f"Creating table: {table_name}")
    response = athena_client.start_query_execution(
        QueryString=query,
        QueryExecutionContext={'Database': database_name},
        ResultConfiguration={
            'OutputLocation': f's3://{bucket_name}/athena-results/'
        }
    )

    query_execution_id = response['QueryExecutionId']

    # Wait for query to complete
    import time
    while True:
        status_response = athena_client.get_query_execution(
            QueryExecutionId=query_execution_id
        )
        status = status_response['QueryExecution']['Status']['State']

        if status in ['SUCCEEDED', 'FAILED', 'CANCELLED']:
            break
        time.sleep(1)

    if status == 'SUCCEEDED':
        print(f"  ✓ Table {table_name} created")
    else:
        error = status_response['QueryExecution']['Status'].get('StateChangeReason', 'Unknown error')
        print(f"  ✗ Table creation failed: {error}")


def create_all_tables(database_name: str, bucket_name: str, prefix: str, region: str):
    """Create all denormalized student analytics tables."""
    print("Creating denormalized Athena tables...\n")

    # Define denormalized table schemas
    tables = {
        'student_enrollment_analytics': """
            student_id STRING,
            student_first_name STRING,
            student_last_name STRING,
            student_email STRING,
            student_major STRING,
            student_gpa DOUBLE,
            student_status STRING,
            student_department_id INT,
            student_department_name STRING,
            student_dean_name STRING,
            student_building_name STRING,
            student_enrollment_id STRING,
            student_enrollment_date STRING,
            student_enrollment_status STRING,
            enrollment_year INT,
            enrollment_month INT,
            enrollment_quarter INT,
            course_id STRING,
            course_code STRING,
            course_name STRING,
            course_credits INT,
            course_type STRING,
            course_semester STRING,
            course_max_enrollment INT,
            course_room_number STRING,
            course_instructor_id INT,
            course_instructor_first_name STRING,
            course_instructor_last_name STRING,
            course_instructor_rank STRING,
            course_instructor_email STRING
        """,

        'financial_summary_by_student': """
            student_id STRING,
            student_first_name STRING,
            student_last_name STRING,
            student_email STRING,
            student_major STRING,
            student_status STRING,
            student_gpa DOUBLE,
            student_enrollment_date STRING,
            student_department_name STRING,
            student_department_id INT,
            total_tuition_due DOUBLE,
            total_tuition_paid DOUBLE,
            outstanding_balance DOUBLE,
            last_payment_date STRING,
            last_payment_amount DOUBLE,
            last_payment_method STRING,
            total_scholarships_received DOUBLE,
            scholarship_count INT,
            merit_scholarships_total DOUBLE,
            need_based_scholarships_total DOUBLE,
            athletic_scholarships_total DOUBLE,
            departmental_scholarships_total DOUBLE,
            net_tuition_after_scholarships DOUBLE,
            scholarship_coverage_rate_pct DOUBLE,
            has_outstanding_balance BOOLEAN,
            is_scholarship_recipient BOOLEAN
        """
    }

    for table_name, columns in tables.items():
        create_table(table_name, columns, database_name, bucket_name, prefix, region)

    print(f"\n✓ All {len(tables)} denormalized tables created successfully!")


def setup_athena(
    bucket: str = None,
    database: str = 'student_analytics',
    prefix: str = 'student-analytics',
    region: str = None,
    data_dir: str = None,
    skip_upload: bool = False
):
    """
    Setup Athena database and tables.

    Can be called directly from Python/Jupyter or via command line.

    Args:
        bucket: S3 bucket name (required, or set S3_BUCKET_NAME env var)
        database: Athena database name (default: student_analytics)
        prefix: S3 prefix for data (default: student-analytics)
        region: AWS region (default: from AWS_REGION env var or us-east-1)
        data_dir: Directory containing CSV files (default: ../data/demo_data)
        skip_upload: Skip S3 upload if data already uploaded
    """
    # Get bucket from env if not provided
    if bucket is None:
        bucket = os.environ.get('S3_BUCKET_NAME')
    if bucket is None or bucket.startswith('YOUR_'):
        raise ValueError("bucket parameter required or set S3_BUCKET_NAME environment variable")

    # Get region from env if not provided
    if region is None:
        region = os.environ.get('AWS_REGION', 'us-west-2')

    # Determine data directory
    if data_dir:
        data_path = Path(data_dir)
    else:
        data_path = Path(__file__).parent.parent / 'data' / 'demo_data'

    if not data_path.exists():
        print(f"Error: Data directory not found: {data_path}")
        return False

    print("=" * 80)
    print("ATHENA SETUP SCRIPT")
    print("=" * 80)
    print(f"Bucket: {bucket}")
    print(f"Database: {database}")
    print(f"Region: {region}")
    print(f"Data Directory: {data_path}")
    print(f"Skip Upload: {skip_upload}")
    print("=" * 80)
    print()

    # Step 1: Upload data to S3 (unless skipped)
    if not skip_upload:
        upload_data_to_s3(data_path, bucket, prefix)
    else:
        print("Skipping S3 upload (data assumed to be already uploaded)\n")

    # Step 2: Create database
    create_athena_database(database, bucket, region)

    # Step 3: Create tables
    create_all_tables(database, bucket, prefix, region)

    print("\n" + "=" * 80)
    print("SETUP COMPLETE!")
    print("=" * 80)
    print(f"\nYou can now query your denormalized analytics data using:")
    print(f"  Database: {database}")
    print(f"  Region: {region}")
    print(f"\nExample queries:")
    print(f"  SELECT COUNT(DISTINCT student_id) FROM {database}.student_enrollment_analytics;")
    print(f"  SELECT * FROM {database}.student_academic_performance WHERE is_honor_roll = true LIMIT 10;")
    print(f"  SELECT student_major, AVG(outstanding_balance) FROM {database}.financial_summary_by_student GROUP BY student_major;")
    print()
    return True


def main():
    parser = argparse.ArgumentParser(description='Setup Athena database and tables')
    parser.add_argument('--bucket', required=True, help='S3 bucket name')
    parser.add_argument('--database', default='student_analytics', help='Athena database name')
    parser.add_argument('--prefix', default='student-analytics', help='S3 prefix for data')
    parser.add_argument('--region', default='us-west-2', help='AWS region')
    parser.add_argument('--data-dir', help='Directory containing CSV files (default: ../data/demo_data)')
    parser.add_argument('--skip-upload', action='store_true', help='Skip S3 upload')

    args = parser.parse_args()

    setup_athena(
        bucket=args.bucket,
        database=args.database,
        prefix=args.prefix,
        region=args.region,
        data_dir=args.data_dir,
        skip_upload=args.skip_upload
    )


if __name__ == '__main__':
    main()
