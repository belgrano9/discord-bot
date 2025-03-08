import base64
import hashlib
import hmac
import json
import logging
import os
import time
import uuid
import http.client
from urllib.parse import urlencode

import requests


class KucoinClient:
    def __init__(self, api_key: str, api_secret: str, api_passphrase: str):
        """
        KucoinClient contains information about 'apiKey', 'apiSecret', 'apiPassPhrase'
        and provides methods to sign and generate headers for API requests.
        """
        self.api_key = api_key or ""
        self.api_secret = api_secret or ""
        self.api_passphrase = api_passphrase or ""

        if api_passphrase and api_secret:
            self.api_passphrase = self.sign(api_passphrase.encode('utf-8'), api_secret.encode('utf-8'))

        if not all([api_key, api_secret, api_passphrase]):
            logging.warning("API token is empty. Access is restricted to public interfaces only.")

    def sign(self, plain: bytes, key: bytes) -> str:
        hm = hmac.new(key, plain, hashlib.sha256)
        return base64.b64encode(hm.digest()).decode()

    def headers(self, plain: str) -> dict:
        """
        Headers method generates and returns a map of signature headers needed for API authorization
        It takes a plain string as an argument to help form the signature. The outputs are a set of API headers.
        """
        timestamp = str(int(time.time() * 1000))
        signature = self.sign((timestamp + plain).encode('utf-8'), self.api_secret.encode('utf-8'))

        return {
            "KC-API-KEY": self.api_key,
            "KC-API-PASSPHRASE": self.api_passphrase,
            "KC-API-TIMESTAMP": timestamp,
            "KC-API-SIGN": signature,
            "KC-API-KEY-VERSION": "2"
        }


