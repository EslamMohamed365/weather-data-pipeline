# 🐛 Debug Quick Reference Card

## 🚨 Top 4 Critical Bugs

```
┌─────────────────────────────────────────────────────────────┐
│ BUG #1: JSON Parsing Crash                                  │
├─────────────────────────────────────────────────────────────┤
│ Location:  src/extract.py:92                                │
│ Symptom:   JSONDecodeError: Expecting value: line 1 column 1│
│ Cause:     API returns HTML error page instead of JSON      │
│ Priority:  🔴 CRITICAL - Pipeline crashes completely        │
│ Fix Time:  10 minutes                                       │
├─────────────────────────────────────────────────────────────┤
│ FIX:                                                         │
│   except requests.exceptions.JSONDecodeError as e:          │
│       last_exception = e                                    │
│       logger.warning(f"Invalid JSON attempt {attempt}")     │
│       continue  # Retry                                     │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ BUG #2: Connection Pool Hang                                │
├─────────────────────────────────────────────────────────────┤
│ Location:  src/load.py:228                                  │
│ Symptom:   Process hangs, no output, can't kill with Ctrl+C│
│ Cause:     >10 connections in use, getconn() blocks forever │
│ Priority:  🔴 CRITICAL - Silent hang, hard to debug         │
│ Fix Time:  30 minutes                                       │
├─────────────────────────────────────────────────────────────┤
│ WORKAROUND:                                                  │
│   pkill -9 -f pipeline.py  # Kill hung process              │
│   Check: SELECT count(*) FROM pg_stat_activity              │
│          WHERE datname='weather_db';                        │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ BUG #3: Schema Not Validated                                │
├─────────────────────────────────────────────────────────────┤
│ Location:  src/pipeline.py:76                               │
│ Symptom:   relation "locations" does not exist              │
│ Cause:     Fresh database, schema.sql not run               │
│ Priority:  🟠 HIGH - Confusing error on new installs        │
│ Fix Time:  20 minutes                                       │
├─────────────────────────────────────────────────────────────┤
│ IMMEDIATE FIX:                                               │
│   psql -U postgres -d weather_db -f sql/schema.sql         │
│                                                              │
│ PERMANENT FIX:                                               │
│   Add verify_schema() check on pipeline startup            │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ BUG #4: DateTime Format Mismatch                            │
├─────────────────────────────────────────────────────────────┤
│ Location:  src/transform.py:61                              │
│ Symptom:   ComputeError: Could not parse "2024-03-05T14:30" │
│ Cause:     Format lacks seconds (%H:%M vs %H:%M:%S)        │
│ Priority:  🟠 HIGH - Transform phase crashes                │
│ Fix Time:  15 minutes                                       │
├─────────────────────────────────────────────────────────────┤
│ FIX:                                                         │
│   df.with_columns(                                          │
│     pl.col("recorded_at").str.to_datetime(                 │
│       "%Y-%m-%dT%H:%M:%S", strict=False                    │
│     )                                                        │
│   )                                                          │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔍 Common Error Messages

```
┌──────────────────────────────────────────────────────────────┐
│ ERROR MESSAGE                        │ SOLUTION              │
├──────────────────────────────────────┼───────────────────────┤
│ JSONDecodeError: Expecting value     │ → Apply Bug Fix #1    │
│                                      │   (API returning HTML)│
├──────────────────────────────────────┼───────────────────────┤
│ Process hangs, no output             │ → Check connection    │
│                                      │   pool (Bug #2)       │
├──────────────────────────────────────┼───────────────────────┤
│ relation "locations" does not exist  │ → Run schema.sql      │
│                                      │   (Bug #3)            │
├──────────────────────────────────────┼───────────────────────┤
│ ComputeError: Could not parse        │ → Fix datetime format │
│ "2024-03-05T14:30:00"                │   (Bug #4)            │
├──────────────────────────────────────┼───────────────────────┤
│ All cities failed extraction         │ → Check API status    │
│                                      │ → ping api.open-meteo │
├──────────────────────────────────────┼───────────────────────┤
│ Database connection test failed      │ → Check .env file     │
│                                      │ → Verify PostgreSQL   │
├──────────────────────────────────────┼───────────────────────┤
│ No data extracted. Aborting          │ → Check coordinates   │
│                                      │ → Review API logs     │
└──────────────────────────────────────┴───────────────────────┘
```

---

## 🧰 Emergency Troubleshooting

### Pipeline Crashed?
```bash
# Step 1: Check last error in logs
tail -n 50 pipeline.log | grep -i error

# Step 2: Test API connectivity
curl "https://api.open-meteo.com/v1/forecast?latitude=30&longitude=31&hourly=temperature_2m"

# Step 3: Test database connectivity
psql -U postgres -d weather_db -c "SELECT 1;"

# Step 4: Check data integrity
python scripts/validate_data_integrity.py

# Step 5: Re-run pipeline (safe due to deduplication)
python src/pipeline.py
```

### Pipeline Hangs?
```bash
# Step 1: Check if actually running
ps aux | grep pipeline.py

# Step 2: Check database connections
psql -U postgres -d weather_db -c "
  SELECT count(*), state FROM pg_stat_activity 
  WHERE datname = 'weather_db' GROUP BY state;
"

# Step 3: Kill if stuck (connection pool exhaustion)
pkill -9 -f pipeline.py

# Step 4: Check for deadlocks
psql -U postgres -d weather_db -c "
  SELECT pid, state, wait_event, query 
  FROM pg_stat_activity 
  WHERE datname = 'weather_db' AND state = 'active';
"
```

### Fresh Database Setup?
```bash
# Complete initialization sequence:
createdb -U postgres weather_db
psql -U postgres -d weather_db -f sql/schema.sql

# Verify schema
psql -U postgres -d weather_db -c "\dt"

# Should see:
#  locations
#  weather_readings

# Run first pipeline
python src/pipeline.py
```

---

## 📊 Health Check Commands

```bash
# Check data freshness (should be <2 hours)
psql -d weather_db -c "
  SELECT 
    city_name, 
    MAX(ingested_at) as last_ingestion,
    EXTRACT(EPOCH FROM (NOW() - MAX(ingested_at)))/3600 as age_hours
  FROM weather_readings wr
  JOIN locations l ON wr.location_id = l.id
  GROUP BY city_name;
"

# Check row counts per city
psql -d weather_db -c "
  SELECT city_name, COUNT(*) 
  FROM weather_readings wr
  JOIN locations l ON wr.location_id = l.id
  GROUP BY city_name;
"

# Check for invalid data
psql -d weather_db -c "
  SELECT COUNT(*) as invalid_temps
  FROM weather_readings
  WHERE temperature_c < -100 OR temperature_c > 60;
"

# Check for duplicates (should be 0)
psql -d weather_db -c "
  SELECT location_id, recorded_at, COUNT(*)
  FROM weather_readings
  GROUP BY location_id, recorded_at
  HAVING COUNT(*) > 1;
"
```

---

## 🧪 Quick Tests

### Test API Connectivity
```python
import requests
resp = requests.get(
    "https://api.open-meteo.com/v1/forecast",
    params={
        "latitude": 30.0,
        "longitude": 31.0,
        "hourly": "temperature_2m",
        "current_weather": "true"
    },
    timeout=10
)
print(f"Status: {resp.status_code}")
print(f"Response: {resp.json()}")
```

### Test Database Connection
```python
from src.load import test_connection
if test_connection():
    print("✅ Database connection OK")
else:
    print("❌ Database connection FAILED")
```

### Test Full Pipeline (Dry Run)
```python
from src.pipeline import run_pipeline
from src.extract import City

# Test with single city
stats = run_pipeline(cities=[City("Cairo", 30.0444, 31.2357)])
print(f"Success: {stats['success']}")
print(f"Rows inserted: {stats['rows_inserted']}")
print(f"Errors: {stats['errors']}")
```

---

## 📈 Success Metrics

```
✅ Healthy Pipeline:
   - Success rate: >95%
   - API retry rate: <0.5 per call
   - Validation failure rate: <10%
   - Data freshness: <2 hours
   - Pipeline duration: <5 minutes
   - Zero crashes or hangs

⚠️ Warning Signs:
   - Success rate: 90-95%
   - Retries increasing
   - Data freshness: 2-6 hours
   - Validation failures: 10-20%

🚨 Critical Issues:
   - Success rate: <90%
   - Multiple consecutive failures
   - Data freshness: >6 hours
   - Pipeline crashes/hangs
   - All cities failing
```

---

## 🎯 Fix Priority

```
┌─────────────────────────────────────────────────┐
│ IMMEDIATE (50 min)                              │
├─────────────────────────────────────────────────┤
│ 1. Add JSONDecodeError handling     [10 min]   │
│ 2. Add schema validation            [20 min]   │
│ 3. Fix datetime format               [15 min]   │
│ 4. Check empty response              [5 min]    │
│                                                  │
│ ✓ Prevents 80% of production crashes           │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│ SHORT-TERM (2 hours)                            │
├─────────────────────────────────────────────────┤
│ 5. Add connection pool timeout      [30 min]   │
│ 6. Improve rate limit handling      [15 min]   │
│ 7. Validate environment vars        [10 min]   │
│ 8. Create error tests               [60 min]   │
│                                                  │
│ ✓ Production-grade error handling               │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│ FUTURE (8 hours)                                │
├─────────────────────────────────────────────────┤
│ 9. Structured JSON logging          [90 min]   │
│ 10. Prometheus metrics              [120 min]  │
│ 11. Monitoring dashboard            [180 min]  │
│ 12. Integration tests               [120 min]  │
│                                                  │
│ ✓ Enterprise monitoring & observability        │
└─────────────────────────────────────────────────┘
```

---

## 📞 Quick Links

- **Full Analysis**: See `DEBUG_ANALYSIS.md` (38 pages)
- **Summary**: See `DEBUG_SUMMARY.md` (5 pages)
- **Architecture**: See `ARCHITECTURE_REVIEW.md`
- **Security**: See `SECURITY_VERIFICATION_REPORT.md`

---

## 🆘 Getting Help

**Issue?** Follow this decision tree:

```
Pipeline fails?
├─ Check error message in this card
├─ Run health check commands
├─ Review logs: tail -n 100 pipeline.log
├─ Test API: curl https://api.open-meteo.com/...
├─ Test DB: psql -d weather_db -c "SELECT 1;"
└─ Still stuck? See DEBUG_ANALYSIS.md Section 12
```

---

**Version**: 1.0 | **Last Updated**: 2026-03-05
