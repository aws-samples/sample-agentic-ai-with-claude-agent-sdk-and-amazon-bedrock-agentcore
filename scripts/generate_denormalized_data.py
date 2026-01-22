#!/usr/bin/env python3
"""
Generate denormalized analytics tables optimized for AI agent queries.
Following the design principle: each table answers specific business questions
without requiring joins.
"""

import csv
import random
from datetime import datetime, timedelta
from pathlib import Path
from faker import Faker

fake = Faker()
Faker.seed(42)
random.seed(42)

OUTPUT_DIR = Path(__file__).parent.parent / "data" / "demo_data"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Configuration
NUM_STUDENTS = 10000
NUM_COURSES = 500
NUM_INSTRUCTORS = 200
NUM_DEPARTMENTS = 20


def generate_base_data():
    """Generate base data that will be denormalized into analytics tables."""
    print("Generating base data for denormalization...")

    # Departments
    department_names = [
        "Computer Science", "Mathematics", "Physics", "Chemistry", "Biology",
        "English", "History", "Psychology", "Economics", "Business Administration",
        "Engineering", "Nursing", "Education", "Art", "Music",
        "Philosophy", "Sociology", "Political Science", "Communications", "Statistics"
    ]

    departments = []
    for dept_id, dept_name in enumerate(department_names, 1):
        departments.append({
            'id': dept_id,
            'name': dept_name,
            'dean': fake.name(),
            'building': f"{fake.last_name()} Hall",
            'budget': random.randint(500000, 5000000),
            'established_year': random.randint(1950, 2010)
        })

    # Instructors
    instructors = []
    ranks = ['Professor', 'Associate Professor', 'Assistant Professor', 'Lecturer', 'Adjunct']
    for i in range(1, NUM_INSTRUCTORS + 1):
        dept = random.choice(departments)
        instructors.append({
            'id': i,
            'first_name': fake.first_name(),
            'last_name': fake.last_name(),
            'email': fake.email(),
            'department_id': dept['id'],
            'department_name': dept['name'],
            'rank': random.choice(ranks),
            'hire_date': fake.date_between(start_date='-20y', end_date='today'),
            'office': f"{random.randint(100, 999)}{random.choice(['A', 'B', 'C'])}",
            'salary': random.randint(60000, 180000)
        })

    # Students
    students = []
    majors = ['Computer Science', 'Business', 'Engineering', 'Biology', 'Psychology',
              'Economics', 'Mathematics', 'English', 'History', 'Physics']
    for i in range(1, NUM_STUDENTS + 1):
        enrollment_date = fake.date_between(start_date='-4y', end_date='today')
        students.append({
            'id': i,
            'first_name': fake.first_name(),
            'last_name': fake.last_name(),
            'email': fake.email(),
            'dob': fake.date_of_birth(minimum_age=18, maximum_age=35),
            'gender': random.choice(['M', 'F', 'Other']),
            'enrollment_date': enrollment_date,
            'major': random.choice(majors),
            'gpa': round(random.uniform(2.0, 4.0), 2),
            'credits_completed': random.randint(0, 120),
            'status': random.choice(['Active', 'Active', 'Active', 'Active', 'Graduated', 'On Leave']),
            'cohort_year': enrollment_date.year
        })

    # Courses
    courses = []
    course_types = ['Lecture', 'Lab', 'Seminar', 'Workshop', 'Online']
    semesters = ['Fall 2024', 'Spring 2024', 'Fall 2023', 'Spring 2023']
    for i in range(1, NUM_COURSES + 1):
        dept = random.choice(departments)
        instructor = random.choice([inst for inst in instructors if inst['department_id'] == dept['id']])
        courses.append({
            'id': i,
            'code': f"{dept['name'][:3].upper()}{random.randint(100, 499)}",
            'name': f"{fake.catch_phrase()} in {dept['name']}",
            'department_id': dept['id'],
            'department_name': dept['name'],
            'instructor_id': instructor['id'],
            'instructor_name': f"{instructor['first_name']} {instructor['last_name']}",
            'instructor_rank': instructor['rank'],
            'credits': random.choice([3, 4, 5]),
            'type': random.choice(course_types),
            'max_enrollment': random.randint(20, 200),
            'semester': random.choice(semesters),
            'room': f"{random.randint(100, 999)}"
        })

    return departments, instructors, students, courses


def generate_student_enrollment_analytics(students, courses, departments, instructors):
    """Generate denormalized enrollment analytics table."""
    print("Generating student_enrollment_analytics...")

    data = []
    enrollment_id = 1

    # Create enrollments (denormalized with all context)
    for _ in range(50000):
        student = random.choice(students)
        course = random.choice(courses)
        enrollment_date = fake.date_between(start_date='-2y', end_date='today')

        # Get full department context
        dept = next(d for d in departments if d['id'] == course['department_id'])
        instructor = next(i for i in instructors if i['id'] == course['instructor_id'])

        # Calculate metrics
        current_enrollment = random.randint(10, course['max_enrollment'])
        utilization_rate = round((current_enrollment / course['max_enrollment']) * 100, 2)

        data.append({
            # Student context (denormalized)
            'student_id': student['id'],
            'student_first_name': student['first_name'],
            'student_last_name': student['last_name'],
            'student_email': student['email'],
            'student_major': student['major'],
            'student_gpa': student['gpa'],
            'student_status': student['status'],
            'student_enrollment_date': student['enrollment_date'],
            'student_credits_completed': student['credits_completed'],

            # Course context (denormalized)
            'course_id': course['id'],
            'course_code': course['code'],
            'course_name': course['name'],
            'course_credits': course['credits'],
            'course_type': course['type'],
            'course_semester': course['semester'],
            'course_max_enrollment': course['max_enrollment'],
            'course_room_number': course['room'],

            # Department context (denormalized)
            'department_id': dept['id'],
            'department_name': dept['name'],
            'dean_name': dept['dean'],
            'building_name': dept['building'],

            # Instructor context (denormalized)
            'instructor_id': instructor['id'],
            'instructor_first_name': instructor['first_name'],
            'instructor_last_name': instructor['last_name'],
            'instructor_rank': instructor['rank'],
            'instructor_email': instructor['email'],

            # Enrollment facts
            'enrollment_id': enrollment_id,
            'enrollment_date': enrollment_date,
            'enrollment_status': random.choice(['Enrolled', 'Enrolled', 'Enrolled', 'Dropped', 'Completed']),
            'current_enrollment_count': current_enrollment,
            'utilization_rate_pct': utilization_rate,

            # Time dimensions
            'enrollment_year': enrollment_date.year,
            'enrollment_month': enrollment_date.month,
            'enrollment_quarter': (enrollment_date.month - 1) // 3 + 1,
            'is_current_semester': course['semester'] == 'Fall 2024',
            'days_since_enrollment': (datetime.now().date() - enrollment_date).days
        })
        enrollment_id += 1

    with open(OUTPUT_DIR / 'student_enrollment_analytics.csv', 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)

    return data


