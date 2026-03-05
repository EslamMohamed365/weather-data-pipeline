# Weather Data Pipeline - Architecture Review

**Review Date**: March 5, 2026  
**Reviewer**: Senior Data Engineer  
**Project Version**: 1.0.0

---

## Executive Summary

This architecture review evaluates the Weather Data Pipeline from a production data engineering perspective, focusing on data quality, monitoring, scalability, and error recovery. The pipeline demonstrates solid foundational design with clear opportunities for enhancement as workloads scale.

**Overall Assessment**: ✅ **Production-Ready for Small-to-Medium Scale**

- **Current Capacity**: 5 cities × 168 hourly records = 840 rows/run
- **Estimated Annual Data Volume**: ~7.3M rows (~3.5GB)
- **Suitable For**: Portfolio projects, departmental analytics, proof-of-concept deployments

---

## 1. Data Quality Checks

### Current State ✅

The pipeline implements **basic data integrity** through:

- Database-level constraints (`UNIQUE`, `FOREIGN KEY`, `NOT NULL`)
- Idempotent inserts via `ON CONFLICT DO NOTHING`
- Retry logic with exponential backoff (3 attempts)
- Partial failure handling (continues if one city fails)

### Recommended Enhancements 🔧

#### 1.1 Pre-Load Validation Layer

**Add validation before database insertion:**

```python
# src/validators.py
from dataclasses import dataclass
from typing import List
import polars as pl

@dataclass
class ValidationResult:
    passed: bool
    warnings: List[str]
    errors: List[str]
    metrics: dict

def validate_weather_data(df: pl.DataFrame) -> ValidationResult:
    """
    Comprehensive data quality checks before loading.
    """
    warnings = []
    errors = []
    metrics = {}
    
    # 1. Schema validation
    expected_columns = [
        'city_name', 'recorded_at', 'temperature_c', 'temperature_f',
        'humidity_pct', 'wind_speed_kmh', 'precipitation_mm', 'weather_code'
    ]
    missing_cols = set(expected_columns) - set(df.columns)
    if missing_cols:
        errors.append(f"Missing columns: {missing_cols}")
    
    # 2. Temperature range check (-100°C to 60°C is physically plausible)
    temp_outliers = df.filter(
        (pl.col('temperature_c') < -100) | (pl.col('temperature_c') > 60)
    )
    if len(temp_outliers) > 0:
        warnings.append(f"Found {len(temp_outliers)} temperature outliers")
        metrics['temperature_outliers'] = len(temp_outliers)
    
    # 3. Humidity validation (0-100%)
    humidity_invalid = df.filter(
        (pl.col('humidity_pct') < 0) | (pl.col('humidity_pct') > 100)
    )
    if len(humidity_invalid) > 0:
        warnings.append(f"Found {len(humidity_invalid)} invalid humidity values")
    
    # 4. Wind speed sanity check (>500 km/h is tornado/hurricane)
    extreme_wind = df.filter(pl.col('wind_speed_kmh') > 500)
    if len(extreme_wind) > 0:
        warnings.append(f"Found {len(extreme_wind)} extreme wind speeds")
    
    # 5. Timestamp freshness (data should be within 7 days)
    from datetime import datetime, timezone, timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    stale_data = df.filter(pl.col('recorded_at') < cutoff)
    if len(stale_data) > 0:
        warnings.append(f"Found {len(stale_data)} stale records (>7 days old)")
    
    # 6. Null percentage tracking
    for col in df.columns:
        null_pct = df[col].null_count() / len(df) * 100
        if null_pct > 20:
            warnings.append(f"Column '{col}' has {null_pct:.1f}% null values")
        metrics[f'null_pct_{col}'] = null_pct
    
    # 7. Duplicate detection (before DB insert)
    duplicate_count = len(df) - len(df.unique(subset=['city_name', 'recorded_at']))
    if duplicate_count > 0:
        warnings.append(f"Found {duplicate_count} duplicate records (will be removed)")
        metrics['duplicates'] = duplicate_count
    
    # 8. Record count validation
    expected_min_rows = 168 * 0.8  # Allow 20% data loss per city
    actual_rows = len(df.filter(pl.col('city_name') == df['city_name'][0]))
    if actual_rows < expected_min_rows:
        warnings.append(f"Low record count: {actual_rows} < {expected_min_rows}")
    
    passed = len(errors) == 0
    return ValidationResult(passed, warnings, errors, metrics)
```

**Integration point:**

