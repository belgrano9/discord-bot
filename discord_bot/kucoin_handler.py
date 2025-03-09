import base64
import hashlib
import hmac
import json
import logging
import time
import uuid
from typing import Dict, Any
from urllib.parse import urlencode

import requests


class KucoinClient:
    """Base client for KuCoin API authentication and signing."""
    
    def __init__(self, api_key: str, api_secret: str, api_passphrase: str):
        """
        Initialize the KuCoin API client with authentication credentials.
        
        Args:
            api_key: KuCoin API key
            api_secret: KuCoin API secret
            api_passphrase: KuCoin API passphrase
        """
        self.api_key = api_key or ""
        self.api_secret = api_secret or ""
        
        # Sign the passphrase if credentials are provided
        if api_passphrase and api_secret:
            self.api_passphrase = self.sign(api_passphrase.encode('utf-8'), api_secret.encode('utf-8'))
        else:
            self.api_passphrase = api_passphrase or ""

        if not all([api_key, api_secret, api_passphrase]):
            logging.warning("API token is empty. Access is restricted to public interfaces only.")

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

    def headers(self, payload: str) -> Dict[str, str]:
        """
        Generate headers required for KuCoin API authentication.
        
        Args:
            payload: String containing method + endpoint + body
            
        Returns:
            Dictionary of headers for API authentication
        """
        timestamp = str(int(time.time() * 1000))
        signature = self.sign((timestamp + payload).encode('utf-8'), self.api_secret.encode('utf-8'))

        return {
            "KC-API-KEY": self.api_key,
            "KC-API-PASSPHRASE": self.api_passphrase,
            "KC-API-TIMESTAMP": timestamp,
            "KC-API-SIGN": signature,
            "KC-API-KEY-VERSION": "2"
        }