def generate_student_academic_performance(students, courses, instructors, departments):
    """Generate denormalized academic performance table."""
    print("Generating student_academic_performance...")

    data = []
    grades = ['A', 'A-', 'B+', 'B', 'B-', 'C+', 'C', 'C-', 'D', 'F']
    grade_points = {'A': 4.0, 'A-': 3.7, 'B+': 3.3, 'B': 3.0, 'B-': 2.7,
                    'C+': 2.3, 'C': 2.0, 'C-': 1.7, 'D': 1.0, 'F': 0.0}

    for grade_id in range(1, 45001):
        student = random.choice(students)
        course = random.choice(courses)
        dept = next(d for d in departments if d['id'] == course['department_id'])
        instructor = next(i for i in instructors if i['id'] == course['instructor_id'])

        letter_grade = random.choice(grades)
        numeric_grade = grade_points[letter_grade]
        percentage = round(random.uniform(60, 100) if numeric_grade > 0 else random.uniform(0, 60), 1)

        # Calculate student-level metrics
        total_courses = random.randint(5, 30)
        courses_passed = int(total_courses * random.uniform(0.7, 1.0))
        courses_failed = total_courses - courses_passed

        data.append({
            # Student context
            'student_id': student['id'],
            'student_first_name': student['first_name'],
            'student_last_name': student['last_name'],
            'student_email': student['email'],
            'student_major': student['major'],
            'student_overall_gpa': student['gpa'],
            'student_status': student['status'],
            'student_credits_completed': student['credits_completed'],
            'student_cohort_year': student['cohort_year'],

            # Course context
            'course_id': course['id'],
            'course_code': course['code'],
            'course_name': course['name'],
            'course_credits': course['credits'],
            'department_name': dept['name'],
            'course_level': int(course['code'][-3]),
            'course_type': course['type'],

            # Instructor context
            'instructor_id': instructor['id'],
            'instructor_name': f"{instructor['first_name']} {instructor['last_name']}",
            'instructor_rank': instructor['rank'],
            'instructor_avg_rating': round(random.uniform(3.0, 5.0), 2),
            'instructor_department': dept['name'],

            # Grade facts
            'grade_id': grade_id,
            'letter_grade': letter_grade,
            'numeric_grade': numeric_grade,
            'percentage_score': percentage,
            'semester': course['semester'],
            'grade_date': fake.date_between(start_date='-2y', end_date='today'),

            # Performance metrics (pre-calculated)
            'student_semester_gpa': round(random.uniform(2.0, 4.0), 2),
            'student_cumulative_gpa': student['gpa'],
            'course_avg_grade': round(random.uniform(2.5, 3.5), 2),
            'course_grade_percentile': random.randint(1, 100),
            'grade_points_earned': numeric_grade * course['credits'],

            # Flags
            'is_passing': numeric_grade >= 2.0,
            'is_honor_roll': student['gpa'] >= 3.5,
            'is_at_risk': student['gpa'] < 2.5,
            'is_dean_list': student['gpa'] >= 3.7,

            # Aggregations
            'student_total_courses': total_courses,
            'student_courses_passed': courses_passed,
            'student_courses_failed': courses_failed,
            'pass_rate_pct': round((courses_passed / total_courses) * 100, 2)
        })

    with open(OUTPUT_DIR / 'student_academic_performance.csv', 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)

    return data


