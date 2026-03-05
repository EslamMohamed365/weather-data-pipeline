# Weather Pipeline Database Schema

## Entity Relationship Diagram

```
┌────────────────────────────────────────────────┐
│                  LOCATIONS                     │
├────────────────────────────────────────────────┤
│ PK │ id               SERIAL                   │
│    │ city_name        VARCHAR(100)   NOT NULL  │
│    │ country_code     CHAR(2)        NOT NULL  │
│    │ latitude         NUMERIC(8,6)   NOT NULL  │
│    │ longitude        NUMERIC(9,6)   NOT NULL  │
│    │ created_at       TIMESTAMP      NOT NULL  │
├────────────────────────────────────────────────┤
│ UNIQUE: (city_name, country_code)              │
│ INDEX:  (latitude, longitude)                  │
└────────────────────────────────────────────────┘
                       │
                       │ 1:N
                       │ ON DELETE CASCADE
                       ▼
┌────────────────────────────────────────────────┐
│              WEATHER_READINGS                  │
├────────────────────────────────────────────────┤
│ PK │ id               SERIAL                   │
│ FK │ location_id      INTEGER        NOT NULL  │
│    │ recorded_at      TIMESTAMP      NOT NULL  │
│    │ temperature_c    NUMERIC(5,2)             │
│    │ temperature_f    NUMERIC(5,2)             │
│    │ humidity_pct     NUMERIC(5,2)             │
│    │ wind_speed_kmh   NUMERIC(6,2)             │
│    │ precipitation_mm NUMERIC(6,2)             │
│    │ weather_code     INTEGER                  │
│    │ ingested_at      TIMESTAMP      NOT NULL  │
│    │ source           VARCHAR(50)    NOT NULL  │
├────────────────────────────────────────────────┤
│ UNIQUE: (location_id, recorded_at)             │
│ INDEX:  (location_id, recorded_at DESC)        │
│ INDEX:  (recorded_at DESC)                     │
│ INDEX:  (ingested_at DESC)                     │
└────────────────────────────────────────────────┘
```

## Table Details

### locations
**Purpose**: Store unique geographical locations for weather tracking

| Column        | Type           | Constraints    | Description                          |
|---------------|----------------|----------------|--------------------------------------|
| id            | SERIAL         | PRIMARY KEY    | Auto-incrementing identifier         |
| city_name     | VARCHAR(100)   | NOT NULL       | City name (e.g., "Cairo")            |
| country_code  | CHAR(2)        | NOT NULL       | ISO 3166-1 alpha-2 code (e.g., "EG") |
| latitude      | NUMERIC(8,6)   | NOT NULL       | Decimal degrees, WGS84 (-90 to 90)   |
| longitude     | NUMERIC(9,6)   | NOT NULL       | Decimal degrees, WGS84 (-180 to 180) |
| created_at    | TIMESTAMP      | NOT NULL       | When location was added (UTC)        |

**Constraints**:
- `uq_location_identity`: UNIQUE (city_name, country_code)

**Indexes**:
- `idx_locations_coordinates`: (latitude, longitude) - for geospatial queries

**Example Row**:
```sql
id=1, city_name='Cairo', country_code='EG', 
latitude=30.044400, longitude=31.235700, 
created_at='2024-03-05 10:00:00'
```

---

### weather_readings
**Purpose**: Time-series storage for weather observations

| Column           | Type           | Constraints    | Description                               |
|------------------|----------------|----------------|-------------------------------------------|
| id               | SERIAL         | PRIMARY KEY    | Auto-incrementing identifier              |
| location_id      | INTEGER        | FK, NOT NULL   | References locations(id)                  |
| recorded_at      | TIMESTAMP      | NOT NULL       | When weather was observed (UTC from API)  |
| temperature_c    | NUMERIC(5,2)   | NULLABLE       | Temperature in Celsius (-999.99 to 999.99)|
| temperature_f    | NUMERIC(5,2)   | NULLABLE       | Temperature in Fahrenheit                 |
| humidity_pct     | NUMERIC(5,2)   | NULLABLE       | Relative humidity (0.00 to 100.00)        |
| wind_speed_kmh   | NUMERIC(6,2)   | NULLABLE       | Wind speed in km/h (0.00 to 9999.99)     |
| precipitation_mm | NUMERIC(6,2)   | NULLABLE       | Precipitation in mm (0.00 to 9999.99)     |
| weather_code     | INTEGER        | NULLABLE       | WMO weather interpretation code (0-99)    |
| ingested_at      | TIMESTAMP      | NOT NULL       | When data entered our system (UTC)        |
| source           | VARCHAR(50)    | NOT NULL       | Data provider (default: 'open-meteo')     |

