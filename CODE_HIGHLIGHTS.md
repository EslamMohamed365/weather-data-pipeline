# Code Highlights - Python Best Practices

This document highlights the modern Python 3.11+ features and best practices used throughout the Weather ETL Pipeline implementation.

## 1. Type Hints & Type Safety

### Complete Function Signatures
```python
# extract.py
def fetch_weather_data(
    latitude: float,
    longitude: float,
    hourly_fields: list[str] | None = None,  # Modern union syntax (PEP 604)
    timezone: str = "UTC",
    timeout: int = 30,
) -> dict[str, Any]:
    """Comprehensive type hints for all parameters and return values."""
```

### Modern Union Syntax (Python 3.10+)
```python
# Instead of: Optional[List[City]]
cities: list[City] | None = None

# Instead of: Union[DataFrame, None]
def transform_weather_data(...) -> pl.DataFrame | None:
```

### Type Aliases for Clarity
```python
from typing import Any

WeatherData = dict[str, Any]
CityDataList = list[tuple[str, dict[str, Any]]]
```

## 2. Dataclasses (PEP 557)

### Clean Data Structures
```python
from dataclasses import dataclass

@dataclass
class City:
    """City configuration with coordinates."""
    name: str
    latitude: float
    longitude: float

# Usage - automatic __init__, __repr__, __eq__
city = City("Paris", 48.8566, 2.3522)
print(city)  # City(name='Paris', latitude=48.8566, longitude=2.3522)
```

### Benefits Over Traditional Classes
- ✅ No boilerplate `__init__` code
- ✅ Automatic `__repr__` for debugging
- ✅ Automatic `__eq__` for comparisons
- ✅ Type hints built-in
- ✅ Immutable with `frozen=True` option

## 3. Context Managers

### Resource Management
```python
# load.py
from contextlib import contextmanager
from typing import Generator

@contextmanager
def get_db_connection() -> Generator[psycopg2.extensions.connection, None, None]:
    """
    Context manager ensures:
    - Connection cleanup even on exceptions
    - Automatic commit on success
    - Automatic rollback on failure
    """
    conn = None
    try:
        conn = psycopg2.connect(...)
        yield conn
        conn.commit()  # Automatic commit
    except psycopg2.Error as e:
        if conn:
            conn.rollback()  # Automatic rollback
        raise
    finally:
        if conn:
            conn.close()  # Guaranteed cleanup

# Usage
with get_db_connection() as conn:
    cursor = conn.cursor()
    # Work with connection
    # Automatic cleanup happens here
```

## 4. Logging Best Practices

### Structured Logging
```python
import logging

logger = logging.getLogger(__name__)  # Module-level logger

# Different log levels for different scenarios
logger.info(f"Successfully fetched data for {city.name}")
logger.warning(f"Retrying in {sleep_time:.1f} seconds...")
logger.error(f"Failed to fetch data: {e}", exc_info=True)
```

### Pipeline-Wide Configuration
```python
# pipeline.py
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
```

## 5. Error Handling Strategies

### Retry Logic with Exponential Backoff
```python
# extract.py
MAX_RETRIES = 3
INITIAL_BACKOFF = 1.0

for attempt in range(1, MAX_RETRIES + 1):
    try:
        response = requests.get(url, params=params, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        if attempt < MAX_RETRIES:
            sleep_time = INITIAL_BACKOFF * (2 ** (attempt - 1))
            time.sleep(sleep_time)
```

### Graceful Degradation
```python
# Continue with other cities if one fails
for city in cities:
    try:
        weather_data = fetch_weather_data(...)
        results.append((city.name, weather_data))
    except requests.RequestException as e:
        logger.error(f"Failed for {city.name}: {e}")
        continue  # Don't fail entire pipeline
```

### Transaction Safety
```python
# Automatic rollback on any database error
try:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        execute_values(cursor, insert_query, records)
except psycopg2.Error as e:
    logger.error(f"Error: {e}")
    # Connection context manager handles rollback
    raise
```

## 6. Polars DataFrame Operations

