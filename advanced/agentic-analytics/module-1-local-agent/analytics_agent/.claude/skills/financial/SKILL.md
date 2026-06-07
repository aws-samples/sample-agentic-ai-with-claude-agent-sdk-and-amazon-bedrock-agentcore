---
name: financial-analytics
description: Analyze tuition payments and revenue, outstanding balances and payment status, scholarship awards and distribution, payment methods and transaction patterns, financial aid and coverage rates, net tuition after scholarships, and semester-wise financial breakdowns. Use when user asks about tuition, payments, scholarships, financial aid, or student finances.
---

# Quick Start Guide

**Before writing ANY SQL query:**

1. **Read metadata files** (MANDATORY):
   - `data/metadata/financial_summary_by_student.yaml`
   - `data/metadata/financial_summary_by_student_sample_data.csv`

2. **Identify query pattern** from user's question:
   - "How many..." → Pattern 1 (Simple Counting)
   - "...for each [dimension]" → Pattern 2 (Aggregation by Dimension)
   - "Which majors..." → Pattern 3 (Ranking Dimensions)
   - "Top N students..." → Pattern 4 (Top N)
   - "Breakdown by..." → Pattern 5 (Distribution)

3. **Apply Default Assumptions** - Filter for active students unless explicitly stated otherwise

4. **Check Standard Metric Definitions** for ambiguous terms like "financial support"

5. **Apply pattern guidelines** (see Query Pattern Guidelines section)

6. **Verify with Result Validation Checklist** before executing

# Default Assumptions (READ THIS FIRST)

**⚠️ CRITICAL: These defaults apply to ALL queries unless user explicitly states otherwise:**

## Student Population Rule
**Default: ALWAYS filter for Active students**

Apply this filter to ALL query patterns (1-5) by default:
- Pattern 1 (Counting): "How many students have X?" → Filter Active students
- Pattern 2 (Aggregation): "Average Y for each major" → Filter Active students
- Pattern 3 (Ranking): "Which majors receive most X?" → Filter Active students
- Pattern 4 (Top N): Consider context - usually Active students
- Pattern 5 (Breakdown): "Breakdown by payment method" → Filter Active students

**Only skip this filter when user explicitly says:**
- "all students including graduated"
- "all students regardless of status"
- "historical data for all students"

**Present tense verbs indicate current/active students:**
- "How many students **have** outstanding balances?" → Active students
- "Which majors **receive** most support?" → Active students
- "Show me students **with** high GPA" → Active students

# General Rules:
- **CRITICAL**: When generating SQL query, you should focus on answering user's question, rather than over-analyzing things you are not asked for.
- **CRITICAL**: Use Query Pattern Guidelines (1-5) for consistent approach
- **CRITICAL**: For ambiguous metrics like "financial support", include multiple related metrics (total, average, coverage)
- DO NOT sort by id columns
- DO NOT select unrequested columns
- Use ROUND(AVG(), 1) for averages operation
- Use ROUND(SUM(), 2) for dollar amounts when appropriate

# Financial Analytics

## Primary Table
**financial_summary_by_student**
- Metadata: `data/metadata/financial_summary_by_student.yaml`
- Sample data: `data/metadata/financial_summary_by_student_sample_data.csv`

**CRITICAL**: You MUST read BOTH files before writing ANY SQL query:
1. Read `data/metadata/financial_summary_by_student.yaml` for complete schema
2. Read `data/metadata/financial_summary_by_student_sample_data.csv` for actual data examples

## Table Structure

**One Record Per Student:**
- Each row represents ONE student's complete financial summary
- All metrics are pre-aggregated at the student level
- No need to use `COUNT(DISTINCT student_id)` - simple `COUNT(*)` counts students
- Student count = Row count (when properly filtered)

**Key Column Prefixes:**
- `student_*` - Student information (id, name, major, GPA, status, enrollment date)
- `student_department_*` - Department for student's major
- `total_*` - Pre-aggregated totals (tuition due, paid, scholarships)
- `*_scholarships_total` - Breakdown by scholarship type
- `last_payment_*` - Most recent payment details
- Boolean flags: `has_outstanding_balance`, `is_scholarship_recipient`

