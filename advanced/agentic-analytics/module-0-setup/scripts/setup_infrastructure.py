#!/usr/bin/env python3
"""One-shot infrastructure setup for the Agentic Analytics workshop.

Stands up the DATA LAYER the text-to-SQL agent queries:
  1. an S3 bucket (demo data + Athena query results),
  2. uploads the two demo CSVs,
  3. an Athena database + two external tables over that data,
  4. a smoke query to prove it all works.

Everything is idempotent — safe to re-run. The participant runs ONE command
(`python scripts/setup_infrastructure.py`) and reads the ✅ checklist it prints;
they never run a test. The same `verify()` function is reused by the module's
`slow` test so dev/CI validates the exact thing the participant sees.

Usage:
    python scripts/setup_infrastructure.py [--region us-west-2] [--bucket NAME]
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

# ── Fixed workshop identifiers ───────────────────────────────────────────────
DATABASE = "student_analytics"
S3_PREFIX = "student-analytics"          # where demo data lands under the bucket
RESULTS_PREFIX = "athena-results"        # where Athena writes query output
DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# The two demo tables, as {table_name: (csv_filename, athena_ddl_columns)}.
# DDL uses Athena PHYSICAL types (STRING/INT/DOUBLE/BOOLEAN) — this is the
# source of truth for table creation. (The agent's metadata YAML carries the
# LOGICAL schema + value docs; that's a different layer, read by the agent.)
TABLES: dict[str, tuple[str, str]] = {
    "student_enrollment_analytics": (
        "student_enrollment_analytics.csv",
        """
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
    ),
    "financial_summary_by_student": (
        "financial_summary_by_student.csv",
        """
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
        """,
    ),
}


# ── Helpers ──────────────────────────────────────────────────────────────────
def _default_bucket(account_id: str) -> str:
    return f"student-analytics-agent-{account_id}"


def _results_location(bucket: str) -> str:
    return f"s3://{bucket}/{RESULTS_PREFIX}/"


def _run_athena(athena, query: str, *, bucket: str, database: str | None = None) -> dict:
    """Run an Athena query, block until it finishes, return the final status dict."""
    kwargs: dict = {
        "QueryString": query,
        "ResultConfiguration": {"OutputLocation": _results_location(bucket)},
    }
    if database:
        kwargs["QueryExecutionContext"] = {"Database": database}
    resp = athena.start_query_execution(**kwargs)
    qid = resp["QueryExecutionId"]
    while True:
        execution = athena.get_query_execution(QueryExecutionId=qid)["QueryExecution"]
        state = execution["Status"]["State"]
        if state in ("SUCCEEDED", "FAILED", "CANCELLED"):
            if state != "SUCCEEDED":
                reason = execution["Status"].get("StateChangeReason", "unknown")
                raise RuntimeError(f"Athena query {state}: {reason}\nQuery: {query[:200]}")
            return execution
        time.sleep(1)


def _table_row_count(athena, table: str, *, bucket: str) -> int:
    execution = _run_athena(
        athena, f"SELECT COUNT(*) FROM {DATABASE}.{table}", bucket=bucket, database=DATABASE
    )
    qid = execution["QueryExecutionId"]
    rows = boto3.client(
        "athena", region_name=athena.meta.region_name
    ).get_query_results(QueryExecutionId=qid)["ResultSet"]["Rows"]
    # rows[0] is the header, rows[1] is the value
    return int(rows[1]["Data"][0]["VarCharValue"])


# ── Steps ──────────────────────────────────────────────────────────────────--
def ensure_bucket(s3, bucket: str, region: str) -> bool:
    """Create the bucket if absent. Returns True if created."""
    try:
        s3.head_bucket(Bucket=bucket)
        return False
    except ClientError:
        pass
    kwargs = {"Bucket": bucket}
    if region != "us-east-1":
        kwargs["CreateBucketConfiguration"] = {"LocationConstraint": region}
    s3.create_bucket(**kwargs)
    s3.get_waiter("bucket_exists").wait(Bucket=bucket)
    return True


def upload_demo_data(s3, bucket: str) -> int:
    """Upload demo CSVs that aren't already in S3. Returns count uploaded."""
    uploaded = 0
    for table, (csv_name, _ddl) in TABLES.items():
        key = f"{S3_PREFIX}/data/{table}/{csv_name}"
        try:
            s3.head_object(Bucket=bucket, Key=key)
            continue  # already there — idempotent
        except ClientError:
            pass
        local = DATA_DIR / csv_name
        if not local.exists():
            raise FileNotFoundError(f"demo data missing: {local}")
        s3.upload_file(str(local), bucket, key)
        uploaded += 1
    return uploaded


