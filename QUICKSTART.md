# Weather Pipeline Quick Start Guide

## Prerequisites
- Python 3.11+
- PostgreSQL database running
- `uv` installed (or use pip)

## Quick Setup (5 minutes)

### 1. Install Dependencies
```bash
# Using uv (recommended)
uv venv
source .venv/bin/activate
uv pip install -e .

# OR using pip
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

### 2. Configure Database
```bash
# Copy environment template
cp .env.example .env

# Edit .env with your database credentials
# DB_HOST=localhost
# DB_PORT=5432
# DB_NAME=weather_db
# DB_USER=postgres
# DB_PASSWORD=your_password
```

### 3. Setup Database Tables
```bash
# Option A: If you have the schema.sql file
psql -U postgres -d weather_db -f sql/schema.sql

# Option B: Manual setup
psql -U postgres -d weather_db
```

Run this SQL:
```sql
CREATE TABLE locations (
    location_id SERIAL PRIMARY KEY,
    city_name VARCHAR(100) UNIQUE NOT NULL,
    country VARCHAR(100),
    latitude DECIMAL(9, 6),
    longitude DECIMAL(9, 6),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

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

### 4. Run the Pipeline
```bash
cd src
python pipeline.py
```

## Expected Output

```
================================================================================
Weather Data ETL Pipeline Started
Start Time: 2026-03-05T14:30:00.000000+00:00
================================================================================
Target cities: ['Cairo', 'London', 'Tokyo', 'New York', 'Sydney']

--------------------------------------------------------------------------------
Step 0: Testing Database Connection
--------------------------------------------------------------------------------
Database connection test successful

--------------------------------------------------------------------------------
Step 1: Extracting Weather Data
--------------------------------------------------------------------------------
Fetching weather data for (30.0444, 31.2357) - Attempt 1/3
Successfully fetched weather data for (30.0444, 31.2357)
... [continues for all cities]
Extraction successful for 5 cities

--------------------------------------------------------------------------------
Step 2: Transforming Weather Data
--------------------------------------------------------------------------------
Transformed 168 rows for Cairo
Transformed 168 rows for London
... [continues for all cities]
Total transformed rows: 840 from 5 cities
Schema validation passed

--------------------------------------------------------------------------------
Step 3: Loading Weather Data to Database
--------------------------------------------------------------------------------
Ensured 5 locations exist in database
Retrieved location IDs for 5 cities
Load complete: ~840 rows inserted, ~0 rows skipped (duplicates)

================================================================================
Weather Data ETL Pipeline Summary
================================================================================
Status: SUCCESS
Start Time: 2026-03-05T14:30:00.000000+00:00
End Time: 2026-03-05T14:30:15.500000+00:00
Duration: 15.50 seconds
Cities Requested: 5
Cities Extracted: 5
Rows Transformed: 840
Rows Inserted: 840
Rows Skipped (Duplicates): 0
Errors: 0
================================================================================
```

## Verify Data Loaded

```bash
psql -U postgres -d weather_db
```

```sql
-- Check locations
SELECT * FROM locations;

-- Check weather readings count
SELECT city_name, COUNT(*) as reading_count
FROM weather_readings wr
JOIN locations l ON wr.location_id = l.location_id
GROUP BY city_name
ORDER BY city_name;

-- View recent readings
SELECT l.city_name, wr.recorded_at, wr.temperature_c, wr.humidity_pct
FROM weather_readings wr
JOIN locations l ON wr.location_id = l.location_id
ORDER BY wr.recorded_at DESC
LIMIT 10;
```

## Customization

### Use Custom Cities
Edit `src/pipeline.py` and modify the `DEFAULT_CITIES` list, or use programmatically:

```python
from src.pipeline import run_pipeline
from src.extract import City

custom_cities = [
    City("Paris", 48.8566, 2.3522),
    City("Berlin", 52.5200, 13.4050),
]

stats = run_pipeline(cities=custom_cities)
```

### Schedule with Cron
```bash
# Edit crontab
crontab -e

# Run every hour
0 * * * * cd /path/to/project && /path/to/.venv/bin/python src/pipeline.py >> logs/pipeline.log 2>&1
```

## Troubleshooting

### Import Errors
```bash
# Make sure virtual environment is activated
source .venv/bin/activate

# Reinstall dependencies
uv pip install -e .
```

### Database Connection Error
- Check PostgreSQL is running: `sudo systemctl status postgresql`
- Verify credentials in `.env`
- Test connection: `psql -U postgres -d weather_db`

### API Rate Limiting
- The Open-Meteo API is free and has generous limits
- Pipeline includes retry logic with exponential backoff
- For production, consider caching or reducing frequency

## Next Steps

1. **Visualization**: Use Streamlit dashboard (see `dashboard.py`)
2. **Scheduling**: Set up cron jobs or Airflow DAG
3. **Monitoring**: Add alerting for pipeline failures
4. **Testing**: Run test suite with `pytest`
5. **Deployment**: Containerize with Docker

## Support

- Check logs in console output
- Review error messages in pipeline summary
- Consult README.md for detailed documentation
