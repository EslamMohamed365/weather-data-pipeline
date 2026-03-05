-- =====================================================
-- Weather Pipeline - Quick SQL Reference
-- =====================================================
-- Common queries for development and debugging

-- =====================================================
-- SCHEMA INSPECTION
-- =====================================================

-- List all tables
\dt

-- Describe table structure
\d+ locations
\d+ weather_readings

-- List all indexes with sizes
SELECT 
    schemaname,
    tablename,
    indexname,
    pg_size_pretty(pg_relation_size(indexrelid)) AS index_size,
    idx_scan AS times_used
FROM pg_stat_user_indexes
ORDER BY pg_relation_size(indexrelid) DESC;

-- Table sizes
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS total_size,
    pg_size_pretty(pg_relation_size(schemaname||'.'||tablename)) AS table_size,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename) - pg_relation_size(schemaname||'.'||tablename)) AS indexes_size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;


-- =====================================================
-- DATA INSERTION
-- =====================================================

-- Insert location (idempotent)
INSERT INTO locations (city_name, country_code, latitude, longitude)
VALUES ('Cairo', 'EG', 30.0444, 31.2357)
ON CONFLICT (city_name, country_code) DO NOTHING
RETURNING id;

-- Insert weather reading (idempotent)
INSERT INTO weather_readings (
    location_id, 
    recorded_at, 
    temperature_c, 
    temperature_f, 
    humidity_pct, 
    wind_speed_kmh, 
    precipitation_mm, 
    weather_code,
    source
)
VALUES (
    1,                          -- location_id
    '2024-03-05 14:00:00',     -- recorded_at
    22.5,                       -- temperature_c
    72.5,                       -- temperature_f
    65.0,                       -- humidity_pct
    15.3,                       -- wind_speed_kmh
    0.0,                        -- precipitation_mm
    1,                          -- weather_code (1 = Mainly clear)
    'open-meteo'                -- source
)
ON CONFLICT (location_id, recorded_at) DO NOTHING;

-- Bulk insert with ON CONFLICT
INSERT INTO weather_readings (location_id, recorded_at, temperature_c, source)
VALUES 
    (1, '2024-03-05 15:00:00', 23.1, 'open-meteo'),
    (1, '2024-03-05 16:00:00', 23.8, 'open-meteo'),
    (1, '2024-03-05 17:00:00', 24.2, 'open-meteo')
ON CONFLICT (location_id, recorded_at) DO NOTHING;


-- =====================================================
-- COMMON QUERIES
-- =====================================================

-- Latest reading for each location
SELECT 
    l.city_name,
    l.country_code,
    w.recorded_at,
    w.temperature_c,
    w.humidity_pct,
    w.wind_speed_kmh
FROM locations l
LEFT JOIN LATERAL (
    SELECT *
    FROM weather_readings
    WHERE location_id = l.id
    ORDER BY recorded_at DESC
    LIMIT 1
) w ON true
ORDER BY l.city_name;

-- Weather readings for specific location (last 7 days)
SELECT 
    recorded_at,
    temperature_c,
    humidity_pct,
    wind_speed_kmh,
    precipitation_mm,
    weather_code
FROM weather_readings
WHERE location_id = 1
  AND recorded_at >= NOW() - INTERVAL '7 days'
ORDER BY recorded_at DESC;

-- Average temperature by location (last 24 hours)
SELECT 
    l.city_name,
    l.country_code,
    ROUND(AVG(w.temperature_c)::numeric, 2) AS avg_temp_c,
    ROUND(MIN(w.temperature_c)::numeric, 2) AS min_temp_c,
    ROUND(MAX(w.temperature_c)::numeric, 2) AS max_temp_c,
    COUNT(*) AS reading_count
FROM locations l
JOIN weather_readings w ON l.id = w.location_id
WHERE w.recorded_at >= NOW() - INTERVAL '24 hours'
GROUP BY l.id, l.city_name, l.country_code
ORDER BY avg_temp_c DESC;

-- Hourly temperature trend for location
SELECT 
    DATE_TRUNC('hour', recorded_at) AS hour,
    ROUND(AVG(temperature_c)::numeric, 2) AS avg_temp_c,
    ROUND(AVG(humidity_pct)::numeric, 2) AS avg_humidity_pct
FROM weather_readings
WHERE location_id = 1
  AND recorded_at >= NOW() - INTERVAL '3 days'
GROUP BY DATE_TRUNC('hour', recorded_at)
ORDER BY hour DESC;

-- All locations with their latest reading time
SELECT 
    l.city_name,
    l.country_code,
    MAX(w.recorded_at) AS last_reading,
    AGE(NOW(), MAX(w.recorded_at)) AS data_age,
    COUNT(*) AS total_readings
FROM locations l
LEFT JOIN weather_readings w ON l.id = w.location_id
GROUP BY l.id, l.city_name, l.country_code
ORDER BY last_reading DESC NULLS LAST;


-- =====================================================
-- DATA QUALITY CHECKS
-- =====================================================

-- Check for gaps in time-series data (hourly expected)
WITH hourly_series AS (
    SELECT 
        location_id,
        generate_series(
            DATE_TRUNC('hour', MIN(recorded_at)),
            DATE_TRUNC('hour', MAX(recorded_at)),
            INTERVAL '1 hour'
        ) AS expected_hour
    FROM weather_readings
    WHERE location_id = 1
    GROUP BY location_id
)
SELECT 
    h.expected_hour,
    COUNT(w.id) AS reading_count
FROM hourly_series h
LEFT JOIN weather_readings w ON 
    h.location_id = w.location_id AND
    DATE_TRUNC('hour', w.recorded_at) = h.expected_hour
GROUP BY h.expected_hour
HAVING COUNT(w.id) = 0
ORDER BY h.expected_hour DESC
LIMIT 20;