class KucoinAPI:
    """
    KuCoin API client for trading and account management.
    
    This class provides methods to interact with KuCoin's API endpoints
    for various purposes including getting market data, managing orders,
    and accessing account information.
    """
    
    def __init__(self, api_key: str, api_secret: str, passphrase: str):
        """
        Initialize the KuCoin API with authentication credentials.
        
        Args:
            api_key: KuCoin API key
            api_secret: KuCoin API secret
            passphrase: KuCoin API passphrase
        """
        self.signer = KucoinClient(api_key, api_secret, passphrase)
        self.api_key = api_key
        self.api_secret = api_secret
        self.host = "api.kucoin.com"
        self.base_url = f"https://{self.host}"

    def _make_request(self, 
                     method: str, 
                     endpoint: str, 
                     params: Dict[str, Any] = None, 
                     data: Dict[str, Any] = None, 
                     auth_required: bool = True) -> Dict[str, Any]:
        """
        Make an HTTP request to the KuCoin API.
        
        Args:
            method: HTTP method (GET, POST, DELETE, etc.)
            endpoint: API endpoint path
            params: Query parameters for GET requests
            data: JSON body for POST requests
            auth_required: Whether authentication is required
            
        Returns:
            Parsed JSON response
        """
        # Build URL with query parameters if provided
        url = f"{self.base_url}{endpoint}"
        query_string = ""
        
        if params:
            query_string = urlencode(params)
            url = f"{url}?{query_string}"
            endpoint = f"{endpoint}?{query_string}"
        
        # Prepare headers and data
        headers = {"Content-Type": "application/json"} if data else {}
        body_str = json.dumps(data) if data else ""
        body = body_str.encode() if body_str else b""
        
        # Add authentication headers if required
        if auth_required:
            # Create payload for signing
            payload = method + endpoint
            if body:
                payload += body_str
                
            # Get and add authentication headers
            auth_headers = self.signer.headers(payload)
            headers.update(auth_headers)
        
        # Make the request
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                data=body if body else None,
                timeout=10  # Add timeout for safety
            )
            
            # Raise exception for HTTP errors
            response.raise_for_status()
            
            # Parse and return JSON response
            return response.json()
        except requests.exceptions.RequestException as e:
            logging.error(f"Request error: {str(e)}")
            # Return error response if available
            if hasattr(e, 'response') and e.response is not None:
                try:
                    return e.response.json()
                except:
                    return {"code": "999999", "msg": str(e)}
            return {"code": "999999", "msg": str(e)}

    ###################
    # MARKET DATA API #
    ###################
    
    def get_ticker(self, symbol: str = "BTC-USDT") -> Dict[str, Any]:
        """
        Get level 1 orderbook data (ticker) for a symbol.
        
        Args:
            symbol: Trading pair symbol (e.g., BTC-USDT)
        
        Returns:
            Ticker data including best bid/ask price and size
        """
        return self._make_request(
            method="GET",
            endpoint="/api/v1/market/orderbook/level1",
            params={"symbol": symbol},
            auth_required=False  # Public endpoint
        )
    
    def get_market_list(self) -> Dict[str, Any]:
        """
        Get list of available trading pairs.
        
        Returns:
            List of available symbols and their metadata
        """
        return self._make_request(
            method="GET",
            endpoint="/api/v1/symbols",
            auth_required=False  # Public endpoint
        )
    
    def get_24h_stats(self, symbol: str = "BTC-USDT") -> Dict[str, Any]:
        """
        Get 24-hour statistics for a symbol.
        
        Args:
            symbol: Trading pair symbol (e.g., BTC-USDT)
            
        Returns:
            24-hour trading statistics including volume and price changes
        """
        return self._make_request(
            method="GET",
            endpoint="/api/v1/market/stats",
            params={"symbol": symbol},
            auth_required=False  # Public endpoint
        )
    
    ###################
    # TRADE FEES API  #
    ###################
    
    def get_trade_fees(self, symbols: str = "BTC-USDT") -> Dict[str, Any]:
        """
        Get trade fees for specific symbols.
        
        Args:
            symbols: Comma-separated trading pair symbols (e.g., "BTC-USDT,ETH-USDT")
            
        Returns:
            Dictionary containing fee information for the requested symbols
        """
        return self._make_request(
            method="GET",
            endpoint="/api/v1/trade-fees",
            params={"symbols": symbols}
        )
    
    ###################
    # ACCOUNT API     #
    ###################
    
    def get_account_list(self, currency: str = None, account_type: str = None) -> Dict[str, Any]:
        """
        Get list of accounts with optional filtering.
        
        Args:
            currency: Filter accounts by currency (e.g., 'BTC', 'USDT')
            account_type: Filter by account type ('main', 'trade', 'margin', 'trade_hf')
                
        Returns:
            List of accounts with balance information
        """
        params = {}
        if currency:
            params["currency"] = currency
        if account_type:
            params["type"] = account_type
            
        return self._make_request(
            method="GET",
            endpoint="/api/v1/accounts",
            params=params
        )
    
    def get_account_details(self, account_id: str) -> Dict[str, Any]:
        """
        Get details for a specific account by ID.
        
        Args:
            account_id: The ID of the account to retrieve
                
        Returns:
            Account details including balance, available funds, and holds
        """
        return self._make_request(
            method="GET",
            endpoint=f"/api/v1/accounts/{account_id}"
        )
    
    def get_account_summary_info(self) -> Dict[str, Any]:
        """
        Get user information summary.
        
        Returns:
            User information summary
        """
        return self._make_request(
            method="GET",
            endpoint="/api/v2/user-info"
        )
    
    ###################
    # MARGIN API      #
    ###################
    
    def get_isolated_margin_accounts(self, 
                                    symbol: str = None, 
                                    quote_currency: str = "USDT", 
                                    query_type: str = "ISOLATED") -> Dict[str, Any]:
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
            
        return self._make_request(
            method="GET",
            endpoint="/api/v3/isolated/accounts",
            params=params
        )
    
    ###################
    # ORDER API       #
    ###################
    
    def test_order(self, 
                  order_type: str = "limit", 
                  symbol: str = "BTC-USDT", 
                  side: str = "buy", 
                  price: str = None, 
                  size: str = None, 
                  funds: str = None, 
                  client_oid: str = None,
                  time_in_force: str = "GTC", 
                  cancel_after: int = -1, 
                  post_only: bool = False,
                  hidden: bool = False, 
                  iceberg: bool = False, 
                  visible_size: str = None,
                  stp: str = None, 
                  tags: str = None, 
                  remark: str = None,
                  allow_max_time_window: int = None, 
                  client_timestamp: int = None) -> Dict[str, Any]:
        """
        Test order creation without actually placing an order.
        
        Args:
            order_type: Order type - 'limit' or 'market'
            symbol: Trading pair symbol (e.g., BTC-USDT)
            side: 'buy' or 'sell'
            price: Specify price for limit orders
            size: Quantity to buy/sell
            funds: Funds to use (for market orders, use either size or funds)
            client_oid: Client-generated order ID
            time_in_force: Time in force strategy - GTC, GTT, IOC, FOK
            cancel_after: Cancel after n seconds (for GTT orders)
            post_only: Whether the order is post-only
            hidden: Whether the order is hidden
            iceberg: Whether the order is an iceberg order
            visible_size: Maximum visible quantity for iceberg orders
            stp: Self-trade prevention strategy - DC, CO, CN, CB
            tags: Order tag (max 20 characters)
            remark: Order remarks (max 20 characters)
            allow_max_time_window: Order timeout in milliseconds
            client_timestamp: Client timestamp matching KC-API-TIMESTAMP
            
        Returns:
            Test results without placing a real order
        """
        # Prepare order data
        data = {
            "type": order_type,
            "symbol": symbol,
            "side": side,
            "clientOid": client_oid or str(uuid.uuid4())
        }
        
        # Add parameters based on order type
        if order_type == "limit":
            if price is None:
                raise ValueError("Price is required for limit orders")
            if size is None:
                raise ValueError("Size is required for limit orders")
            
            data["price"] = str(price)
            data["size"] = str(size)
            
            # Add optional parameters for limit orders
            if time_in_force:
                data["timeInForce"] = time_in_force
            if cancel_after > 0:
                data["cancelAfter"] = cancel_after
            if post_only:
                data["postOnly"] = post_only
            if hidden:
                data["hidden"] = hidden
            if iceberg:
                data["iceberg"] = iceberg
                if visible_size:
                    data["visibleSize"] = str(visible_size)
        
        elif order_type == "market":
            # For market orders, either size or funds must be provided
            if size is not None:
                data["size"] = str(size)
            elif funds is not None:
                data["funds"] = str(funds)
            else:
                raise ValueError("Either size or funds must be provided for market orders")
        
        # Add other optional parameters
        if stp:
            data["stp"] = stp
        if tags:
            data["tags"] = tags
        if remark:
            data["remark"] = remark
        if allow_max_time_window:
            data["allowMaxTimeWindow"] = allow_max_time_window
        if client_timestamp:
            data["clientTimestamp"] = client_timestamp
        
        return self._make_request(
            method="POST",
            endpoint="/api/v1/hf/orders/test",
            data=data
        )
    
    def place_limit_order(self, 
                         symbol: str, 
                         side: str, 
                         price: str, 
                         size: str, 
                         client_oid: str = None,
                         time_in_force: str = "GTC",
                         **kwargs) -> Dict[str, Any]:
        """
        Place a limit order (simplified interface).
        
        Args:
            symbol: Trading pair symbol (e.g., BTC-USDT)
            side: 'buy' or 'sell'
            price: Limit price
            size: Quantity to buy/sell
            client_oid: Client-generated order ID
            time_in_force: Time in force strategy - GTC, GTT, IOC, FOK
            **kwargs: Additional order parameters
            
        Returns:
            Order creation response
        """
        return self.test_order(
            order_type="limit",
            symbol=symbol,
            side=side,
            price=price,
            size=size,
            client_oid=client_oid,
            time_in_force=time_in_force,
            **kwargs
        )
    
    def place_market_order(self, 
                          symbol: str, 
                          side: str, 
                          size: str = None,
                          funds: str = None,
                          client_oid: str = None,
                          **kwargs) -> Dict[str, Any]:
        """
        Place a market order (simplified interface).
        
        Args:
            symbol: Trading pair symbol (e.g., BTC-USDT)
            side: 'buy' or 'sell'
            size: Quantity to buy/sell
            funds: Funds to use (alternative to size)
            client_oid: Client-generated order ID
            **kwargs: Additional order parameters
            
        Returns:
            Order creation response
        """
        return self.test_order(
            order_type="market",
            symbol=symbol,
            side=side,
            size=size,
            funds=funds,
            client_oid=client_oid,
            **kwargs
        )
    
    def add_margin_order(self, 
                        order_type: str = "limit", 
                        symbol: str = "BTC-USDT", 
                        side: str = "buy", 
                        price: str = None, 
                        size: str = None, 
                        funds: str = None, 
                        client_oid: str = None,
                        margin_model: str = "isolated", 
                        auto_borrow: bool = False, 
                        auto_repay: bool = False,
                        **kwargs) -> Dict[str, Any]:
        """
        Place a real order in the margin trading system.
        
        Args:
            order_type: Order type - 'limit' or 'market'
            symbol: Trading pair symbol (e.g., BTC-USDT)
            side: 'buy' or 'sell'
            price: Specify price for limit orders
            size: Quantity to buy/sell
            funds: Funds to use (for market orders, use either size or funds)
            client_oid: Client-generated order ID
            margin_model: "cross" or "isolated" (default)
            auto_borrow: Whether to automatically borrow if balance is insufficient
            auto_repay: Whether to automatically repay when position is closed
            **kwargs: Additional order parameters
            
        Returns:
            Margin order creation response
        """
        # Prepare order data
        data = {
            "type": order_type,
            "symbol": symbol,
            "side": side,
            "clientOid": client_oid or str(uuid.uuid4()),
            "marginModel": margin_model
        }
        
        # Add auto-borrow and auto-repay if specified
        if auto_borrow:
            data["autoBorrow"] = True
        if auto_repay:
            data["autoRepay"] = True
        
        # Add parameters based on order type
        if order_type == "limit":
            if price is None:
                raise ValueError("Price is required for limit orders")
            if size is None:
                raise ValueError("Size is required for limit orders")
            
            data["price"] = str(price)
            data["size"] = str(size)
            
            # Add optional parameters from kwargs
            for key in ["timeInForce", "cancelAfter", "postOnly", "hidden", "iceberg", "visibleSize", "stp"]:
                if key in kwargs:
                    data[key] = kwargs[key]
        
        elif order_type == "market":
            # For market orders, either size or funds must be provided
            if size is not None:
                data["size"] = str(size)
            elif funds is not None:
                data["funds"] = str(funds)
            else:
                raise ValueError("Either size or funds must be provided for market orders")
        
        return self._make_request(
            method="POST",
            endpoint="/api/v1/margin/order",
            data=data
        )
    
    def cancel_order_by_id(self, order_id: str) -> Dict[str, Any]:
        """
        Cancel a single order by its order ID.
        
        Args:
            order_id: The unique order ID assigned by the server
                
        Returns:
            Cancellation response
        """
        return self._make_request(
            method="DELETE",
            endpoint=f"/api/v1/orders/{order_id}"
        )
    
    ###################
    # TRADE HISTORY   #
    ###################
    
    def get_filled_list(self, 
                       symbol: str = None, 
                       order_id: str = None, 
                       side: str = None, 
                       order_type: str = None,
                       start_at: int = None, 
                       end_at: int = None, 
                       trade_type: str = "TRADE", 
                       limit: int = None, 
                       current_page: int = None) -> Dict[str, Any]:
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
        
        return self._make_request(
            method="GET",
            endpoint="/api/v1/fills",
            params=params
        )


if __name__ == '__main__':
    # Example usage
    import os
    
    key = os.getenv("KUCOIN_API_KEY", "")
    secret = os.getenv("KUCOIN_API_SECRET", "")
    passphrase = os.getenv("KUCOIN_API_PASSPHRASE", "")
    
    kucoin_api = KucoinAPI(key, secret, passphrase)
    
    # Get isolated margin accounts
    balance = kucoin_api.get_isolated_margin_accounts(symbol="BTC-USDT")
    
    if balance.get("code") == "200000" and "data" in balance:
        print("Isolated Margin Account:")
        print(balance["data"]["assets"][0])
    
    # Get account list
    accounts = kucoin_api.get_account_list()
    if accounts.get("code") == "200000" and "data" in accounts:
        print(f"\nFound {len(accounts['data'])} accounts")