# check examples: https://github.com/binance/binance-connector-python/tree/master/examples/spot/trade

import os
from binance.spot import Spot as Client

api_key = os.getenv("BINANCE_API_KEY", "")
api_secret = os.getenv("BINANCE_API_SECRET", "")
    
client = Client(api_key=api_key, api_secret=api_secret)

#print(client.account()) # works
print(client.my_trades("BTCUSDC", limit=2)) # works but empty

params = {
    "symbol": "BTCUSDT",
    "side": "BUY",
    "type": "LIMIT",
    "timeInForce": "GTC",
    "quantity": 0.001,
    "price": 49500,
}

#new_test_order = client.new_order_test(**params) # no error
print(client.get_order_rate_limit())
