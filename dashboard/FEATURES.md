# Weather Dashboard - Feature Guide

## 🚀 Quick Launch

```bash
# Ensure PostgreSQL is running
docker-compose up -d

# Launch the dashboard
uv run streamlit run dashboard/app.py
```

Open browser to: http://localhost:8501

---

## 📋 Complete Feature List

### Global Controls (Sidebar)

#### 1. City Selection
- **Type**: Multi-select dropdown
- **Purpose**: Choose one or more cities to visualize
- **Default**: First 3 cities (if available)
- **Behavior**: Filters all pages simultaneously

**How to use**:
1. Click the dropdown
2. Select/deselect cities
3. Changes apply immediately to all pages

#### 2. Date Range Picker
- **Type**: Two date inputs (start/end)
- **Purpose**: Filter historical data by date range
- **Default**: Last 7 days
- **Max**: Today's date
- **Behavior**: Affects trends and comparison pages only

**How to use**:
1. Click "Start" date → pick from calendar
2. Click "End" date → pick from calendar
3. Data refreshes automatically

#### 3. Temperature Unit Toggle
- **Type**: Radio button (°C / °F)
- **Purpose**: Display temperatures in Celsius or Fahrenheit
- **Default**: °C
- **Behavior**: Converts all temperature displays instantly

**How to use**:
- Click °C or °F radio button
- All temperature values update immediately

#### 4. Page Navigation
- **Type**: Radio button menu
- **Options**:
  - ☀️ Current Conditions
  - 📈 Historical Trends
  - 🌍 City Comparison

**How to use**:
- Click any page name to navigate
- Sidebar filters persist across pages

---

## 📄 Page 1: Current Conditions

### Purpose
Display the **latest weather reading** for each selected city.

### Features

#### Weather Metric Cards
Shows real-time data per city:
- **Temperature** (with selected unit)
- **Humidity** (percentage)
- **Wind Speed** (km/h)
- **Precipitation** (mm)

#### Weather Condition Badge
- **Weather emoji** (☀️, 🌧️, ⛈️, etc.)
- **Human-readable label** ("Clear sky", "Light rain", etc.)
- Based on WMO weather code (0-99)

#### Last Updated Timestamp
Shows when the reading was recorded.

### Layout
- **3-column grid** (desktop)
- **Stacked cards** (mobile)
- Auto-adjusts to number of selected cities

### Use Cases
- Check current weather at a glance
- Monitor real-time conditions across multiple cities
- Quick status overview before diving into trends

---

## 📄 Page 2: Historical Trends

### Purpose
Analyze weather patterns over time with interactive charts.

### Chart 1: Temperature Over Time

**Type**: Line chart (Plotly)

**Features**:
- Multi-city comparison (different colored lines)
- Hourly data points
- Hover tooltips with exact values
- Zoom/pan controls
- Unit-aware (°C or °F)

**X-axis**: Date & time (hourly)  
**Y-axis**: Temperature (selected unit)  
**Legend**: City names

**How to use**:
- Hover over line to see exact temperature
- Click legend to show/hide cities
- Drag to zoom, double-click to reset

### Chart 2: Daily Precipitation

**Type**: Grouped bar chart (Plotly)

**Features**:
- Total precipitation per day per city
- Bars grouped by date
- Color-coded by city
- Hover tooltips with exact mm

**X-axis**: Date (daily)  
**Y-axis**: Precipitation (mm)  
**Legend**: City names

**How to use**:
- Compare rainfall across cities
- Identify rainy periods
- Hover for exact values

### Chart 3: Humidity Trend

**Type**: Area chart (Plotly)

**Features**:
- Single-city analysis
- Hourly humidity readings
- Filled area under curve
- Y-axis fixed at 0-100%

**City selector**: Dropdown to choose which city to analyze

**X-axis**: Date & time (hourly)  
**Y-axis**: Humidity (%)

**How to use**:
1. Select a city from dropdown
2. View humidity patterns over time
3. Identify high/low humidity periods

### Chart 4: Raw Data Table

**Type**: Interactive data table

**Features**:
- All weather readings for selected cities/dates
- Sortable columns (click header)
- Scrollable (up to 1000 rows visible)
- Full data export available

**Columns**:
- city_name
- country_code
- recorded_at
- temperature_c, temperature_f
- humidity_pct
- wind_speed_kmh
- precipitation_mm
- weather_code
- ingested_at

