"""
Database query functions for the weather dashboard.
All functions return Polars DataFrames and use caching for performance.
"""

from datetime import date, datetime
from typing import Any

import polars as pl
import streamlit as st
from sqlalchemy import text
from sqlalchemy.engine import Connection


@st.cache_data(ttl=300)
def get_available_cities(_conn: Connection) -> list[str]:
    """
    Fetch list of all cities from the locations table.

    Args:
        _conn: SQLAlchemy database connection (underscore prevents hashing)

    Returns:
        List of city names sorted alphabetically
    """
    query = """
        SELECT DISTINCT city_name
        FROM locations
        ORDER BY city_name
    """

    df = pl.read_database(query, connection=_conn)

    if df.is_empty():
        return []

    return df["city_name"].to_list()


@st.cache_data(ttl=300)
def get_latest_readings(_conn: Connection, cities: list[str]) -> pl.DataFrame:
    """
    Get the most recent weather reading for each selected city.

    Args:
        _conn: SQLAlchemy database connection
        cities: List of city names to fetch readings for

    Returns:
        Polars DataFrame with latest readings per city
    """
    if not cities:
        return pl.DataFrame()

    # Generate individual placeholders: :city0, :city1, :city2, etc.
    placeholders = ", ".join([f":city{i}" for i in range(len(cities))])

    query_safe = text(f"""
        WITH latest_per_location AS (
            SELECT 
                location_id,
                MAX(recorded_at) as max_recorded_at
            FROM weather_readings
            GROUP BY location_id
        )
        SELECT 
            l.city_name,
            l.country_code,
            wr.recorded_at,
            wr.temperature_c,
            wr.temperature_f,
            wr.humidity_pct,
            wr.wind_speed_kmh,
            wr.precipitation_mm,
            wr.weather_code,
            wr.ingested_at
        FROM weather_readings wr
        JOIN latest_per_location lpl 
            ON wr.location_id = lpl.location_id 
            AND wr.recorded_at = lpl.max_recorded_at
        JOIN locations l ON wr.location_id = l.id
        WHERE l.city_name IN ({placeholders})
        ORDER BY l.city_name
    """)

    # Create parameter dict: {"city0": "Cairo", "city1": "London", ...}
    params = {f"city{i}": city for i, city in enumerate(cities)}

    df = pl.read_database(
        query_safe, connection=_conn, execute_options={"parameters": params}
    )

    return df


@st.cache_data(ttl=300)
def get_temperature_trend(
    _conn: Connection, cities: list[str], start: date, end: date
) -> pl.DataFrame:
    """
    Get hourly temperature data for selected cities within date range.

    Args:
        _conn: SQLAlchemy database connection
        cities: List of city names
        start: Start date (inclusive)
        end: End date (inclusive)

    Returns:
        Polars DataFrame with hourly temperature trends
    """
    if not cities:
        return pl.DataFrame()

    # Generate individual placeholders: :city0, :city1, :city2, etc.
    placeholders = ", ".join([f":city{i}" for i in range(len(cities))])

    query_safe = text(f"""
        SELECT 
            l.city_name,
            wr.recorded_at,
            wr.temperature_c,
            wr.temperature_f
        FROM weather_readings wr
        JOIN locations l ON wr.location_id = l.id
        WHERE l.city_name IN ({placeholders})
            AND DATE(wr.recorded_at) BETWEEN :start_date AND :end_date
        ORDER BY wr.recorded_at, l.city_name
    """)

    # Create parameter dict: {"city0": "Cairo", "city1": "London", ...}
    params = {f"city{i}": city for i, city in enumerate(cities)}
    params["start_date"] = start
    params["end_date"] = end

    df = pl.read_database(
        query_safe,
        connection=_conn,
        execute_options={"parameters": params},
    )

    return df


@st.cache_data(ttl=300)
def get_daily_precipitation(
    _conn: Connection, cities: list[str], start: date, end: date
) -> pl.DataFrame:
    """
    Get daily total precipitation for selected cities.

    Args:
        _conn: SQLAlchemy database connection
        cities: List of city names
        start: Start date (inclusive)
        end: End date (inclusive)

    Returns:
        Polars DataFrame with daily precipitation totals
    """
    if not cities:
        return pl.DataFrame()

    # Generate individual placeholders: :city0, :city1, :city2, etc.
    placeholders = ", ".join([f":city{i}" for i in range(len(cities))])

    query_safe = text(f"""
        SELECT 
            l.city_name,
            DATE(wr.recorded_at) as date,
            SUM(wr.precipitation_mm) as total_precipitation_mm
        FROM weather_readings wr
        JOIN locations l ON wr.location_id = l.id
        WHERE l.city_name IN ({placeholders})
            AND DATE(wr.recorded_at) BETWEEN :start_date AND :end_date
        GROUP BY l.city_name, DATE(wr.recorded_at)
        ORDER BY date, l.city_name
    """)

    # Create parameter dict: {"city0": "Cairo", "city1": "London", ...}
    params = {f"city{i}": city for i, city in enumerate(cities)}
    params["start_date"] = start
    params["end_date"] = end

    df = pl.read_database(
        query_safe,
        connection=_conn,
        execute_options={"parameters": params},
    )

    return df


