"""
Root conftest.py — configures Django before pytest collects tests.
"""
import django
from django.conf import settings


def pytest_configure(config):
    """Called by pytest before collection — ensure Django is set up."""
    if not settings.configured:
        settings.configure()
