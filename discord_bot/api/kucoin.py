"""
Asynchronous implementation of the KuCoin API client.
Handles authentication, request signing, and provides access to
all KuCoin API endpoints including market data, trading, and account management.
"""

import os
import base64
import hashlib
import hmac
import json
import time
import uuid
from typing import Dict, Any, Tuple
from loguru import logger
import asyncio
from discord_bot.api.base import AsyncBaseAPI, require_api_key, ApiKeyRequiredError


class AsyncKucoinClient(AsyncBaseAPI):
    """
    Base class for KuCoin API authentication and signing.
    Handles the common authentication logic for all KuCoin API requests.
    """
    
    def __init__(
        self,
        api_key: str,
        api_secret: str,
        api_passphrase: str
    ):
        """
        Initialize the KuCoin API client with authentication credentials.
        
        Args:
            api_key: KuCoin API key
            api_secret: KuCoin API secret
            api_passphrase: KuCoin API passphrase
        """
        # Initialize base class
        super().__init__(
            base_url="https://api.kucoin.com",
            api_key=api_key
        )
        
        self.api_secret = api_secret
        
        # Sign the passphrase if credentials are provided
        if api_passphrase and api_secret:
            self.api_passphrase = self.sign(
                api_passphrase.encode('utf-8'), 
                api_secret.encode('utf-8')
            )
        else:
            self.api_passphrase = api_passphrase or ""
        
        logger.debug("Initialized AsyncKucoinClient")
        
        if not all([api_key, api_secret, api_passphrase]):
            logger.warning("API token is empty. Access is restricted to public interfaces only.")
    
    def sign(self, plain: bytes, key: bytes) -> str:
        """
        Create HMAC SHA256 signature encoded as base64.
        
        Args:
            plain: Data to sign
            key: Key to use for signing
            
        Returns:
            Base64 encoded signature
        """
        hm = hmac.new(key, plain, hashlib.sha256)
        return base64.b64encode(hm.digest()).decode()
    
    def get_auth_headers(self, payload: str) -> Dict[str, str]:
        """
        Generate headers required for KuCoin API authentication.
        
        Args:
            payload: String containing method + endpoint + body
            
        Returns:
            Dictionary of headers for API authentication
        """
        timestamp = str(int(time.time() * 1000))
        signature = self.sign(
            (timestamp + payload).encode('utf-8'), 
            self.api_secret.encode('utf-8')
        )
        
        return {
            "KC-API-KEY": self.api_key,
            "KC-API-PASSPHRASE": self.api_passphrase,
            "KC-API-TIMESTAMP": timestamp,
            "KC-API-SIGN": signature,
            "KC-API-KEY-VERSION": "2"
        }
    
    async def authenticated_request(
        self,
        method: str,
        endpoint: str,
        params: Dict[str, Any] = None,
        data: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Make an authenticated request to the KuCoin API.
        
        Args:
            method: HTTP method (GET, POST, DELETE, etc.)
            endpoint: API endpoint
            params: Query parameters
            data: Request body
            
        Returns:
            API response
        """
        # Build the endpoint with query parameters if provided
        query_string = ""
        if params:
            import urllib.parse
            query_string = urllib.parse.urlencode(params)
            endpoint_with_query = f"{endpoint}?{query_string}"
        else:
            endpoint_with_query = endpoint
        
        # Prepare the payload for signing
        body_str = json.dumps(data) if data else ""
        payload = method + endpoint_with_query + body_str
        
        # Get authentication headers
        auth_headers = self.get_auth_headers(payload)
        
        # Add content type header if there's a body
        if data:
            auth_headers["Content-Type"] = "application/json"
        
        # Make the request
        return await self.request(
            method=method,
            endpoint=endpoint,
            params=params,
            data=data,
            headers=auth_headers
        )
    
    async def public_request(
        self,
        endpoint: str,
        params: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Make a public request to the KuCoin API (no authentication required).
        
        Args:
            endpoint: API endpoint
            params: Query parameters
            
        Returns:
            API response
        """
        return await self.get(endpoint, params=params)


class AsyncKucoinAPI:
    """
    Asynchronous KuCoin API client for trading and account management.
    
    Provides methods to interact with KuCoin's API endpoints for various purposes
    including getting market data, managing orders, and accessing account information.
    """
    
    def __init__(
        self,
        api_key: str = None,
        api_secret: str = None,
        passphrase: str = None
    ):
        """
        Initialize the KuCoin API client.
        
        Args:
            api_key: KuCoin API key (optional, will use env var if not provided)
            api_secret: KuCoin API secret (optional, will use env var if not provided)
            passphrase: KuCoin API passphrase (optional, will use env var if not provided)
        """
        # Get API credentials from environment if not provided
        self.api_key = api_key or os.getenv("KUCOIN_API_KEY", "")
        self.api_secret = api_secret or os.getenv("KUCOIN_API_SECRET", "")
        self.passphrase = passphrase or os.getenv("KUCOIN_API_PASSPHRASE", "")
        
        # Initialize the client
        self.client = AsyncKucoinClient(
            api_key=self.api_key,
            api_secret=self.api_secret,
            api_passphrase=self.passphrase
        )
        
        logger.debug("Initialized AsyncKucoinAPI")
    
    async def _process_response(
        self,
        response: Dict[str, Any],
        error_key: str = "msg"
    ) -> Tuple[bool, Any, str]:
        """
        Process KuCoin API response.
        
        Args:
            response: API response
            error_key: Key for error message
            
        Returns:
            Tuple of (success, data, error_message)
        """
        if not response:
            return False, None, "No response received"
        
        # Check for KuCoin success code
        if response.get("code") == "200000":
            return True, response.get("data"), None
        
        # Extract error message
        error_msg = response.get(error_key, "Unknown error")
        code = response.get("code", "Unknown code")
        
        return False, None, f"Error {code}: {error_msg}"
    
    ###################
    # MARKET DATA API #
    ###################
    
    async def get_ticker(self, symbol: str = "BTC-USDT") -> Dict[str, Any]:
        """
        Get level 1 orderbook data (ticker) for a symbol.
        
        Args:
            symbol: Trading pair symbol (e.g., BTC-USDT)
        
        Returns:
            Ticker data including best bid/ask price and size
        """
        response = await self.client.public_request(
            endpoint="/api/v1/market/orderbook/level1",
            params={"symbol": symbol}
        )
        
        success, data, error = await self._process_response(response)
        if not success:
            logger.warning(f"Failed to get ticker for {symbol}: {error}")
            return {"code": response.get("code", "999999"), "msg": error}
        
        return {"code": "200000", "data": data}
    
    async def get_market_list(self) -> Dict[str, Any]:
        """
        Get list of available trading pairs.
        
        Returns:
            List of available symbols and their metadata
        """
        response = await self.client.public_request(
            endpoint="/api/v1/symbols"
        )
        
        success, data, error = await self._process_response(response)
        if not success:
            logger.warning(f"Failed to get market list: {error}")
            return {"code": response.get("code", "999999"), "msg": error}
        
        return {"code": "200000", "data": data}
    
    async def get_24h_stats(self, symbol: str = "BTC-USDT") -> Dict[str, Any]:
        """
        Get 24-hour statistics for a symbol.
        
        Args:
            symbol: Trading pair symbol (e.g., BTC-USDT)
            
        Returns:
            24-hour trading statistics including volume and price changes
        """
        response = await self.client.public_request(
            endpoint="/api/v1/market/stats",
            params={"symbol": symbol}
        )
        
        success, data, error = await self._process_response(response)
        if not success:
            logger.warning(f"Failed to get 24h stats for {symbol}: {error}")
            return {"code": response.get("code", "999999"), "msg": error}
        
        return {"code": "200000", "data": data}
    
    ###################
    # TRADE FEES API  #
    ###################
    
    @require_api_key
    async def get_trade_fees(self, symbols: str = "BTC-USDT") -> Dict[str, Any]:
        """
        Get trade fees for specific symbols.
        
        Args:
            symbols: Comma-separated trading pair symbols (e.g., "BTC-USDT,ETH-USDT")
            
        Returns:
            Dictionary containing fee information for the requested symbols
        """
        response = await self.client.authenticated_request(
            method="GET",
            endpoint="/api/v1/trade-fees",
            params={"symbols": symbols}
        )
        
        success, data, error = await self._process_response(response)
        if not success:
            logger.warning(f"Failed to get trade fees for {symbols}: {error}")
            return {"code": response.get("code", "999999"), "msg": error}
        
        return {"code": "200000", "data": data}
    
    ###################
    # ACCOUNT API     #
    ###################
    
    @require_api_key
    async def get_account_list(
        self,
        currency: str = None,
        account_type: str = None
    ) -> Dict[str, Any]:
        """
        Get list of accounts with optional filtering.
        
        Args:
            currency: Filter accounts by currency (e.g., 'BTC', 'USDT')
            account_type: Filter by account type ('main', 'trade', 'margin', etc.)
                
        Returns:
            List of accounts with balance information
        """
        params = {}
        if currency:
            params["currency"] = currency
        if account_type:
            params["type"] = account_type
            
        response = await self.client.authenticated_request(
            method="GET",
            endpoint="/api/v1/accounts",
            params=params
        )
        
        success, data, error = await self._process_response(response)
        if not success:
            logger.warning(f"Failed to get account list: {error}")
            return {"code": response.get("code", "999999"), "msg": error}
        
        return {"code": "200000", "data": data}
    
    ###################
    # MARGIN API      #
    ###################
    
    @require_api_key
    async def get_isolated_margin_accounts(
        self,
        symbol: str = None,
        quote_currency: str = "USDT",
        query_type: str = "ISOLATED"
    ) -> Dict[str, Any]:
        """
        Get isolated margin account information.
        
        Args:
            symbol: Trading pair symbol (optional)
            quote_currency: Quote currency, e.g., USDT (default)
            query_type: Account type - "ISOLATED" (default), "ISOLATED_V2", or "ALL"
                
        Returns:
            Isolated margin account data including assets and liabilities
        """
        params = {
            "quoteCurrency": quote_currency,
            "queryType": query_type
        }
        
        if symbol:
            params["symbol"] = symbol
            
        response = await self.client.authenticated_request(
            method="GET",
            endpoint="/api/v3/isolated/accounts",
            params=params
        )
        
        success, data, error = await self._process_response(response)
        if not success:
            logger.warning(f"Failed to get isolated margin accounts: {error}")
            return {"code": response.get("code", "999999"), "msg": error}
        
        return {"code": "200000", "data": data}
    
    ###################
    # ORDER API       #
    ###################
    
    @require_api_key
    async def add_margin_order(
        self,
        symbol: str,
        side: str,
        client_oid: str = None,
        order_type: str = "limit",
        price: str = None,
        size: str = None,
        funds: str = None,
        is_isolated: bool = False,
        auto_borrow: bool = False,
        auto_repay: bool = False,
        time_in_force: str = "GTC"
    ) -> Dict[str, Any]:
        """
        Place an order in the margin trading system (cross or isolated).
        
        Args:
            symbol: Trading pair symbol (e.g., BTC-USDT)
            side: 'buy' or 'sell'
            client_oid: Client-generated order ID (recommended to use UUID)
            order_type: Order type - 'limit' or 'market'
            price: Price for limit orders
            size: Quantity to buy/sell
            funds: Funds to use (for market orders, alternative to size)
            is_isolated: True for isolated margin, False for cross margin
            auto_borrow: Whether to auto-borrow if insufficient balance
            auto_repay: Whether to auto-repay when closing position
            time_in_force: Order timing strategy - 'GTC', 'GTT', 'IOC', 'FOK'
            
        Returns:
            Order response including orderId, clientOid, etc.
        """
        # Prepare order data
        data = {
            "symbol": symbol,
            "side": side,
            "clientOid": client_oid or str(uuid.uuid4()),
            "type": order_type,
            "isIsolated": is_isolated,
            "autoBorrow": auto_borrow,
            "autoRepay": auto_repay
        }
        
        # Add parameters based on order type
        if order_type == "limit":
            if price is None:
                raise ValueError("Price is required for limit orders")
            if size is None:
                raise ValueError("Size is required for limit orders")
            
            data["price"] = str(price)
            data["size"] = str(size)
            
            # Add time in force for limit orders
            if time_in_force:
                data["timeInForce"] = time_in_force
        
        elif order_type == "market":
            # For market orders, either size or funds must be provided
            if size is not None:
                data["size"] = str(size)
            elif funds is not None:
                data["funds"] = str(funds)
            else:
                raise ValueError("Either size or funds must be provided for market orders")
        
        # Make the API request
        response = await self.client.authenticated_request(
            method="POST",
            endpoint="/api/v3/hf/margin/order",
            data=data
        )
        
        success, api_data, error = await self._process_response(response)
        if not success:
            logger.warning(f"Failed to place margin order: {error}")
            return {"code": response.get("code", "999999"), "msg": error}
        
        return {"code": "200000", "data": api_data}
    
    @require_api_key
    async def cancel_order_by_id(self, order_id: str) -> Dict[str, Any]:
        """
        Cancel a single order by its order ID.
        
        Args:
            order_id: The unique order ID assigned by the server
                
        Returns:
            Cancellation response
        """
        response = await self.client.authenticated_request(
            method="DELETE",
            endpoint=f"/api/v1/orders/{order_id}"
        )
        
        success, data, error = await self._process_response(response)
        if not success:
            logger.warning(f"Failed to cancel order {order_id}: {error}")
            return {"code": response.get("code", "999999"), "msg": error}
        
        return {"code": "200000", "data": data}
    
    ###################
    # TRADE HISTORY   #
    ###################
    
    @require_api_key
    async def get_filled_list(
        self,
        symbol: str = None,
        order_id: str = None,
        side: str = None,
        order_type: str = None,
        start_at: int = None,
        end_at: int = None,
        trade_type: str = "TRADE",
        limit: int = None,
        current_page: int = None
    ) -> Dict[str, Any]:
        """
        Get the recent fills (order execution history).
        
        Args:
            symbol: Limit the list of fills to this symbol
            order_id: Limit the list of fills to this orderId
            side: 'buy' or 'sell'
            order_type: 'limit', 'market', 'limit_stop' or 'market_stop'
            start_at: Start time in milliseconds
            end_at: End time in milliseconds
            trade_type: Type of trading, default is "TRADE" (Spot Trading)
                      Options: "TRADE", "MARGIN_TRADE", "MARGIN_ISOLATED_TRADE"
            limit: Number of results per request
            current_page: Current page number
                
        Returns:
            Fills data including pagination info
        """
        # Construct query parameters
        params = {}
        
        # Add parameters only if they are provided and not None
        if order_id:
            params["orderId"] = order_id
        if symbol:
            params["symbol"] = symbol
        if side:
            params["side"] = side
        if order_type:
            params["type"] = order_type
        if start_at:
            params["startAt"] = start_at
        if end_at:
            params["endAt"] = end_at
        if trade_type:
            params["tradeType"] = trade_type
        if limit:
            params["pageSize"] = limit
        if current_page:
            params["currentPage"] = current_page
        
        response = await self.client.authenticated_request(
            method="GET",
            endpoint="/api/v1/fills",
            params=params
        )
        
        success, data, error = await self._process_response(response)
        if not success:
            logger.warning(f"Failed to get filled list: {error}")
            return {"code": response.get("code", "999999"), "msg": error}
        
        return {"code": "200000", "data": data}


# Backward compatibility wrapper for the original KucoinAPI
class KucoinAPI:
    """
    Backward compatibility wrapper for the AsyncKucoinAPI.
    Allows existing code to use the new async implementation without changes.
    """
    
    def __init__(
        self,
        api_key: str = None,
        api_secret: str = None,
        passphrase: str = None
    ):
        """
        Initialize the backward compatibility wrapper.
        
        Args:
            api_key: KuCoin API key
            api_secret: KuCoin API secret
            passphrase: KuCoin API passphrase
        """
        # Store credentials
        self.api_key = api_key or os.getenv("KUCOIN_API_KEY", "")
        self.api_secret = api_secret or os.getenv("KUCOIN_API_SECRET", "")
        self.passphrase = passphrase or os.getenv("KUCOIN_API_PASSPHRASE", "")
        
        # Initialize async client
        self.async_api = AsyncKucoinAPI(
            api_key=self.api_key,
            api_secret=self.api_secret,
            passphrase=self.passphrase
        )
        
        # Default host and URL
        self.host = "api.kucoin.com"
        self.base_url = f"https://{self.host}"
    
    def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Dict[str, Any] = None,
        data: Dict[str, Any] = None,
        auth_required: bool = True
    ) -> Dict[str, Any]:
        """
        Legacy method to make a HTTP request to the KuCoin API.
        Now uses the async version internally.
        
        Args:
            method: HTTP method
            endpoint: API endpoint
            params: Query parameters
            data: Request body
            auth_required: Whether authentication is required
            
        Returns:
            API response
        """
        # Run the async version in a synchronous context
        import asyncio
        loop = asyncio.get_event_loop()
        
        # Handle running in an existing event loop
        if loop.is_running():
            # Create a new event loop if the current one is already running
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        # Choose the right async method based on auth requirement
        if auth_required:
            coro = self.async_api.client.authenticated_request(
                method=method,
                endpoint=endpoint,
                params=params,
                data=data
            )
        else:
            coro = self.async_api.client.public_request(
                endpoint=endpoint,
                params=params
            )
        
        return loop.run_until_complete(coro)
    
    def _run_async(self, coroutine):
        """Helper to run async functions synchronously"""
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Create a new event loop if the current one is already running
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete(coroutine)
    
    # Implement all the legacy methods using the async versions
    
    def get_ticker(self, symbol: str = "BTC-USDT") -> Dict[str, Any]:
        """Get ticker information for a symbol"""
        return self._run_async(self.async_api.get_ticker(symbol))
    
    def get_trade_fees(self, symbols: str = "BTC-USDT") -> Dict[str, Any]:
        """Get trade fees for specific symbols"""
        return self._run_async(self.async_api.get_trade_fees(symbols))
    
    def get_isolated_margin_accounts(
        self,
        symbol: str = None,
        quote_currency: str = "USDT",
        query_type: str = "ISOLATED"
    ) -> Dict[str, Any]:
        """Get isolated margin account information"""
        return self._run_async(
            self.async_api.get_isolated_margin_accounts(
                symbol, quote_currency, query_type
            )
        )
    
    def add_margin_order(
        self,
        symbol: str,
        side: str,
        client_oid: str = None,
        order_type: str = "limit",
        price: str = None,
        size: str = None,
        funds: str = None,
        is_isolated: bool = False,
        auto_borrow: bool = False,
        auto_repay: bool = False,
        time_in_force: str = "GTC"
    ) -> Dict[str, Any]:
        """Place an order in the margin trading system"""
        return self._run_async(
            self.async_api.add_margin_order(
                symbol=symbol,
                side=side,
                client_oid=client_oid,
                order_type=order_type,
                price=price,
                size=size,
                funds=funds,
                is_isolated=is_isolated,
                auto_borrow=auto_borrow,
                auto_repay=auto_repay,
                time_in_force=time_in_force
            )
        )
    
    def cancel_order_by_id(self, order_id: str) -> Dict[str, Any]:
        """Cancel a single order by its order ID"""
        return self._run_async(self.async_api.cancel_order_by_id(order_id))
    
    def get_filled_list(
        self,
        symbol: str = None,
        order_id: str = None,
        side: str = None,
        order_type: str = None,
        start_at: int = None,
        end_at: int = None,
        trade_type: str = "TRADE",
        limit: int = None,
        current_page: int = None
    ) -> Dict[str, Any]:
        """Get the recent fills (order execution history)"""
        return self._run_async(
            self.async_api.get_filled_list(
                symbol=symbol,
                order_id=order_id,
                side=side,
                order_type=order_type,
                start_at=start_at,
                end_at=end_at,
                trade_type=trade_type,
                limit=limit,
                current_page=current_page
            )
        )