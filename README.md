# Financial Bot Documentation

## Overview

This Discord bot provides financial data tracking, stock price alerts, and portfolio management capabilities. It uses a financial data API to fetch real-time and historical market data.

## Modules

### 1. API Module (`api.py`)

The foundation for all financial data requests, containing API wrappers for various endpoints.

#### Classes:

- **BaseAPI**: Abstract base class defining common API request methods
- **FinancialAPI**: Fetches financial statements and metrics
- **PricesAPI**: Retrieves stock price data

#### Key Features:

- Financial statements (income, balance sheet, cash flow)
- Financial metrics and ratios
- Historical and real-time price data

### 2. Stock Commands (`stock_commands.py`)

Discord commands for fetching and displaying stock data.

#### Commands:

- `!stock [ticker]`: Display financial snapshot with key metrics
- `!price [ticker] [days]`: Show price data (default: latest price)
- `!live [ticker]`: Get real-time price with change information
- `!financials [ticker] [statement_type]`: View financial statements (income, balance, cash)

### 3. Stock Alerts (`stock_alerts.py`)

Monitors stocks and sends alerts based on user-defined conditions.

#### Commands:

- `!alert add [ticker] [percent|price] [value]`: Create a new price alert
- `!alert remove [index]`: Remove an alert by index
- `!alert list`: Show all active alerts
- `!alert test`: Test the alert system functionality
- `!end test`: Stop a running alert test
- `!watchlist`: Display stocks being monitored from config

#### Features:

- Percentage-based alerts (e.g., stock grows by 5%)
- Price threshold alerts (e.g., stock reaches $150)
- Automatic background monitoring with configurable intervals
- Persistent alerts saved between bot restarts

### 4. Portfolio Tracker (`portfolio_tracker.py`)

Tracks portfolio value and performance over time.

#### Commands:

- `!portfolio`: Display current portfolio status with gains/losses

#### Features:

- Real-time portfolio valuation
- Individual position tracking
- Gain/loss calculation (total and per position)
- Automatic updates at configured intervals

### 5. Configuration (`config.py`)

Central configuration for various bot settings.

#### Settings:

- `ALERT_CHANNEL_ID`: Default channel for stock alerts
- `STOCKS`: Stocks to monitor with threshold values
- `CHECK_INTERVAL`: Time between alert checks
- `PORTFOLIO`: Stock positions with shares and entry prices
- `PORTFOLIO_UPDATE_INTERVAL`: Time between portfolio updates
- `PORTFOLIO_CHANNEL_ID`: Channel for automatic portfolio updates

### 6. Main Bot (`bot.py`)

Discord bot setup and initialization.

#### Commands:

- `!ping`: Simple command to test if bot is responsive

#### Features:

- Dynamic loading of command modules
- Intents configuration
- Startup diagnostic information

## Setup and Usage

### Environment Variables

- `DISCORD_TOKEN`: Discord bot authentication token
- `FINANCIAL_DATASETS_API_KEY`: API key for financial data

### Example Commands

```
!stock AAPL                 # Get Apple financial snapshot
!price MSFT 7               # Get Microsoft price data for past 7 days
!live NVDA                  # Get real-time Nvidia stock price
!alert add TSLA percent 5   # Alert when Tesla grows by 5%
!alert add AMD price 150    # Alert when AMD reaches $150
!portfolio                  # View your current portfolio status
```

## Architecture

- Discord.py framework with Cog-based module organization
- Polling-based price checks for alerts and portfolio tracking
- Persistent data storage for alerts
- Polars DataFrame handling for price data analysis
