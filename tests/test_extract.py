"""Tests for extract module."""

import pytest
from src.extract import City, DEFAULT_CITIES


def test_city_dataclass():
    """Test City dataclass creation."""
    city = City("Paris", 48.8566, 2.3522)
    assert city.name == "Paris"
    assert city.latitude == 48.8566
    assert city.longitude == 2.3522


def test_default_cities_configured():
    """Test that default cities are configured."""
    assert len(DEFAULT_CITIES) == 5
    city_names = [city.name for city in DEFAULT_CITIES]
    assert "Cairo" in city_names
    assert "London" in city_names
    assert "Tokyo" in city_names
    assert "New York" in city_names
    assert "Sydney" in city_names


def test_default_cities_have_valid_coordinates():
    """Test that all default cities have valid coordinates."""
    for city in DEFAULT_CITIES:
        assert -90 <= city.latitude <= 90
        assert -180 <= city.longitude <= 180
