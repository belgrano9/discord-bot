"""
Asynchronous implementation using the official Binance Connector library.
Provides an alternative to the custom Binance API client.
"""

import os
import asyncio
from typing import Dict, List, Any, Optional, Tuple
from loguru import logger
import time

try:
    from binance.spot import Spot as BinanceSpot
    from binance.error import ClientError, ServerError
    BINANCE_CONNECTOR_AVAILABLE = True
except ImportError:
    logger.warning("Binance Connector package not installed. Please run 'pip install binance-connector'")
    BINANCE_CONNECTOR_AVAILABLE = False

from .base import AsyncBaseAPI, require_api_key, ApiKeyRequiredError


class AsyncBinanceConnectorClient(AsyncBaseAPI):
    """
    Async wrapper around the official Binance Connector library.
    """
    
    def __init__(
        self,
        api_key: str = None,
        api_secret: str = None,
        base_url: str = "https://api.binance.com",
        timeout: int = 10,
        proxies: Dict[str, str] = None,
        show_limit_usage: bool = False,
        show_header: bool = False
    ):
        """
        Initialize the Binance Connector client.
        
        Args:
            api_key: Binance API key
            api_secret: Binance API secret
            base_url: API base URL
            timeout: Request timeout in seconds
            proxies: Proxy configuration
            show_limit_usage: Whether to show rate limit usage in responses
            show_header: Whether to show full response headers
        """
        # Initialize the parent class
        super().__init__(base_url=base_url, api_key=api_key)
        
        # Store credentials
        self.api_secret = api_secret
        
        if not BINANCE_CONNECTOR_AVAILABLE:
            logger.error("Binance Connector is not available. Please install it with 'pip install binance-connector'")
            return
            
        # Initialize the official client
        self.client = BinanceSpot(
            api_key=api_key,
            api_secret=api_secret,
            base_url=base_url,
            timeout=timeout,
            proxies=proxies,
            show_limit_usage=show_limit_usage,
            show_header=show_header
        )
        
        logger.debug("Initialized AsyncBinanceConnectorClient")
    
    async def _run_client_method(self, method_name: str, *args, **kwargs) -> Any:
        """
        Run a method of the Binance Connector client asynchronously.
        
        Args:
            method_name: Name of the method to call
            *args: Positional arguments to pass to the method
            **kwargs: Keyword arguments to pass to the method
            
        Returns:
            Response from the Binance API
        """
        if not BINANCE_CONNECTOR_AVAILABLE:
            raise ImportError("Binance Connector is not installed")
            
        # Get the method from the client
        method = getattr(self.client, method_name)
        
        # Run the method in a thread pool
        loop = asyncio.get_event_loop()
        try:
            return await loop.run_in_executor(
                None, 
                lambda: method(*args, **kwargs)
            )
        except (ClientError, ServerError) as e:
            logger.error(f"Binance API error ({method_name}): {str(e)}")
            # Convert to a format consistent with your error handling
            return {"error": True, "code": getattr(e, "status_code", 500), "msg": str(e)}
        except Exception as e:
            logger.error(f"Unexpected error in {method_name}: {str(e)}")
            return {"error": True, "code": 500, "msg": str(e)}

    # Public endpoints
    
    async def get_ticker(self, symbol: str = "BTCUSDT") -> Dict[str, Any]:
        """
        Get symbol price ticker.
        
        Args:
            symbol: Trading pair symbol (e.g., BTCUSDT)
        
        Returns:
            Ticker data
        """
        return await self._run_client_method('ticker_price', symbol=symbol)
    
    async def get_ticker_24hr(self, symbol: str = "BTCUSDT") -> Dict[str, Any]:
        """
        Get 24-hour statistics for a symbol.
        
        Args:
            symbol: Trading pair symbol (e.g., BTCUSDT)
            
        Returns:
            24-hour trading statistics
        """
        return await self._run_client_method('ticker_24hr', symbol=symbol)
    
    async def get_exchange_info(self) -> Dict[str, Any]:
        """
        Get exchange trading rules and symbol information.
        
        Returns:
            Exchange information
        """
        return await self._run_client_method('exchange_info')
    
    # Margin account endpoints
    
    @require_api_key
    async def get_margin_account(self) -> Dict[str, Any]:
        """
        Get cross margin account details.
        
        Returns:
            Cross margin account information
        """
        return await self._run_client_method('margin_account')
    
    @require_api_key
    async def get_isolated_margin_account(self, symbols: Optional[str] = None) -> Dict[str, Any]:
        """
        Get isolated margin account details.
        
        Args:
            symbols: List of trading pairs as a single string (e.g., "BTCUSDT,ETHUSDT")
            
        Returns:
            Isolated margin account information
        """
        params = {}
        if symbols:
            params["symbols"] = symbols
            
        return await self._run_client_method('isolated_margin_account', **params)
    
    # Order endpoints
    
    @require_api_key
    async def create_margin_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: Optional[float] = None,
        price: Optional[float] = None,
        stop_price: Optional[float] = None,
        time_in_force: Optional[str] = None,
        is_isolated: bool = False,
        quote_order_qty: Optional[float] = None,
        new_client_order_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new margin order.
        
        Args:
            symbol: Trading pair symbol (e.g., BTCUSDT)
            side: BUY or SELL
            order_type: LIMIT, MARKET, STOP_LOSS, etc.
            quantity: Quantity to trade
            price: Order price (required for limit orders)
            stop_price: Stop price (for stop orders)
            time_in_force: GTC, IOC, FOK
            is_isolated: Whether to use isolated margin
            quote_order_qty: Quote quantity (for market orders)
            new_client_order_id: Client order ID
            
        Returns:
            Order response
        """
        params = {
            "symbol": symbol,
            "side": side,
            "type": order_type
        }
        
        # Add timeInForce only for limit orders
        if order_type == "LIMIT" and time_in_force:
            params["timeInForce"] = time_in_force
        
        # Add quantity or quoteOrderQty (but not both)
        if quantity is not None:
            params["quantity"] = f"{quantity}"
        elif quote_order_qty is not None:
            params["quoteOrderQty"] = f"{quote_order_qty}"
        
        # Add price for limit orders
        if price is not None:
            params["price"] = f"{price}"
        
        # Add stopPrice for stop orders
        if stop_price is not None:
            params["stopPrice"] = f"{stop_price}"
        
        # Add isolated margin flag
        if is_isolated:
            params["isIsolated"] = "TRUE"
        
        # Add client order ID if provided
        if new_client_order_id:
            params["newClientOrderId"] = new_client_order_id
        
        return await self._run_client_method('new_margin_order', **params)

class AsyncBinanceConnectorAPI:
    """
    Asynchronous Binance API client using the official Binance Connector.
    
    Provides methods to interact with Binance's API endpoints for various purposes
    including getting market data, managing orders, and accessing account information.
    """
    
    def __init__(
        self,
        api_key: str = None,
        api_secret: str = None,
        base_url: str = "https://api.binance.com",
        timeout: int = 10,
        proxies: Dict[str, str] = None
    ):
        """
        Initialize the Binance API client.
        
        Args:
            api_key: Binance API key (optional, will use env var if not provided)
            api_secret: Binance API secret (optional, will use env var if not provided)
            base_url: API base URL
            timeout: Request timeout in seconds
            proxies: Proxy configuration
        """
        # Get API credentials from environment if not provided
        self.api_key = api_key or os.getenv("BINANCE_API_KEY", "")
        self.api_secret = api_secret or os.getenv("BINANCE_API_SECRET", "")
        
        # Initialize the client
        self.client = AsyncBinanceConnectorClient(
            api_key=self.api_key,
            api_secret=self.api_secret,
            base_url=base_url,
            timeout=timeout,
            proxies=proxies,
            show_limit_usage=True
        )
        
        logger.debug("Initialized AsyncBinanceConnectorAPI")
        
    async def _process_response(self, response: Any) -> Tuple[bool, Any, str]:
        """
        Process API response.
        
        Args:
            response: API response
            
        Returns:
            Tuple of (success, data, error_message)
        """
        if isinstance(response, dict) and response.get("error", False):
            return False, None, response.get("msg", "Unknown error")
            
        return True, response, None
    
    # Market Data Methods
    
    async def get_ticker(self, symbol: str = "BTCUSDT") -> Dict[str, Any]:
        """
        Get symbol price ticker.
        
        Args:
            symbol: Trading pair symbol (e.g., BTCUSDT)
        
        Returns:
            Ticker data
        """
        response = await self.client.get_ticker(symbol)
        success, data, error = await self._process_response(response)
        
        if not success:
            logger.warning(f"Failed to get ticker for {symbol}: {error}")
            return {"error": True, "msg": error}
            
        return {"code": "200000", "data": data}  # Mimicking your current response format
    
    async def get_ticker_24hr(self, symbol: str = "BTCUSDT") -> Dict[str, Any]:
        """
        Get 24-hour statistics for a symbol.
        
        Args:
            symbol: Trading pair symbol (e.g., BTCUSDT)
            
        Returns:
            24-hour trading statistics
        """
        response = await self.client.get_ticker_24hr(symbol)
        success, data, error = await self._process_response(response)
        
        if not success:
            logger.warning(f"Failed to get 24hr stats for {symbol}: {error}")
            return {"error": True, "msg": error}
            
        return {"code": "200000", "data": data}
    
    async def get_exchange_info(self) -> Dict[str, Any]:
        """
        Get exchange trading rules and symbol information.
        
        Returns:
            Exchange information
        """
        response = await self.client.get_exchange_info()
        success, data, error = await self._process_response(response)
        
        if not success:
            logger.warning(f"Failed to get exchange info: {error}")
            return {"error": True, "msg": error}
            
        return {"code": "200000", "data": data}
    
    # Account Methods
    
    @require_api_key
    async def get_margin_account(self) -> Dict[str, Any]:
        """
        Get cross margin account details.
        
        Returns:
            Cross margin account information
        """
        response = await self.client._run_client_method('margin_account')
        success, data, error = await self._process_response(response)
        
        if not success:
            logger.warning(f"Failed to get margin account: {error}")
            return {"error": True, "msg": error}
            
        return {"code": "200000", "data": data}
    
    @require_api_key
    async def get_isolated_margin_account(self, symbols: Optional[str] = None) -> Dict[str, Any]:
        """
        Get isolated margin account details.
        
        Args:
            symbols: List of trading pairs as a single string (e.g., "BTCUSDT,ETHUSDT")
            
        Returns:
            Isolated margin account information
        """
        params = {}
        if symbols:
            params["symbols"] = symbols
            
        response = await self.client._run_client_method('isolated_margin_account', **params)
        success, data, error = await self._process_response(response)
        
        if not success:
            logger.warning(f"Failed to get isolated margin account: {error}")
            return {"error": True, "msg": error}
            
        return {"code": "200000", "data": data}
    
    # Order Methods
    
    @require_api_key
    async def create_margin_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: Optional[float] = None,
        price: Optional[float] = None,
        stop_price: Optional[float] = None,
        time_in_force: Optional[str] = None,
        is_isolated: bool = False,
        quote_order_qty: Optional[float] = None,
        new_client_order_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new margin order.
        
        Args:
            symbol: Trading pair symbol (e.g., BTCUSDT)
            side: BUY or SELL
            order_type: LIMIT, MARKET, STOP_LOSS, etc.
            quantity: Quantity to trade
            price: Order price (required for limit orders)
            stop_price: Stop price (for stop orders)
            time_in_force: GTC, IOC, FOK
            is_isolated: Whether to use isolated margin
            quote_order_qty: Quote quantity (for market orders)
            new_client_order_id: Client order ID
            
        Returns:
            Order response
        """
        params = {
            "symbol": symbol,
            "side": side,
            "type": order_type
        }
        
        # Add timeInForce only for limit orders
        if order_type == "LIMIT" and time_in_force:
            params["timeInForce"] = time_in_force
        
        # Add quantity or quoteOrderQty (but not both)
        if quantity is not None:
            params["quantity"] = f"{quantity}"
        elif quote_order_qty is not None:
            params["quoteOrderQty"] = f"{quote_order_qty}"
        
        # Add price for limit orders
        if price is not None:
            params["price"] = f"{price}"
        
        # Add stopPrice for stop orders
        if stop_price is not None:
            params["stopPrice"] = f"{stop_price}"
        
        # Add isolated margin flag
        if is_isolated:
            params["isIsolated"] = "TRUE"
        
        # Add client order ID if provided
        if new_client_order_id:
            params["newClientOrderId"] = new_client_order_id
        
        response = await self.client._run_client_method('new_margin_order', **params)
        success, data, error = await self._process_response(response)
        
        if not success:
            logger.warning(f"Failed to create margin order: {error}")
            return {"error": True, "msg": error}
            
        return {"code": "200000", "data": data}
    
    @require_api_key
    async def place_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: Optional[float] = None,
        price: Optional[float] = None,
        time_in_force: Optional[str] = "GTC",
        quote_order_qty: Optional[float] = None,
        new_client_order_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Place a regular spot order.
        
        Args:
            symbol: Trading pair symbol (e.g., BTCUSDT)
            side: BUY or SELL
            order_type: LIMIT, MARKET, etc.
            quantity: Quantity to trade
            price: Order price (required for limit orders)
            time_in_force: GTC, IOC, FOK
            quote_order_qty: Quote quantity (for market orders)
            new_client_order_id: Client order ID
            
        Returns:
            Order response
        """
        params = {
            "symbol": symbol,
            "side": side,
            "type": order_type
        }
        
        # Add timeInForce only for limit orders
        if order_type == "LIMIT" and time_in_force:
            params["timeInForce"] = time_in_force
        
        # Add quantity or quoteOrderQty (but not both)
        if quantity is not None:
            params["quantity"] = f"{quantity}"
        elif quote_order_qty is not None:
            params["quoteOrderQty"] = f"{quote_order_qty}"
        
        # Add price for limit orders
        if price is not None:
            params["price"] = f"{price}"
        
        # Add client order ID if provided
        if new_client_order_id:
            params["newClientOrderId"] = new_client_order_id
        
        response = await self.client._run_client_method('new_order', **params)
        success, data, error = await self._process_response(response)
        
        if not success:
            logger.warning(f"Failed to place order: {error}")
            return {"error": True, "msg": error}
            
        return {"code": "200000", "data": data}
    
    @require_api_key
    async def cancel_order(
        self,
        symbol: str,
        order_id: Optional[int] = None,
        orig_client_order_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Cancel an existing order.
        
        Args:
            symbol: Trading pair symbol (e.g., BTCUSDT)
            order_id: Order ID to cancel
            orig_client_order_id: Original client order ID
            
        Returns:
            Cancellation response
        """
        params = {
            "symbol": symbol
        }
        
        if order_id:
            params["orderId"] = order_id
        elif orig_client_order_id:
            params["origClientOrderId"] = orig_client_order_id
        else:
            return {"error": True, "msg": "Either orderId or origClientOrderId must be provided"}
        
        response = await self.client._run_client_method('cancel_order', **params)
        success, data, error = await self._process_response(response)
        
        if not success:
            logger.warning(f"Failed to cancel order: {error}")
            return {"error": True, "msg": error}
            
        return {"code": "200000", "data": data}


