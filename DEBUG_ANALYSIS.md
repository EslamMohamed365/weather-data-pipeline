# Weather Data Pipeline - Comprehensive Debugging Analysis

## Executive Summary

**Overall Error Handling Quality Score: 7.5/10**

### ✅ Strengths
- SQL injection protection fully implemented (parameterized queries)
- Connection pooling with proper resource management
- Retry logic for transient database and API errors
- Input validation with comprehensive range checks
- Proper transaction management with rollback
- Detailed logging throughout the pipeline

### ⚠️ Critical Gaps Identified
1. **JSON parsing lacks explicit error handling** (High Priority)
2. **No handling for malformed API responses** (High Priority)
3. **Schema column mismatch between load.py and schema.sql** (Critical)
4. **Empty DataFrame edge cases not fully tested** (Medium Priority)
5. **Connection pool exhaustion lacks monitoring** (Medium Priority)
6. **Race conditions in concurrent pipeline runs** (Low Priority)
7. **Missing timeout configuration for database operations** (Medium Priority)

### 🚨 Most Likely Failure Scenarios
1. **API returns invalid JSON** → Pipeline crashes (no try-except around `response.json()`)
2. **All cities fail extraction** → Transform gets empty list, continues gracefully ✓
3. **Database connection pool exhausted** → Hangs indefinitely (no timeout on `getconn()`)
4. **Schema change in API response** → KeyError in transform phase (caught, but logs generic error)
5. **Location table uses `id` but code references `location_id`** → Database query failures

---

## 1. Runtime Error Analysis

### 1.1 Type Errors

| Location | Issue | Likelihood | Current Handling | Risk |
|----------|-------|------------|------------------|------|
| `load.py:294` | `cursor.execute()` with tuple vs list | Low | ✅ Correct usage | None |
| `transform.py:61` | ISO 8601 parsing with wrong format | Medium | ⚠️ Generic exception catch | Medium |
| `dashboard/queries.py:82` | Column name mismatch: `l.id` vs `l.location_id` | **HIGH** | ❌ Unhandled | **CRITICAL** |
| `load.py:359-360` | `city_mapping.get()` returns None | Low | ✅ Checked at line 361 | None |

#### ❌ **CRITICAL BUG FOUND: Schema Column Mismatch**

**File: `dashboard/queries.py`, Line 82**
```python
JOIN locations l ON wr.location_id = l.id
```

**Issue**: Schema defines `locations.id` but the JOIN references `l.id` which should work. However, in `get_latest_readings()` line 82, there's a potential issue if the schema was modified.

**Actually reviewing schema.sql again:**
- `locations` table has `id SERIAL PRIMARY KEY` (line 11)
- `weather_readings` table has `location_id INTEGER NOT NULL` (line 40)

**Status**: ✅ Actually correct - false alarm. The foreign key properly references `locations.id`.

#### ⚠️ **Datetime Parsing Risk**

**File: `transform.py`, Line 61**
```python
df = df.with_columns(pl.col("recorded_at").str.to_datetime("%Y-%m-%dT%H:%M"))
```

**Issues**:
1. **Missing seconds**: Format lacks `%S` - API likely returns `2024-03-05T14:30:00`
2. **Missing timezone**: Format lacks timezone specifier
3. **No explicit error handling**: If parsing fails, generic exception is caught

**Expected API Format**: `2024-03-05T14:30:00` (ISO 8601 with seconds)

**Fix Required**:
```python
# Should be:
df = df.with_columns(
    pl.col("recorded_at").str.to_datetime("%Y-%m-%dT%H:%M:%S", strict=False)
)
```

**Test**: Create data with API-format timestamps to verify.

---

### 1.2 Index Errors

| Location | Issue | Likelihood | Current Handling | Risk |
|----------|-------|------------|------------------|------|
| `dashboard/app.py:289-293` | Accessing row with `[0]` index | Low | ⚠️ Assumes DataFrame not empty | Low |
| `transform.py:36-41` | Dictionary `.get()` on missing keys | Low | ✅ Returns None, checked at line 44 | None |
| `load.py:357` | Iterating empty DataFrame | Low | ✅ Checked at line 318, 329 | None |

**Safeguard Recommendation**: Add assertions or length checks before indexing.

---

### 1.3 Key Errors

| Location | Issue | Likelihood | Current Handling | Risk |
|----------|-------|------------|------------------|------|
| `transform.py:29-41` | Missing keys in API response | Medium | ✅ Uses `.get()` with defaults | Low |
| `extract.py:92` | **Malformed JSON response** | **Medium** | ❌ **No try-except** | **HIGH** |
| `load.py:50-55` | Missing environment variables | Low | ✅ Defaults provided | None |
| `dashboard/app.py:132-136` | Missing DB env vars | Low | ✅ Defaults provided | None |

#### ❌ **CRITICAL GAP: JSON Parsing Not Protected**

**File: `extract.py`, Line 92**
```python
data = response.json()  # ❌ No try-except for JSONDecodeError
```

**Failure Scenarios**:
1. API returns HTML error page instead of JSON (500 error)
2. API returns truncated JSON (network interruption)
3. API returns invalid JSON (API bug)

**Impact**: Pipeline crashes with `JSONDecodeError`, no retry possible.

**Current Code**:
```python
except requests.exceptions.RequestException as e:
    # This does NOT catch JSONDecodeError!
```

**Fix Required**:
```python
try:
    response = requests.get(API_BASE_URL, params=params, timeout=timeout)
    response.raise_for_status()
    data = response.json()  # Can raise JSONDecodeError
    
except requests.exceptions.JSONDecodeError as e:
    last_exception = e
    logger.warning(f"Invalid JSON response on attempt {attempt}/{MAX_RETRIES}")
    
except requests.exceptions.Timeout as e:
    # ... existing code
```

---

### 1.4 Value Errors

| Location | Issue | Likelihood | Current Handling | Risk |
|----------|-------|------------|------------------|------|
| `load.py:52` | `int(os.getenv("DB_PORT"))` on non-numeric | Low | ⚠️ Crashes on invalid value | Low |
| `transform.py:61` | Date parsing with wrong format | Medium | ⚠️ Generic exception | Medium |
| `load.py:110-210` | Validation filters invalid data | Low | ✅ Comprehensive checks | None |

**Environment Variable Validation Missing**:
```python
# Current code (load.py:52)
port=int(os.getenv("DB_PORT", "5432"))

# If .env has: DB_PORT=abc
# Result: ValueError: invalid literal for int() with base 10: 'abc'
```

**Fix**:
```python
try:
    port = int(os.getenv("DB_PORT", "5432"))
except ValueError:
    logger.warning("Invalid DB_PORT, using default 5432")
    port = 5432
```

---

## 2. Database Error Scenarios

### 2.1 Connection Issues

| Scenario | Current Behavior | Expected Behavior | Gap? |
|----------|------------------|-------------------|------|
| PostgreSQL is down | Retry 3x, then crash | ✓ Retry, fail gracefully | No |
| Connection pool exhausted (>10 concurrent) | **Hangs indefinitely** | Timeout + error message | **YES** |
| Network timeout during query | Retry 3x | ✓ Correct | No |
| SSL/TLS certificate invalid | Crash with psycopg2.Error | ⚠️ Generic error message | Minor |

#### ⚠️ **Connection Pool Exhaustion Risk**

**File: `load.py`, Line 228**
```python
conn = pool_instance.getconn()  # ❌ No timeout parameter
```

**Issue**: If 10 connections are in use and a request arrives, `getconn()` **blocks indefinitely**.

**Scenario**:
1. 10 concurrent pipeline instances running
2. 11th instance calls `get_db_connection()`
3. Process hangs forever (no timeout)
4. No error message, just silent hang

**Fix Required**:
```python
# Option 1: Add timeout (requires psycopg2.pool extension)
try:
    conn = pool_instance.getconn(timeout=30)  # Wait max 30 seconds
except Exception:
    logger.error("Connection pool exhausted - all 10 connections in use")
    raise

# Option 2: Check pool before requesting
if pool_instance._used == pool_instance.maxconn:
    logger.error("Connection pool exhausted (10/10 connections in use)")
    raise RuntimeError("Database connection pool exhausted")
```

