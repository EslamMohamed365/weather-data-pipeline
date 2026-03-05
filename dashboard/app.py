"""
Interactive Streamlit dashboard for visualizing weather data from PostgreSQL.
Provides current conditions, historical trends, and city comparisons.
"""

import os
from datetime import datetime, timedelta
from typing import Any

import polars as pl
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import Connection

from queries import (
    get_available_cities,
    get_city_comparison,
    get_daily_avg_temperature,
    get_daily_precipitation,
    get_filtered_records,
    get_humidity_trend,
    get_latest_readings,
    get_temperature_trend,
)

# Load environment variables
load_dotenv()

# Page configuration
st.set_page_config(
    page_title="Weather Dashboard",
    page_icon="🌤️",
    layout="wide",
    initial_sidebar_state="expanded",
)


# =====================================================
# UTILITY FUNCTIONS
# =====================================================


def get_weather_label(weather_code: int | None) -> str:
    """
    Map WMO weather code to human-readable label.

    Args:
        weather_code: WMO weather interpretation code (0-99)

    Returns:
        Human-readable weather condition label
    """
    if weather_code is None:
        return "Unknown"

    weather_map = {
        0: "Clear sky",
        1: "Mainly clear",
        2: "Partly cloudy",
        3: "Overcast",
        45: "Fog",
        48: "Depositing rime fog",
        51: "Light drizzle",
        53: "Moderate drizzle",
        55: "Dense drizzle",
        61: "Slight rain",
        63: "Moderate rain",
        65: "Heavy rain",
        71: "Slight snow",
        73: "Moderate snow",
        75: "Heavy snow",
        77: "Snow grains",
        80: "Slight rain showers",
        81: "Moderate rain showers",
        82: "Violent rain showers",
        85: "Slight snow showers",
        86: "Heavy snow showers",
        95: "Thunderstorm",
        96: "Thunderstorm with slight hail",
        99: "Thunderstorm with heavy hail",
    }

    return weather_map.get(weather_code, f"Code {weather_code}")


def get_weather_emoji(weather_code: int | None) -> str:
    """
    Get emoji representation for weather code.

    Args:
        weather_code: WMO weather interpretation code

    Returns:
        Weather emoji
    """
    if weather_code is None:
        return "❓"

    if weather_code == 0:
        return "☀️"
    elif weather_code in [1, 2, 3]:
        return "⛅"
    elif weather_code in [45, 48]:
        return "🌫️"
    elif weather_code in [51, 53, 55]:
        return "🌦️"
    elif weather_code in [61, 63, 65]:
        return "🌧️"
    elif weather_code in [71, 73, 75, 77]:
        return "❄️"
    elif weather_code in [80, 81, 82]:
        return "🌧️"
    elif weather_code in [85, 86]:
        return "🌨️"
    elif weather_code in [95, 96, 99]:
        return "⛈️"
    else:
        return "🌤️"


@st.cache_resource
def get_db_connection() -> Connection:
    """
    Create and cache database connection.

    Returns:
        SQLAlchemy connection object
    """
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = os.getenv("DB_PORT", "5432")
    db_name = os.getenv("DB_NAME", "weather_db")
    db_user = os.getenv("DB_USER", "postgres")
    db_password = os.getenv("DB_PASSWORD", "")

    connection_string = (
        f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    )

    engine = create_engine(connection_string)
    return engine.connect()


def convert_temperature(df: pl.DataFrame, unit: str, temp_col: str) -> pl.DataFrame:
    """
    Select appropriate temperature column based on unit preference.

    Args:
        df: Polars DataFrame
        unit: Temperature unit ("°C" or "°F")
        temp_col: Base column name (without unit suffix)

    Returns:
        DataFrame with temperature column renamed
    """
    if df.is_empty():
        return df

    if unit == "°C":
        if f"{temp_col}_c" in df.columns:
            return df.rename({f"{temp_col}_c": temp_col})
    else:
        if f"{temp_col}_f" in df.columns:
            return df.rename({f"{temp_col}_f": temp_col})

    return df


# =====================================================
# SIDEBAR - GLOBAL CONTROLS
# =====================================================


