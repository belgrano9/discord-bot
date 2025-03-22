import asyncio
from loguru import logger
from discord_bot.api.kucoin import AsyncKucoinAPI
import pytest

# Configure logger
logger.remove()
logger.add(lambda msg: print(msg), level="DEBUG")

async def test_async_kucoin_api():
    """Test and demonstrate AsyncKucoinAPI functionality"""
    # Initialize the API client with credentials from environment variables
    api = AsyncKucoinAPI()
    
    # Test public endpoints (no authentication required)
    logger.info("Testing public endpoints...")
    
    # Test get_ticker
    ticker_data = await api.get_ticker("BTC-USDT")
    if ticker_data.get("code") == "200000":
        logger.success(f"Successfully retrieved ticker data: {ticker_data['data']}")
    else:
        logger.error(f"Failed to get ticker data: {ticker_data.get('msg', 'Unknown error')}")
    
    # Test authenticated endpoints (only if credentials are available)
    if api.api_key and api.api_secret and api.passphrase:
        logger.info("Testing authenticated endpoints...")
        
        # Test get_isolated_margin_accounts
        accounts = await api.get_isolated_margin_accounts(symbol="BTC-USDT")
        if accounts.get("code") == "200000":
            logger.success(f"Successfully retrieved margin accounts")
        else:
            logger.error(f"Failed to get margin accounts: {accounts.get('msg', 'Unknown error')}")
        
        # Add more authenticated method tests as needed
    else:
        logger.warning("Skipping authenticated endpoints test due to missing API credentials")

async def test_deposit_address():
    api = AsyncKucoinAPI()
    result = await api.get_deposit_address("BTC")
    logger.info(f"Deposit address result: {result}")

async def test_get_account_list():
    api = AsyncKucoinAPI()
    result = await api.get_account_list()
    logger.info(f"Account list result: {result}")

async def test_get_trade_fees():
    api = AsyncKucoinAPI()
    result = await api.get_trade_fees()
    logger.info(f"Trade fees: {result}")





if __name__ == "__main__":
    # Create and run the event loop
    loop = asyncio.get_event_loop()
    
    # Run the main test function
    logger.info("Starting AsyncKucoinAPI tests")
    loop.run_until_complete(test_async_kucoin_api())
    
    # Uncomment to test new methods:
    loop.run_until_complete(test_get_account_list())
    loop.run_until_complete(test_get_trade_fees())
    
    logger.info("All tests completed")