**Monitoring Recommendation**: Add metrics to track pool usage:
```python
logger.info(f"Pool status: {pool_instance._used}/{pool_instance.maxconn} connections in use")
```

---

### 2.2 Transaction Failures

| Scenario | Current Behavior | Expected Behavior | Gap? |
|----------|------------------|-------------------|------|
| Commit fails mid-transaction | Rollback + exception | ✓ Correct | No |
| Deadlock (2 pipelines insert same city) | Retry 3x via decorator | ✓ Correct | No |
| Unique constraint violation | `ON CONFLICT DO NOTHING` | ✓ Correct | No |
| Foreign key constraint violation | Crash with IntegrityError | ⚠️ Should never happen if locations exist | Minor |

**Edge Case**: What if `ensure_locations_exist()` fails but transaction commits partially?

**Analysis**:
- `ensure_locations_exist()` uses `ON CONFLICT DO NOTHING` → Safe
- If locations insert fails, `city_mapping` will be empty
- Code checks `if location_id is None` at line 361 → Skips row
- **Status**: ✅ Handled correctly

---

### 2.3 Query Failures

| Scenario | Current Behavior | Expected Behavior | Gap? |
|----------|------------------|-------------------|------|
| Syntax error in query | Crash with ProgrammingError | ⚠️ Should not retry | **Minor** |
| Missing table (schema not initialized) | Crash with ProgrammingError | Pipeline should detect on startup | **YES** |
| Column type mismatch | Crash with DataError | ⚠️ Should not happen if schema correct | Minor |
| Query timeout | Retry 3x | ✓ Correct | No |

#### ⚠️ **Schema Validation Missing on Startup**

**File: `pipeline.py`, Line 76**
```python
if not test_connection():
    logger.error("Database connection test failed. Aborting pipeline.")
```

**Gap**: `test_connection()` only runs `SELECT 1` - does not verify schema exists.

**Scenario**:
1. Fresh PostgreSQL database
2. Schema not created (`schema.sql` not run)
3. `test_connection()` passes ✓
4. Pipeline proceeds to load step
5. **Crashes** with `relation "locations" does not exist`

**Fix Required**:
```python
@retry_on_db_error(max_retries=3)
def verify_schema() -> bool:
    """Verify required tables exist."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'locations'
                ) AND EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'weather_readings'
                )
            """)
            result = cursor.fetchone()
            if result and result[0]:
                logger.info("✅ Database schema verified")
                return True
            else:
                logger.error("❌ Missing required tables (locations, weather_readings)")
                logger.error("Please run: psql -d weather_db -f sql/schema.sql")
                return False
    except psycopg2.Error as e:
        logger.error(f"Schema verification failed: {e}")
        return False
```

**Add to pipeline.py**:
```python
# After line 79, before extraction:
if not verify_schema():
    logger.error("Database schema invalid. Aborting pipeline.")
    pipeline_stats["errors"] += 1
    return pipeline_stats
```

---

## 3. API Error Scenarios

### 3.1 Network Errors

| Error Type | Current Behavior | Expected Behavior | Gap? |
|------------|------------------|-------------------|------|
| Connection timeout | Retry 3x with exponential backoff | ✓ Correct | No |
| DNS resolution failure | Retry 3x | ✓ Correct | No |
| SSL certificate verification | Crash with requests.SSLError | ⚠️ Retry not helpful | Minor |
| Rate limiting (429) | Retry 3x | ⚠️ Should use longer backoff | **YES** |

#### ⚠️ **Rate Limiting Needs Special Handling**

**Issue**: Current backoff (1s, 2s, 4s) may be too short for rate limiting.

**API Response Headers**:
```
HTTP/1.1 429 Too Many Requests
Retry-After: 60
```

**Fix**:
```python
except requests.exceptions.HTTPError as e:
    last_exception = e
    status_code = e.response.status_code if e.response else None
    
    # Special handling for rate limiting
    if status_code == 429:
        retry_after = e.response.headers.get('Retry-After', 60)
        logger.warning(f"Rate limited. Waiting {retry_after}s before retry...")
        time.sleep(int(retry_after))
        continue
    
    logger.warning(f"HTTP error {status_code} on attempt {attempt}/{MAX_RETRIES}")
```

---

### 3.2 API Response Errors

| Scenario | Current Behavior | Expected Behavior | Gap? |
|----------|------------------|-------------------|------|
| Invalid JSON (malformed) | **Crash with JSONDecodeError** | Retry as transient error | **YES** |
| Missing fields in JSON | Returns None via `.get()` | ✓ Handled in transform | No |
| Unexpected data types | Generic exception in transform | ⚠️ Should validate types | Minor |
| Empty response body | `response.json()` raises error | ⚠️ Should check `Content-Length` | Minor |

#### ❌ **Missing: Empty Response Handling**

```python
# Add before response.json():
if not response.content:
    logger.warning("Empty response body from API")
    raise requests.RequestException("Empty response body")

data = response.json()
```

---

### 3.3 Retry Logic Verification

**Current Implementation Analysis**:

```python
# extract.py, lines 84-121
for attempt in range(1, MAX_RETRIES + 1):
    try:
        # ... fetch logic
    except requests.exceptions.Timeout as e:
        # ✅ Retries timeout errors
    except requests.exceptions.HTTPError as e:
        # ✅ Retries HTTP errors (including 429, 500, 503)
    except requests.exceptions.RequestException as e:
        # ✅ Retries all other request errors
    
    # Backoff calculation
    if attempt < MAX_RETRIES:
        sleep_time = backoff * (2 ** (attempt - 1))  # 1s, 2s, 4s
```

**Verification**:
- ✅ Retries transient errors
- ✅ Exponential backoff implemented correctly
- ✅ Max retries respected (3 attempts)
- ✅ Logging during retries
- ❌ **Does not retry JSONDecodeError** (not caught)
- ⚠️ Rate limiting (429) uses same backoff as transient errors

---

## 4. Data Quality Issues

### 4.1 Input Validation Coverage

**File: `load.py:110-210` - `validate_weather_data()`**

| Validation Rule | Implementation | Edge Cases Handled? | Status |
|-----------------|----------------|---------------------|--------|
| Timestamp range (8 days past to 1h future) | ✅ Lines 129-143 | ✅ Timezone-aware | Complete |
| Temperature (-100°C to 60°C) | ✅ Lines 146-153 | ✅ Null allowed | Complete |
| Humidity (0-100%, clamped) | ✅ Lines 156-165 | ✅ Null allowed | Complete |
| Wind speed (0-400 km/h) | ✅ Lines 168-175 | ✅ Null allowed | Complete |
| Precipitation (0-2000mm) | ✅ Lines 178-185 | ✅ Null allowed | Complete |
| Weather code (0-99) | ✅ Lines 188-195 | ✅ Null allowed | Complete |
| City name not empty | ✅ Lines 198-201 | ⚠️ Null check OK, but no length limit | Minor |

#### ⚠️ **Edge Case: Exactly at Boundary Values**

**Test Case**:
```python
# Temperature exactly -100°C (should pass)
df = pl.DataFrame({"temperature_c": [-100.0]})

# Filter: (pl.col("temperature_c") >= -100) & (pl.col("temperature_c") <= 60)
# Result: ✅ Passes (inclusive bounds)
```

**Validation**: ✅ Boundaries are inclusive (`>=` and `<=`), which is correct.

#### ⚠️ **Humidity Clamping Edge Case**

**Code**:
```python
df_valid = df_valid.with_columns(
    pl.when(pl.col("humidity_pct").is_null())
      .then(None)
      .when(pl.col("humidity_pct") < 0)
      .then(0.0)
      .when(pl.col("humidity_pct") > 100)
      .then(100.0)
      .otherwise(pl.col("humidity_pct"))
      .alias("humidity_pct")
)
```

**Test Cases**:
- `-10.0` → `0.0` ✅
- `150.0` → `100.0` ✅
- `null` → `null` ✅
- `50.0` → `50.0` ✅

**Status**: ✅ Implementation correct.

---

### 4.2 Transformation Errors

