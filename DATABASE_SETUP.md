# Weather Data Pipeline - Database Setup Guide

## Quick Start

### 1. Configure Environment
```bash
# Copy template and edit with your credentials
cp .env.example .env
nano .env  # or use your preferred editor
```

### 2. Start Database Services
```bash
# Start PostgreSQL + pgAdmin
docker-compose up -d

# Verify containers are running
docker-compose ps

# Check PostgreSQL logs
docker-compose logs postgres

# Check schema was applied
docker-compose exec postgres psql -U weather_admin -d weather_pipeline -c "\dt"
```

### 3. Access pgAdmin
- URL: http://localhost:5050
- Login: Use `PGADMIN_EMAIL` and `PGADMIN_PASSWORD` from .env
- Add Server:
  - Name: Weather Pipeline
  - Host: postgres (use service name, not localhost)
  - Port: 5432
  - Database: weather_pipeline
  - Username: weather_admin
  - Password: (from .env)

## Database Schema

### Tables

#### `locations`
- Stores unique cities with coordinates
- Unique constraint on (city_name, country_code)
- Indexed on coordinates for geospatial queries

#### `weather_readings`
- Time-series weather observations
- Foreign key to locations (CASCADE delete)
- Unique constraint on (location_id, recorded_at) prevents duplicates
- Optimized indexes for temporal queries

### Indexes Strategy

1. **`idx_readings_location_time`** (location_id, recorded_at DESC)
   - Primary composite index for filtered time-series queries
   - Supports: "Show me weather for Cairo in March"

2. **`idx_readings_time`** (recorded_at DESC)
   - Standalone temporal index
   - Supports: "Show me latest readings across all cities"

3. **`idx_readings_ingested_at`** (ingested_at DESC)
   - ETL monitoring index
   - Supports: "Show me data ingested in last hour"

## Idempotent Inserts

Prevent duplicate data during pipeline reruns:

```sql
INSERT INTO weather_readings (location_id, recorded_at, temperature_c, ...)
VALUES (1, '2024-03-05 12:00:00', 15.5, ...)
ON CONFLICT (location_id, recorded_at) DO NOTHING;
```

## Useful Commands

### Database Management
```bash
# Stop services
docker-compose down

# Stop and remove volumes (⚠️ deletes all data)
docker-compose down -v

# Restart single service
docker-compose restart postgres

# View real-time logs
docker-compose logs -f postgres
```

### PostgreSQL CLI Access
```bash
# Connect to psql
docker-compose exec postgres psql -U weather_admin -d weather_pipeline

# Common queries
\dt              # List tables
\d+ locations    # Describe locations table
\di              # List indexes
\df              # List functions
```

### Performance Monitoring
```sql
-- Check table sizes
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- Check index usage
SELECT 
    schemaname,
    tablename,
    indexname,
    idx_scan as index_scans,
    pg_size_pretty(pg_relation_size(indexrelid)) as index_size
FROM pg_stat_user_indexes
ORDER BY idx_scan ASC;

-- Active connections
SELECT count(*) FROM pg_stat_activity WHERE state = 'active';
```

## Production Considerations

### Security
- [ ] Change default passwords in .env
- [ ] Add .env to .gitignore
- [ ] Restrict PostgreSQL port exposure (remove from docker-compose ports in prod)
- [ ] Enable SSL/TLS for connections
- [ ] Use secrets management (AWS Secrets Manager, Vault, etc.)

### Performance
- [ ] Tune shared_buffers based on available RAM (25% of system memory)
- [ ] Enable pg_stat_statements extension for query analysis
- [ ] Set up connection pooling (PgBouncer)
- [ ] Configure autovacuum for time-series workload
- [ ] Monitor index bloat and reindex periodically

### Reliability
- [ ] Set up streaming replication (hot standby)
- [ ] Configure WAL archiving for PITR
- [ ] Implement automated backups (pg_dump daily, WAL continuous)
- [ ] Test restore procedures regularly
- [ ] Set up monitoring (Prometheus + Grafana)
- [ ] Configure alerting (disk space, replication lag, connection count)

### Scalability
- [ ] Consider table partitioning for weather_readings (monthly partitions)
- [ ] Implement TimescaleDB extension for better time-series performance
- [ ] Set up read replicas for reporting queries
- [ ] Archive old data to cold storage (S3 + Parquet)
- [ ] Use connection pooling to handle high concurrent loads

## Troubleshooting

### Container won't start
```bash
# Check logs
docker-compose logs postgres

# Common issues:
# - Port 5432 already in use (stop other PostgreSQL instances)
# - Invalid .env configuration (check syntax)
# - Permission issues with volumes (check Docker permissions)
```

### Schema not applied
```bash
# Check if schema.sql has errors
docker-compose exec postgres psql -U weather_admin -d weather_pipeline -f /docker-entrypoint-initdb.d/01-schema.sql

# Manual schema application
docker-compose exec postgres psql -U weather_admin -d weather_pipeline < sql/schema.sql
```

### Connection refused from Python
```python
# Use 'localhost' when connecting from host machine
# Use 'postgres' when connecting from another Docker container

# Host machine connection:
conn = psycopg2.connect(
    host="localhost",  # or 127.0.0.1
    port=5432,
    database="weather_pipeline",
    user="weather_admin",
    password="your_password"
)
```

## Next Steps

1. Install Python dependencies: `pip install psycopg2-binary python-dotenv`
2. Create database connection module in `src/database.py`
3. Implement ETL pipeline to populate tables
4. Set up monitoring dashboards in pgAdmin
5. Configure automated backups

## Resources

- [PostgreSQL Documentation](https://www.postgresql.org/docs/15/)
- [Docker Compose Reference](https://docs.docker.com/compose/compose-file/)
- [pgAdmin Documentation](https://www.pgadmin.org/docs/)
- [Time-Series Best Practices](https://www.timescale.com/blog/time-series-data-postgresql-10-vs-timescaledb-816ee808bac5/)
