-- Weather Data Pipeline - PostgreSQL Schema
-- Optimized for time-series workloads with efficient indexing strategy

-- =====================================================
-- LOCATIONS TABLE
-- =====================================================
-- Stores unique geographical locations for weather tracking
-- City-level granularity with coordinates for API queries

CREATE TABLE IF NOT EXISTS locations (
    id SERIAL PRIMARY KEY,
    city_name VARCHAR(100) NOT NULL,
    country_code CHAR(2) NOT NULL,  -- ISO 3166-1 alpha-2 code
    latitude NUMERIC(8, 6) NOT NULL,  -- Range: -90.000000 to 90.000000
    longitude NUMERIC(9, 6) NOT NULL, -- Range: -180.000000 to 180.000000
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    -- Prevent duplicate locations (same city+country must have same coordinates)
    CONSTRAINT uq_location_identity UNIQUE (city_name, country_code)
);

-- Index for coordinate-based queries (proximity searches, geospatial operations)
CREATE INDEX IF NOT EXISTS idx_locations_coordinates 
    ON locations (latitude, longitude);

-- Add table comment
COMMENT ON TABLE locations IS 'Geographic locations for weather data collection';
COMMENT ON COLUMN locations.latitude IS 'Decimal degrees, WGS84 coordinate system';
COMMENT ON COLUMN locations.longitude IS 'Decimal degrees, WGS84 coordinate system';


-- =====================================================
-- WEATHER_READINGS TABLE
-- =====================================================
-- Time-series storage for weather observations
-- Optimized for high-volume ingestion and temporal queries

CREATE TABLE IF NOT EXISTS weather_readings (
    id SERIAL PRIMARY KEY,
    location_id INTEGER NOT NULL,
    recorded_at TIMESTAMP NOT NULL,  -- When the weather was observed (UTC from API)
    
    -- Weather measurements
    temperature_c NUMERIC(5, 2),      -- Celsius: -999.99 to 999.99
    temperature_f NUMERIC(5, 2),      -- Fahrenheit: -999.99 to 999.99
    humidity_pct NUMERIC(5, 2),       -- Percentage: 0.00 to 100.00
    wind_speed_kmh NUMERIC(6, 2),     -- km/h: 0.00 to 9999.99
    precipitation_mm NUMERIC(6, 2),   -- mm: 0.00 to 9999.99
    weather_code INTEGER,             -- WMO weather interpretation code
    
    -- Metadata
    ingested_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,  -- When data entered our system
    source VARCHAR(50) NOT NULL DEFAULT 'open-meteo',          -- Data provider identifier
    
    -- Foreign key with CASCADE delete: removing location deletes all its readings
    CONSTRAINT fk_location
        FOREIGN KEY (location_id)
        REFERENCES locations (id)
        ON DELETE CASCADE,
    
    -- Prevent duplicate readings for same location+time
    CONSTRAINT uq_reading_identity
        UNIQUE (location_id, recorded_at)
);

-- =====================================================
-- PERFORMANCE INDEXES
-- =====================================================

-- INDEX STRATEGY RATIONALE:
-- 1. Time-series queries are primary workload (date range filters)
-- 2. Location filtering is secondary (per-city dashboards)
-- 3. Joins on location_id are frequent (enriching readings with city info)
-- 4. Composite index supports both individual and combined queries

-- Composite index for time-series queries filtered by location
-- Supports queries like: SELECT * FROM weather_readings WHERE location_id = X AND recorded_at BETWEEN Y AND Z
-- PostgreSQL can use this for location-only queries via index-only scan on prefix
CREATE INDEX IF NOT EXISTS idx_readings_location_time 
    ON weather_readings (location_id, recorded_at DESC);

-- Standalone temporal index for global time-range queries
-- Supports queries like: SELECT * FROM weather_readings WHERE recorded_at > NOW() - INTERVAL '7 days'
-- DESC ordering optimizes "latest readings first" queries (common dashboard pattern)
CREATE INDEX IF NOT EXISTS idx_readings_time 
    ON weather_readings (recorded_at DESC);

-- Index on ingestion timestamp for ETL monitoring and data quality checks
-- Enables fast queries: "Show me data ingested in the last hour"
CREATE INDEX IF NOT EXISTS idx_readings_ingested_at 
    ON weather_readings (ingested_at DESC);

-- Add table comments
COMMENT ON TABLE weather_readings IS 'Time-series weather observations with deduplication';
COMMENT ON COLUMN weather_readings.recorded_at IS 'Observation timestamp from weather API (UTC)';
COMMENT ON COLUMN weather_readings.ingested_at IS 'Pipeline ingestion timestamp (UTC)';
COMMENT ON COLUMN weather_readings.weather_code IS 'WMO weather interpretation code (0-99)';
COMMENT ON INDEX idx_readings_location_time IS 'Composite index: supports location+time queries efficiently';
COMMENT ON INDEX idx_readings_time IS 'Temporal index: optimized for date range scans and latest-first ordering';
COMMENT ON INDEX idx_readings_ingested_at IS 'ETL monitoring: tracks data freshness and pipeline performance';


-- =====================================================
-- IDEMPOTENT INSERT EXAMPLES
-- =====================================================
-- Usage pattern for pipeline:
--
-- INSERT INTO weather_readings (location_id, recorded_at, temperature_c, ...)
-- VALUES (1, '2024-03-05 12:00:00', 15.5, ...)
-- ON CONFLICT (location_id, recorded_at) DO NOTHING;
--
-- This prevents duplicate ingestion if pipeline runs multiple times
-- for the same time range (common in backfill scenarios)