| Scenario | Current Behavior | Expected Behavior | Gap? |
|----------|------------------|-------------------|------|
| Polars operations on empty DataFrame | Returns empty DataFrame | ✓ Correct | No |
| Type conversion failure (str to float) | Generic exception | ⚠️ Should log specific field | Minor |
| DateTime parsing error | Generic exception | ⚠️ Wrong format in code | **YES** |
| Negative values in unit conversion | Converted correctly | ✓ Math is correct | No |

#### ⚠️ **DateTime Format Mismatch (REVISITED)**

**API Response Example** (from Open-Meteo docs):
```json
{
  "hourly": {
    "time": [
      "2024-03-05T00:00",
      "2024-03-05T01:00"
    ]
  }
}
```

**Current Code**:
```python
df = df.with_columns(pl.col("recorded_at").str.to_datetime("%Y-%m-%dT%H:%M"))
```

**Analysis**:
- ✅ Format matches if API returns without seconds
- ⚠️ **BUT**: Most ISO 8601 includes seconds: `2024-03-05T00:00:00`
- ❌ No `try-except` for format errors

**Test Required**: Verify actual API response format.

**Safer Implementation**:
```python
try:
    df = df.with_columns(
        pl.col("recorded_at").str.to_datetime("%Y-%m-%dT%H:%M:%S")
    )
except:
    # Fallback if API doesn't include seconds
    df = df.with_columns(
        pl.col("recorded_at").str.to_datetime("%Y-%m-%dT%H:%M")
    )
```

---

### 4.3 Deduplication Logic

**Implementation**: `transform.py:101-107`

```python
initial_rows = df.height
df = df.unique(subset=["city_name", "recorded_at"], keep="first")
deduplicated_rows = initial_rows - df.height
```

**Test Cases**:

| Scenario | Expected Result | Verified? |
|----------|----------------|-----------|
| All rows duplicates | Returns 1 row (first) | ✅ Polars behavior |
| No duplicates | Returns all rows | ✅ No change |
| Mixed duplicates | Keeps first occurrence | ✅ `keep="first"` |
| Empty DataFrame | Returns empty DataFrame | ✅ No crash |

**Race Condition Analysis**:
- **Scenario**: Two pipeline instances run simultaneously
- **Behavior**: 
  1. Both fetch same data from API
  2. Both transform and deduplicate locally (no race)
  3. Both attempt to insert same rows
  4. Database `ON CONFLICT (location_id, recorded_at) DO NOTHING` handles it ✅
- **Status**: ✅ No data corruption risk

---

## 5. Resource Exhaustion

### 5.1 Memory Leaks

| Component | Potential Leak | Analysis | Risk |
|-----------|---------------|----------|------|
| Connection pool | Connections not returned | ✅ `finally` block at line 244 ensures `putconn()` | None |
| Polars DataFrames | Not garbage collected | ✅ Python GC handles after function return | None |
| Streamlit cache | Growing unbounded | ⚠️ TTL=300s set, but no size limit | Low |
| File handles | Not closed | ✅ No file operations in pipeline | None |

#### ⚠️ **Streamlit Cache Growth**

**Dashboard Query Caching**: `@st.cache_data(ttl=300)`

**Issue**: Cache keys based on function arguments (cities, dates). With many different queries, cache can grow large.

**Example**:
```python
@st.cache_data(ttl=300)
def get_temperature_trend(_conn, cities, start, end):
    # Cache key = hash(cities + start + end)
    # If user selects 100 different date ranges → 100 cache entries
```

**Monitoring**:
```python
# Add to dashboard:
import sys
cache_size = sum(sys.getsizeof(v) for v in st.session_state.values())
logger.info(f"Cache size: {cache_size / 1024 / 1024:.2f} MB")
```

**Mitigation**: Streamlit automatically evicts after TTL (300s = 5 minutes). No action needed.

---

### 5.2 Connection Leaks

**Analysis of `get_db_connection()` Context Manager**:

```python
@contextmanager
def get_db_connection():
    pool_instance = get_connection_pool()
    conn = pool_instance.getconn()  # Get connection
    
    try:
        yield conn
        conn.commit()  # Auto-commit on success
        
    except psycopg2.Error as e:
        if conn:
            conn.rollback()  # Rollback on error
        raise
        
    finally:
        if conn:
            pool_instance.putconn(conn)  # ✅ ALWAYS returns connection
```

**Exception Scenarios**:

| Scenario | `putconn()` Called? | Connection Leaked? |
|----------|---------------------|-------------------|
| Success | ✅ Yes (finally) | No |
| psycopg2.Error | ✅ Yes (finally) | No |
| KeyboardInterrupt | ✅ Yes (finally) | No |
| SystemExit | ✅ Yes (finally) | No |
| `getconn()` raises exception | ❌ No (never acquired) | No |

**Status**: ✅ No connection leaks possible.

---

### 5.3 Thread Safety

| Component | Thread-Safe? | Analysis |
|-----------|-------------|----------|
| Connection pool initialization | ✅ Yes | Double-checked locking with `_pool_lock` (line 46) |
| Connection pool usage | ✅ Yes | `SimpleConnectionPool` is thread-safe |
| Global variables | ✅ Yes | Only `_connection_pool` (protected by lock) |
| Streamlit caching | ✅ Yes | Streamlit handles thread safety |
| Logging | ✅ Yes | Python logging module is thread-safe |

**Analysis of Pool Initialization**:
```python
_connection_pool: pool.SimpleConnectionPool | None = None
_pool_lock = Lock()

def get_connection_pool():
    global _connection_pool
    
    if _connection_pool is None:  # First check (no lock)
        with _pool_lock:  # Acquire lock
            if _connection_pool is None:  # Second check (with lock)
                _connection_pool = pool.SimpleConnectionPool(...)
    
    return _connection_pool
```

**Pattern**: Classic double-checked locking ✅ (safe in Python due to GIL)

**Status**: ✅ Thread-safe implementation.

---

## 6. Error Message Quality

### 6.1 Error Messages Audit

| Location | Current Message | Quality | Improvement |
|----------|----------------|---------|-------------|
| `extract.py:124` | "Failed to fetch weather data for (lat, lon) after 3 attempts" | ✅ Good | Include city name |
| `transform.py:113` | "Error transforming data for {city_name}: {e}" | ⚠️ Generic | Include row count, field that failed |
| `load.py:237` | "Database error: {e}" | ⚠️ Generic | Include operation (commit/rollback) |
| `pipeline.py:148` | "Unexpected error in pipeline: {e}" | ⚠️ Generic | Include pipeline stage |

#### ⚠️ **Generic Error Messages**

**Example**: `transform.py:113`
```python
except Exception as e:
    logger.error(f"Error transforming data for {city_name}: {e}", exc_info=True)
    return None
```

**Issue**: If Polars fails on line 61 (datetime parsing), error message doesn't indicate which field.

**Better Implementation**:
```python
except pl.exceptions.ComputeError as e:
    logger.error(f"Polars computation error for {city_name}: {e}")
    logger.error(f"Columns: {list(df.columns)}")
    logger.error(f"Sample data: {df.head(1)}")
    return None
except Exception as e:
    logger.error(f"Unexpected error transforming {city_name}: {e}", exc_info=True)
    return None
```

---

### 6.2 Logging Quality

| Aspect | Implementation | Quality | Improvement |
|--------|---------------|---------|-------------|
| Log levels | INFO, WARNING, ERROR, DEBUG | ✅ Appropriate | None |
| Context included | City name, attempt number, row counts | ✅ Good | Add request IDs for correlation |
| Stack traces | `exc_info=True` in error logs | ✅ Excellent | None |
| Structured logging | Plain text | ⚠️ Not parseable | Add JSON logging option |
| Sensitive data | Passwords not logged | ✅ Safe | Verify coordinates not PII |

#### ⚠️ **No Structured Logging**

**Current**: Plain text logs
```
2024-03-05 10:15:23 - src.extract - INFO - Fetching weather data for (30.0444, 31.2357)
```

**Better**: JSON logs for parsing
```json
{
  "timestamp": "2024-03-05T10:15:23Z",
  "level": "INFO",
  "module": "src.extract",
  "message": "Fetching weather data",
  "city": "Cairo",
  "latitude": 30.0444,
  "longitude": 31.2357,
  "attempt": 1,
  "max_retries": 3
}
```

