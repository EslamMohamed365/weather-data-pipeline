#!/usr/bin/env python3
"""Verification script to test the weather pipeline setup."""

import os
import sys
from dotenv import load_dotenv
import psycopg2


def test_environment():
    """Test if environment variables are loaded."""
    load_dotenv()
    required_vars = ["DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD"]
    missing = [var for var in required_vars if not os.getenv(var)]

    if missing:
        print(f"❌ Missing environment variables: {', '.join(missing)}")
        return False
    print("✅ Environment variables loaded")
    return True


def test_database_connection():
    """Test database connection."""
    load_dotenv()
    try:
        conn = psycopg2.connect(
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT"),
            database=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
        )
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        result = cursor.fetchone()
        version = result[0] if result else "Unknown"
        print(f"✅ Database connection successful")
        print(f"   PostgreSQL version: {version.split(',')[0]}")

        # Check tables
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name;
        """)
        tables = [row[0] for row in cursor.fetchall()]
        print(f"   Tables found: {', '.join(tables)}")

        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False


def test_imports():
    """Test if required packages can be imported."""
    packages = {
        "requests": "HTTP client",
        "polars": "Data transformation",
        "sqlalchemy": "Database ORM",
        "streamlit": "Dashboard",
        "dotenv": "Environment variables",
    }

    all_ok = True
    for package, description in packages.items():
        try:
            __import__(package)
            print(f"✅ {package:15} - {description}")
        except ImportError:
            print(f"❌ {package:15} - {description} (not installed)")
            all_ok = False

    return all_ok


def main():
    """Run all verification tests."""
    print("=" * 60)
    print("Weather Data Pipeline - Setup Verification")
    print("=" * 60)
    print()

    print("Testing Python packages...")
    test1 = test_imports()
    print()

    print("Testing environment configuration...")
    test2 = test_environment()
    print()

    print("Testing database connection...")
    test3 = test_database_connection()
    print()

    print("=" * 60)
    if test1 and test2 and test3:
        print("🎉 All tests passed! Setup is complete.")
        print()
        print("Next steps:")
        print("  1. Run the ETL pipeline: uv run python -m src.main")
        print("  2. Start the dashboard: uv run streamlit run dashboard/app.py")
        print("  3. Access pgAdmin: http://localhost:5050")
        print("=" * 60)
        return 0
    else:
        print("⚠️  Some tests failed. Please review the errors above.")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
