"""
Extract weather data from Open-Meteo API with retry logic.
"""

import logging
import time
from dataclasses import dataclass
from typing import Any

import requests

logger = logging.getLogger(__name__)


@dataclass
class City:
    """City configuration with coordinates."""

    name: str
    latitude: float
    longitude: float
    country_code: str = "XX"


# Default cities configuration
DEFAULT_CITIES = [
    City("Cairo", 30.0444, 31.2357, "EG"),
    City("London", 51.5074, -0.1278, "GB"),
    City("Tokyo", 35.6762, 139.6503, "JP"),
    City("New York", 40.7128, -74.0060, "US"),
    City("Sydney", -33.8688, 151.2093, "AU"),
]

# Open-Meteo API configuration
API_BASE_URL = "https://api.open-meteo.com/v1/forecast"
DEFAULT_HOURLY_FIELDS = [
    "temperature_2m",
    "relative_humidity_2m",
    "wind_speed_10m",
    "precipitation",
    "weathercode",
]

MAX_RETRIES = 3
INITIAL_BACKOFF = 1.0  # seconds


def fetch_weather_data(
    latitude: float,
    longitude: float,
    hourly_fields: list[str] | None = None,
    timezone: str = "UTC",
    timeout: int = 30,
) -> dict[str, Any]:
    """
    Fetch weather data from Open-Meteo API with exponential backoff retry logic.

    Args:
        latitude: Latitude coordinate
        longitude: Longitude coordinate
        hourly_fields: List of hourly weather parameters to fetch
        timezone: Timezone for the response (default: UTC)
        timeout: Request timeout in seconds

    Returns:
        Raw JSON response as Python dict

    Raises:
        requests.RequestException: If all retry attempts fail
    """
    if hourly_fields is None:
        hourly_fields = DEFAULT_HOURLY_FIELDS

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "hourly": ",".join(hourly_fields),
        "current_weather": "true",
        "timezone": timezone,
    }

    last_exception = None
    backoff = INITIAL_BACKOFF

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info(
                f"Fetching weather data for ({latitude}, {longitude}) - Attempt {attempt}/{MAX_RETRIES}"
            )
            response = requests.get(API_BASE_URL, params=params, timeout=timeout)
            response.raise_for_status()

            data = response.json()
            logger.info(
                f"Successfully fetched weather data for ({latitude}, {longitude})"
            )
            return data

        except requests.exceptions.Timeout as e:
            last_exception = e
            logger.warning(
                f"Timeout on attempt {attempt}/{MAX_RETRIES} for ({latitude}, {longitude})"
            )

        except requests.exceptions.HTTPError as e:
            last_exception = e
            status_code = e.response.status_code if e.response else None
            logger.warning(
                f"HTTP error {status_code} on attempt {attempt}/{MAX_RETRIES} for ({latitude}, {longitude})"
            )

        except requests.exceptions.RequestException as e:
            last_exception = e
            logger.warning(
                f"Request error on attempt {attempt}/{MAX_RETRIES} for ({latitude}, {longitude}): {e}"
            )

        # Don't sleep after the last attempt
        if attempt < MAX_RETRIES:
            sleep_time = backoff * (2 ** (attempt - 1))
            logger.info(f"Retrying in {sleep_time:.1f} seconds...")
            time.sleep(sleep_time)

    # All retries exhausted
    error_msg = f"Failed to fetch weather data for ({latitude}, {longitude}) after {MAX_RETRIES} attempts"
    logger.error(error_msg)
    raise requests.RequestException(error_msg) from last_exception


def extract_weather_for_cities(
    cities: list[City] | None = None,
    hourly_fields: list[str] | None = None,
    timezone: str = "UTC",
) -> list[tuple[str, dict[str, Any]]]:
    """
    Extract weather data for multiple cities.

    Args:
        cities: List of City objects (uses DEFAULT_CITIES if None)
        hourly_fields: List of hourly weather parameters to fetch
        timezone: Timezone for the response

    Returns:
        List of (city_name, weather_data) tuples
    """
    if cities is None:
        cities = DEFAULT_CITIES

    if hourly_fields is None:
        hourly_fields = DEFAULT_HOURLY_FIELDS

    results: list[tuple[str, dict[str, Any]]] = []

    for city in cities:
        try:
            weather_data = fetch_weather_data(
                latitude=city.latitude,
                longitude=city.longitude,
                hourly_fields=hourly_fields,
                timezone=timezone,
            )
            results.append((city.name, weather_data))
            logger.info(f"Successfully extracted data for {city.name}")

        except requests.RequestException as e:
            logger.error(f"Failed to extract data for {city.name}: {e}")
            # Continue with other cities even if one fails
            continue

    logger.info(f"Extraction complete: {len(results)}/{len(cities)} cities successful")
    return results
