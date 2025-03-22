# Trading Module

## Overview

The `trading` module provides cryptocurrency trading functionality through integration with exchange APIs. It allows users to place, manage, and monitor crypto trades directly from Discord, with support for market data, account information, and order management.

## Architecture

The trading module follows a modular architecture with clear separation of concerns:

```
trading/
├── __init__.py               # Package exports
├── cog.py                    # Discord command registration
├── models/                   # Data models
│   ├── __init__.py
│   ├── order.py              # Order data structures
│   └── account.py            # Account data structures
├── services/                 # API integration
│   ├── __init__.py
│   ├── kucoin_service.py     # KuCoin API interactions
│   └── market_service.py     # Market data retrieval
├── formatters/               # Data presentation
│   ├── __init__.py
│   ├── order_formatter.py    # Order data formatting
│   ├── account_formatter.py  # Account data formatting
│   └── market_formatter.py   # Market data formatting
├── commands/                 # Command handlers
│   ├── __init__.py
│   ├── order_commands.py     # Order-related commands
│   ├── account_commands.py   # Account-related commands
│   └── market_commands.py    # Market data commands
└── interactions/             # User interaction handling
    ├── __init__.py
    ├── input_manager.py      # Interactive input collection
    └── reaction_handler.py   # Emoji reaction handling
```

## Key Components

### Data Models

* `OrderRequest`: Structure for creating new orders
* `OrderResponse`: Response data from order creation
* `OrderSide` & `OrderType`: Enums for order parameters
* `Asset`: Account asset representation
* `MarginAccount`: Margin account data structure
* `TradeInfo`: Trade execution data

### Services

* `KuCoinService`: Handles KuCoin API communication and order execution
* `MarketService`: Retrieves market data like prices and order book

### Formatters

* `OrderFormatter`: Formats order data into Discord embeds
* `AccountFormatter`: Creates account balance and trade history displays
* `MarketFormatter`: Builds market data visualizations

### Command Handlers

* `OrderCommands`: Handles order creation and management
* `AccountCommands`: Provides account information and trade history
* `MarketCommands`: Delivers market data and price information

### Interactive Components

* `InputManager`: Collects and validates user input through messages
* `ReactionHandler`: Processes emoji reactions for interactive controls

## User Commands

The module provides several Discord commands:

* `!testtrade [market] [side] [amount] [price] [order_type]` - Test trade without real execution
* `!realorder [market] [side] [amount] [price_or_type] [order_type]` - Place a real trade
* `!ticker [symbol]` - Get current market information
* `!fees [symbol]` - Get trading fee information
* `!balance [symbol]` - Show margin account information
* `!last_trade [symbol]` - Show most recent trade
* `!list_trades [symbol] [limit]` - Show trade history
* `!cancel_order [order_id]` - Cancel an existing order

## Security Features

* Role-based permissions for real trading commands
* Confirmation requirements for real orders
* Interactive parameter collection with validation
* Test mode for simulating trades without risk

## Integration Points

The trading module integrates with:

* `api.kucoin` for exchange API communication
* Discord's reaction system for interactive elements
* Discord's embedding system for rich displays

## Example Usage

```
# Test a trade (no real execution)
!testtrade BTC-USDT buy 0.001 50000 limit

# Get ticker information
!ticker ETH-USDT

# Check your margin account balance
!balance BTC-USDT

# View recent trades
!list_trades BTC-USDT 5
```
