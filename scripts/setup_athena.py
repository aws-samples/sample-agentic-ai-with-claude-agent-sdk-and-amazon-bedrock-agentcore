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

        'student_academic_performance': """
            student_id STRING,
            student_first_name STRING,
            student_last_name STRING,
            student_email STRING,
            student_major STRING,
            student_overall_gpa DOUBLE,
            student_status STRING,
            student_credits_completed INT,
            student_cohort_year INT,
            course_id STRING,
            course_code STRING,
            course_name STRING,
            course_credits INT,
            department_name STRING,
            course_level INT,
            course_type STRING,
            instructor_id INT,
            instructor_name STRING,
            instructor_rank STRING,
            instructor_avg_rating DOUBLE,
            instructor_department STRING,
            grade_id INT,
            letter_grade STRING,
            numeric_grade DOUBLE,
            percentage_score DOUBLE,
            semester STRING,
            grade_date STRING,
            student_semester_gpa DOUBLE,
            student_cumulative_gpa DOUBLE,
            course_avg_grade DOUBLE,
            course_grade_percentile INT,
            grade_points_earned DOUBLE,
            is_passing BOOLEAN,
            is_honor_roll BOOLEAN,
            is_at_risk BOOLEAN,
            is_dean_list BOOLEAN,
            student_total_courses INT,
            student_courses_passed INT,
            student_courses_failed INT,
            pass_rate_pct DOUBLE
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

        'course_performance_analytics': """
            course_id STRING,
            course_code STRING,
            course_name STRING,
            course_credits INT,
            course_type STRING,
            course_level INT,
            semester STRING,
            max_enrollment INT,
            department_id INT,
            department_name STRING,
            dean_name STRING,
            department_budget BIGINT,
            building_name STRING,
            instructor_id INT,
            instructor_first_name STRING,
            instructor_last_name STRING,
            instructor_rank STRING,
            instructor_email STRING,
            instructor_hire_date STRING,
            instructor_salary INT,
            instructor_office STRING,
            total_enrolled INT,
            total_completed INT,
            total_dropped INT,
            current_enrollment INT,
            enrollment_rate_pct DOUBLE,
            drop_rate_pct DOUBLE,
            total_grades INT,
            avg_numeric_grade DOUBLE,
            avg_gpa DOUBLE,
            median_grade DOUBLE,
            mode_letter_grade STRING,
            a_grade_count INT,
            b_grade_count INT,
            c_grade_count INT,
            d_grade_count INT,
            f_grade_count INT,
            pass_rate_pct DOUBLE,
            fail_rate_pct DOUBLE,
            total_feedback_count INT,
            avg_overall_rating DOUBLE,
            avg_course_content_rating DOUBLE,
            avg_instructor_rating DOUBLE,
            avg_difficulty_rating DOUBLE,
            avg_workload_rating DOUBLE,
            would_recommend_pct DOUBLE,
            avg_attendance_rate_pct DOUBLE,
            absent_count_avg DOUBLE,
            late_count_avg DOUBLE,
            excused_absence_avg DOUBLE,
            course_grade_vs_dept_avg DOUBLE,
            course_rating_vs_dept_avg DOUBLE,
            course_difficulty_vs_grade_correlation DOUBLE,
            is_high_enrollment BOOLEAN,
            is_high_failure_rate BOOLEAN,
            is_highly_rated BOOLEAN,
            is_difficult_course BOOLEAN
        """,

        'instructor_performance_summary': """
            instructor_id INT,
            instructor_first_name STRING,
            instructor_last_name STRING,
            instructor_email STRING,
            instructor_rank STRING,
            instructor_hire_date STRING,
            instructor_office STRING,
            instructor_salary INT,
            years_of_service INT,
            department_id INT,
            department_name STRING,
            dean_name STRING,
            building_name STRING,
            courses_teaching_count INT,
            total_students_current INT,
            total_credits_teaching INT,
            sections_count INT,
            total_courses_taught_all_time INT,
            total_students_taught INT,
            semesters_teaching_count INT,
            avg_grade_given DOUBLE,
            median_grade_given DOUBLE,
            a_grade_pct DOUBLE,
            b_grade_pct DOUBLE,
            c_grade_pct DOUBLE,
            d_grade_pct DOUBLE,
            f_grade_pct DOUBLE,
            pass_rate_pct DOUBLE,
            avg_gpa_given DOUBLE,
            total_feedback_count INT,
            avg_overall_rating DOUBLE,
            avg_instructor_rating DOUBLE,
            avg_course_content_rating DOUBLE,
            avg_difficulty_rating DOUBLE,
            avg_workload_rating DOUBLE,
            would_recommend_pct DOUBLE,
            student_avg_gpa_in_courses DOUBLE,
            student_completion_rate DOUBLE,
            student_drop_rate_pct DOUBLE,
            rating_vs_dept_avg DOUBLE,
            grade_generosity_vs_dept_avg DOUBLE,
            workload_vs_dept_avg DOUBLE,
            dept_rating_rank INT,
            university_rating_rank INT,
            is_highly_rated BOOLEAN,
            is_tough_grader BOOLEAN,
            is_easy_grader BOOLEAN,
            has_high_workload BOOLEAN,
            is_tenured BOOLEAN
        """,

        'department_summary_metrics': """
            department_id INT,
            department_name STRING,
            dean_name STRING,
            building_name STRING,
            established_year INT,
            budget_amount BIGINT,
            total_students_enrolled INT,
            total_students_active INT,
            total_students_graduated INT,
            avg_student_gpa DOUBLE,
            students_on_deans_list INT,
            students_at_risk INT,
            total_instructors INT,
            professor_count INT,
            associate_prof_count INT,
            assistant_prof_count INT,
            lecturer_count INT,
            adjunct_count INT,
            avg_instructor_rating DOUBLE,
            avg_instructor_salary DOUBLE,
            total_courses_offered INT,
            total_enrollments INT,
            avg_class_size DOUBLE,
            avg_course_rating DOUBLE,
            avg_pass_rate_pct DOUBLE,
            avg_course_grade DOUBLE,
            total_tuition_revenue DOUBLE,
            total_scholarships_distributed DOUBLE,
            net_revenue DOUBLE,
            budget_per_student DOUBLE,
            revenue_per_instructor DOUBLE,
            enrollment_yoy_growth_pct DOUBLE,
            revenue_yoy_growth_pct DOUBLE,
            graduation_rate_pct DOUBLE,
            retention_rate_pct DOUBLE,
            fall_2024_enrollment INT,
            spring_2024_enrollment INT,
            fall_2023_enrollment INT,
            enrollment_trend STRING,
            enrollment_rank INT,
            gpa_rank INT,
            rating_rank INT,
            revenue_rank INT,
            graduation_rate_rank INT,
            is_growing_enrollment BOOLEAN,
            is_high_performing BOOLEAN,
            is_budget_efficient BOOLEAN,
            has_scholarship_program BOOLEAN
        """,

        'student_activity_engagement': """
            student_id STRING,
            student_first_name STRING,
            student_last_name STRING,
            student_email STRING,
            student_major STRING,
            student_gpa DOUBLE,
            student_status STRING,
            student_year STRING,
            student_credits_completed INT,
            department_name STRING,
            department_id INT,
            activity_id STRING,
            activity_name STRING,
            activity_type STRING,
            student_role STRING,
            activity_status STRING,
            join_date STRING,
            hours_per_week DOUBLE,
            total_hours_committed DOUBLE,
            total_activities INT,
            active_activities_count INT,
            leadership_positions_count INT,
            total_hours_per_week DOUBLE,
            total_community_service_hours DOUBLE,
            total_academic_society_hours DOUBLE,
            sports_activities_count INT,
            academic_clubs_count INT,
            volunteer_activities_count INT,
            cultural_clubs_count INT,
            engagement_score DOUBLE,
            is_highly_engaged BOOLEAN,
            weeks_active INT,
            semesters_active INT,
            gpa_vs_activity_hours DOUBLE,
            retention_risk_score DOUBLE,
            is_student_leader BOOLEAN,
            is_athlete BOOLEAN,
            is_volunteer BOOLEAN,
            is_academic_club_member BOOLEAN,
            has_multiple_activities BOOLEAN
        """,

        'attendance_behavior_analytics': """
            student_id STRING,
            student_first_name STRING,
            student_last_name STRING,
            student_email STRING,
            student_major STRING,
            student_gpa DOUBLE,
            student_status STRING,
            course_id STRING,
            course_code STRING,
            course_name STRING,
            course_credits INT,
            instructor_name STRING,
            department_name STRING,
            semester STRING,
            total_class_sessions INT,
            classes_attended INT,
            classes_absent INT,
            classes_late INT,
            classes_excused INT,
            attendance_rate_pct DOUBLE,
            absence_rate_pct DOUBLE,
            late_rate_pct DOUBLE,
            student_total_classes INT,
            student_attendance_rate_pct DOUBLE,
            student_chronic_absences INT,
            student_consecutive_absences INT,
            course_avg_attendance_rate DOUBLE,
            course_absent_count INT,
            recent_week_attendance_rate DOUBLE,
            recent_month_attendance_rate DOUBLE,
            attendance_trend STRING,
            last_absence_date STRING,
            days_since_last_absence INT,
            student_grade_in_course DOUBLE,
            attendance_grade_correlation DOUBLE,
            attendance_percentile INT,
            is_chronic_absenteeism BOOLEAN,
            is_perfect_attendance BOOLEAN,
            has_recent_absence_pattern BOOLEAN,
            is_attendance_at_risk BOOLEAN,
            absence_alert_sent BOOLEAN,
            last_alert_date STRING,
            alert_count INT
        """,

        'scholarship_recipient_analysis': """
            student_id STRING,
            student_first_name STRING,
            student_last_name STRING,
            student_email STRING,
            student_major STRING,
            student_status STRING,
            student_enrollment_date STRING,
            student_cohort INT,
            current_gpa DOUBLE,
            cumulative_gpa DOUBLE,
            credits_completed INT,
            semesters_enrolled INT,
            academic_standing STRING,
            scholarship_id STRING,
            scholarship_name STRING,
            scholarship_type STRING,
            scholarship_amount DOUBLE,
            award_date STRING,
            academic_year STRING,
            is_renewable BOOLEAN,
            gpa_requirement DOUBLE,
            renewal_count INT,
            total_scholarships INT,
            total_scholarship_amount DOUBLE,
            merit_scholarship_total DOUBLE,
            need_based_total DOUBLE,
            athletic_scholarship_total DOUBLE,
            departmental_total DOUBLE,
            avg_scholarship_amount DOUBLE,
            largest_scholarship DOUBLE,
            total_tuition_paid DOUBLE,
            scholarship_coverage_pct DOUBLE,
            net_tuition_cost DOUBLE,
            has_additional_aid BOOLEAN,
            semesters_since_award INT,
            gpa_at_award DOUBLE,
            gpa_current DOUBLE,
            gpa_change_since_award DOUBLE,
            met_gpa_requirement BOOLEAN,
            courses_passed_since_award INT,
            credits_earned_since_award INT,
            is_still_enrolled BOOLEAN,
            retention_status STRING,
            graduation_status STRING,
            semesters_retained INT,
            retention_rate_pct DOUBLE,
            gpa_vs_non_scholarship_avg DOUBLE,
            retention_vs_non_scholarship DOUBLE,
            graduation_rate_vs_average DOUBLE,
            scholarship_per_credit_hour DOUBLE,
            scholarship_roi_score DOUBLE,
            is_scholarship_at_risk BOOLEAN,
            is_high_performer BOOLEAN,
            is_scholarship_renewed BOOLEAN,
            meets_requirements BOOLEAN
        """,

        'library_usage_patterns': """
            student_id STRING,
            student_first_name STRING,
            student_last_name STRING,
            student_email STRING,
            student_major STRING,
            student_gpa DOUBLE,
            student_status STRING,
            student_year STRING,
            department_name STRING,
            department_id INT,
            checkout_id STRING,
            book_title STRING,
            author_name STRING,
            isbn STRING,
            resource_category STRING,
            resource_type STRING,
            checkout_date STRING,
            due_date STRING,
            return_date STRING,
            days_checked_out INT,
            is_returned BOOLEAN,
            is_overdue BOOLEAN,
            overdue_days INT,
            overdue_fee DOUBLE,
            total_checkouts INT,
            total_returns INT,
            total_overdue INT,
            current_checkouts INT,
            total_overdue_fees DOUBLE,
            avg_checkout_duration_days DOUBLE,
            overdue_rate_pct DOUBLE,
            textbook_checkouts INT,
            reference_checkouts INT,
            fiction_checkouts INT,
            research_material_checkouts INT,
            checkouts_this_semester INT,
            checkouts_last_30_days INT,
            avg_checkouts_per_month DOUBLE,
            usage_frequency STRING,
            student_gpa DOUBLE,
            library_usage_gpa_correlation DOUBLE,
            library_usage_percentile INT,
            is_frequent_user BOOLEAN,
            has_overdue_items BOOLEAN,
            is_responsible_borrower BOOLEAN,
            has_outstanding_fees BOOLEAN
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
        print("Please run generate_denormalized_data.py first to create the CSV files.")
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