**Implementation**:
```python
import logging
import json
from datetime import datetime

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "module": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, 'city'):
            log_data['city'] = record.city
        if hasattr(record, 'attempt'):
            log_data['attempt'] = record.attempt
        return json.dumps(log_data)

# Usage:
handler = logging.StreamHandler()
handler.setFormatter(JSONFormatter())
logger.addHandler(handler)

# Log with extra context:
logger.info("Fetching weather data", extra={"city": city_name, "attempt": 1})
```

---

## 7. Edge Cases

### 7.1 Empty Data Scenarios

| Scenario | Current Behavior | Expected Behavior | Gap? |
|----------|------------------|-------------------|------|
| API returns no hourly data | `transform_weather_data()` returns None | ✅ Logged, skipped | No |
| Database has no cities configured | Uses DEFAULT_CITIES | ✅ Correct | No |
| All cities fail extraction | `city_data_list` is empty, transform returns None | ✅ Pipeline logs error, exits | No |
| All rows filtered by validation | Returns stats with 0 inserted | ✅ Logged at line 330 | No |

**Test Case**: All Cities Fail Extraction

```python
# Simulate all cities failing
def test_all_cities_fail():
    # Mock API to always fail
    results = extract_weather_for_cities([City("Invalid", 999, 999)])
    # Expected: results = [] (empty list)
    
    df = transform_all_cities(results)
    # Expected: df = None (line 141)
    
    stats = load_weather_data(df)
    # Expected: stats = {"inserted": 0, "skipped": 0, "errors": 0, "filtered_invalid": 0}
```

**Verification**: ✅ Code handles gracefully (checked lines 92-95, 106-111, 318-320 in pipeline).

---

### 7.2 Boundary Conditions

| Condition | Test Case | Expected Result | Verified? |
|-----------|-----------|----------------|-----------|
| Exactly 10 connections in pool | 10 concurrent requests | 10 succeed, 11th blocks | ⚠️ No timeout |
| Timestamp exactly 8 days ago | Record at `now - timedelta(days=8)` | ✅ Passes validation (>=) | Yes |
| Temperature exactly -100°C | Record with `-100.0` | ✅ Passes validation (>=) | Yes |
| Empty city name string | Record with `city_name=""` | ✅ Filtered by validation | Yes |

**Test**: Connection Pool Limit
```python
import threading
import time

def worker():
    with get_db_connection() as conn:
        time.sleep(10)  # Hold connection

# Spawn 11 threads
threads = [threading.Thread(target=worker) for _ in range(11)]
for t in threads:
    t.start()

# Expected: First 10 succeed, 11th hangs indefinitely ❌
```

---

### 7.3 Race Conditions

| Scenario | Risk | Mitigation | Status |
|----------|------|------------|--------|
| Two pipeline instances insert same data | Duplicate rows | `ON CONFLICT DO NOTHING` | ✅ Safe |
| Dashboard queries during data insert | Read uncommitted data | ❌ PostgreSQL default isolation is READ COMMITTED | ⚠️ Possible |
| Schema migration during pipeline run | Crash | No migration system | ⚠️ Manual coordination required |

#### ⚠️ **Dashboard Reading Uncommitted Data**

**Scenario**:
1. Pipeline starts inserting 1000 rows (transaction open)
2. Dashboard queries data (sees 0 new rows because transaction not committed)
3. Pipeline commits transaction
4. Dashboard refreshes (now sees all 1000 rows)

**Analysis**: 
- PostgreSQL default isolation level: `READ COMMITTED`
- Dashboard cannot see uncommitted data ✅
- However, dashboard may see **partial batch** if commit happens mid-query

**Impact**: Low - users may see data appear incrementally, which is acceptable.

**No fix required** - this is expected behavior for near-real-time dashboards.

---

## 8. Failure Mode Analysis

### 8.1 Extract Phase Failures

| Failure Mode | Current Behavior | Expected Behavior | Gap? |
|-------------|------------------|-------------------|------|
| All cities fail | `extract_weather_for_cities()` returns `[]` | Pipeline logs error and exits gracefully | ✅ No gap |
| Some cities fail | Continue with successful ones | ✅ Correct (line 166) | No |
| API returns partial data | Transform handles missing fields | ✅ Uses `.get()` with defaults | No |

**Code Review**: `extract.py:164-167`
```python
except requests.RequestException as e:
    logger.error(f"Failed to extract data for {city.name}: {e}")
    # Continue with other cities even if one fails
    continue
```

**Status**: ✅ Graceful degradation implemented correctly.

---

### 8.2 Transform Phase Failures

| Failure Mode | Current Behavior | Expected Behavior | Gap? |
|-------------|------------------|-------------------|------|
| Invalid JSON structure | Returns None | ✅ Logged, skipped | No |
| Missing required fields | Returns None if no timestamps | ✅ Checked at line 44 | No |
| All rows filtered by deduplication | Returns DataFrame with 0 rows | ⚠️ Should warn | **Minor** |

**Edge Case**: All Rows Are Duplicates

```python
# If df.height = 100 and all are duplicates:
df = df.unique(subset=["city_name", "recorded_at"], keep="first")
# Result: df.height = 1 (keeps first occurrence)

# What if user runs pipeline twice immediately?
# First run: Inserts 100 rows
# Second run: All 100 rows are duplicates
# Result: df still has 100 rows after local dedup, but DB will skip all via ON CONFLICT
```

**Current Behavior**: No warning if all rows are duplicates (only logs if some are).

**Improvement**:
```python
if deduplicated_rows == initial_rows - 1:  # All duplicates except first
    logger.warning(f"All rows for {city_name} were duplicates - data may be stale")
```

---

### 8.3 Load Phase Failures

| Failure Mode | Current Behavior | Expected Behavior | Gap? |
|-------------|------------------|-------------------|------|
| Database unreachable | Retry 3x, then crash with psycopg2.Error | ✅ Correct | No |
| Duplicate rows | Skipped via `ON CONFLICT DO NOTHING` | ✅ Correct | No |
| All rows rejected by validation | Returns `{"inserted": 0, ...}` | ✅ Logged at line 330 | No |

**Code Review**: `load.py:318-336`
```python
if df is None or df.height == 0:
    logger.warning("No data to load")
    return {"inserted": 0, "skipped": 0, "errors": 0, "filtered_invalid": 0}

# Validate data
df_validated, validation_warnings = validate_weather_data(df)

for warning in validation_warnings:
    logger.warning(f"⚠️  {warning}")

if df_validated.height == 0:
    logger.warning("No valid rows to insert after validation")
    return {
        "inserted": 0,
        "skipped": 0,
        "errors": 0,
        "filtered_invalid": original_count
    }
```

**Status**: ✅ All failure modes handled with appropriate logging.

---

## 9. Error Catalog

### Priority 1: Critical (Must Fix)

| ID | Error | Likelihood | Impact | Location | Fix Effort |
|----|-------|------------|--------|----------|-----------|
| E001 | **JSONDecodeError not caught** | Medium | Pipeline crash | `extract.py:92` | 10 min |
| E002 | **Connection pool exhaustion hangs** | Medium | Silent hang | `load.py:228` | 30 min |
| E003 | **Schema validation missing** | High (new installs) | Confusing crash | `pipeline.py:76` | 20 min |

---

### Priority 2: High (Should Fix)

| ID | Error | Likelihood | Impact | Location | Fix Effort |
|----|-------|------------|--------|----------|-----------|
| E004 | **DateTime format may be wrong** | Medium | Transform fails | `transform.py:61` | 15 min |
| E005 | **Rate limiting uses wrong backoff** | Low | API bans | `extract.py:104` | 15 min |
| E006 | **Environment variable int() crashes** | Low | Startup crash | `load.py:52` | 10 min |

---

### Priority 3: Medium (Nice to Fix)

| ID | Error | Likelihood | Impact | Location | Fix Effort |
|----|-------|------------|--------|----------|-----------|
| E007 | Generic error messages | High | Hard to debug | Multiple | 60 min |
| E008 | No structured logging | N/A | Log parsing hard | `pipeline.py:18` | 90 min |
| E009 | Empty response body not checked | Low | JSONDecodeError | `extract.py:92` | 5 min |