def generate_financial_summary_by_student(students, departments):
    """Generate denormalized financial summary table."""
    print("Generating financial_summary_by_student...")

    data = []

    for student in students:
        dept = next((d for d in departments if d['name'] == student['major']), departments[0])

        # Calculate financial metrics
        total_tuition_paid = round(random.uniform(5000, 60000), 2)
        total_scholarships = round(random.uniform(0, 25000), 2)
        outstanding_balance = round(random.uniform(0, 5000), 2)

        completed_payments = random.randint(1, 15)
        pending_payments = random.randint(0, 2)
        failed_payments = random.randint(0, 1)
        total_payments = completed_payments + pending_payments + failed_payments

        data.append({
            # Student context
            'student_id': student['id'],
            'student_first_name': student['first_name'],
            'student_last_name': student['last_name'],
            'student_email': student['email'],
            'student_major': student['major'],
            'student_status': student['status'],
            'student_gpa': student['gpa'],
            'student_enrollment_date': student['enrollment_date'],

            # Department context
            'department_name': dept['name'],
            'department_id': dept['id'],

            # Payment aggregations (pre-calculated)
            'total_tuition_paid': total_tuition_paid,
            'total_tuition_due': total_tuition_paid + outstanding_balance,
            'outstanding_balance': outstanding_balance,
            'total_payments_count': total_payments,
            'completed_payments_count': completed_payments,
            'pending_payments_count': pending_payments,
            'failed_payments_count': failed_payments,
            'last_payment_date': fake.date_between(start_date='-1y', end_date='today'),
            'last_payment_amount': round(random.uniform(1000, 10000), 2),
            'last_payment_method': random.choice(['Credit Card', 'Bank Transfer', 'Check', 'Financial Aid']),

            # Payment method breakdown
            'credit_card_payments_total': round(total_tuition_paid * random.uniform(0.3, 0.6), 2),
            'bank_transfer_total': round(total_tuition_paid * random.uniform(0.2, 0.4), 2),
            'check_payments_total': round(total_tuition_paid * random.uniform(0.05, 0.15), 2),
            'financial_aid_total': round(total_tuition_paid * random.uniform(0.1, 0.25), 2),

            # Scholarship aggregations (pre-calculated)
            'total_scholarships_received': total_scholarships,
            'scholarship_count': random.randint(0, 3) if total_scholarships > 0 else 0,
            'merit_scholarships_total': round(total_scholarships * random.uniform(0.4, 0.7), 2) if total_scholarships > 0 else 0,
            'need_based_scholarships_total': round(total_scholarships * random.uniform(0.2, 0.5), 2) if total_scholarships > 0 else 0,
            'athletic_scholarships_total': round(total_scholarships * random.uniform(0, 0.3), 2) if total_scholarships > 0 else 0,
            'departmental_scholarships_total': round(total_scholarships * random.uniform(0.1, 0.3), 2) if total_scholarships > 0 else 0,
            'largest_scholarship_amount': round(total_scholarships * random.uniform(0.5, 1.0), 2) if total_scholarships > 0 else 0,
            'latest_scholarship_date': fake.date_between(start_date='-1y', end_date='today') if total_scholarships > 0 else None,

            # Financial metrics (pre-calculated)
            'net_tuition_after_scholarships': total_tuition_paid - total_scholarships,
            'scholarship_coverage_rate_pct': round((total_scholarships / (total_tuition_paid + 0.01)) * 100, 2),
            'payment_success_rate_pct': round((completed_payments / total_payments) * 100, 2),
            'avg_payment_amount': round(total_tuition_paid / max(completed_payments, 1), 2),

            # Semester breakdown
            'fall_2024_tuition': round(total_tuition_paid * 0.25, 2),
            'fall_2024_scholarships': round(total_scholarships * 0.25, 2),
            'spring_2024_tuition': round(total_tuition_paid * 0.25, 2),
            'spring_2024_scholarships': round(total_scholarships * 0.25, 2),
            'fall_2023_tuition': round(total_tuition_paid * 0.25, 2),
            'fall_2023_scholarships': round(total_scholarships * 0.25, 2),

            # Flags
            'has_outstanding_balance': outstanding_balance > 0,
            'is_scholarship_recipient': total_scholarships > 0,
            'is_payment_plan_active': pending_payments > 0,
            'is_financial_aid_recipient': total_scholarships > 5000
        })

    with open(OUTPUT_DIR / 'financial_summary_by_student.csv', 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)

    return data


def generate_course_performance_analytics(courses, departments, instructors):
    """Generate denormalized course performance analytics table."""
    print("Generating course_performance_analytics...")

    data = []

    for course in courses:
        dept = next(d for d in departments if d['id'] == course['department_id'])
        instructor = next(i for i in instructors if i['id'] == course['instructor_id'])

        # Enrollment metrics
        total_enrolled = random.randint(10, course['max_enrollment'])
        total_completed = int(total_enrolled * random.uniform(0.85, 0.98))
        total_dropped = total_enrolled - total_completed
        current_enrollment = total_enrolled - total_dropped

        # Grade metrics
        total_grades = total_completed
        avg_numeric_grade = round(random.uniform(2.5, 3.8), 2)
        a_count = int(total_grades * random.uniform(0.15, 0.35))
        b_count = int(total_grades * random.uniform(0.25, 0.40))
        c_count = int(total_grades * random.uniform(0.15, 0.30))
        d_count = int(total_grades * random.uniform(0.05, 0.15))
        f_count = total_grades - (a_count + b_count + c_count + d_count)

        # Feedback metrics
        feedback_count = random.randint(5, total_enrolled)
        avg_rating = round(random.uniform(3.0, 5.0), 2)

        data.append({
            # Course context
            'course_id': course['id'],
            'course_code': course['code'],
            'course_name': course['name'],
            'course_credits': course['credits'],
            'course_type': course['type'],
            'course_level': int(course['code'][-3]),
            'semester': course['semester'],
            'max_enrollment': course['max_enrollment'],

            # Department context
            'department_id': dept['id'],
            'department_name': dept['name'],
            'dean_name': dept['dean'],
            'department_budget': dept['budget'],
            'building_name': dept['building'],

            # Instructor context
            'instructor_id': instructor['id'],
            'instructor_first_name': instructor['first_name'],
            'instructor_last_name': instructor['last_name'],
            'instructor_rank': instructor['rank'],
            'instructor_email': instructor['email'],
            'instructor_hire_date': instructor['hire_date'],
            'instructor_salary': instructor['salary'],
            'instructor_office': instructor['office'],

            # Enrollment metrics (pre-aggregated)
            'total_enrolled': total_enrolled,
            'total_completed': total_completed,
            'total_dropped': total_dropped,
            'current_enrollment': current_enrollment,
            'enrollment_rate_pct': round((current_enrollment / course['max_enrollment']) * 100, 2),
            'drop_rate_pct': round((total_dropped / total_enrolled) * 100, 2),

            # Grade metrics (pre-aggregated)
            'total_grades': total_grades,
            'avg_numeric_grade': avg_numeric_grade,
            'avg_gpa': avg_numeric_grade,
            'median_grade': round(random.uniform(2.5, 3.5), 2),
            'mode_letter_grade': random.choice(['A', 'B+', 'B', 'C+']),
            'a_grade_count': a_count,
            'b_grade_count': b_count,
            'c_grade_count': c_count,
            'd_grade_count': d_count,
            'f_grade_count': f_count,
            'pass_rate_pct': round(((total_grades - f_count) / total_grades) * 100, 2),
            'fail_rate_pct': round((f_count / total_grades) * 100, 2),

            # Student feedback metrics (pre-aggregated)
            'total_feedback_count': feedback_count,
            'avg_overall_rating': avg_rating,
            'avg_course_content_rating': round(random.uniform(3.0, 5.0), 2),
            'avg_instructor_rating': round(random.uniform(3.0, 5.0), 2),
            'avg_difficulty_rating': round(random.uniform(2.0, 4.5), 2),
            'avg_workload_rating': round(random.uniform(2.5, 4.5), 2),
            'would_recommend_pct': round(random.uniform(60, 95), 2),

            # Attendance metrics (pre-aggregated)
            'avg_attendance_rate_pct': round(random.uniform(75, 95), 2),
            'absent_count_avg': round(random.uniform(1, 5), 1),
            'late_count_avg': round(random.uniform(0.5, 3), 1),
            'excused_absence_avg': round(random.uniform(0.5, 2), 1),

            # Comparative metrics
            'course_grade_vs_dept_avg': round(random.uniform(-0.3, 0.3), 2),
            'course_rating_vs_dept_avg': round(random.uniform(-0.5, 0.5), 2),
            'course_difficulty_vs_grade_correlation': round(random.uniform(-0.7, 0.3), 2),

            # Flags
            'is_high_enrollment': current_enrollment > course['max_enrollment'] * 0.9,
            'is_high_failure_rate': f_count / total_grades > 0.15,
            'is_highly_rated': avg_rating >= 4.5,
            'is_difficult_course': avg_numeric_grade < 2.8
        })

    with open(OUTPUT_DIR / 'course_performance_analytics.csv', 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)

    return data


