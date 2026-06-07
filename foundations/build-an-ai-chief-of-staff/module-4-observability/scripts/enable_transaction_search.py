#!/usr/bin/env python3
"""Enable CloudWatch Transaction Search — the one-time, account-level setup that lets
AgentCore agent traces/spans show up in the GenAI Observability dashboard.

This is the ONLY new setup Module 4 needs. AgentCore Runtime auto-instruments the agent
with OpenTelemetry on deploy (no agent-code change); Transaction Search is what makes the
emitted spans searchable in CloudWatch (`/aws/spans`).

Idempotent: checks the current state first and only changes what's needed. Safe to re-run.

Usage:
    python scripts/enable_transaction_search.py [--region us-west-2] [--sampling 1]
"""
from __future__ import annotations

import argparse
import json
import sys

import boto3
from botocore.exceptions import ClientError

# X-Ray writes indexed spans into these CloudWatch log groups; the resource policy lets it.
SPANS_LOG_GROUP = "aws/spans"
APP_SIGNALS_LOG_GROUP = "/aws/application-signals/data"
RESOURCE_POLICY_NAME = "TransactionSearchAccess"


def _account_id(session: boto3.Session) -> str:
    return session.client("sts").get_caller_identity()["Account"]


def _ensure_log_resource_policy(logs, region: str, account: str) -> bool:
    """Grant X-Ray permission to put span events into the CloudWatch log groups. Returns True if created."""
    partition = "aws"
    policy_doc = {
        "Version": "2012-10-17",
        "Statement": [{
            "Sid": "TransactionSearchXRayAccess",
            "Effect": "Allow",
            "Principal": {"Service": "xray.amazonaws.com"},
            "Action": "logs:PutLogEvents",
            "Resource": [
                f"arn:{partition}:logs:{region}:{account}:log-group:{SPANS_LOG_GROUP}:*",
                f"arn:{partition}:logs:{region}:{account}:log-group:{APP_SIGNALS_LOG_GROUP}:*",
            ],
            "Condition": {
                "ArnLike": {"aws:SourceArn": f"arn:{partition}:xray:{region}:{account}:*"},
                "StringEquals": {"aws:SourceAccount": account},
            },
        }],
    }
    existing = {p["policyName"] for p in logs.describe_resource_policies().get("resourcePolicies", [])}
    if RESOURCE_POLICY_NAME in existing:
        print(f"  • log resource policy '{RESOURCE_POLICY_NAME}' already present")
        return False
    logs.put_resource_policy(policyName=RESOURCE_POLICY_NAME, policyDocument=json.dumps(policy_doc))
    print(f"  ✓ created log resource policy '{RESOURCE_POLICY_NAME}'")
    return True


def _ensure_segment_destination(xray) -> bool:
    """Point X-Ray trace segments at CloudWatch Logs. Returns True if it changed."""
    dest = xray.get_trace_segment_destination()
    if dest.get("Destination") == "CloudWatchLogs" and dest.get("Status") == "ACTIVE":
        print(f"  • trace segment destination already CloudWatchLogs/ACTIVE")
        return False
    xray.update_trace_segment_destination(Destination="CloudWatchLogs")
    print("  ✓ set trace segment destination → CloudWatchLogs")
    return True


def enable_transaction_search(region: str, sampling_percent: int | None = None) -> dict:
    session = boto3.Session(region_name=region)
    account = _account_id(session)
    logs = session.client("logs")
    xray = session.client("xray")

    print(f"Enabling CloudWatch Transaction Search in {region} (account {account})…")
    changed_policy = _ensure_log_resource_policy(logs, region, account)
    changed_dest = _ensure_segment_destination(xray)

    if sampling_percent is not None:
        xray.update_indexing_rule(
            Name="Default",
            Rule={"Probabilistic": {"DesiredSamplingPercentage": float(sampling_percent)}},
        )
        print(f"  ✓ indexing sampling set to {sampling_percent}%")

    final = xray.get_trace_segment_destination()
    already_on = not (changed_policy or changed_dest)
    print(
        f"\n{'✅ Already enabled' if already_on else '✅ Enabled'} — "
        f"Destination={final.get('Destination')}, Status={final.get('Status')}.\n"
        "Note: it can take ~10 minutes for spans to become searchable in /aws/spans."
    )
    return {"destination": final.get("Destination"), "status": final.get("Status"),
            "changed": not already_on}


def main() -> int:
    ap = argparse.ArgumentParser(description="Enable CloudWatch Transaction Search (idempotent).")
    ap.add_argument("--region", default=None, help="AWS region (default: session/env region)")
    ap.add_argument("--sampling", type=int, default=None,
                    help="Optional: indexed-span sampling %% (1 = free tier). Omit to leave unchanged.")
    args = ap.parse_args()

    region = args.region or boto3.Session().region_name
    if not region:
        print("ERROR: no region. Pass --region or set AWS_REGION.", file=sys.stderr)
        return 2
    try:
        enable_transaction_search(region, args.sampling)
        return 0
    except ClientError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