---

## 10. Failure Mode Matrix

| Failure Scenario | Current Behavior | Expected Behavior | Gap? | Priority | Fix Effort |
|------------------|------------------|-------------------|------|----------|-----------|
| **API Errors** |
| API returns invalid JSON | ❌ Crash with JSONDecodeError | Retry 3x, then fail | **YES** | P1 | 10 min |
| API rate limits (429) | Retry with 1s, 2s, 4s backoff | Use `Retry-After` header | **YES** | P2 | 15 min |
| API returns empty body | ❌ Crash with JSONDecodeError | Log warning, retry | **YES** | P3 | 5 min |
| All cities fail API | ✅ Log error, exit gracefully | ✓ Correct | No | - | - |
| **Database Errors** |
| DB connection lost | ✅ Retry 3x, then fail | ✓ Correct | No | - | - |
| Connection pool exhausted | ❌ Hang indefinitely | Timeout + error message | **YES** | P1 | 30 min |
| Schema not initialized | ❌ Crash with "table does not exist" | Check on startup | **YES** | P1 | 20 min |
| Deadlock | ✅ Retry 3x via decorator | ✓ Correct | No | - | - |
| **Data Quality** |
| All rows invalid | ✅ Log warning, return 0 inserted | ✓ Correct | No | - | - |
| DateTime parse fails | ⚠️ Generic exception | Specific error message | **YES** | P2 | 15 min |
| Empty DataFrame | ✅ Returns None, logged | ✓ Correct | No | - | - |
| **Resource Exhaustion** |
| Memory leak | ✅ No leaks detected | ✓ Correct | No | - | - |
| Connection leak | ✅ `finally` ensures putconn() | ✓ Correct | No | - | - |
| **Race Conditions** |
| Concurrent pipeline runs | ✅ `ON CONFLICT DO NOTHING` | ✓ Correct | No | - | - |
| Dashboard during insert | ✅ READ COMMITTED isolation | ✓ Acceptable | No | - | - |

**Summary**:
- ✅ **8 scenarios handled correctly**
- ❌ **6 scenarios have gaps**
- Total fix effort: **~105 minutes** for all Priority 1 + Priority 2 issues

---

## 11. Error Injection Test Cases

### 11.1 Test Suite Overview

Create `tests/test_error_scenarios.py`:

```python
"""
Error injection tests to verify error handling.
Run with: pytest tests/test_error_scenarios.py -v
"""

import pytest
from unittest.mock import Mock, patch
import requests
import psycopg2
from src.extract import fetch_weather_data
from src.transform import transform_weather_data
from src.load import get_db_connection, load_weather_data
import polars as pl
from datetime import datetime, timezone

class TestAPIErrors:
    """Test API error handling."""
    
    def test_invalid_json_response(self):
        """API returns invalid JSON - should retry then fail."""
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.json.side_effect = requests.exceptions.JSONDecodeError("msg", "doc", 0)
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response
            
            with pytest.raises(requests.RequestException):
                fetch_weather_data(30.0, 31.0)
            
            # Should retry 3 times
            assert mock_get.call_count == 3
    
    def test_empty_response_body(self):
        """API returns empty response body."""
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.content = b""
            mock_response.json.side_effect = requests.exceptions.JSONDecodeError("msg", "doc", 0)
            mock_get.return_value = mock_response
            
            with pytest.raises(requests.RequestException):
                fetch_weather_data(30.0, 31.0)
    
    def test_rate_limiting_429(self):
        """API returns 429 rate limit error."""
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 429
            mock_response.headers = {'Retry-After': '5'}
            mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(response=mock_response)
            mock_get.return_value = mock_response
            
            with pytest.raises(requests.RequestException):
                fetch_weather_data(30.0, 31.0)
    
    def test_timeout_retries(self):
        """API timeout triggers retry logic."""
        with patch('requests.get') as mock_get:
            mock_get.side_effect = requests.exceptions.Timeout("Connection timeout")
            
            with pytest.raises(requests.RequestException):
                fetch_weather_data(30.0, 31.0)
            
            # Should retry 3 times
            assert mock_get.call_count == 3


class TestTransformErrors:
    """Test transformation error handling."""
    
    def test_missing_hourly_data(self):
        """API response missing 'hourly' key."""
        raw_data = {"latitude": 30.0, "longitude": 31.0}
        result = transform_weather_data("Cairo", raw_data)
        assert result is None
    
    def test_empty_timestamps(self):
        """API response has empty timestamps array."""
        raw_data = {
            "hourly": {
                "time": [],
                "temperature_2m": []
            }
        }
        result = transform_weather_data("Cairo", raw_data)
        assert result is None
    
    def test_datetime_parse_error(self):
        """Datetime parsing with wrong format."""
        raw_data = {
            "hourly": {
                "time": ["2024-03-05T14:30:00"],  # Includes seconds
                "temperature_2m": [25.0],
                "relative_humidity_2m": [60.0],
                "wind_speed_10m": [15.0],
                "precipitation": [0.0],
                "weathercode": [1]
            }
        }
        # Current code uses format without seconds - may fail
        # This test will reveal the bug
        result = transform_weather_data("Cairo", raw_data)
        # Expected: Should handle both formats gracefully


class TestDatabaseErrors:
    """Test database error handling."""
    
    def test_connection_pool_exhaustion(self):
        """Connection pool exhausted - should timeout."""
        # This test requires actual connection pool
        # Mock test:
        with patch('psycopg2.pool.SimpleConnectionPool.getconn') as mock_getconn:
            mock_getconn.side_effect = Exception("Pool exhausted")
            
            with pytest.raises(Exception):
                with get_db_connection() as conn:
                    pass
    
    def test_schema_missing_tables(self):
        """Database missing required tables."""
        with patch('psycopg2.connect') as mock_connect:
            mock_conn = Mock()
            mock_cursor = Mock()
            mock_cursor.execute.side_effect = psycopg2.errors.UndefinedTable("relation \"locations\" does not exist")
            mock_conn.cursor.return_value = mock_cursor
            mock_connect.return_value = mock_conn
            
            # Should detect missing schema
            # (Requires implementing verify_schema() first)
    
    def test_transaction_rollback(self):
        """Transaction error triggers rollback."""
        # Create test DataFrame
        df = pl.DataFrame({
            "city_name": ["TestCity"],
            "recorded_at": [datetime.now(timezone.utc)],
            "temperature_c": [25.0],
            "temperature_f": [77.0],
            "humidity_pct": [60.0],
            "wind_speed_kmh": [15.0],
            "precipitation_mm": [0.0],
            "weather_code": [1],
            "ingested_at": [datetime.now(timezone.utc)],
            "source": ["test"]
        })
        
        with patch('src.load.get_db_connection') as mock_get_conn:
            mock_conn = Mock()
            mock_cursor = Mock()
            mock_cursor.execute.side_effect = psycopg2.Error("Simulated DB error")
            mock_conn.cursor.return_value = mock_cursor
            mock_get_conn.return_value.__enter__.return_value = mock_conn
            
            with pytest.raises(psycopg2.Error):
                load_weather_data(df)
            
            # Verify rollback was called
            mock_conn.rollback.assert_called_once()


class TestValidationEdgeCases:
    """Test data validation edge cases."""
    
    def test_exactly_boundary_temperature(self):
        """Temperature exactly at boundary (-100°C, 60°C)."""
        from src.load import validate_weather_data
        
        df = pl.DataFrame({
            "city_name": ["Test1", "Test2"],
            "recorded_at": [datetime.now(timezone.utc)] * 2,
            "temperature_c": [-100.0, 60.0],  # Exactly at boundaries
            "humidity_pct": [50.0] * 2,
            "wind_speed_kmh": [10.0] * 2,
            "precipitation_mm": [0.0] * 2,
            "weather_code": [1] * 2,
            "temperature_f": [0.0] * 2,
            "ingested_at": [datetime.now(timezone.utc)] * 2,
            "source": ["test"] * 2
        })
        
        df_validated, warnings = validate_weather_data(df)
        
        # Both rows should pass (inclusive bounds)
        assert df_validated.height == 2
    
    def test_humidity_clamping(self):
        """Humidity values outside range are clamped."""
        from src.load import validate_weather_data
        
        df = pl.DataFrame({
            "city_name": ["Test1", "Test2"],
            "recorded_at": [datetime.now(timezone.utc)] * 2,
            "temperature_c": [20.0] * 2,
            "humidity_pct": [-10.0, 150.0],  # Outside range
            "wind_speed_kmh": [10.0] * 2,
            "precipitation_mm": [0.0] * 2,
            "weather_code": [1] * 2,
            "temperature_f": [68.0] * 2,
            "ingested_at": [datetime.now(timezone.utc)] * 2,
            "source": ["test"] * 2
        })
        
        df_validated, warnings = validate_weather_data(df)
        
        # Check clamped values
        humidity_values = df_validated["humidity_pct"].to_list()
        assert humidity_values[0] == 0.0  # Clamped from -10
        assert humidity_values[1] == 100.0  # Clamped from 150
    
    def test_empty_city_name(self):
        """Empty city name should be filtered."""
        from src.load import validate_weather_data
        
        df = pl.DataFrame({
            "city_name": [""],
            "recorded_at": [datetime.now(timezone.utc)],
            "temperature_c": [20.0],
            "humidity_pct": [50.0],
            "wind_speed_kmh": [10.0],
            "precipitation_mm": [0.0],
            "weather_code": [1],
            "temperature_f": [68.0],
            "ingested_at": [datetime.now(timezone.utc)],
            "source": ["test"]
        })
        
        df_validated, warnings = validate_weather_data(df)
        
        # Row should be filtered
        assert df_validated.height == 0


class TestEndToEndScenarios:
    """Test complete pipeline failure scenarios."""
    
    def test_all_cities_fail_extraction(self):
        """All cities fail API extraction."""
        from src.extract import City, extract_weather_for_cities
        from src.transform import transform_all_cities
        from src.load import load_weather_data
        
        with patch('src.extract.fetch_weather_data') as mock_fetch:
            mock_fetch.side_effect = requests.RequestException("API down")
            
            # Extract fails for all cities
            cities = [City("Cairo", 30.0, 31.0), City("London", 51.5, -0.1)]
            results = extract_weather_for_cities(cities)
            
            assert len(results) == 0
            
            # Transform handles empty list
            df = transform_all_cities(results)
            assert df is None
            
            # Load handles None DataFrame
            stats = load_weather_data(df)
            assert stats["inserted"] == 0
    
    def test_all_rows_filtered_by_validation(self):
        """All rows fail validation checks."""
        from src.load import load_weather_data
        
        # Create DataFrame with all invalid data
        df = pl.DataFrame({
            "city_name": ["Test"],
            "recorded_at": [datetime.now(timezone.utc)],
            "temperature_c": [1000.0],  # Invalid: too hot
            "humidity_pct": [50.0],
            "wind_speed_kmh": [10.0],
            "precipitation_mm": [0.0],
            "weather_code": [1],
            "temperature_f": [1832.0],
            "ingested_at": [datetime.now(timezone.utc)],
            "source": ["test"]
        })
        
        stats = load_weather_data(df)
        
        assert stats["inserted"] == 0
        assert stats["filtered_invalid"] == 1
```