**⚠️ IMPORTANT - Columns That DON'T EXIST:**
- ❌ `credit_card_payments_total`, `bank_transfer_total`, `check_payments_total`, `financial_aid_total`
- ❌ `total_payments_count`, `completed_payments_count`, `pending_payments_count`, `failed_payments_count`
- ❌ `payment_success_rate_pct`, `avg_payment_amount`
- ❌ `fall_2024_tuition`, `fall_2024_scholarships`, `spring_2024_tuition`, etc.
- ❌ `is_payment_plan_active`, `is_financial_aid_recipient`
- ✅ ONLY `last_payment_method` exists (categorical: 'Credit Card', 'Bank Transfer', 'Check', 'Financial Aid')

## Natural Language to SQL Mappings

### ⚠️ CRITICAL: "Current Students" vs "All Students"

When user asks about **current/active students**, ALWAYS filter:

```sql
WHERE student_status = 'Active'
```

**Triggers:**
- "currently enrolled students"
- "active students"
- "students with outstanding balances" (implies current)
- "how many students have..." (present tense = current)
- "which students..." (without past context = current)

**Exception:** Only include ALL statuses when explicitly asked:
- "all students including graduated"
- "historical data"
- "students who have ever..."

### ⚠️ CRITICAL: Standard Metric Definitions

**When user asks about "financial support" or "scholarships", use these standard metrics:**

| Metric Name | SQL Expression | When to Use |
|-------------|----------------|-------------|
| **Total Financial Support** | `SUM(total_scholarships_received)` | "Which majors receive the **most** financial support" (total dollars across all students) |
| **Average Support Per Student** | `AVG(total_scholarships_received)` | "What's the **average** financial support per student" |
| **Scholarship Coverage Rate** | `AVG(scholarship_coverage_rate_pct)` | "What percentage of tuition is covered by scholarships" |

**Default Behavior for Ambiguous Queries:**
- "financial support" without qualifier → Include **ALL THREE metrics** in the query
- "most financial support" → Order by **total dollars** (`SUM`) but include average for context
- Always include `COUNT(*) as student_count` to show population size

### ⚠️ CRITICAL: Ambiguous Terms

| User Says | Ambiguity | Standard Interpretation | SQL Pattern |
|-----------|-----------|------------------------|-------------|
| "most/highest financial support" | Could be total $ or average $ | **Total dollars** (SUM), but include average for context | `SUM(total_scholarships_received)` + `AVG(total_scholarships_received)` |
| "average scholarship coverage rate" | Already clear | Use existing calculated column | `AVG(scholarship_coverage_rate_pct)` |
| "payment method distribution" | ONLY last payment available | Count by last_payment_method | `GROUP BY last_payment_method, COUNT(*)` |
| "students with balances" | Could mean > 0 or > threshold | Use boolean flag unless threshold specified | `has_outstanding_balance = true` OR `outstanding_balance > X` |
| "breakdown by [dimension]" | Need counts and percentages | Group and count with percentage | `GROUP BY [dimension], COUNT(*), percentage calculation` |

### Student Status Values

| Status | Meaning | Include in "Active" queries? |
|--------|---------|------------------------------|
| `'Active'` | Currently enrolled | ✅ Yes |
| `'Graduated'` | Completed program | ❌ No |
| `'On Leave'` | Temporarily not enrolled | ❌ No |

### Scholarship Coverage Thresholds

| Range | Interpretation | Query Pattern |
|-------|----------------|---------------|
| >= 75% | Most tuition covered | `WHERE scholarship_coverage_rate_pct >= 75` |
| 50-74% | Significant coverage | `WHERE scholarship_coverage_rate_pct BETWEEN 50 AND 74.99` |
| 25-49% | Partial coverage | `WHERE scholarship_coverage_rate_pct BETWEEN 25 AND 49.99` |
| < 25% | Minimal coverage | `WHERE scholarship_coverage_rate_pct < 25` |
| 0% | No scholarships | `WHERE is_scholarship_recipient = false` |
| > 100% | Scholarships exceed payments | `WHERE scholarship_coverage_rate_pct > 100` |

### Outstanding Balance Patterns

| User Asks About | SQL Pattern |
|-----------------|-------------|
| "students with outstanding balances" | `WHERE has_outstanding_balance = true` |
| "balances over $X" | `WHERE outstanding_balance > X` |
| "balances greater than $X" | `WHERE outstanding_balance > X` |
| "students who paid in full" | `WHERE has_outstanding_balance = false` |
| "highest balances" | `ORDER BY outstanding_balance DESC` |

