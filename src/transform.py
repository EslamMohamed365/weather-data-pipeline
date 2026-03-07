"""
Transform raw weather data into structured Polars DataFrame.
"""

import logging
from datetime import datetime, timezone
from typing import Any

import polars as pl

logger = logging.getLogger(__name__)


def transform_weather_data(
    city_name: str, raw_data: dict[str, Any]
) -> pl.DataFrame | None:
    """
    Transform raw Open-Meteo JSON response to Polars DataFrame.

    Args:
        city_name: Name of the city
        raw_data: Raw JSON response from Open-Meteo API

    Returns:
        Polars DataFrame with transformed weather data, or None if transformation fails
    """
    try:
        # Extract hourly data
        hourly = raw_data.get("hourly", {})

        if not hourly:
            logger.warning(f"No hourly data found for {city_name}")
            return None

        # Extract arrays
        timestamps = hourly.get("time", [])
        temperatures = hourly.get("temperature_2m", [])
        humidity = hourly.get("relative_humidity_2m", [])
        wind_speeds = hourly.get("wind_speed_10m", [])
        precipitation = hourly.get("precipitation", [])
        weather_codes = hourly.get("weathercode", [])

        # Validate data length
        if not timestamps:
            logger.warning(f"No timestamps found for {city_name}")
            return None

        # Create DataFrame from hourly arrays
        df = pl.DataFrame(
            {
                "recorded_at": timestamps,
                "temperature_c": temperatures,
                "humidity_pct": humidity,
                "wind_speed_ms": wind_speeds,
                "precipitation_mm": precipitation,
                "weather_code": weather_codes,
            }
        )

        # Parse ISO 8601 timestamps to Datetime
        df = df.with_columns(pl.col("recorded_at").str.to_datetime("%Y-%m-%dT%H:%M"))

        # Add derived temperature in Fahrenheit: (°C × 9/5) + 32
        df = df.with_columns(
            (pl.col("temperature_c") * 9.0 / 5.0 + 32.0).alias("temperature_f")
        )

        # Convert humidity to Float64 (API returns as Int64)
        df = df.with_columns(pl.col("humidity_pct").cast(pl.Float64))

        # Convert wind speed from m/s to km/h: × 3.6
        df = df.with_columns(
            (pl.col("wind_speed_ms") * 3.6).alias("wind_speed_kmh")
        ).drop("wind_speed_ms")

        # Add city name (title-cased)
        df = df.with_columns(pl.lit(city_name.title()).alias("city_name"))

        # Add ingestion metadata
        ingested_at = datetime.now(timezone.utc)
        df = df.with_columns(
            [
                pl.lit(ingested_at).alias("ingested_at"),
                pl.lit("open-meteo").alias("source"),
            ]
        )

        # Reorder columns to match schema
        df = df.select(
            [
                "city_name",
                "recorded_at",
                "temperature_c",
                "temperature_f",
                "humidity_pct",
                "wind_speed_kmh",
                "precipitation_mm",
                "weather_code",
                "ingested_at",
                "source",
            ]
        )

        # Deduplicate on (city_name, recorded_at)
        initial_rows = df.height
        df = df.unique(subset=["city_name", "recorded_at"], keep="first")
        deduplicated_rows = initial_rows - df.height

        if deduplicated_rows > 0:
            logger.info(f"Deduplicated {deduplicated_rows} rows for {city_name}")

        logger.info(f"Transformed {df.height} rows for {city_name}")
        return df

    except Exception as e:
        logger.error(f"Error transforming data for {city_name}: {e}", exc_info=True)
        return None


def transform_all_cities(
    city_data_list: list[tuple[str, dict[str, Any]]],
) -> pl.DataFrame | None:
    """
    Transform weather data for all cities and concatenate into single DataFrame.

    Args:
        city_data_list: List of (city_name, raw_weather_data) tuples

    Returns:
        Combined Polars DataFrame with all cities' data, or None if all transformations fail
    """
    if not city_data_list:
        logger.warning("No city data provided for transformation")
        return None

    dataframes: list[pl.DataFrame] = []

    for city_name, raw_data in city_data_list:
        df = transform_weather_data(city_name, raw_data)
        if df is not None and df.height > 0:
            dataframes.append(df)

    if not dataframes:
        logger.error("All transformations failed - no valid DataFrames")
        return None

    # Concatenate all DataFrames
    combined_df = pl.concat(dataframes, how="vertical")

    # Final deduplication across all cities
    initial_rows = combined_df.height
    combined_df = combined_df.unique(subset=["city_name", "recorded_at"], keep="first")
    deduplicated_rows = initial_rows - combined_df.height

    if deduplicated_rows > 0:
        logger.info(f"Deduplicated {deduplicated_rows} rows across all cities")

    logger.info(
        f"Total transformed rows: {combined_df.height} from {len(dataframes)} cities"
    )

    return combined_df


def validate_schema(df: pl.DataFrame) -> bool:
    """
    Validate DataFrame schema matches expected structure.

    Args:
        df: DataFrame to validate

    Returns:
        True if schema is valid, False otherwise
    """
    expected_schema = {
        "city_name": pl.String,
        "recorded_at": pl.Datetime,
        "temperature_c": pl.Float64,
        "temperature_f": pl.Float64,
        "humidity_pct": pl.Float64,
        "wind_speed_kmh": pl.Float64,
        "precipitation_mm": pl.Float64,
        "weather_code": pl.Int64,  # Polars may use Int64 instead of Int32
        "ingested_at": pl.Datetime,
        "source": pl.String,
    }

    actual_schema = dict(df.schema)

    for col_name, expected_dtype in expected_schema.items():
        if col_name not in actual_schema:
            logger.error(f"Missing column: {col_name}")
            return False

        actual_dtype = actual_schema[col_name]
        # Allow Int64/Int32 flexibility
        if expected_dtype == pl.Int64 and actual_dtype in (pl.Int32, pl.Int64):
            continue
        if actual_dtype != expected_dtype:
            logger.error(
                f"Column {col_name} has incorrect type: expected {expected_dtype}, got {actual_dtype}"
            )
            return False

    logger.info("Schema validation passed")
    return True
