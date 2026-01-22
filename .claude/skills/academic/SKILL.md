---
name: academic-performance
description: Analyze student GPA and academic performance, grade distributions, honor roll and dean's list students, at-risk students, course difficulty and pass/fail rates, instructor effectiveness and ratings, academic achievement by major or department, and grade comparisons. Use when user asks about grades, GPA, academic standing, course performance, or instructor evaluations.
---

# Academic Performance Analytics

## Primary Table
**student_academic_performance** - Metadata: `data/metadata/student_academic_performance.yaml`

## Related Tables
- **course_performance_analytics** - Course metrics
- **instructor_performance_summary** - Instructor metrics
- **attendance_behavior_analytics** - Attendance impact

## Pre-Calculated Metrics
- GPAs: `student_overall_gpa`, `student_semester_gpa`, `student_cumulative_gpa`
- Grades: `course_avg_grade`, `course_grade_percentile`, `pass_rate_pct`
- Counts: `student_courses_passed`, `student_courses_failed`
- Flags: `is_honor_roll`, `is_dean_list`, `is_at_risk`, `is_passing`

## Key Thresholds
- Honor roll: GPA >= 3.5
- Dean's list: GPA >= 3.75
- At risk: GPA < 2.5 or pass_rate_pct < 70

## Query Patterns

All queries filter by `student_status = 'Active'` and GROUP BY student_id to avoid duplicates.

### Top Students by GPA
```sql
SELECT student_id, student_first_name, student_last_name,
       student_major, student_overall_gpa, student_credits_completed
FROM student_academic_performance
WHERE student_status = 'Active'
GROUP BY student_id, student_first_name, student_last_name,
         student_major, student_overall_gpa, student_credits_completed
ORDER BY student_overall_gpa DESC
LIMIT 20
```

### At-Risk Students
```sql
SELECT student_id, student_first_name, student_last_name,
       student_major, student_overall_gpa, student_courses_failed, pass_rate_pct
FROM student_academic_performance
WHERE is_at_risk = true AND student_status = 'Active'
GROUP BY student_id, student_first_name, student_last_name,
         student_major, student_overall_gpa, student_courses_failed, pass_rate_pct
ORDER BY student_overall_gpa ASC
```

### Grade Distribution
```sql
SELECT letter_grade, COUNT(*) as student_count,
       ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) as percentage
FROM student_academic_performance
WHERE course_code = 'CS101' AND semester = 'Fall 2024'
GROUP BY letter_grade
ORDER BY CASE letter_grade
    WHEN 'A' THEN 1 WHEN 'B' THEN 2 WHEN 'C' THEN 3
    WHEN 'D' THEN 4 WHEN 'F' THEN 5 END
```

### GPA by Major
```sql
SELECT student_major, COUNT(DISTINCT student_id) as student_count,
       AVG(student_overall_gpa) as avg_gpa, AVG(pass_rate_pct) as avg_pass_rate
FROM student_academic_performance
WHERE student_status = 'Active'
GROUP BY student_major
ORDER BY avg_gpa DESC
```

### Honor Roll / Dean's List
```sql
SELECT student_id, student_first_name, student_last_name, student_major,
       student_overall_gpa,
       CASE WHEN is_dean_list = true THEN 'Dean''s List'
            WHEN is_honor_roll = true THEN 'Honor Roll' END as recognition
FROM student_academic_performance
WHERE (is_honor_roll = true OR is_dean_list = true)
  AND student_status = 'Active' AND semester = 'Fall 2024'
GROUP BY student_id, student_first_name, student_last_name,
         student_major, student_overall_gpa, is_dean_list, is_honor_roll
ORDER BY student_overall_gpa DESC
```

### Course Difficulty
```sql
SELECT course_code, course_name, instructor_name,
       COUNT(*) as total_students, AVG(numeric_grade) as avg_grade,
       SUM(CASE WHEN is_passing = false THEN 1 ELSE 0 END) as failed_count,
       ROUND(AVG(CASE WHEN is_passing = true THEN 100.0 ELSE 0.0 END), 2) as pass_rate
FROM student_academic_performance
WHERE semester = 'Fall 2024'
GROUP BY course_code, course_name, instructor_name
ORDER BY pass_rate ASC
LIMIT 20
```

## Complex Scenarios

### Student Performance Over Time
```sql
SELECT student_id, semester, student_semester_gpa, student_cumulative_gpa,
       student_courses_passed, student_courses_failed
FROM student_academic_performance
WHERE student_id = '12345'
GROUP BY student_id, semester, student_semester_gpa, student_cumulative_gpa,
         student_courses_passed, student_courses_failed
ORDER BY semester
```
Visualization: Line chart of GPA trend

### Instructor Effectiveness
```sql
SELECT instructor_name, instructor_rank, department_name,
       COUNT(DISTINCT course_id) as courses_taught,
       AVG(numeric_grade) as avg_grade_given,
       AVG(instructor_avg_rating) as avg_rating,
       AVG(CASE WHEN is_passing = true THEN 100.0 ELSE 0.0 END) as pass_rate
FROM student_academic_performance
WHERE semester = 'Fall 2024'
GROUP BY instructor_name, instructor_rank, department_name
HAVING COUNT(*) >= 20
ORDER BY avg_rating DESC, pass_rate DESC
```

### Department Comparison
```sql
SELECT department_name, COUNT(DISTINCT student_id) as total_students,
       AVG(student_overall_gpa) as avg_gpa,
       SUM(CASE WHEN is_honor_roll = true THEN 1 ELSE 0 END) as honor_roll_count,
       SUM(CASE WHEN is_at_risk = true THEN 1 ELSE 0 END) as at_risk_count
FROM student_academic_performance
WHERE student_status = 'Active'
GROUP BY department_name
ORDER BY avg_gpa DESC
```

## Visualizations
- Histogram: GPA distribution
- Bar Chart: Grade distribution, GPA by major
- Line Chart: GPA trends over time
- Box Plot: GPA by department