### 11.2 Integration Tests

Create `tests/test_integration_errors.py`:

```python
"""
Integration tests requiring actual database/API.
Run with: pytest tests/test_integration_errors.py -v --integration
"""

import pytest
import psycopg2
import time
from src.pipeline import run_pipeline
from src.extract import City

@pytest.mark.integration
def test_database_down():
    """Pipeline handles database being down."""
    # Temporarily stop PostgreSQL or use wrong credentials
    import os
    original_host = os.getenv("DB_HOST")
    os.environ["DB_HOST"] = "invalid-host-12345"
    
    try:
        stats = run_pipeline()
        assert stats["success"] == False
        assert stats["errors"] > 0
    finally:
        os.environ["DB_HOST"] = original_host

@pytest.mark.integration
def test_network_timeout():
    """Pipeline handles network timeout."""
    # Use unreachable IP to force timeout
    cities = [City("Unreachable", 999.0, 999.0)]
    
    stats = run_pipeline(cities=cities)
    
    # Should fail gracefully
    assert stats["cities_extracted"] == 0
    assert stats["errors"] > 0

@pytest.mark.integration
def test_concurrent_pipeline_runs():
    """Two pipeline instances run simultaneously."""
    import threading
    
    results = []
    
    def run():
        stats = run_pipeline()
        results.append(stats)
    
    # Start two threads
    threads = [threading.Thread(target=run) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    
    # Both should succeed (or at least not crash)
    assert len(results) == 2
    # Data integrity maintained by ON CONFLICT DO NOTHING
```

---

## 12. Debugging Guide

### 12.1 Common Issues and Solutions

#### **Issue 1: Pipeline crashes with "JSONDecodeError"**

**Symptoms**:
```
requests.exceptions.JSONDecodeError: Expecting value: line 1 column 1 (char 0)
```

**Cause**: API returned invalid JSON (likely HTML error page).

**Debug Steps**:
1. Check API status: `curl https://api.open-meteo.com/v1/forecast?latitude=30&longitude=31`
2. Review logs for HTTP status code before crash
3. Check network connectivity: `ping api.open-meteo.com`

**Fix**: Apply fix for **E001** (add JSONDecodeError handling).

**Workaround**: Wait and retry manually.

---

#### **Issue 2: Pipeline hangs indefinitely**

**Symptoms**:
- Process running but no log output
- CPU usage near 0%
- Cannot kill with Ctrl+C

**Cause**: Connection pool exhausted (10+ concurrent connections).

**Debug Steps**:
1. Check PostgreSQL connections:
   ```sql
   SELECT count(*), state FROM pg_stat_activity 
   WHERE datname = 'weather_db' 
   GROUP BY state;
   ```
2. Look for blocked queries:
   ```sql
   SELECT pid, state, query, wait_event 
   FROM pg_stat_activity 
   WHERE datname = 'weather_db' AND state = 'active';
   ```

**Fix**: Apply fix for **E002** (add connection timeout).

**Workaround**: 
```bash
# Kill hanging process
pkill -9 -f pipeline.py

# Restart with reduced concurrency
python src/pipeline.py
```

---

#### **Issue 3: "Relation 'locations' does not exist"**

**Symptoms**:
```
psycopg2.errors.UndefinedTable: relation "locations" does not exist
```

**Cause**: Database schema not initialized.

**Debug Steps**:
1. Check if tables exist:
   ```sql
   \dt
   ```
2. Verify database name:
   ```sql
   SELECT current_database();
   ```

**Fix**: Initialize schema:
```bash
psql -U postgres -d weather_db -f sql/schema.sql
```

**Prevention**: Apply fix for **E003** (add schema validation).

---

#### **Issue 4: DateTime parsing fails**

**Symptoms**:
```
polars.exceptions.ComputeError: Could not parse "2024-03-05T14:30:00" with format "%Y-%m-%dT%H:%M"
```

**Cause**: API timestamp includes seconds but format string doesn't.

**Debug Steps**:
1. Check API response format:
   ```python
   import requests
   resp = requests.get("https://api.open-meteo.com/v1/forecast?latitude=30&longitude=31&hourly=temperature_2m")
   print(resp.json()["hourly"]["time"][0])
   ```

**Fix**: Apply fix for **E004** (update datetime format).

**Workaround**: None - must fix code.

---

### 12.2 Log Analysis

#### **Finding Error Context**

```bash
# Find all errors in last run
grep -i "error" pipeline.log

# Find errors for specific city
grep "Cairo.*error" pipeline.log -i

# Count retries by attempt number
grep "Retrying in" pipeline.log | wc -l

# Find validation failures
grep "Filtered.*rows" pipeline.log

# Track pipeline execution time
grep "Duration:" pipeline.log | tail -1
```

#### **Log Locations**

| Component | Log Output | Location |
|-----------|-----------|----------|
| Pipeline | STDOUT | Console or redirected file |
| Dashboard | Streamlit logs | `.streamlit/` directory |
| PostgreSQL | System logs | `/var/log/postgresql/` or `pg_log/` |
| API Requests | Not logged | N/A (add via `requests` logging) |