### Aggregation Patterns

| User Asks About | SQL Pattern |
|-----------------|-------------|
| "How many students..." | `SELECT COUNT(*) ...` (one row per student) |
| "Average scholarship by major" | `SELECT student_major, ROUND(AVG(total_scholarships_received), 1) ... GROUP BY student_major` |
| "Average coverage rate for each major" | `SELECT student_major, ROUND(AVG(scholarship_coverage_rate_pct), 1) ... GROUP BY student_major` |
| "Total revenue" | `SELECT SUM(total_tuition_paid) ...` |
| "Top students by..." | `ORDER BY ... DESC LIMIT N` |
| "Students by payment method" | `SELECT last_payment_method, COUNT(*) ... GROUP BY last_payment_method` |
| "Which majors receive most..." | See "Ambiguous Terms" section - could be SUM or AVG |

## Query Pattern Guidelines

**Identify the query pattern based on user's question structure:**

### Pattern 1: Simple Counting
**Trigger:** "How many students [condition]?"
**Approach:**
- Use `COUNT(*)` to count students
- Include `WHERE student_status = 'Active'` by default
- Apply the condition filter

### Pattern 2: Aggregation by Dimension
**Trigger:** "[metric] for each [dimension]" OR "[metric] by [dimension]"
**Approach:**
- **ALWAYS filter for active students first** using the default student status rule (unless user explicitly says "all students")
- SELECT the dimension column
- Apply appropriate aggregation (AVG, SUM) with ROUND()
- Include `COUNT(*) as student_count` for context
- GROUP BY the dimension
- ORDER BY the metric (DESC for "most/highest", ASC for "least/lowest")

**Examples:**
- "average scholarship coverage rate for each major" → Filter Active students + GROUP BY student_major
- "total revenue by department" → Filter Active students + GROUP BY department
- "payment distribution for each major" → Filter Active students + GROUP BY student_major

### Pattern 3: Ranking Dimensions (Ambiguous Metrics)
**Trigger:** "Which [dimension] [verb] the most [metric]?" (e.g., "Which majors receive most financial support?")
**Approach:**
- SELECT the dimension (e.g., student_major)
- Include `COUNT(*) as student_count`
- For ambiguous terms like "financial support", include ALL THREE metrics:
  - `SUM(total_scholarships_received)` as total
  - `AVG(total_scholarships_received)` as average per student
  - `AVG(scholarship_coverage_rate_pct)` as coverage rate
- GROUP BY dimension
- ORDER BY the primary interpretation (total for "most", average for "average")
- Filter active students by default

**Key Point:** This pattern addresses ambiguity by providing multiple metrics rather than guessing which one.

### Pattern 4: Top N Individual Records
**Trigger:** "Top N students by [metric]" OR "Show me [N] students with [condition]"
**Approach:**
- SELECT student identifiers (student_id, student_name)
- SELECT the ranking metric
- SELECT ONLY explicitly requested additional columns (e.g., "along with GPA" → include student_gpa)
- ORDER BY ranking metric DESC
- LIMIT N
- Consider whether to filter Active:
  - Include filter for "top students with highest balance" (current context)
  - Omit filter if user wants to see enrollment_status variety

**Key Point:** Minimize column selection - only include what user explicitly requested.

### Pattern 5: Breakdown/Distribution
**Trigger:** "Breakdown by [dimension]" OR "Distribution of [dimension]"
**Approach:**
- **ALWAYS filter for active students first** using the default student status rule (unless user explicitly says "all students")
- SELECT the dimension
- Include `COUNT(*) as student_count`
- Include percentage calculation: `ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 1) as percentage`
- GROUP BY dimension
- ORDER BY student_count DESC

**Examples:**
- "breakdown of students by payment method" → Filter Active students + GROUP BY last_payment_method
- "distribution of majors" → Filter Active students + GROUP BY student_major

## Column Selection Guidelines

**CRITICAL: Only SELECT columns that are:**
1. **Grouping dimensions** (e.g., student_major when GROUP BY student_major)
2. **Explicitly requested by user** (e.g., "along with their GPA" → include student_gpa)
3. **Calculated metrics** (aggregations like COUNT, AVG, SUM)
4. **Context count** (`COUNT(*) as student_count` in GROUP BY queries)

