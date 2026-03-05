# Weather Dashboard

Interactive Streamlit dashboard for visualizing weather data from PostgreSQL.

## Features

### 🌤️ Current Conditions
- Real-time weather metrics for selected cities
- Temperature, humidity, wind speed, and precipitation
- Weather condition labels and emojis (based on WMO codes)
- Last updated timestamps

### 📈 Historical Trends
- Temperature time-series charts (multi-city)
- Daily precipitation bar charts
- Hourly humidity area charts (single city)
- Raw data table with CSV export

### 🌍 City Comparison
- Side-by-side metric cards
- Average daily temperature comparison
- Temperature heatmap (city × date matrix)
- Interactive timestamp slider

## Quick Start

### Prerequisites
1. PostgreSQL database running with weather data
2. `.env` file with database credentials
3. Python 3.11+ with uv installed

### Launch Dashboard

```bash
uv run streamlit run dashboard/app.py
```

The dashboard will open in your browser at `http://localhost:8501`

## Configuration

Create a `.env` file in the project root:

```env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=weather_db
DB_USER=postgres
DB_PASSWORD=your_password_here
```

## Dashboard Controls

### Sidebar Filters (Global)
- **City Selector**: Multi-select dropdown (choose 1+ cities)
- **Date Range**: Start and end date pickers (defaults to last 7 days)
- **Temperature Unit**: Toggle between °C and °F

### Page Navigation
Use the radio buttons in the sidebar to switch between:
1. Current Conditions
2. Historical Trends  
3. City Comparison

## Technical Details

### Architecture
- **Backend**: PostgreSQL database (read-only queries)
- **Query Layer**: `queries.py` - all SQL queries return Polars DataFrames
- **Frontend**: Streamlit with Plotly for interactive charts
- **Caching**: 5-minute TTL on all queries for performance

### Key Technologies
- **Polars**: High-performance DataFrames (faster than pandas)
- **SQLAlchemy**: Database connection management
- **Plotly**: Interactive visualizations
- **Streamlit**: Web UI framework

### Caching Strategy
- `@st.cache_resource`: Database connection (shared, persistent)
- `@st.cache_data(ttl=300)`: Query results (5-minute refresh)

## WMO Weather Code Mapping

The dashboard displays human-readable weather conditions:

| Code Range | Condition |
|------------|-----------|
| 0 | Clear sky |
| 1-3 | Partly cloudy to overcast |
| 45-48 | Fog |
| 51-55 | Drizzle |
| 61-65 | Rain |
| 71-77 | Snow |
| 80-82 | Rain showers |
| 85-86 | Snow showers |
| 95-99 | Thunderstorm |

## File Structure

```
dashboard/
├── app.py          # Main Streamlit application
├── queries.py      # Database query functions
└── README.md       # This file
```

## Query Functions

All functions in `queries.py`:

- `get_available_cities()` - List all cities in database
- `get_latest_readings()` - Most recent reading per city
- `get_temperature_trend()` - Hourly temperature data
- `get_daily_precipitation()` - Daily precipitation totals
- `get_humidity_trend()` - Hourly humidity (single city)
- `get_city_comparison()` - Metrics at specific timestamp
- `get_filtered_records()` - Raw data table
- `get_daily_avg_temperature()` - Average daily temps

## Error Handling

The dashboard gracefully handles:
- Database connection failures (displays error message)
- Empty result sets (shows "No data" info messages)
- Missing cities (warning prompts)
- Invalid date ranges (Streamlit validation)

## Performance

- Query results cached for 5 minutes
- Database connection reused across queries
- Polars DataFrames for fast data processing
- Lazy loading (data fetched only when needed)

## Troubleshooting

### "Database connection failed"
- Check `.env` file exists and has correct credentials
- Verify PostgreSQL is running: `docker-compose ps`
- Test connection: `psql -h localhost -U postgres -d weather_db`

### "No cities found in database"
- Run the ETL pipeline first to populate data
- Check locations table: `SELECT * FROM locations;`

### Dashboard won't start
- Install dependencies: `uv sync`
- Check Python version: `python --version` (must be 3.11+)
- View Streamlit logs for detailed errors

## Development

### Running in development mode

```bash
# Enable auto-reload on file changes
uv run streamlit run dashboard/app.py --server.runOnSave true
```

### Clearing cache

If data appears stale, clear Streamlit's cache:
- Press `C` in the dashboard
- Or restart the server

## Future Enhancements

Potential additions:
- [ ] Forecasting charts (if forecast data added to DB)
- [ ] Weather alerts/notifications
- [ ] Map visualization with location markers
- [ ] Export to PDF reports
- [ ] User authentication
- [ ] Custom date range presets (last 24h, 30d, etc.)
- [ ] Mobile-responsive layout improvements

## License

Part of the Weather Data Pipeline project.
