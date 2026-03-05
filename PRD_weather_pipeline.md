# Product Requirements Document (PRD)

## Weather Data Pipeline — Python, Polars, PostgreSQL & Streamlit

| Field            | Detail                |
| ---------------- | --------------------- |
| **Project Name** | Weather Data Pipeline |
| **Version**      | 1.0.0                 |
| **Author**       | Data Engineering Team |
| **Status**       | Draft                 |

---

## 1. Overview

This project implements a production-style **ETL (Extract → Transform → Load)** data pipeline that collects weather data from a public API, cleanses and normalizes it using Python and Polars, stores it in a PostgreSQL database running inside a Docker container, and exposes the data through an interactive **Streamlit dashboard**.

The pipeline is designed as a portfolio-grade project demonstrating core data engineering competencies: API ingestion, data transformation, relational storage, containerization, scheduling, and data visualization.

---

## 2. Objectives

- Build a fully functional, automated weather data pipeline from scratch
- Practice real-world data engineering skills: ETL, schema design, containerization
- Use **Polars** (instead of pandas) for high-performance, memory-efficient data transformation
- Run PostgreSQL in **Docker** to demonstrate containerization proficiency
- Build a **Streamlit dashboard** to visualize stored weather data interactively
- Produce clean, queryable historical weather data across multiple cities

---

## 3. Scope

### In Scope

- Fetching current weather and hourly forecasts from the **Open-Meteo API**
- Transforming raw JSON into structured, clean tabular data using **Polars**
- Loading clean data into a **PostgreSQL** database
- Running PostgreSQL and pgAdmin via **Docker Compose**
- Scheduling the pipeline to run on a recurring interval (hourly via cron)
- Supporting multiple city locations
- **Interactive Streamlit dashboard** for visualizing stored weather data

### Out of Scope

- Authentication or user management
- Cloud deployment (AWS, GCP, Azure)
- Real-time streaming (Kafka, etc.)

---

## 4. Tech Stack

| Layer               | Technology                | Reason                                                                          |
| ------------------- | ------------------------- | ------------------------------------------------------------------------------- |
| Language            | Python 3.11+              | Industry standard for data engineering                                          |
| **Package Manager** | **`uv`**                  | **Extremely fast pip/venv replacement, single tool for deps & Python versions** |
| API Source          | Open-Meteo (free, no key) | No authentication friction                                                      |
| HTTP Client         | `requests`                | Simple, reliable HTTP library                                                   |
| Transformation      | **Polars**                | Faster than pandas, Rust-backed, modern API                                     |
| Database            | PostgreSQL 15             | Robust, production-grade RDBMS                                                  |
| DB Connector        | `psycopg2` / `SQLAlchemy` | Standard Python PostgreSQL drivers                                              |
| **Visualization**   | **Streamlit**             | **Pure-Python dashboards, zero frontend code required**                         |
| Containerization    | Docker + Docker Compose   | Isolates DB, demonstrates DevOps skills                                         |
| DB GUI              | pgAdmin 4                 | Visual database explorer                                                        |
| Config              | `python-dotenv`           | Manages secrets via `.env` file                                                 |
| Scheduler           | `cron` (Linux/macOS)      | Automates pipeline runs                                                         |

---

## 5. System Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                           PIPELINE FLOW                              │
│                                                                      │
│  ┌──────────────┐   ┌──────────────┐   ┌────────────────────────┐   │
│  │   EXTRACT    │──▶│  TRANSFORM   │──▶│         LOAD           │   │
│  │              │   │              │   │                        │   │
│  │ Open-Meteo   │   │   Polars     │   │    PostgreSQL 15       │   │
│  │ REST API     │   │  DataFrame   │   │      (Docker)          │   │
│  └──────────────┘   └──────────────┘   └───────────┬────────────┘   │
│                                                    │                │
│                                                    ▼                │
│                                        ┌────────────────────────┐   │
│                                        │   VISUALIZE            │   │
│                                        │                        │   │
│                                        │  Streamlit Dashboard   │   │
│                                        │  (reads from Postgres) │   │
│                                        └────────────────────────┘   │
│                                                                      │
│  Orchestrated by: pipeline.py       Scheduled by: cron (hourly)     │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 6. Project Structure