### High-Performance Transformations
```python
import polars as pl

# Parse timestamps
df = df.with_columns(
    pl.col("recorded_at").str.to_datetime("%Y-%m-%dT%H:%M")
)

# Derived calculations (vectorized)
df = df.with_columns(
    (pl.col("temperature_c") * 9.0 / 5.0 + 32.0).alias("temperature_f")
)

# Multiple transformations in single pass
df = df.with_columns([
    pl.lit(ingested_at).alias("ingested_at"),
    pl.lit("open-meteo").alias("source"),
])

# Efficient deduplication
df = df.unique(subset=["city_name", "recorded_at"], keep="first")
```

### Method Chaining
```python
df = (
    pl.DataFrame(data)
    .with_columns(pl.col("recorded_at").str.to_datetime("%Y-%m-%dT%H:%M"))
    .with_columns((pl.col("temperature_c") * 9.0 / 5.0 + 32.0).alias("temperature_f"))
    .with_columns(pl.lit(city_name.title()).alias("city_name"))
    .unique(subset=["city_name", "recorded_at"])
)
```

## 7. Database Best Practices

### Batch Inserts
```python
from psycopg2.extras import execute_values

# Prepare batch data
records = [(val1, val2, val3) for row in dataframe]

# Single query for all records (10-100x faster than loop)
execute_values(cursor, insert_query, records, page_size=1000)
```

### Idempotent Operations
```python
# Locations: Insert if not exists
insert_query = """
    INSERT INTO locations (city_name, country, latitude, longitude)
    VALUES %s
    ON CONFLICT (city_name) DO NOTHING
"""

# Weather readings: Insert if not exists (by unique constraint)
insert_query = """
    INSERT INTO weather_readings (...)
    VALUES %s
    ON CONFLICT (location_id, recorded_at) DO NOTHING
"""
```

### Environment-Based Configuration
```python
from dotenv import load_dotenv
import os

load_dotenv()

conn = psycopg2.connect(
    host=os.getenv("DB_HOST", "localhost"),
    port=int(os.getenv("DB_PORT", "5432")),
    database=os.getenv("DB_NAME", "weather_db"),
    user=os.getenv("DB_USER", "postgres"),
    password=os.getenv("DB_PASSWORD", ""),
)
```

## 8. Pythonic Patterns

### List Comprehensions
```python
# Extract city names
city_names = [city.name for city in cities]

# Filter and transform
valid_cities = [city for city in cities if -90 <= city.latitude <= 90]
```

### Dictionary Comprehensions
```python
# Create location mapping
city_mapping = {city_name: location_id for location_id, city_name in rows}
```

### Generator Expressions (Memory Efficient)
```python
# Process large datasets without loading all into memory
total = sum(row['value'] for row in large_dataset)
```

### Enumerate for Index + Value
```python
for idx, city in enumerate(cities, start=1):
    logger.info(f"Processing city {idx}/{len(cities)}: {city.name}")
```

## 9. Documentation Standards

### Google-Style Docstrings
```python
def fetch_weather_data(
    latitude: float,
    longitude: float,
    hourly_fields: list[str] | None = None,
) -> dict[str, Any]:
    """
    Fetch weather data from Open-Meteo API with exponential backoff.

    Args:
        latitude: Latitude coordinate
        longitude: Longitude coordinate
        hourly_fields: List of hourly parameters to fetch

    Returns:
        Raw JSON response as Python dict

    Raises:
        requests.RequestException: If all retry attempts fail

    Example:
        >>> data = fetch_weather_data(51.5074, -0.1278)
        >>> print(data['current_weather'])
    """
```

### Module-Level Documentation
```python
"""
Extract weather data from Open-Meteo API with retry logic.

This module provides functions to fetch weather data for multiple cities
with automatic retry handling and exponential backoff.
"""
```

## 10. Configuration Management

### Constants at Module Level
```python
# extract.py
API_BASE_URL = "https://api.open-meteo.com/v1/forecast"
MAX_RETRIES = 3
INITIAL_BACKOFF = 1.0

DEFAULT_HOURLY_FIELDS = [
    "temperature_2m",
    "relative_humidity_2m",
    "wind_speed_10m",
    "precipitation",
    "weathercode",
]
```

