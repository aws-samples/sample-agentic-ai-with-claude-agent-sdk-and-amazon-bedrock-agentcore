#!/usr/bin/env python3
"""
Setup script to create Athena database and tables.
Uploads demo CSV data to S3 and creates Athena tables.
"""

import boto3
from botocore.config import Config
import os
from pathlib import Path
import argparse


def upload_data_to_s3(data_dir: Path, bucket_name: str, prefix: str):
    """Upload CSV files to S3 using SigV4."""
    # Configure S3 client to use SigV4
    config = Config(signature_version='s3v4')
    s3_client = boto3.client('s3', config=config)

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
            department_name STRING,
            department_id INT,
            total_tuition_paid DOUBLE,
            total_tuition_due DOUBLE,
            outstanding_balance DOUBLE,
            total_payments_count INT,
            completed_payments_count INT,
            pending_payments_count INT,
            failed_payments_count INT,
            last_payment_date STRING,
            last_payment_amount DOUBLE,
            last_payment_method STRING,
            credit_card_payments_total DOUBLE,
            bank_transfer_total DOUBLE,
            check_payments_total DOUBLE,
            financial_aid_total DOUBLE,
            total_scholarships_received DOUBLE,
            scholarship_count INT,
            merit_scholarships_total DOUBLE,
            need_based_scholarships_total DOUBLE,
            athletic_scholarships_total DOUBLE,
            departmental_scholarships_total DOUBLE,
            largest_scholarship_amount DOUBLE,
            latest_scholarship_date STRING,
            net_tuition_after_scholarships DOUBLE,
            scholarship_coverage_rate_pct DOUBLE,
            payment_success_rate_pct DOUBLE,
            avg_payment_amount DOUBLE,
            fall_2024_tuition DOUBLE,
            fall_2024_scholarships DOUBLE,
            spring_2024_tuition DOUBLE,
            spring_2024_scholarships DOUBLE,
            fall_2023_tuition DOUBLE,
            fall_2023_scholarships DOUBLE,
            has_outstanding_balance BOOLEAN,
            is_scholarship_recipient BOOLEAN,
            is_payment_plan_active BOOLEAN,
            is_financial_aid_recipient BOOLEAN
        """,
    }

    for table_name, columns in tables.items():
        create_table(table_name, columns, database_name, bucket_name, prefix, region)

    print(f"\n✓ All {len(tables)} denormalized tables created successfully!")


def main():
    parser = argparse.ArgumentParser(description='Setup Athena database and tables')
    parser.add_argument('--bucket', required=True, help='S3 bucket name')
    parser.add_argument('--database', default='student_analytics', help='Athena database name')
    parser.add_argument('--prefix', default='student-analytics', help='S3 prefix for data')
    parser.add_argument('--region', default='us-east-1', help='AWS region')
    parser.add_argument('--data-dir', help='Directory containing CSV files (default: ../data/demo_data)')

    args = parser.parse_args()

    # Determine data directory
    if args.data_dir:
        data_dir = Path(args.data_dir)
    else:
        data_dir = Path(__file__).parent.parent / 'data' / 'demo_data'

    if not data_dir.exists():
        print(f"Error: Data directory not found: {data_dir}")
        print("Please run generate_denormalized_data.py first to create the CSV files.")
        return

    print("=" * 80)
    print("ATHENA SETUP SCRIPT")
    print("=" * 80)
    print(f"Bucket: {args.bucket}")
    print(f"Database: {args.database}")
    print(f"Region: {args.region}")
    print(f"Data Directory: {data_dir}")
    print("=" * 80)
    print()

    # Step 1: Upload data to S3
    upload_data_to_s3(data_dir, args.bucket, args.prefix)

    # Step 2: Create database
    create_athena_database(args.database, args.bucket, args.region)

    # Step 3: Create tables
    create_all_tables(args.database, args.bucket, args.prefix, args.region)

    print("\n" + "=" * 80)
    print("SETUP COMPLETE!")
    print("=" * 80)
    print(f"\nYou can now query your denormalized analytics data using:")
    print(f"  Database: {args.database}")
    print(f"  Region: {args.region}")
    print(f"\nExample queries:")
    print(f"  SELECT COUNT(DISTINCT student_id) FROM {args.database}.student_enrollment_analytics;")
    print(f"  SELECT * FROM {args.database}.student_academic_performance WHERE is_honor_roll = true LIMIT 10;")
    print(f"  SELECT student_major, AVG(outstanding_balance) FROM {args.database}.financial_summary_by_student GROUP BY student_major;")
    print()


if __name__ == '__main__':
    main()