```
weather-pipeline/
│
├── docker-compose.yml          # PostgreSQL 15 + pgAdmin services
├── .env                        # DB credentials & config (gitignored)
├── .env.example                # Template for environment variables
├── pyproject.toml              # Project metadata & dependencies (uv)
├── uv.lock                     # Locked dependency tree (commit this)
├── README.md                   # Setup & usage guide
│
├── src/
│   ├── extract.py              # Fetch raw JSON from Open-Meteo API
│   ├── transform.py            # Clean & normalize data with Polars
│   ├── load.py                 # Insert records into PostgreSQL
│   └── pipeline.py             # ETL orchestrator (runs all 3 phases)
│
├── dashboard/
│   ├── app.py                  # Streamlit app entry point
│   └── queries.py              # SQL query helpers for the dashboard
│
└── sql/
    └── schema.sql              # DDL: table definitions & indexes
```

---

## 7. Functional Requirements

### 7.1 Extract (`src/extract.py`)

| Requirement         | Detail                                                                                     |
| ------------------- | ------------------------------------------------------------------------------------------ |
| **API**             | `https://api.open-meteo.com/v1/forecast`                                                   |
| **Parameters**      | `latitude`, `longitude`, `hourly`, `current_weather`, `timezone`                           |
| **Fields to fetch** | `temperature_2m`, `relative_humidity_2m`, `wind_speed_10m`, `precipitation`, `weathercode` |
| **Cities**          | Configurable list of (city_name, lat, lon) tuples                                          |
| **Error handling**  | Retry on HTTP errors (3 attempts, exponential backoff)                                     |
| **Output**          | Raw Python dict (parsed JSON) per city                                                     |

**Example API call:**

```
GET https://api.open-meteo.com/v1/forecast
  ?latitude=30.06&longitude=31.25
  &hourly=temperature_2m,relative_humidity_2m,wind_speed_10m,precipitation,weathercode
  &current_weather=true
  &timezone=Africa/Cairo
```

---

### 7.2 Transform (`src/transform.py`)

All transformation must be done using **Polars DataFrames**. No pandas.

| Transformation              | Detail                                                         |
| --------------------------- | -------------------------------------------------------------- |
| **Flatten JSON**            | Unnest hourly arrays into one row per timestamp per city       |
| **Unit conversion**         | Add `temperature_f` column: `(°C × 9/5) + 32`                  |
| **Wind speed**              | Convert m/s → km/h: `× 3.6`                                    |
| **Handle nulls**            | Fill missing numeric values with `null` (do not drop rows)     |
| **Timestamp parsing**       | Parse ISO 8601 strings → `pl.Datetime` dtype                   |
| **City name normalization** | Title-case all city names (e.g. `"cairo"` → `"Cairo"`)         |
| **Add metadata**            | `ingested_at` = current UTC timestamp, `source = "open-meteo"` |
| **Deduplication**           | Drop duplicate `(city_name, recorded_at)` pairs                |
| **Output**                  | `polars.DataFrame` with clean, typed columns                   |

**Expected output schema:**

```
city_name        : String
recorded_at      : Datetime
temperature_c    : Float64
temperature_f    : Float64
humidity_pct     : Float64
wind_speed_kmh   : Float64
precipitation_mm : Float64
weather_code     : Int32
ingested_at      : Datetime
source           : String
```

---

### 7.3 Load (`src/load.py`)

| Requirement         | Detail                                                       |
| ------------------- | ------------------------------------------------------------ |
| **Connection**      | Read credentials from `.env` via `python-dotenv`             |
| **Insert strategy** | `INSERT ... ON CONFLICT DO NOTHING` to prevent duplicates    |
| **Batch insert**    | Use `executemany` or `copy_records_to_table` for performance |
| **Logging**         | Log count of rows inserted vs. skipped                       |
| **Error handling**  | Rollback transaction on failure, log error                   |

---

### 7.4 Database Schema (`sql/schema.sql`)

```sql
-- Locations lookup table
CREATE TABLE IF NOT EXISTS locations (
    id           SERIAL PRIMARY KEY,
    city_name    VARCHAR(100) NOT NULL,
    country_code CHAR(2),
    latitude     FLOAT NOT NULL,
    longitude    FLOAT NOT NULL,
    UNIQUE (city_name)
);

-- Core weather readings table
CREATE TABLE IF NOT EXISTS weather_readings (
    id               SERIAL PRIMARY KEY,
    location_id      INT REFERENCES locations(id) ON DELETE CASCADE,
    recorded_at      TIMESTAMP NOT NULL,
    temperature_c    FLOAT,
    temperature_f    FLOAT,
    humidity_pct     FLOAT,
    wind_speed_kmh   FLOAT,
    precipitation_mm FLOAT,
    weather_code     INT,
    ingested_at      TIMESTAMP DEFAULT NOW(),
    source           VARCHAR(50) DEFAULT 'open-meteo',
    UNIQUE (location_id, recorded_at)
);

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_readings_location ON weather_readings(location_id);
CREATE INDEX IF NOT EXISTS idx_readings_recorded_at ON weather_readings(recorded_at);
```