```python
# In src/pipeline.py
transformed_df = transform.clean_data(raw_data)
validation = validate_weather_data(transformed_df)

if not validation.passed:
    logger.error(f"Validation failed: {validation.errors}")
    raise ValueError("Data quality check failed")

for warning in validation.warnings:
    logger.warning(warning)

# Log metrics for monitoring
logger.info(f"Data quality metrics: {validation.metrics}")
```

#### 1.2 Statistical Anomaly Detection

**Detect unusual patterns using historical baselines:**

```sql
-- Example: Detect temperature anomalies using 30-day rolling average
WITH stats AS (
    SELECT
        location_id,
        AVG(temperature_c) as mean_temp,
        STDDEV(temperature_c) as stddev_temp
    FROM weather_readings
    WHERE recorded_at >= NOW() - INTERVAL '30 days'
    GROUP BY location_id
)
SELECT w.id, w.city_name, w.temperature_c,
       ABS(w.temperature_c - s.mean_temp) / s.stddev_temp AS z_score
FROM weather_readings w
JOIN stats s ON w.location_id = s.location_id
WHERE ABS(w.temperature_c - s.mean_temp) / s.stddev_temp > 3  -- 3-sigma rule
    AND w.recorded_at >= NOW() - INTERVAL '1 day';
```

#### 1.3 Data Quality Scorecard Table

**Track quality metrics over time:**

```sql
CREATE TABLE data_quality_metrics (
    id SERIAL PRIMARY KEY,
    pipeline_run_id INTEGER,
    metric_name VARCHAR(100) NOT NULL,
    metric_value NUMERIC,
    metric_unit VARCHAR(20),
    severity VARCHAR(20),  -- 'info', 'warning', 'error'
    recorded_at TIMESTAMP DEFAULT NOW()
);

-- Example insert from pipeline
INSERT INTO data_quality_metrics (pipeline_run_id, metric_name, metric_value, severity)
VALUES
    (123, 'temperature_outliers', 0, 'info'),
    (123, 'null_pct_humidity', 2.5, 'info'),
    (123, 'stale_records', 12, 'warning');
```

---

## 2. Monitoring Considerations

### Current State ⚠️

**Gaps:**
- No centralized monitoring dashboard
- Logging to stdout (ephemeral in containers)
- No alerting mechanism
- No SLA tracking

### Recommended Monitoring Stack 📊

#### 2.1 Key Metrics & Targets

| Metric Category | Metric | Target | Alert Threshold | Collection Method |
|-----------------|--------|--------|-----------------|-------------------|
| **Pipeline Health** | Success rate | 99%+ | < 95% in 24h | Database run log |
| | Runtime duration | < 30s | > 2 minutes | Python logging |
| | Runs per day | 24 (hourly) | < 20 runs | Cron + DB log |
| **Data Freshness** | Lag since last update | < 1 hour | > 2 hours | `MAX(ingested_at)` query |
| | Missing hours (gaps) | 0 | > 5 gaps/day | Gap detection query |
| **API Performance** | Response time (avg) | < 5s | > 10s | Request timing |
| | HTTP 4xx rate | 0% | > 1% | Exception counting |
| | HTTP 5xx rate | 0% | > 5% | Exception counting |
| | Timeout rate | 0% | > 10% | Retry counter |
| **Data Volume** | Rows inserted/run | 840 (5 cities) | < 500 | INSERT counter |
| | Duplicate rate | < 1% | > 5% | CONFLICT counter |
| | Total database size | ~3.5GB/year | 10x spike | `pg_database_size()` |
| **Data Quality** | Null percentage | < 5% | > 20% | Column stats |
| | Outlier rate | < 0.1% | > 5% | Validation checks |
| | Schema drift events | 0 | > 0 | Column mismatch |

#### 2.2 Implementation: Pipeline Run Tracking

**Create monitoring table:**

```sql
CREATE TABLE pipeline_runs (
    id SERIAL PRIMARY KEY,
    started_at TIMESTAMP NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMP,
    status VARCHAR(20) NOT NULL,  -- 'running', 'success', 'failed', 'partial'
    
    -- Metrics
    cities_attempted INTEGER,
    cities_succeeded INTEGER,
    rows_fetched INTEGER,
    rows_inserted INTEGER,
    rows_skipped INTEGER,
    
    -- Performance
    duration_seconds NUMERIC(10, 2),
    avg_api_response_ms NUMERIC(10, 2),
    
    -- Errors
    error_message TEXT,
    error_traceback TEXT,
    
    -- Environment
    hostname VARCHAR(255),
    python_version VARCHAR(50),
    
    -- Hash for idempotency tracking
    run_hash VARCHAR(64)  -- Hash of (cities + timestamp range)
);

-- Index for monitoring queries
CREATE INDEX idx_pipeline_runs_started ON pipeline_runs(started_at DESC);
CREATE INDEX idx_pipeline_runs_status ON pipeline_runs(status);
```