**DO NOT include:**
- ❌ Unrequested additional context columns
- ❌ Extra scholarship breakdowns unless asked
- ❌ All possible metrics "just in case"
- ❌ Department info unless specifically asked

**Examples of column selection:**
- User: "average scholarship by major" → SELECT: student_major, AVG(total_scholarships_received), COUNT(*)
- User: "top 10 students by GPA" → SELECT: student_id, student_name, student_gpa (no other columns)
- User: "top 10 by GPA along with their major" → SELECT: student_id, student_name, student_gpa, student_major
- User: "which majors receive most support" → SELECT: student_major, SUM, AVG, coverage rate, COUNT (multiple metrics for ambiguous "support")

### Payment Method Limitations

**⚠️ CRITICAL:** ONLY `last_payment_method` exists (categorical field)

| What User Wants | What's Available | SQL Pattern |
|-----------------|------------------|-------------|
| "Count students by payment method" | ✅ Available | `GROUP BY last_payment_method` with `COUNT(*)` |
| "Average payment by method" | ✅ Available | `GROUP BY last_payment_method` with `AVG(last_payment_amount)` |
| "Total amount paid via credit card" | ❌ NOT Available | NO column exists for payment method totals |
| "Percentage paid via bank transfer" | ❌ NOT Available | Cannot calculate (no payment totals by method) |

**When user asks about payment method totals:**
- Explain limitation: "Only last payment method is available, not totals by method"
- Offer alternative: "I can show you student count and average payment amount by last payment method"

## Data Quality Notes

- **One row per student**: Simple `COUNT(*)` counts students (no DISTINCT needed)
- **All metrics pre-aggregated**: Scholarships, payments already summed per student
- **Boolean flags**: Use `has_outstanding_balance`, `is_scholarship_recipient` for filtering
- **Coverage rate can exceed 100%**: Some students receive scholarships > tuition paid
- **No temporal data**: No semester breakdowns, only aggregated totals

## Semantic Keywords Reference

**Use this table to identify query intent and select the correct pattern:**

| User Keywords | Query Intent | SQL Pattern | Template Reference |
|--------------|--------------|-------------|-------------------|
| "how many", "count" | Simple counting | `SELECT COUNT(*) ... WHERE` | Pattern 1 |
| "for each", "by [dimension]" | Aggregation by dimension | `SELECT [dim], AVG/SUM ... GROUP BY` | Pattern 2 |
| "which", "what [dimension]" | Ranking dimensions | `SELECT [dim], metrics ... ORDER BY` | Pattern 3 |
| "most", "highest", "top" | Descending order | `ORDER BY [metric] DESC` | Pattern 3 or 4 |
| "least", "lowest", "bottom" | Ascending order | `ORDER BY [metric] ASC` | Pattern 3 or 4 |
| "top N", "first N", "show me N" | Limited results | `LIMIT N` | Pattern 4 |
| "breakdown", "distribution" | Group with percentages | `GROUP BY ... with percentage calc` | Pattern 5 |
| "average", "mean" | Average aggregation | `AVG()` | Pattern 2 |
| "total", "sum" | Sum aggregation | `SUM()` | Pattern 3 |

## Result Validation Checklist

**Before executing SQL, verify these items:**

### Filtering & Data Scope
- [ ] **⚠️ CRITICAL: Applied default student status filter** - Used Active students filter UNLESS user explicitly requested "all students"
- [ ] Did NOT filter Active when user asks about "enrollment status" variety or distribution by status
- [ ] Used `is_scholarship_recipient = true` when analyzing only scholarship recipients
- [ ] Applied correct threshold for outstanding balances (e.g., `> 3000` not `> 1000`)

### Query Pattern Compliance
- [ ] Matched query to correct Standard Query Pattern (1-5)
- [ ] Followed template structure exactly for chosen pattern
- [ ] Included `COUNT(*) as student_count` in GROUP BY queries for context
- [ ] Used `LIMIT N` for "top N" queries

### Column Selection
- [ ] Selected ONLY explicitly requested columns
- [ ] Did NOT add unrequested context columns or extra metrics
- [ ] Included grouping dimension in SELECT when using GROUP BY
- [ ] Used appropriate column for requested attribute (e.g., `student_gpa` not `cumulative_gpa`)

