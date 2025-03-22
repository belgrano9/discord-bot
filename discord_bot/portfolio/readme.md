# Portfolio Module

## Overview

The `portfolio` module provides functionality for tracking and analyzing stock portfolios. It maintains a collection of stock positions with their purchase prices and current market values, calculates performance metrics, and generates reports for Discord users.

## Architecture

The portfolio module follows a clean architecture pattern:

```
portfolio/
├── __init__.py         # Package exports
├── models.py           # Data models for portfolio information
├── price_service.py    # Service for retrieving stock price data
├── portfolio_storage.py # Persistence and caching of portfolio data
├── calculator.py       # Business logic for portfolio calculations
├── embed_builder.py    # Formatting portfolio data for Discord embeds
├── commands.py         # Command handlers for user interactions
└── cog.py              # Discord cog for command registration
```

## Key Components

### Data Models

The module defines two primary data structures:

* `Position`: Represents a single stock position with information about purchase price, current price, shares owned, and performance metrics.
* `Portfolio`: Contains a collection of positions and calculates aggregate metrics like total value and overall performance.

### Portfolio Storage

The `PortfolioStorage` class handles:

* Loading portfolio configuration from settings
* Retrieving current price information for positions
* Caching data to reduce API calls
* Providing a consistent interface for portfolio access

### Price Service

The `PortfolioPriceService` is responsible for:

* Retrieving current price data for stocks from external APIs
* Updating position prices in batches
* Handling error cases when price data isn't available

### Portfolio Calculator

The `PortfolioCalculator` provides business logic for:

* Calculating portfolio summary statistics
* Identifying top and bottom performing positions
* Computing value changes between updates

### Embed Builder

The `PortfolioEmbedBuilder` formats portfolio data into Discord embeds:

* Creating summary views of the entire portfolio
* Building performance comparisons with top/bottom performers
* Formatting value changes and gains/losses

## Usage

The module exposes its functionality through Discord commands:

* `!portfolio` - Display the current portfolio status
* Additionally, scheduled reports can display portfolio information at regular intervals

## Integration Points

The portfolio module integrates with several other components:

* Uses the `api.prices` module to retrieve current stock prices
* Provides data to the `reports` module for scheduled portfolio updates
* Uses Discord's embed system for rich visual displays

## Configuration

The portfolio is configured through the `config.py` file:

```python
PORTFOLIO = {
    "NVDA": {"shares": 2, "entry_price": 120.1},
    # Additional positions...
}

PORTFOLIO_UPDATE_INTERVAL = 180  # 3 minutes
PORTFOLIO_CHANNEL_ID = 1234567890  # Discord channel for updates
```
