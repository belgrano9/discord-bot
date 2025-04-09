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


from discord_bot.logging_setup import get_logger

logger = get_logger("stock_commands")

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
        logger.info("Initializing KucoinClient")

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
        logger.info("Initializing KucoinAPI")

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
            account_type: Filter by account type ('main', 'trade', 'margin','isolation', 'trade_hf')
                
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
    
    def get_cross_margin_accounts(self, 
                                    quote_currency: str = "USDT", 
                                    query_type: str = "MARGIN") -> Dict[str, Any]:
        """
        Get cross margin account information.
        
        Args:
            quote_currency: Quote currency, e.g., USDT (default)
            query_type: Account type - "MARGIN" (default), "MARGIN_V2", or "ALL"
                
        Returns:
            Isolated margin account data including assets and liabilities
        """
        params = {
            "quoteCurrency": quote_currency,
            "queryType": query_type
        }
        

            
        return self._make_request(
            method="GET",
            endpoint="/api/v3/margin/accounts",
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
                     stp: str = None,
                     time_in_force: str = "GTC",
                     cancel_after: int = None,
                     post_only: bool = False,
                     hidden: bool = False,
                     iceberg: bool = False,
                     visible_size: str = None,
                     remark: str = None) -> Dict[str, Any]:
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
            stp: Self-trade prevention strategy - 'CN', 'CO', 'CB', or 'DC'
            time_in_force: Order timing strategy - 'GTC', 'GTT', 'IOC', 'FOK'
            cancel_after: Cancel after n seconds (for GTT orders)
            post_only: Whether the order is post-only
            hidden: Whether the order is hidden
            iceberg: Whether the order is an iceberg order
            visible_size: Maximum visible quantity for iceberg orders
            remark: Order remarks
            
        Returns:
            Order response including orderId, clientOid, and potentially
            borrowSize and loanApplyId if auto_borrow is enabled
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
        
        # Add STP if specified
        if stp:
            data["stp"] = stp
            
        # Add remark if specified
        if remark:
            data["remark"] = remark
        
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
            
            if cancel_after and time_in_force == "GTT":
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
        
        # Make the API request
        return self._make_request(
            method="POST",
            endpoint="/api/v3/hf/margin/order",
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
    
    def get_margin_open_orders(self, 
                           symbol: str, 
                           trade_type: str = "MARGIN_ISOLATED_TRADE") -> Dict[str, Any]:
        """
        Get all active margin orders for a symbol.
        
        Args:
            symbol: Trading pair symbol (e.g., BTC-USDT)
            trade_type: Type of margin trading
                    "MARGIN_TRADE" - cross margin trading order
                    "MARGIN_ISOLATED_TRADE" - isolated margin trading order
            
        Returns:
            List of active margin orders sorted by latest update time
        """
        # Validate trade_type parameter
        valid_trade_types = ["MARGIN_TRADE", "MARGIN_ISOLATED_TRADE"]
        if trade_type not in valid_trade_types:
            raise ValueError(f"trade_type must be one of {valid_trade_types}")
            
        # Prepare query parameters
        params = {
            "symbol": symbol,
            "tradeType": trade_type
        }
        
        # Make the API request
        return self._make_request(
            method="GET",
            endpoint="/api/v3/hf/margin/orders/active",
            params=params
        )
    
    def add_stop_order(self,
                  symbol: str,
                  side: str,
                  stop_price: str,
                  order_type: str = "limit",
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
                  remark: str = None,
                  stp: str = None,
                  trade_type: str = "TRADE") -> Dict[str, Any]:
        """
        Place a stop order to the Spot/Margin trading system.
        The maximum untriggered stop orders for a single trading pair in one account is 20.
        
        Args:
            symbol: Trading pair symbol (e.g., BTC-USDT)
            side: 'buy' or 'sell'
            stop_price: The trigger price
            order_type: Order type - 'limit' or 'market' (default: 'limit')
            price: Price for limit orders (required if order_type is 'limit')
            size: Quantity to buy/sell (required for limit orders, or for market buy orders)
            funds: Funds to use (alternative to size for market orders)
            client_oid: Client-generated order ID (recommend to use UUID)
            time_in_force: Time in force strategy - 'GTC', 'GTT', 'IOC', 'FOK' (default: 'GTC')
            cancel_after: Cancel after n seconds, only for GTT orders (default: -1, not cancelled)
            post_only: Whether the order is post-only (default: False)
            hidden: Whether the order is hidden (default: False)
            iceberg: Whether the order is an iceberg order (default: False)
            visible_size: Maximum visible quantity for iceberg orders
            remark: Order remarks, max 20 characters
            stp: Self-trade prevention strategy - 'DC', 'CO', 'CN', 'CB'
            trade_type: Type of trading - 'TRADE' (Spot), 'MARGIN_TRADE' (Cross Margin),
                        'MARGIN_ISOLATED_TRADE' (Isolated Margin) (default: 'TRADE')
        
        Returns:
            Dictionary containing the order ID
        """
        # Validate required parameters
        if not symbol or not side or not stop_price:
            raise ValueError("Symbol, side, and stop_price are required parameters")
        
        if order_type not in ["limit", "market"]:
            raise ValueError("Order type must be either 'limit' or 'market'")
        
        if side not in ["buy", "sell"]:
            raise ValueError("Side must be either 'buy' or 'sell'")
        
        # Validate parameters based on order type
        if order_type == "limit" and price is None:
            raise ValueError("Price is required for limit orders")
        
        if order_type == "limit" and size is None:
            raise ValueError("Size is required for limit orders")
        
        if order_type == "market" and size is None and funds is None:
            raise ValueError("Either size or funds must be provided for market orders")
        
        # Prepare order data
        data = {
            "symbol": symbol,
            "side": side,
            "stopPrice": stop_price,
            "type": order_type,
            "clientOid": client_oid or str(uuid.uuid4())
        }
        
        # Add price for limit orders
        if order_type == "limit" and price is not None:
            data["price"] = price
        
        # Add size if provided
        if size is not None:
            data["size"] = size
        
        # Add funds if provided (for market orders)
        if funds is not None and order_type == "market":
            data["funds"] = funds
        
        # Add optional parameters if specified
        if time_in_force:
            data["timeInForce"] = time_in_force
        
        if cancel_after != -1:
            data["cancelAfter"] = cancel_after
        
        if post_only:
            data["postOnly"] = post_only
        
        if hidden:
            data["hidden"] = hidden
        
        if iceberg:
            data["iceberg"] = iceberg
            if visible_size:
                data["visibleSize"] = visible_size
        
        if remark:
            data["remark"] = remark
        
        if stp:
            data["stp"] = stp
        
        if trade_type:
            data["tradeType"] = trade_type
        
        # Make the API request
        return self._make_request(
            method="POST",
            endpoint="/api/v1/stop-order",
            data=data
        )

    def cancel_stop_order(self, order_id: str) -> Dict[str, Any]:
        """
        Cancel a single stop order by its order ID.
        
        Args:
            order_id: The unique order ID of the stop order to be cancelled
                
        Returns:
            Dictionary containing a list of cancelled order IDs
            
        Note:
            The order ID is the server-assigned order id and not the passed clientOid.
            You'll receive cancelledOrderIds field once the system has received the 
            cancellation request. The cancellation request will be processed by the 
            matching engine in sequence.
        """
        return self._make_request(
            method="DELETE",
            endpoint=f"/api/v1/stop-order/{order_id}"
        )
    
    
    ###################
    #       DEBT      #
    ###################
    def get_borrow_history(self,
                      currency: str,
                      is_isolated: bool = False,
                      symbol: str = None,
                      order_no: str = None,
                      start_time: int = None,
                      end_time: int = None,
                      current_page: int = 1,
                      page_size: int = 50) -> Dict[str, Any]:
        """
        Get the borrowing orders for cross and isolated margin accounts.
        
        Args:
            currency: The currency to query (e.g., BTC, ETH, KCS)
            is_isolated: True for isolated margin, False for cross margin (default: False)
            symbol: Trading pair symbol, mandatory for isolated margin account (e.g., BTC-USDT)
            order_no: Borrow Order ID to filter by
            start_time: Start time in milliseconds 
                    (if not provided or less than 1680278400000, defaults to April 1, 2023)
            end_time: End time in milliseconds
            current_page: Current query page, starting from 1 (default: 1)
            page_size: Number of results per page, between 10 and 500 (default: 50)
        
        Returns:
            Dictionary containing borrowing history data including pagination info and items
        """
        # Prepare query parameters
        params = {
            "currency": currency
        }
        
        # Add optional parameters if provided
        if is_isolated is not None:
            params["isIsolated"] = is_isolated
        
        if symbol:
            params["symbol"] = symbol
        
        if order_no:
            params["orderNo"] = order_no
        
        if start_time:
            params["startTime"] = start_time
        
        if end_time:
            params["endTime"] = end_time
        
        if current_page:
            params["currentPage"] = current_page
        
        if page_size:
            # Ensure page_size is within allowed limits (10-500)
            page_size = max(10, min(500, page_size))
            params["pageSize"] = page_size
        
        # Make the API request
        return self._make_request(
            method="GET",
            endpoint="/api/v3/margin/borrow",
            params=params
        )

    def repay_margin_loan(self,
                     currency: str,
                     size: float,
                     symbol: str = None,
                     is_isolated: bool = False,
                     is_hf: bool = False) -> Dict[str, Any]:
        """
        Initiate an application for cross or isolated margin repayment.
        
        Args:
            currency: The currency to repay (e.g., BTC, ETH, USDT)
            size: Amount to repay
            symbol: Trading pair symbol, mandatory for isolated margin account (e.g., BTC-USDT)
            is_isolated: True for isolated margin, False for cross margin (default: False)
            is_hf: True for high frequency repayment, False for low frequency (default: False)
        
        Returns:
            Dictionary containing repayment details including orderNo and actualSize
        """
        # Prepare request data
        data = {
            "currency": currency,
            "size": size
        }
        
        # Add optional parameters if applicable
        if symbol:
            data["symbol"] = symbol
        
        if is_isolated is not None:
            data["isIsolated"] = is_isolated
        
        if is_hf is not None:
            data["isHf"] = is_hf
        
        # Make the API request
        return self._make_request(
            method="POST",
            endpoint="/api/v3/margin/repay",
            data=data
        )

    def add_margin_order_v1(self, 
                     symbol: str,
                     side: str,
                     client_oid: str = None,
                     order_type: str = "limit",
                     price: str = None,
                     size: str = None,
                     funds: str = None,
                     margin_model: str = "cross",
                     auto_borrow: bool = False,
                     auto_repay: bool = False,
                     stp: str = None,
                     time_in_force: str = "GTC",
                     cancel_after: int = None,
                     post_only: bool = False,
                     hidden: bool = False,
                     iceberg: bool = False,
                     visible_size: str = None,
                     remark: str = None) -> Dict[str, Any]:
        """
        Place an order in the margin trading system (v1 endpoint).
        
        Args:
            symbol: Trading pair symbol (e.g., ETH-BTC)
            side: 'buy' or 'sell'
            client_oid: Client-generated order ID (recommend to use UUID)
            order_type: Order type - 'limit' or 'market'
            price: Price for limit orders
            size: Quantity to buy/sell
            funds: Funds to use (for market orders, alternative to size)
            margin_model: 'cross' (cross mode) or 'isolated' (isolated mode)
            auto_borrow: Whether to auto-borrow if insufficient balance
            auto_repay: Whether to auto-repay when closing position
            stp: Self-trade prevention strategy - 'CN', 'CO', 'CB', or 'DC'
            time_in_force: Order timing strategy - 'GTC', 'GTT', 'IOC', 'FOK'
            cancel_after: Cancel after n seconds (for GTT orders)
            post_only: Whether the order is post-only
            hidden: Whether the order is hidden
            iceberg: Whether the order is an iceberg order
            visible_size: Maximum visible quantity for iceberg orders
            remark: Order remarks
            
        Returns:
            Dictionary containing orderId, possibly borrowSize and loanApplyId
        """
        # Prepare order data
        data = {
            "symbol": symbol,
            "side": side,
            "clientOid": client_oid or str(uuid.uuid4()),
        }
        
        # Add order type if specified
        if order_type:
            data["type"] = order_type
        
        # Add margin model
        if margin_model:
            data["marginModel"] = margin_model
        
        # Add auto-borrow and auto-repay flags
        if auto_borrow:
            data["autoBorrow"] = auto_borrow
        if auto_repay:
            data["autoRepay"] = auto_repay
        
        # Add STP if specified
        if stp:
            data["stp"] = stp
        
        # Add remark if specified
        if remark:
            data["remark"] = remark
        
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
            
            if cancel_after and time_in_force == "GTT":
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
        
        # Make the API request
        return self._make_request(
            method="POST",
            endpoint="/api/v1/margin/order",
            data=data
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

    def get_recent_orders(self) -> Dict[str, Any]:
        """
        Get recent orders from the last 24 hours (up to 1000 orders).
        
        Returns:
            Dictionary containing recent orders data, paginated and sorted in descending 
            order by time.
            
        Note:
            This endpoint requires the General permission.
            The response includes detailed information about each order including:
            ID, symbol, type, side, price, size, fees, and various order parameters.
        """
        return self._make_request(
            method="GET",
            endpoint="/api/v1/limit/orders",
            auth_required=True
        )
    
    def get_order_list(self, 
                  status: str = "done", 
                  symbol: str = "BTC-USDT", 
                  side: str = None, 
                  order_type: str = None,
                  trade_type: str = "MARGIN_ISOLATED_TRADE", 
                  start_at: int = None, 
                  end_at: int = None) -> Dict[str, Any]:
        """
        Get a list of orders with pagination, sorted in descending order by time.
        
        Args:
            status: Order status - 'active' or 'done' (default: 'done')
            symbol: Only list orders for a specific symbol (e.g., 'BTC-USDT')
            side: Filter by side - 'buy' or 'sell'
            order_type: Filter by order type - 'limit', 'market', 'limit_stop' or 'market_stop'
            trade_type: The type of trading - 'TRADE' (Spot Trading, default),
                        'MARGIN_TRADE' (Cross Margin Trading),
                        'MARGIN_ISOLATED_TRADE' (Isolated Margin Trading)
            start_at: Start time in milliseconds
            end_at: End time in milliseconds
            
        Returns:
            Dictionary containing paginated order data including totalNum, 
            currentPage, pageSize, totalPage, and items (order array)
            
        Notes:
            - When querying orders in 'done' status, the time range cannot exceed 7 days
            - History for cancelled orders is kept for 1 month, filled orders for 6 months
            - For high-volume trading, maintain your own list of open orders
        """
        # Prepare query parameters
        params = {}
        
        # Add parameters only if they are provided and not None
        if status:
            params["status"] = status
        if symbol:
            params["symbol"] = symbol
        if side:
            params["side"] = side
        if order_type:
            params["type"] = order_type
        if trade_type:
            params["tradeType"] = trade_type
        if start_at:
            params["startAt"] = start_at
        if end_at:
            params["endAt"] = end_at
        
        return self._make_request(
            method="GET",
            endpoint="/api/v1/orders",
            params=params
        )
    
    ####################
    #   POSITIONS      #
    ####################
    
    def cancel_margin_order(self, order_id: str, symbol: str = "BTC-USDT") -> Dict[str, Any]:
        """
        **DOESN'T WORK!!!!!!**  Cancel a margin order by its order ID.
        
        Args:
            order_id: The unique order ID to cancel
            symbol: Trading pair symbol (e.g., BTC-USDT)
            
        Returns:
            Dictionary containing cancellation response
        """
        return self._make_request(
            method="DELETE",
            endpoint=f"/api/v3/hf/margin/orders/{order_id}",
            params={"symbol": symbol}
        )
    
    def get_margin_open_orders(self, symbol: str = "BTC-USDT", trade_type: str = "MARGIN_ISOLATED_TRADE") -> Dict[str, Any]:
        """
        **DOESN'T WORK**Get all active margin orders for a symbol.
        
        Args:
            symbol: Trading pair symbol (e.g., BTC-USDT)
            trade_type: Type of margin trading
                    "MARGIN_TRADE" - cross margin trading order
                    "MARGIN_ISOLATED_TRADE" - isolated margin trading order
            
        Returns:
            List of active margin orders sorted by latest update time
        """
        # Validate trade_type parameter
        valid_trade_types = ["MARGIN_TRADE", "MARGIN_ISOLATED_TRADE"]
        if trade_type not in valid_trade_types:
            raise ValueError(f"trade_type must be one of {valid_trade_types}")
            
        # Prepare query parameters
        params = {
            "symbol": symbol,
            "tradeType": trade_type
        }
        
        # Make the API request
        return self._make_request(
            method="GET",
            endpoint="/api/v3/hf/margin/orders/active",
            params=params
        )

    def get_order_details(self, order_id:str):
        return self._make_request(
            method="GET",
            endpoint=f"/api/v1/orders/{order_id}",
        )


if __name__ == '__main__':
    
    import os
    
    key = os.getenv("KUCOIN_API_KEY", "")
    secret = os.getenv("KUCOIN_API_SECRET", "")
    passphrase = os.getenv("KUCOIN_API_PASSPHRASE", "")
    

    kucoin_api = KucoinAPI(key, secret, passphrase)
    

    stats = kucoin_api.get_24h_stats()
    print(stats)
    balance = kucoin_api.get_isolated_margin_accounts(symbol="BTC-USDT",quote_currency="USDT")
    
    print("Balance is:")
    print(balance["data"]["assets"])
    
    # CHECK OPEN ORDERS
    #act = kucoin_api.get_order_details()
    #print(act)

    # SIMPLE ORDERS
    ## SELL 
    ### IF I DO HAVE FUNDS USE V1:
    
    #sell = kucoin_api.add_margin_order_v1("BTC-USDT", side = "sell", size=0.0004 ,order_type="market", margin_model="isolated")
    #print(sell)
    
    ### IF I DON'T HAVE FUNDS, I NEED TO BORROW. USE V3: 
    #sell = kucoin_api.add_margin_order("BTC-USDT", side = "sell",order_type="market", is_isolated=True, auto_borrow=True, size=0.0001 , remark="Bot test short with funds")
    #print(sell)

    ## BUY
    ### V3 DOESN'T WORK
    #buy = kucoin_api.add_margin_order("BTC-USDT", side = "buy", order_type="limit", size=0.00004, price =10000, is_isolated=True, remark ="Bot")
    #print(buy)
    
    ### USE V1:
    #buy = kucoin_api.add_margin_order_v1("BTC-USDT", side = "buy", funds=1 ,order_type="market", margin_model="isolated")
    #print(buy)

    # ADVANCED ORDER
    ## I HAVE BOUGHT 

    #stop = kucoin_api.add_stop_order("BTC-USDT", side = "sell", order_type="market", stop_price=85260, funds=1 ,trade_type="MARGIN_ISOLATED_TRADE", remark="bot test stop order buy")
    #print(stop)

    #open=kucoin_api.get_recent_orders()
    #print(open)

    #id=buy["data"]["orderId"]
    #cancel = kucoin_api.cancel_order_by_id(order_id=id)
    #print(cancel)

    
    #n_borrow = kucoin_api.get_borrow_history(currency="BTC")["data"]["items"][0]["size"]
    #currency =kucoin_api.get_borrow_history(currency="BTC")["data"]["items"][0]["currency"]
    #print(n_borrow)
    #print(kucoin_api.repay_margin_loan(currency=currency, size=n_borrow, symbol="BTC-USDT", is_isolated=True))