def generate_instructor_performance_summary(instructors, departments, courses):
    """Generate denormalized instructor performance summary table."""
    print("Generating instructor_performance_summary...")

    data = []

    for instructor in instructors:
        dept = next(d for d in departments if d['id'] == instructor['department_id'])

        # Teaching load
        instructor_courses = [c for c in courses if c['instructor_id'] == instructor['id']]
        courses_teaching = len(instructor_courses)
        total_students = sum(random.randint(10, 40) for _ in instructor_courses)
        total_credits = sum(c['credits'] for c in instructor_courses)

        # Historical metrics
        total_courses_taught = random.randint(20, 150)
        total_students_taught = random.randint(500, 5000)
        semesters_teaching = random.randint(4, 30)

        # Grade distribution
        a_pct = round(random.uniform(15, 35), 2)
        b_pct = round(random.uniform(25, 40), 2)
        c_pct = round(random.uniform(15, 30), 2)
        d_pct = round(random.uniform(5, 15), 2)
        f_pct = round(100 - (a_pct + b_pct + c_pct + d_pct), 2)

        # Ratings
        feedback_count = random.randint(50, 500)
        avg_rating = round(random.uniform(3.0, 5.0), 2)

        data.append({
            # Instructor context
            'instructor_id': instructor['id'],
            'instructor_first_name': instructor['first_name'],
            'instructor_last_name': instructor['last_name'],
            'instructor_email': instructor['email'],
            'instructor_rank': instructor['rank'],
            'instructor_hire_date': instructor['hire_date'],
            'instructor_office': instructor['office'],
            'instructor_salary': instructor['salary'],
            'years_of_service': (datetime.now().date() - instructor['hire_date']).days // 365,

            # Department context
            'department_id': dept['id'],
            'department_name': dept['name'],
            'dean_name': dept['dean'],
            'building_name': dept['building'],

            # Current semester teaching load
            'courses_teaching_count': courses_teaching,
            'total_students_current': total_students,
            'total_credits_teaching': total_credits,
            'sections_count': courses_teaching,

            # Historical teaching metrics (pre-aggregated)
            'total_courses_taught_all_time': total_courses_taught,
            'total_students_taught': total_students_taught,
            'semesters_teaching_count': semesters_teaching,

            # Grade distribution metrics (pre-aggregated)
            'avg_grade_given': round(random.uniform(2.5, 3.5), 2),
            'median_grade_given': round(random.uniform(2.5, 3.5), 2),
            'a_grade_pct': a_pct,
            'b_grade_pct': b_pct,
            'c_grade_pct': c_pct,
            'd_grade_pct': d_pct,
            'f_grade_pct': f_pct,
            'pass_rate_pct': round(100 - f_pct, 2),
            'avg_gpa_given': round(random.uniform(2.5, 3.5), 2),

            # Rating metrics (pre-aggregated)
            'total_feedback_count': feedback_count,
            'avg_overall_rating': avg_rating,
            'avg_instructor_rating': round(random.uniform(3.0, 5.0), 2),
            'avg_course_content_rating': round(random.uniform(3.0, 5.0), 2),
            'avg_difficulty_rating': round(random.uniform(2.0, 4.5), 2),
            'avg_workload_rating': round(random.uniform(2.5, 4.5), 2),
            'would_recommend_pct': round(random.uniform(60, 95), 2),

            # Student outcomes
            'student_avg_gpa_in_courses': round(random.uniform(2.5, 3.5), 2),
            'student_completion_rate': round(random.uniform(85, 98), 2),
            'student_drop_rate_pct': round(random.uniform(2, 15), 2),

            # Comparative metrics
            'rating_vs_dept_avg': round(random.uniform(-0.5, 0.5), 2),
            'grade_generosity_vs_dept_avg': round(random.uniform(-0.3, 0.3), 2),
            'workload_vs_dept_avg': round(random.uniform(-0.5, 0.5), 2),

            # Rankings (pre-calculated)
            'dept_rating_rank': random.randint(1, 20),
            'university_rating_rank': random.randint(1, 100),

            # Flags
            'is_highly_rated': avg_rating >= 4.5,
            'is_tough_grader': f_pct > 15,
            'is_easy_grader': a_pct > 30,
            'has_high_workload': random.choice([True, False]),
            'is_tenured': instructor['rank'] in ['Professor', 'Associate Professor']
        })

    with open(OUTPUT_DIR / 'instructor_performance_summary.csv', 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)

    return data


