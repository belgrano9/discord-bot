# Price Tracker Documentation

## Overview

The `price_tracker` package implements a real-time cryptocurrency price tracking system for the Discord bot. It allows users to track multiple cryptocurrency prices with customizable update intervals, provides detailed statistics, and offers interactive controls through Discord reactions.

## Architecture

The price tracker follows a clean, modular architecture with clear separation of concerns:

```
price_tracker/
├── __init__.py           # Package exports
├── tracker_model.py      # Data model for tracked prices
├── price_service.py      # Service for retrieving price data
├── tracker_storage.py    # Storage for tracked prices
├── embed_builder.py      # Discord embed builder
├── tracker_manager.py    # Core manager for tracking
├── commands.py           # Command handlers
├── reaction_handler.py   # Reaction handler
└── cog.py                # Discord cog
```

## Modules

### `tracker_model.py`

Defines the core data structure for tracked cryptocurrency prices:

* `TrackedPrice` - A dataclass representing a cryptocurrency price tracker
  * `symbol` - Trading pair (e.g., "BTC-USDT")
  * `price_data` - Current price information
  * `last_update` - Timestamp of last update
  * `message_id` - Discord message ID displaying the tracker
  * `channel_id` - Discord channel ID where tracker is displayed
  * `interval` - Update interval in seconds
  * `created_at` - Timestamp when tracking started
  * `history` - List of historical prices

Key functionality:

* Convenient property accessors (`current_price`, `starting_price`)
* Price history management
* Change calculation for different timeframes
* Statistical analysis of price data

### `price_service.py`

Handles cryptocurrency price data retrieval:

* `PriceService` - Service for getting price data
  * `get_current_price()` - Get current price for a symbol
  * `get_prices_batch()` - Get prices for multiple symbols in parallel
  * `extract_price()` - Extract numeric price from data
  * `format_ticker_data()` - Format raw ticker data

Key functionality:

* Asynchronous API communication
* Error handling for API failures
* Batch processing for efficiency
* Consistent data formatting

### `tracker_storage.py`

Manages the collection of tracked prices:

* `TrackerStorage` - Manager for storing tracked prices
  * `add_tracked_price()` - Add a new tracked price
  * `remove_tracked_price()` - Remove a tracked price
  * `get_tracked_price()` - Get a tracked price by symbol
  * `get_all_tracked_prices()` - Get all tracked prices
  * `get_symbols_to_update()` - Get symbols that need updating
  * `remove_by_message()` - Remove tracked price by message ID

Key functionality:

* In-memory storage of tracked prices
* Efficient symbol lookup
* Update scheduling based on intervals

### `embed_builder.py`

Creates formatted Discord embeds for price data:

* `EmbedBuilder` - Builder for price tracking embeds
  * `build_tracking_embed()` - Create embed for tracked price
  * `build_stopped_embed()` - Create embed for stopped tracker
  * `build_details_embed()` - Create detailed statistics embed

Key functionality:

* Consistent visual formatting
* Rich statistical displays
* Color coding based on price movement
* Detailed historical analysis

### `tracker_manager.py`

Core business logic for price tracking:

* `TrackerManager` - Manager for price tracking functionality
  * `start_tracking()` - Start tracking a cryptocurrency price
  * `stop_tracking()` - Stop tracking a symbol
  * `update_prices()` - Update all prices needing updates
  * `show_details()` - Show detailed price statistics

Key functionality:

* Coordination between storage, service, and UI
* Discord message management
* Background update processing
* Efficient batch updates

### `commands.py`

Implements Discord command handlers:

* `TrackerCommands` - Command handlers for price tracking
  * `track_command()` - Handle the track command
  * `untrack_command()` - Handle the untrack command
  * `list_tracking_command()` - Handle the tracking command

Key functionality:

* User-friendly command responses
* Input validation and normalization
* Formatted embed displays

### `reaction_handler.py`

Handles Discord reactions on price tracking messages:

* `ReactionHandler` - Handler for reactions on tracking messages
  * `handle_reaction()` - Process a reaction event
  * `_handle_stop_tracking()` - Handle stop tracking reaction
  * `_handle_show_details()` - Handle show details reaction

Key functionality:

* Interactive control of trackers
* User-friendly reaction responses
* Permission validation

### `cog.py`

Discord cog that integrates all components:

* `PriceTracker` - Main Discord cog for price tracking
  * Discord commands for tracker management
  * Background task for price updates
  * Reaction handling for user interaction

Key functionality:

* Command registration and routing
* Background task scheduling
* Event handling for reactions

## Usage Examples

### Starting a Price Tracker

Users can start tracking a cryptocurrency price with customizable update intervals:

```
!track BTC-USDT           # Track Bitcoin with default 60s updates
!track ETH-USDT 30        # Track Ethereum with 30s updates
```

### Managing Trackers

Users can view and stop their trackers:

```
!tracking                 # List all active trackers
!untrack BTC-USDT         # Stop tracking Bitcoin
```

### Interactive Controls

Users can interact with tracker messages using reactions:

* `⏹️` - Stop tracking the symbol
* `📊` - Show detailed statistics and price history

## Implementation Details

### Update Process

1. The `price_update_task` runs every second to check all trackers
2. Trackers due for updates based on their intervals are identified
3. Prices are fetched in batch for efficiency
4. Tracked price data and history are updated
5. Discord messages are edited with new embeds

### Efficiency Considerations

* Only checks trackers that need updating based on interval
* Batches API requests for multiple symbols
* Only one update task regardless of number of trackers
* Efficient Discord API usage (editing existing messages)

### Error Handling

* API errors are logged but don't crash the system
* Missing messages are handled by removing the tracker
* Invalid user input is validated and normalized
* Rate limiting consideration for message updates

## Statistical Analysis

The detailed view provides rich statistics:

* Current, high, low, and average prices
* Price range and volatility
* Percentage change from high/low points
* Tracking duration and data points
* Recent price history with change percentages
* Up/down movement count

## Dependencies

* `discord.py` - Discord API integration
* `api.kucoin` - Price data retrieval
* `utils.embed_utilities` - Embed creation utilities
* `loguru` - Logging framework
* `polars` - Statistical analysis (optional)
