# Dashboard Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        User Browser                              │
│                     (localhost:8501)                             │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             │ HTTP
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Streamlit Server                              │
│                    (dashboard/app.py)                            │
│                                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   Current    │  │  Historical  │  │     City     │          │
│  │  Conditions  │  │    Trends    │  │  Comparison  │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│         │                  │                  │                  │
│         └──────────────────┴──────────────────┘                  │
│                             │                                     │
│                             ▼                                     │
│                  ┌─────────────────────┐                         │
│                  │   Query Functions   │                         │
│                  │  (queries.py)       │                         │
│                  │                     │                         │
│                  │ • get_latest_...    │                         │
│                  │ • get_temperature...│                         │
│                  │ • get_humidity_...  │                         │
│                  │ • get_city_comp...  │                         │
│                  └─────────────────────┘                         │
│                             │                                     │
│                             ▼                                     │
│                  ┌─────────────────────┐                         │
│                  │   Cache Layer       │                         │
│                  │   (5-min TTL)       │                         │
│                  └─────────────────────┘                         │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             │ SQLAlchemy
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                     PostgreSQL Database                          │
│                        (weather_db)                              │
│                                                                   │
│  ┌──────────────────┐         ┌─────────────────────────┐       │
│  │    locations     │◄───────┤   weather_readings      │       │
│  ├──────────────────┤         ├─────────────────────────┤       │
│  │ id (PK)          │         │ id (PK)                 │       │
│  │ city_name        │         │ location_id (FK)        │       │
│  │ country_code     │         │ recorded_at             │       │
│  │ latitude         │         │ temperature_c           │       │
│  │ longitude        │         │ temperature_f           │       │
│  └──────────────────┘         │ humidity_pct            │       │
│                                │ wind_speed_kmh          │       │
│                                │ precipitation_mm        │       │
│                                │ weather_code            │       │
│                                │ ingested_at             │       │
│                                └─────────────────────────┘       │
└─────────────────────────────────────────────────────────────────┘
```

## Data Flow

### 1. Initial Page Load

```
User selects cities + date range
        ↓
Sidebar filters applied
        ↓
Query functions called with parameters
        ↓
Check cache (5-min TTL)
        ↓
Cache miss → Execute SQL query
        ↓
PostgreSQL returns results
        ↓
Convert to Polars DataFrame
        ↓
Store in cache
        ↓
Render UI components (charts, metrics)
        ↓
Display to user
```

### 2. Subsequent Interactions

```
User changes filters (city/date/unit)
        ↓
Query functions called with NEW parameters
        ↓
Check cache (different key)
        ↓
Cache miss/hit determines SQL execution
        ↓
Render updated UI
```

### 3. Cache Refresh (After 5 Minutes)

```
User stays on page > 5 minutes
        ↓
Cache TTL expires
        ↓
Next interaction triggers cache miss
        ↓
Fresh SQL query executed
        ↓
New data displayed
```

## Component Responsibilities

### `app.py` (UI Layer)
- Renders pages and components
- Handles user interactions
- Manages global state (filters)
- Converts data for visualization
- Error handling and loading states

**Key Functions**:
- `render_sidebar()` - Global filter controls
- `render_current_conditions()` - Page 1
- `render_historical_trends()` - Page 2
- `render_city_comparison()` - Page 3
- `get_weather_label()` - WMO code mapping
- `get_db_connection()` - Connection management

### `queries.py` (Data Layer)
- All SQL query logic
- Database connection handling
- Result caching
- Polars DataFrame conversion

**Query Functions** (all cached 5 min):
- `get_available_cities()` - City list
- `get_latest_readings()` - Current conditions
- `get_temperature_trend()` - Time-series data
- `get_daily_precipitation()` - Aggregated daily data
- `get_humidity_trend()` - Single-city humidity
- `get_city_comparison()` - Point-in-time comparison
- `get_filtered_records()` - Raw data export
- `get_daily_avg_temperature()` - Comparison charts

## Caching Strategy

### Connection Cache (`@st.cache_resource`)
```python
@st.cache_resource
def get_db_connection() -> Connection:
    # Creates connection ONCE
    # Shared across all queries
    # Persists for session lifetime
```

**Why?** Avoid reconnection overhead on every query.

### Query Cache (`@st.cache_data(ttl=300)`)
```python
@st.cache_data(ttl=300)
def get_temperature_trend(_conn, cities, start, end):
    # Cached for 5 minutes
    # Separate cache key per unique parameter combo
    # Auto-refresh after TTL
