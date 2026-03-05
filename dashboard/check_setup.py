#!/usr/bin/env python3
"""
Pre-flight check script for the Weather Dashboard.
Verifies all dependencies and database connectivity before launching.
"""

import sys
from pathlib import Path


def check_imports() -> bool:
    """Check if all required packages are installed."""
    print("🔍 Checking Python packages...")

    required_packages = [
        ("polars", "Polars"),
        ("streamlit", "Streamlit"),
        ("plotly", "Plotly"),
        ("sqlalchemy", "SQLAlchemy"),
        ("psycopg2", "psycopg2-binary"),
        ("dotenv", "python-dotenv"),
    ]

    missing = []
    for module, package in required_packages:
        try:
            __import__(module)
            print(f"  ✅ {package}")
        except ImportError:
            print(f"  ❌ {package} (missing)")
            missing.append(package)

    if missing:
        print(f"\n❌ Missing packages: {', '.join(missing)}")
        print("Run: uv sync")
        return False

    print("✅ All packages installed\n")
    return True


def check_env_file() -> bool:
    """Check if .env file exists and has required variables."""
    print("🔍 Checking .env file...")

    env_path = Path(".env")
    if not env_path.exists():
        print("  ❌ .env file not found")
        print("  Create .env file with database credentials:")
        print("    DB_HOST=localhost")
        print("    DB_PORT=5432")
        print("    DB_NAME=weather_db")
        print("    DB_USER=postgres")
        print("    DB_PASSWORD=your_password")
        return False

    print("  ✅ .env file exists")

    # Check for required variables
    required_vars = ["DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD"]
    env_content = env_path.read_text()

    missing = []
    for var in required_vars:
        if var not in env_content:
            missing.append(var)

    if missing:
        print(f"  ⚠️  Missing variables: {', '.join(missing)}")
    else:
        print("  ✅ All required variables present")

    print()
    return True


def check_database() -> bool:
    """Check database connectivity."""
    print("🔍 Checking database connection...")

    try:
        import os
        from dotenv import load_dotenv
        from sqlalchemy import create_engine, text

        load_dotenv()

        db_host = os.getenv("DB_HOST", "localhost")
        db_port = os.getenv("DB_PORT", "5432")
        db_name = os.getenv("DB_NAME", "weather_db")
        db_user = os.getenv("DB_USER", "postgres")
        db_password = os.getenv("DB_PASSWORD", "")

        connection_string = (
            f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
        )

        engine = create_engine(connection_string)
        conn = engine.connect()

        # Test query
        result = conn.execute(text("SELECT COUNT(*) FROM locations"))
        count = result.fetchone()[0]

        print(f"  ✅ Connected to database")
        print(f"  📊 Found {count} cities in database")

        # Check for weather readings
        result = conn.execute(text("SELECT COUNT(*) FROM weather_readings"))
        readings = result.fetchone()[0]
        print(f"  📊 Found {readings:,} weather readings")

        conn.close()
        print()
        return True

    except Exception as e:
        print(f"  ❌ Database connection failed: {e}")
        print("\nTroubleshooting:")
        print("  1. Ensure PostgreSQL is running: docker-compose up -d")
        print("  2. Check .env file has correct credentials")
        print("  3. Verify database exists: psql -l")
        print()
        return False


def check_dashboard_files() -> bool:
    """Check if dashboard files exist."""
    print("🔍 Checking dashboard files...")

    required_files = [
        "dashboard/__init__.py",
        "dashboard/app.py",
        "dashboard/queries.py",
    ]

    missing = []
    for file in required_files:
        path = Path(file)
        if path.exists():
            print(f"  ✅ {file}")
        else:
            print(f"  ❌ {file} (missing)")
            missing.append(file)

    if missing:
        print(f"\n❌ Missing files: {', '.join(missing)}")
        return False

    print()
    return True


def main() -> None:
    """Run all pre-flight checks."""
    print("=" * 60)
    print("Weather Dashboard - Pre-Flight Check")
    print("=" * 60)
    print()

    checks = [
        ("Dashboard Files", check_dashboard_files),
        ("Python Packages", check_imports),
        ("Environment File", check_env_file),
        ("Database Connection", check_database),
    ]

    results = []
    for name, check_func in checks:
        try:
            result = check_func()
            results.append((name, result))
        except Exception as e:
            print(f"❌ {name} check failed with error: {e}\n")
            results.append((name, False))

    print("=" * 60)
    print("Summary")
    print("=" * 60)

    all_passed = True
    for name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{name:.<40} {status}")
        if not result:
            all_passed = False

    print()

    if all_passed:
        print("🎉 All checks passed! Ready to launch dashboard.")
        print()
        print("To start the dashboard, run:")
        print("  uv run streamlit run dashboard/app.py")
        print()
        sys.exit(0)
    else:
        print("⚠️  Some checks failed. Please fix the issues above before launching.")
        print()
        sys.exit(1)


if __name__ == "__main__":
    main()
