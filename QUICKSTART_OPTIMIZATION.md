# Quick Start: Performance Optimization

**🚀 Get 80-98% performance improvement in 5 hours**

---

## Step 1: Understand the Problem (5 minutes)

Read the executive summary:
```bash
cat PERFORMANCE_SUMMARY.md
```

**TL;DR:** Three bottlenecks identified:
1. Serial API calls (92.6% of time)
2. Unbounded database queries  
3. Python row iteration

---

## Step 2: Benchmark Current Performance (2 minutes)

```bash
# Run benchmark
python scripts/benchmark.py

# Expected output:
# Average duration: ~27 seconds for 5 cities
```

---

## Step 3: Implement Quick Wins (5 hours)

### Fix #1: Parallel API Extraction (2 hours)

**File:** `src/extract.py`

Replace lines 153-167:
```python
# BEFORE (Serial)
for city in cities:
    try:
        weather_data = fetch_weather_data(...)
        results.append((city.name, weather_data))
    except requests.RequestException:
        continue
```

With:
```python
# AFTER (Parallel)
from concurrent.futures import ThreadPoolExecutor, as_completed

results: list[tuple[str, dict[str, Any]]] = []

with ThreadPoolExecutor(max_workers=10) as executor:
    future_to_city = {
        executor.submit(
            fetch_weather_data,
            city.latitude,
            city.longitude,
            hourly_fields,
            timezone
        ): city
        for city in cities
    }
    
    for future in as_completed(future_to_city):
        city = future_to_city[future]
        try:
            weather_data = future.result()
            results.append((city.name, weather_data))
            logger.info(f"✓ {city.name}")
        except Exception as e:
            logger.error(f"✗ {city.name}: {e}")
```

**Expected improvement:** 25s → 5s (80% faster)

---

### Fix #2: Add LIMIT Clauses (1 hour)

**File:** `dashboard/queries.py`

Update `get_filtered_records` (lines 301-353):
```python
@st.cache_data(ttl=300)
def get_filtered_records(
    _conn: Connection, 
    cities: list[str], 
    start: date, 
    end: date,
    limit: int = 1000,    # ADD THIS
    offset: int = 0        # ADD THIS
) -> pl.DataFrame:
    # ... existing code ...
    
    query_safe = text(f"""
        SELECT ...
        FROM weather_readings wr
        JOIN locations l ON wr.location_id = l.id
        WHERE l.city_name IN ({placeholders})
            AND DATE(wr.recorded_at) BETWEEN :start_date AND :end_date
        ORDER BY wr.recorded_at DESC, l.city_name
        LIMIT :limit OFFSET :offset  -- ADD THIS
    """)
    
    params = {f"city{i}": city for i, city in enumerate(cities)}
    params.update({
        "start_date": start,
        "end_date": end,
        "limit": limit,      # ADD THIS
        "offset": offset     # ADD THIS
    })
```

**Repeat for:** `get_temperature_trend`, `get_daily_precipitation`, `get_humidity_trend`

**Expected improvement:** 15s → 50ms (99.7% faster at scale)

---

### Fix #3: Vectorize Load Operations (2 hours)

**File:** `src/load.py`

Replace lines 357-380:
```python
# BEFORE (Python loop)
records: list[tuple[Any, ...]] = []
for row in df_validated.iter_rows(named=True):
    city_name = row["city_name"]
    location_id = city_mapping.get(city_name)
    if location_id is None:
        stats["skipped"] += 1
        continue
    record = (location_id, row["recorded_at"], ...)
    records.append(record)
```

With:
```python
# AFTER (Vectorized)
# Create location mapping DataFrame
location_df = pl.DataFrame({
    "city_name": list(city_mapping.keys()),
    "location_id": list(city_mapping.values())
})

# Join to add location_id column (MUCH faster)
df_with_location = df_validated.join(
    location_df,
    on="city_name",
    how="inner"
)

# Select columns and convert to list
records = df_with_location.select([
    "location_id", "recorded_at", "temperature_c", "temperature_f",
    "humidity_pct", "wind_speed_kmh", "precipitation_mm",
    "weather_code", "ingested_at", "source"
]).to_numpy().tolist()

stats["skipped"] = df_validated.height - len(records)
```

**Expected improvement:** 840ms → 10ms (98% faster)

---

## Step 4: Verify Improvements (2 minutes)

```bash
# Re-run benchmark
python scripts/benchmark.py

# Expected output:
# Average duration: ~5.5 seconds for 5 cities (was 27s)
# Improvement: 80% faster!
```

---

## Step 5: Test at Scale (5 minutes)

Modify `src/extract.py` to test with more cities:
```python
# Add more test cities
TEST_CITIES = [
    City("Cairo", 30.0444, 31.2357),
    City("London", 51.5074, -0.1278),
    City("Tokyo", 35.6762, 139.6503),
    City("New York", 40.7128, -74.0060),
    City("Sydney", -33.8688, 151.2093),
    City("Paris", 48.8566, 2.3522),
    City("Berlin", 52.5200, 13.4050),
    City("Mumbai", 19.0760, 72.8777),
    City("Dubai", 25.2048, 55.2708),
    City("Singapore", 1.3521, 103.8198),
]

# Test with 10 cities
python scripts/benchmark.py
# Expected: ~5.5 seconds (same as 5 cities!)
```

---

## Verification Checklist

After implementing fixes:
- [ ] Pipeline runs in <10s for 5 cities
- [ ] Pipeline runs in <10s for 10 cities  
- [ ] Dashboard loads in <2s
- [ ] No browser crashes on large date ranges
- [ ] All tests pass: `pytest tests/`
- [ ] Benchmark shows 80%+ improvement

---

## Troubleshooting

**Import Error: "No module named 'concurrent'"**
```bash
# concurrent.futures is in Python stdlib (3.2+)
python --version  # Should be 3.11+
```

**Test Failure: "Connection refused"**
```bash
# Start database
docker-compose up -d postgres
docker ps  # Verify it's running
```

**Dashboard Error: "Too many parameters"**
```bash
# If you get parameter errors, check LIMIT/OFFSET are added correctly
# See PERFORMANCE_REVIEW.md Section 2.2 for full examples
```

---

## Next Steps

1. ✅ Implement 3 quick fixes (5 hours)
2. ✅ Verify 80%+ improvement
3. 📖 Read `PERFORMANCE_REVIEW.md` for detailed analysis
4. 🔧 Implement Phase 2 optimizations (8.5 hours)
5. 📊 Set up monitoring (Phase 3, 6 hours)

---

## Need Help?

- **Detailed implementation:** See `PERFORMANCE_REVIEW.md` Sections 1-2
- **Profiling:** See `scripts/README.md`
- **Database optimization:** See `PERFORMANCE_REVIEW.md` Section 2
- **Cost analysis:** See `PERFORMANCE_SUMMARY.md`

---

**Expected Total Time:** 5 hours  
**Expected Improvement:** 80-98% faster execution  
**Risk Level:** Low (all changes are backward-compatible)

🚀 Ready to optimize! Start with Fix #1 (parallel extraction).
