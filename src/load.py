"""
Load transformed weather data into PostgreSQL database.
"""

import logging
import os
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from functools import wraps
from threading import Lock
from typing import Any, Callable, Generator, TypeVar

import polars as pl
import psycopg2
from dotenv import load_dotenv
from psycopg2 import pool
from psycopg2.extras import execute_values

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Connection pool singleton
_connection_pool: pool.SimpleConnectionPool | None = None
_pool_lock = Lock()

# Type variable for retry decorator
F = TypeVar("F", bound=Callable[..., Any])


def get_connection_pool() -> pool.SimpleConnectionPool:
    """
    Get or create the connection pool (singleton pattern).

    Returns:
        SimpleConnectionPool: Thread-safe connection pool with 1-10 connections

    Raises:
        psycopg2.Error: If pool initialization fails
    """
    global _connection_pool

    if _connection_pool is None:
        with _pool_lock:
            if _connection_pool is None:
                _connection_pool = pool.SimpleConnectionPool(
                    minconn=1,
                    maxconn=10,
                    host=os.getenv("DB_HOST", "localhost"),
                    port=int(os.getenv("DB_PORT", "5432")),
                    database=os.getenv("DB_NAME", "weather_db"),
                    user=os.getenv("DB_USER", "postgres"),
                    password=os.getenv("DB_PASSWORD", ""),
                    connect_timeout=10,
                )
                logger.info(
                    "✅ Database connection pool initialized (1-10 connections)"
                )

    return _connection_pool