---

### 7.5 Orchestration (`src/pipeline.py`)

```
run():
  1. For each configured city:
     a. extract(city)  → raw JSON
     b. transform(raw) → Polars DataFrame
  2. Concatenate all DataFrames
  3. load(dataframe)  → PostgreSQL
  4. Log: total rows fetched, inserted, skipped, duration
```

---

### 7.6 Docker Setup (`docker-compose.yml`)

Two services must be defined:

| Service    | Image            | Port   | Purpose           |
| ---------- | ---------------- | ------ | ----------------- |
| `postgres` | `postgres:15`    | `5432` | Primary database  |
| `pgadmin`  | `dpage/pgadmin4` | `5050` | Visual DB browser |

Requirements:

- PostgreSQL data must be persisted via a named Docker volume
- `schema.sql` must be auto-executed on first container start via `docker-entrypoint-initdb.d`
- All credentials must be injected via environment variables (not hardcoded)

---

### 7.7 Streamlit Dashboard (`dashboard/app.py`)

The dashboard reads directly from PostgreSQL and must **never** call the Open-Meteo API — it is a pure visualization layer over stored data.

**Launch command:**

```bash
uv run streamlit run dashboard/app.py
```

#### Pages & Components

**Sidebar (global controls)**

- City multi-select (populated dynamically from `locations` table)
- Date range picker (default: last 7 days)
- Temperature unit toggle: °C / °F

---

**Page 1 — Current Conditions**

| Component              | Detail                                                                       |
| ---------------------- | ---------------------------------------------------------------------------- |
| Metric cards           | Latest temperature, humidity, wind speed, precipitation per selected city    |
| Weather code badge     | Human-readable label mapped from WMO weather code (e.g. `2 → Partly Cloudy`) |
| Last updated timestamp | Shows `ingested_at` of the most recent record                                |

---

**Page 2 — Historical Trends**

| Component  | Detail                                                               |
| ---------- | -------------------------------------------------------------------- |
| Line chart | Temperature over time, one line per city (`st.line_chart` or Plotly) |
| Bar chart  | Total daily precipitation per city                                   |
| Area chart | Hourly humidity trend for selected city                              |
| Data table | Raw filtered records with Polars → `st.dataframe`                    |

---

**Page 3 — City Comparison**

| Component                 | Detail                                                                          |
| ------------------------- | ------------------------------------------------------------------------------- |
| Side-by-side metric cards | Compare temperature & humidity across all selected cities at the same timestamp |
| Grouped bar chart         | Average daily temperature per city over selected date range                     |
| Heatmap (optional)        | City × Hour matrix of average temperature                                       |

---

#### `dashboard/queries.py`

All SQL queries must be encapsulated here as functions returning **Polars DataFrames**. No raw SQL in `app.py`.

```python
def get_latest_readings(conn, cities: list[str]) -> pl.DataFrame: ...
def get_temperature_trend(conn, cities: list[str], start: date, end: date) -> pl.DataFrame: ...
def get_daily_precipitation(conn, cities: list[str], start: date, end: date) -> pl.DataFrame: ...
def get_city_comparison(conn, cities: list[str], at: datetime) -> pl.DataFrame: ...
```

#### Caching

- Use `@st.cache_data(ttl=300)` on all query functions (5-minute cache)
- This prevents hammering the database on every widget interaction

#### Connection

- Read DB credentials from `.env` via `python-dotenv`
- Use `SQLAlchemy` engine, shared via `st.cache_resource`

---

## 8. Non-Functional Requirements

| Category          | Requirement                                                             |
| ----------------- | ----------------------------------------------------------------------- |
| **Performance**   | Transform 168 hourly rows × 5 cities in under 2 seconds                 |
| **Reliability**   | Pipeline must handle API timeouts and DB connection failures gracefully |
| **Idempotency**   | Re-running the pipeline must not create duplicate rows                  |
| **Security**      | All credentials stored in `.env`, never committed to version control    |
| **Portability**   | Must run on macOS, Linux, and Windows (via WSL2)                        |
| **Observability** | Pipeline must log start time, end time, rows processed, and any errors  |