**Instrument pipeline code:**

```python
# src/pipeline.py
import time
import socket
import sys
from contextlib import contextmanager

@contextmanager
def track_pipeline_run(conn):
    """Context manager to track pipeline execution."""
    run_id = None
    started_at = time.time()
    
    try:
        # Insert run start
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO pipeline_runs (started_at, status, hostname, python_version)
            VALUES (NOW(), 'running', %s, %s)
            RETURNING id
            """,
            (socket.gethostname(), sys.version.split()[0])
        )
        run_id = cursor.fetchone()[0]
        conn.commit()
        
        yield run_id
        
        # Update on success
        duration = time.time() - started_at
        cursor.execute(
            """
            UPDATE pipeline_runs
            SET completed_at = NOW(),
                status = 'success',
                duration_seconds = %s
            WHERE id = %s
            """,
            (duration, run_id)
        )
        conn.commit()
        
    except Exception as e:
        # Update on failure
        duration = time.time() - started_at
        if run_id:
            cursor.execute(
                """
                UPDATE pipeline_runs
                SET completed_at = NOW(),
                    status = 'failed',
                    duration_seconds = %s,
                    error_message = %s,
                    error_traceback = %s
                WHERE id = %s
                """,
                (duration, str(e), traceback.format_exc(), run_id)
            )
            conn.commit()
        raise
```

#### 2.3 Monitoring Dashboard Options

**Option A: Simple SQL Monitoring (No External Tools)**

```sql
-- Dashboard query: Last 24 hours pipeline health
SELECT
    DATE_TRUNC('hour', started_at) AS hour,
    COUNT(*) AS total_runs,
    SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) AS successful,
    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed,
    ROUND(AVG(duration_seconds), 2) AS avg_duration_sec,
    ROUND(AVG(rows_inserted), 0) AS avg_rows_inserted
FROM pipeline_runs
WHERE started_at >= NOW() - INTERVAL '24 hours'
GROUP BY hour
ORDER BY hour DESC;
```

**Option B: Streamlit Monitoring Page**

Add to `dashboard/app.py`:

```python
# New page: "Pipeline Health"
def show_pipeline_health():
    st.header("Pipeline Health Monitor")
    
    # Success rate (last 24h)
    success_rate = get_success_rate(conn, hours=24)
    st.metric("Success Rate (24h)", f"{success_rate:.1f}%",
              delta=f"Target: 99%")
    
    # Runtime chart
    runtime_df = get_runtime_trend(conn, days=7)
    st.line_chart(runtime_df, x='hour', y='duration_seconds')
    
    # Data freshness
    last_update = get_last_ingestion_time(conn)
    minutes_ago = (datetime.now() - last_update).total_seconds() / 60
    st.metric("Data Freshness", f"{minutes_ago:.0f} minutes ago",
              delta="-30 min" if minutes_ago < 60 else f"+{minutes_ago-60:.0f} min")
    
    # Recent failures
    st.subheader("Recent Failures")
    failures = get_recent_failures(conn, limit=10)
    st.dataframe(failures)
```

**Option C: Prometheus + Grafana (Production-Grade)**

1. **Export metrics from pipeline:**

```python
# src/metrics.py
from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry, push_to_gateway

registry = CollectorRegistry()

pipeline_runs_total = Counter(
    'weather_pipeline_runs_total',
    'Total pipeline runs',
    ['status'],
    registry=registry
)

pipeline_duration_seconds = Histogram(
    'weather_pipeline_duration_seconds',
    'Pipeline execution duration',
    registry=registry
)

rows_inserted_total = Counter(
    'weather_pipeline_rows_inserted_total',
    'Total rows inserted',
    registry=registry
)

data_freshness_seconds = Gauge(
    'weather_pipeline_data_freshness_seconds',
    'Seconds since last data ingestion',
    registry=registry
)

# In pipeline.py
from src.metrics import pipeline_runs_total, pipeline_duration_seconds

def run_pipeline():
    start = time.time()
    try:
        # ... pipeline logic ...
        pipeline_runs_total.labels(status='success').inc()
    except Exception as e:
        pipeline_runs_total.labels(status='failed').inc()
        raise
    finally:
        duration = time.time() - start
        pipeline_duration_seconds.observe(duration)
```

