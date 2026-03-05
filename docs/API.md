# API Reference

Developer guide for using and extending the Weather Data Pipeline programmatically.

---

## Pipeline API

### Running the Pipeline

#### Basic Usage

```python
from src.pipeline import run_pipeline

# Run with default cities (Cairo, London, Tokyo, New York, Sydney)
stats = run_pipeline()

print(f"✅ Pipeline complete")
print(f"   Inserted: {stats['rows_inserted']} rows")
print(f"   Skipped: {stats['rows_skipped']} duplicates")
print(f"   Duration: {stats['duration_seconds']:.1f}s")
```

#### Custom Cities

```python
from src.pipeline import run_pipeline
from src.extract import City

# Define custom cities
cities = [
    City("Paris", 48.8566, 2.3522),
    City("Berlin", 52.5200, 13.4050),
    City("Madrid", 40.4168, -3.7038),
    City("Rome", 41.9028, 12.4964),
]

# Run pipeline
stats = run_pipeline(cities=cities)
```

#### Return Value

`run_pipeline()` returns a dictionary with execution statistics:

```python
{
    'start_time': datetime,              # Pipeline start timestamp
    'end_time': datetime,                # Pipeline end timestamp
    'duration_seconds': float,           # Total execution time
    'cities_requested': int,             # Number of cities in request
    'cities_extracted': int,             # Successfully extracted cities
    'total_fetched': int,                # Total API rows fetched
    'total_rows_transformed': int,       # Rows after transformation
    'filtered_invalid': int,             # Rows filtered during validation
    'rows_inserted': int,                # Rows successfully inserted
    'rows_skipped': int,                 # Duplicates skipped
    'errors': int,                       # Error count
    'success': bool                      # Overall success status
}
```

---

## Extract Module

### City Configuration

```python
from src.extract import City

# Create city
city = City(name="Tokyo", latitude=35.6762, longitude=139.6503)

# Access properties
print(city.name)       # "Tokyo"
print(city.latitude)   # 35.6762
print(city.longitude)  # 139.6503
```

### Fetching Weather Data

```python
from src.extract import fetch_weather_data

# Fetch for specific coordinates
data = fetch_weather_data(
    latitude=51.5074,
    longitude=-0.1278,
    hourly_fields=[
        "temperature_2m",
        "relative_humidity_2m",
        "wind_speed_10m",
        "precipitation",
        "weathercode"
    ],
    timezone="UTC",
    timeout=30
)

# Access response
print(data['hourly']['temperature_2m'])  # List of temperatures
print(data['current_weather'])           # Current conditions
```

### Multi-City Extraction

```python
from src.extract import extract_weather_for_cities, DEFAULT_CITIES

# Use default cities
results = extract_weather_for_cities()

# Or custom cities
custom_cities = [
    City("Paris", 48.8566, 2.3522),
    City("Berlin", 52.5200, 13.4050),
]
results = extract_weather_for_cities(cities=custom_cities)

# Results format: list[tuple[str, dict]]
for city_name, weather_data in results:
    print(f"{city_name}: {len(weather_data['hourly']['time'])} hours")
```

---

## Transform Module

### Single City Transformation

```python
from src.transform import transform_weather_data
from datetime import datetime, timezone

# Transform raw API data to DataFrame
df = transform_weather_data(
    city_name="London",
    raw_data=api_response,
    ingested_at=datetime.now(timezone.utc)
)

# DataFrame schema
print(df.schema)
# {
#     'city_name': String,
#     'recorded_at': Datetime,
#     'temperature_c': Float64,
#     'temperature_f': Float64,
#     'humidity_pct': Float64,
#     'wind_speed_kmh': Float64,
#     'precipitation_mm': Float64,
#     'weather_code': Int64,
#     'ingested_at': Datetime,
#     'source': String
# }
```

### Multi-City Transformation