---

## 9. Environment Variables (`.env.example`)

```env
# PostgreSQL
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=weather_db
POSTGRES_USER=weather_user
POSTGRES_PASSWORD=your_password_here

# pgAdmin
PGADMIN_EMAIL=admin@example.com
PGADMIN_PASSWORD=admin_password_here

# Pipeline config
CITIES=Cairo,London,Tokyo,New_York,Sydney
FETCH_FORECAST_DAYS=7
```

---

## 10. Package Management with `uv`

All dependency management **must** use [`uv`](https://github.com/astral-sh/uv) — no `pip`, no `venv`, no `requirements.txt`.

### Setup Commands

```bash
# Create project and virtual environment
uv init .
# Add all dependencies
uv add requests polars psycopg2-binary sqlalchemy python-dotenv streamlit plotly

# Run the pipeline inside the managed environment
uv run python src/pipeline.py

# Launch the Streamlit dashboard
uv run streamlit run dashboard/app.py
```

### `pyproject.toml` (generated by uv)

```toml
[project]
name = "weather-pipeline"
version = "1.0.0"
requires-python = ">=3.11"
dependencies = [
    "requests>=2.31.0",
    "polars>=0.20.0",
    "psycopg2-binary>=2.9.9",
    "sqlalchemy>=2.0.0",
    "python-dotenv>=1.0.0",
    "streamlit>=1.35.0",
    "plotly>=5.22.0",
]
```

> **Rule:** `uv.lock` must be committed to version control. This guarantees every developer and every CI run uses the exact same dependency tree.

---

## 11. Sample SQL Queries (Portfolio Demos)

```sql
-- Latest temperature for each city
SELECT l.city_name, w.recorded_at, w.temperature_c, w.humidity_pct
FROM weather_readings w
JOIN locations l ON w.location_id = l.id
WHERE w.recorded_at = (
    SELECT MAX(recorded_at) FROM weather_readings WHERE location_id = w.location_id
);

-- Average daily temperature per city over last 7 days
SELECT l.city_name,
       DATE(w.recorded_at) AS day,
       ROUND(AVG(w.temperature_c)::numeric, 2) AS avg_temp_c
FROM weather_readings w
JOIN locations l ON w.location_id = l.id
WHERE w.recorded_at >= NOW() - INTERVAL '7 days'
GROUP BY l.city_name, day
ORDER BY l.city_name, day;

-- Total precipitation per city this week
SELECT l.city_name, ROUND(SUM(w.precipitation_mm)::numeric, 2) AS total_rain_mm
FROM weather_readings w
JOIN locations l ON w.location_id = l.id
WHERE w.recorded_at >= DATE_TRUNC('week', NOW())
GROUP BY l.city_name
ORDER BY total_rain_mm DESC;
```

---

## 12. Deliverables

| Deliverable            | Description                                   |
| ---------------------- | --------------------------------------------- |
| `src/extract.py`       | API ingestion module                          |
| `src/transform.py`     | Polars-based transformation module            |
| `src/load.py`          | PostgreSQL loader module                      |
| `src/pipeline.py`      | ETL orchestrator                              |
| `dashboard/app.py`     | Streamlit dashboard entry point               |
| `dashboard/queries.py` | SQL query helpers returning Polars DataFrames |
| `sql/schema.sql`       | Database schema DDL                           |
| `docker-compose.yml`   | Containerized PostgreSQL + pgAdmin            |
| `.env.example`         | Environment variable template                 |
| `pyproject.toml`       | uv-managed project dependencies               |
| `uv.lock`              | Locked, reproducible dependency tree          |
| `README.md`            | Full setup and usage documentation            |

---

## 13. Success Criteria

The project is considered complete when:

1. `docker-compose up -d` starts PostgreSQL and pgAdmin with no errors
2. `uv run python src/pipeline.py` runs end-to-end without exceptions
3. Weather data for all configured cities appears in the `weather_readings` table
4. Re-running the pipeline does not create duplicate rows
5. At least 24 hours of historical data has been accumulated via cron scheduling
6. All 3 sample SQL queries return correct results
7. `uv run streamlit run dashboard/app.py` launches the dashboard without errors
8. The dashboard correctly renders current conditions, historical trends, and city comparison pages
9. Sidebar city filter and date range picker update all charts dynamically