### Ambiguous Terms Handling
- [ ] For "financial support" queries: included total, average, AND coverage rate metrics
- [ ] Ordered by primary metric (total dollars for "most")
- [ ] Used correct metric definition from Standard Metrics table

### SQL Syntax
- [ ] Used ROUND(AVG(), 1) for averages
- [ ] Used ROUND(SUM(), 2) for dollar amounts when needed
- [ ] Did NOT sort by ID columns (student_id, department_id, etc.)
- [ ] Did NOT use `COUNT(DISTINCT student_id)` (unnecessary - one row per student)
- [ ] Used percentage calculation: `ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 1)` for breakdowns

### Column Existence
- [ ] Did NOT reference non-existent columns:
  - Payment method totals (credit_card_payments_total, etc.)
  - Payment counts (total_payments_count, etc.)
  - Semester fields (fall_2024_tuition, etc.)
- [ ] Used ONLY `last_payment_method` for payment method analysis (categorical only)

### Edge Cases
- [ ] Handled NULL values appropriately
- [ ] Considered that scholarship_coverage_rate_pct can exceed 100%
- [ ] Used window function for percentages in breakdown queries

## Common Mistakes to Avoid

### Query Pattern Violations

❌ **DON'T:**
- Write ad-hoc queries without considering Pattern Guidelines (1-5)
- Provide only single metric for ambiguous terms like "financial support"
- Add unrequested columns

✅ **DO:**
- Identify which Pattern (1-5) best matches the user's question
- Follow the pattern approach guidelines consistently
- For ambiguous metrics, include multiple related metrics (total, average, coverage)

### Column Selection Errors

❌ **DON'T over-select columns:**
- Including all scholarship breakdowns when user asks for "average scholarship"
- Adding context columns not requested (e.g., department when not asked)
- Selecting all possible metrics "just in case"

✅ **DO:**
- Select ONLY: grouping columns + requested metrics + student_count
- Add columns ONLY when explicitly requested by user
- For ambiguous terms: include multiple metrics of SAME concept (total, average, coverage for "financial support")

### Non-Existent Columns

❌ **DON'T reference columns that don't exist:**
- `credit_card_payments_total`, `bank_transfer_total`, `check_payments_total`
- `payment_success_rate_pct`, `total_payments_count`, `avg_payment_amount`
- `fall_2024_tuition`, `spring_2024_tuition` (no semester breakdowns)
- `is_payment_plan_active`, `is_financial_aid_recipient`

✅ **DO:**
- Use ONLY `last_payment_method` (categorical) for payment method analysis
- Use pre-aggregated totals: `total_tuition_paid`, `total_scholarships_received`
- Check metadata files before using any column

### Filtering Mistakes

❌ **DON'T:**
- Forget `student_status = 'Active'` when user asks about "current students"
- Filter Active when user wants to see "enrollment status" variety
- Use wrong threshold (e.g., > 1000 when user said > 3000)

✅ **DO:**
- Always filter Active for present-tense queries ("how many students have...")
- Omit status filter when showing status as a dimension
- Use exact thresholds specified by user

### Aggregation Mistakes

❌ **DON'T:**
- Use `COUNT(DISTINCT student_id)` (unnecessary - one row per student)
- Provide only SUM OR AVG for ambiguous "financial support" queries
- Sort by ID columns (student_id, department_id)

✅ **DO:**
- Use simple `COUNT(*)` to count students
- Include multiple metrics (total, average, coverage) for ambiguous terms
- Order by meaningful metrics, not IDs

### Consistency Guidelines

**These pattern guidelines were validated through consistency testing. Following them ensures:**
- ✅ Consistent SQL approach across similar queries
- ✅ Predictable results for similar questions
- ✅ Reduced ambiguity in metric interpretation
- ✅ Standard handling of ambiguous terms

**Reference:** See `consistency_analysis_Jan_27__10_13/` for detailed analysis that informed these guidelines.

## Visualizations

- **Pie Chart:** Payment method distribution (last payment), student status distribution
- **Bar Chart:** Revenue by department, scholarship by major, outstanding balances by major
- **Stacked Bar Chart:** Scholarship types by major
- **Histogram:** Outstanding balance distribution, scholarship coverage rate distribution
- **Scatter Plot:** GPA vs scholarship amount, GPA vs coverage rate