def generate_department_summary_metrics(departments, students, instructors, courses):
    """Generate denormalized department summary metrics table."""
    print("Generating department_summary_metrics...")

    data = []

    for dept in departments:
        # Student metrics
        dept_students = [s for s in students if s['major'] == dept['name']]
        total_students = len(dept_students)
        active_students = len([s for s in dept_students if s['status'] == 'Active'])
        avg_gpa = sum(s['gpa'] for s in dept_students) / max(total_students, 1)
        deans_list = len([s for s in dept_students if s['gpa'] >= 3.7])
        at_risk = len([s for s in dept_students if s['gpa'] < 2.5])

        # Instructor metrics
        dept_instructors = [i for i in instructors if i['department_id'] == dept['id']]
        total_instructors = len(dept_instructors)
        professors = len([i for i in dept_instructors if i['rank'] == 'Professor'])
        assoc_profs = len([i for i in dept_instructors if i['rank'] == 'Associate Professor'])
        asst_profs = len([i for i in dept_instructors if i['rank'] == 'Assistant Professor'])
        lecturers = len([i for i in dept_instructors if i['rank'] == 'Lecturer'])
        adjuncts = len([i for i in dept_instructors if i['rank'] == 'Adjunct'])
        avg_salary = sum(i['salary'] for i in dept_instructors) / max(total_instructors, 1)

        # Course metrics
        dept_courses = [c for c in courses if c['department_id'] == dept['id']]
        total_courses = len(dept_courses)
        total_enrollments = sum(random.randint(10, 40) for _ in dept_courses)
        avg_class_size = total_enrollments / max(total_courses, 1)

        # Financial metrics
        tuition_revenue = total_students * random.uniform(20000, 50000)
        scholarships = tuition_revenue * random.uniform(0.1, 0.3)
        net_revenue = tuition_revenue - scholarships

        data.append({
            # Department context
            'department_id': dept['id'],
            'department_name': dept['name'],
            'dean_name': dept['dean'],
            'building_name': dept['building'],
            'established_year': random.randint(1950, 2010),
            'budget_amount': dept['budget'],

            # Student metrics (pre-aggregated)
            'total_students_enrolled': total_students,
            'total_students_active': active_students,
            'total_students_graduated': int(total_students * random.uniform(0.1, 0.3)),
            'avg_student_gpa': round(avg_gpa, 2),
            'students_on_deans_list': deans_list,
            'students_at_risk': at_risk,

            # Instructor metrics (pre-aggregated)
            'total_instructors': total_instructors,
            'professor_count': professors,
            'associate_prof_count': assoc_profs,
            'assistant_prof_count': asst_profs,
            'lecturer_count': lecturers,
            'adjunct_count': adjuncts,
            'avg_instructor_rating': round(random.uniform(3.5, 4.8), 2),
            'avg_instructor_salary': round(avg_salary, 2),

            # Course metrics (pre-aggregated)
            'total_courses_offered': total_courses,
            'total_enrollments': total_enrollments,
            'avg_class_size': round(avg_class_size, 1),
            'avg_course_rating': round(random.uniform(3.5, 4.8), 2),
            'avg_pass_rate_pct': round(random.uniform(80, 95), 2),
            'avg_course_grade': round(random.uniform(2.8, 3.5), 2),

            # Financial metrics (pre-aggregated)
            'total_tuition_revenue': round(tuition_revenue, 2),
            'total_scholarships_distributed': round(scholarships, 2),
            'net_revenue': round(net_revenue, 2),
            'budget_per_student': round(dept['budget'] / max(total_students, 1), 2),
            'revenue_per_instructor': round(tuition_revenue / max(total_instructors, 1), 2),

            # Growth metrics (pre-calculated)
            'enrollment_yoy_growth_pct': round(random.uniform(-5, 15), 2),
            'revenue_yoy_growth_pct': round(random.uniform(-3, 12), 2),
            'graduation_rate_pct': round(random.uniform(65, 90), 2),
            'retention_rate_pct': round(random.uniform(80, 95), 2),

            # Semester comparisons
            'fall_2024_enrollment': int(total_students * 0.55),
            'spring_2024_enrollment': int(total_students * 0.45),
            'fall_2023_enrollment': int(total_students * 0.52),
            'enrollment_trend': random.choice(['Growing', 'Stable', 'Declining']),

            # Rankings (pre-calculated)
            'enrollment_rank': random.randint(1, 10),
            'gpa_rank': random.randint(1, 10),
            'rating_rank': random.randint(1, 10),
            'revenue_rank': random.randint(1, 10),
            'graduation_rate_rank': random.randint(1, 10),

            # Flags
            'is_growing_enrollment': random.choice([True, False]),
            'is_high_performing': avg_gpa >= 3.3,
            'is_budget_efficient': random.choice([True, False]),
            'has_scholarship_program': scholarships > 0
        })

    with open(OUTPUT_DIR / 'department_summary_metrics.csv', 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)

    return data