@st.cache_data(ttl=300)
def get_humidity_trend(
    _conn: Connection, city: str, start: date, end: date
) -> pl.DataFrame:
    """
    Get hourly humidity data for a single city.

    Args:
        _conn: SQLAlchemy database connection
        city: City name
        start: Start date (inclusive)
        end: End date (inclusive)

    Returns:
        Polars DataFrame with hourly humidity readings
    """
    query = """
        SELECT 
            wr.recorded_at,
            wr.humidity_pct
        FROM weather_readings wr
        JOIN locations l ON wr.location_id = l.id
        WHERE l.city_name = :city
            AND DATE(wr.recorded_at) BETWEEN :start_date AND :end_date
        ORDER BY wr.recorded_at
    """

    df = pl.read_database(
        query,
        connection=_conn,
        execute_options={
            "parameters": {"city": city, "start_date": start, "end_date": end}
        },
    )

    return df


@st.cache_data(ttl=300)
def get_city_comparison(
    _conn: Connection, cities: list[str], at: datetime
) -> pl.DataFrame:
    """
    Get weather metrics for all cities at a specific timestamp.
    Finds the closest reading to the specified timestamp for each city.

    Args:
        _conn: SQLAlchemy database connection
        cities: List of city names
        at: Timestamp to compare cities at

    Returns:
        Polars DataFrame with metrics for each city
    """
    if not cities:
        return pl.DataFrame()

    # Generate individual placeholders: :city0, :city1, :city2, etc.
    placeholders = ", ".join([f":city{i}" for i in range(len(cities))])

    query_safe = text(f"""
        WITH closest_readings AS (
            SELECT 
                l.city_name,
                wr.recorded_at,
                wr.temperature_c,
                wr.temperature_f,
                wr.humidity_pct,
                wr.wind_speed_kmh,
                wr.precipitation_mm,
                wr.weather_code,
                ABS(EXTRACT(EPOCH FROM (wr.recorded_at - :target_time))) as time_diff_seconds,
                ROW_NUMBER() OVER (
                    PARTITION BY l.id 
                    ORDER BY ABS(EXTRACT(EPOCH FROM (wr.recorded_at - :target_time)))
                ) as rn
            FROM weather_readings wr
            JOIN locations l ON wr.location_id = l.id
            WHERE l.city_name IN ({placeholders})
        )
        SELECT 
            city_name,
            recorded_at,
            temperature_c,
            temperature_f,
            humidity_pct,
            wind_speed_kmh,
            precipitation_mm,
            weather_code
        FROM closest_readings
        WHERE rn = 1
        ORDER BY city_name
    """)

    # Create parameter dict: {"city0": "Cairo", "city1": "London", ...}
    params = {f"city{i}": city for i, city in enumerate(cities)}
    params["target_time"] = at

    df = pl.read_database(
        query_safe,
        connection=_conn,
        execute_options={"parameters": params},
    )

    return df


@st.cache_data(ttl=300)
def get_filtered_records(
    _conn: Connection, cities: list[str], start: date, end: date
) -> pl.DataFrame:
    """
    Get raw weather readings table filtered by cities and date range.

    Args:
        _conn: SQLAlchemy database connection
        cities: List of city names
        start: Start date (inclusive)
        end: End date (inclusive)

    Returns:
        Polars DataFrame with raw weather records
    """
    if not cities:
        return pl.DataFrame()

    # Generate individual placeholders: :city0, :city1, :city2, etc.
    placeholders = ", ".join([f":city{i}" for i in range(len(cities))])

    query_safe = text(f"""
        SELECT 
            l.city_name,
            l.country_code,
            wr.recorded_at,
            wr.temperature_c,
            wr.temperature_f,
            wr.humidity_pct,
            wr.wind_speed_kmh,
            wr.precipitation_mm,
            wr.weather_code,
            wr.ingested_at
        FROM weather_readings wr
        JOIN locations l ON wr.location_id = l.id
        WHERE l.city_name IN ({placeholders})
            AND DATE(wr.recorded_at) BETWEEN :start_date AND :end_date
        ORDER BY wr.recorded_at DESC, l.city_name
    """)

    # Create parameter dict: {"city0": "Cairo", "city1": "London", ...}
    params = {f"city{i}": city for i, city in enumerate(cities)}
    params["start_date"] = start
    params["end_date"] = end

    df = pl.read_database(
        query_safe,
        connection=_conn,
        execute_options={"parameters": params},
    )

    return df


@st.cache_data(ttl=300)
def get_daily_avg_temperature(
    _conn: Connection, cities: list[str], start: date, end: date
) -> pl.DataFrame:
    """
    Get average daily temperature for selected cities (used for comparison charts).

    Args:
        _conn: SQLAlchemy database connection
        cities: List of city names
        start: Start date (inclusive)
        end: End date (inclusive)

    Returns:
        Polars DataFrame with daily average temperatures
    """
    if not cities:
        return pl.DataFrame()

    # Generate individual placeholders: :city0, :city1, :city2, etc.
    placeholders = ", ".join([f":city{i}" for i in range(len(cities))])

    query_safe = text(f"""
        SELECT 
            l.city_name,
            DATE(wr.recorded_at) as date,
            AVG(wr.temperature_c) as avg_temperature_c,
            AVG(wr.temperature_f) as avg_temperature_f
        FROM weather_readings wr
        JOIN locations l ON wr.location_id = l.id
        WHERE l.city_name IN ({placeholders})
            AND DATE(wr.recorded_at) BETWEEN :start_date AND :end_date
        GROUP BY l.city_name, DATE(wr.recorded_at)
        ORDER BY date, l.city_name
    """)

    # Create parameter dict: {"city0": "Cairo", "city1": "London", ...}
    params = {f"city{i}": city for i, city in enumerate(cities)}
    params["start_date"] = start
    params["end_date"] = end

    df = pl.read_database(
        query_safe,
        connection=_conn,
        execute_options={"parameters": params},
    )

    return df
