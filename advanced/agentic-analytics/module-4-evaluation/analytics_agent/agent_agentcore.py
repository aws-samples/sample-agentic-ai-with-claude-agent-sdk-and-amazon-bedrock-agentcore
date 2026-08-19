"""
Agentic Analytics Agent — Amazon Bedrock AgentCore entrypoint.

This is the THIN deployment wrapper. It holds only:
  - the BedrockAgentCoreApp + @app.entrypoint decorator,
  - request parsing + streaming the response,
  - deployment-only plumbing: uploading any files the agent produced to S3 and
    handing the caller presigned URLs.

It contains ZERO agent logic of its own — the agent's identity (system prompt,
Athena tool, skills, cwd) comes from build_agent_options() in agent.py, the SAME
function the local Module 1 run_query() uses. One source of truth.

Run locally:  agentcore dev
Deployed:     AgentCore Runtime invokes `invoke` over HTTP.
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from pathlib import Path
from urllib.parse import urlparse

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from dotenv import load_dotenv

from bedrock_agentcore import BedrockAgentCoreApp
from claude_agent_sdk import ClaudeSDKClient

# Reuse the agent's single source of truth.
from agent import AGENT_DIR, build_agent_options, _default_output_location

load_dotenv()
os.environ.setdefault("CLAUDE_CODE_USE_BEDROCK", "1")

logging.basicConfig(level=logging.INFO, force=True)
logger = logging.getLogger(__name__)

AWS_REGION = os.getenv("AWS_REGION", "us-west-2")

app = BedrockAgentCoreApp()


def _result_bucket() -> str | None:
    """The S3 bucket to upload agent-produced files to (the Athena output bucket)."""
    try:
        parsed = urlparse(_default_output_location())
        return parsed.netloc if parsed.scheme == "s3" else None
    except Exception:
        return None


def _upload_and_sign(bucket: str, local_path: Path, key: str) -> dict | None:
    """Upload one file to S3 and return a presigned URL (5-min) descriptor."""
    cfg = Config(signature_version="s3v4", region_name=AWS_REGION)
    s3 = boto3.client("s3", config=cfg, region_name=AWS_REGION)
    try:
        s3.upload_file(str(local_path), bucket, key)
        url = s3.generate_presigned_url(
            "get_object", Params={"Bucket": bucket, "Key": key}, ExpiresIn=300
        )
        return {"filename": local_path.name, "url": url, "expires_in_seconds": 300,
                "s3_location": f"s3://{bucket}/{key}"}
    except ClientError as e:
        logger.error("upload failed for %s: %s", local_path, e)
        return None


def _collect_outputs(request_id: str, bucket: str | None) -> list[dict]:
    """Upload everything the agent wrote under results/<request_id>/ and sign it."""
    if not bucket:
        return []
    out: list[dict] = []
    base = Path(AGENT_DIR) / "results"
    for sub in ("raw", "processed"):
        d = base / sub / request_id
        if not d.exists():
            continue
        for f in sorted(d.glob("*")):
            if f.is_file():
                signed = _upload_and_sign(bucket, f, f"results/{sub}/{request_id}/{f.name}")
                if signed:
                    out.append(signed)
    return out


@app.entrypoint
async def invoke(payload: dict):
    """AgentCore entrypoint. Expects {"prompt": "..."} and streams text chunks.

    After the turn completes, any files the agent produced are uploaded to S3 and
    a JSON block of presigned URLs is appended to the stream.
    """
    prompt = (payload or {}).get("prompt") or (payload or {}).get("query")
    if not prompt:
        yield "Error: payload must include a 'prompt' field, e.g. {\"prompt\": \"How many students are enrolled?\"}"
        return

    request_id = str(uuid.uuid4())
    options = build_agent_options(request_id=request_id)

    async with ClaudeSDKClient(options=options) as client:
        await client.query(prompt)
        async for msg in client.receive_response():
            for block in getattr(msg, "content", []) or []:
                text = getattr(block, "text", None)
                if text:
                    yield text

    files = _collect_outputs(request_id, _result_bucket())
    if files:
        yield "\n\n```json\n" + json.dumps(
            {"request_id": request_id, "generated_files": files,
             "note": "URLs valid for 5 minutes"}, indent=2
        ) + "\n```\n"


if __name__ == "__main__":
    app.run()
