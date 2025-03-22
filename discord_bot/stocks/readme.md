# Stocks Module

## Overview

The `stocks` module provides functionality for retrieving and displaying financial data about stocks. It integrates with financial data APIs to provide users with stock prices, company financial statements, and other market information through Discord commands.

## Architecture

The stocks module follows a service-oriented architecture:

```
stocks/
├── __init__.py              # Package exports
├── cog.py                   # Discord command registration
├── commands.py              # Command handling logic
├── services/
│   ├── __init__.py          # Service exports
│   ├── financial_service.py # Financial data retrieval
│   └── price_service.py     # Price data retrieval
└── formatters/
    ├── __init__.py          # Formatter exports
    ├── finance_formatter.py # Financial data formatting
    └── price_formatter.py   # Price data formatting
```

## Key Components

### Services

The module contains two primary services:

* `FinancialService`: Retrieves financial statements, company metrics, and other fundamental data
* `PriceService`: Fetches current and historical price data for stocks

### Formatters

Data presentation is handled by formatters:

* `FinanceFormatter`: Formats financial statements and snapshots into Discord embeds
* `PriceFormatter`: Creates price charts and current price displays

### Commands

The command handling layer:

* Processes user input and validates parameters
* Coordinates between services and formatters
* Handles error cases and edge conditions

## User Commands

The module provides several Discord commands:

* `!stock [ticker]` - Get a snapshot of key financial metrics
* `!price [ticker] [days]` - Get price information with optional historical data
* `!live [ticker]` - Get real-time price information
* `!financials [ticker] [statement_type]` - Get financial statements (income, balance, cash)

## Example Usage

```
# Get a snapshot of Apple's financial metrics
!stock AAPL

# Get Microsoft's price for the past 7 days
!price MSFT 7

# Get the latest price for Tesla
!live TSLA

# Get Amazon's income statement
!financials AMZN income
```

## Integration Points

The stocks module integrates with:

* `api.financial` for financial data retrieval
* `api.prices` for price data retrieval
* Polars for data analysis and transformations
* Discord's embedding system for rich displays

## Features

* Real-time and historical price tracking
* Company financial metrics visualization
* Financial statement analysis
* Price change highlighting and calculations