class KucoinAPI:
    def __init__(self, api_key: str, api_secret: str, passphrase: str):
        self.signer = KucoinClient(api_key, api_secret, passphrase)
        self.api_key = api_key
        self.api_secret = api_secret
        self.session = requests.Session()
        self.endpoint = "https://api.kucoin.com"
        self.host = "api.kucoin.com"

    def process_headers(self, body: bytes, raw_url: str, request: requests.PreparedRequest, method: str):
        """Process and add necessary headers to the request"""
        request.headers["Content-Type"] = "application/json"

        # Create the payload by combining method, raw URL, and body
        payload = method + raw_url + body.decode()
        headers = self.signer.headers(payload)

        # Add headers to the request
        request.headers.update(headers)

    def get_trade_fees(self, symbols="BTC-USDT"):
        """Get trade fees for specific symbols"""
        path = "/api/v1/trade-fees"
        method = "GET"
        query_params = {"symbols": symbols}

        # Build full URL and raw URL
        full_path = f"{self.endpoint}{path}?{urlencode(query_params)}"
        raw_url = f"{path}?{urlencode(query_params)}"

        req = requests.Request(method=method, url=full_path).prepare()
        self.process_headers(b"", raw_url, req, method)

        resp = self.session.send(req)
        return json.loads(resp.content)

    def add_limit_order(self, symbol="BTC-USDT", side="buy", price="10000", size="0.001"):
        """Add a limit order"""
        path = "/api/v1/hf/orders"
        method = "POST"

        # Prepare order data
        order_data = json.dumps({
            "clientOid": str(uuid.uuid4()),
            "side": side,
            "symbol": symbol,
            "type": "limit",
            "price": price,
            "size": size,
        })

        # Build full URL and raw URL
        full_path = f"{self.endpoint}{path}"
        raw_url = path

        req = requests.Request(method=method, url=full_path, data=order_data).prepare()
        self.process_headers(order_data.encode(), raw_url, req, method)

        resp = self.session.send(req)
        return json.loads(resp.content)

    def get_account_summary_info(self):
        """Get user information using http.client"""
        path = "/api/v2/user-info"
        method = "GET"
        
        # Create signature for authentication
        payload = method + path
        headers = self.signer.headers(payload)
        
        # Set up the connection
        conn = http.client.HTTPSConnection(self.host)
        conn.request(method, path, "", headers)
        
        # Get and process response
        res = conn.getresponse()
        data = res.read()
        conn.close()
        
        return json.loads(data.decode("utf-8"))

    def get_isolated_margin_accounts(self, symbol=None, quote_currency="USDT", query_type="ISOLATED"):
        """
        Get isolated margin accounts information
        
        Args:
            symbol: Trading pair symbol (optional)
            quote_currency: Quote currency, e.g., USDT
            query_type: Account type, default is ISOLATED
            
        Returns:
            JSON response with isolated margin accounts data
        """
        # Construct query parameters - omit symbol if None
        query_params = {}
        if symbol:
            query_params["symbol"] = symbol
        query_params["quoteCurrency"] = quote_currency
        query_params["queryType"] = query_type
        
        # Build the path with query parameters
        path = f"/api/v3/isolated/accounts?{urlencode(query_params)}"
        method = "GET"
        
        # Create signature for authentication
        payload = method + path
        headers = self.signer.headers(payload)
        
        # Set up the connection using http.client
        conn = http.client.HTTPSConnection(self.host)
        conn.request(method, path, "", headers)
        
        # Get and process response
        res = conn.getresponse()
        data = res.read()
        conn.close()
        
        return json.loads(data.decode("utf-8"))

    def get_account_details(self, account_id):
        """
        Get details for a specific account by ID
        
        Args:
            account_id: The ID of the account to retrieve
            
        Returns:
            JSON response with account details
        """
        path = f"/api/v1/accounts/{account_id}"
        method = "GET"
        
        # Create signature for authentication
        payload = method + path
        headers = self.signer.headers(payload)
        
        # Set up the connection using http.client
        conn = http.client.HTTPSConnection(self.host)
        conn.request(method, path, "", headers)
        
        # Get and process response
        res = conn.getresponse()
        data = res.read()
        conn.close()
        
        return json.loads(data.decode("utf-8"))

    ##### SPOT TRADING #####
     
    def get_ticker(self, symbol="BTC-USDT"):
        """
        Get level 1 orderbook data for a symbol
        
        Args:
            symbol: Trading pair symbol (e.g., BTC-USDT)
        
        Returns:
            JSON response with level 1 orderbook data including best bid and ask
        """
        # Construct query parameters
        from urllib.parse import urlencode
        query_params = {"symbol": symbol}
        
        # Build the path with query parameters
        path = f"/api/v1/market/orderbook/level1?{urlencode(query_params)}"
        method = "GET"
        
        # This is a public endpoint, so authentication is not required for KuCoin
        
        # Set up the connection using http.client
        conn = http.client.HTTPSConnection(self.host)
        conn.request(method, path, "")
        
        # Get and process response
        res = conn.getresponse()
        data = res.read()
        conn.close()
        
        return json.loads(data.decode("utf-8")) 
     
    def test_order(self, order_type="limit", symbol="BTC-USDT", side="buy", 
               price=None, size=None, funds=None, client_oid=None,
               time_in_force="GTC", cancel_after=-1, post_only=False,
               hidden=False, iceberg=False, visible_size=None,
               stp=None, tags=None, remark=None,
               allow_max_time_window=None, client_timestamp=None):
        """
        Test order creation without actually placing an order
        
        This endpoint has the same parameters as the regular order endpoint,
        but will only validate the order parameters without actually placing it.
        
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
            JSON response with orderId and clientOid if successful
        """
        # Prepare order data
        data = {
            "type": order_type,
            "symbol": symbol,
            "side": side
        }
        
        # Add client order ID if provided, otherwise generate one
        if client_oid:
            data["clientOid"] = client_oid
        else:
            data["clientOid"] = str(uuid.uuid4())
        
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
        
        # Convert data to JSON string
        body = json.dumps(data)
        
        # Prepare request
        method = "POST"
        endpoint = "/api/v1/hf/orders/test"
        
        # Create signature for authentication
        payload = method + endpoint + body
        headers = self.signer.headers(payload)
        headers["Content-Type"] = "application/json"
        
        # Make request using http.client
        conn = http.client.HTTPSConnection(self.host)
        conn.request(method, endpoint, body, headers)
        
        # Get and process response
        res = conn.getresponse()
        response_data = res.read()
        conn.close()
        
        return json.loads(response_data.decode("utf-8"))
     
    def get_trade_history_spot(self, symbol, order_id=None, side=None, order_type=None, 
                    last_id=None, limit=20, start_at=None, end_at=None):
        """
        Get a list of the latest spot transaction details
        
        Args:
            symbol: Trading pair symbol (e.g., BTC-USDT) - required
            order_id: Unique order id (optional)
            side: 'buy' or 'sell' (optional)
            order_type: 'limit' or 'market' (optional)
            last_id: ID for pagination (optional)
            limit: Number of records to return, default 20, max 100 (optional)
            start_at: Start time in milliseconds (optional)
            end_at: End time in milliseconds (optional)
            
        Returns:
            JSON response with trade history data
        """
        # Construct query parameters
        query_params = {"symbol": symbol}
        
        # Add optional parameters if provided
        if order_id:
            query_params["orderId"] = order_id
        if side:
            query_params["side"] = side
        if order_type:
            query_params["type"] = order_type
        if last_id:
            query_params["lastId"] = last_id
        if limit:
            query_params["limit"] = limit
        if start_at:
            query_params["startAt"] = start_at
        if end_at:
            query_params["endAt"] = end_at
        
        # Build the path with query parameters
        path = f"/api/v1/hf/fills?{urlencode(query_params)}"
        method = "GET"
        
        # Create signature for authentication
        payload = method + path
        headers = self.signer.headers(payload)
        
        # Set up the connection using http.client
        conn = http.client.HTTPSConnection(self.host)
        conn.request(method, path, "", headers)
        
        # Get and process response
        res = conn.getresponse()
        data = res.read()
        conn.close()
        
        return json.loads(data.decode("utf-8"))
     
    #### MARGIN TRADING ##### 
    def get_margin_trade_history(self, symbol, trade_type, order_id=None, side=None, 
                           order_type=None, last_id=None, limit=20, start_at=None, end_at=None):
        """
        Get a list of the latest margin transaction details
        
        Args:
            symbol: Trading pair symbol (e.g., BTC-USDT) - required
            trade_type: Trade type (MARGIN_TRADE for cross margin, MARGIN_ISOLATED_TRADE for isolated) - required
            order_id: Unique order id (optional)
            side: 'buy' or 'sell' (optional)
            order_type: 'limit' or 'market' (optional)
            last_id: ID for pagination (optional)
            limit: Number of records to return, default 20, max 100 (optional)
            start_at: Start time in milliseconds (optional)
            end_at: End time in milliseconds (optional)
            
        Returns:
            JSON response with margin trade history data
        """
        # Validate trade_type
        valid_trade_types = ["MARGIN_TRADE", "MARGIN_ISOLATED_TRADE"]
        if trade_type not in valid_trade_types:
            raise ValueError(f"Invalid trade_type. Must be one of: {', '.join(valid_trade_types)}")
        
        # Construct query parameters
        query_params = {
            "symbol": symbol,
            "tradeType": trade_type
        }
        
        # Add optional parameters if provided
        if order_id:
            query_params["orderId"] = order_id
        if side:
            query_params["side"] = side
        if order_type:
            query_params["type"] = order_type
        if last_id:
            query_params["lastId"] = last_id
        if limit:
            query_params["limit"] = limit
        if start_at:
            query_params["startAt"] = start_at
        if end_at:
            query_params["endAt"] = end_at
        
        # Build the path with query parameters
        path = f"/api/v3/hf/margin/fills?{urlencode(query_params)}"
        method = "GET"
        
        # Create signature for authentication
        payload = method + path
        headers = self.signer.headers(payload)
        
        # Set up the connection using http.client
        conn = http.client.HTTPSConnection(self.host)
        conn.request(method, path, "", headers)
        
        # Get and process response
        res = conn.getresponse()
        data = res.read()
        conn.close()
        
        return json.loads(data.decode("utf-8"))

    def get_margin_closed_orders(self, symbol, trade_type, side=None, order_type=None,
                           last_id=None, limit=20, start_at=None, end_at=None):
        """
        Get a list of completed margin orders
        
        Args:
            symbol: Trading pair symbol (e.g., BTC-USDT) - required
            trade_type: Trade type (MARGIN_TRADE for cross margin, MARGIN_ISOLATED_TRADE for isolated) - required
            side: 'buy' or 'sell' (optional)
            order_type: 'limit' or 'market' (optional)
            last_id: ID for pagination (optional)
            limit: Number of records to return, default 20, max 100 (optional)
            start_at: Start time in milliseconds (optional)
            end_at: End time in milliseconds (optional)
            
        Returns:
            JSON response with closed margin orders data
        """
        # Validate trade_type
        valid_trade_types = ["MARGIN_TRADE", "MARGIN_ISOLATED_TRADE"]
        if trade_type not in valid_trade_types:
            raise ValueError(f"Invalid trade_type. Must be one of: {', '.join(valid_trade_types)}")
        
        # Construct query parameters
        query_params = {
            "symbol": symbol,
            "tradeType": trade_type
        }
        
        # Add optional parameters if provided
        if side:
            query_params["side"] = side
        if order_type:
            query_params["type"] = order_type
        if last_id:
            query_params["lastId"] = last_id
        if limit:
            query_params["limit"] = limit
        if start_at:
            query_params["startAt"] = start_at
        if end_at:
            query_params["endAt"] = end_at
        
        # Build the path with query parameters
        path = f"/api/v3/hf/margin/orders/done?{urlencode(query_params)}"
        method = "GET"
        
        # Create signature for authentication
        payload = method + path
        headers = self.signer.headers(payload)
        
        # Set up the connection using http.client
        conn = http.client.HTTPSConnection(self.host)
        conn.request(method, path, "", headers)
        
        # Get and process response
        res = conn.getresponse()
        data = res.read()
        conn.close()
        
        return json.loads(data.decode("utf-8"))

if __name__ == '__main__':
    key = os.getenv("KUCOIN_API_KEY", "")
    secret = os.getenv("KUCOIN_API_SECRET", "")
    passphrase = os.getenv("KUCOIN_API_PASSPHRASE", "")
    account_id = os.getenv("KUCOIN_ID", "")


    from datetime import datetime, timedelta

    kucoin_api = KucoinAPI(key, secret, passphrase)
    # Calculate timestamp for yesterday and today
    end_time = int(datetime.now().timestamp() * 1000)
    start_time = int((datetime.now() - timedelta(days=2)).timestamp() * 1000)

    # Test with explicit time range
    order_history = kucoin_api.get_margin_closed_orders(
        "BTC-USDT", 
        "MARGIN_ISOLATED_TRADE",
        start_at=start_time,
        end_at=end_time
    )
    print(json.dumps(order_history, indent=2))


