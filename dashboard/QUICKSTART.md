# Dashboard Quick Start Guide

## Launch the Dashboard

```bash
# From project root
uv run streamlit run dashboard/app.py
```

The dashboard will automatically open in your browser at `http://localhost:8501`

## First Time Setup

1. **Ensure PostgreSQL is running**:
   ```bash
   docker-compose up -d
   ```

2. **Run the ETL pipeline to populate data**:
   ```bash
   uv run python src/pipeline.py
   ```

3. **Verify your `.env` file** has database credentials:
   ```env
   DB_HOST=localhost
   DB_PORT=5432
   DB_NAME=weather_db
   DB_USER=postgres
   DB_PASSWORD=your_password_here
   ```

4. **Launch the dashboard** (see command above)

## Dashboard Overview

### Three Main Pages

1. **☀️ Current Conditions**
   - Live weather metrics for each selected city
   - Temperature, humidity, wind speed, precipitation
   - Weather condition badges with emojis

2. **📈 Historical Trends**
   - Temperature line charts (multi-city)
   - Daily precipitation bar charts
   - Hourly humidity area chart
   - Raw data table with CSV download

3. **🌍 City Comparison**
   - Side-by-side comparison at specific timestamps
   - Average daily temperature charts
   - Temperature heatmap visualization

### Global Controls (Sidebar)

- **City Selector**: Choose one or more cities to visualize
- **Date Range**: Select start and end dates (default: last 7 days)
- **Temperature Unit**: Toggle between °C and °F

## Features

✅ **Real-time data** with 5-minute cache refresh  
✅ **Interactive charts** powered by Plotly  
✅ **Responsive design** works on desktop and mobile  
✅ **Fast queries** using Polars DataFrames  
✅ **CSV export** for raw data analysis  
✅ **Smart caching** for optimal performance  

## Keyboard Shortcuts

- `C` - Clear cache and refresh data
- `R` - Rerun the app
- `Ctrl+C` (terminal) - Stop the server

## Common Issues

**"Database connection failed"**
→ Check `.env` file and verify PostgreSQL is running

**"No cities found in database"**  
→ Run the ETL pipeline first to populate data

**Stale data displayed**  
→ Press `C` to clear cache or wait for 5-minute auto-refresh

## Architecture

```
dashboard/
├── app.py          # Main Streamlit application (UI logic)
├── queries.py      # Database query functions (data layer)
├── __init__.py     # Package initialization
└── README.md       # Detailed documentation
```

## Performance Notes

- All queries are cached for 5 minutes
- Database connection is shared across queries
- Polars provides 2-3x faster data processing than pandas
- Charts render client-side (no server overhead)

## Next Steps

- Explore different date ranges to see historical patterns
- Compare weather across multiple cities
- Download CSV data for external analysis
- Customize visualizations using Plotly's interactive features

For detailed documentation, see `dashboard/README.md`
