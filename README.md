# Weather Data Pipeline

A production-ready ETL pipeline that extracts weather data from the Open-Meteo API, transforms it using Polars, and loads it into PostgreSQL.

## Features

- **Extract**: Fetches weather data from Open-Meteo API with retry logic and exponential backoff
- **Transform**: Uses Polars for high-performance data transformation (NOT pandas)
- **Load**: Batch inserts into PostgreSQL with idempotent operations
- **Production-Ready**: Comprehensive logging, error handling, type hints, and modern Python 3.11+ patterns

## Project Structure

```
weather-pipeline/
├── src/
│   ├── __init__.py
│   ├── extract.py       # API data extraction with retry logic
│   ├── transform.py     # Polars-based data transformation
│   ├── load.py          # PostgreSQL loading with batch inserts
│   └── pipeline.py      # Main orchestrator
├── pyproject.toml       # uv/pip dependency configuration
├── .env.example         # Environment variables template
└── README.md
```

## Requirements

- Python 3.11+
- PostgreSQL database
- uv (recommended) or pip for dependency management

## Installation

### Using uv (recommended)

```bash
# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create virtual environment and install dependencies
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -e .
```

### Using pip

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e .
```

## Configuration

1. Copy `.env.example` to `.env`:

   ```bash
   cp .env.example .env
   ```

2. Update `.env` with your PostgreSQL credentials:

   ```env
   DB_HOST=localhost
   DB_PORT=5432
   DB_NAME=weather_db
   DB_USER=postgres
   DB_PASSWORD=your_password
   ```

3. Ensure your PostgreSQL database has the required tables (see schema below).

## Database Schema

The pipeline expects these tables to exist:

```sql
-- Locations table
CREATE TABLE locations (
    location_id SERIAL PRIMARY KEY,
    city_name VARCHAR(100) UNIQUE NOT NULL,
    country VARCHAR(100),
    latitude DECIMAL(9, 6),
    longitude DECIMAL(9, 6),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Weather readings table
CREATE TABLE weather_readings (
    reading_id SERIAL PRIMARY KEY,
    location_id INTEGER REFERENCES locations(location_id),
    recorded_at TIMESTAMP NOT NULL,
    temperature_c DECIMAL(5, 2),
    temperature_f DECIMAL(5, 2),
    humidity_pct DECIMAL(5, 2),
    wind_speed_kmh DECIMAL(6, 2),
    precipitation_mm DECIMAL(6, 2),
    weather_code INTEGER,
    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    source VARCHAR(50),
    UNIQUE(location_id, recorded_at)
);

CREATE INDEX idx_weather_recorded_at ON weather_readings(recorded_at);
CREATE INDEX idx_weather_location_id ON weather_readings(location_id);
```

## Usage

### Run the complete pipeline

```bash
cd src
python pipeline.py
```

### Use as a module

```python
from src.pipeline import run_pipeline
from src.extract import City

# Run with default cities
stats = run_pipeline()

# Run with custom cities
custom_cities = [
    City("Paris", 48.8566, 2.3522),
    City("Berlin", 52.5200, 13.4050),
]
stats = run_pipeline(cities=custom_cities)

print(f"Inserted {stats['rows_inserted']} rows")
```

## Default Cities

The pipeline fetches data for these cities by default:

- Cairo (Egypt)
- London (UK)
- Tokyo (Japan)
- New York (USA)
- Sydney (Australia)

## Data Schema

The transformed DataFrame has the following columns:

| Column           | Type     | Description                             |
| ---------------- | -------- | --------------------------------------- |
| city_name        | String   | City name (title-cased)                 |
| recorded_at      | Datetime | Timestamp of weather reading            |
| temperature_c    | Float64  | Temperature in Celsius                  |
| temperature_f    | Float64  | Temperature in Fahrenheit (derived)     |
| humidity_pct     | Float64  | Relative humidity percentage            |
| wind_speed_kmh   | Float64  | Wind speed in km/h (converted from m/s) |
| precipitation_mm | Float64  | Precipitation in millimeters            |
| weather_code     | Int64    | WMO weather code                        |
| ingested_at      | Datetime | Pipeline ingestion timestamp (UTC)      |
| source           | String   | Data source (always "open-meteo")       |

## Features

### Retry Logic

- 3 retry attempts with exponential backoff
- Handles HTTP errors, timeouts, and connection issues
- Continues with other cities if one fails

### Data Quality

- Automatic deduplication on (city_name, recorded_at)
- Null handling (preserves nulls, doesn't drop rows)
- Schema validation
- Type safety with comprehensive type hints

### Idempotency

- INSERT ... ON CONFLICT DO NOTHING for locations
- INSERT ... ON CONFLICT (location_id, recorded_at) DO NOTHING for readings
- Safe to re-run without duplicating data

### Performance

- Polars for high-performance data transformation
- Batch inserts using psycopg2's execute_values
- Efficient memory usage with generators where applicable

### Observability

- Comprehensive logging at INFO level
- Detailed pipeline statistics
- Error tracking and reporting
- Execution time tracking

## Development

### Install development dependencies

```bash
uv pip install -e ".[dev]"
```

### Run tests

```bash
pytest
```

### Code formatting

```bash
black src/
```

### Type checking

```bash
mypy src/
```

### Linting

```bash
ruff check src/
```

## Troubleshooting

### Database connection fails

- Verify PostgreSQL is running
- Check `.env` credentials
- Ensure database and tables exist
- Check firewall/network settings

### API requests fail

- Check internet connectivity
- Verify Open-Meteo API is accessible
- Review retry logs for specific error messages

### Import errors

- Ensure virtual environment is activated
- Run `uv pip install -e .` or `pip install -e .`

## License

MIT

## Contributing

Contributions welcome! Please follow these guidelines:

- Use Python 3.11+ features
- Include type hints
- Follow PEP 8 (enforced by Black)
- Add tests for new features
- Update documentation
