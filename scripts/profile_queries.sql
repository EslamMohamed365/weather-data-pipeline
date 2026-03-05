-- =====================================================
-- PostgreSQL Query Performance Analysis
-- =====================================================

-- Enable query execution time display
\timing on

-- =====================================================
-- 1. ANALYZE EXPLAIN for Dashboard Queries
-- =====================================================

-- Latest readings query
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
WITH latest_per_location AS (
    SELECT 
        location_id,
        MAX(recorded_at) as max_recorded_at
    FROM weather_readings
    GROUP BY location_id
)
SELECT 
    l.city_name,
    l.country_code,
    wr.recorded_at,
    wr.temperature_c,
    wr.temperature_f,
    wr.humidity_pct,
    wr.wind_speed_kmh,
    wr.precipitation_mm,
    wr.weather_code,
    wr.ingested_at
FROM weather_readings wr
JOIN latest_per_location lpl 
    ON wr.location_id = lpl.location_id 
    AND wr.recorded_at = lpl.max_recorded_at
JOIN locations l ON wr.location_id = l.id
WHERE l.city_name IN ('Cairo', 'London', 'Tokyo', 'New York', 'Sydney')
ORDER BY l.city_name;

-- Temperature trend query
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT 
    l.city_name,
    wr.recorded_at,
    wr.temperature_c,
    wr.temperature_f
FROM weather_readings wr
JOIN locations l ON wr.location_id = l.id
WHERE l.city_name IN ('Cairo', 'London', 'Tokyo')
    AND DATE(wr.recorded_at) BETWEEN '2024-01-01' AND '2024-01-07'
ORDER BY wr.recorded_at, l.city_name;

-- =====================================================
-- 2. Index Usage Statistics
-- =====================================================

SELECT 
    schemaname,
    tablename,
    indexname,
    idx_scan AS times_used,
    idx_tup_read AS tuples_read,
    idx_tup_fetch AS tuples_fetched,
    pg_size_pretty(pg_relation_size(indexrelid)) AS index_size,
    ROUND(100.0 * idx_scan / NULLIF(idx_scan + seq_scan, 0), 2) AS index_usage_pct
FROM pg_stat_user_indexes
JOIN pg_stat_user_tables USING (schemaname, tablename)
WHERE schemaname = 'public'
ORDER BY idx_scan DESC;

-- =====================================================
-- 3. Slow Query Detection
-- =====================================================

-- Requires pg_stat_statements extension
-- CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

SELECT 
    query,
    calls,
    total_exec_time / 1000 AS total_seconds,
    mean_exec_time / 1000 AS avg_seconds,
    max_exec_time / 1000 AS max_seconds,
    stddev_exec_time / 1000 AS stddev_seconds,
    rows / calls AS avg_rows_returned
FROM pg_stat_statements
WHERE query NOT LIKE '%pg_stat%'
ORDER BY mean_exec_time DESC
LIMIT 20;

-- =====================================================
-- 4. Table Bloat Analysis
-- =====================================================

SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS total_size,
    n_live_tup AS live_rows,
    n_dead_tup AS dead_rows,
    ROUND(100.0 * n_dead_tup / NULLIF(n_live_tup, 0), 2) AS bloat_pct,
    last_vacuum,
    last_autovacuum
FROM pg_stat_user_tables
WHERE schemaname = 'public'
ORDER BY n_dead_tup DESC;

-- =====================================================
-- 5. Cache Hit Ratio (Should be >99%)
-- =====================================================

SELECT 
    'Index Hit Rate' AS metric,
    ROUND(100.0 * sum(idx_blks_hit) / NULLIF(sum(idx_blks_hit + idx_blks_read), 0), 2) AS percentage
FROM pg_statio_user_indexes
UNION ALL
SELECT 
    'Table Hit Rate' AS metric,
    ROUND(100.0 * sum(heap_blks_hit) / NULLIF(sum(heap_blks_hit + heap_blks_read), 0), 2) AS percentage
FROM pg_statio_user_tables;