def render_sidebar(conn: Connection) -> dict[str, Any]:
    """
    Render sidebar with global filter controls.

    Args:
        conn: Database connection

    Returns:
        Dictionary with selected filters
    """
    st.sidebar.title("🌤️ Weather Dashboard")
    st.sidebar.markdown("---")

    # Fetch available cities
    with st.spinner("Loading cities..."):
        cities = get_available_cities(conn)

    if not cities:
        st.sidebar.error("No cities found in database!")
        return {
            "cities": [],
            "start_date": datetime.now().date() - timedelta(days=7),
            "end_date": datetime.now().date(),
            "temp_unit": "°C",
        }

    # City selector
    selected_cities = st.sidebar.multiselect(
        "Select Cities",
        options=cities,
        default=cities[:3] if len(cities) >= 3 else cities,
        help="Choose one or more cities to visualize",
    )

    # Date range picker
    st.sidebar.markdown("### Date Range")
    col1, col2 = st.sidebar.columns(2)

    default_start = datetime.now().date() - timedelta(days=7)
    default_end = datetime.now().date()

    start_date = col1.date_input(
        "Start",
        value=default_start,
        max_value=datetime.now().date(),
    )

    end_date = col2.date_input(
        "End",
        value=default_end,
        max_value=datetime.now().date(),
    )

    # Temperature unit toggle
    st.sidebar.markdown("### Temperature Unit")
    temp_unit = st.sidebar.radio(
        "Select unit",
        options=["°C", "°F"],
        index=0,
        horizontal=True,
    )

    st.sidebar.markdown("---")
    st.sidebar.info(
        "📊 Data refreshes every 5 minutes\n\n🔄 Use filters to customize your view"
    )

    return {
        "cities": selected_cities,
        "start_date": start_date,
        "end_date": end_date,
        "temp_unit": temp_unit,
    }


# =====================================================
# PAGE 1 - CURRENT CONDITIONS
# =====================================================


def render_current_conditions(conn: Connection, filters: dict[str, Any]) -> None:
    """
    Render current weather conditions page.

    Args:
        conn: Database connection
        filters: Global filters from sidebar
    """
    st.title("☀️ Current Weather Conditions")

    cities = filters["cities"]
    temp_unit = filters["temp_unit"]

    if not cities:
        st.warning("Please select at least one city from the sidebar.")
        return

    # Fetch latest readings
    with st.spinner("Loading current conditions..."):
        df = get_latest_readings(conn, cities)

    if df.is_empty():
        st.error("No weather data available for selected cities.")
        return

    # Display metrics for each city
    for i in range(0, len(df), 3):
        cols = st.columns(3)

        for j, col in enumerate(cols):
            if i + j >= len(df):
                break

            row = df[i + j]
            city = row["city_name"][0]
            country = row["country_code"][0]
            recorded_at = row["recorded_at"][0]
            weather_code = row["weather_code"][0]

            # Temperature
            if temp_unit == "°C":
                temp = row["temperature_c"][0]
            else:
                temp = row["temperature_f"][0]

            humidity = row["humidity_pct"][0]
            wind = row["wind_speed_kmh"][0]
            precip = row["precipitation_mm"][0]

            with col:
                st.markdown(f"### {get_weather_emoji(weather_code)} {city}, {country}")
                st.markdown(f"**{get_weather_label(weather_code)}**")

                # Metric cards
                metric_cols = st.columns(2)
                metric_cols[0].metric(
                    "Temperature",
                    f"{temp:.1f}{temp_unit}" if temp is not None else "N/A",
                )
                metric_cols[1].metric(
                    "Humidity", f"{humidity:.0f}%" if humidity is not None else "N/A"
                )

                metric_cols = st.columns(2)
                metric_cols[0].metric(
                    "Wind Speed", f"{wind:.1f} km/h" if wind is not None else "N/A"
                )
                metric_cols[1].metric(
                    "Precipitation", f"{precip:.1f} mm" if precip is not None else "N/A"
                )

                # Timestamp
                st.caption(f"📅 Last updated: {recorded_at}")
                st.markdown("---")


# =====================================================
# PAGE 2 - HISTORICAL TRENDS
# =====================================================


