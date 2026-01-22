# Student Analytics Agent - Project Context

## Overview
Student Analytics AI Agent built on Claude Agent SDK. Queries Amazon Athena database for student management data analysis through natural language.

## Critical Rule
ALWAYS load appropriate skills and read BOTH the metadata file AND sample data file FIRST before writing any SQL query.

**For each table, review:**
- `data/metadata/<table_name>.yaml` - Complete column definitions, data types, and possible values
- `data/metadata/<table_name>_sample_data.csv` - Sample rows showing actual data format and examples

DO NOT guess or assume column names or values.

## Project Structure
```
/
├── results/
│   ├── raw/{request_id}/      # Athena query results (CSV)
│   └── processed/{request_id}/ # Processed data and visualizations
├── .claude/
│   └── skills/           # Domain-specific agent skills
│       ├── academic/SKILL.md
│       ├── enrollment/SKILL.md
│       └── financial/SKILL.md
├── data/
│   └── metadata/         # Table metadata files
│       ├── <table_name>.yaml           # Column definitions, types, possible values
│       └── <table_name>_sample_data.csv # Sample rows with actual data
├── tools/
│   └── athena_tools.py   # AthenaQueryExecutor for executing Athena queries
└── agent/
    ├── basic_agent.py         # Module 1a: Agent without skills
    ├── skills_agent.py        # Module 1b: Agent with skills
    ├── agent_agentcore.py     # Module 2: AgentCore deployment
    └── agent_agentcore_observable.py # Module 3b: With observability
```

## Environment Configuration

**Database**: student_analytics
**Query Engine**: Amazon Athena
**Storage**: Results in S3, downloaded locally

Configuration values (from environment variables):
- `ATHENA_DATABASE` - Database name
- `ATHENA_OUTPUT_LOCATION` - S3 output location
- `AWS_REGION` - AWS region

## File Management

Save all outputs to disk. Never load large datasets into context.

**IMPORTANT:** All files must be organized by request_id:
- **Query Results**: `results/raw/{request_id}/{filename}.csv` (handled automatically by execute_athena_query tool)
- **Processed Data**: `results/processed/{request_id}/{descriptive_name}.csv`
- **Visualizations**: `results/processed/{request_id}/{name}.png`
- **Reports**: `results/processed/{request_id}/{name}_report.txt`

Use descriptive filenames: `enrollment_trends_2024_analysis.csv` not `data.csv`

## Executing SQL Queries

Use the `execute_athena_query` tool (MCP tool) with two parameters:
- `query`: The SQL SELECT query string
- `local_filename`: A descriptive filename for results (e.g., "enrollment_count.csv")

Example:
```
execute_athena_query(
    query="SELECT COUNT(*) as total_students FROM student_enrollment_analytics",
    local_filename="total_student_count.csv"
)
```

**Security**: Only SELECT queries are allowed.

## Agent Workflow

1. **Load Domain Skill** - Use Skill tool to load appropriate domain expertise
   - GPA, grades → `academic-performance`
   - Enrollment, capacity → `enrollment-analytics`
   - Tuition, payments → `financial-analytics`

2. **Read Table Documentation** - Read both files for the target table:
   - `data/metadata/<table_name>.yaml` - Column definitions, types, constraints
   - `data/metadata/<table_name>_sample_data.csv` - Sample rows to understand data format

3. **Write SQL** - Follow query patterns from skill, use exact column names from metadata

4. **Execute Query** - Use `execute_athena_query` tool with the SQL query and descriptive filename

5. **Process Results** - Load CSV with pandas, perform analysis

6. **Generate Insights** - Create visualizations if appropriate

7. **Present Results** - Clear answer with file references and key statistics

## Available Tables

Denormalized analytics tables (no joins unless absolutely necessary):

1. **student_enrollment_analytics** - Enrollment, course capacity, utilization
2. **student_academic_performance** - Grades, GPA, academic standing
3. **financial_summary_by_student** - Tuition, payments, scholarships
4. **course_performance_analytics** - Course difficulty, instructor effectiveness
5. **instructor_performance_summary** - Instructor workload, ratings
6. **department_summary_metrics** - Department-level aggregates
7. **student_activity_engagement** - Extracurricular activities
8. **attendance_behavior_analytics** - Attendance patterns
9. **scholarship_recipient_analysis** - Scholarship effectiveness
10. **library_usage_patterns** - Library resource utilization

## Skills

Skills are automatically discovered from `.claude/skills/` when agent is configured with `setting_sources=["project"]`.

Skills provide domain expertise, query patterns, and table guidance. The agent invokes skills based on user query type.

## Python Libraries
pandas, numpy, matplotlib, seaborn, scipy