def retry_on_db_error(max_retries: int = 3, backoff: float = 2.0) -> Callable[[F], F]:
    """
    Decorator to retry database operations on transient errors.

    Args:
        max_retries: Maximum number of retry attempts (default: 3)
        backoff: Base for exponential backoff calculation (default: 2.0)

    Returns:
        Decorated function with retry logic

    Note:
        Only retries on OperationalError and InterfaceError (transient errors).
        Does not retry on IntegrityError or ProgrammingError (permanent errors).
    """

    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            for attempt in range(1, max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except (psycopg2.OperationalError, psycopg2.InterfaceError) as e:
                    if attempt < max_retries:
                        sleep_time = backoff**attempt
                        logger.warning(
                            f"Database error on attempt {attempt}/{max_retries}: {e}. "
                            f"Retrying in {sleep_time:.1f}s..."
                        )
                        time.sleep(sleep_time)
                    else:
                        logger.error(
                            f"Database operation failed after {max_retries} attempts"
                        )
                        raise
                except Exception as e:
                    # Don't retry on non-transient errors
                    logger.error(f"Non-retryable error: {e}")
                    raise

        return wrapper  # type: ignore

    return decorator


def validate_weather_data(df: pl.DataFrame) -> tuple[pl.DataFrame, list[str]]:
    """
    Validate weather data ranges before insertion.
    
    Args:
        df: Polars DataFrame with weather data to validate
    
    Returns:
        Tuple of (validated_df, list_of_warnings)
        
    Note:
        - Filters out rows with invalid values (except humidity which is clamped)
        - Null values are allowed for optional fields
        - Returns warnings list for logging purposes
    """
    warnings = []
    original_count = df.height
    
    # 1. TIMESTAMP VALIDATION (not too old or future)
    now = datetime.now(timezone.utc)
    cutoff_past = now - timedelta(days=8)  # API provides 7 days
    cutoff_future = now + timedelta(hours=1)  # Allow 1h clock skew
    
    df_valid = df.filter(
        (pl.col("recorded_at") >= cutoff_past) &
        (pl.col("recorded_at") <= cutoff_future)
    )
    
    timestamp_filtered = original_count - df_valid.height
    if timestamp_filtered > 0:
        warnings.append(
            f"Filtered {timestamp_filtered} rows with invalid timestamps "
            f"(must be between {cutoff_past} and {cutoff_future})"
        )
    
    # 2. TEMPERATURE VALIDATION (-100°C to 60°C)
    temp_before = df_valid.height
    df_valid = df_valid.filter(
        (pl.col("temperature_c").is_null()) |
        ((pl.col("temperature_c") >= -100) & (pl.col("temperature_c") <= 60))
    )
    temp_filtered = temp_before - df_valid.height
    if temp_filtered > 0:
        warnings.append(f"Filtered {temp_filtered} rows with invalid temperature")
    
    # 3. HUMIDITY VALIDATION (0-100%, clamp values)
    df_valid = df_valid.with_columns(
        pl.when(pl.col("humidity_pct").is_null())
          .then(None)
          .when(pl.col("humidity_pct") < 0)
          .then(0.0)
          .when(pl.col("humidity_pct") > 100)
          .then(100.0)
          .otherwise(pl.col("humidity_pct"))
          .alias("humidity_pct")
    )
    
    # 4. WIND SPEED VALIDATION (0-400 km/h max recorded wind)
    wind_before = df_valid.height
    df_valid = df_valid.filter(
        (pl.col("wind_speed_kmh").is_null()) |
        ((pl.col("wind_speed_kmh") >= 0) & (pl.col("wind_speed_kmh") <= 400))
    )
    wind_filtered = wind_before - df_valid.height
    if wind_filtered > 0:
        warnings.append(f"Filtered {wind_filtered} rows with invalid wind speed")
    
    # 5. PRECIPITATION VALIDATION (0-2000mm max daily precip)
    precip_before = df_valid.height
    df_valid = df_valid.filter(
        (pl.col("precipitation_mm").is_null()) |
        ((pl.col("precipitation_mm") >= 0) & (pl.col("precipitation_mm") <= 2000))
    )
    precip_filtered = precip_before - df_valid.height
    if precip_filtered > 0:
        warnings.append(f"Filtered {precip_filtered} rows with invalid precipitation")
    
    # 6. WEATHER CODE VALIDATION (0-99 per WMO standard)
    code_before = df_valid.height
    df_valid = df_valid.filter(
        (pl.col("weather_code").is_null()) |
        ((pl.col("weather_code") >= 0) & (pl.col("weather_code") <= 99))
    )
    code_filtered = code_before - df_valid.height
    if code_filtered > 0:
        warnings.append(f"Filtered {code_filtered} rows with invalid weather code")
    
    # 7. CITY NAME VALIDATION (not empty)
    df_valid = df_valid.filter(
        pl.col("city_name").is_not_null() & 
        (pl.col("city_name").str.lengths() > 0)
    )
    
    total_filtered = original_count - df_valid.height
    if total_filtered > 0:
        warnings.append(
            f"📊 Validation Summary: {df_valid.height}/{original_count} rows passed "
            f"({total_filtered} filtered, {100*total_filtered/original_count:.1f}%)"
        )
    
    return df_valid, warnings


@contextmanager
def get_db_connection() -> Generator[psycopg2.extensions.connection, None, None]:
    """
    Context manager for PostgreSQL database connections from pool.

    Yields:
        psycopg2 connection object from the connection pool

    Raises:
        psycopg2.Error: If connection fails or database operations fail

    Note:
        Connections are automatically returned to the pool, not closed.
    """
    pool_instance = get_connection_pool()
    conn = pool_instance.getconn()  # Get connection from pool

    try:
        logger.debug("Connection acquired from pool")
        yield conn
        conn.commit()
        logger.debug("Transaction committed successfully")

    except psycopg2.Error as e:
        logger.error(f"Database error: {e}", exc_info=True)
        if conn:
            conn.rollback()
            logger.debug("Transaction rolled back")
        raise

    finally:
        if conn:
            pool_instance.putconn(conn)  # Return connection to pool (not close!)
            logger.debug("Connection returned to pool")


@retry_on_db_error(max_retries=3)
def ensure_locations_exist(
    cursor: psycopg2.extensions.cursor, cities: list[str]
) -> dict[str, int]:
    """
    Ensure cities exist in locations table and return city_name -> location_id mapping.

    Args:
        cursor: Database cursor
        cities: List of city names

    Returns:
        Dictionary mapping city_name to location_id

    Raises:
        psycopg2.Error: If database operations fail after retries
    """
    city_mapping: dict[str, int] = {}

    # Insert cities with ON CONFLICT DO NOTHING
    insert_query = """
        INSERT INTO locations (city_name, country, latitude, longitude)
        VALUES %s
        ON CONFLICT (city_name) DO NOTHING
    """

    # For simplicity, we use placeholder coordinates - in production,
    # you'd pass actual coordinates from the extract phase
    city_values = [(city, None, None, None) for city in cities]

    try:
        execute_values(cursor, insert_query, city_values)
        logger.info(f"Ensured {len(cities)} locations exist in database")

    except psycopg2.Error as e:
        logger.error(f"Error inserting locations: {e}")
        raise

    # Fetch location_id for each city
    select_query = """
        SELECT location_id, city_name
        FROM locations
        WHERE city_name = ANY(%s)
    """

    cursor.execute(select_query, (cities,))
    rows = cursor.fetchall()

    for location_id, city_name in rows:
        city_mapping[city_name] = location_id

    logger.info(f"Retrieved location IDs for {len(city_mapping)} cities")
    return city_mapping


@retry_on_db_error(max_retries=3)
def load_weather_data(df: pl.DataFrame) -> dict[str, int]:
    """
    Load transformed weather data into PostgreSQL database.

    Args:
        df: Polars DataFrame with transformed weather data

    Returns:
        Dictionary with statistics: {'inserted': count, 'skipped': count, 'errors': count, 'filtered_invalid': count}

    Raises:
        psycopg2.Error: If database operations fail after retries
    """
    if df is None or df.height == 0:
        logger.warning("No data to load")
        return {"inserted": 0, "skipped": 0, "errors": 0, "filtered_invalid": 0}

    # Validate data before insertion
    original_count = df.height
    df_validated, validation_warnings = validate_weather_data(df)
    
    for warning in validation_warnings:
        logger.warning(f"⚠️  {warning}")
    
    if df_validated.height == 0:
        logger.warning("No valid rows to insert after validation")
        return {
            "inserted": 0,
            "skipped": 0,
            "errors": 0,
            "filtered_invalid": original_count
        }

    stats = {
        "inserted": 0,
        "skipped": 0,
        "errors": 0,
        "filtered_invalid": original_count - df_validated.height
    }

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            # Get unique cities from DataFrame (after validation)
            cities = df_validated["city_name"].unique().to_list()
            city_mapping = ensure_locations_exist(cursor, cities)

            # Prepare data for insertion
            # Convert DataFrame to list of tuples for batch insert
            records: list[tuple[Any, ...]] = []

            for row in df_validated.iter_rows(named=True):
                city_name = row["city_name"]
                location_id = city_mapping.get(city_name)

                if location_id is None:
                    logger.warning(
                        f"No location_id found for {city_name}, skipping row"
                    )
                    stats["skipped"] += 1
                    continue

                record = (
                    location_id,
                    row["recorded_at"],
                    row["temperature_c"],
                    row["temperature_f"],
                    row["humidity_pct"],
                    row["wind_speed_kmh"],
                    row["precipitation_mm"],
                    row["weather_code"],
                    row["ingested_at"],
                    row["source"],
                )
                records.append(record)

            if not records:
                logger.warning("No valid records to insert")
                return stats

            # Batch insert with ON CONFLICT DO NOTHING
            insert_query = """
                INSERT INTO weather_readings (
                    location_id,
                    recorded_at,
                    temperature_c,
                    temperature_f,
                    humidity_pct,
                    wind_speed_kmh,
                    precipitation_mm,
                    weather_code,
                    ingested_at,
                    source
                )
                VALUES %s
                ON CONFLICT (location_id, recorded_at) DO NOTHING
            """

            try:
                # Execute batch insert
                cursor_result = execute_values(
                    cursor, insert_query, records, fetch=False
                )

                # Get number of rows inserted
                # execute_values doesn't return rowcount reliably with ON CONFLICT
                # So we'll count based on before/after queries
                cursor.execute("SELECT COUNT(*) FROM weather_readings")
                final_count = cursor.fetchone()[0]

                # Estimate inserted vs skipped
                # Note: This is approximate since we can't get exact count from execute_values
                stats["inserted"] = (
                    cursor.rowcount if cursor.rowcount >= 0 else len(records)
                )
                stats["skipped"] = len(records) - stats["inserted"]

                logger.info(
                    f"Load complete: ~{stats['inserted']} rows inserted, "
                    f"~{stats['skipped']} rows skipped (duplicates), "
                    f"{stats['filtered_invalid']} filtered (invalid data)"
                )

            except psycopg2.Error as e:
                logger.error(f"Error during batch insert: {e}", exc_info=True)
                stats["errors"] = len(records)
                raise

    except psycopg2.Error as e:
        logger.error(f"Database connection or operation failed: {e}", exc_info=True)
        raise

    return stats


@retry_on_db_error(max_retries=3)
def test_connection() -> bool:
    """
    Test database connectivity with retry logic.

    Returns:
        True if connection successful, False otherwise

    Raises:
        psycopg2.Error: If connection fails after retries
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            if result == (1,):
                logger.info("Database connection test successful")
                return True
            return False

    except psycopg2.Error as e:
        logger.error(f"Database connection test failed: {e}")
        return False
