# Financial Markets Discord Bot

A powerful Discord bot for tracking stock and cryptocurrency prices, managing portfolios, setting price alerts, and executing trades across multiple exchanges.

## Overview

This Discord bot integrates with financial market APIs to provide real-time data, alerts, and trading functionality directly within Discord channels. It includes modules for stock price tracking, portfolio management, scheduled reports, and cryptocurrency trading.

### Key Features

* **Stock Market Data** : Fetch real-time stock prices, financial metrics, and company data
* **Portfolio Tracking** : Monitor your investment portfolio with real-time performance updates
* **Price Alerts** : Set custom alerts when stocks reach specified price levels or percentage changes
* **Scheduled Reports** : Receive automated daily and weekly portfolio performance summaries
* **Cryptocurrency Trading** : Execute trades directly through Discord (supports KuCoin)
* **Real-time Price Tracking** : Live updates on cryptocurrency prices with price movement visualizations

## Components

### Stock Data

* Stock price lookups and financial metrics
* Company financial statements and snapshots
* Historical price data with performance metrics

### Portfolio Management

* Track multiple stocks and cryptocurrencies in one portfolio
* Real-time valuation and performance metrics
* Visual performance reports showing gains/losses

### Alerting System

* Configure price threshold alerts
* Set percentage change notifications
* Receive timely notifications when conditions are met

### Scheduled Reporting

* Daily and weekly portfolio performance summaries
* Customizable reporting schedule
* Performance comparison against previous periods

### Trading Interface

* Execute cryptocurrency trades directly from Discord
* View trade history and account balances
* Place market and limit orders on supported exchanges

## Command Reference

### Stock Commands

```
!stock <ticker>            - Get financial snapshot of a stock
!price <ticker> [days]     - Get price data for a stock
!live <ticker>             - Get real-time price for a stock
!financials <ticker> <type> - Get financial statements (income, balance, cash)
```

### Portfolio Commands

```
!portfolio                 - Show current portfolio status
!watchlist                 - Show configured stocks to monitor
```

### Alert Commands

```
!alert add <ticker> <type> <value> - Add price alert
!alert remove [index]      - Remove alert by index
!alert list                - List all active alerts
!alert test                - Test alert functionality
```

### Report Commands

```
!report setup <type> <time> [day] - Configure scheduled reports
!report daily <on|off|toggle>     - Enable/disable daily reports
!report weekly <on|off|toggle>    - Enable/disable weekly reports
!report now [type]                - Generate report immediately
!report status                    - Check report configuration
```

### Cryptocurrency Commands

```
!ticker <symbol>           - Get ticker information for a trading pair
!track <symbol> [interval] - Start tracking a crypto price with live updates
!untrack <symbol>          - Stop tracking a cryptocurrency
!tracking                  - List all currently tracked symbols
!balance [symbol]          - Show your exchange account balance
!last_trade <symbol>       - Show your most recent trade for a symbol
!filter_trades             - Interactive command to filter trade history
```

### Trading Commands

```
!testtrade <market> <side> <amount> [price] [type] - Create test trade
!realorder <market> <side> <amount> [price] [type] - Place real order on exchange
!cancel_order <order_id>   - Cancel an existing order
!fees <symbol>             - Get trading fee information
```

## Technical Architecture

The bot is built with several integrated components:

* **Discord.py** : Core framework for Discord integration
* **API Clients** : Custom clients for financial data APIs and exchange APIs
* **Database** : Local file storage for configuration and historical data
* **Scheduled Tasks** : Background tasks for alerts, reports, and price tracking
* **WebSocket Integration** : Real-time data streaming for live crypto prices

### Exchange Integrations

* **KuCoin API** : Full trading functionality with margin capabilities
* **Financial Datasets API** : Stock market data and financial metrics
* **Bitvavo API** : Support for cryptocurrency trading (additional exchange)

## Installation and Setup

### Prerequisites

* Python 3.8+
* Discord Bot Token
* API Keys for supported exchanges and data providers

### Required Python Packages

```
discord.py
requests
polars
python-dotenv
loguru
websocket-client
uuid
```

### Environment Variables

Create a `.env` file with the following variables:

```
DISCORD_TOKEN=your_discord_bot_token
FINANCIAL_DATASETS_API_KEY=your_financial_api_key
KUCOIN_API_KEY=your_kucoin_key
KUCOIN_API_SECRET=your_kucoin_secret
KUCOIN_API_PASSPHRASE=your_kucoin_passphrase
BITVAVO_API_KEY=your_bitvavo_key
BITVAVO_API_SECRET=your_bitvavo_secret
```

### Configuration Files

The bot uses several configuration files:

* `config.py`: Core configuration including stocks to monitor and thresholds
* `reports_config.json`: Configuration for scheduled reports
* `stock_alerts.json`: Saved price alerts

### Discord Server Setup

1. Create a Discord bot in the [Discord Developer Portal](https://discord.com/developers/applications)
2. Enable the necessary intents (Message Content intent is required)
3. Invite the bot to your server with appropriate permissions
4. Create roles for trading permissions:
   * `Trading-Authorized`: Required for executing real trades

## Running the Bot

```bash
# Clone the repository
git clone https://github.com/belgrano9/discord-bot.git
cd discord-bot

# Install dependencies
pip install -r requirements.txt

# Run the bot
python discord-bot/bot.py
```

## Security Considerations

* The bot includes role-based security for sensitive operations
* Real trading commands require the `Trading-Authorized` role
* API keys are stored in environment variables, not in code
* Test commands are available to verify functionality without using real funds

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Disclaimer

This bot is for educational and informational purposes only. Trading cryptocurrencies involves significant risk. Always do your own research before making investment decisions. The creators of this bot are not responsible for any financial losses incurred through its use.
