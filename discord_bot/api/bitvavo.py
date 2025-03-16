"""
Asynchronous implementation of the Bitvavo API client.
Refactored to use standardized async request handling and error processing.
"""

import asyncio
import json
import time
import hashlib
import hmac
from typing import Dict, Any, Optional, List, Union
from loguru import logger

from discord_bot.api.base import AsyncBaseAPI, require_api_key, ApiKeyRequiredError


class AsyncBitvavoClient(AsyncBaseAPI):
    """
    Asynchronous client for Bitvavo API endpoints.
    Handles request signing and authentication.
    """
    
    def __init__(
        self,
        api_key: str,
        api_secret: str,
        access_window: int = 10000
    ):
        """
        Initialize the Bitvavo API client.
        
        Args:
            api_key: Bitvavo API key
            api_secret: Bitvavo API secret
            access_window: Access window in milliseconds
        """
        # Initialize base class
        super().__init__(
            base_url="https://api.bitvavo.com/v2",
            api_key=api_key
        )
        
        # Store authentication details
        self.api_secret = api_secret
        self.access_window = access_window
        
        logger.debug("Initialized AsyncBitvavoClient")
    
    def create_signature(
        self,
        timestamp: int,
        method: str,
        url: str,
        body: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Create a hashed signature for request authentication.
        
        Args:
            timestamp: Current timestamp in milliseconds
            method: HTTP method
            url: Request URL
            body: Request body
            
        Returns:
            HMAC-SHA256 signature encoded as hex
        """
        # Create the string to sign
        string = str(timestamp) + method + "/v2" + url
        if body and len(body) > 0:
            string += json.dumps(body, separators=(",", ":"))
        
        # Create the signature
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return signature
    
    async def _authenticated_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Make an authenticated request to the Bitvavo API.
        
        Args:
            method: HTTP method
            endpoint: API endpoint
            params: Query parameters
            data: Request body
            
        Returns:
            API response data
        """
        # Get current timestamp
        timestamp = int(time.time() * 1000)
        
        # Create signature
        signature = self.create_signature(timestamp, method, endpoint, data)
        
        # Add authentication headers
        headers = {
            "bitvavo-access-key": self.api_key,
            "bitvavo-access-signature": signature,
            "bitvavo-access-timestamp": str(timestamp),
            "bitvavo-access-window": str(self.access_window)
        }
        
        # Make the request
        return await self.request(
            method=method,
            endpoint=endpoint,
            params=params,
            data=data,
            headers=headers
        )
    
    async def public_request(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Make a public request to the Bitvavo API.
        
        Args:
            endpoint: API endpoint
            params: Query parameters
            
        Returns:
            API response data
        """
        return await self.get(endpoint, params=params)
    
    @require_api_key
    async def place_order(
        self,
        market: str,
        side: str,
        order_type: str,
        body: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Place an order on Bitvavo.
        
        Args:
            market: Market symbol
            side: buy or sell
            order_type: limit or market
            body: Order details
            
        Returns:
            Order response data
        """
        # Add market and side to the body
        body["market"] = market
        body["side"] = side
        body["orderType"] = order_type
        
        # Make the authenticated request
        return await self._authenticated_request(
            method="POST",
            endpoint="/order",
            data=body
        )
    
    @require_api_key
    async def get_account_balance(
        self,
        symbol: Optional[str] = None
    ) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Get account balance information.
        
        Args:
            symbol: Optional symbol to filter by
            
        Returns:
            Account balance data
        """
        try:
            # Get all balances
            balances = await self._authenticated_request(
                method="GET",
                endpoint="/balance"
            )
            
            # Check for errors
            if isinstance(balances, dict) and "errorCode" in balances:
                raise ValueError(f"API error: {balances.get('error', 'Unknown error')}")
            
            # Filter by symbol if requested
            if symbol:
                for balance in balances:
                    if balance.get("symbol") == symbol:
                        return balance
                return {"symbol": symbol, "available": "0", "inOrder": "0"}
            
            return balances
            
        except Exception as e:
            logger.error(f"Error retrieving balance: {str(e)}")
            raise ValueError(f"Error retrieving balance: {str(e)}")
    
    async def get_ticker(self, market: str) -> Dict[str, Any]:
        """
        Get ticker information for a market.
        
        Args:
            market: Market symbol
            
        Returns:
            Ticker data
        """
        # Convert slash format to dash format if needed
        market = market.replace("/", "-")
        
        # Make the public request
        return await self.public_request(endpoint=f"/ticker/price/{market}")
    
    async def get_markets(
        self,
        filter_str: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get available markets from Bitvavo.
        
        Args:
            filter_str: Optional string to filter markets
            
        Returns:
            List of markets
        """
        try:
            # Get all markets
            markets = await self.public_request(endpoint="/markets")
            
            # Filter if requested
            if filter_str:
                filter_str = filter_str.upper()
                markets = [m for m in markets if filter_str in m.get("market", "")]
            
            return markets
            
        except Exception as e:
            logger.error(f"Error getting markets: {str(e)}")
            return []
    
    async def get_order_book(
        self,
        market: str,
        depth: int = 10
    ) -> Dict[str, Any]:
        """
        Get order book for a market.
        
        Args:
            market: Market symbol
            depth: Order book depth
            
        Returns:
            Order book data
        """
        try:
            params = {"depth": depth}
            return await self.public_request(
                endpoint=f"/orderbook/{market}",
                params=params
            )
        except Exception as e:
            logger.error(f"Error getting order book: {str(e)}")
            return {"bids": [], "asks": []}


# Backward compatibility wrapper for the original BitvavoHandler
class BitvavoHandler:
    """
    Backward compatibility wrapper for the AsyncBitvavoClient.
    Allows existing code to use the new async implementation without changes.
    """
    
    def __init__(self):
        """Initialize the Bitvavo handler with API keys from environment."""
        import os
        self.api_key = os.getenv("BITVAVO_API_KEY", "")
        self.api_secret = os.getenv("BITVAVO_API_SECRET", "")
        self.client = BitvavoRestClient(self.api_key, self.api_secret)
        
        # Initialize the async client
        self.async_client = AsyncBitvavoClient(self.api_key, self.api_secret)
    
    def _run_async(self, coroutine):
        """Helper to run async functions synchronously"""
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Create a new event loop if the current one is already running
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete(coroutine)
    
    def check_authentication(self) -> tuple:
        """Check if API credentials are valid"""
        try:
            response = self.client.private_request(endpoint="/account")
            if "errorCode" in response:
                return (
                    False,
                    f"Authentication error: {response.get('error', 'Unknown error')}",
                )
            return True, ""
        except Exception as e:
            return False, f"Error checking authentication: {str(e)}"
    
    def get_markets(self, filter_str=None):
        """Get available markets from Bitvavo"""
        return self._run_async(self.async_client.get_markets(filter_str))
    
    def get_ticker(self, market):
        """Get ticker information for a specific market"""
        return self._run_async(self.async_client.get_ticker(market))
    
    def get_order_book(self, market, depth=10):
        """Get order book for a market"""
        return self._run_async(self.async_client.get_order_book(market, depth))
    
    def get_balance(self, symbol=None):
        """Get account balance"""
        return self._run_async(self.async_client.get_account_balance(symbol))


# Keep the original BitvavoRestClient for backward compatibility
class BitvavoRestClient:
    """Original BitvavoRestClient (preserved for backward compatibility)"""
    def __init__(self, api_key, api_secret, access_window=10000):
        self.api_key = api_key
        self.api_secret = api_secret
        self.access_window = access_window
        self.base = "https://api.bitvavo.com/v2"

    def place_order(self, market, side, order_type, body):
        body["market"] = market
        body["side"] = side
        body["orderType"] = order_type
        return self.private_request(method="POST", endpoint="/order", body=body)

    def private_request(self, endpoint, body=None, method="GET"):
        now = int(time.time() * 1000)
        sig = self.create_signature(now, method, endpoint, body)
        url = self.base + endpoint
        headers = {
            "bitvavo-access-key": self.api_key,
            "bitvavo-access-signature": sig,
            "bitvavo-access-timestamp": str(now),
            "bitvavo-access-window": str(self.access_window),
        }

        import requests
        r = requests.request(method=method, url=url, headers=headers, json=body)
        return r.json()

    def create_signature(self, timestamp, method, url, body):
        string = str(timestamp) + method + "/v2" + url
        if (body is not None) and (len(body.keys()) != 0):
            string += json.dumps(body, separators=(",", ":"))
        signature = hmac.new(
            self.api_secret.encode("utf-8"), string.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        return signature

    def public_request(self, endpoint, params=None):
        import requests
        url = self.base + endpoint
        r = requests.get(url, params=params)
        return r.json()