**CSV Download**:
- Button below table: "📥 Download CSV"
- Filename format: `weather_data_YYYY-MM-DD_YYYY-MM-DD.csv`
- Contains ALL filtered records (not just visible 1000)

**How to use**:
1. Scroll through table to inspect data
2. Click column headers to sort
3. Click "Download CSV" for external analysis (Excel, Python, etc.)

---

## 📄 Page 3: City Comparison

### Purpose
Compare weather across multiple cities at specific times.

### Feature 1: Timestamp Slider

**Type**: Interactive slider

**Purpose**: Select a specific point in time for comparison

**Range**: Start date 00:00 to End date 23:59  
**Default**: End date at 12:00 PM

**How to use**:
1. Drag slider to select time
2. Cards below update to show closest readings
3. Time displayed in format: YYYY-MM-DD HH:MM

### Feature 2: Side-by-Side Metric Cards

**Type**: Column layout with metric cards

**Shows**:
- Temperature (selected unit)
- Humidity (%)
- Wind speed (km/h)
- Weather condition label + emoji

**Purpose**: Instant visual comparison at selected timestamp

**How to use**:
- Adjust timestamp slider
- Cards update to show data at that time
- Compare values across cities side-by-side

### Feature 3: Average Daily Temperature Chart

**Type**: Grouped bar chart (Plotly)

**Features**:
- Average temperature per day per city
- Bars grouped by date
- Color-coded by city
- Unit-aware (°C or °F)

**X-axis**: Date (daily)  
**Y-axis**: Average Temperature  
**Legend**: City names

**How to use**:
- Identify warmest/coldest cities
- Compare daily averages over time
- Hover for exact average values

### Feature 4: Temperature Heatmap

**Type**: 2D heatmap (Plotly)

**Features**:
- Rows: Cities
- Columns: Dates
- Color intensity: Temperature
- Color scale: Red (hot) → Yellow → Blue (cold)

**Purpose**: Spot temperature patterns at a glance

**How to use**:
- Look for color patterns (hot/cold periods)
- Hover over cells for exact temperature
- Compare temperature distributions across cities

---

## 🎯 Common Workflows

### Workflow 1: Check Current Weather
1. Navigate to "Current Conditions"
2. Select cities of interest
3. View metric cards with latest data
4. Check weather emojis for quick status

### Workflow 2: Analyze Temperature Trends
1. Navigate to "Historical Trends"
2. Select cities and date range (e.g., last 30 days)
3. View line chart for temperature patterns
4. Identify peaks, valleys, and trends

### Workflow 3: Compare Cities
1. Navigate to "City Comparison"
2. Select 2+ cities
3. Adjust timestamp slider to specific time
4. View side-by-side metrics
5. Scroll down for daily average chart

### Workflow 4: Export Data for Analysis
1. Navigate to "Historical Trends"
2. Set desired date range
3. Scroll to "Raw Data" section
4. Click "📥 Download CSV"
5. Open in Excel/Python for custom analysis

### Workflow 5: Monitor Precipitation
1. Navigate to "Historical Trends"
2. Select cities and recent date range (e.g., last 7 days)
3. View "Daily Precipitation" bar chart
4. Identify rainy days and totals

---

## 🎨 UI Tips

### Chart Interactions (Plotly)

**Hover**: View exact values  
**Click legend**: Show/hide series  
**Drag**: Zoom into region  
**Double-click**: Reset zoom  
**Pan**: Hold shift + drag  
**Download**: Camera icon (top-right of chart) → save as PNG

### Responsive Design

**Desktop (>1200px)**: 3-column layout, full-width charts  
**Tablet (768-1200px)**: 2-column layout  
**Mobile (<768px)**: Stacked single-column

### Performance Tips

- **First load**: 1-2 seconds (queries database)
- **Subsequent loads**: <100ms (cached)
- **Cache refresh**: Every 5 minutes automatically
- **Manual refresh**: Press `R` or `C` in dashboard

### Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `C` | Clear cache and refresh |
| `R` | Rerun dashboard |
| `S` | Toggle sidebar (hide/show) |
| `Ctrl+C` | Stop server (in terminal) |

---

## 🔍 Data Details

### WMO Weather Code Reference