class BinanceConnectorAPI:
    """
    Backward compatibility wrapper for the AsyncBinanceConnectorAPI.
    Allows existing code to use the new async implementation synchronously.
    """
    
    def __init__(
        self,
        api_key: str = None,
        api_secret: str = None,
        base_url: str = "https://api.binance.com",
        timeout: int = 10,
        proxies: Dict[str, str] = None
    ):
        """
        Initialize the backward compatibility wrapper.
        
        Args:
            api_key: Binance API key
            api_secret: Binance API secret
            base_url: API base URL
            timeout: Request timeout in seconds
            proxies: Proxy configuration
        """
        # Store credentials
        self.api_key = api_key or os.getenv("BINANCE_API_KEY", "")
        self.api_secret = api_secret or os.getenv("BINANCE_API_SECRET", "")
        
        # Initialize async client
        self.async_api = AsyncBinanceConnectorAPI(
            api_key=self.api_key,
            api_secret=self.api_secret,
            base_url=base_url,
            timeout=timeout,
            proxies=proxies
        )
    
    def _run_async(self, coroutine):
        """Helper to run async functions synchronously"""
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Create a new event loop if the current one is already running
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
        return loop.run_until_complete(coroutine)
    
    # Market Data Methods
    
    def get_ticker(self, symbol: str = "BTCUSDT") -> Dict[str, Any]:
        """Get ticker information for a symbol"""
        return self._run_async(self.async_api.get_ticker(symbol))
    
    def get_ticker_24hr(self, symbol: str = "BTCUSDT") -> Dict[str, Any]:
        """Get 24-hour statistics for a symbol"""
        return self._run_async(self.async_api.get_ticker_24hr(symbol))
    
    def get_exchange_info(self) -> Dict[str, Any]:
        """Get exchange trading rules and symbol information"""
        return self._run_async(self.async_api.get_exchange_info())
    
    # Account Methods
    
    def get_margin_account(self) -> Dict[str, Any]:
        """Get cross margin account details"""
        return self._run_async(self.async_api.get_margin_account())
    
    def get_isolated_margin_account(self, symbols: Optional[str] = None) -> Dict[str, Any]:
        """Get isolated margin account details"""
        return self._run_async(self.async_api.get_isolated_margin_account(symbols))
    
    # Order Methods
    
    def create_margin_order(self, **kwargs) -> Dict[str, Any]:
        """Create a new margin order"""
        return self._run_async(self.async_api.create_margin_order(**kwargs))
    
    def place_order(self, **kwargs) -> Dict[str, Any]:
        """Place a regular spot order"""
        return self._run_async(self.async_api.place_order(**kwargs))
    
    def cancel_order(self, **kwargs) -> Dict[str, Any]:
        """Cancel an existing order"""
        return self._run_async(self.async_api.cancel_order(**kwargs))