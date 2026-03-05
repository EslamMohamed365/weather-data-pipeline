# Setup Guide

Complete installation and configuration guide for the Weather Data Pipeline.

---

## Prerequisites

- **Python 3.11+** - [Download](https://www.python.org/downloads/)
- **Docker & Docker Compose** - [Install Docker](https://docs.docker.com/get-docker/)
- **Git** - [Install Git](https://git-scm.com/downloads)
- **5-10 minutes** for setup

---

## Installation

### Option 1: Using `uv` (Recommended - 10-100x faster)

```bash
# Install uv (Rust-based package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone repository
git clone https://github.com/YOUR_USERNAME/weather-data-pipeline.git
cd weather-data-pipeline

# Install dependencies and create virtual environment
uv sync

# Activate virtual environment
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows
```

### Option 2: Using `pip`

```bash
# Clone repository
git clone https://github.com/YOUR_USERNAME/weather-data-pipeline.git
cd weather-data-pipeline

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/macOS

# Install dependencies
pip install -e .
```

---

## Database Setup

### 1. Configure Environment

```bash
# Copy environment template
cp .env.example .env

# Edit with your credentials
nano .env  # or use your preferred editor
```

**Environment Variables:**

```bash
# PostgreSQL Configuration
DB_HOST=localhost
DB_PORT=5432
DB_NAME=weather_pipeline
DB_USER=weather_admin
DB_PASSWORD=your_secure_password_here

# pgAdmin Configuration (optional)
PGADMIN_EMAIL=admin@example.com
PGADMIN_PASSWORD=admin_password_here
```

### 2. Start Database Services

```bash
# Start PostgreSQL and pgAdmin
docker-compose up -d

# Verify containers are running
docker ps

# Should see:
# - weather-pipeline-postgres-1 (PostgreSQL)
# - weather-pipeline-pgadmin-1 (pgAdmin)
```

### 3. Verify Database Setup

```bash
# Check PostgreSQL logs
docker-compose logs postgres

# Verify schema was applied
docker-compose exec postgres psql -U weather_admin -d weather_pipeline -c "\dt"

# Expected output:
#              List of relations
#  Schema |       Name        | Type  |     Owner
# --------+-------------------+-------+---------------
#  public | locations         | table | weather_admin
#  public | weather_readings  | table | weather_admin
```

### 4. Access pgAdmin (Optional)

1. Open **http://localhost:5050** in browser
2. Login with credentials from `.env`:
   - Email: `PGADMIN_EMAIL`
   - Password: `PGADMIN_PASSWORD`
3. Add server:
   - **Name**: Weather Pipeline
   - **Host**: `postgres` (Docker service name, NOT localhost)
   - **Port**: `5432`
   - **Database**: `weather_pipeline`
   - **Username**: `weather_admin`
   - **Password**: From `.env`

---

## Running the Pipeline

### Execute ETL Pipeline

```bash
# Run the complete pipeline
uv run python src/pipeline.py

# Or with activated virtual environment
python src/pipeline.py
```

**Expected Output:**

```
================================================================================
Weather Data ETL Pipeline Started
================================================================================
Target cities: ['Cairo', 'London', 'Tokyo', 'New York', 'Sydney']

--------------------------------------------------------------------------------
Step 1: Extracting Weather Data
--------------------------------------------------------------------------------
✅ Cairo: 168 hourly readings fetched
✅ London: 168 hourly readings fetched
✅ Tokyo: 168 hourly readings fetched
✅ New York: 168 hourly readings fetched
✅ Sydney: 168 hourly readings fetched

--------------------------------------------------------------------------------
Step 2: Transforming Weather Data
--------------------------------------------------------------------------------
✅ Validation: 840/840 rows passed

--------------------------------------------------------------------------------
Step 3: Loading to Database
--------------------------------------------------------------------------------
✅ Load complete: 840 rows inserted, 0 skipped

================================================================================
Pipeline Complete
Duration: 27.3 seconds
================================================================================
```

### Verify Data Loaded

```bash
# Connect to PostgreSQL
docker-compose exec postgres psql -U weather_admin -d weather_pipeline

# Check locations
SELECT * FROM locations;

# Check weather readings count
SELECT l.city_name, COUNT(*) as reading_count
FROM weather_readings wr
JOIN locations l ON wr.location_id = l.id
GROUP BY l.city_name
ORDER BY l.city_name;

# View recent readings
SELECT l.city_name, wr.recorded_at, wr.temperature_c, wr.humidity_pct
FROM weather_readings wr
JOIN locations l ON wr.location_id = l.id
ORDER BY wr.recorded_at DESC
LIMIT 10;
```

---

## Launching the Dashboard

### Start Streamlit Dashboard

```bash
# Launch dashboard
uv run streamlit run dashboard/app.py

# Or with activated virtual environment
streamlit run dashboard/app.py
```

**Access Dashboard:**
- Open browser to **http://localhost:8501**
- Dashboard auto-refreshes when you save code changes

### Dashboard Features

**Page 1: Current Conditions** 🌤️
- Latest temperature, humidity, wind speed, precipitation
- Weather badges with emojis
- Last updated timestamp

**Page 2: Historical Trends** 📈
- Multi-city temperature comparison (line chart)
- Precipitation totals (bar chart)
- Humidity trends (area chart)
- Raw data table with CSV export

**Page 3: City Comparison** 🏙️
- Timestamp slider for point-in-time comparison
- Side-by-side metrics
- Average temperature chart
- Temperature heatmap

**Global Controls (Sidebar):**
- 🌍 City multi-select (1-5 cities)
- 📅 Date range picker
- 🌡️ Temperature unit toggle (°C / °F)

---

## Scheduling (Production)

### Option 1: Cron (Linux/macOS)

```bash
# Edit crontab
crontab -e

# Add hourly execution at minute 5
5 * * * * cd /path/to/weather-data-pipeline && /path/to/.venv/bin/python src/pipeline.py >> logs/pipeline.log 2>&1

# Create logs directory
mkdir -p logs
```

### Option 2: systemd Timer (Linux)

```ini
# /etc/systemd/system/weather-pipeline.service
[Unit]
Description=Weather Data Pipeline ETL
After=network.target postgresql.service

[Service]
Type=oneshot
User=your_user
WorkingDirectory=/path/to/weather-data-pipeline
Environment="PATH=/path/to/.venv/bin"
ExecStart=/path/to/.venv/bin/python src/pipeline.py
StandardOutput=append:/var/log/weather-pipeline.log
StandardError=append:/var/log/weather-pipeline.log

# /etc/systemd/system/weather-pipeline.timer
[Unit]
Description=Weather Pipeline Hourly Timer

[Timer]
OnCalendar=hourly
Persistent=true

[Install]
WantedBy=timers.target
```

```bash
# Enable and start timer
sudo systemctl enable weather-pipeline.timer
sudo systemctl start weather-pipeline.timer

# Check status
sudo systemctl status weather-pipeline.timer
```

---

## Troubleshooting

### Database Connection Fails

```bash
# Check if PostgreSQL is running
docker ps | grep postgres

# Check logs for errors
docker-compose logs postgres

# Verify credentials in .env
cat .env | grep DB_

# Test connection manually
docker-compose exec postgres psql -U weather_admin -d weather_pipeline
```

**Common Issues:**
- **Port 5432 already in use**: Stop other PostgreSQL instances
- **Invalid credentials**: Check `.env` matches docker-compose.yml
- **Container won't start**: Check `docker-compose logs postgres`

### API Requests Fail

```bash
# Test API manually
curl "https://api.open-meteo.com/v1/forecast?latitude=30.06&longitude=31.25&current_weather=true"

# Check retry logs in pipeline output
uv run python src/pipeline.py 2>&1 | grep -i retry

# Verify internet connectivity
ping api.open-meteo.com
```

**Common Issues:**
- **Timeout errors**: Check firewall/proxy settings
- **Rate limiting**: Free tier allows 5,000 requests/day
- **Network issues**: Retry logic handles transient failures (3 attempts)

### Import Errors

```bash
# Ensure virtual environment is activated
which python  # Should point to .venv/bin/python

# Reinstall dependencies
uv sync --force

# Or with pip
pip install -e . --force-reinstall

# Verify installation
python -c "import polars; print(polars.__version__)"
```

### Dashboard Won't Load

```bash
# Check if data exists
docker-compose exec postgres psql -U weather_admin -d weather_pipeline \
  -c "SELECT COUNT(*) FROM weather_readings;"

# Run pre-flight check
python dashboard/check_setup.py

# Check Streamlit logs
uv run streamlit run dashboard/app.py --logger.level debug
```

**Common Issues:**
- **No data in database**: Run pipeline first (`python src/pipeline.py`)
- **Port 8501 in use**: Stop other Streamlit instances or use `--server.port 8502`
- **Import errors**: Check all dependencies installed

### Schema Not Applied

```bash
# Manually apply schema
docker-compose exec postgres psql -U weather_admin -d weather_pipeline \
  < sql/schema.sql

# Or apply from within container
docker-compose exec postgres psql -U weather_admin -d weather_pipeline \
  -f /docker-entrypoint-initdb.d/01-schema.sql

# Verify tables exist
docker-compose exec postgres psql -U weather_admin -d weather_pipeline -c "\dt"
```

---

## Development Setup

### Install Development Dependencies

```bash
# Add development tools
uv add --dev pytest pytest-cov pytest-mock black ruff mypy

# Or with pip
pip install -e ".[dev]"
```

### Code Quality Tools

```bash
# Format code
black src/ dashboard/

# Lint code
ruff check src/ dashboard/

# Type check
mypy src/ dashboard/

# Run all checks
black src/ dashboard/ && ruff check src/ dashboard/ && mypy src/ dashboard/
```

### Run Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov=dashboard --cov-report=html --cov-report=term

# View coverage report
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
```

---

## Next Steps

1. ✅ **Customize Cities**: Edit `DEFAULT_CITIES` in `src/extract.py`
2. ✅ **Add More Metrics**: Extend API parameters in `extract.py`
3. ✅ **Enhance Dashboard**: Add new visualizations in `dashboard/app.py`
4. ✅ **Set Up Monitoring**: See [docs/ARCHITECTURE.md](ARCHITECTURE.md)
5. ✅ **Write Tests**: Add tests in `tests/` directory
6. ✅ **Deploy to Production**: See [docs/ARCHITECTURE.md](ARCHITECTURE.md) for scaling considerations

---

## Resources

- [Open-Meteo API Documentation](https://open-meteo.com/en/docs)
- [Polars Documentation](https://pola-rs.github.io/polars/py-polars/html/reference/)
- [Streamlit Documentation](https://docs.streamlit.io/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/15/)
- [Docker Compose Reference](https://docs.docker.com/compose/compose-file/)