| Code | Condition | Emoji |
|------|-----------|-------|
| 0 | Clear sky | ☀️ |
| 1 | Mainly clear | ⛅ |
| 2 | Partly cloudy | ⛅ |
| 3 | Overcast | ⛅ |
| 45-48 | Fog | 🌫️ |
| 51-55 | Drizzle | 🌦️ |
| 61-65 | Rain | 🌧️ |
| 71-77 | Snow | ❄️ |
| 80-82 | Rain showers | 🌧️ |
| 85-86 | Snow showers | 🌨️ |
| 95-99 | Thunderstorm | ⛈️ |

### Temperature Units

**Celsius (°C)**:
- Used in most countries worldwide
- Water freezes at 0°C, boils at 100°C

**Fahrenheit (°F)**:
- Used primarily in the United States
- Water freezes at 32°F, boils at 212°F

**Conversion**: F = (C × 9/5) + 32

### Humidity Percentage

- **0-30%**: Very dry
- **30-50%**: Comfortable
- **50-70%**: Moderate
- **70-100%**: High (humid)

### Wind Speed (km/h)

- **0-10**: Calm
- **10-30**: Light breeze
- **30-50**: Moderate wind
- **50+**: Strong wind

---

## ⚙️ Advanced Features

### Cache Management

**Automatic**:
- Query results cached for 5 minutes
- Database connection cached for session

**Manual**:
- Press `C` to clear cache immediately
- Useful after ETL pipeline updates database

### Custom Date Ranges

**Presets** (via date picker):
- Last 7 days (default)
- Last 30 days
- Custom range (any dates)

**Tips**:
- Larger ranges = more data = slower queries
- Keep ranges reasonable (< 90 days) for performance

### Multi-City Comparison

**Optimal**: 2-5 cities  
**Maximum**: No hard limit (but charts get crowded)

**Tips**:
- Too many cities make charts hard to read
- Use comparison page for side-by-side analysis
- Filter to specific cities of interest

---

## 🐛 Troubleshooting

### "Database connection failed"

**Causes**:
- PostgreSQL not running
- Wrong credentials in `.env`
- Network issue

**Solutions**:
1. Check Docker: `docker-compose ps`
2. Verify `.env` file exists and has correct values
3. Test connection: `psql -h localhost -U postgres -d weather_db`

### "No cities found in database"

**Cause**: Database is empty

**Solution**:
1. Run ETL pipeline: `uv run python src/pipeline.py`
2. Verify data: `psql -d weather_db -c "SELECT * FROM locations;"`
3. Refresh dashboard (press `R`)

### "No data available"

**Causes**:
- Selected date range has no data
- Cities exist but no readings yet

**Solutions**:
1. Adjust date range to recent dates
2. Check if ETL pipeline ran successfully
3. Query database directly to verify data exists

### Charts not displaying

**Causes**:
- JavaScript disabled
- Browser compatibility issue
- Data format error

**Solutions**:
1. Refresh page (F5)
2. Clear browser cache
3. Try different browser (Chrome recommended)
4. Check browser console for errors

### Slow performance

**Causes**:
- Large date range selected
- Many cities selected
- Cache expired

**Solutions**:
1. Reduce date range (e.g., 7 days instead of 90)
2. Select fewer cities
3. Wait for cache to populate (first load is slower)

---

## 📚 Additional Resources

- **Dashboard README**: `dashboard/README.md` (technical details)
- **Architecture Guide**: `dashboard/ARCHITECTURE.md` (system design)
- **Quick Start**: `dashboard/QUICKSTART.md` (setup guide)
- **Implementation**: `dashboard/IMPLEMENTATION_SUMMARY.md` (dev notes)

---

## 🎓 Learning Path

### Beginner
1. Launch dashboard
2. Explore Current Conditions page
3. Select different cities
4. Try temperature unit toggle

### Intermediate
1. Navigate to Historical Trends
2. Adjust date range
3. Analyze temperature patterns
4. Download CSV for Excel analysis

### Advanced
1. Use City Comparison page
2. Adjust timestamp slider for point-in-time comparison
3. Interpret heatmap patterns
4. Combine insights across all three pages

---

**Dashboard Version**: 1.0.0  
**Last Updated**: March 5, 2026  
**Compatible with**: PostgreSQL 14+, Python 3.11+, Streamlit 1.35+