### Default Values
```python
DEFAULT_CITIES = [
    City("Cairo", 30.0444, 31.2357),
    City("London", 51.5074, -0.1278),
    # ...
]

def extract_weather_for_cities(
    cities: list[City] | None = None,  # Use default if None
    hourly_fields: list[str] | None = None,
) -> list[tuple[str, dict[str, Any]]]:
    if cities is None:
        cities = DEFAULT_CITIES
```

## 11. Statistics and Observability

### Comprehensive Pipeline Statistics
```python
pipeline_stats = {
    "start_time": datetime.now(timezone.utc),
    "end_time": None,
    "duration_seconds": None,
    "cities_requested": len(cities),
    "cities_extracted": 0,
    "total_rows_transformed": 0,
    "rows_inserted": 0,
    "rows_skipped": 0,
    "errors": 0,
    "success": False,
}

# Update throughout pipeline
pipeline_stats["cities_extracted"] = len(city_data_list)
pipeline_stats["total_rows_transformed"] = df.height

# Calculate derived metrics
end_time = datetime.now(timezone.utc)
pipeline_stats["duration_seconds"] = (end_time - start_time).total_seconds()
```

### Detailed Logging
```python
logger.info("=" * 80)
logger.info("Weather Data ETL Pipeline Summary")
logger.info("=" * 80)
logger.info(f"Status: {'SUCCESS' if success else 'FAILED'}")
logger.info(f"Duration: {duration:.2f} seconds")
logger.info(f"Rows Inserted: {rows_inserted}")
```

## 12. Code Organization

### Single Responsibility Principle
```
extract.py   → API interaction and retry logic
transform.py → Data transformation and validation
load.py      → Database operations
pipeline.py  → Orchestration and coordination
```

### Clear Module Boundaries
```python
# Each module has a clear purpose and interface
from extract import extract_weather_for_cities
from transform import transform_all_cities
from load import load_weather_data

# Clean orchestration
def run_pipeline():
    city_data = extract_weather_for_cities()
    df = transform_all_cities(city_data)
    stats = load_weather_data(df)
```

## 13. Testing Considerations

### Testable Design
```python
# Functions accept parameters (not hardcoded)
def fetch_weather_data(latitude, longitude, ...):
    # Easy to test with different inputs

# Return values that can be asserted
def transform_weather_data(...) -> pl.DataFrame | None:
    # Return None on failure for easy assertion
```

### Sample Test Structure
```python
def test_city_dataclass():
    """Test City dataclass creation."""
    city = City("Paris", 48.8566, 2.3522)
    assert city.name == "Paris"
    assert city.latitude == 48.8566

def test_default_cities_configured():
    """Test that default cities are configured."""
    assert len(DEFAULT_CITIES) == 5
```

## 14. Performance Optimizations

### Polars Over Pandas
```python
# Polars is 5-10x faster than pandas
import polars as pl  # NOT pandas

df = pl.DataFrame(data)  # Fast columnar processing
```

### Batch Operations
```python
# Single batch insert instead of loop
execute_values(cursor, query, all_records)

# Instead of:
for record in records:
    cursor.execute(query, record)  # Slow!
```

### Generator Pattern (when needed)
```python
def stream_large_dataset():
    """Stream data instead of loading all at once."""
    for batch in get_batches():
        yield process_batch(batch)
```

## 15. Security Best Practices

### Environment Variables for Secrets
```python
# Never hardcode credentials
password = os.getenv("DB_PASSWORD")  # ✅ Good

# Instead of:
password = "my_secret_password"  # ❌ Bad
```

### SQL Injection Prevention
```python
# Use parameterized queries
cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))  # ✅ Safe

# Instead of:
cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")  # ❌ Unsafe
```

### Timeout Configuration
```python
# Prevent hanging requests
response = requests.get(url, timeout=30)
```

## Conclusion

This implementation demonstrates:
- ✅ Modern Python 3.11+ syntax and features
- ✅ Comprehensive type hints for maintainability
- ✅ Production-ready error handling
- ✅ High-performance data processing
- ✅ Clean code organization
- ✅ Excellent observability
- ✅ Security best practices
- ✅ Testable design patterns

The code is ready for production use, extension, and maintenance by teams.
