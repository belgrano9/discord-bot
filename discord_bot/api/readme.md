
# API Module

## Overview

The API module provides standardized, asynchronous interfaces to various financial data sources and cryptocurrency exchanges. It abstracts away the complexities of API authentication, request signing, response parsing, and error handling to provide a consistent experience across different data providers.

## Architecture

The module follows a consistent architecture pattern with base classes and specialized implementations:

```
api/
├── __init__.py           # Package exports
├── base.py               # AsyncBaseAPI and core utilities
├── request_utilities.py  # Shared request handling utilities
├── financial.py          # Financial datasets API client
├── prices.py             # Price data API client
├── kucoin.py             # KuCoin exchange API client
├── bitvavo.py            # Bitvavo exchange API client
└── compatibility.py      # Backward compatibility wrappers
```

## Core Components

### AsyncBaseAPI

The `AsyncBaseAPI` serves as a foundation for all API clients, providing:

* Asynchronous HTTP request methods (`get`, `post`, etc.)
* Consistent error handling and response formatting
* Authentication management
* Customizable request options

```python
class AsyncBaseAPI(ABC):
    def __init__(self, base_url: str, api_key: Optional[str] = None):
        # Initialize base URL and authentication
    
    async def request(self, method: str, endpoint: str, ...):
        # Handle HTTP requests with error handling
    
    async def get(self, endpoint: str, params: Dict = None, ...):
        # Convenience wrapper for GET requests
    
    async def post(self, endpoint: str, data: Dict = None, ...):
        # Convenience wrapper for POST requests
```

### Request Utilities

The `request_utilities.py` module provides shared functionality:

* Asynchronous HTTP request handling with retries
* Rate limiting mechanisms
* Consistent error handling
* Response processing and data extraction
* URL construction and parameter encoding

### API Client Implementations

Each specialized client extends `AsyncBaseAPI` and implements endpoints for a specific service:

#### `AsyncFinancialAPI`

Provides access to financial data including:

* Company financial statements
* Financial ratios and metrics
* Real-time financial snapshots
* Historical financial data

#### `AsyncPricesAPI`

Handles price data retrieval for stocks and assets:

* Current price snapshots
* Historical price data with customizable intervals
* Price statistics and calculations

#### `AsyncKucoinAPI`

Implements KuCoin cryptocurrency exchange functionality:

* Market data retrieval
* Trading execution and order management
* Account information and balances
* Trade history and order tracking

#### `AsyncBitvavoAPI`

Provides access to Bitvavo cryptocurrency exchange:

* Market data and orderbook information
* Trading functionality
* Account management
* Order processing

### Backward Compatibility

For smooth transition from synchronous to asynchronous code, compatibility wrappers are provided:

```python
class FinancialAPI:
    def __init__(self, ticker: str, period: str = None, limit: int = None):
        # Initialize the async client
        self.async_api = AsyncFinancialAPI(ticker, period, limit)
    
    def get_snapshots(self):
        # Run the async version synchronously
        return self._run_async(self.async_api.get_snapshots())
```

## Key Features

1. **Asynchronous by Default** : All API clients use async/await pattern for non-blocking I/O
2. **Consistent Error Handling** : Standardized approach to error processing
3. **Intelligent Response Parsing** : Extracts relevant data from varied API responses
4. **Environmental Configuration** : Falls back to environment variables for API keys
5. **Comprehensive Logging** : Detailed logging for debugging and monitoring
6. **Retry Logic** : Automatic retries with exponential backoff
7. **Rate Limiting** : Protection against API rate limits

## Usage Examples

### Using Async API in Discord Commands

```python
@commands.command()
async def price(self, ctx, ticker: str):
    # Use async API directly in commands
    api = AsyncPricesAPI(
        ticker=ticker,
        interval="day",
        interval_multiplier=1,
        start_date=datetime.now().strftime("%Y-%m-%d"),
        end_date=datetime.now().strftime("%Y-%m-%d")
    )
    data = await api.get_live_price()
    await ctx.send(f"Current price: ${data['price']}")
```

### Using Backward Compatibility Wrapper

```python
# Legacy code still works with the new implementation
financial_api = FinancialAPI(ticker="AAPL")
snapshot = financial_api.get_snapshots()
```

### Standardized Error Handling

```python
try:
    result = await api.get_ticker("BTC-USDT")
    success, data, error = await api.process_response(result)
    if not success:
        logger.warning(f"API error: {error}")
except APIError as e:
    logger.error(f"Request failed: {e.message}")
```

## Authentication Management

API key management is handled consistently across all clients:

1. API keys can be passed directly to constructors
2. Or retrieved from environment variables if not provided
3. Methods requiring authentication are protected with `@require_api_key` decorator
4. Authentication errors are raised with clear messages

## Integration Points

The API module integrates with:

* Financial data providers
* Cryptocurrency exchanges
* Logging system for monitoring and debugging
* Discord command system for user interactions