**Constraints**:
- `fk_location`: FOREIGN KEY (location_id) REFERENCES locations(id) ON DELETE CASCADE
- `uq_reading_identity`: UNIQUE (location_id, recorded_at)

**Indexes**:
- `idx_readings_location_time`: (location_id, recorded_at DESC) - composite for filtered queries
- `idx_readings_time`: (recorded_at DESC) - temporal range queries
- `idx_readings_ingested_at`: (ingested_at DESC) - ETL monitoring

**Example Row**:
```sql
id=1, location_id=1, recorded_at='2024-03-05 14:00:00',
temperature_c=22.50, temperature_f=72.50, humidity_pct=65.00,
wind_speed_kmh=15.30, precipitation_mm=0.00, weather_code=1,
ingested_at='2024-03-05 14:05:00', source='open-meteo'
```

---

## Index Strategy

### Why These Indexes?

#### 1. `idx_readings_location_time` (location_id, recorded_at DESC)
**Primary composite index for time-series queries**

```sql
-- Supports queries like:
SELECT * FROM weather_readings 
WHERE location_id = 1 
  AND recorded_at BETWEEN '2024-03-01' AND '2024-03-07'
ORDER BY recorded_at DESC;

-- Also supports location-only queries via index prefix scan:
SELECT * FROM weather_readings 
WHERE location_id = 1
ORDER BY recorded_at DESC;
```

**Why composite?**
- Time-series workloads frequently filter by location AND time range
- Single index serves multiple query patterns
- DESC ordering optimizes "latest first" sorts (common in dashboards)

#### 2. `idx_readings_time` (recorded_at DESC)
**Global temporal index for cross-location queries**

```sql
-- Supports queries like:
SELECT * FROM weather_readings 
WHERE recorded_at >= NOW() - INTERVAL '24 hours'
ORDER BY recorded_at DESC;

-- Latest reading across all locations:
SELECT DISTINCT ON (location_id) *
FROM weather_readings
ORDER BY location_id, recorded_at DESC;
```

**Why standalone?**
- Not all queries filter by location (global dashboards, aggregate reports)
- DESC ordering for "latest first" is more efficient than ASC + LIMIT

#### 3. `idx_readings_ingested_at` (ingested_at DESC)
**ETL monitoring and data quality checks**

```sql
-- Supports queries like:
SELECT * FROM weather_readings 
WHERE ingested_at >= NOW() - INTERVAL '1 hour';

-- Check for stale data:
SELECT location_id, MAX(ingested_at) AS last_ingestion
FROM weather_readings
GROUP BY location_id;
```

**Why separate from recorded_at?**
- `recorded_at` = when weather was observed (business timestamp)
- `ingested_at` = when data entered our system (technical timestamp)
- Different query patterns for operational monitoring vs business analytics

#### 4. `idx_locations_coordinates` (latitude, longitude)
**Geospatial queries and proximity searches**

```sql
-- Supports queries like:
SELECT * FROM locations 
WHERE latitude BETWEEN 30.0 AND 40.0 
  AND longitude BETWEEN 20.0 AND 35.0;
```

**Why B-tree not PostGIS?**
- Simple rectangular range queries sufficient for this use case
- No complex geospatial operations (distance calculations, polygon intersections)
- Lower overhead than PostGIS GIST indexes
- Future migration path: If complex geospatial needs arise, add PostGIS extension

---

## Query Patterns and Performance

