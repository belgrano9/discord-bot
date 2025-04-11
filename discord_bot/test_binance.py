# check examples: https://github.com/binance/binance-connector-python/tree/master/examples/spot/trade

import os
from binance.spot import Spot as Client

api_key = os.getenv("BINANCE_API_KEY", "")
api_secret = os.getenv("BINANCE_API_SECRET", "")
    
client = Client(api_key=api_key, api_secret=api_secret)

#print(client.account()) # works
#print(client.margin_my_trades("BTCUSDT")) # works but empty

order = client.new_margin_order(
    symbol="BTCUSDC",
    side="SELL",
    type="MARKET",
    quantity=0.0001,
    #price="150000",
    #timeInForce="GTC",
    sideEffectType = "AUTO_BORROW_REPAY"
    )

print(order)

#new_test_order = client.new_order_test(**params) # no error
#print(client.get_order_rate_limit())