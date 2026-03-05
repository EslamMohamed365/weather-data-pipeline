# Architecture Documentation

Technical deep-dive into the Weather Data Pipeline design, implementation, and key decisions.

---

## System Design Overview

The pipeline follows a classic **ETL (Extract, Transform, Load)** pattern with modern Python best practices:

```
┌────────────────────────────────────────────────────────────────┐
│                      PIPELINE ARCHITECTURE                      │
│                                                                 │
│  ┌─────────────┐    ┌──────────────┐    ┌──────────────────┐  │
│  │  EXTRACT    │───▶│  TRANSFORM   │───▶│      LOAD        │  │
│  │             │    │              │    │                  │  │
│  │ Open-Meteo  │    │   Polars     │    │   PostgreSQL     │  │
│  │ REST API    │    │  DataFrame   │    │  + Connection    │  │
│  │ + Retry (3x)│    │+ Validation  │    │    Pooling       │  │
│  │+ Exp Backoff│    │+ Schema Check│    │+ Batch Inserts   │  │
│  └─────────────┘    └──────────────┘    └─────────┬────────┘  │
│                                                    │           │
│                                                    ▼           │
│                                        ┌────────────────────┐  │
│                                        │   VISUALIZE        │  │
│                                        │                    │  │
│                                        │  Streamlit App     │  │
│                                        │  + Query Layer     │  │
│                                        │  + 5min Caching    │  │
│                                        └────────────────────┘  │
│                                                                 │
│  Orchestrated by: src/pipeline.py                              │
│  Scheduled by: cron / systemd timer (hourly)                   │
└────────────────────────────────────────────────────────────────┘
```

---

## Project Structure

```
weather-data-pipeline/
├── src/                      # Core ETL modules
│   ├── extract.py            # API client (170 lines)
│   ├── transform.py          # Polars transformations (203 lines)
│   ├── load.py               # PostgreSQL operations (464 lines)
│   └── pipeline.py           # ETL orchestrator (193 lines)
│
├── dashboard/                # Streamlit visualization
│   ├── app.py                # Main dashboard (662 lines, 3 pages)
│   └── queries.py            # SQL helpers (366 lines, 8 functions)
│
├── sql/
│   └── schema.sql            # Database DDL with indexes
│
├── scripts/                  # Performance & benchmarking
│   ├── benchmark.py          # Multi-run testing
│   ├── profile_pipeline.py   # CPU profiling
│   └── load_test.py          # Dashboard load testing (Locust)
│
├── tests/                    # Test suite
│   └── test_extract.py       # Unit tests (coverage: 8% → targeting 80%)
│
├── docker-compose.yml        # PostgreSQL + pgAdmin services
├── pyproject.toml            # Dependencies & tooling config
└── .env.example              # Environment template
```

---

## ETL Pipeline Architecture

### Extract Module (`src/extract.py`)

**Purpose**: Fetch weather data from Open-Meteo API with robust error handling.

**Key Components:**

```python
@dataclass
class City:
    """Type-safe city configuration."""
    name: str
    latitude: float
    longitude: float

DEFAULT_CITIES = [
    City("Cairo", 30.0444, 31.2357),
    City("London", 51.5074, -0.1278),
    City("Tokyo", 35.6762, 139.6503),
    City("New York", 40.7128, -74.0060),
    City("Sydney", -33.8688, 151.2093),
]
```

**Retry Logic:**

```python
MAX_RETRIES = 3
INITIAL_BACKOFF = 1.0

for attempt in range(1, MAX_RETRIES + 1):
    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        if attempt < MAX_RETRIES:
            sleep_time = INITIAL_BACKOFF * (2 ** (attempt - 1))
            time.sleep(sleep_time)
```

**Exponential Backoff Schedule:**
- Attempt 1: Immediate
- Attempt 2: 1 second delay
- Attempt 3: 2 seconds delay
- Attempt 4: Fails with exception

**API Parameters:**
- `hourly`: temperature_2m, relative_humidity_2m, wind_speed_10m, precipitation, weathercode
- `current_weather=true`
- `timezone=UTC`

---

### Transform Module (`src/transform.py`)

**Purpose**: Convert raw JSON to structured Polars DataFrame with validation.

**Transformations Applied:**

1. **Timestamp Parsing**: ISO 8601 → `pl.Datetime`
   ```python
   df = df.with_columns(
       pl.col("recorded_at").str.to_datetime("%Y-%m-%dT%H:%M")
   )
   ```