def render_historical_trends(conn: Connection, filters: dict[str, Any]) -> None:
    """
    Render historical trends page with time-series visualizations.

    Args:
        conn: Database connection
        filters: Global filters from sidebar
    """
    st.title("📈 Historical Trends")

    cities = filters["cities"]
    start_date = filters["start_date"]
    end_date = filters["end_date"]
    temp_unit = filters["temp_unit"]

    if not cities:
        st.warning("Please select at least one city from the sidebar.")
        return

    # Temperature trend
    st.subheader("🌡️ Temperature Over Time")
    with st.spinner("Loading temperature data..."):
        temp_df = get_temperature_trend(conn, cities, start_date, end_date)

    if not temp_df.is_empty():
        # Select appropriate temperature column
        temp_col = "temperature_c" if temp_unit == "°C" else "temperature_f"

        # Convert to pandas for plotly
        temp_pd = temp_df.to_pandas()

        fig = px.line(
            temp_pd,
            x="recorded_at",
            y=temp_col,
            color="city_name",
            title=f"Temperature Trends ({temp_unit})",
            labels={
                temp_col: f"Temperature ({temp_unit})",
                "recorded_at": "Date & Time",
                "city_name": "City",
            },
            height=400,
        )

        fig.update_layout(
            xaxis_title="Date & Time",
            yaxis_title=f"Temperature ({temp_unit})",
            hovermode="x unified",
        )

        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No temperature data available for the selected period.")

    # Precipitation chart
    st.subheader("🌧️ Daily Precipitation")
    with st.spinner("Loading precipitation data..."):
        precip_df = get_daily_precipitation(conn, cities, start_date, end_date)

    if not precip_df.is_empty():
        precip_pd = precip_df.to_pandas()

        fig = px.bar(
            precip_pd,
            x="date",
            y="total_precipitation_mm",
            color="city_name",
            title="Total Daily Precipitation (mm)",
            labels={
                "total_precipitation_mm": "Precipitation (mm)",
                "date": "Date",
                "city_name": "City",
            },
            height=400,
            barmode="group",
        )

        fig.update_layout(
            xaxis_title="Date",
            yaxis_title="Precipitation (mm)",
        )

        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No precipitation data available for the selected period.")

    # Humidity trend for single city
    if len(cities) > 0:
        st.subheader("💧 Humidity Trend")

        selected_city = st.selectbox(
            "Select a city for humidity analysis", options=cities, key="humidity_city"
        )

        with st.spinner("Loading humidity data..."):
            humidity_df = get_humidity_trend(conn, selected_city, start_date, end_date)

        if not humidity_df.is_empty():
            humidity_pd = humidity_df.to_pandas()

            fig = px.area(
                humidity_pd,
                x="recorded_at",
                y="humidity_pct",
                title=f"Humidity Trend for {selected_city} (%)",
                labels={"humidity_pct": "Humidity (%)", "recorded_at": "Date & Time"},
                height=400,
            )

            fig.update_layout(
                xaxis_title="Date & Time",
                yaxis_title="Humidity (%)",
                yaxis_range=[0, 100],
            )

            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info(f"No humidity data available for {selected_city}.")

    # Raw data table
    st.subheader("📋 Raw Data")
    with st.spinner("Loading records..."):
        raw_df = get_filtered_records(conn, cities, start_date, end_date)

    if not raw_df.is_empty():
        st.dataframe(
            raw_df,
            use_container_width=True,
            height=400,
        )

        # Download button
        csv = raw_df.write_csv()
        st.download_button(
            label="📥 Download CSV",
            data=csv,
            file_name=f"weather_data_{start_date}_{end_date}.csv",
            mime="text/csv",
        )
    else:
        st.info("No records found for the selected criteria.")


# =====================================================
# PAGE 3 - CITY COMPARISON
# =====================================================