-- Check for duplicate readings (should be 0)
SELECT 
    location_id,
    recorded_at,
    COUNT(*) AS duplicate_count
FROM weather_readings
GROUP BY location_id, recorded_at
HAVING COUNT(*) > 1;

-- Check for null values in critical columns
SELECT 
    COUNT(*) AS total_readings,
    SUM(CASE WHEN temperature_c IS NULL THEN 1 ELSE 0 END) AS null_temperature,
    SUM(CASE WHEN humidity_pct IS NULL THEN 1 ELSE 0 END) AS null_humidity,
    SUM(CASE WHEN wind_speed_kmh IS NULL THEN 1 ELSE 0 END) AS null_wind_speed,
    SUM(CASE WHEN weather_code IS NULL THEN 1 ELSE 0 END) AS null_weather_code
FROM weather_readings;

-- Data ingestion lag (time between observation and ingestion)
SELECT 
    AVG(EXTRACT(EPOCH FROM (ingested_at - recorded_at))) / 60 AS avg_lag_minutes,
    MAX(EXTRACT(EPOCH FROM (ingested_at - recorded_at))) / 60 AS max_lag_minutes
FROM weather_readings
WHERE ingested_at >= NOW() - INTERVAL '24 hours';


-- =====================================================
-- ETL MONITORING
-- =====================================================

-- Recent ingestion activity
SELECT 
    DATE_TRUNC('hour', ingested_at) AS ingestion_hour,
    COUNT(*) AS records_ingested,
    COUNT(DISTINCT location_id) AS locations_updated
FROM weather_readings
WHERE ingested_at >= NOW() - INTERVAL '24 hours'
GROUP BY DATE_TRUNC('hour', ingested_at)
ORDER BY ingestion_hour DESC;

-- Ingestion rate per source
SELECT 
    source,
    COUNT(*) AS total_records,
    MIN(ingested_at) AS first_ingested,
    MAX(ingested_at) AS last_ingested,
    COUNT(DISTINCT location_id) AS locations_covered
FROM weather_readings
GROUP BY source;

-- Latest readings ingested (last 10)
SELECT 
    l.city_name,
    w.recorded_at,
    w.ingested_at,
    AGE(w.ingested_at, w.recorded_at) AS ingestion_lag,
    w.temperature_c,
    w.source
FROM weather_readings w
JOIN locations l ON w.location_id = l.id
ORDER BY w.ingested_at DESC
LIMIT 10;


-- =====================================================
-- PERFORMANCE ANALYSIS
-- =====================================================

-- Index usage statistics
SELECT 
    schemaname,
    tablename,
    indexname,
    idx_scan AS index_scans,
    idx_tup_read AS tuples_read,
    idx_tup_fetch AS tuples_fetched,
    pg_size_pretty(pg_relation_size(indexrelid)) AS index_size
FROM pg_stat_user_indexes
WHERE schemaname = 'public'
ORDER BY idx_scan DESC;

-- Sequential scans (should be minimal for indexed queries)
SELECT 
    schemaname,
    tablename,
    seq_scan AS sequential_scans,
    seq_tup_read AS tuples_read,
    idx_scan AS index_scans,
    ROUND(100.0 * seq_scan / NULLIF(seq_scan + idx_scan, 0), 2) AS seq_scan_pct
FROM pg_stat_user_tables
WHERE schemaname = 'public'
ORDER BY seq_scan DESC;

-- Table bloat estimation
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS total_size,
    n_dead_tup AS dead_tuples,
    n_live_tup AS live_tuples,
    ROUND(100.0 * n_dead_tup / NULLIF(n_live_tup, 0), 2) AS dead_tuple_pct,
    last_autovacuum
FROM pg_stat_user_tables
WHERE schemaname = 'public'
ORDER BY n_dead_tup DESC;


-- =====================================================
-- MAINTENANCE
-- =====================================================

-- Manual vacuum (run during low activity)
VACUUM ANALYZE weather_readings;
VACUUM ANALYZE locations;

-- Reindex if needed (after bulk operations)
REINDEX TABLE weather_readings;

-- Update statistics for query planner
ANALYZE weather_readings;

-- Check for missing indexes (query planner suggestions)
-- Run after enabling pg_stat_statements extension
-- CREATE EXTENSION IF NOT EXISTS pg_stat_statements;


-- =====================================================
-- DATA CLEANUP
-- =====================================================

-- Delete old readings (e.g., older than 2 years)
DELETE FROM weather_readings
WHERE recorded_at < NOW() - INTERVAL '2 years';

-- Delete location and all its readings (CASCADE)
DELETE FROM locations
WHERE city_name = 'OldCity' AND country_code = 'OC';

-- Truncate all data (fast, but irreversible)
TRUNCATE weather_readings CASCADE;
TRUNCATE locations CASCADE;


-- =====================================================
-- USEFUL SETTINGS
-- =====================================================

-- Show current configuration
SHOW shared_buffers;
SHOW work_mem;
SHOW effective_cache_size;
SHOW max_connections;

-- Database size
SELECT pg_size_pretty(pg_database_size(current_database()));

-- Active connections
SELECT 
    COUNT(*) AS total_connections,
    COUNT(*) FILTER (WHERE state = 'active') AS active_connections,
    COUNT(*) FILTER (WHERE state = 'idle') AS idle_connections
FROM pg_stat_activity
WHERE datname = current_database();

-- Long-running queries (> 1 minute)
SELECT 
    pid,
    usename,
    application_name,
    state,
    query,
    NOW() - query_start AS duration
FROM pg_stat_activity
WHERE state != 'idle'
  AND NOW() - query_start > INTERVAL '1 minute'
ORDER BY duration DESC;