2. **Push to Prometheus Pushgateway:**

```python
from prometheus_client import push_to_gateway

push_to_gateway('localhost:9091', job='weather_pipeline', registry=registry)
```

3. **Grafana dashboard queries:**

```promql
# Success rate (last 1h)
rate(weather_pipeline_runs_total{status="success"}[1h]) /
rate(weather_pipeline_runs_total[1h]) * 100

# Average duration
rate(weather_pipeline_duration_seconds_sum[5m]) /
rate(weather_pipeline_duration_seconds_count[5m])

# Data freshness
weather_pipeline_data_freshness_seconds
```

#### 2.4 Alerting Strategy

**Critical Alerts (Page Immediately):**

| Condition | Threshold | Action |
|-----------|-----------|--------|
| Pipeline failure rate | > 50% in 1 hour | Page on-call engineer |
| Data freshness | > 4 hours stale | Page + auto-trigger backfill |
| Database connection failure | 3+ consecutive runs | Page + check DB health |

**Warning Alerts (Notify Team Channel):**

| Condition | Threshold | Action |
|-----------|-----------|--------|
| Single pipeline failure | Any failure | Slack notification |
| Data freshness | > 2 hours stale | Slack warning |
| Slow performance | > 2 minutes runtime | Investigate API/DB |
| High duplicate rate | > 5% duplicates | Check for clock drift |

**Implementation with healthchecks.io (simple):**

```python
# src/pipeline.py
import requests

HEALTHCHECK_URL = "https://hc-ping.com/your-uuid-here"

def run_pipeline():
    try:
        # ... pipeline logic ...
        requests.get(HEALTHCHECK_URL, timeout=10)  # Success ping
    except Exception as e:
        requests.get(f"{HEALTHCHECK_URL}/fail", timeout=10)  # Failure ping
        raise
```

---

## 3. Scalability Analysis

### Current Architecture Limits

| Component | Current | Bottleneck At | Mitigation |
|-----------|---------|---------------|------------|
| **API Calls** | 5 cities | ~50 cities (rate limits) | Parallel requests with rate limiting |
| **Memory** | 840 rows | ~100K rows | Polars handles this easily (use lazy evaluation for 1M+) |
| **Database Inserts** | 840 rows | ~100K rows/batch | Switch to COPY or batch larger inserts |
| **Pipeline Runtime** | ~15s | ~5 min (100 cities) | Parallelize extraction with ThreadPoolExecutor |
| **Database Size** | 7.3M rows/year | 100M+ rows | Partition by `recorded_at` (monthly/yearly) |
| **Query Performance** | Indexed queries | Full table scans on 100M+ rows | Materialized views, partitioning |

### Scaling to 100 Cities (16,800 rows/run)

**Estimated Impact:**

- **API Calls**: 5 → 100 (20x increase)
  - Serial execution: 15s × 20 = **5 minutes** ❌
  - Parallel execution (10 threads): **~1 minute** ✅

- **Memory**: 840 rows → 16,800 rows (20x increase)
  - Current: ~1MB
  - At scale: ~20MB ✅ (negligible)

- **Database Inserts**: 840 → 16,800 rows
  - `executemany`: ~500ms ✅
  - `COPY`: ~50ms ✅

- **Annual Data Volume**: 7.3M → 147M rows
  - Storage: 3.5GB → 70GB ✅ (manageable)
  - Index size: ~10GB ✅

**Recommended Changes for 100 Cities:**

#### 3.1 Parallel API Extraction

```python
# src/extract.py
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

def extract_weather_parallel(
    cities: list[City],
    max_workers: int = 10,
    rate_limit_per_second: float = 10.0
) -> list[tuple[str, dict]]:
    """
    Fetch weather data in parallel with rate limiting.
    
    Args:
        cities: List of cities to fetch
        max_workers: Max concurrent requests
        rate_limit_per_second: Max API calls per second
    """
    results = []
    delay_between_calls = 1.0 / rate_limit_per_second
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_city = {
            executor.submit(fetch_weather_data, city.latitude, city.longitude): city
            for city in cities
        }
        
        # Process completed tasks
        for future in as_completed(future_to_city):
            city = future_to_city[future]
            try:
                data = future.result()
                results.append((city.name, data))
                logger.info(f"✓ {city.name}")
            except Exception as e:
                logger.error(f"✗ {city.name}: {e}")
            
            # Rate limiting
            time.sleep(delay_between_calls)
    
    return results
```

#### 3.2 Bulk Insert Optimization

