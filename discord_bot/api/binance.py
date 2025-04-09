"""
Asynchronous implementation of the Binance API client.
Handles authentication, request signing, and provides access to
Binance API endpoints including market data, trading, and margin operations.
"""

import os
import hmac
import hashlib
import time
import urllib.parse
from typing import Dict, List, Any, Optional, Tuple
from loguru import logger

from .base import AsyncBaseAPI, require_api_key, ApiKeyRequiredError


class AsyncBinanceClient(AsyncBaseAPI):
    """
    Base class for Binance API authentication and signing.
    Handles the common authentication logic for all Binance API requests.
    """
    
    def __init__(
        self,
        api_key: str,
        api_secret: str
    ):
        """
        Initialize the Binance API client with authentication credentials.
        
        Args:
            api_key: Binance API key
            api_secret: Binance API secret
        """
        # Initialize base class
        super().__init__(
            base_url="https://api.binance.com",
            api_key=api_key
        )
        
        self.api_secret = api_secret
        
        logger.debug("Initialized AsyncBinanceClient")
        
        if not all([api_key, api_secret]):
            logger.warning("API credentials are empty. Access is restricted to public endpoints only.")
            print(self.api_secret, self.api_key)
            print("hi")
    
    def _generate_signature(self, query_string: str) -> str:
        """
        Generate HMAC-SHA256 signature for Binance API requests.
        
        Args:
            query_string: Query string to sign
            
        Returns:
            Signature as hexadecimal string
        """
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return signature
    
    async def public_request(
        self,
        endpoint: str,
        params: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Make a public request to the Binance API (no authentication required).
        
        Args:
            endpoint: API endpoint
            params: Query parameters
            
        Returns:
            API response
        """
        return await self.get(endpoint, params=params)
    
    async def signed_request(
        self,
        method: str,
        endpoint: str,
        params: Dict[str, Any] = None,
        data: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Make a signed request to the Binance API.
        
        Args:
            method: HTTP method (GET, POST, DELETE, etc.)
            endpoint: API endpoint
            params: Query parameters
            data: Request body
            
        Returns:
            API response
        """
        # Prepare parameters
        params = params or {}
        
        # Add timestamp for signature
        params['timestamp'] = int(time.time() * 1000)
        
        # Build query string
        query_string = urllib.parse.urlencode(params)
        
        # Generate signature
        signature = self._generate_signature(query_string)
        
        # Add signature to parameters
        params['signature'] = signature
        
        # Prepare headers
        headers = {"X-MBX-APIKEY": self.api_key}
        
        # Make the request based on HTTP method
        if method == 'GET':
            return await self.get(endpoint, params=params, headers=headers)
        elif method == 'POST':
            return await self.post(endpoint, params=params, headers=headers)
        elif method == 'DELETE':
            return await self.request(method='DELETE', endpoint=endpoint, params=params, headers=headers)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")


class AsyncBinanceAPI:
    """
    Asynchronous Binance API client for trading and account management.
    
    Provides methods to interact with Binance's API endpoints for various purposes
    including getting market data, managing orders, and accessing account information.
    """
    
    def __init__(
        self,
        api_key: str = None,
        api_secret: str = None
    ):
        """
        Initialize the Binance API client.
        
        Args:
            api_key: Binance API key (optional, will use env var if not provided)
            api_secret: Binance API secret (optional, will use env var if not provided)
        """
        # Get API credentials from environment if not provided
        self.api_key = api_key or os.getenv("BINANCE_API_KEY", "")
        self.api_secret = api_secret or os.getenv("BINANCE_API_SECRET", "")
        
        # Initialize the client
        self.client = AsyncBinanceClient(
            api_key=self.api_key,
            api_secret=self.api_secret
        )
        
        logger.debug("Initialized AsyncBinanceAPI")
    
    ###################
    # MARKET DATA API #
    ###################
    
    async def get_ticker(self, symbol: str = "BTCUSDT") -> Dict[str, Any]:
        """
        Get symbol price ticker.
        
        Args:
            symbol: Trading pair symbol (e.g., BTCUSDT)
        
        Returns:
            Ticker data including price
        """
        return await self.client.public_request(
            endpoint="/api/v3/ticker/price",
            params={"symbol": symbol}
        )
    
    async def get_ticker_24hr(self, symbol: str = "BTCUSDT") -> Dict[str, Any]:
        """
        Get 24-hour statistics for a symbol.
        
        Args:
            symbol: Trading pair symbol (e.g., BTCUSDT)
            
        Returns:
            24-hour trading statistics including volume and price changes
        """
        return await self.client.public_request(
            endpoint="/api/v3/ticker/24hr",
            params={"symbol": symbol}
        )
    
    async def get_exchange_info(self) -> Dict[str, Any]:
        """
        Get exchange trading rules and symbol information.
        
        Returns:
            Exchange information including trading pairs and rules
        """
        return await self.client.public_request(
            endpoint="/api/v3/exchangeInfo"
        )
    
    ###################
    # MARGIN API      #
    ###################
    
    @require_api_key
    async def get_margin_account(self) -> Dict[str, Any]:
        """
        Get cross margin account details.
        
        Returns:
            Cross margin account information
        """
        return await self.client.signed_request(
            method="GET",
            endpoint="/sapi/v1/margin/account"
        )
    
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
            
        return await self.client.signed_request(
            method="GET",
            endpoint="/sapi/v1/margin/isolated/account",
            params=params
        )
    
    @require_api_key
    async def get_margin_open_orders(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        """
        Get margin open orders.
        
        Args:
            symbol: Trading pair symbol (e.g., BTCUSDT)
            
        Returns:
            List of open margin orders
        """
        params = {}
        if symbol:
            params["symbol"] = symbol
            
        return await self.client.signed_request(
            method="GET",
            endpoint="/sapi/v1/margin/openOrders",
            params=params
        )
    
    @require_api_key
    async def get_margin_pairs(self) -> Dict[str, Any]:
        """
        Get all cross margin pairs.
        
        Returns:
            List of all cross margin pairs
        """
        # This endpoint requires the API key but doesn't need signing
        headers = {"X-MBX-APIKEY": self.api_key}
        return await self.client.get(
            endpoint="/sapi/v1/margin/allPairs",
            headers=headers
        )
    
    @require_api_key
    async def get_isolated_margin_pairs(self) -> Dict[str, Any]:
        """
        Get all isolated margin pairs.
        
        Returns:
            List of all isolated margin pairs
        """
        return await self.client.public_request(
            endpoint="/sapi/v1/margin/isolated/allPairs"
        )
    
    ###################
    # ORDER API       #
    ###################
    

    # Updated method in AsyncBinanceAPI class
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
        """Create a new margin order."""
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
        
        return await self.client.signed_request(
            method="POST",
            endpoint="/sapi/v1/margin/order",
            params=params
        )

    @require_api_key
    async def cancel_margin_order(
        self,
        symbol: str,
        order_id: Optional[int] = None,
        orig_client_order_id: Optional[str] = None,
        is_isolated: bool = False
    ) -> Dict[str, Any]:
        """
        Cancel a margin order.
        
        Args:
            symbol: Trading pair symbol (e.g., BTCUSDT)
            order_id: Order ID to cancel
            orig_client_order_id: Original client order ID
            is_isolated: Whether the order is in isolated margin
            
        Returns:
            Cancellation response
        """
        params = {
            "symbol": symbol,
            "isIsolated": "TRUE" if is_isolated else "FALSE"
        }
        
        if order_id:
            params["orderId"] = order_id
            
        if orig_client_order_id:
            params["origClientOrderId"] = orig_client_order_id
            
        return await self.client.signed_request(
            method="DELETE",
            endpoint="/sapi/v1/margin/order",
            params=params
        )
    
    @require_api_key
    async def get_margin_order(
        self,
        symbol: str,
        order_id: Optional[int] = None,
        orig_client_order_id: Optional[str] = None,
        is_isolated: bool = False
    ) -> Dict[str, Any]:
        """
        Query margin order status.
        
        Args:
            symbol: Trading pair symbol (e.g., BTCUSDT)
            order_id: Order ID to query
            orig_client_order_id: Original client order ID
            is_isolated: Whether the order is in isolated margin
            
        Returns:
            Order information
        """
        params = {
            "symbol": symbol,
            "isIsolated": "TRUE" if is_isolated else "FALSE"
        }
        
        if order_id:
            params["orderId"] = order_id
            
        if orig_client_order_id:
            params["origClientOrderId"] = orig_client_order_id
            
        return await self.client.signed_request(
            method="GET",
            endpoint="/sapi/v1/margin/order",
            params=params
        )
    
    ###################
    # BORROW/REPAY API #
    ###################
    
    @require_api_key
    async def margin_borrow(
        self,
        asset: str,
        amount: float,
        symbol: Optional[str] = None,
        is_isolated: bool = False
    ) -> Dict[str, Any]:
        """
        Borrow asset in cross or isolated margin.
        
        Args:
            asset: Asset to borrow (e.g., BTC)
            amount: Amount to borrow
            symbol: Trading pair symbol, required for isolated margin
            is_isolated: Whether to borrow in isolated margin
            
        Returns:
            Transaction ID
        """
        params = {
            "asset": asset,
            "amount": amount
        }
        
        if is_isolated:
            if not symbol:
                raise ValueError("Symbol is required for isolated margin borrowing")
            params["isIsolated"] = "TRUE"
            params["symbol"] = symbol
            
        return await self.client.signed_request(
            method="POST",
            endpoint="/sapi/v1/margin/loan",
            params=params
        )
    
    @require_api_key
    async def margin_repay(
        self,
        asset: str,
        amount: float,
        symbol: Optional[str] = None,
        is_isolated: bool = False
    ) -> Dict[str, Any]:
        """
        Repay asset in cross or isolated margin.
        
        Args:
            asset: Asset to repay (e.g., BTC)
            amount: Amount to repay
            symbol: Trading pair symbol, required for isolated margin
            is_isolated: Whether to repay in isolated margin
            
        Returns:
            Transaction ID
        """
        params = {
            "asset": asset,
            "amount": amount
        }
        
        if is_isolated:
            if not symbol:
                raise ValueError("Symbol is required for isolated margin repayment")
            params["isIsolated"] = "TRUE"
            params["symbol"] = symbol
            
        return await self.client.signed_request(
            method="POST",
            endpoint="/sapi/v1/margin/repay",
            params=params
        )

# Backward compatibility wrapper for synchronous use
class BinanceAPI:
    """
    Backward compatibility wrapper for the AsyncBinanceAPI.
    Allows existing code to use the new async implementation synchronously.
    """
    
    def __init__(
        self,
        api_key: str = None,
        api_secret: str = None
    ):
        """
        Initialize the backward compatibility wrapper.
        
        Args:
            api_key: Binance API key
            api_secret: Binance API secret
        """
        import asyncio
        
        # Store credentials
        self.api_key = api_key or os.getenv("BINANCE_API_KEY", "")
        self.api_secret = api_secret or os.getenv("BINANCE_API_SECRET", "")
        
        # Initialize async client
        self.async_api = AsyncBinanceAPI(
            api_key=self.api_key,
            api_secret=self.api_secret
        )
    
    def _run_async(self, coroutine):
        """Helper to run async functions synchronously"""
        import asyncio
        
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Create a new event loop if the current one is already running
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
        return loop.run_until_complete(coroutine)
    
    # Implement synchronous wrappers for async methods
    def get_ticker(self, symbol: str = "BTCUSDT") -> Dict[str, Any]:
        """Get ticker information for a symbol"""
        return self._run_async(self.async_api.get_ticker(symbol))
    
    def get_ticker_24hr(self, symbol: str = "BTCUSDT") -> Dict[str, Any]:
        """Get 24-hour statistics for a symbol"""
        return self._run_async(self.async_api.get_ticker_24hr(symbol))
    
    def get_margin_account(self) -> Dict[str, Any]:
        """Get cross margin account details"""
        return self._run_async(self.async_api.get_margin_account())
    
    def get_isolated_margin_account(self, symbols: Optional[str] = None) -> Dict[str, Any]:
        """Get isolated margin account details"""
        return self._run_async(self.async_api.get_isolated_margin_account(symbols))
    
    def create_margin_order(self, **kwargs) -> Dict[str, Any]:
        """Create a new margin order"""
        return self._run_async(self.async_api.create_margin_order(**kwargs))
    
    def cancel_margin_order(self, **kwargs) -> Dict[str, Any]:
        """Cancel a margin order"""
        return self._run_async(self.async_api.cancel_margin_order(**kwargs))
    
    def margin_borrow(self, **kwargs) -> Dict[str, Any]:
        """Borrow asset in margin account"""
        return self._run_async(self.async_api.margin_borrow(**kwargs))
    
    def margin_repay(self, **kwargs) -> Dict[str, Any]:
        """Repay asset in margin account"""
        return self._run_async(self.async_api.margin_repay(**kwargs))