"""
SQL Validator for Athena queries.
Uses sqlparse to ensure only safe SELECT statements are executed.
"""

import sqlparse
from sqlparse.sql import Statement
from sqlparse.tokens import Keyword, DML


class SQLValidator:
    """
    Validate SQL queries to ensure they are safe for execution.

    Uses SQL parsing to analyze query structure and only allows SELECT statements.
    This prevents DDL operations like DROP, ALTER, TRUNCATE, etc.
    """

    # Allowed statement types
    ALLOWED_STATEMENT_TYPES = {'SELECT', 'WITH', 'UNKNOWN'}

    # Keywords that indicate dangerous operations
    DANGEROUS_KEYWORDS = {
        'DROP', 'ALTER', 'TRUNCATE', 'CREATE', 'REPLACE',
        'INSERT', 'UPDATE', 'DELETE', 'GRANT', 'REVOKE'
    }

    def __init__(self, strict_mode: bool = True):
        """
        Initialize SQL validator.

        Args:
            strict_mode: If True, only allows SELECT and WITH (for CTEs).
                        If False, also allows UNKNOWN statement types.
        """
        self.strict_mode = strict_mode

    def validate(self, sql: str) -> tuple[bool, str]:
        """
        Validate SQL query for safety.

        Args:
            sql: SQL query string to validate

        Returns:
            Tuple of (is_valid, error_message)
            - is_valid: True if query is safe, False otherwise
            - error_message: Empty string if valid, error description if invalid
        """
        if not sql or not sql.strip():
            return False, "SQL query is empty"

        try:
            # Parse the SQL
            parsed = sqlparse.parse(sql)

            if not parsed:
                return False, "Unable to parse SQL query"

            # Validate each statement
            for statement in parsed:
                is_valid, error = self._validate_statement(statement)
                if not is_valid:
                    return False, error

            return True, ""

        except Exception as e:
            return False, f"SQL parsing error: {str(e)}"

    def _validate_statement(self, statement: Statement) -> tuple[bool, str]:
        """
        Validate a single SQL statement.

        Args:
            statement: Parsed SQL statement

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Get statement type
        stmt_type = statement.get_type()

        # Check if statement type is allowed
        if stmt_type not in self.ALLOWED_STATEMENT_TYPES:
            return False, f"Statement type '{stmt_type}' not allowed. Only SELECT queries are permitted."

        # If strict mode and type is UNKNOWN, reject it
        if self.strict_mode and stmt_type == 'UNKNOWN':
            return False, "Unable to determine statement type. Only SELECT queries are permitted."

        # Check for dangerous keywords in the statement
        dangerous_found = self._check_dangerous_keywords(statement)
        if dangerous_found:
            return False, f"Dangerous keyword '{dangerous_found}' detected. Only SELECT queries are permitted."

        return True, ""

    def _check_dangerous_keywords(self, statement: Statement) -> str | None:
        """
        Check for dangerous SQL keywords in the statement.

        Args:
            statement: Parsed SQL statement

        Returns:
            The dangerous keyword if found, None otherwise
        """
        # Flatten all tokens in the statement
        for token in statement.flatten():
            # Check if token is a keyword
            if token.ttype in (Keyword, DML, Keyword.DDL, Keyword.DML):
                keyword = token.value.upper()

                # Check if it's a dangerous keyword
                if keyword in self.DANGEROUS_KEYWORDS:
                    return keyword

        return None

    def validate_and_raise(self, sql: str) -> None:
        """
        Validate SQL query and raise ValueError if invalid.

        Args:
            sql: SQL query string to validate

        Raises:
            ValueError: If the SQL query is not safe
        """
        is_valid, error = self.validate(sql)
        if not is_valid:
            raise ValueError(f"SQL validation failed: {error}")


# Convenience function for quick validation
def validate_sql(sql: str, strict_mode: bool = True) -> tuple[bool, str]:
    """
    Validate SQL query for safety.

    Args:
        sql: SQL query string to validate
        strict_mode: If True, only allows SELECT and WITH statements

    Returns:
        Tuple of (is_valid, error_message)
    """
    validator = SQLValidator(strict_mode=strict_mode)
    return validator.validate(sql)


def validate_sql_or_raise(sql: str, strict_mode: bool = True) -> None:
    """
    Validate SQL query and raise ValueError if invalid.

    Args:
        sql: SQL query string to validate
        strict_mode: If True, only allows SELECT and WITH statements

    Raises:
        ValueError: If the SQL query is not safe
    """
    validator = SQLValidator(strict_mode=strict_mode)
    validator.validate_and_raise(sql)


# Example usage and tests
if __name__ == "__main__":
    validator = SQLValidator()

    # Test cases
    test_cases = [
        # Safe queries
        ("SELECT * FROM students", True),
        ("SELECT enrollment_status, total_dropped FROM course_performance_analytics WHERE enrollment_status = 'Dropped'", True),
        ("SELECT COUNT(*) FROM students WHERE status = 'Dropped'", True),
        ("WITH cte AS (SELECT * FROM students) SELECT * FROM cte", True),
        ("""
            SELECT
                student_id,
                total_dropped,
                enrollment_status
            FROM student_enrollment_analytics
            WHERE enrollment_status = 'Dropped'
            GROUP BY student_id, total_dropped, enrollment_status
        """, True),

        # Dangerous queries
        ("DROP TABLE students", False),
        ("DROP DATABASE student_analytics", False),
        ("ALTER TABLE students DROP COLUMN name", False),
        ("TRUNCATE TABLE students", False),
        ("DELETE FROM students WHERE 1=1", False),
        ("INSERT INTO students VALUES (1, 'John')", False),
        ("UPDATE students SET name='John' WHERE id=1", False),
        ("CREATE TABLE new_table (id INT)", False),

        # Edge cases
        ("", False),  # Empty query
        ("   ", False),  # Whitespace only
    ]

    print("Running SQL Validator Tests\n" + "=" * 60)

    passed = 0
    failed = 0

    for sql, expected_valid in test_cases:
        is_valid, error = validator.validate(sql)

        # Check if result matches expectation
        if is_valid == expected_valid:
            status = "✓ PASS"
            passed += 1
        else:
            status = "✗ FAIL"
            failed += 1

        # Print result
        sql_preview = sql[:50].replace('\n', ' ').strip()
        if len(sql) > 50:
            sql_preview += "..."

        print(f"{status} | Expected: {expected_valid:5} | Got: {is_valid:5}")
        print(f"       SQL: {sql_preview}")
        if error:
            print(f"       Error: {error}")
        print()

    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed out of {len(test_cases)} tests")