2. **Derived Fields**:
   ```python
   # Temperature conversion
   (pl.col("temperature_c") * 9.0 / 5.0 + 32.0).alias("temperature_f")
   
   # Wind speed conversion (m/s → km/h)
   (pl.col("wind_speed_ms") * 3.6).alias("wind_speed_kmh")
   ```

3. **Metadata Addition**:
   ```python
   df = df.with_columns([
       pl.lit(datetime.now(timezone.utc)).alias("ingested_at"),
       pl.lit("open-meteo").alias("source"),
   ])
   ```

4. **Deduplication**:
   ```python
   df = df.unique(subset=["city_name", "recorded_at"], keep="first")
   ```

**Output Schema:**

| Column | Type | Description |
|--------|------|-------------|
| city_name | String | Title-cased city name |
| recorded_at | Datetime | Observation timestamp (UTC) |
| temperature_c | Float64 | Temperature in Celsius |
| temperature_f | Float64 | Temperature in Fahrenheit |
| humidity_pct | Float64 | Relative humidity (0-100) |
| wind_speed_kmh | Float64 | Wind speed in km/h |
| precipitation_mm | Float64 | Precipitation in mm |
| weather_code | Int64 | WMO weather code (0-99) |
| ingested_at | Datetime | ETL ingestion timestamp |
| source | String | Data provider ("open-meteo") |

---

### Load Module (`src/load.py`)

**Purpose**: Insert data into PostgreSQL with connection pooling and idempotency.

**Connection Management:**

```python
from psycopg2.pool import SimpleConnectionPool

# Connection pool (1-10 connections)
pool = SimpleConnectionPool(
    minconn=1,
    maxconn=10,
    host=os.getenv("DB_HOST"),
    port=int(os.getenv("DB_PORT", 5432)),
    database=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
)

@contextmanager
def get_db_connection():
    """Context manager for safe connection handling."""
    conn = pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)
```

**Two-Phase Loading:**

**Phase 1: Ensure locations exist**
```sql
INSERT INTO locations (city_name, country_code, latitude, longitude)
VALUES
    ('Cairo', 'EG', 30.0444, 31.2357),
    ('London', 'GB', 51.5074, -0.1278),
    ...
ON CONFLICT (city_name, country_code) DO NOTHING
RETURNING id, city_name;
```

**Phase 2: Insert weather readings**
```sql
INSERT INTO weather_readings (
    location_id, recorded_at, temperature_c, temperature_f,
    humidity_pct, wind_speed_kmh, precipitation_mm, weather_code,
    ingested_at, source
)
VALUES %s
ON CONFLICT (location_id, recorded_at) DO NOTHING;
```

**Batch Insert Performance:**
```python
from psycopg2.extras import execute_values

# Single query for all rows (10-100x faster than loop)
execute_values(cursor, insert_query, records, page_size=1000)
```

---

## Database Schema

### Locations Table

```sql
CREATE TABLE locations (
    id SERIAL PRIMARY KEY,
    city_name VARCHAR(100) NOT NULL,
    country_code CHAR(2) NOT NULL,
    latitude NUMERIC(8,6) NOT NULL,
    longitude NUMERIC(9,6) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT uq_location_identity UNIQUE (city_name, country_code)
);

CREATE INDEX idx_locations_coordinates ON locations (latitude, longitude);
```

**Design Rationale:**
- `SERIAL` primary key for simple joins
- Unique constraint prevents duplicate cities
- Coordinates indexed for geospatial queries (future feature)

### Weather Readings Table

```sql
CREATE TABLE weather_readings (
    id SERIAL PRIMARY KEY,
    location_id INTEGER NOT NULL REFERENCES locations(id) ON DELETE CASCADE,
    recorded_at TIMESTAMP NOT NULL,
    temperature_c NUMERIC(5,2),
    temperature_f NUMERIC(5,2),
    humidity_pct NUMERIC(5,2),
    wind_speed_kmh NUMERIC(6,2),
    precipitation_mm NUMERIC(6,2),
    weather_code INTEGER,
    ingested_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    source VARCHAR(50) NOT NULL DEFAULT 'open-meteo',
    
    CONSTRAINT uq_reading_identity UNIQUE (location_id, recorded_at)
);

-- Performance indexes
CREATE INDEX idx_readings_location_time ON weather_readings (location_id, recorded_at DESC);
CREATE INDEX idx_readings_time ON weather_readings (recorded_at DESC);
CREATE INDEX idx_readings_ingested_at ON weather_readings (ingested_at DESC);
```

**Design Rationale:**
- Composite unique constraint enables idempotent inserts
- `ON DELETE CASCADE` ensures referential integrity
- Three indexes support different query patterns (see Index Strategy)

---

## Index Strategy