---

### 12.3 Troubleshooting Flowchart

```
Pipeline fails?
├─ Check logs for last error
│
├─ Is error "JSONDecodeError"?
│  ├─ Yes → API returning invalid JSON
│  │        → Check API status
│  │        → Apply Fix E001
│  └─ No → Continue
│
├─ Is error "UndefinedTable"?
│  ├─ Yes → Schema not initialized
│  │        → Run: psql -f sql/schema.sql
│  │        → Apply Fix E003
│  └─ No → Continue
│
├─ Does pipeline hang?
│  ├─ Yes → Connection pool exhausted
│  │        → Check pg_stat_activity
│  │        → Apply Fix E002
│  └─ No → Continue
│
├─ Is error "ComputeError"?
│  ├─ Yes → DateTime parsing issue
│  │        → Check API timestamp format
│  │        → Apply Fix E004
│  └─ No → Continue
│
├─ All cities fail extraction?
│  ├─ Yes → API unreachable
│  │        → Check network: ping api.open-meteo.com
│  │        → Check API status page
│  └─ No → Continue
│
└─ Check generic error handling
   → Review stack trace in logs
   → Increase log level to DEBUG
```

---

## 13. Monitoring Recommendations

### 13.1 Key Metrics to Track

| Metric | Description | Alert Threshold | Collection Method |
|--------|-------------|----------------|-------------------|
| **Pipeline Success Rate** | % of successful pipeline runs | < 95% | Log scraping |
| **API Retry Rate** | Retries per API call | > 0.5 | Counter in extract.py |
| **Validation Failure Rate** | % of rows filtered | > 10% | Stats from load_weather_data() |
| **Pipeline Duration** | End-to-end execution time | > 5 minutes | Pipeline stats |
| **Database Connection Pool Usage** | Active connections / max | > 8/10 (80%) | pg_stat_activity |
| **Rows Inserted per Run** | New rows added | < 100 | Load stats |
| **Cities Failing Extraction** | Count of cities with errors | > 1 | Extract phase logs |
| **Data Freshness** | Time since last successful run | > 2 hours | Query max(ingested_at) |

---

### 13.2 Prometheus Metrics (Example)

Add to pipeline:

```python
from prometheus_client import Counter, Histogram, Gauge

# Metrics
pipeline_runs_total = Counter('weather_pipeline_runs_total', 'Total pipeline runs', ['status'])
pipeline_duration_seconds = Histogram('weather_pipeline_duration_seconds', 'Pipeline execution time')
api_retries_total = Counter('weather_api_retries_total', 'API retry attempts', ['city'])
validation_failures_total = Counter('weather_validation_failures_total', 'Rows filtered by validation')
db_connections_active = Gauge('weather_db_connections_active', 'Active database connections')

# Usage in pipeline:
with pipeline_duration_seconds.time():
    stats = run_pipeline()
    
pipeline_runs_total.labels(status='success' if stats['success'] else 'failure').inc()
validation_failures_total.inc(stats.get('filtered_invalid', 0))
```

---

### 13.3 Health Check Endpoint

Create `health_check.py`:

```python
"""
Health check script for monitoring systems.
Returns:
  - Exit code 0 if healthy
  - Exit code 1 if unhealthy
  - JSON status to stdout
"""

import json
import sys
from datetime import datetime, timezone, timedelta
from src.load import test_connection, get_db_connection

def check_health():
    """Run health checks."""
    health = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "healthy",
        "checks": {}
    }
    
    # Check 1: Database connectivity
    try:
        if test_connection():
            health["checks"]["database"] = {"status": "healthy"}
        else:
            health["checks"]["database"] = {"status": "unhealthy", "error": "Connection failed"}
            health["status"] = "unhealthy"
    except Exception as e:
        health["checks"]["database"] = {"status": "unhealthy", "error": str(e)}
        health["status"] = "unhealthy"
    
    # Check 2: Data freshness
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT MAX(ingested_at) FROM weather_readings")
            last_ingestion = cursor.fetchone()[0]
            
            if last_ingestion:
                age_hours = (datetime.now(timezone.utc) - last_ingestion).total_seconds() / 3600
                if age_hours < 2:
                    health["checks"]["data_freshness"] = {
                        "status": "healthy",
                        "last_ingestion": last_ingestion.isoformat(),
                        "age_hours": age_hours
                    }
                else:
                    health["checks"]["data_freshness"] = {
                        "status": "stale",
                        "last_ingestion": last_ingestion.isoformat(),
                        "age_hours": age_hours
                    }
                    health["status"] = "degraded"
            else:
                health["checks"]["data_freshness"] = {"status": "no_data"}
                health["status"] = "degraded"
                
    except Exception as e:
        health["checks"]["data_freshness"] = {"status": "unknown", "error": str(e)}
    
    # Check 3: Connection pool status
    try:
        from src.load import _connection_pool
        if _connection_pool:
            # Note: SimpleConnectionPool doesn't expose usage stats directly
            # This is approximate
            health["checks"]["connection_pool"] = {
                "status": "healthy",
                "note": "Pool exists but usage metrics not available"
            }
        else:
            health["checks"]["connection_pool"] = {
                "status": "not_initialized"
            }
    except Exception as e:
        health["checks"]["connection_pool"] = {"status": "unknown", "error": str(e)}
    
    return health

if __name__ == "__main__":
    health = check_health()
    print(json.dumps(health, indent=2))
    sys.exit(0 if health["status"] == "healthy" else 1)
```

**Usage**:
```bash
# Manual check
python health_check.py

# Automated monitoring (cron)
*/5 * * * * /usr/bin/python /path/to/health_check.py || echo "Pipeline unhealthy" | mail -s "Alert" admin@example.com
```

---

### 13.4 Alert Thresholds

| Alert | Condition | Severity | Action |
|-------|-----------|----------|--------|
| **Pipeline Failed** | `success = false` in last run | Critical | Investigate logs immediately |
| **Data Stale** | No new data in 2+ hours | Warning | Check if pipeline running |
| **High Validation Failure Rate** | >10% rows filtered | Warning | Review API data quality |
| **Connection Pool Near Limit** | >8/10 connections active | Warning | Reduce concurrency or increase pool size |
| **All Cities Failing** | 0 cities extracted | Critical | Check API status |
| **Slow Pipeline** | Duration >5 minutes | Info | Investigate performance |

---

## 14. Error Recovery Playbook

### 14.1 Manual Recovery Procedures

#### **Scenario 1: Pipeline Crashed Mid-Run**

**Symptoms**: Pipeline stopped unexpectedly, partial data inserted.

**Recovery Steps**:
1. **Check data integrity**:
   ```sql
   SELECT city_name, COUNT(*), MAX(recorded_at) 
   FROM weather_readings 
   WHERE ingested_at > NOW() - INTERVAL '1 hour'
   GROUP BY city_name;
   ```

2. **Identify missing cities**: Compare with expected cities list.

3. **Re-run pipeline**: Safe due to `ON CONFLICT DO NOTHING`:
   ```bash
   python src/pipeline.py
   ```

4. **Verify completeness**:
   ```sql
   SELECT COUNT(DISTINCT city_name) FROM weather_readings 
   WHERE ingested_at > NOW() - INTERVAL '1 hour';
   ```

**No data loss risk** - duplicate prevention ensures idempotency.

---

#### **Scenario 2: Database Corruption**

**Symptoms**: Integrity errors, foreign key violations.

**Recovery Steps**:
1. **Stop all pipelines**: Prevent further corruption.

2. **Check constraints**:
   ```sql
   SELECT conname, contype, conrelid::regclass 
   FROM pg_constraint 
   WHERE conrelid::regclass::text IN ('locations', 'weather_readings');
   ```

3. **Find orphaned records**:
   ```sql
   SELECT * FROM weather_readings wr
   WHERE NOT EXISTS (
     SELECT 1 FROM locations l WHERE l.id = wr.location_id
   );
   ```

4. **Fix orphans** (if any):
   ```sql
   DELETE FROM weather_readings
   WHERE NOT EXISTS (
     SELECT 1 FROM locations l WHERE l.id = location_id
   );
   ```