def create_database_and_tables(athena, bucket: str) -> None:
    _run_athena(athena, f"CREATE DATABASE IF NOT EXISTS {DATABASE}", bucket=bucket)
    for table, (_csv, ddl) in TABLES.items():
        location = f"s3://{bucket}/{S3_PREFIX}/data/{table}/"
        ddl_query = f"""
        CREATE EXTERNAL TABLE IF NOT EXISTS {DATABASE}.{table} (
            {ddl}
        )
        ROW FORMAT DELIMITED
        FIELDS TERMINATED BY ','
        STORED AS TEXTFILE
        LOCATION '{location}'
        TBLPROPERTIES ('skip.header.line.count'='1')
        """
        _run_athena(athena, ddl_query, bucket=bucket, database=DATABASE)


# ── Verify (reused by the slow test) ─────────────────────────────────────────
def verify(region: str, bucket: str) -> dict:
    """Check every piece exists & is queryable. Returns a structured result.

    Used both by the CLI (prints a human checklist) and the `slow` test
    (asserts on the returned dict) — one source of truth, two presentations.
    """
    session = boto3.Session(region_name=region)
    s3 = session.client("s3")
    athena = session.client("athena")

    result: dict = {"region": region, "bucket": bucket, "tables": {}, "ok": False}

    # bucket
    s3.head_bucket(Bucket=bucket)
    result["bucket_ok"] = True

    # database
    dbs = athena.list_databases(CatalogName="AwsDataCatalog")["DatabaseList"]
    result["database_ok"] = any(d["Name"] == DATABASE for d in dbs)
    if not result["database_ok"]:
        raise RuntimeError(f"database '{DATABASE}' not found")

    # tables + row counts
    for table in TABLES:
        count = _table_row_count(athena, table, bucket=bucket)
        result["tables"][table] = count
        if count <= 0:
            raise RuntimeError(f"table '{table}' has 0 rows")

    result["ok"] = True
    return result


def print_checklist(result: dict) -> None:
    print()
    print("=" * 70)
    print("  Agentic Analytics — infrastructure check")
    print("=" * 70)
    print(f"  ✅ S3 bucket:        {result['bucket']}")
    print(f"  ✅ Athena database:  {DATABASE}")
    for table, count in result["tables"].items():
        print(f"  ✅ Table:            {table}  ({count:,} rows)")
    print(f"  ✅ Region:           {result['region']}")
    print("=" * 70)
    print("  Setup complete — you're ready for Module 1. 🎉")
    print("=" * 70)
    print()


# ── Entry point ──────────────────────────────────────────────────────────────
def setup(region: str | None = None, bucket: str | None = None) -> dict:
    session = boto3.Session(region_name=region) if region else boto3.Session()
    region = session.region_name
    if not region:
        raise SystemExit("ERROR: no region. Pass --region or set AWS_REGION.")
    account = session.client("sts").get_caller_identity()["Account"]
    bucket = bucket or _default_bucket(account)

    s3 = session.client("s3")
    athena = session.client("athena")

    print(f"Setting up Agentic Analytics infrastructure in {region} (account {account})…")

    created = ensure_bucket(s3, bucket, region)
    print(f"  • S3 bucket {'created' if created else 'already present'}: {bucket}")

    uploaded = upload_demo_data(s3, bucket)
    print(f"  • demo data: {uploaded} file(s) uploaded"
          + ("" if uploaded else " (already in S3)"))

    create_database_and_tables(athena, bucket)
    print(f"  • Athena database + tables ready (CREATE IF NOT EXISTS)")

    result = verify(region, bucket)
    print_checklist(result)
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description="One-shot Agentic Analytics infra setup (idempotent).")
    ap.add_argument("--region", default=None, help="AWS region (default: session/env region)")
    ap.add_argument("--bucket", default=None,
                    help="S3 bucket name (default: student-analytics-agent-<account_id>)")
    args = ap.parse_args()
    try:
        setup(region=args.region, bucket=args.bucket)
        return 0
    except (ClientError, RuntimeError, FileNotFoundError) as e:
        print(f"\n❌ Setup failed: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