### Pattern 1: Latest Reading Per Location
```sql
SELECT DISTINCT ON (location_id) *
FROM weather_readings
ORDER BY location_id, recorded_at DESC;
```
**Index used**: `idx_readings_location_time`  
**Expected time**: < 20ms for 10 locations, 1M readings

---

### Pattern 2: Location-Specific Time Range
```sql
SELECT * FROM weather_readings
WHERE location_id = 1 
  AND recorded_at BETWEEN '2024-03-01' AND '2024-03-07'
ORDER BY recorded_at DESC;
```
**Index used**: `idx_readings_location_time`  
**Expected time**: < 10ms for 168 hourly readings (7 days)

---

### Pattern 3: Global Recent Readings
```sql
SELECT l.city_name, w.*
FROM weather_readings w
JOIN locations l ON w.location_id = l.id
WHERE w.recorded_at >= NOW() - INTERVAL '24 hours'
ORDER BY w.recorded_at DESC;
```
**Index used**: `idx_readings_time` (for weather_readings scan), PK on locations  
**Expected time**: < 50ms for 240 readings (10 locations × 24 hours)

---

### Pattern 4: ETL Data Freshness Check
```sql
SELECT 
    l.city_name,
    MAX(w.ingested_at) AS last_ingestion,
    AGE(NOW(), MAX(w.ingested_at)) AS data_age
FROM locations l
LEFT JOIN weather_readings w ON l.id = w.location_id
GROUP BY l.id, l.city_name;
```
**Index used**: `idx_readings_ingested_at`  
**Expected time**: < 30ms for 10 locations

---

## Data Types Rationale

### NUMERIC vs FLOAT
**Why NUMERIC for measurements?**
- **Precision**: NUMERIC stores exact decimal values (no floating-point errors)
- **Consistency**: Financial-grade accuracy for scientific data
- **Performance**: Slightly slower than FLOAT, but difference negligible for this workload

Example of FLOAT issues:
```sql
-- FLOAT can produce rounding errors:
SELECT 22.5::FLOAT = 22.5;  -- true
SELECT (22.5::FLOAT + 0.1::FLOAT) = 22.6::FLOAT;  -- sometimes false!

-- NUMERIC is always exact:
SELECT 22.5::NUMERIC(5,2) = 22.5;  -- always true
SELECT (22.5::NUMERIC(5,2) + 0.1::NUMERIC(5,2)) = 22.6::NUMERIC(5,2);  -- always true
```

### TIMESTAMP vs TIMESTAMPTZ
**Why TIMESTAMP without timezone?**
- **API contract**: Open-Meteo provides UTC timestamps
- **Storage efficiency**: TIMESTAMP is 8 bytes, TIMESTAMPTZ is 8 bytes + conversion overhead
- **Query simplicity**: No timezone conversion in WHERE clauses
- **Convention**: All timestamps in UTC by application design

If you need timezone-aware queries later:
```sql
-- Convert to specific timezone on read:
SELECT recorded_at AT TIME ZONE 'America/New_York' AS local_time
FROM weather_readings;
```

### VARCHAR vs TEXT
**Why VARCHAR(100) for city_name?**
- **Validation**: Enforces reasonable length limit (longest city name < 100 chars)
- **Performance**: Fixed-width storage is slightly faster for short strings
- **Indexing**: VARCHAR indexes are more efficient than TEXT indexes

**Why VARCHAR(50) for source?**
- Known set of API providers (open-meteo, weatherapi, etc.)
- Unlikely to exceed 50 characters
- Prevents accidental insertion of long strings

---

## Idempotent Insert Pattern

### Problem
ETL pipelines may run multiple times for the same time range:
- **Backfill**: Re-process historical data after bug fixes
- **Retry**: Network failures during ingestion
- **Overlap**: Scheduled jobs with overlapping windows

### Solution
Use `ON CONFLICT DO NOTHING` with unique constraint:

```sql
INSERT INTO weather_readings (
    location_id, 
    recorded_at, 
    temperature_c, 
    source
)
VALUES 
    (1, '2024-03-05 14:00:00', 22.5, 'open-meteo'),
    (1, '2024-03-05 15:00:00', 23.1, 'open-meteo')
ON CONFLICT (location_id, recorded_at) DO NOTHING;
```

**Key points**:
- ✅ **Safe reruns**: Running same insert multiple times has no effect
- ✅ **No errors**: Conflicts are silently ignored (check `row_count` for actual inserts)
- ✅ **Performance**: Uses index for conflict detection (no table scan)
- ⚠️ **Limitation**: Cannot update existing rows (use `DO UPDATE SET` if needed)

### Alternative: Upsert Pattern
If you need to update existing readings:

```sql
INSERT INTO weather_readings (
    location_id, 
    recorded_at, 
    temperature_c, 
    source
)
VALUES (1, '2024-03-05 14:00:00', 22.5, 'open-meteo')
ON CONFLICT (location_id, recorded_at) 
DO UPDATE SET 
    temperature_c = EXCLUDED.temperature_c,
    ingested_at = CURRENT_TIMESTAMP;  -- Track last update
```

---

## Scaling Considerations

### Current Capacity
- **Reads**: < 50ms for typical queries with proper indexes
- **Writes**: > 10,000 rows/sec single connection
- **Storage**: ~100 bytes/row average (varies with NULL values)
- **Capacity**: Millions of readings without partitioning

### When to Partition?
Consider table partitioning when:
- **Table size** > 50 million rows
- **Query performance** degrades despite proper indexes
- **Maintenance windows** (VACUUM, REINDEX) take too long

**Recommended partitioning strategy**:
```sql
-- Range partition by month on recorded_at
CREATE TABLE weather_readings_2024_03 PARTITION OF weather_readings
    FOR VALUES FROM ('2024-03-01') TO ('2024-04-01');

CREATE TABLE weather_readings_2024_04 PARTITION OF weather_readings
    FOR VALUES FROM ('2024-04-01') TO ('2024-05-01');
```

**Benefits**:
- ✅ Faster queries (partition pruning)
- ✅ Faster maintenance (per-partition VACUUM)
- ✅ Easy archival (detach old partitions)

### When to Use TimescaleDB?
Consider TimescaleDB extension when:
- **Complex time-series queries** (time_bucket, LOCF interpolation)
- **Automatic retention policies** (drop old chunks automatically)
- **Continuous aggregates** (materialized views for time-series)
- **Compression** (native columnar compression for old data)

**Trade-offs**:
- ➕ Better time-series performance (2-20x faster for complex queries)
- ➕ Simpler operational management (automatic chunk management)
- ➖ Additional extension dependency (must install on all replicas)
- ➖ Learning curve (different mental model than vanilla PostgreSQL)

---

## Next Steps

1. **Test the schema**:
   ```bash
   ./validate_database.sh
   ```

2. **Populate sample data**:
   ```sql
   -- See sql/queries.sql for insertion examples
   ```

3. **Monitor query performance**:
   ```sql
   -- Enable pg_stat_statements
   CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
   
   -- Check slow queries
   SELECT * FROM pg_stat_statements 
   ORDER BY mean_exec_time DESC 
   LIMIT 10;
   ```

4. **Implement connection pooling**:
   - Use `psycopg2.pool.SimpleConnectionPool` in Python
   - Or deploy PgBouncer for multi-application scenarios

5. **Set up monitoring**:
   - Grafana + Prometheus for metrics
   - Alert on: disk space, connection count, replication lag

---

## References

- [PostgreSQL Time-Series Best Practices](https://www.timescale.com/blog/time-series-data-postgresql-10-vs-timescaledb-816ee808bac5/)
- [Index Types in PostgreSQL](https://www.postgresql.org/docs/current/indexes-types.html)
- [NUMERIC vs FLOAT](https://www.postgresql.org/docs/current/datatype-numeric.html)
- [Partitioning Guide](https://www.postgresql.org/docs/current/ddl-partitioning.html)
- [ON CONFLICT Documentation](https://www.postgresql.org/docs/current/sql-insert.html#SQL-ON-CONFLICT)
