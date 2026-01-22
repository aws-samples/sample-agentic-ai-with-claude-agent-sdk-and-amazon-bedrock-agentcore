---
name: enrollment-analytics
description: Analyze student enrollment trends, course capacity utilization, enrollment patterns by semester/department/major, student retention, course popularity, and over-enrolled or under-enrolled courses. Use when user asks about enrollment, course registration, capacity planning, or enrollment status tracking.
---

# Enrollment Analytics

## Primary Table
**student_enrollment_analytics** - Metadata: `data/metadata/student_enrollment_analytics.yaml`

## Related Tables
- **student_activity_engagement** - Extracurricular involvement
- **library_usage_patterns** - Library utilization
- **department_summary_metrics** - Department-level enrollment

## Pre-Calculated Metrics
- Utilization: `utilization_rate_pct`, `current_enrollment_count`, `course_max_enrollment`
- Flags: `is_current_semester`, `days_since_enrollment`

## Key Thresholds
**Utilization Rate:**
- >= 100%: Over-enrolled (need more sections)
- 90-99%: Near capacity (popular)
- 50-89%: Healthy enrollment
- < 50%: Under-enrolled (may cancel)

**Enrollment Status Values:**
- 'Enrolled': Currently active
- 'Dropped': Student dropped course
- 'Completed': Student finished course
- 'Waitlisted': Student on waitlist

## Query Patterns

**CRITICAL RULE: When querying for "current" or "currently enrolled" students, or if the current status in natural language is inferred, ALWAYS use ALL THREE filters:**
```sql
WHERE enrollment_status = 'Enrolled'    -- Active course enrollment
  AND student_status = 'Active'         -- Active university student
  AND is_current_semester = true        -- Current semester only
```
This applies to ANY query asking about:
- "currently enrolled students"
- "current enrollment"
- "students enrolled this semester"
- "active students"
- Present-tense enrollment questions

### Currently Enrolled Students
```sql
SELECT COUNT(DISTINCT student_id) as total_enrolled_students
FROM student_enrollment_analytics
WHERE enrollment_status = 'Enrolled'
  AND student_status = 'Active'
  AND is_current_semester = true
```

### Over-Enrolled Courses
```sql
SELECT course_code, course_name, department_name,
       instructor_first_name, instructor_last_name,
       course_max_enrollment, current_enrollment_count, utilization_rate_pct
FROM student_enrollment_analytics
WHERE utilization_rate_pct >= 100 AND is_current_semester = true
GROUP BY course_code, course_name, department_name,
         instructor_first_name, instructor_last_name,
         course_max_enrollment, current_enrollment_count, utilization_rate_pct
ORDER BY utilization_rate_pct DESC
```

### Enrollment by Department
```sql
SELECT department_name,
       COUNT(DISTINCT student_id) as unique_students,
       COUNT(DISTINCT course_id) as total_courses,
       COUNT(*) as total_enrollments
FROM student_enrollment_analytics
WHERE enrollment_status = 'Enrolled' AND is_current_semester = true
GROUP BY department_name
ORDER BY total_enrollments DESC
```

### Enrollment Trends Over Time
```sql
SELECT course_semester, enrollment_year, enrollment_quarter,
       COUNT(DISTINCT student_id) as unique_students,
       COUNT(*) as total_enrollments
FROM student_enrollment_analytics
WHERE enrollment_status = 'Enrolled'
GROUP BY course_semester, enrollment_year, enrollment_quarter
ORDER BY enrollment_year DESC, enrollment_quarter DESC
```

### Most Popular Courses
```sql
SELECT course_code, course_name, department_name,
       COUNT(DISTINCT student_id) as enrollment_count,
       AVG(utilization_rate_pct) as avg_utilization
FROM student_enrollment_analytics
WHERE enrollment_status = 'Enrolled' AND is_current_semester = true
GROUP BY course_code, course_name, department_name
ORDER BY enrollment_count DESC
LIMIT 20
```

### Students by Major
```sql
SELECT student_major, COUNT(DISTINCT student_id) as student_count,
       AVG(student_gpa) as avg_gpa, AVG(student_credits_completed) as avg_credits
FROM student_enrollment_analytics
WHERE student_status = 'Active'
GROUP BY student_major
ORDER BY student_count DESC
```

## Complex Scenarios

### Capacity Planning
```sql
SELECT course_code, course_name,
       COUNT(*) as times_offered,
       AVG(utilization_rate_pct) as avg_utilization,
       MAX(current_enrollment_count) as peak_enrollment
FROM student_enrollment_analytics
WHERE enrollment_status = 'Enrolled'
GROUP BY course_code, course_name
HAVING AVG(utilization_rate_pct) >= 90
ORDER BY avg_utilization DESC
```
Recommendation: If avg_utilization > 95%, consider adding sections

### Department Comparison
```sql
SELECT department_name,
       COUNT(DISTINCT course_code) as courses_offered,
       COUNT(DISTINCT student_id) as total_students,
       AVG(utilization_rate_pct) as avg_utilization,
       COUNT(DISTINCT instructor_id) as instructor_count
FROM student_enrollment_analytics
WHERE enrollment_status = 'Enrolled' AND is_current_semester = true
GROUP BY department_name
ORDER BY total_students DESC
```

### Enrollment Velocity
```sql
SELECT course_code, course_name,
       AVG(days_since_enrollment) as avg_days_enrolled,
       COUNT(*) as total_enrollments
FROM student_enrollment_analytics
WHERE enrollment_status = 'Enrolled' AND is_current_semester = true
GROUP BY course_code, course_name
ORDER BY avg_days_enrolled ASC
```
Insight: Low avg_days_enrolled indicates recent/late enrollments

## Visualizations
- Bar Chart: Enrollment by department or major
- Line Chart: Enrollment trends over semesters
- Scatter Plot: Utilization rate vs enrollment
- Heatmap: Enrollment patterns by department and semester
