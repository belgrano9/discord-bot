import os
import json
import time
import hashlib
import hmac
import requests
from typing import Dict, List, Any, Optional, Tuple, Union


class BitvavoRestClient:
    """
    A class to interact with the Bitvavo REST API.
    """

    def __init__(self, api_key: str, api_secret: str, access_window: int = 10000):
        self.api_key = api_key
        self.api_secret = api_secret
        self.access_window = access_window
        self.base = "https://api.bitvavo.com/v2"

    def place_order(self, market: str, side: str, order_type: str, body: dict):
        """
        Send an instruction to Bitvavo to buy or sell a quantity of digital assets at a specific price.
        """
        body["market"] = market
        body["side"] = side
        body["orderType"] = order_type
        return self.private_request(method="POST", endpoint="/order", body=body)

    def private_request(
        self, endpoint: str, body: dict | None = None, method: str = "GET"
    ):
        """
        Create the headers to authenticate your request, then make the call to Bitvavo API.
        """
        now = int(time.time() * 1000)
        sig = self.create_signature(now, method, endpoint, body)
        url = self.base + endpoint
        headers = {
            "bitvavo-access-key": self.api_key,
            "bitvavo-access-signature": sig,
            "bitvavo-access-timestamp": str(now),
            "bitvavo-access-window": str(self.access_window),
        }

        try:
            r = requests.request(method=method, url=url, headers=headers, json=body)
            r.raise_for_status()  # Raise an exception for bad status codes

            if not r.text:
                return {}

            return r.json()
        except requests.exceptions.RequestException as e:
            print(f"Request error: {e}")
            return {
                "error": f"Request failed: {str(e)}",
                "status_code": getattr(e.response, "status_code", None),
            }
        except json.JSONDecodeError as e:
            print(f"JSON decode error: {e}")
            return {
                "error": "Invalid JSON response",
                "status_code": r.status_code,
                "text": r.text[:100],
            }

    def create_signature(
        self, timestamp: int, method: str, url: str, body: dict | None
    ):
        """
        Create a hashed code to authenticate requests to Bitvavo API.
        """
        string = str(timestamp) + method + "/v2" + url
        if (body is not None) and (len(body.keys()) != 0):
            string += json.dumps(body, separators=(",", ":"))
        signature = hmac.new(
            self.api_secret.encode("utf-8"), string.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        return signature

    def public_request(self, endpoint: str, params: dict = None):
        """
        Make a public request to the Bitvavo API without authentication.
        """
        url = self.base + endpoint
        try:
            r = requests.get(url, params=params)
            r.raise_for_status()  # Raise an exception for bad status codes

            if not r.text:
                return {}

            return r.json()
        except requests.exceptions.RequestException as e:
            print(f"Request error: {e}")
            return {
                "error": f"Request failed: {str(e)}",
                "status_code": getattr(e.response, "status_code", None),
            }
        except json.JSONDecodeError as e:
            print(f"JSON decode error: {e}")
            return {
                "error": "Invalid JSON response",
                "status_code": r.status_code,
                "text": r.text[:100] if hasattr(r, "text") else "No text",
            }


class BitvavoHandler:
    """Handler for Bitvavo API operations"""

    def __init__(self):
        """Initialize the Bitvavo API client"""
        self.api_key = os.getenv("BITVAVO_API_KEY", "")
        self.api_secret = os.getenv("BITVAVO_API_SECRET", "")
        self.client = BitvavoRestClient(self.api_key, self.api_secret)

    def check_authentication(self) -> Tuple[bool, str]:
        """Check if API credentials are valid and have proper permissions"""
        try:
            response = self.client.private_request(endpoint="/account")
            if "errorCode" in response or "error" in response:
                return (
                    False,
                    f"Authentication error: {response.get('error', 'Unknown error')}",
                )
            return True, ""
        except Exception as e:
            return False, f"Error checking authentication: {str(e)}"

    def get_markets(self, filter_str: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get available markets from Bitvavo"""
        try:
            markets = self.client.public_request(endpoint="/markets")
            if "error" in markets:
                print(f"Error in markets response: {markets.get('error')}")
                return []

            if filter_str:
                filter_str = filter_str.upper()
                markets = [m for m in markets if filter_str in m["market"]]
            return markets
        except Exception as e:
            print(f"Error getting markets: {str(e)}")
            return []

    def get_ticker(self, market: str) -> Dict[str, Any]:
        """Get ticker information for a specific market"""
        try:
            # Convert slash format to dash format if needed
            market = market.replace("/", "-")

            # Using correct endpoint format per Bitvavo API documentation
            response = self.client.public_request(endpoint=f"/ticker?market={market}")

            if isinstance(response, list) and len(response) > 0:
                return {"price": response[0].get("price", "0")}

            if "error" in response:
                print(f"API error getting ticker: {response.get('error')}")

            # Fallback for simulation
            return {"price": "0"}

        except Exception as e:
            print(f"Error getting ticker: {str(e)}")
            return {"price": "0"}

    def get_ticker_24h(self, market: str) -> Dict[str, Any]:
        """Get 24 hour ticker information"""
        try:
            # Using correct endpoint format per Bitvavo API documentation
            response = self.client.public_request(
                endpoint=f"/ticker/24h?market={market}"
            )
            if isinstance(response, list) and len(response) > 0:
                return response[0]

            if "error" in response:
                print(f"API error getting 24h ticker: {response.get('error')}")
            return {}
        except Exception as e:
            print(f"Error getting 24h ticker: {str(e)}")
            return {}

    def get_order_book(self, market: str, depth: int = 10) -> Dict[str, Any]:
        """Get order book for a market"""
        try:
            params = {"market": market, "depth": depth}
            response = self.client.public_request(endpoint="/orderbook", params=params)
            if "error" in response:
                print(f"API error getting order book: {response.get('error')}")
            return response
        except Exception as e:
            print(f"Error getting order book: {str(e)}")
            return {"bids": [], "asks": []}

    def place_real_limit_order(
        self, market: str, side: str, amount: float, price: float
    ) -> Dict[str, Any]:
        """Place a real limit order on Bitvavo"""
        body = {"amount": str(amount), "price": str(price)}
        return self.client.place_order(market, side, "limit", body)

    def place_real_market_order(
        self, market: str, side: str, amount: float
    ) -> Dict[str, Any]:
        """Place a real market order on Bitvavo"""
        body = {"amount": str(amount)}
        return self.client.place_order(market, side, "market", body)

    def cancel_order(self, market: str, order_id: str) -> Dict[str, Any]:
        """Cancel an order"""
        body = {"orderId": order_id, "market": market}
        return self.client.private_request(
            endpoint="/order", body=body, method="DELETE"
        )

    def get_order(self, market: str, order_id: str) -> Dict[str, Any]:
        """Get information about an order"""
        params = {"market": market, "orderId": order_id}
        return self.client.private_request(endpoint="/order", body=params)

    def get_orders(self, market: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get list of open orders"""
        params = {"market": market, "limit": limit}
        response = self.client.private_request(endpoint="/orders", body=params)
        if isinstance(response, dict) and "error" in response:
            print(f"API error getting orders: {response.get('error')}")
            return []
        return response if isinstance(response, list) else []

    def get_trades(self, market: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get trade history"""
        params = {"market": market, "limit": limit}
        response = self.client.private_request(endpoint="/trades", body=params)
        if isinstance(response, dict) and "error" in response:
            print(f"API error getting trades: {response.get('error')}")
            return []
        return response if isinstance(response, list) else []

    def get_balance(
        self, symbol: Optional[str] = None
    ) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
        """Get account balance"""
        try:
            balances = self.client.private_request(endpoint="/balance")
            if isinstance(balances, dict) and (
                "errorCode" in balances or "error" in balances
            ):
                raise ValueError(
                    f"API error: {balances.get('error', balances.get('errorCode', 'Unknown error'))}"
                )

            if not isinstance(balances, list):
                return (
                    []
                    if symbol is None
                    else {"symbol": symbol, "available": "0", "inOrder": "0"}
                )

            if symbol:
                for balance in balances:
                    if balance.get("symbol") == symbol:
                        return balance
                return {"symbol": symbol, "available": "0", "inOrder": "0"}
            return balances
        except Exception as e:
            raise ValueError(f"Error retrieving balance: {str(e)}")

    def simulate_order(self, market: str, side: str, amount: float) -> Dict[str, Any]:
        """Simulate placing an order (for testing)"""
        try:
            # Get current price
            ticker = self.get_ticker(market)

            # Use a default price for simulation if API fails
            if "price" not in ticker or ticker["price"] == "0":
                current_price = 1000.0 if "BTC" in market else 100.0
                print(f"Using default price {current_price} for simulation")
            else:
                current_price = float(ticker["price"])

            # Generate a test order ID
            order_id = f"test-{int(time.time())}"

            # Calculate total value
            total_value = amount * current_price

            # Return simulated order info
            return {
                "orderId": order_id,
                "market": market,
                "side": side,
                "amount": str(amount),
                "price": str(current_price),
                "total": str(total_value),
                "status": "test",
                "created": int(time.time() * 1000),
            }
        except Exception as e:
            print(f"Error simulating order: {str(e)}")
            return {
                "orderId": f"error-{int(time.time())}",
                "market": market,
                "side": side,
                "amount": str(amount),
                "price": "0",
                "total": "0",
                "status": "error",
                "error": str(e),
            }


if __name__ == "__main__":
    # check authentication
    bitvavo = BitvavoHandler()
    auth_result = bitvavo.check_authentication()
    print(auth_result)

    # Test getting list of markets first to verify API connection
    print("\nTesting get_markets method...")
    markets = bitvavo.get_markets()
    print(f"Found {len(markets)} markets")
    if markets and len(markets) > 0:
        first_market = markets[0]["market"]
        print(f"Using first market for testing: {first_market}")
    else:
        first_market = "BTC-EUR"
        print(f"No markets found, using default: {first_market}")

    # Test the fixed ticker method with proper debugging
    print("\nTesting get_ticker method...")
    ticker_result = bitvavo.get_ticker(first_market)
    print(f"Ticker result: {ticker_result}")

    # Test simulate_order with robustness to API failures
    print("\nTesting simulate_order method...")
    order_result = bitvavo.simulate_order(first_market, "buy", 0.001)
    print(f"Order simulation result: {order_result}")