```

**Why?** Balance data freshness with query performance.

## Query Optimization

### Index Usage
- `idx_readings_location_time` - Location + time queries
- `idx_readings_time` - Time-range scans
- `idx_locations_coordinates` - Geospatial (future)

### Query Patterns
- **Latest readings**: `MAX(recorded_at)` with window function
- **Time-series**: `BETWEEN :start AND :end` on indexed column
- **Aggregations**: `GROUP BY DATE(recorded_at)` for daily data
- **Multi-city**: `city_name = ANY(:cities)` for efficient filtering

### Performance Tips
- Date filtering at SQL level (not Python)
- Use composite indexes (location + time)
- Limit result sets with date ranges
- Polars for fast data transformations

## UI Components

### Sidebar (Always Visible)
```
┌─────────────────────┐
│ 🌤️ Weather Dashboard│
├─────────────────────┤
│ Select Cities       │
│ [x] London          │
│ [x] Paris           │
│ [ ] Tokyo           │
├─────────────────────┤
│ Date Range          │
│ Start: 2024-02-28   │
│ End:   2024-03-05   │
├─────────────────────┤
│ Temperature Unit    │
│ (•) °C  ( ) °F      │
├─────────────────────┤
│ Navigate            │
│ • Current Conditions│
│ • Historical Trends │
│ • City Comparison   │
└─────────────────────┘
```

### Page 1: Current Conditions
```
┌───────────────────────────────────────────────┐
│ ☀️ Current Weather Conditions                 │
├───────────────┬───────────────┬───────────────┤
│ ☀️ London, GB │ ⛅ Paris, FR  │ 🌧️ Tokyo, JP  │
│ Clear sky     │ Partly cloudy │ Light rain    │
│               │               │               │
│ 🌡️ 15.5°C     │ 🌡️ 12.3°C    │ 🌡️ 8.7°C     │
│ 💧 65%        │ 💧 72%        │ 💧 88%        │
│ 💨 12 km/h    │ 💨 8 km/h     │ 💨 15 km/h    │
│ 🌧️ 0.0 mm    │ 🌧️ 0.0 mm    │ 🌧️ 2.5 mm    │
└───────────────┴───────────────┴───────────────┘
```

### Page 2: Historical Trends
```
┌─────────────────────────────────────────────────┐
│ 📈 Historical Trends                             │
├─────────────────────────────────────────────────┤
│ 🌡️ Temperature Over Time                        │
│ ┌─────────────────────────────────────────────┐ │
│ │          [Interactive Line Chart]            │ │
│ └─────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────┤
│ 🌧️ Daily Precipitation                          │
│ ┌─────────────────────────────────────────────┐ │
│ │          [Grouped Bar Chart]                 │ │
│ └─────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────┤
│ 💧 Humidity Trend for [London ▼]                │
│ ┌─────────────────────────────────────────────┐ │
│ │          [Area Chart]                        │ │
│ └─────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────┤
│ 📋 Raw Data                                      │
│ [Data table with 1000 rows × 10 columns]        │
│ [📥 Download CSV]                                │
└─────────────────────────────────────────────────┘
```

### Page 3: City Comparison
```
┌─────────────────────────────────────────────────┐
│ 🌍 City Comparison                               │
├─────────────────────────────────────────────────┤
│ 📅 Select Comparison Time                        │
│ [═════════●══════] 2024-03-05 12:00             │
├─────────────────────────────────────────────────┤
│ 🏙️ Side-by-Side Metrics                         │
│ ┌──────────┬──────────┬──────────┐              │
│ │  London  │  Paris   │  Tokyo   │              │
│ │  15.5°C  │  12.3°C  │  8.7°C   │              │
│ └──────────┴──────────┴──────────┘              │
├─────────────────────────────────────────────────┤
│ 📊 Average Daily Temperature Comparison          │
│ ┌─────────────────────────────────────────────┐ │
│ │          [Grouped Bar Chart]                 │ │
│ └─────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────┤
│ 🗺️ Temperature Heatmap                          │
│ ┌─────────────────────────────────────────────┐ │
│ │          [City × Date Heatmap]               │ │
│ └─────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────┘
```

## Error Handling Flow

```
Try to get DB connection
    ↓
  Success? → Continue
    ↓ No
Display error message
    ↓
Show troubleshooting tips
    ↓
Stop rendering
```

```
Execute query
    ↓
  Results empty? → Show "No data" message
    ↓ No (has data)
Check if cities selected
    ↓
  None selected? → Show warning
    ↓ No (has cities)
Render visualizations
```

## State Management

Streamlit manages state automatically:
- Sidebar selections persist across page changes
- Cache keys include all parameters (automatic)
- Session state available for custom needs

## Deployment Considerations

### Local Development
```bash
uv run streamlit run dashboard/app.py
```

### Production (Docker)
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
CMD ["streamlit", "run", "dashboard/app.py", "--server.port=8501"]
```

### Environment Variables
```env
DB_HOST=postgres_container
DB_PORT=5432
DB_NAME=weather_db
DB_USER=postgres
DB_PASSWORD=secure_password
```

## Security Notes

- Dashboard is **read-only** (only SELECT queries)
- Parameterized queries prevent SQL injection
- No user authentication (add if needed)
- Database credentials in `.env` (not committed)
- Connection pooling for multi-user scalability

## Monitoring

Track these metrics:
- **Query execution time** (log slow queries)
- **Cache hit rate** (should be >80% after warmup)
- **Concurrent users** (Streamlit handles well up to ~100)
- **Database connection pool** (ensure enough connections)

---

**Last Updated**: March 5, 2026
