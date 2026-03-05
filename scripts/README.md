# Performance Profiling & Benchmarking Scripts

This directory contains tools for profiling, benchmarking, and load testing the Weather Data Pipeline.

## 📋 Available Scripts

### 1. **Pipeline Profiler** (`profile_pipeline.py`)
Profile the ETL pipeline to identify performance bottlenecks.

**Usage:**
```bash
python scripts/profile_pipeline.py
```

**Output:**
- `pipeline.prof` - Binary cProfile output
- `pipeline_profile.txt` - Human-readable report
- Console output with top 10 slowest functions

**Interactive Analysis:**
```bash
python -m pstats pipeline.prof
>>> sort cumulative
>>> stats 20
>>> quit
```

---

### 2. **Benchmark Suite** (`benchmark.py`)
Run pipeline multiple times and collect performance statistics.

**Usage:**
```bash
python scripts/benchmark.py
```

**Output:**
- Average execution time
- Standard deviation
- Min/max execution time
- Throughput (cities/second, rows/second)
- Scalability projections for 10, 50, 100 cities

**Example Output:**
```
================================================================================
PIPELINE BENCHMARK - 3 runs
================================================================================

--- Run 1/3 ---
...
Run 1 completed in 27.35s

================================================================================
BENCHMARK RESULTS
================================================================================
Average duration: 27.12s
Std deviation: 0.45s
Min duration: 26.80s
Max duration: 27.35s

--------------------------------------------------------------------------------
THROUGHPUT
--------------------------------------------------------------------------------
Cities per second: 0.18
Rows per second: 30.98

--------------------------------------------------------------------------------
SCALABILITY PROJECTIONS
--------------------------------------------------------------------------------
10 cities estimated: 54.2s
50 cities estimated: 271.2s
100 cities estimated: 542.4s
```

---

### 3. **Database Query Profiler** (`profile_queries.sql`)
Analyze PostgreSQL query performance, index usage, and cache hit rates.

**Usage:**
```bash
# Connect to database
docker exec -it weather_pipeline_db psql -U postgres -d weather_db

# Run profiling script
\i scripts/profile_queries.sql
```

**What it checks:**
- EXPLAIN ANALYZE for critical queries
- Index usage statistics
- Slow query detection (requires `pg_stat_statements` extension)
- Table bloat analysis
- Cache hit ratio (should be >99%)

---

### 4. **Load Testing Tool** (`load_test.py`)
Simulate multiple concurrent users accessing the Streamlit dashboard.

**Installation:**
```bash
pip install locust
```

**Usage:**

**Method 1: Web UI (Recommended)**
```bash
# Start dashboard
streamlit run dashboard/app.py

# In another terminal, start Locust
locust -f scripts/load_test.py --host=http://localhost:8501

# Open browser: http://localhost:8089
# Configure: Users=10, Spawn rate=1, Duration=5m
```

**Method 2: Command Line**
```bash
locust -f scripts/load_test.py \
    --host=http://localhost:8501 \
    --users 10 \
    --spawn-rate 1 \
    --run-time 5m \
    --headless
```

**Test Scenarios:**
- 60% - View current conditions (most common)
- 30% - View historical trends
- 10% - Compare cities

---

## 🎯 Quick Start: Full Performance Assessment

Run all profiling tools in sequence:

```bash
# 1. Benchmark pipeline performance
echo "=== BENCHMARKING PIPELINE ==="
python scripts/benchmark.py

# 2. Profile for bottlenecks
echo "\n=== PROFILING FOR BOTTLENECKS ==="
python scripts/profile_pipeline.py

# 3. Check database performance
echo "\n=== DATABASE QUERY ANALYSIS ==="
docker exec -it weather_pipeline_db psql -U postgres -d weather_db -f scripts/profile_queries.sql

# 4. Load test dashboard (run this manually in separate terminal)
echo "\n=== DASHBOARD LOAD TESTING ==="
echo "Start dashboard: streamlit run dashboard/app.py"
echo "Then run: locust -f scripts/load_test.py --host=http://localhost:8501"
```

---

## 📊 Performance Targets (Current System)

| Metric | Current | Target | Status |
|--------|---------|--------|--------|
| Pipeline runtime (5 cities) | ~27s | <30s | ✅ PASS |
| Extraction time | ~25s | <25s | ⚠️ At limit |
| Transformation time | ~10ms | <100ms | ✅ PASS |
| Load time | ~990ms | <5s | ✅ PASS |
| Dashboard query time | 100-500ms | <500ms | ✅ PASS |

---

## 🚀 Expected Performance After Optimizations

| Metric | Current | Optimized | Improvement |
|--------|---------|-----------|-------------|
| Pipeline (5 cities) | 27s | 5.5s | **80% faster** |
| Pipeline (100 cities) | 8m 40s | 9.5s | **98% faster** |
| Dashboard queries | 15s | 50ms | **99.7% faster** |

See `PERFORMANCE_REVIEW.md` for detailed analysis and optimization recommendations.

---

## 🔧 Advanced Profiling

### Memory Profiling
```bash
# Install memory profiler
pip install memory-profiler

# Create memory profile script
python -m memory_profiler scripts/profile_pipeline.py
```

### Line-by-Line Profiling
```bash
# Install line_profiler
pip install line_profiler

# Add @profile decorator to functions you want to profile
kernprof -l -v scripts/benchmark.py
```

### Visual Flame Graphs
```bash
# Install flamegraph tools
pip install flameprof

# Generate flame graph from profile
flameprof pipeline.prof > pipeline_flamegraph.svg

# Open in browser
firefox pipeline_flamegraph.svg
```

---

## 📖 Related Documentation

- **PERFORMANCE_REVIEW.md** - Comprehensive performance analysis
- **README.md** - Project overview
- **QUICKSTART.md** - Getting started guide

---

## 🐛 Troubleshooting

**Issue: "No module named 'src'"**
```bash
# Make sure you're running from project root
cd /path/to/weather-data-pipeline
python scripts/benchmark.py
```

**Issue: "Database connection failed"**
```bash
# Ensure PostgreSQL is running
docker ps | grep weather_pipeline_db

# Start database if needed
docker-compose up -d postgres
```

**Issue: "Locust not found"**
```bash
# Install locust
pip install locust

# Or use project dependencies
pip install -r requirements.txt
```

---

**Last Updated:** 2026-03-05  
**Maintainer:** Performance Engineering Team