```python
# src/load.py
import io
import csv

def bulk_insert_with_copy(conn, df: pl.DataFrame):
    """
    Use PostgreSQL COPY for 10x faster inserts.
    """
    # Convert Polars DataFrame to CSV buffer
    buffer = io.StringIO()
    df.write_csv(buffer)
    buffer.seek(0)
    
    # Use COPY command
    cursor = conn.cursor()
    cursor.copy_expert(
        """
        COPY weather_readings (
            location_id, recorded_at, temperature_c, temperature_f,
            humidity_pct, wind_speed_kmh, precipitation_mm, weather_code,
            ingested_at, source
        )
        FROM STDIN WITH CSV HEADER
        ON CONFLICT (location_id, recorded_at) DO NOTHING
        """,
        buffer
    )
    
    rows_inserted = cursor.rowcount
    conn.commit()
    return rows_inserted
```

#### 3.3 Database Partitioning (for 100M+ rows)

```sql
-- Convert to partitioned table
CREATE TABLE weather_readings_new (
    LIKE weather_readings INCLUDING ALL
) PARTITION BY RANGE (recorded_at);

-- Create monthly partitions
CREATE TABLE weather_readings_2024_01 PARTITION OF weather_readings_new
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

CREATE TABLE weather_readings_2024_02 PARTITION OF weather_readings_new
    FOR VALUES FROM ('2024-02-01') TO ('2024-03-01');

-- Migrate data
INSERT INTO weather_readings_new SELECT * FROM weather_readings;

-- Swap tables
ALTER TABLE weather_readings RENAME TO weather_readings_old;
ALTER TABLE weather_readings_new RENAME TO weather_readings;

-- Automate partition creation with cron
-- Script: sql/create_monthly_partition.sql
DO $$
DECLARE
    partition_date DATE := DATE_TRUNC('month', NOW() + INTERVAL '1 month');
    partition_name TEXT := 'weather_readings_' || TO_CHAR(partition_date, 'YYYY_MM');
    start_date TEXT := TO_CHAR(partition_date, 'YYYY-MM-DD');
    end_date TEXT := TO_CHAR(partition_date + INTERVAL '1 month', 'YYYY-MM-DD');
BEGIN
    EXECUTE format(
        'CREATE TABLE IF NOT EXISTS %I PARTITION OF weather_readings FOR VALUES FROM (%L) TO (%L)',
        partition_name, start_date, end_date
    );
END $$;
```

#### 3.4 Query Optimization with Materialized Views

```sql
-- Pre-compute daily aggregates for faster dashboard queries
CREATE MATERIALIZED VIEW daily_weather_summary AS
SELECT
    l.city_name,
    DATE(w.recorded_at) AS date,
    ROUND(AVG(w.temperature_c)::numeric, 2) AS avg_temp_c,
    ROUND(MIN(w.temperature_c)::numeric, 2) AS min_temp_c,
    ROUND(MAX(w.temperature_c)::numeric, 2) AS max_temp_c,
    ROUND(AVG(w.humidity_pct)::numeric, 2) AS avg_humidity,
    ROUND(SUM(w.precipitation_mm)::numeric, 2) AS total_precipitation_mm
FROM weather_readings w
JOIN locations l ON w.location_id = l.id
GROUP BY l.city_name, DATE(w.recorded_at);

-- Index for fast lookups
CREATE INDEX idx_daily_summary_city_date ON daily_weather_summary(city_name, date DESC);

-- Refresh strategy (run after pipeline)
REFRESH MATERIALIZED VIEW CONCURRENTLY daily_weather_summary;
```

---

## 4. Error Recovery Strategies

### Current State ✅

