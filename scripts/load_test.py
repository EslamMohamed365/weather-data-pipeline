"""
Load testing for the weather dashboard using Locust.

Usage:
    pip install locust
    locust -f scripts/load_test.py --host=http://localhost:8501

    # Open browser: http://localhost:8089
    # Set users: 10, spawn rate: 1
"""

from locust import HttpUser, task, between
import random


class DashboardUser(HttpUser):
    """Simulates a user browsing the weather dashboard."""

    wait_time = between(2, 5)  # Wait 2-5 seconds between requests

    cities = ["Cairo", "London", "Tokyo", "New York", "Sydney"]

    @task(3)
    def view_current_conditions(self):
        """View current weather conditions (most common action)."""
        self.client.get("/?page=current")

    @task(2)
    def view_historical_trends(self):
        """View historical trends."""
        self.client.get("/?page=historical")

    @task(1)
    def view_city_comparison(self):
        """Compare cities."""
        self.client.get("/?page=comparison")

    def on_start(self):
        """Called when a user starts."""
        print(f"User {self.environment.runner.user_count} started")
