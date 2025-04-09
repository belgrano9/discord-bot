import os
import asyncio
from loguru import logger
import time
import json
# Import your Binance API client
from discord_bot.api.binance import AsyncBinanceAPI, BinanceAPI
from dotenv import load_dotenv
import os

load_dotenv()


# Now os.getenv() will work with those variables
import os
my_var = os.getenv('MY_VARIABLE')
# Configure logger
logger.add("binance_test.log", rotation="10 MB")

async def test_public_endpoints():
    print("Testing public endpoints...")
    api = AsyncBinanceAPI()
    
    # Test ticker endpoint
    ticker = await api.get_ticker(symbol="BTCUSDT")
    print(f"BTC/USDT Ticker: {ticker}")
    
    # Test 24hr statistics
    stats = await api.get_ticker_24hr(symbol="BTCUSDT")
    print(f"24hr Stats: Price change: {stats.get('priceChange')}, Volume: {stats.get('volume')}")
    
    return True

async def test_authenticated_endpoints():
    print("Testing authenticated endpoints...")
    
    # Check if API keys are set
    api_key = os.getenv("BINANCE_API_KEY", "")
    api_secret = os.getenv("BINANCE_API_SECRET", "")
    
    if not api_key or not api_secret:
        print("API keys not found in environment variables. Skipping authenticated tests.")
        return False
    
    api = AsyncBinanceAPI(api_key=api_key, api_secret=api_secret)
    
    # Test margin pairs
    try:
        margin_pairs = await api.get_margin_pairs()
        print(f"Successfully retrieved {len(margin_pairs)} margin pairs")
        
        # Test margin account info
        account = await api.get_margin_account()
        print(f"Margin account retrieved: {account['marginLevel'] if 'marginLevel' in account else 'N/A'}")
        return True
    except Exception as e:
        print(f"Authentication test failed: {str(e)}")
        return False


async def test_real_margin_order():
    print("\nWARNING: About to place a REAL margin order with REAL funds!")
    print("Ctrl+C now to cancel")
    await asyncio.sleep(5)  # Give time to cancel
    
    api_key = os.getenv("BINANCE_API_KEY")
    api_secret = os.getenv("BINANCE_API_SECRET")
    
    if not api_key or not api_secret:
        print("API keys not found. Skipping test.")
        return False
    
    api = AsyncBinanceAPI(api_key=api_key, api_secret=api_secret)
    
    try:
        # Get current price
        ticker = await api.get_ticker("BTCUSDT")
        current_price = float(ticker.get('price', 0))
        print(f"Current BTC price: ${current_price}")
        
        # Set parameters for a tiny order at a price that won't execute
        symbol = "BTCUSDT"
        side = "BUY"
        order_type = "LIMIT"
        price = current_price * 0.7  # 30% below market price - won't execute
        quantity = 0.001  # Minimal amount
        
        print(f"\nPlacing LIMIT {side} order: {quantity} {symbol} @ ${price}")
        print("This order will likely NOT execute due to price being far from market")
        
        response = await api.create_margin_order(
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price
        )
        
        print(f"Order placed successfully!")
        print(json.dumps(response, indent=2))
        
        return True
    except Exception as e:
        print(f"Order placement failed: {str(e)}")
        return False



async def test_margin_stop_order():
    print("\nTesting margin stop order creation (simulated, will not execute)...")
    
    # Check if API keys are set
    api_key = os.getenv("BINANCE_API_KEY")
    api_secret = os.getenv("BINANCE_API_SECRET")
    
    if not api_key or not api_secret:
        print("API keys not found in environment variables. Skipping test.")
        return False
    
    api = AsyncBinanceAPI(api_key=api_key, api_secret=api_secret)
    
    try:
        # Define test parameters for a stop-limit order that won't execute
        symbol = "BTCUSDT"
        side = "SELL"
        order_type = "STOP_LOSS_LIMIT"
        stop_price = 15000.00  # Stop price far from current price
        price = 14900.00  # Limit price
        quantity = 0.001  # Small quantity
        time_in_force = "GTC"
        is_isolated = True
        
        # Print what would be submitted
        print(f"Would submit stop order: {symbol} {side} {quantity} @ {price} (Stop: {stop_price})")
        print("Parameters that would be sent:")
        
        params = {
            "symbol": symbol,
            "side": side,
            "type": order_type,
            "timeInForce": time_in_force,
            "quantity": quantity,
            "price": price,
            "stopPrice": stop_price,
            "isIsolated": "TRUE" if is_isolated else "FALSE",
            "newClientOrderId": f"test_stop_{int(time.time())}"
        }
        
        print(json.dumps(params, indent=2))
        
        # To actually place the order, uncomment:
        # order = await api.create_margin_order(
        #     symbol=symbol,
        #     side=side,
        #     order_type=order_type,
        #     quantity=quantity,
        #     price=price,
        #     stop_price=stop_price,
        #     time_in_force=time_in_force,
        #     is_isolated=is_isolated
        # )
        # print(f"Stop order response: {order}")
        
        return True
    except Exception as e:
        print(f"Margin stop order test failed: {str(e)}")
        return False


async def main():
    public_test_success = await test_public_endpoints()
    auth_test_success = await test_authenticated_endpoints()
    add_margin_order_success = await test_real_margin_order()
    
    print("\nTest Results:")
    print(f"Public Endpoints: {'✅ Success' if public_test_success else '❌ Failed'}")
    print(f"Authenticated Endpoints: {'✅ Success' if auth_test_success else '❌ Failed'}")
    print(f"Placing margin order : {'✅ Success' if add_margin_order_success else '❌ Failed'}")



if __name__ == "__main__":
    asyncio.run(main())