```python
from src.transform import transform_all_cities

# Transform list of (city_name, raw_data) tuples
city_data_list = [
    ("Paris", paris_api_data),
    ("Berlin", berlin_api_data),
]

combined_df = transform_all_cities(city_data_list)
print(f"Total rows: {combined_df.height}")
```

### Schema Validation

```python
from src.transform import validate_schema
import polars as pl

# Validate DataFrame schema
df = pl.DataFrame({...})
is_valid = validate_schema(df)

if not is_valid:
    print("Schema validation failed!")
```

---

## Load Module

### Database Connection

```python
from src.load import get_db_connection

# Use context manager for safe connection handling
with get_db_connection() as conn:
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM locations")
    count = cursor.fetchone()[0]
    print(f"Total locations: {count}")
    # Automatic commit on success, rollback on exception
```

### Loading Data

```python
from src.load import load_weather_data
import polars as pl

# Load DataFrame to database
df = pl.DataFrame({...})  # Your transformed data

stats = load_weather_data(df)

print(f"Inserted: {stats['inserted']}")
print(f"Skipped: {stats['skipped']}")
print(f"Errors: {stats['errors']}")
```

### Testing Connection

```python
from src.load import test_connection

# Verify database connectivity
if test_connection():
    print("✅ Database connection successful")
else:
    print("❌ Database connection failed")
```

---

## Dashboard Query Functions

### Get Latest Readings

```python
from dashboard.queries import get_latest_readings
from src.load import get_db_connection

with get_db_connection() as conn:
    df = get_latest_readings(
        conn=conn,
        city_names=["Cairo", "London", "Tokyo"]
    )
    
    print(df)
    # Returns Polars DataFrame with latest reading per city
```

### Get Historical Data

```python
from dashboard.queries import get_historical_data
from datetime import datetime, timedelta

end_date = datetime.now()
start_date = end_date - timedelta(days=7)

df = get_historical_data(
    conn=conn,
    city_names=["Cairo", "London"],
    start_date=start_date,
    end_date=end_date,
    limit=1000  # Optional
)
```

### Get Daily Aggregates

```python
from dashboard.queries import get_daily_aggregates

df = get_daily_aggregates(
    conn=conn,
    city_names=["Cairo"],
    start_date=start_date,
    end_date=end_date
)

# Returns: city_name, date, avg_temp, min_temp, max_temp
```

---

## Configuration

### Environment Variables

```python
import os
from dotenv import load_dotenv

load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", 5432))
DB_NAME = os.getenv("DB_NAME", "weather_db")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
```

### Custom Configuration

```python
# Override default cities
from src.extract import City

MY_CITIES = [
    City("Amsterdam", 52.3676, 4.9041),
    City("Brussels", 50.8503, 4.3517),
    City("Copenhagen", 55.6761, 12.5683),
]

# Override API parameters
CUSTOM_HOURLY_FIELDS = [
    "temperature_2m",
    "relative_humidity_2m",
    "wind_speed_10m",
    "precipitation",
    "weathercode",
    "cloud_cover",        # Additional field
    "pressure_msl",       # Additional field
]
```

---

## Extension Points

### Adding New Data Sources

```python
# src/extract_custom.py
def fetch_from_custom_api(city: City) -> dict:
    """Fetch data from alternative weather API."""
    response = requests.get(
        "https://api.custom-weather.com/forecast",
        params={
            "lat": city.latitude,
            "lon": city.longitude,
        }
    )
    return response.json()

# Integrate into pipeline
from src.pipeline import run_pipeline

def run_custom_pipeline():
    # Extract from custom API
    city_data = [(city.name, fetch_from_custom_api(city)) for city in cities]
    
    # Use existing transform/load
    df = transform_all_cities(city_data)
    stats = load_weather_data(df)
    
    return stats
```

### Custom Transformations

