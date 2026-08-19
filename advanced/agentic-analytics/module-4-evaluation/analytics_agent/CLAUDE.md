# Student Analytics Agent — Project Context

## Overview
Text-to-SQL analytics agent built on the Claude Agent SDK. It answers natural-language
questions about university student data by querying Amazon Athena.

## Critical Rule
ALWAYS load the appropriate skill and read BOTH the metadata file AND the sample-data file
for a table BEFORE writing any SQL. Do NOT guess column names or values.

For each table, review:
- `data/metadata/<table_name>.yaml` — column definitions, types, and possible values
- `data/metadata/<table_name>_sample_data.csv` — sample rows showing the actual data format

## Available Tables
Two denormalized analytics tables (avoid joins unless absolutely necessary):
- **student_enrollment_analytics** — students, courses, enrollment, instructors, capacity
- **financial_summary_by_student** — tuition, payments, scholarships, balances

## Skills
Skills are auto-discovered from `.claude/skills/` (the agent runs with `setting_sources=["project"]`).
Load the one that matches the question:
- **enrollment** — student counts, enrollment, course loads, capacity, instructors
- **financial** — tuition, payments, scholarships, financial aid, outstanding balances

## Agent Workflow
1. **Load the domain skill** with the Skill tool (enrollment vs. financial).
2. **Read the table docs** — the `.yaml` (schema) and `_sample_data.csv` (format) for the target table.
3. **Write SQL** — SELECT only, using exact column names from the metadata.
4. **Run it** with the `execute_athena_query` tool: pass the SQL `query` and a descriptive
   `local_filename` (e.g. `enrollment_by_major.csv`).
5. **Analyze** the downloaded CSV with pandas; create a chart if it helps.
6. **Answer** clearly, citing the key numbers.

## Executing SQL Queries
Use the `execute_athena_query` MCP tool:
- `query`: the SQL SELECT string
- `local_filename`: a descriptive results filename

**Security:** only SELECT queries are allowed (enforced by the SQL validator).

## File Management
Save outputs under `results/processed/<request_id>/` (the request id is in the system prompt).
Query results are written automatically under `results/raw/<request_id>/` by the tool.
Never load large datasets into context — work from the saved CSV files.

## Environment Configuration
From environment variables (set by Module 0 / your `.env`):
- `ATHENA_DATABASE` — database name (`student_analytics`)
- `ATHENA_OUTPUT_LOCATION` — S3 location for Athena results
- `AWS_REGION` — AWS region

## Python Libraries
pandas, numpy, matplotlib
