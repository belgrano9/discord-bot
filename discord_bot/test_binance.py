# check examples: https://github.com/binance/binance-connector-python/tree/master/examples/spot/trade

import os
from binance.spot import Spot as Client

api_key = os.getenv("BINANCE_API_KEY", "")
api_secret = os.getenv("BINANCE_API_SECRET", "")
    
client = Client(api_key=api_key, api_secret=api_secret)

#print(client.account()) # works
#print(client.margin_my_trades("BTCUSDT")) # works but empty

"""
order = client.new_margin_order(
    symbol="BTCUSDC",
    side="SELL",
    type="MARKET",
    quantity=0.0001,
    #price="150000",
    #timeInForce="GTC",
    sideEffectType = "AUTO_BORROW_REPAY"
    )
"""
#new_test_order = client.new_order_test(**params) # no error
#print(client.get_order_rate_limit())

# 1. Define Order Parameters
params = {
    "symbol": "BTCUSDC",           # The trading pair: Bitcoin against USD Coin.
    "side": "SELL",                # The direction of the order: You want to sell BTC to get USDC.
    "quantity": 0.0001,            # The amount of the base currency (BTC) to sell.
    "price": 85000,                # The price for the LIMIT order part of the OCO.
                                   # This acts as your "Take Profit" price.
                                   # The order will only execute if the market price reaches 84000 or higher.

    "stopPrice": 80000,            # The trigger price for the STOP-LOSS part of the OCO.
                                   # If the market price drops to 75000 or below, the stop-loss limit order is activated.

    "sideEffectType": "AUTO_BORROW_REPAY", # Specific to MARGIN trading.
                                           # This tells Binance:
                                           # - If you don't have enough BTC to sell, automatically borrow it.
                                           # - If the order fills (either take-profit or stop-loss), automatically use the resulting USDC to repay any outstanding BTC loan first.
}
# If i remove the stoplimit i'll get a market order for stop loss

# 2. Place the Margin OCO Order
#response = client.new_margin_oco_order(**params)
#   - `client`: This is the authenticated Binance client object you created earlier using your API keys.
#   - `.new_margin_oco_order`: This specific method on the client object is used to place a "One-Cancels-the-Other" (OCO) order on the MARGIN account.
#   - `**params`: This Python syntax unpacks the `params` dictionary. It passes each key-value pair from the dictionary as a named argument to the function. It's equivalent to writing:
#     client.new_margin_oco_order(symbol="BTCUSDC", side="SELL", quantity=0.0002, price=95000, ...)

# 3. Print the Response
#print(response)
#   - After the API call is made, Binance sends back a response.
#   - This line prints that response to your console.
#   - The response is typically a JSON object (represented as a Python dictionary by the library) containing details about the orders placed.
#   - It will usually include:
#     - Information about the order list itself (an OCO is technically an `orderList`).
#     - Details and order IDs for the two underlying orders created: the LIMIT order (take-profit) and the STOP_LOSS_LIMIT order (stop-loss).
#     - Confirmation of the parameters used.
#     - The status of the orders (likely "NEW" initially).

# 1. Fetch the full margin account response
full_api_response = client.margin_account() # Use the synchronous client method

print("\n--- Raw Full API Response ---")
print(full_api_response) # Print the entire raw response dictionary

# 2. Check structure and attempt to access the nested 'data' dictionary
print("\n--- Attempting to Isolate Nested 'data' ---")
if isinstance(full_api_response, dict):
    nested_account_data = full_api_response
    print("Successfully isolated 'data' dictionary:")
    print(nested_account_data) # Print just the nested dictionary

    # 3. Attempt to access individual keys using .get() from the nested data
    print("\n--- Accessing Individual Keys from Nested Data ---")

    # Use .get() which returns None if key is missing (safer than direct access)
    margin_level_str = nested_account_data.get('marginLevel')
    total_asset_btc_str = nested_account_data.get('totalAssetOfBtc')
    total_liability_btc_str = nested_account_data.get('totalLiabilityOfBtc')
    total_net_asset_btc_str = nested_account_data.get('totalNetAssetOfBtc') # Optional

    print(f"Value for 'marginLevel': {margin_level_str} (Type: {type(margin_level_str)})")
    print(f"Value for 'totalAssetOfBtc': {total_asset_btc_str} (Type: {type(total_asset_btc_str)})")
    print(f"Value for 'totalLiabilityOfBtc': {total_liability_btc_str} (Type: {type(total_liability_btc_str)})")
    print(f"Value for 'totalNetAssetOfBtc': {total_net_asset_btc_str} (Type: {type(total_net_asset_btc_str)})")

    # 4. Attempt to convert to float (like in the service)
    print("\n--- Attempting Float Conversion ---")
    try:
        if margin_level_str and total_asset_btc_str and total_liability_btc_str:
            margin_level_float = float(margin_level_str)
            total_asset_btc_float = float(total_asset_btc_str)
            total_liability_btc_float = float(total_liability_btc_str)
            print(f"  Successfully converted marginLevel: {margin_level_float}")
            print(f"  Successfully converted totalAssetOfBtc: {total_asset_btc_float}")
            print(f"  Successfully converted totalLiabilityOfBtc: {total_liability_btc_float}")
        else:
            print("  Skipping float conversion because one or more required string values were None.")
    except (ValueError, TypeError) as e:
        print(f"  ERROR during float conversion: {e}")

elif isinstance(full_api_response, dict):
        print(f"Error: 'data' key not found or not a dictionary in the response. Keys present: {list(full_api_response.keys())}")
else:
    print(f"Error: Response was not a dictionary. Response type: {type(full_api_response)}")
