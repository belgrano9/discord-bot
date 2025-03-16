# API Module

This module provides a standardized approach to making API requests across multiple financial data providers. It uses asynchronous programming to improve performance and ensure the Discord bot remains responsive while waiting for API calls to complete.

## Architecture

The API module follows a consistent architecture pattern:

```
api/
├── __init__.py                # Package exports
├── base.py                    # AsyncBaseAPI and core utilities
├── request_utilities.py       # Shared request handling utilities
├── financial.py               # Financial datasets API
├── prices.py                  # Price data API
├── bitvavo.py                 # Bitvavo exchange API
├── kucoin.py                  # KuCoin exchange API
└── compatibility.py           # Backward compatibility wrappers
```

## Key Components

### AsyncBaseAPI

The `AsyncBaseAPI` class serves as a foundation for all API clients, providing:

* Standardized request methods (`get`, `post`, etc.)
* Consistent error handling
* Response formatting
* Authentication management

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

### API Client Implementations

Each API client extends `AsyncBaseAPI` and implements specific endpoints:

```python
class AsyncFinancialAPI(AsyncBaseAPI):
    async def get_snapshots(self) -> Dict[str, Any]:
        # Get financial snapshots
      
    async def get_income_statements(self) -> List[Dict[str, Any]]:
        # Get income statements
```

### Backward Compatibility

For a smooth transition, backward compatibility wrappers are provided:

```python
class FinancialAPI:
    def __init__(self, ticker: str, period: str = None, limit: int = None):
        # Initialize the async client
        self.async_api = AsyncFinancialAPI(ticker, period, limit)
      
    def get_snapshots(self):
        # Run the async version synchronously
        return self._run_async(self.async_api.get_snapshots())
```

## Benefits

1. **Performance** : Non-blocking API calls improve Discord bot responsiveness
2. **Consistency** : Standardized error handling and response formatting
3. **Maintainability** : Common code patterns reduce duplication
4. **Reliability** : Improved logging and error handling

## Usage Examples

### Using Async API in Discord Commands

```python
@commands.command()
async def price(self, ctx, ticker: str):
    # Use async API directly in commands
    api = AsyncPricesAPI(ticker, ...)
    data = await api.get_live_price()
    await ctx.send(f"Current price: ${data['price']}")
```

### Using Backward Compatibility Wrapper

```python
# Legacy code still works with the new implementation
financial_api = FinancialAPI(ticker="AAPL")
snapshot = financial_api.get_snapshots()
```

## Error Handling

All API clients use a standardized error handling approach:

```python
try:
    result = await api.get_ticker("BTC-USDT")
    success, data, error = await api.process_response(result)
    if not success:
        logger.warning(f"API error: {error}")
except APIError as e:
    logger.error(f"Request failed: {e.message}")
```

## Authentication

API key management is handled consistently across all clients:

1. API keys can be passed directly to constructors
2. Or retrieved from environment variables if not provided
3. Methods requiring authentication are protected with decorators