### 1. `idx_readings_location_time` (location_id, recorded_at DESC)

**Purpose**: Primary index for filtered time-series queries.

**Supports:**
```sql
-- Typical dashboard query
SELECT * FROM weather_readings 
WHERE location_id = 1 
  AND recorded_at BETWEEN '2024-03-01' AND '2024-03-07'
ORDER BY recorded_at DESC;
```

**Why composite?**
- Most queries filter by both location AND time range
- DESC ordering optimizes "latest first" sorts
- Single index serves multiple query patterns

### 2. `idx_readings_time` (recorded_at DESC)

**Purpose**: Global temporal index for cross-location queries.

**Supports:**
```sql
-- Latest readings across all cities
SELECT DISTINCT ON (location_id) *
FROM weather_readings
ORDER BY location_id, recorded_at DESC;
```

### 3. `idx_readings_ingested_at` (ingested_at DESC)

**Purpose**: ETL monitoring and data quality checks.

**Supports:**
```sql
-- Check for stale data
SELECT location_id, MAX(ingested_at) AS last_ingestion
FROM weather_readings
GROUP BY location_id;
```

---

## Dashboard Architecture

### Streamlit Application (`dashboard/app.py`)

**Structure:**

```python
# Page 1: Current Conditions
def show_current_conditions():
    """Display latest readings with metric cards."""
    st.metric("Temperature", f"{temp}°C", delta=f"{delta}°C")
    # 4 metrics + weather badges

# Page 2: Historical Trends
def show_historical_trends():
    """Time-series visualizations with Plotly."""
    fig = px.line(df, x='recorded_at', y='temperature_c', color='city_name')
    st.plotly_chart(fig, use_container_width=True)

# Page 3: City Comparison
def show_city_comparison():
    """Side-by-side city comparison at specific time."""
    timestamp = st.slider("Select Timestamp", ...)
    st.dataframe(comparison_df)
```

**Query Layer (`dashboard/queries.py`):**

```python
@st.cache_data(ttl=300)  # 5-minute cache
def get_latest_readings(conn, city_names: list[str]) -> pl.DataFrame:
    """Fetch latest reading per city with caching."""
    query = """
        SELECT DISTINCT ON (l.city_name) ...
        FROM weather_readings wr
        JOIN locations l ON wr.location_id = l.id
        WHERE l.city_name = ANY(%s)
        ORDER BY l.city_name, wr.recorded_at DESC
    """
    return pl.read_database(query, conn, params=(city_names,))
```

**Caching Strategy:**
- 5-minute TTL on all queries
- Invalidated on sidebar input changes
- Reduces database load by 80%+

---

## Key Design Decisions

### ADR-001: Why Polars over Pandas?

**Decision**: Use Polars as primary DataFrame library.

**Rationale:**
- **Performance**: 5-10x faster than pandas for most operations
- **Memory Efficiency**: Rust-backed, zero-copy operations
- **Modern API**: Cleaner syntax, better type hints
- **Lazy Evaluation**: Optimizes query plans automatically

**Trade-offs:**
- Smaller community (fewer StackOverflow answers)
- Some libraries expect pandas (requires `.to_pandas()`)
- Less mature (pandas has 15+ years)

**When to reconsider:**
- If pandas-only library integration becomes critical
- If team has strong pandas expertise

### ADR-002: Why Connection Pooling?

**Decision**: Use `SimpleConnectionPool(1-10 connections)`.

**Rationale:**
- **Performance**: 10-100x faster connection acquisition
- **Resource Management**: Prevents connection exhaustion
- **Thread Safety**: Safe for concurrent requests (dashboard)

**Trade-offs:**
- Slightly more complex than single connection
- Requires careful cleanup (context managers)

**Metrics:**
- Single connection: 50-100ms per acquisition
- Connection pool: < 1ms per acquisition

### ADR-003: Why Idempotent Operations?

**Decision**: Use `ON CONFLICT DO NOTHING` for all inserts.

**Rationale:**
- **Reliability**: Safe to re-run pipeline on failures
- **Simplicity**: No need for complex de-duplication logic
- **Performance**: Database handles conflict detection efficiently

**Trade-offs:**
- Slightly slower than INSERT without conflict handling (~5%)
- Cannot detect if row was actually inserted (OK for our use case)

### ADR-004: Why Batch Inserts?

**Decision**: Use `execute_values()` instead of row-by-row inserts.

**Rationale:**
- **Performance**: 10-100x faster than looping
- **Network Efficiency**: Single round-trip to database
- **Transaction Safety**: All-or-nothing commit

