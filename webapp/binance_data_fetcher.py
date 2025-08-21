import os
from dotenv import load_dotenv
from binance.client import Client
from datetime import datetime
import pandas as pd

# Load environment variables
load_dotenv()

# Get credentials from environment
api_key = os.getenv('BINANCE_API_KEY')
api_secret = os.getenv('BINANCE_API_SECRET')

print("Step 1: Checking environment variables...")
print(f"API Key found: {'Yes' if api_key else 'No'}")
print(f"API Secret found: {'Yes' if api_secret else 'No'}")
print(f"API Key (first 5 chars): {api_key[:5]}..." if api_key else "No API key found")

try:
    # Initialize the client
    print("\nStep 2: Initializing Binance client...")
    client = Client(api_key, api_secret)
    
    # Test 1: Get server time (no authentication needed)
    print("\nStep 3: Testing public endpoint (server time)...")
    server_time = client.get_server_time()
    server_datetime = datetime.fromtimestamp(server_time['serverTime']/1000)
    print(f"Server time: {server_datetime}")
    print(f"Connection successful! ✓")
    
except Exception as e:
    print(f"Error connecting to Binance: {e}")
    print("This might mean:")
    print("- Your API credentials are incorrect")
    print("- You need to whitelist your IP on Binance")
    print("- Network connection issues")

try:
    print("\nStep 4: Testing market data endpoint...")
    
    # Get recent trades for BTC/USDT
    ticker = client.get_ticker(symbol='BTCUSDT')
    print(f"BTC/USDT current price: ${float(ticker['lastPrice']):,.2f}")
    
    # Get available symbols
    print("\nStep 5: Fetching available crypto pairs...")
    exchange_info = client.get_exchange_info()
    
    # Filter for USD stablecoins
    usdt_pairs = [s['symbol'] for s in exchange_info['symbols'] 
                  if s['symbol'].endswith('USDT') and s['status'] == 'TRADING']
    
    print(f"Found {len(usdt_pairs)} USDT trading pairs")
    print("Popular pairs:", usdt_pairs[:10])
    
except Exception as e:
    print(f"Error fetching market data: {e}")

try:
    print("\nStep 6: Testing historical data fetch...")
    
    # Get candlestick data
    klines = client.get_klines(
        symbol='BTCUSDT',
        interval=Client.KLINE_INTERVAL_30MINUTE,  # 30m candles
        limit=10  # Last 10 candles
    )
    
    # Convert to DataFrame for easier viewing
    df = pd.DataFrame(klines, columns=[
        'timestamp', 'open', 'high', 'low', 'close', 'volume',
        'close_time', 'quote_volume', 'trades', 'taker_buy_base',
        'taker_buy_quote', 'ignore'
    ])
    
    # Convert timestamp to datetime
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df['close_time'] = pd.to_datetime(df['close_time'], unit='ms')
    
    # Convert price columns to float
    price_columns = ['open', 'high', 'low', 'close', 'volume']
    df[price_columns] = df[price_columns].astype(float)
    
    print("\nLast 5 candles (30-minute):")
    print(df[['timestamp', 'open', 'high', 'low', 'close', 'volume']].tail())
    
    # Test different timeframes
    print("\nStep 7: Testing available timeframes...")
    timeframes = {
        '1m': Client.KLINE_INTERVAL_1MINUTE,
        '5m': Client.KLINE_INTERVAL_5MINUTE,
        '15m': Client.KLINE_INTERVAL_15MINUTE,
        '30m': Client.KLINE_INTERVAL_30MINUTE,
        '1h': Client.KLINE_INTERVAL_1HOUR,
        '4h': Client.KLINE_INTERVAL_4HOUR,
        '1d': Client.KLINE_INTERVAL_1DAY,
    }
    
    for tf_name, tf_value in timeframes.items():
        try:
            test_kline = client.get_klines(symbol='BTCUSDT', interval=tf_value, limit=1)
            print(f"✓ {tf_name} timeframe: Available")
        except:
            print(f"✗ {tf_name} timeframe: Not available")
            
except Exception as e:
    print(f"Error fetching historical data: {e}")