def generate_student_activity_engagement(students, departments):
    """Generate denormalized student activity engagement table."""
    print("Generating student_activity_engagement...")

    data = []
    activity_types = ['Sports', 'Academic Club', 'Volunteer', 'Cultural Club', 'Student Government']
    activities = [
        'Basketball Team', 'Computer Science Club', 'Volunteer Corps', 'Cultural Society',
        'Student Senate', 'Debate Team', 'Math Club', 'Community Service', 'Drama Club',
        'Engineering Society', 'Chess Club', 'Environmental Club', 'Music Ensemble'
    ]

    for _ in range(15000):  # Generate 15K activity participation records
        student = random.choice(students)
        dept = next((d for d in departments if d['name'] == student['major']), departments[0])
        activity_name = random.choice(activities)
        activity_type = random.choice(activity_types)

        hours_per_week = round(random.uniform(2, 15), 1)
        weeks_active = random.randint(4, 40)
        total_hours = hours_per_week * weeks_active

        # Calculate engagement metrics
        total_activities = random.randint(1, 5)
        active_activities = random.randint(1, total_activities)
        leadership_positions = random.randint(0, 2)

        data.append({
            # Student context (denormalized)
            'student_id': student['id'],
            'student_first_name': student['first_name'],
            'student_last_name': student['last_name'],
            'student_email': student['email'],
            'student_major': student['major'],
            'student_gpa': student['gpa'],
            'student_status': student['status'],
            'student_year': random.choice(['Freshman', 'Sophomore', 'Junior', 'Senior']),
            'student_credits_completed': student['credits_completed'],

            # Department context
            'department_name': dept['name'],
            'department_id': dept['id'],

            # Activity details (denormalized per activity)
            'activity_id': fake.uuid4(),
            'activity_name': activity_name,
            'activity_type': activity_type,
            'student_role': random.choice(['Member', 'Officer', 'President', 'Vice President', 'Secretary']),
            'activity_status': random.choice(['Active', 'Inactive', 'Completed']),
            'join_date': fake.date_between(start_date='-2y', end_date='today'),
            'hours_per_week': hours_per_week,
            'total_hours_committed': total_hours,

            # Aggregated metrics (pre-calculated)
            'total_activities': total_activities,
            'active_activities_count': active_activities,
            'leadership_positions_count': leadership_positions,
            'total_hours_per_week': round(hours_per_week * total_activities, 1),
            'total_community_service_hours': round(total_hours * 0.3, 1) if activity_type == 'Volunteer' else 0,
            'total_academic_society_hours': round(total_hours * 0.4, 1) if activity_type == 'Academic Club' else 0,

            # Activity type breakdown
            'sports_activities_count': 1 if activity_type == 'Sports' else 0,
            'academic_clubs_count': 1 if activity_type == 'Academic Club' else 0,
            'volunteer_activities_count': 1 if activity_type == 'Volunteer' else 0,
            'cultural_clubs_count': 1 if activity_type == 'Cultural Club' else 0,

            # Engagement metrics
            'engagement_score': round(random.uniform(50, 100), 2),
            'is_highly_engaged': total_activities >= 3,
            'weeks_active': weeks_active,
            'semesters_active': weeks_active // 16,

            # Correlation metrics
            'gpa_vs_activity_hours': round(random.uniform(-0.5, 0.5), 2),
            'retention_risk_score': round(random.uniform(0, 100), 2),

            # Flags
            'is_student_leader': leadership_positions > 0,
            'is_athlete': activity_type == 'Sports',
            'is_volunteer': activity_type == 'Volunteer',
            'is_academic_club_member': activity_type == 'Academic Club',
            'has_multiple_activities': total_activities > 1
        })

    with open(OUTPUT_DIR / 'student_activity_engagement.csv', 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)

    return data


def generate_attendance_behavior_analytics(students, courses, instructors, departments):
    """Generate denormalized attendance behavior analytics table."""
    print("Generating attendance_behavior_analytics...")

    data = []

    for _ in range(30000):  # Generate 30K attendance records
        student = random.choice(students)
        course = random.choice(courses)
        dept = next(d for d in departments if d['id'] == course['department_id'])
        instructor = next(i for i in instructors if i['id'] == course['instructor_id'])

        # Attendance metrics
        total_sessions = random.randint(25, 40)
        attended = int(total_sessions * random.uniform(0.6, 1.0))
        absent = total_sessions - attended
        late = int(attended * random.uniform(0.05, 0.2))
        excused = int(absent * random.uniform(0.1, 0.5))

        attendance_rate = (attended / total_sessions) * 100

        # Student-level aggregations
        student_total_classes = random.randint(100, 200)
        student_attendance_rate = round(random.uniform(60, 98), 2)

        data.append({
            # Student context (denormalized)
            'student_id': student['id'],
            'student_first_name': student['first_name'],
            'student_last_name': student['last_name'],
            'student_email': student['email'],
            'student_major': student['major'],
            'student_gpa': student['gpa'],
            'student_status': student['status'],

            # Course context (denormalized)
            'course_id': course['id'],
            'course_code': course['code'],
            'course_name': course['name'],
            'course_credits': course['credits'],
            'instructor_name': f"{instructor['first_name']} {instructor['last_name']}",
            'department_name': dept['name'],
            'semester': course['semester'],

            # Attendance metrics (pre-aggregated)
            'total_class_sessions': total_sessions,
            'classes_attended': attended,
            'classes_absent': absent,
            'classes_late': late,
            'classes_excused': excused,
            'attendance_rate_pct': round(attendance_rate, 2),
            'absence_rate_pct': round((absent / total_sessions) * 100, 2),
            'late_rate_pct': round((late / attended) * 100, 2) if attended > 0 else 0,

            # Student-level aggregations
            'student_total_classes': student_total_classes,
            'student_attendance_rate_pct': student_attendance_rate,
            'student_chronic_absences': random.randint(0, 10),
            'student_consecutive_absences': random.randint(0, 5),

            # Course-level aggregations
            'course_avg_attendance_rate': round(random.uniform(75, 92), 2),
            'course_absent_count': random.randint(5, 20),

            # Time patterns
            'recent_week_attendance_rate': round(random.uniform(60, 100), 2),
            'recent_month_attendance_rate': round(random.uniform(65, 98), 2),
            'attendance_trend': random.choice(['Improving', 'Stable', 'Declining']),
            'last_absence_date': fake.date_between(start_date='-60d', end_date='today'),
            'days_since_last_absence': random.randint(0, 60),

            # Performance correlation
            'student_grade_in_course': round(random.uniform(1.5, 4.0), 2),
            'attendance_grade_correlation': round(random.uniform(0.3, 0.8), 2),
            'attendance_percentile': random.randint(1, 100),

            # Flags
            'is_chronic_absenteeism': attendance_rate < 70,
            'is_perfect_attendance': absent == 0,
            'has_recent_absence_pattern': random.choice([True, False]),
            'is_attendance_at_risk': attendance_rate < 75,

            # Intervention
            'absence_alert_sent': attendance_rate < 75,
            'last_alert_date': fake.date_between(start_date='-30d', end_date='today') if attendance_rate < 75 else None,
            'alert_count': random.randint(0, 3) if attendance_rate < 75 else 0
        })

    with open(OUTPUT_DIR / 'attendance_behavior_analytics.csv', 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)

    return data