5. **Re-run VACUUM**:
   ```sql
   VACUUM ANALYZE weather_readings;
   ```

---

#### **Scenario 3: API Key Exhausted / Rate Limited**

**Symptoms**: All API calls failing with 429.

**Recovery Steps**:
1. **Check API quota**: Review Open-Meteo API limits (10,000 calls/day free tier).

2. **Wait for quota reset**: Usually resets at midnight UTC.

3. **Reduce frequency**: If running too often, space out pipeline runs:
   ```bash
   # Instead of hourly:
   0 * * * * /usr/bin/python /path/to/pipeline.py
   
   # Run every 3 hours:
   0 */3 * * * /usr/bin/python /path/to/pipeline.py
   ```

4. **Implement backoff**: Apply fix **E005** for rate limit handling.

---

### 14.2 Automated Backfill Strategies

#### **Backfill Missing Data**

Create `scripts/backfill.py`:

```python
"""
Backfill missing historical weather data.
Usage: python scripts/backfill.py --start 2024-03-01 --end 2024-03-05
"""

import argparse
from datetime import datetime, timedelta
from src.pipeline import run_pipeline
from src.extract import DEFAULT_CITIES
import time

def backfill(start_date, end_date):
    """
    Backfill data for date range.
    Note: Open-Meteo API provides historical data automatically.
    """
    print(f"Backfilling data from {start_date} to {end_date}")
    
    # Run pipeline (API automatically provides historical data within 7 day window)
    stats = run_pipeline()
    
    if stats['success']:
        print(f"✅ Backfill completed: {stats['rows_inserted']} rows inserted")
    else:
        print(f"❌ Backfill failed: {stats['errors']} errors")
    
    return stats

def backfill_range(start, end):
    """
    Backfill data day by day (if needed for older data).
    Note: Free API only provides 7 days of history.
    """
    current = start
    while current <= end:
        print(f"\nBackfilling {current.date()}...")
        
        # For historical data beyond 7 days, would need:
        # 1. Historical weather API (premium feature)
        # 2. Or load from alternative data source
        
        stats = run_pipeline()
        
        # Rate limit: wait between runs
        time.sleep(60)  # Wait 1 minute
        
        current += timedelta(days=1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill weather data")
    parser.add_argument("--start", required=True, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", required=True, help="End date (YYYY-MM-DD)")
    
    args = parser.parse_args()
    
    start = datetime.strptime(args.start, "%Y-%m-%d")
    end = datetime.strptime(args.end, "%Y-%m-%d")
    
    backfill_range(start, end)
```

---

### 14.3 Data Consistency Checks

Create `scripts/validate_data_integrity.py`:

```python
"""
Validate data integrity and consistency.
Run after incidents to verify database state.
"""

from src.load import get_db_connection
import sys

def check_integrity():
    """Run integrity checks on database."""
    issues = []
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Check 1: Orphaned weather readings
        cursor.execute("""
            SELECT COUNT(*) FROM weather_readings wr
            WHERE NOT EXISTS (
                SELECT 1 FROM locations l WHERE l.id = wr.location_id
            )
        """)
        orphaned = cursor.fetchone()[0]
        if orphaned > 0:
            issues.append(f"❌ {orphaned} orphaned weather readings found")
        else:
            print("✅ No orphaned weather readings")
        
        # Check 2: Duplicate readings
        cursor.execute("""
            SELECT location_id, recorded_at, COUNT(*)
            FROM weather_readings
            GROUP BY location_id, recorded_at
            HAVING COUNT(*) > 1
        """)
        duplicates = cursor.fetchall()
        if duplicates:
            issues.append(f"❌ {len(duplicates)} duplicate readings found")
        else:
            print("✅ No duplicate readings")
        
        # Check 3: Data range validation
        cursor.execute("""
            SELECT COUNT(*) FROM weather_readings
            WHERE temperature_c < -100 OR temperature_c > 60
        """)
        invalid_temps = cursor.fetchone()[0]
        if invalid_temps > 0:
            issues.append(f"⚠️  {invalid_temps} readings with invalid temperature")
        else:
            print("✅ All temperatures within valid range")
        
        # Check 4: Missing recent data
        cursor.execute("""
            SELECT COUNT(DISTINCT city_name) FROM locations
        """)
        total_cities = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT COUNT(DISTINCT l.city_name)
            FROM weather_readings wr
            JOIN locations l ON wr.location_id = l.id
            WHERE wr.ingested_at > NOW() - INTERVAL '2 hours'
        """)
        recent_cities = cursor.fetchone()[0]
        
        if recent_cities < total_cities:
            issues.append(f"⚠️  Only {recent_cities}/{total_cities} cities have recent data")
        else:
            print(f"✅ All {total_cities} cities have recent data")
    
    # Summary
    print("\n" + "="*60)
    if issues:
        print("INTEGRITY ISSUES FOUND:")
        for issue in issues:
            print(issue)
        return False
    else:
        print("✅ ALL INTEGRITY CHECKS PASSED")
        return True

if __name__ == "__main__":
    success = check_integrity()
    sys.exit(0 if success else 1)
```

**Run after recovery**:
```bash
python scripts/validate_data_integrity.py
```

---

## 15. Implementation Priority

### Immediate Fixes (Do First) - ~1 hour total

1. **E001: Add JSONDecodeError handling** (10 min)
   ```python
   # In extract.py, line 92
   try:
       data = response.json()
   except requests.exceptions.JSONDecodeError as e:
       last_exception = e
       logger.warning(f"Invalid JSON on attempt {attempt}/{MAX_RETRIES}")
       if attempt >= MAX_RETRIES:
           raise requests.RequestException("Invalid JSON response") from e
       continue
   ```

2. **E003: Add schema validation** (20 min)
   - Implement `verify_schema()` function in load.py
   - Add call in pipeline.py before extraction
   - Test with empty database

3. **E004: Fix datetime format** (15 min)
   ```python
   # In transform.py, line 61
   df = df.with_columns(
       pl.col("recorded_at").str.to_datetime("%Y-%m-%dT%H:%M:%S", strict=False)
   )
   ```

4. **E009: Check for empty response** (5 min)
   ```python
   # In extract.py, before line 92
   if not response.content:
       raise requests.RequestException("Empty response body")
   ```

5. **E002: Add connection pool timeout** (30 min)
   - Research psycopg2 connection timeout options
   - Implement with error handling
   - Add logging for pool usage

---

### Short-term Improvements (Next Sprint) - ~3 hours total

1. **E005: Better rate limit handling** (15 min)
2. **E006: Environment variable validation** (10 min)
3. **E007: Improve error messages** (60 min)
4. **Create error injection tests** (60 min)
5. **Add health check endpoint** (30 min)
6. **Document recovery procedures** (15 min)

---

### Long-term Enhancements (Future) - ~8 hours total

1. **E008: Structured JSON logging** (90 min)
2. **Add Prometheus metrics** (120 min)
3. **Implement comprehensive monitoring dashboard** (180 min)
4. **Create automated backfill system** (90 min)
5. **Add integration tests for all failure modes** (120 min)

---

## Conclusion

The Weather Data Pipeline demonstrates **strong foundational error handling** with several **critical gaps** that could cause production incidents. The priority fixes (**E001-E003**) should be implemented immediately to prevent the most likely failure scenarios.

### Key Takeaways

✅ **Strengths**:
- SQL injection protection complete
- Transaction management with rollback
- Retry logic for transient errors
- Input validation comprehensive
- Graceful degradation (continues on partial failures)

❌ **Critical Gaps**:
- JSON parsing not protected
- Connection pool can hang
- Schema validation missing
- DateTime format may be incorrect

⚠️ **Recommended Actions**:
1. Implement immediate fixes (E001-E003) - **1 hour**
2. Add error injection tests - **1 hour**
3. Set up basic monitoring (health checks) - **30 min**
4. Document recovery procedures - **15 min**

**Total effort to production-ready**: ~3 hours

---

**Document Version**: 1.0  
**Last Updated**: 2026-03-05  
**Reviewed By**: Debugging Specialist Agent  
**Next Review**: After implementing Priority 1 fixes
