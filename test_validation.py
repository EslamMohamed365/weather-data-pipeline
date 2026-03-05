"""
Test script to verify input validation works correctly.
"""

import polars as pl
from datetime import datetime, timezone, timedelta
from src.load import validate_weather_data


def test_validation():
    """Test the validation function with various invalid data."""

    # Create test data with various invalid values
    now = datetime.now(timezone.utc)

    test_data = {
        "city_name": [
            "London",  # Valid
            "Paris",  # Valid
            "",  # Invalid: empty city name
            "Tokyo",  # Valid
            "Berlin",  # Valid
            "Madrid",  # Valid
        ],
        "recorded_at": [
            now,  # Valid
            now - timedelta(days=10),  # Invalid: too old
            now,  # Valid (but empty city)
            now + timedelta(hours=2),  # Invalid: future
            now,  # Valid
            now - timedelta(days=1),  # Valid
        ],
        "temperature_c": [
            25.0,  # Valid
            -150.0,  # Invalid: too cold
            30.0,  # Valid
            1000.0,  # Invalid: too hot
            15.0,  # Valid
            -5.0,  # Valid
        ],
        "humidity_pct": [
            60.0,  # Valid
            -10.0,  # Invalid: will be clamped to 0
            50.0,  # Valid
            150.0,  # Invalid: will be clamped to 100
            70.0,  # Valid
            80.0,  # Valid
        ],
        "wind_speed_kmh": [
            15.0,  # Valid
            20.0,  # Valid
            10.0,  # Valid
            500.0,  # Invalid: too fast
            12.0,  # Valid
            8.0,  # Valid
        ],
        "precipitation_mm": [
            5.0,  # Valid
            0.0,  # Valid
            2.0,  # Valid
            3000.0,  # Invalid: too much
            1.0,  # Valid
            0.5,  # Valid
        ],
        "weather_code": [
            10,  # Valid
            50,  # Valid
            25,  # Valid
            200,  # Invalid: code too high
            15,  # Valid
            30,  # Valid
        ],
        "temperature_f": [77.0, 5.0, 86.0, 1832.0, 59.0, 23.0],
        "ingested_at": [now] * 6,
        "source": ["test"] * 6,
    }

    df = pl.DataFrame(test_data)

    print("Original DataFrame:")
    print(df)
    print(f"\nOriginal row count: {df.height}")

    # Validate the data
    df_validated, warnings = validate_weather_data(df)

    print("\n" + "=" * 80)
    print("VALIDATION WARNINGS:")
    print("=" * 80)
    for warning in warnings:
        print(f"⚠️  {warning}")

    print("\n" + "=" * 80)
    print("VALIDATED DATAFRAME:")
    print("=" * 80)
    print(df_validated)
    print(f"\nValidated row count: {df_validated.height}")

    # Expected results:
    # - Empty city name row should be filtered
    # - Too old timestamp row should be filtered
    # - Future timestamp row should be filtered
    # - Temperature -150°C row should be filtered
    # - Temperature 1000°C row should be filtered
    # - Wind speed 500 km/h row should be filtered
    # - Precipitation 3000mm row should be filtered
    # - Weather code 200 row should be filtered
    # - Humidity values should be clamped (not filtered)

    print("\n" + "=" * 80)
    print("TEST SUMMARY:")
    print("=" * 80)
    print(f"Expected to filter ~5-6 rows (multiple validation failures)")
    print(f"Actually filtered: {df.height - df_validated.height} rows")

    # Check humidity clamping
    print("\nHumidity clamping check:")
    humidity_values = df_validated["humidity_pct"].to_list()
    print(f"Humidity values after validation: {humidity_values}")
    print("Expected: All values should be between 0 and 100")

    return df_validated, warnings


if __name__ == "__main__":
    print("Testing input validation...\n")
    test_validation()
    print("\n✅ Validation test complete!")
