# Alert System Documentation

## Overview

The `alerts` package implements a comprehensive stock price alert system for the Discord bot. It allows users to set price alerts based on either a specific price threshold or a percentage change, tracks prices in the background, and sends notifications when alert conditions are met.

## Architecture

The alert system follows a modular architecture with clear separation of concerns:

```
alerts/
├── __init__.py           # Package exports
├── alert_model.py        # Data models for alerts
├── alert_storage.py      # Persistence of alerts
├── alert_commands.py     # Command handlers
├── alert_monitor.py      # Price checking logic
├── config_checker.py     # Config-based alerts
├── test_handler.py       # Test functionality
└── cog.py                # Discord cog
```

## Modules

### `alert_model.py`

Defines the core data structure for price alerts:

* `PriceAlert` - A dataclass representing a stock price alert
  * `ticker` - Stock symbol (e.g., "AAPL")
  * `alert_type` - Either "percent" or "price"
  * `value` - The target percentage or price
  * `reference_price` - Starting price when alert was created
  * `created_at` - Timestamp when alert was created
  * `channel_id` - Discord channel ID for notifications

Key functionality:

* Serialization to/from dictionary for persistence
* Alert condition checking against current prices
* Target price calculation

### `alert_storage.py`

Manages the persistence of alerts to and from JSON files:

* `AlertStorage` - Class for managing alert storage
  * `load()` - Load alerts from file
  * `save()` - Save alerts to file
  * `add_alert()` - Add a new alert
  * `remove_alert()` - Remove an alert by index
  * `remove_alerts()` - Remove multiple alerts

Key functionality:

* Channel-based organization of alerts
* JSON serialization/deserialization
* Error handling for file operations

### `alert_monitor.py`

Monitors stock prices and triggers alerts when conditions are met:

* `AlertMonitor` - Class for monitoring prices
  * `check_alerts()` - Check all alerts against current prices
  * `handle_triggered_alerts()` - Process and notify for triggered alerts

Key functionality:

* Efficient batch price checking by ticker
* Triggered alert notification generation
* Automatic removal of triggered alerts

### `alert_commands.py`

Implements Discord command handlers for managing alerts:

* `AlertCommands` - Class for alert-related commands
  * `add_alert()` - Add a new price alert
  * `remove_alert()` - Remove an alert by index
  * `list_alerts()` - List all alerts for a channel

Key functionality:

* User-friendly command responses
* Input validation
* Formatted embed displays for alerts

### `config_checker.py`

Checks configured stocks against predefined thresholds:

* `ConfigChecker` - Class for monitoring configured stocks
  * `check_stocks()` - Check stocks against thresholds
  * `_send_threshold_alert()` - Send a threshold alert notification

Key functionality:

* Integration with global configuration
* Threshold-based monitoring (low/high points)
* Color-coded alert notifications

### `test_handler.py`

Provides testing utilities for the alert system:

* `TestHandler` - Class for managing test functionality
  * `start_test()` - Start a test sequence
  * `end_test()` - End a running test
  * `_run_test()` - Run the test message sequence

Key functionality:

* Sequential test message generation
* Task management for test processes
* Graceful cancellation handling

### `cog.py`

Discord cog that integrates all components:

* `StockAlerts` - Main Discord cog for the alert system
  * Discord commands for alert management
  * Background task for price checking
  * Component initialization and lifecycle management

Key functionality:

* Command registration and routing
* Background task scheduling
* Configuration integration

## Usage Examples

### Setting a Price Alert

Users can set alerts based on a specific price or percentage change:

```
!alert add AAPL percent 5    # Alert when AAPL grows by 5%
!alert add MSFT price 150    # Alert when MSFT reaches $150
```

### Managing Alerts

Users can view and remove their alerts:

```
!alert list                  # List all alerts for the channel
!alert remove 2              # Remove alert at index 2
```

### Testing

The system includes a self-test mechanism:

```
!alert test                  # Start sending test messages
!end test                    # Stop the test sequence
```

### Watchlist

Users can view stocks configured in the bot settings:

```
!watchlist                   # Show configured stocks with thresholds
```

## Implementation Details

### Alert Lifecycle

1. User creates an alert with `!alert add`
2. Current price is fetched as reference price
3. Alert is stored in JSON file
4. Background task periodically checks prices
5. When an alert is triggered, notification is sent
6. Triggered alert is automatically removed

### Efficiency Considerations

* Alerts are grouped by ticker to minimize API calls
* Batch API requests for multiple tickers
* JSON persistence for durability across restarts
* Channel-based organization for scalability

### Error Handling

* API errors are logged but don't crash the system
* Missing channels or messages are handled gracefully
* File I/O errors are captured and reported
* Rate limiting consideration for API calls

## Dependencies

* `discord.py` - Discord API integration
* `api.prices` - Price data retrieval
* `utils.embed_utilities` - Embed creation utilities
* `loguru` - Logging framework
* `config` - Global configuration
