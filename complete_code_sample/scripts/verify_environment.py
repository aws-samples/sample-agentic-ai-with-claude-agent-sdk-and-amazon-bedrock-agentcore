#!/usr/bin/env python3
"""
Verify that the Python environment is properly configured.
Checks Python version, required packages, and AWS connectivity.
"""

import sys
import subprocess
from pathlib import Path


def check_python_version():
    """Check if Python version is exactly 3.14."""
    print("Checking Python version...")
    version = sys.version_info

    if version.major == 3 and version.minor == 14:
        print(f"  ✓ Python {version.major}.{version.minor}.{version.micro}")
        return True
    else:
        print(f"  ✗ Python {version.major}.{version.minor}.{version.micro} (requires Python 3.14)")
        print(f"    This project requires Python 3.14 specifically")
        print(f"    Run: uv venv --python 3.14 --clear")
        return False


def check_package(package_name, import_name=None):
    """Check if a package is installed and importable."""
    if import_name is None:
        import_name = package_name

    try:
        module = __import__(import_name)
        version = getattr(module, '__version__', 'unknown')
        print(f"  ✓ {package_name} ({version})")
        return True
    except ImportError:
        print(f"  ✗ {package_name} (not installed)")
        return False


def check_required_packages():
    """Check if all required packages are installed."""
    print("\nChecking required packages...")

    packages = [
        ('claude-agent-sdk', 'claude_agent_sdk'),
        ('boto3', 'boto3'),
        ('pandas', 'pandas'),
        ('numpy', 'numpy'),
        ('matplotlib', 'matplotlib'),
        ('bedrock-agentcore', 'bedrock_agentcore'),
        ('faker', 'faker'),
    ]

    all_installed = True
    for package_name, import_name in packages:
        if not check_package(package_name, import_name):
            all_installed = False

    return all_installed


def check_aws_credentials():
    """Check if AWS credentials are configured."""
    print("\nChecking AWS credentials...")

    try:
        import boto3
        sts = boto3.client('sts')
        identity = sts.get_caller_identity()
        print(f"  ✓ AWS credentials configured")
        print(f"    Account: {identity['Account']}")
        print(f"    User: {identity['Arn'].split('/')[-1]}")
        return True
    except Exception as e:
        print(f"  ✗ AWS credentials not configured or invalid")
        print(f"    Error: {str(e)}")
        return False


def check_uv_installation():
    """Check if uv is installed."""
    print("\nChecking uv installation...")

    try:
        result = subprocess.run(['uv', '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            version = result.stdout.strip()
            print(f"  ✓ uv is installed ({version})")
            return True
        else:
            print(f"  ✗ uv command failed")
            return False
    except FileNotFoundError:
        print(f"  ✗ uv is not installed")
        print(f"    Install with: curl -LsSf https://astral.sh/uv/install.sh | sh")
        return False


def check_project_structure():
    """Check if required project files exist."""
    print("\nChecking project structure...")

    project_root = Path(__file__).parent.parent
    required_files = [
        'requirements.txt',
        'pyproject.toml',
        'CLAUDE.md',
        'agent/agent.py',
        'agent/agent_agentcore.py',
        'tools/athena_executor.py',
    ]

    all_exist = True
    for file_path in required_files:
        full_path = project_root / file_path
        if full_path.exists():
            print(f"  ✓ {file_path}")
        else:
            print(f"  ✗ {file_path} (missing)")
            all_exist = False

    return all_exist


def main():
    """Run all verification checks."""
    print("=" * 70)
    print("Student Analytics Agent - Environment Verification")
    print("=" * 70)

    checks = [
        check_python_version(),
        check_required_packages(),
        check_uv_installation(),
        check_project_structure(),
    ]

    # AWS credentials are optional for local development
    print("\n" + "=" * 70)
    print("Optional Checks")
    print("=" * 70)
    check_aws_credentials()

    print("\n" + "=" * 70)
    print("Summary")
    print("=" * 70)

    if all(checks):
        print("✓ All required checks passed!")
        print("\nYou're ready to:")
        print("  1. Configure AWS credentials (if not done)")
        print("  2. Generate denormalized analytics data: python scripts/generate_denormalized_data.py")
        print("  3. Setup Athena: python scripts/setup_athena.py --bucket your-bucket")
        print("  4. Run agent: python agent/agent.py 'Your query'")
        return 0
    else:
        print("✗ Some checks failed. Please fix the issues above.")
        print("\nTo install dependencies:")
        print("  uv pip install -r requirements.txt")
        return 1


if __name__ == '__main__':
    sys.exit(main())
