# Utils Module

## Overview

The `utils` module provides shared utility functions and helpers that are used across multiple components of the Discord bot. It centralizes common functionality like embed creation, input validation, and formatting to ensure consistency throughout the application.

## Architecture

The utils module is organized by functionality:

```
utils/
├── __init__.py                # Package exports
├── embed_utilities.py         # Discord embed creation helpers
└── validation_utilities.py    # Input validation functions
```

## Key Components

### Embed Utilities

The `embed_utilities.py` module provides standardized functions for creating Discord embeds:

* `create_price_embed()` - Format price information consistently
* `create_portfolio_embed()` - Build portfolio summary displays
* `create_order_embed()` - Format trading order information
* `create_alert_embed()` - Create notification and alert embeds
* `format_large_number()` - Format numbers with K/M/B suffixes
* `format_field_name()` - Convert snake_case to Title Case for field names

These utilities ensure consistent styling, color schemes, and layouts across the entire application, regardless of which module is generating the embed.

### Validation Utilities

The `validation_utilities.py` module offers functions for validating and collecting user input:

* `validate_positive_number()` - Ensure numeric input is positive
* `validate_symbol()` - Check trading symbol format
* `validate_side()` - Validate trading side (buy/sell)
* `validate_order_type()` - Check order type validity
* `validate_choice()` - Ensure input is one of allowed choices
* `validate_interval()` - Validate time interval parameters
* `get_user_input()` - Collect and validate input interactively
* `confirm_action()` - Get confirmation for important actions

## Usage Examples

### Creating Standardized Embeds

```python
from utils.embed_utilities import create_price_embed

# Create a price embed with consistent styling
embed = create_price_embed(
    symbol="BTC-USDT",
    price_data=ticker_data,
    title_prefix="Current",
    show_additional_fields=True,
    color_based_on_change=True
)
```

### Interactive Input Validation

```python
from utils.validation_utilities import get_user_input, validate_symbol

# Collect and validate a trading symbol from the user
symbol = await get_user_input(
    ctx,
    "Enter a trading pair (e.g., BTC-USDT):",
    validator=validate_symbol,
    timeout=60
)

if symbol:
    # Proceed with valid input
    await ctx.send(f"Processing request for {symbol}...")
```

### Getting Action Confirmation

```python
from utils.validation_utilities import confirm_action

# Get confirmation before a critical action
confirmed = await confirm_action(
    ctx,
    title="⚠️ Confirm Order Cancellation",
    description=f"Are you sure you want to cancel order ID: `{order_id}`?",
    color=discord.Color.gold()
)

if confirmed:
    # Proceed with cancellation
    await cancel_order(order_id)
else:
    await ctx.send("Order cancellation aborted.")
```

## Integration Points

The utils module integrates with:

* Discord's embed system for rich visual displays
* Discord's interactive message system for input collection
* Various bot modules that need common functionality

## Benefits

* Ensures consistent UI/UX across all bot features
* Reduces code duplication
* Centralizes formatting and validation logic
* Simplifies the implementation of new features