def generate_scholarship_recipient_analysis(students, departments):
    """Generate denormalized scholarship recipient analysis table."""
    print("Generating scholarship_recipient_analysis...")

    data = []
    scholarship_types = ['Merit', 'Need-Based', 'Athletic', 'Departmental']
    scholarship_names = [
        'Presidential Scholarship', 'Dean\'s Scholarship', 'Athletic Excellence',
        'STEM Innovation Grant', 'Community Service Award', 'Leadership Scholarship',
        'First Generation Grant', 'Diversity Scholarship'
    ]

    for _ in range(8000):  # Generate 8K scholarship award records
        student = random.choice(students)
        dept = next((d for d in departments if d['name'] == student['major']), departments[0])

        scholarship_type = random.choice(scholarship_types)
        scholarship_amount = round(random.uniform(1000, 15000), 2)
        award_date = fake.date_between(start_date='-3y', end_date='-1y')

        # Calculate scholarship totals
        total_scholarships = random.randint(1, 3)
        total_amount = scholarship_amount * random.uniform(1.0, 2.5)

        # Type breakdown
        merit_total = round(total_amount * 0.4, 2) if scholarship_type == 'Merit' else 0
        need_based_total = round(total_amount * 0.3, 2) if scholarship_type == 'Need-Based' else 0
        athletic_total = round(total_amount * 0.5, 2) if scholarship_type == 'Athletic' else 0
        dept_total = round(total_amount * 0.3, 2) if scholarship_type == 'Departmental' else 0

        # Calculate performance since award
        gpa_at_award = round(random.uniform(3.0, 4.0), 2)
        gpa_current = student['gpa']
        gpa_change = round(gpa_current - gpa_at_award, 2)

        data.append({
            # Student context (denormalized)
            'student_id': student['id'],
            'student_first_name': student['first_name'],
            'student_last_name': student['last_name'],
            'student_email': student['email'],
            'student_major': student['major'],
            'student_status': student['status'],
            'student_enrollment_date': student['enrollment_date'],
            'student_cohort': student['cohort_year'],

            # Academic performance (denormalized)
            'current_gpa': student['gpa'],
            'cumulative_gpa': student['gpa'],
            'credits_completed': student['credits_completed'],
            'semesters_enrolled': random.randint(2, 8),
            'academic_standing': 'Good' if student['gpa'] >= 3.0 else 'Warning',

            # Scholarship details (denormalized per scholarship)
            'scholarship_id': fake.uuid4(),
            'scholarship_name': random.choice(scholarship_names),
            'scholarship_type': scholarship_type,
            'scholarship_amount': scholarship_amount,
            'award_date': award_date,
            'academic_year': f"{award_date.year}-{award_date.year + 1}",
            'is_renewable': random.choice([True, False]),
            'gpa_requirement': round(random.uniform(2.5, 3.5), 2),
            'renewal_count': random.randint(0, 3),

            # Aggregated scholarship metrics (pre-calculated)
            'total_scholarships': total_scholarships,
            'total_scholarship_amount': round(total_amount, 2),
            'merit_scholarship_total': merit_total,
            'need_based_total': need_based_total,
            'athletic_scholarship_total': athletic_total,
            'departmental_total': dept_total,
            'avg_scholarship_amount': round(total_amount / total_scholarships, 2),
            'largest_scholarship': scholarship_amount,

            # Financial context
            'total_tuition_paid': round(random.uniform(20000, 60000), 2),
            'scholarship_coverage_pct': round((total_amount / 40000) * 100, 2),
            'net_tuition_cost': round(random.uniform(10000, 50000), 2),
            'has_additional_aid': random.choice([True, False]),

            # Performance metrics (pre-calculated)
            'semesters_since_award': random.randint(1, 6),
            'gpa_at_award': gpa_at_award,
            'gpa_current': gpa_current,
            'gpa_change_since_award': gpa_change,
            'met_gpa_requirement': gpa_current >= 2.5,
            'courses_passed_since_award': random.randint(10, 40),
            'credits_earned_since_award': random.randint(30, 120),

            # Retention metrics
            'is_still_enrolled': student['status'] == 'Active',
            'retention_status': 'Retained' if student['status'] == 'Active' else 'Not Retained',
            'graduation_status': 'In Progress' if student['status'] == 'Active' else 'Graduated',
            'semesters_retained': random.randint(1, 8),
            'retention_rate_pct': round(random.uniform(85, 98), 2),

            # Comparative metrics
            'gpa_vs_non_scholarship_avg': round(random.uniform(-0.3, 0.5), 2),
            'retention_vs_non_scholarship': round(random.uniform(0, 15), 2),
            'graduation_rate_vs_average': round(random.uniform(-5, 10), 2),

            # ROI metrics (pre-calculated)
            'scholarship_per_credit_hour': round(total_amount / max(student['credits_completed'], 1), 2),
            'scholarship_roi_score': round(random.uniform(50, 100), 2),

            # Flags
            'is_scholarship_at_risk': gpa_current < 2.5,
            'is_high_performer': gpa_current >= 3.7,
            'is_scholarship_renewed': random.choice([True, False]),
            'meets_requirements': gpa_current >= 2.5
        })

    with open(OUTPUT_DIR / 'scholarship_recipient_analysis.csv', 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)

    return data


