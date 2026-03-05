"""
Weather Data ETL Pipeline Orchestrator.

Coordinates extraction, transformation, and loading of weather data
from Open-Meteo API to PostgreSQL database.
"""

import logging
import sys
from datetime import datetime, timezone
from typing import Any

from extract import DEFAULT_CITIES, City, extract_weather_for_cities
from load import load_weather_data, test_connection
from transform import transform_all_cities, validate_schema

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger(__name__)


def run_pipeline(
    cities: list[City] | None = None,
    hourly_fields: list[str] | None = None,
    timezone_str: str = "UTC",
) -> dict[str, Any]:
    """
    Execute the complete ETL pipeline: Extract → Transform → Load.

    Args:
        cities: List of City objects to fetch weather data for (uses DEFAULT_CITIES if None)
        hourly_fields: List of hourly weather parameters to fetch
        timezone_str: Timezone for the weather data

    Returns:
        Dictionary with pipeline statistics and results
    """
    start_time = datetime.now(timezone.utc)
    logger.info("=" * 80)
    logger.info("Weather Data ETL Pipeline Started")
    logger.info(f"Start Time: {start_time.isoformat()}")
    logger.info("=" * 80)

    pipeline_stats = {
        "start_time": start_time,
        "end_time": None,
        "duration_seconds": None,
        "cities_requested": 0,
        "cities_extracted": 0,
        "total_rows_fetched": 0,
        "total_rows_transformed": 0,
        "rows_inserted": 0,
        "rows_skipped": 0,
        "errors": 0,
        "success": False,
    }

    try:
        # Use default cities if none provided
        if cities is None:
            cities = DEFAULT_CITIES

        pipeline_stats["cities_requested"] = len(cities)
        logger.info(f"Target cities: {[city.name for city in cities]}")

        # Step 0: Test database connection
        logger.info("\n" + "-" * 80)
        logger.info("Step 0: Testing Database Connection")
        logger.info("-" * 80)

        if not test_connection():
            logger.error("Database connection test failed. Aborting pipeline.")
            pipeline_stats["errors"] += 1
            return pipeline_stats

        # Step 1: Extract
        logger.info("\n" + "-" * 80)
        logger.info("Step 1: Extracting Weather Data")
        logger.info("-" * 80)

        city_data_list = extract_weather_for_cities(
            cities=cities, hourly_fields=hourly_fields, timezone=timezone_str
        )

        pipeline_stats["cities_extracted"] = len(city_data_list)

        if not city_data_list:
            logger.error("No data extracted. Aborting pipeline.")
            pipeline_stats["errors"] += 1
            return pipeline_stats

        logger.info(f"Extraction successful for {len(city_data_list)} cities")

        # Step 2: Transform
        logger.info("\n" + "-" * 80)
        logger.info("Step 2: Transforming Weather Data")
        logger.info("-" * 80)

        transformed_df = transform_all_cities(city_data_list)

        if transformed_df is None or transformed_df.height == 0:
            logger.error(
                "Transformation failed or produced no data. Aborting pipeline."
            )
            pipeline_stats["errors"] += 1
            return pipeline_stats

        pipeline_stats["total_rows_transformed"] = transformed_df.height
        logger.info(f"Transformation successful: {transformed_df.height} rows")

        # Validate schema
        if not validate_schema(transformed_df):
            logger.error("Schema validation failed. Aborting pipeline.")
            pipeline_stats["errors"] += 1
            return pipeline_stats

        # Step 3: Load
        logger.info("\n" + "-" * 80)
        logger.info("Step 3: Loading Weather Data to Database")
        logger.info("-" * 80)

        load_stats = load_weather_data(transformed_df)

        pipeline_stats["rows_inserted"] = load_stats.get("inserted", 0)
        pipeline_stats["rows_skipped"] = load_stats.get("skipped", 0)
        pipeline_stats["errors"] += load_stats.get("errors", 0)

        logger.info(
            f"Load complete: {load_stats['inserted']} inserted, "
            f"{load_stats['skipped']} skipped, "
            f"{load_stats['errors']} errors"
        )

        # Mark as successful if we loaded some data
        if load_stats["inserted"] > 0 or load_stats["skipped"] > 0:
            pipeline_stats["success"] = True

    except KeyboardInterrupt:
        logger.warning("\nPipeline interrupted by user")
        pipeline_stats["errors"] += 1

    except Exception as e:
        logger.error(f"Unexpected error in pipeline: {e}", exc_info=True)
        pipeline_stats["errors"] += 1

    finally:
        # Calculate final statistics
        end_time = datetime.now(timezone.utc)
        pipeline_stats["end_time"] = end_time
        pipeline_stats["duration_seconds"] = (end_time - start_time).total_seconds()

        # Print summary
        logger.info("\n" + "=" * 80)
        logger.info("Weather Data ETL Pipeline Summary")
        logger.info("=" * 80)
        logger.info(f"Status: {'SUCCESS' if pipeline_stats['success'] else 'FAILED'}")
        logger.info(f"Start Time: {pipeline_stats['start_time'].isoformat()}")
        logger.info(f"End Time: {end_time.isoformat()}")
        logger.info(f"Duration: {pipeline_stats['duration_seconds']:.2f} seconds")
        logger.info(f"Cities Requested: {pipeline_stats['cities_requested']}")
        logger.info(f"Cities Extracted: {pipeline_stats['cities_extracted']}")
        logger.info(f"Rows Transformed: {pipeline_stats['total_rows_transformed']}")
        logger.info(f"Rows Inserted: {pipeline_stats['rows_inserted']}")
        logger.info(f"Rows Skipped (Duplicates): {pipeline_stats['rows_skipped']}")
        logger.info(f"Errors: {pipeline_stats['errors']}")
        logger.info("=" * 80)

    return pipeline_stats


def main() -> int:
    """
    Main entry point for the pipeline.

    Returns:
        Exit code: 0 for success, 1 for failure
    """
    try:
        stats = run_pipeline()
        return 0 if stats["success"] else 1

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
