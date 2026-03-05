#!/usr/bin/env python3
"""
Example usage of the Weather ETL Pipeline.

This script demonstrates various ways to use the pipeline programmatically.
"""

import sys
from pathlib import Path

# Add src to Python path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from extract import City
from pipeline import run_pipeline


def example_1_default_cities():
    """Example 1: Run pipeline with default cities."""
    print("=" * 80)
    print("Example 1: Running pipeline with default cities")
    print("=" * 80)

    stats = run_pipeline()

    print("\n📊 Pipeline Results:")
    print(f"   Success: {stats['success']}")
    print(f"   Cities extracted: {stats['cities_extracted']}")
    print(f"   Rows transformed: {stats['total_rows_transformed']}")
    print(f"   Rows inserted: {stats['rows_inserted']}")
    print(f"   Duration: {stats['duration_seconds']:.2f}s")


def example_2_custom_cities():
    """Example 2: Run pipeline with custom cities."""
    print("\n" + "=" * 80)
    print("Example 2: Running pipeline with custom European cities")
    print("=" * 80)

    european_cities = [
        City("Paris", 48.8566, 2.3522),
        City("Berlin", 52.5200, 13.4050),
        City("Madrid", 40.4168, -3.7038),
        City("Rome", 41.9028, 12.4964),
    ]

    stats = run_pipeline(cities=european_cities)

    print("\n📊 Pipeline Results:")
    print(f"   Success: {stats['success']}")
    print(f"   Cities extracted: {stats['cities_extracted']}")
    print(f"   Rows inserted: {stats['rows_inserted']}")


def example_3_single_city():
    """Example 3: Run pipeline for a single city."""
    print("\n" + "=" * 80)
    print("Example 3: Running pipeline for a single city (Dubai)")
    print("=" * 80)

    dubai = [City("Dubai", 25.2048, 55.2708)]

    stats = run_pipeline(cities=dubai)

    print("\n📊 Pipeline Results:")
    print(f"   Success: {stats['success']}")
    print(f"   Rows transformed: {stats['total_rows_transformed']}")
    print(f"   Rows inserted: {stats['rows_inserted']}")


def example_4_error_handling():
    """Example 4: Demonstrate error handling with invalid data."""
    print("\n" + "=" * 80)
    print("Example 4: Error handling demonstration")
    print("=" * 80)

    # Mix of valid and potentially problematic coordinates
    mixed_cities = [
        City("Valid City", 51.5074, -0.1278),
        City("Edge Case", 89.9999, 179.9999),  # Near poles
    ]

    try:
        stats = run_pipeline(cities=mixed_cities)
        print(f"\n✅ Pipeline completed with {stats['errors']} errors")
    except Exception as e:
        print(f"\n❌ Pipeline failed: {e}")


def main():
    """Run all examples."""
    print("🌦️  Weather ETL Pipeline - Usage Examples")
    print("=" * 80)

    # Uncomment the examples you want to run:

    # Example 1: Default cities (Cairo, London, Tokyo, New York, Sydney)
    example_1_default_cities()

    # Example 2: Custom European cities
    # example_2_custom_cities()

    # Example 3: Single city
    # example_3_single_city()

    # Example 4: Error handling
    # example_4_error_handling()

    print("\n" + "=" * 80)
    print("✅ Examples completed!")
    print("=" * 80)


if __name__ == "__main__":
    main()