```python
# src/transform_custom.py
import polars as pl

def add_heat_index(df: pl.DataFrame) -> pl.DataFrame:
    """Add heat index calculation."""
    df = df.with_columns([
        (
            (pl.col("temperature_f") + 61.0 +
             (pl.col("temperature_f") - 68.0) * 1.2 +
             pl.col("humidity_pct") * 0.094) / 2
        ).alias("heat_index")
    ])
    return df

# Use in pipeline
df = transform_all_cities(city_data)
df = add_heat_index(df)
```

### Custom Validators

```python
# src/validators.py
import polars as pl

def validate_extreme_temperatures(df: pl.DataFrame) -> tuple[bool, list[str]]:
    """Validate temperature ranges."""
    warnings = []
    
    # Check for extreme cold
    extreme_cold = df.filter(pl.col("temperature_c") < -50)
    if len(extreme_cold) > 0:
        warnings.append(f"Found {len(extreme_cold)} readings below -50°C")
    
    # Check for extreme heat
    extreme_heat = df.filter(pl.col("temperature_c") > 50)
    if len(extreme_heat) > 0:
        warnings.append(f"Found {len(extreme_heat)} readings above 50°C")
    
    return len(warnings) == 0, warnings
```

---

## Error Handling

### Retry Logic

```python
from src.extract import fetch_weather_data

try:
    data = fetch_weather_data(51.5074, -0.1278)
except requests.RequestException as e:
    print(f"All retry attempts failed: {e}")
```

### Database Errors

```python
from src.load import load_weather_data
import psycopg2

try:
    stats = load_weather_data(df)
except psycopg2.Error as e:
    print(f"Database error: {e}")
    # Connection automatically rolled back
```

---

## Testing Utilities

### Mock API Responses

```python
# tests/test_extract.py
from unittest.mock import Mock, patch

@patch('src.extract.requests.get')
def test_fetch_weather_data(mock_get):
    # Mock API response
    mock_response = Mock()
    mock_response.json.return_value = {
        'hourly': {
            'time': ['2024-01-01T00:00', '2024-01-01T01:00'],
            'temperature_2m': [20.5, 21.0],
        }
    }
    mock_get.return_value = mock_response
    
    # Test function
    data = fetch_weather_data(51.5074, -0.1278)
    assert 'hourly' in data
```

### Test Database Setup

```python
# tests/conftest.py
import pytest
from src.load import get_db_connection

@pytest.fixture
def test_db():
    """Provide test database connection."""
    with get_db_connection() as conn:
        # Setup test data
        cursor = conn.cursor()
        cursor.execute("CREATE TEMP TABLE test_data (...)")
        yield conn
        # Cleanup happens automatically
```

---

## Performance Tips

### Batch Processing

```python
# Process cities in batches
def process_cities_in_batches(cities: list[City], batch_size: int = 10):
    for i in range(0, len(cities), batch_size):
        batch = cities[i:i + batch_size]
        stats = run_pipeline(cities=batch)
        print(f"Batch {i//batch_size + 1}: {stats['rows_inserted']} rows")
```

### Connection Pooling

```python
from psycopg2.pool import SimpleConnectionPool

# Create global pool
pool = SimpleConnectionPool(
    minconn=1,
    maxconn=20,  # Increase for high concurrency
    host=DB_HOST,
    database=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD
)
```

### Query Optimization

```python
# Use EXPLAIN ANALYZE to check query performance
with get_db_connection() as conn:
    cursor = conn.cursor()
    cursor.execute("""
        EXPLAIN ANALYZE
        SELECT * FROM weather_readings
        WHERE location_id = 1
          AND recorded_at >= NOW() - INTERVAL '7 days'
    """)
    print(cursor.fetchall())
```

---

## Related Documentation

- [Architecture Guide](ARCHITECTURE.md) - System design and patterns
- [Performance Analysis](PERFORMANCE.md) - Optimization opportunities
- [Setup Guide](SETUP.md) - Installation and configuration