def generate_library_usage_patterns(students, departments):
    """Generate denormalized library usage patterns table."""
    print("Generating library_usage_patterns...")

    data = []
    resource_categories = ['Textbook', 'Reference', 'Fiction', 'Research Material', 'Journal']
    resource_types = ['Book', 'E-Book', 'Journal', 'Magazine', 'DVD']

    book_titles = [
        'Introduction to Algorithms', 'Calculus I', 'Modern Physics', 'World History',
        'The Great Gatsby', 'Pride and Prejudice', 'Chemistry Fundamentals',
        'Data Structures and Algorithms', 'Biology Today', 'Economics Principles'
    ]

    authors = [
        'Thomas Cormen', 'James Stewart', 'Richard Feynman', 'Howard Zinn',
        'F. Scott Fitzgerald', 'Jane Austen', 'John McMurry', 'Robert Sedgewick'
    ]

    for _ in range(20000):  # Generate 20K library checkout records
        student = random.choice(students)
        dept = next((d for d in departments if d['name'] == student['major']), departments[0])

        checkout_date = fake.date_between(start_date='-1y', end_date='today')
        due_date = checkout_date + timedelta(days=random.randint(14, 30))
        is_returned = random.choice([True, True, True, False])  # 75% returned
        return_date = fake.date_between(start_date=checkout_date, end_date='today') if is_returned else None

        # Calculate metrics
        if return_date:
            days_checked_out = (return_date - checkout_date).days
            is_overdue = return_date > due_date
            overdue_days = max(0, (return_date - due_date).days) if is_overdue else 0
        else:
            days_checked_out = (datetime.now().date() - checkout_date).days
            is_overdue = datetime.now().date() > due_date
            overdue_days = max(0, (datetime.now().date() - due_date).days) if is_overdue else 0

        overdue_fee = overdue_days * 0.50 if is_overdue else 0

        # Student usage aggregations
        total_checkouts = random.randint(5, 50)
        total_returns = int(total_checkouts * 0.85)
        total_overdue = int(total_checkouts * 0.15)

        data.append({
            # Student context (denormalized)
            'student_id': student['id'],
            'student_first_name': student['first_name'],
            'student_last_name': student['last_name'],
            'student_email': student['email'],
            'student_major': student['major'],
            'student_gpa': student['gpa'],
            'student_status': student['status'],
            'student_year': random.choice(['Freshman', 'Sophomore', 'Junior', 'Senior']),

            # Department context
            'department_name': dept['name'],
            'department_id': dept['id'],

            # Resource details (denormalized per checkout)
            'checkout_id': fake.uuid4(),
            'book_title': random.choice(book_titles),
            'author_name': random.choice(authors),
            'isbn': fake.isbn13(),
            'resource_category': random.choice(resource_categories),
            'resource_type': random.choice(resource_types),

            # Checkout details
            'checkout_date': checkout_date,
            'due_date': due_date,
            'return_date': return_date,
            'days_checked_out': days_checked_out,
            'is_returned': is_returned,
            'is_overdue': is_overdue,
            'overdue_days': overdue_days,
            'overdue_fee': round(overdue_fee, 2),

            # Student usage aggregations (pre-calculated)
            'total_checkouts': total_checkouts,
            'total_returns': total_returns,
            'total_overdue': total_overdue,
            'current_checkouts': total_checkouts - total_returns,
            'total_overdue_fees': round(total_overdue * 0.50 * random.uniform(5, 15), 2),
            'avg_checkout_duration_days': round(random.uniform(14, 25), 1),
            'overdue_rate_pct': round((total_overdue / total_checkouts) * 100, 2),

            # Resource type breakdown
            'textbook_checkouts': int(total_checkouts * 0.4),
            'reference_checkouts': int(total_checkouts * 0.2),
            'fiction_checkouts': int(total_checkouts * 0.15),
            'research_material_checkouts': int(total_checkouts * 0.25),

            # Usage patterns
            'checkouts_this_semester': random.randint(3, 15),
            'checkouts_last_30_days': random.randint(1, 5),
            'avg_checkouts_per_month': round(random.uniform(1, 5), 1),
            'usage_frequency': random.choice(['Heavy', 'Moderate', 'Light', 'Rare']),

            # Academic correlation
            'student_gpa': student['gpa'],
            'library_usage_gpa_correlation': round(random.uniform(0.2, 0.7), 2),
            'library_usage_percentile': random.randint(1, 100),

            # Flags
            'is_frequent_user': total_checkouts > 20,
            'has_overdue_items': not is_returned and is_overdue,
            'is_responsible_borrower': total_overdue / total_checkouts < 0.1,
            'has_outstanding_fees': overdue_fee > 0
        })

    with open(OUTPUT_DIR / 'library_usage_patterns.csv', 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)

    return data


def main():
    """Generate all denormalized analytics tables."""
    print("=" * 60)
    print("Generating Denormalized Analytics Tables")
    print("=" * 60)
    print()

    # Generate base data
    departments, instructors, students, courses = generate_base_data()

    # Generate denormalized analytics tables
    enrollment_data = generate_student_enrollment_analytics(students, courses, departments, instructors)
    academic_data = generate_student_academic_performance(students, courses, instructors, departments)
    financial_data = generate_financial_summary_by_student(students, departments)
    course_perf_data = generate_course_performance_analytics(courses, departments, instructors)
    instructor_perf_data = generate_instructor_performance_summary(instructors, departments, courses)
    dept_metrics_data = generate_department_summary_metrics(departments, students, instructors, courses)
    activity_data = generate_student_activity_engagement(students, departments)
    attendance_data = generate_attendance_behavior_analytics(students, courses, instructors, departments)
    scholarship_data = generate_scholarship_recipient_analysis(students, departments)
    library_data = generate_library_usage_patterns(students, departments)

    print()
    print("=" * 60)
    print("Data Generation Complete!")
    print("=" * 60)
    print(f"\nGenerated files in: {OUTPUT_DIR}")
    print(f"  1. student_enrollment_analytics.csv: {len(enrollment_data):,} records")
    print(f"  2. student_academic_performance.csv: {len(academic_data):,} records")
    print(f"  3. financial_summary_by_student.csv: {len(financial_data):,} records")
    print(f"  4. course_performance_analytics.csv: {len(course_perf_data):,} records")
    print(f"  5. instructor_performance_summary.csv: {len(instructor_perf_data):,} records")
    print(f"  6. department_summary_metrics.csv: {len(dept_metrics_data):,} records")
    print(f"  7. student_activity_engagement.csv: {len(activity_data):,} records")
    print(f"  8. attendance_behavior_analytics.csv: {len(attendance_data):,} records")
    print(f"  9. scholarship_recipient_analysis.csv: {len(scholarship_data):,} records")
    print(f" 10. library_usage_patterns.csv: {len(library_data):,} records")

    total_records = (len(enrollment_data) + len(academic_data) + len(financial_data) +
                    len(course_perf_data) + len(instructor_perf_data) + len(dept_metrics_data) +
                    len(activity_data) + len(attendance_data) + len(scholarship_data) +
                    len(library_data))
    print(f"\nTotal records across all tables: {total_records:,}")
    print("\nThese are DENORMALIZED analytics tables:")
    print("  ✓ No joins required")
    print("  ✓ All context in each table")
    print("  ✓ Pre-aggregated metrics")
    print("  ✓ Optimized for AI agent queries")


if __name__ == '__main__':
    main()