**Metrics:**
- Row-by-row: 840 rows × 5ms = 4.2 seconds
- Batch insert: 840 rows in 50ms

---

## Code Highlights

### Type Safety (100% Coverage)

```python
def fetch_weather_data(
    latitude: float,
    longitude: float,
    hourly_fields: list[str] | None = None,  # Modern union syntax
    timezone: str = "UTC",
    timeout: int = 30,
) -> dict[str, Any]:
    """Comprehensive type hints for maintainability."""
```

### Context Managers

```python
@contextmanager
def get_db_connection() -> Generator[psycopg2.extensions.connection, None, None]:
    """Guarantees connection cleanup even on exceptions."""
    conn = pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)
```

### Polars Method Chaining

```python
df = (
    pl.DataFrame(data)
    .with_columns(pl.col("recorded_at").str.to_datetime("%Y-%m-%dT%H:%M"))
    .with_columns((pl.col("temperature_c") * 9.0 / 5.0 + 32.0).alias("temperature_f"))
    .unique(subset=["city_name", "recorded_at"])
)
```

---

## Performance Characteristics

### Current Performance (5 Cities)

| Phase | Duration | Bottleneck |
|-------|----------|------------|
| **Extract** | 25s (93%) | Serial API calls |
| **Transform** | 10ms (0.04%) | Polars is fast |
| **Load** | 1.8s (7%) | Network + validation |
| **Total** | 27s | Extract dominates |

### Optimization Opportunities

**P0 - Parallel Extraction (3 hours implementation):**
- Change: Serial → ThreadPoolExecutor
- Impact: 25s → 5s (80% faster)
- At 100 cities: 8m40s → 9.5s (56x faster)

**P1 - Vectorized Load (1.5 hours implementation):**
- Change: Python loops → Polars bulk operations
- Impact: 1.8s → 0.3s (85% faster)

**P2 - Dashboard Query Limits (30 minutes):**
- Change: Add `LIMIT 1000` to all queries
- Impact: Prevents browser crashes at scale

See [docs/PERFORMANCE.md](PERFORMANCE.md) for detailed analysis.

---

## Monitoring Considerations

### Recommended Metrics

| Metric | Target | Alert Threshold |
|--------|--------|-----------------|
| Pipeline Success Rate | 99%+ | < 95% in 24h |
| Pipeline Duration | < 30s | > 2 minutes |
| Data Freshness | < 1 hour | > 2 hours |
| API Timeout Rate | 0% | > 10% |
| Duplicate Rate | < 1% | > 5% |

### Monitoring Implementation

**Option 1: Database Tracking**
```sql
CREATE TABLE pipeline_runs (
    id SERIAL PRIMARY KEY,
    started_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,
    status VARCHAR(20),
    cities_attempted INTEGER,
    cities_succeeded INTEGER,
    rows_inserted INTEGER,
    duration_seconds NUMERIC(10,2),
    error_message TEXT
);
```

**Option 2: Prometheus + Grafana**
- Export metrics via prometheus_client
- Grafana dashboards for visualization
- Alertmanager for notifications

---

## Scalability Analysis

### Current Limits

| Component | Bottleneck At | Mitigation |
|-----------|---------------|------------|
| API Calls | ~50 cities (rate limits) | Parallel + rate limiting |
| Memory | ~100K rows (unlikely) | Polars handles this |
| Database | ~100K rows/batch | Switch to COPY |
| Query Performance | 100M+ rows | Partitioning |

### Scaling to 100 Cities

**Projected Metrics:**
- Rows per run: 16,800 (vs 840 currently)
- Annual data: 147M rows (vs 7.3M currently)
- Storage: 70GB (vs 3.5GB currently)

**Required Changes:**
1. Parallel API extraction (already designed)
2. Database partitioning (monthly or yearly)
3. Materialized views for aggregations
4. Connection pool tuning (10 → 50 connections)

---

## Future Enhancements

### Phase 1: Testing (Priority)
- Unit tests for all modules
- Integration tests for full pipeline
- Mock API responses for testing

### Phase 2: Performance
- Parallel extraction implementation
- Query optimization
- Dashboard pagination

### Phase 3: Enterprise Features
- Prometheus metrics export
- Automated backfill on gaps
- Apache Airflow orchestration
- Real-time streaming with Kafka

---

## References

- [Polars Documentation](https://pola-rs.github.io/polars/)
- [Open-Meteo API Docs](https://open-meteo.com/en/docs)
- [PostgreSQL Performance Tuning](https://wiki.postgresql.org/wiki/Performance_Optimization)
- [Streamlit Best Practices](https://docs.streamlit.io/library/advanced-features/caching)
