---
name: enrollment-analytics
description: Analyze student enrollment data with focus on student-centric queries including student counts, enrollment analysis, course loads, and tracking student enrollment changes over time. 
---

# General rules:
- Current semester is Fall 2025.
- **CRITICAL**: When generating SQL query, you should focus on answering user's question, rather than over-analysing things you are not asked for.
- DO NOT sort by id columns
- Use ROUND(AVG(), 1) for averages operation

# Enrollment Analytics

## Primary Table
**student_enrollment_analytics**
- Metadata: `data/metadata/student_enrollment_analytics.yaml`
- Sample data: `data/metadata/student_enrollment_analytics_sample_data.csv`

**CRITICAL**: You MUST read BOTH files before writing ANY SQL query:
1. Read `data/metadata/student_enrollment_analytics.yaml` for complete schema
2. Read `data/metadata/student_enrollment_analytics_sample_data.csv` for actual data examples

## Table Structure

**Student-Centric Design:**
This table is a **left join with students as the left table**, meaning:
- Each row represents one student-course enrollment
- One student can have multiple rows (one per enrolled course)
- When counting students, ALWAYS use `COUNT(DISTINCT student_id)` to avoid double-counting

**Key Column Prefixes:**
- `student_*` - Student information (id, name, major, GPA, status)
- `student_department_*` - Department for student's major
- `student_enrollment_*` - Course enrollment details (id, date, status)
- `course_*` - Course information (id, code, name, semester, type)
- `course_instructor_*` - Instructor teaching the course

**IMPORTANT**: There are NO pre-calculated metrics. You must calculate:
- Enrollment student counts: `COUNT(DISTINCT student_id)`
- Course counts per student: `COUNT(DISTINCT course_id)`
- Current semester filter: `WHERE course_semester = 'Fall 2025'`

## Natural Language to SQL Mappings

### ⚠️ CRITICAL: "Current" or "Currently Enrolled"

When user asks about **present-tense enrollment**, ALWAYS use THREE filters:

```sql
WHERE student_enrollment_status = 'Enrolled'    -- Active in course
  AND student_status = 'Active'                 -- Active at university
  AND course_semester = 'Fall 2025'             -- Current semester
```

**Triggers:**
- "currently enrolled"
- "students enrolled this semester"
- "active students"
- "how many students are enrolled" (present tense = current)
- "courses by enrollment this semester"
- "instructors by student enrollment this semester"
- "top courses this semester"
- "top instructors this semester"
- ANY query that counts students in the current semester

**Common mistake:** Forgetting `student_status = 'Active'` when the query doesn't explicitly say "active students". Even when asking about "instructors by enrollment" or "courses by enrollment", you MUST include this filter to count only valid current enrollments.

### Student Status vs Enrollment Status

| User Says | SQL Filters Needed |
|-----------|-------------------|
| "currently enrolled students" | `student_status = 'Active'` AND `student_enrollment_status = 'Enrolled'` AND `course_semester = 'Fall 2025'` |
| "all students" (context: enrollment) | Include all `student_status` values, but filter `student_enrollment_status` |
| "students who dropped courses" | `student_enrollment_status = 'Dropped'` |
| "students who completed courses" | `student_enrollment_status = 'Completed'` |

**Available semesters:** Spring 2024, Fall 2024, Spring 2025, Fall 2025
**Current semester:** Fall 2025

### ⚠️ CRITICAL: Semester-to-Semester Comparisons

When user asks to compare student behavior **"from Semester A to Semester B"**, you MUST:

**Use INNER JOIN to compare only students present in BOTH semesters:**

```sql
WITH semester_a AS (
  ...
),
semester_b AS (
  ...
)
SELECT ...
FROM semester_a a
INNER JOIN semester_b b ON a.student_id = b.student_id  -- ✅ INNER JOIN
```

**❌ DO NOT use FULL OUTER JOIN for temporal comparisons:**
- FULL OUTER JOIN includes students who only appear in one semester
- Students who graduated after Semester A should NOT be counted as "decreased"
- New students in Semester B should NOT be counted as "increased"

**Query patterns that require INNER JOIN:**
- "Students who increased/decreased course load from X to Y"
- "Compare enrollment patterns between X and Y"
- "Track student behavior from X to Y"
- Any query using "from [semester] to [semester]"

**Exception:** Use FULL OUTER JOIN only when explicitly asked to include:
- "Students who graduated after ..."
- "New enrollments in ..."
- "All students in either semester"

DO NOT use `student_status = 'Active'` for Semester-to-Semester Comparisons. Only use this filter when you are explicity asked to do so (when query says "active students")

### Student-Focused Aggregation Patterns

| User Asks About | SQL Pattern |
|-----------------|-------------|
| "How many students..." | `COUNT(DISTINCT student_id)` - ALWAYS use DISTINCT |
| "How many courses per student..." | `COUNT(DISTINCT course_id) ... GROUP BY student_id` |
| "List students..." | `SELECT DISTINCT student_id, student_first_name, student_last_name, ...` |
| "students by major" | `GROUP BY student_major` |
| "students by GPA range" | `WHERE student_gpa BETWEEN x AND y` or `WHERE student_gpa > x` |
| "students in department" | `WHERE student_department_name = 'Dept Name'` |
| "students from X to Y" | Use INNER JOIN - see "Semester-to-Semester Comparisons" above |

## Data Quality Notes

- **Multiple rows per student**: Each row is one student-course enrollment
- **Always use DISTINCT for student counts**: `COUNT(DISTINCT student_id)`
- **Always use DISTINCT for course counts per student**: `COUNT(DISTINCT course_id)`
- **Column naming**: Pay attention to prefixes (`student_*`, `course_*`, `course_instructor_*`)
- **No pre-calculated fields**: Calculate counts, rates, and metrics in your SQL
- **Student-level aggregates**: When aggregating student attributes (like GPA), consider using a CTE with DISTINCT student_id first

## Result Validation

After generating SQL, verify:
- [ ] Used `COUNT(DISTINCT student_id)` for student counts
- [ ] Used `COUNT(DISTINCT course_id)` when counting courses per student
- [ ] Filtered by `course_semester = 'Fall 2025'` for current data
- [ ] Used correct column names with prefixes (`student_*`, `course_*`, etc.)
- [ ] **CRITICAL:** Included all three filters for ANY query counting students in current semester:
  - [ ] `student_enrollment_status = 'Enrolled'`
  - [ ] `student_status = 'Active'`
  - [ ] `course_semester = 'Fall 2025'`
- [ ] **CRITICAL:** For semester-to-semester comparisons, used INNER JOIN (not FULL OUTER JOIN)
- [ ] Used DISTINCT or CTE to avoid duplicate student rows when needed
- [ ] Calculated metrics (not assuming pre-calculated columns exist)