def render_city_comparison(conn: Connection, filters: dict[str, Any]) -> None:
    """
    Render city comparison page with side-by-side metrics.

    Args:
        conn: Database connection
        filters: Global filters from sidebar
    """
    st.title("🌍 City Comparison")

    cities = filters["cities"]
    start_date = filters["start_date"]
    end_date = filters["end_date"]
    temp_unit = filters["temp_unit"]

    if len(cities) < 2:
        st.warning("Please select at least two cities from the sidebar to compare.")
        return

    # Timestamp selector for comparison
    st.subheader("📅 Select Comparison Time")
    comparison_time = st.slider(
        "Choose a time point",
        min_value=datetime.combine(start_date, datetime.min.time()),
        max_value=datetime.combine(end_date, datetime.max.time()),
        value=datetime.combine(end_date, datetime.min.time()) + timedelta(hours=12),
        format="YYYY-MM-DD HH:mm",
    )

    # Fetch comparison data
    with st.spinner("Loading comparison data..."):
        comp_df = get_city_comparison(conn, cities, comparison_time)

    if not comp_df.is_empty():
        st.markdown("### 🏙️ Side-by-Side Metrics")

        # Display metric cards
        cols = st.columns(len(cities))

        for i, city in enumerate(cities):
            city_data = comp_df.filter(pl.col("city_name") == city)

            if city_data.is_empty():
                with cols[i]:
                    st.warning(f"No data for {city}")
                continue

            row = city_data[0]

            # Temperature
            if temp_unit == "°C":
                temp = row["temperature_c"][0]
            else:
                temp = row["temperature_f"][0]

            humidity = row["humidity_pct"][0]
            wind = row["wind_speed_kmh"][0]
            weather_code = row["weather_code"][0]

            with cols[i]:
                st.markdown(f"### {get_weather_emoji(weather_code)} {city}")
                st.metric(
                    "Temperature",
                    f"{temp:.1f}{temp_unit}" if temp is not None else "N/A",
                )
                st.metric(
                    "Humidity", f"{humidity:.0f}%" if humidity is not None else "N/A"
                )
                st.metric("Wind", f"{wind:.1f} km/h" if wind is not None else "N/A")
                st.caption(f"**{get_weather_label(weather_code)}**")
    else:
        st.info("No data available for comparison at the selected time.")

    # Average daily temperature comparison
    st.subheader("📊 Average Daily Temperature Comparison")

    with st.spinner("Loading daily averages..."):
        avg_df = get_daily_avg_temperature(conn, cities, start_date, end_date)

    if not avg_df.is_empty():
        temp_col = "avg_temperature_c" if temp_unit == "°C" else "avg_temperature_f"
        avg_pd = avg_df.to_pandas()

        fig = px.bar(
            avg_pd,
            x="date",
            y=temp_col,
            color="city_name",
            title=f"Average Daily Temperature ({temp_unit})",
            labels={
                temp_col: f"Avg Temperature ({temp_unit})",
                "date": "Date",
                "city_name": "City",
            },
            height=400,
            barmode="group",
        )

        fig.update_layout(
            xaxis_title="Date",
            yaxis_title=f"Average Temperature ({temp_unit})",
        )

        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No daily average data available.")

    # Optional: Temperature heatmap
    if not avg_df.is_empty() and len(cities) >= 2:
        st.subheader("🗺️ Temperature Heatmap")

        # Pivot data for heatmap
        pivot_df = avg_df.pivot(
            values="avg_temperature_c" if temp_unit == "°C" else "avg_temperature_f",
            index="date",
            columns="city_name",
        )

        pivot_pd = pivot_df.to_pandas()

        fig = go.Figure(
            data=go.Heatmap(
                z=pivot_pd.values.T,
                x=pivot_pd.index,
                y=pivot_pd.columns,
                colorscale="RdYlBu_r",
                colorbar=dict(title=f"Temp ({temp_unit})"),
            )
        )

        fig.update_layout(
            title=f"Temperature Heatmap ({temp_unit})",
            xaxis_title="Date",
            yaxis_title="City",
            height=400,
        )

        st.plotly_chart(fig, use_container_width=True)


# =====================================================
# MAIN APPLICATION
# =====================================================


def main() -> None:
    """Main application entry point."""

    # Test database connection
    try:
        conn = get_db_connection()
    except Exception as e:
        st.error(f"❌ Database connection failed: {e}")
        st.info("Please check your .env file and ensure PostgreSQL is running.")
        st.stop()

    # Render sidebar and get filters
    filters = render_sidebar(conn)

    # Page navigation
    page = st.sidebar.radio(
        "Navigate",
        options=["Current Conditions", "Historical Trends", "City Comparison"],
        index=0,
    )

    # Render selected page
    if page == "Current Conditions":
        render_current_conditions(conn, filters)
    elif page == "Historical Trends":
        render_historical_trends(conn, filters)
    elif page == "City Comparison":
        render_city_comparison(conn, filters)


if __name__ == "__main__":
    main()
