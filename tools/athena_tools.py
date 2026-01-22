"""
Athena query execution tools for Claude Agent SDK.
Provides tools to execute SQL queries and download results to local filesystem.
"""

import boto3
import time
import os
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime
from .sql_validator import SQLValidator


class AthenaQueryExecutor:
    """Tools for executing Athena queries and managing results."""

    def __init__(
        self,
        database: str,
        output_location: str,
        results_dir: str,
        region: str = "us-east-1",
        max_poll_attempts: int = 100,
        poll_interval: int = 2
    ):
        """
        Initialize Athena tools.

        Args:
            database: Athena database name
            output_location: S3 location for query results (e.g., s3://bucket/path/)
            results_dir: Local directory to download results (should include full path with request_id if needed)
            region: AWS region
            max_poll_attempts: Maximum number of polling attempts
            poll_interval: Seconds between poll attempts
        """
        self.database = database
        self.output_location = output_location

        # Use results_dir directly (caller provides full path)
        self.results_dir = Path(results_dir)
        self.results_dir.mkdir(parents=True, exist_ok=True)

        self.athena_client = boto3.client('athena', region_name=region)
        self.s3_client = boto3.client('s3', region_name=region)

        self.max_poll_attempts = max_poll_attempts
        self.poll_interval = poll_interval

        # Initialize SQL validator
        self.sql_validator = SQLValidator(strict_mode=True)

    def execute_query(self, query: str) -> Dict:
        """
        Execute an Athena query asynchronously.

        Args:
            query: SQL query string

        Returns:
            Dictionary with query execution details
        """
        # Validate query first
        is_valid, error_msg = self.sql_validator.validate(query)
        if not is_valid:
            raise ValueError(f"Query validation failed: {error_msg}")

        # Execute query
        response = self.athena_client.start_query_execution(
            QueryString=query,
            QueryExecutionContext={'Database': self.database},
            ResultConfiguration={'OutputLocation': self.output_location}
        )

        query_execution_id = response['QueryExecutionId']

        return {
            'query_execution_id': query_execution_id,
            'status': 'SUBMITTED',
            'query': query
        }

    def get_query_status(self, query_execution_id: str) -> Dict:
        """
        Get the status of a query execution.

        Args:
            query_execution_id: Query execution ID

        Returns:
            Dictionary with query status information
        """
        response = self.athena_client.get_query_execution(
            QueryExecutionId=query_execution_id
        )

        execution = response['QueryExecution']
        status = execution['Status']
        state = status['State']

        result = {
            'query_execution_id': query_execution_id,
            'state': state,
            'state_change_reason': status.get('StateChangeReason', '')
        }

        if state == 'SUCCEEDED':
            result['data_scanned_bytes'] = execution.get('Statistics', {}).get('DataScannedInBytes', 0)
            result['execution_time_ms'] = execution.get('Statistics', {}).get('TotalExecutionTimeInMillis', 0)
            result['output_location'] = execution['ResultConfiguration']['OutputLocation']

        elif state == 'FAILED':
            result['error'] = status.get('AthenaError', {})

        return result

    def wait_for_query_completion(self, query_execution_id: str) -> Dict:
        """
        Poll for query completion.

        Args:
            query_execution_id: Query execution ID

        Returns:
            Dictionary with final query status

        Raises:
            TimeoutError: If query doesn't complete within max attempts
            RuntimeError: If query fails
        """
        for attempt in range(self.max_poll_attempts):
            status = self.get_query_status(query_execution_id)
            state = status['state']

            if state == 'SUCCEEDED':
                return status

            elif state == 'FAILED':
                error = status.get('error', {})
                error_msg = error.get('ErrorMessage', 'Unknown error')
                raise RuntimeError(f"Query failed: {error_msg}")

            elif state == 'CANCELLED':
                raise RuntimeError("Query was cancelled")

            # Still running, wait and retry
            time.sleep(self.poll_interval)

        raise TimeoutError(f"Query did not complete within {self.max_poll_attempts * self.poll_interval} seconds")

    def download_query_results(self, query_execution_id: str, local_filename: Optional[str] = None, query: Optional[str] = None) -> str:
        """
        Download query results from S3 to local filesystem.

        Args:
            query_execution_id: Query execution ID
            local_filename: Optional custom filename for local file
            query: Optional SQL query string to save alongside results

        Returns:
            Path to downloaded file

        Raises:
            RuntimeError: If query is not in SUCCEEDED state
        """
        # Get query status
        status = self.get_query_status(query_execution_id)

        if status['state'] != 'SUCCEEDED':
            raise RuntimeError(f"Cannot download results. Query state: {status['state']}")

        # Parse S3 location
        s3_location = status['output_location']
        s3_path = s3_location.replace('s3://', '')
        bucket, key = s3_path.split('/', 1)

        # Determine local filename with timestamp
        if local_filename is None:
            local_filename = f"{query_execution_id}.csv"

        # Extract just the filename (in case a path was provided)
        local_filename = Path(local_filename).name

        # Add timestamp to filename (before extension)
        timestamp = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
        filename_parts = local_filename.rsplit('.', 1)
        if len(filename_parts) == 2:
            local_filename = f"{filename_parts[0]}_{timestamp}.{filename_parts[1]}"
        else:
            local_filename = f"{local_filename}_{timestamp}"

        local_filepath = self.results_dir / local_filename

        # Download from S3
        self.s3_client.download_file(bucket, key, str(local_filepath))

        # Save SQL query to .sql file if provided
        if query:
            sql_filename = local_filename.rsplit('.', 1)[0] + '.sql'
            sql_filepath = self.results_dir / sql_filename
            with open(sql_filepath, 'w') as f:
                f.write(query)

        return str(local_filepath)

    def print_sql_box(self, query: str):
        """
        Print SQL query with simple delimiters.

        Args:
            sql: SQL query string
        """
        print("-------------------- SQL QUERY --------------------")
        print(query)
        print("---------------------------------------------------")

    def execute_and_download(self, query: str, local_filename: Optional[str] = None) -> Dict:
        """
        Execute query, wait for completion, and download results.
        This is the primary method agents should use.

        Args:
            query: SQL query string
            local_filename: Optional custom filename for local file

        Returns:
            Dictionary with execution details and local file path
        """
        self.print_sql_box(query)

        # Execute query
        exec_result = self.execute_query(query)
        query_execution_id = exec_result['query_execution_id']

        print(f"Query submitted with ID: {query_execution_id}")
        print("Waiting for query to complete...")

        # Wait for completion
        status = self.wait_for_query_completion(query_execution_id)

        print(f"Query completed successfully!")
        print(f"  - Data scanned: {status['data_scanned_bytes'] / (1024*1024):.2f} MB")
        print(f"  - Execution time: {status['execution_time_ms'] / 1000:.2f} seconds")

        # Download results and save SQL query
        local_filepath = self.download_query_results(query_execution_id, local_filename, query)

        print(f"Results downloaded to: {local_filepath}")

        return {
            'query_execution_id': query_execution_id,
            'local_file': local_filepath,
            'data_scanned_bytes': status['data_scanned_bytes'],
            'execution_time_ms': status['execution_time_ms'],
            's3_location': status['output_location']
        }


# Backward compatibility alias
AthenaTools = AthenaQueryExecutor