**Existing resilience:**
- 3-attempt retry with exponential backoff
- Partial failure handling (continues with other cities)
- Idempotent inserts (re-running doesn't create duplicates)

### Enhanced Recovery Strategies 🔧

#### 4.1 Scenario: API Down for 6 Hours

**Problem:** Miss 6 hourly runs = 5,040 missing records (6 runs × 840 rows)

**Solution: Automated Backfill Script**

```python
# src/backfill.py
from datetime import datetime, timedelta
import polars as pl

def detect_gaps(conn, lookback_days: int = 7) -> pl.DataFrame:
    """
    Detect missing hourly records for each location.
    """
    query = """
    WITH expected_hours AS (
        SELECT
            l.id AS location_id,
            l.city_name,
            generate_series(
                NOW() - INTERVAL '%s days',
                NOW(),
                '1 hour'::INTERVAL
            ) AS expected_hour
        FROM locations l
    )
    SELECT
        eh.location_id,
        eh.city_name,
        eh.expected_hour AS missing_hour
    FROM expected_hours eh
    LEFT JOIN weather_readings w
        ON w.location_id = eh.location_id
        AND DATE_TRUNC('hour', w.recorded_at) = DATE_TRUNC('hour', eh.expected_hour)
    WHERE w.id IS NULL
    ORDER BY eh.location_id, eh.expected_hour;
    """
    return pl.read_database(query % lookback_days, conn)

def backfill_missing_data(conn, gaps_df: pl.DataFrame):
    """
    Fetch historical data for missing hours using Open-Meteo Archive API.
    """
    # Open-Meteo Archive API (historical data)
    ARCHIVE_API = "https://archive-api.open-meteo.com/v1/archive"
    
    # Group by location and date range
    for location_id, group in gaps_df.groupby('location_id'):
        city_name = group['city_name'][0]
        missing_hours = group['missing_hour'].to_list()
        
        # Batch by date (API limits)
        start_date = min(missing_hours).date()
        end_date = max(missing_hours).date()
        
        logger.info(f"Backfilling {city_name}: {len(missing_hours)} hours ({start_date} to {end_date})")
        
        # Fetch historical data
        location = get_location_by_id(conn, location_id)
        params = {
            'latitude': location.latitude,
            'longitude': location.longitude,
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'hourly': 'temperature_2m,relative_humidity_2m,wind_speed_10m,precipitation,weathercode'
        }
        
        response = requests.get(ARCHIVE_API, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        # Transform and load
        df = transform_historical_data(city_name, data)
        load_to_database(conn, df)
        
        logger.info(f"✓ Backfilled {len(df)} records for {city_name}")

# Automated backfill check (run in cron after main pipeline)
if __name__ == '__main__':
    conn = connect_to_db()
    gaps = detect_gaps(conn, lookback_days=7)
    
    if len(gaps) > 0:
        logger.warning(f"Found {len(gaps)} missing hourly records")
        backfill_missing_data(conn, gaps)
    else:
        logger.info("No gaps detected - data complete")
```

**Cron setup:**

```bash
# Run backfill check daily at 2 AM
0 2 * * * cd /path/to/weather-pipeline && uv run python src/backfill.py >> logs/backfill.log 2>&1
```

#### 4.2 Scenario: Database Connection Failure

**Problem:** Pipeline can't connect to PostgreSQL (container down, network issue, credential change)

**Solution: Circuit Breaker + Dead Letter Queue**

```python
# src/resilience.py
import time
import pickle
from pathlib import Path

class CircuitBreaker:
    """
    Prevent repeated connection attempts to failing database.
    """
    def __init__(self, failure_threshold: int = 3, timeout: int = 300):
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.opened_at = None
        self.state = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN
    
    def call(self, func, *args, **kwargs):
        if self.state == 'OPEN':
            if time.time() - self.opened_at < self.timeout:
                raise Exception(f"Circuit breaker OPEN (retry in {self.timeout - (time.time() - self.opened_at):.0f}s)")
            else:
                self.state = 'HALF_OPEN'
                logger.info("Circuit breaker HALF_OPEN (testing connection)")
        
        try:
            result = func(*args, **kwargs)
            if self.state == 'HALF_OPEN':
                self.state = 'CLOSED'
                self.failure_count = 0
                logger.info("Circuit breaker CLOSED (connection restored)")
            return result
        except Exception as e:
            self.failure_count += 1
            if self.failure_count >= self.failure_threshold:
                self.state = 'OPEN'
                self.opened_at = time.time()
                logger.error(f"Circuit breaker OPEN (failed {self.failure_count} times)")
            raise e

class DeadLetterQueue:
    """
    Store failed pipeline data for later retry.
    """
    def __init__(self, queue_dir: Path = Path("./data/dlq")):
        self.queue_dir = queue_dir
        self.queue_dir.mkdir(parents=True, exist_ok=True)
    
    def enqueue(self, data: pl.DataFrame, error: Exception):
        """Save failed data with timestamp and error."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = self.queue_dir / f"failed_{timestamp}.pkl"
        
        payload = {
            'timestamp': datetime.now(),
            'error': str(error),
            'data': data.to_dict()
        }
        
        with open(filename, 'wb') as f:
            pickle.dump(payload, f)
        
        logger.warning(f"Enqueued {len(data)} rows to DLQ: {filename}")
    
    def process_queue(self, conn):
        """Retry loading all queued data."""
        files = sorted(self.queue_dir.glob("failed_*.pkl"))
        
        for file in files:
            try:
                with open(file, 'rb') as f:
                    payload = pickle.load(f)
                
                df = pl.DataFrame(payload['data'])
                load_to_database(conn, df)
                
                file.unlink()  # Delete on success
                logger.info(f"✓ Processed DLQ file: {file.name}")
            except Exception as e:
                logger.error(f"✗ Failed to process DLQ file {file.name}: {e}")

# Usage in pipeline.py
circuit_breaker = CircuitBreaker()
dlq = DeadLetterQueue()

def run_pipeline():
    # ... extract and transform ...
    
    try:
        conn = circuit_breaker.call(connect_to_database)
        load_to_database(conn, transformed_df)
    except Exception as e:
        logger.error(f"Failed to load data: {e}")
        dlq.enqueue(transformed_df, e)
        raise
```

#### 4.3 Scenario: Schema Drift (API Changes)

**Problem:** Open-Meteo adds/removes fields, breaking transformation

**Solution: Schema Validation + Graceful Degradation**

```python
# src/schema_validator.py
from typing import Dict, Any
import polars as pl

EXPECTED_API_SCHEMA = {
    'hourly': {
        'time': list,
        'temperature_2m': list,
        'relative_humidity_2m': list,
        'wind_speed_10m': list,
        'precipitation': list,
        'weathercode': list
    }
}

def validate_api_response(data: Dict[str, Any]) -> bool:
    """
    Validate API response matches expected schema.
    Alert if drift detected.
    """
    try:
        for section, expected_fields in EXPECTED_API_SCHEMA.items():
            if section not in data:
                logger.error(f"Missing section: {section}")
                return False
            
            for field, expected_type in expected_fields.items():
                if field not in data[section]:
                    logger.error(f"Missing field: {section}.{field}")
                    return False
                
                if not isinstance(data[section][field], expected_type):
                    logger.error(f"Type mismatch: {section}.{field} (expected {expected_type})")
                    return False
        
        return True
    except Exception as e:
        logger.error(f"Schema validation error: {e}")
        return False

def transform_with_fallback(data: Dict[str, Any]) -> pl.DataFrame:
    """
    Transform data with graceful handling of missing fields.
    """
    hourly = data.get('hourly', {})
    
    # Required fields
    df = pl.DataFrame({
        'recorded_at': hourly['time'],
        'temperature_c': hourly.get('temperature_2m', [None] * len(hourly['time'])),
    })
    
    # Optional fields (default to null if missing)
    optional_fields = {
        'humidity_pct': 'relative_humidity_2m',
        'wind_speed_kmh': 'wind_speed_10m',
        'precipitation_mm': 'precipitation',
        'weather_code': 'weathercode'
    }
    
    for col_name, api_field in optional_fields.items():
        if api_field in hourly:
            df = df.with_columns(pl.Series(col_name, hourly[api_field]))
        else:
            logger.warning(f"Missing field {api_field}, using nulls")
            df = df.with_columns(pl.lit(None).alias(col_name))
    
    return df
```

---

## 5. Architecture Decision Records (ADRs)

### ADR-001: Why Polars over Pandas?

**Decision:** Use Polars as the primary DataFrame library.

**Rationale:**
- **Performance**: 5-10x faster than pandas for most operations
- **Memory efficiency**: Rust-backed, zero-copy operations
- **Lazy evaluation**: Optimizes query plans automatically
- **Modern API**: Cleaner syntax, better type hints
- **Future-proof**: Growing ecosystem, active development

**Tradeoffs:**
- Smaller community than pandas (fewer StackOverflow answers)
- Some libraries expect pandas (requires `.to_pandas()` conversion)
- Less mature (pandas has 15+ years of battle-testing)

**When to reconsider:**
- If integration with pandas-only libraries becomes critical
- If team has strong pandas expertise but no Polars experience

---

### ADR-002: Why uv over pip/poetry?

**Decision:** Use uv for dependency management.

**Rationale:**
- **Speed**: 100x faster than pip (Rust-based)
- **Simplicity**: Single tool for deps + Python version management
- **Reproducibility**: `uv.lock` guarantees identical environments
- **Modern**: Built-in virtual env management

**Tradeoffs:**
- Newer tool (less mature than pip/poetry)
- Smaller ecosystem (fewer tutorials)

**When to reconsider:**
- If team uses monorepo with existing Poetry setup
- If complex build requirements need pip's flexibility

---

### ADR-003: Why PostgreSQL in Docker?

**Decision:** Run PostgreSQL in Docker container.

**Rationale:**
- **Isolation**: Doesn't pollute host OS
- **Consistency**: Same DB version across dev/staging/prod
- **Easy setup**: `docker-compose up` vs. manual install
- **Portability**: Works identically on macOS/Linux/Windows

**Tradeoffs:**
- Slight performance overhead (5-10%)
- Requires Docker knowledge
- Volume management adds complexity

**When to reconsider:**
- Production deployment (use managed RDS/Cloud SQL instead)
- Performance-critical workloads (bare-metal may be better)

---

## 6. Recommended Next Steps

### Short-Term (Next Sprint)

1. **Add data quality validation layer** (Section 1.1)
   - Implement `validators.py` module
   - Integrate into `pipeline.py`
   - Add quality metrics to logs

2. **Implement pipeline run tracking** (Section 2.2)
   - Create `pipeline_runs` table
   - Instrument pipeline code
   - Build basic monitoring queries

3. **Add backfill script** (Section 4.1)
   - Implement gap detection
   - Create `src/backfill.py`
   - Schedule daily cron job

### Medium-Term (Next Quarter)

4. **Set up monitoring dashboard** (Section 2.3)
   - Add Streamlit "Pipeline Health" page
   - Implement key metrics visualization
   - Configure alerts (healthchecks.io or PagerDuty)

5. **Optimize for 100 cities** (Section 3)
   - Parallelize API extraction
   - Implement COPY-based bulk inserts
   - Load test with 100 city configuration

6. **Add comprehensive error handling** (Section 4)
   - Implement circuit breaker
   - Create dead letter queue
   - Add schema drift detection

### Long-Term (Next Year)

7. **Production hardening**
   - Move to managed PostgreSQL (AWS RDS, Google Cloud SQL)
   - Implement proper secrets management (AWS Secrets Manager, HashiCorp Vault)
   - Set up CI/CD pipeline (GitHub Actions, GitLab CI)
   - Add comprehensive test suite (pytest, coverage >80%)

8. **Advanced features**
   - Real-time streaming with Kafka
   - Machine learning forecasting models
   - REST API for external consumers
   - dbt integration for SQL-based transformations

---

## 7. Final Assessment

### Strengths ✅

- ✅ Clean architecture with clear separation of concerns (Extract/Transform/Load)
- ✅ Idempotent pipeline design (re-running is safe)
- ✅ Proper use of modern tools (Polars, uv, Docker)
- ✅ Good database schema with appropriate indexes
- ✅ Retry logic and partial failure handling
- ✅ Well-documented codebase

### Areas for Improvement ⚠️

- ⚠️ Limited data quality validation
- ⚠️ No centralized monitoring/alerting
- ⚠️ Serial API extraction (slow for many cities)
- ⚠️ Logging to stdout (no persistence)
- ⚠️ No automated testing
- ⚠️ Manual backfill process

### Production Readiness Score: 7/10

| Category | Score | Notes |
|----------|-------|-------|
| Architecture | 9/10 | Solid ETL design, minor scalability concerns |
| Data Quality | 6/10 | Basic validation, needs comprehensive checks |
| Monitoring | 5/10 | Logging exists, but no dashboards/alerts |
| Scalability | 7/10 | Works for 5 cities, needs work for 100+ |
| Error Handling | 7/10 | Retry logic good, recovery could be better |
| Security | 8/10 | Credentials in .env, proper .gitignore |
| Documentation | 9/10 | Excellent README and inline comments |
| Testing | 3/10 | No automated tests currently |

---

## 8. Conclusion

This Weather Data Pipeline is **well-architected for a portfolio project** and demonstrates strong data engineering fundamentals. The use of modern tools (Polars, uv), proper containerization, and idempotent design show production-quality thinking.

**Key recommendations:**
1. Add data quality validation (catches issues early)
2. Implement monitoring dashboard (observe pipeline health)
3. Create backfill automation (handles API outages)
4. Parallelize extraction (scales to 100+ cities)

With these enhancements, the pipeline would be **production-ready for medium-scale deployments** (up to 100 cities, ~147M rows/year).

**Estimated effort to production-ready:**
- Data quality: 2 days
- Monitoring: 3 days
- Backfill automation: 2 days
- Parallelization: 1 day
- **Total: ~8 days of focused work**

The architecture is solid—these are refinements, not rewrites. Excellent work! 🚀

---

**Reviewed by**: Senior Data Engineer  
**Date**: March 5, 2026  
**Next Review**: After implementing short-term recommendations
