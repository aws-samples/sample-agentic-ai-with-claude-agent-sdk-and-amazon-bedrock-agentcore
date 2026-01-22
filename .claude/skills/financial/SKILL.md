---
name: financial-analytics
description: Analyze tuition payments and revenue, outstanding balances and payment status, scholarship awards and distribution, payment methods and transaction patterns, financial aid and coverage rates, net tuition after scholarships, payment success/failure rates, and semester-wise financial breakdowns. Use when user asks about tuition, payments, scholarships, financial aid, or student finances.
---

# Financial Analytics

## Primary Table
**financial_summary_by_student** - Metadata: `data/metadata/financial_summary_by_student.yaml`

## Related Tables
- **scholarship_recipient_analysis** - Scholarship ROI and retention
- **department_summary_metrics** - Department financial metrics

## Pre-Calculated Metrics
- Tuition: `total_tuition_paid`, `outstanding_balance`, `net_tuition_after_scholarships`
- Scholarships: `total_scholarships_received`, `scholarship_coverage_rate_pct`
- Payment methods: `credit_card_payments_total`, `bank_transfer_total`, etc.
- Scholarship types: `merit_scholarships_total`, `athletic_scholarships_total`, etc.
- Success rate: `payment_success_rate_pct`
- Flags: `has_outstanding_balance`, `is_scholarship_recipient`

## Key Thresholds
**Scholarship Coverage:**
- >= 75%: Most tuition covered
- 50-74%: Significant coverage
- 25-49%: Partial coverage
- < 25%: Minimal coverage

**Payment Success:**
- >= 95%: Excellent history
- 80-94%: Good history
- 50-79%: Payment issues
- < 50%: Serious problems

## Query Patterns

All queries filter by `student_status = 'Active'` for current students.

### Outstanding Balances
```sql
SELECT student_id, student_first_name, student_last_name,
       student_major, total_tuition_paid, outstanding_balance,
       last_payment_date, last_payment_method
FROM financial_summary_by_student
WHERE has_outstanding_balance = true AND student_status = 'Active'
ORDER BY outstanding_balance DESC
```

### Total Revenue
```sql
SELECT SUM(total_tuition_paid) as total_revenue,
       SUM(total_scholarships_received) as total_scholarships_distributed,
       SUM(net_tuition_after_scholarships) as net_revenue,
       COUNT(DISTINCT student_id) as total_paying_students,
       AVG(total_tuition_paid) as avg_tuition_per_student
FROM financial_summary_by_student
WHERE student_status = 'Active'
```

### Top Scholarship Recipients
```sql
SELECT student_id, student_first_name, student_last_name,
       student_major, student_gpa, total_scholarships_received,
       scholarship_coverage_rate_pct,
       merit_scholarships_total, athletic_scholarships_total
FROM financial_summary_by_student
WHERE is_scholarship_recipient = true AND student_status = 'Active'
ORDER BY total_scholarships_received DESC
LIMIT 20
```

### Payment Method Distribution
```sql
SELECT COUNT(DISTINCT student_id) as total_students,
       SUM(credit_card_payments_total) as total_credit_card,
       SUM(bank_transfer_total) as total_bank_transfer,
       SUM(check_payments_total) as total_check,
       SUM(financial_aid_total) as total_financial_aid,
       ROUND(SUM(credit_card_payments_total) * 100.0 / SUM(total_tuition_paid), 2) as credit_card_pct
FROM financial_summary_by_student
WHERE student_status = 'Active'
```

### Scholarship by Major
```sql
SELECT student_major, COUNT(DISTINCT student_id) as student_count,
       AVG(student_gpa) as avg_gpa,
       SUM(total_scholarships_received) as total_scholarships,
       AVG(scholarship_coverage_rate_pct) as avg_coverage_rate,
       COUNT(CASE WHEN is_scholarship_recipient = true THEN 1 END) as recipients_count
FROM financial_summary_by_student
WHERE student_status = 'Active'
GROUP BY student_major
ORDER BY total_scholarships DESC
```

### Payment Success Analysis
```sql
SELECT student_id, student_first_name, student_last_name,
       student_major, total_payments_count,
       completed_payments_count, failed_payments_count,
       payment_success_rate_pct, outstanding_balance
FROM financial_summary_by_student
WHERE payment_success_rate_pct < 80 AND student_status = 'Active'
ORDER BY payment_success_rate_pct ASC
```

## Complex Scenarios

### Revenue by Department
```sql
SELECT department_name, COUNT(DISTINCT student_id) as student_count,
       SUM(total_tuition_paid) as total_revenue,
       SUM(total_scholarships_received) as scholarships_distributed,
       SUM(net_tuition_after_scholarships) as net_revenue,
       SUM(outstanding_balance) as total_outstanding
FROM financial_summary_by_student
WHERE student_status = 'Active'
GROUP BY department_name
ORDER BY total_revenue DESC
```

### Semester-wise Breakdown
```sql
SELECT student_major,
       AVG(fall_2024_tuition) as avg_fall_2024_tuition,
       AVG(fall_2024_scholarships) as avg_fall_2024_scholarships,
       AVG(spring_2024_tuition) as avg_spring_2024_tuition,
       AVG(spring_2024_scholarships) as avg_spring_2024_scholarships,
       COUNT(DISTINCT student_id) as student_count
FROM financial_summary_by_student
WHERE student_status = 'Active'
GROUP BY student_major
ORDER BY avg_fall_2024_tuition DESC
```

### Scholarship Type Distribution
```sql
SELECT COUNT(DISTINCT student_id) as total_recipients,
       SUM(merit_scholarships_total) as total_merit,
       SUM(need_based_scholarships_total) as total_need_based,
       SUM(athletic_scholarships_total) as total_athletic,
       SUM(departmental_scholarships_total) as total_departmental
FROM financial_summary_by_student
WHERE is_scholarship_recipient = true AND student_status = 'Active'
```

### Financial Risk Assessment
```sql
SELECT student_id, student_first_name, student_last_name,
       outstanding_balance, failed_payments_count, payment_success_rate_pct,
       CASE
           WHEN outstanding_balance > 10000 AND failed_payments_count > 3 THEN 'High Risk'
           WHEN outstanding_balance > 5000 OR failed_payments_count > 1 THEN 'Medium Risk'
           ELSE 'Low Risk'
       END as risk_level
FROM financial_summary_by_student
WHERE has_outstanding_balance = true AND student_status = 'Active'
ORDER BY outstanding_balance DESC
```

## Visualizations
- Pie Chart: Payment method distribution
- Bar Chart: Revenue by department, scholarship by major
- Stacked Bar Chart: Scholarship types by major
- Histogram: Outstanding balance distribution
- Line Chart: Revenue trends by semester
