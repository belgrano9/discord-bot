"""
Stock price alerts package.
Provides functionality for monitoring stock prices and sending alert notifications.
"""

from .cog import StockAlerts, setup

__all__ = ["StockAlerts", "setup"]