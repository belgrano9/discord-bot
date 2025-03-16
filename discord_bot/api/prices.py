"""
Asynchronous implementation of the Prices API client.
Refactored to use standardized async request handling and error processing.
"""
import os
from typing import Dict, Any, Optional, List, Union
import asyncio
from loguru import logger

from .base import AsyncBaseAPI, require_api_key, ApiKeyRequiredError

class AsyncPricesAPI(AsyncBaseAPI):
    """
    Asynchronous client for price data API endpoints.
    Handles requests for historical prices and live price data.
    """
    
    def __init__(
        self,
        ticker: str,
        interval: str,
        interval_multiplier: int,
        start_date: str,
        end_date: str,
        limit: Optional[int] = None,
        api_key: Optional[str] = None
    ):
        """
        Initialize the Prices API client.
        
        Args:
            ticker: Stock ticker symbol
            interval: Time interval for price data
            interval_multiplier: Multiplier for the interval
            start_date: Start date for historical data
            end_date: End date for historical data
            limit: Limit the number of results
            api_key: API key (falls back to env var if not provided)
        """
        # Get API key from environment if not provided
        if not api_key:
            api_key = os.getenv("FINANCIAL_DATASETS_API_KEY")
        
        # Initialize base class
        super().__init__(
            base_url="https://api.financialdatasets.ai",
            api_key=api_key
        )
        
        # Set instance variables
        self.ticker = ticker
        self.interval = interval
        self.interval_multiplier = interval_multiplier
        self.start_date = start_date
        self.end_date = end_date
        self.limit = limit
        
        logger.debug(f"Initialized AsyncPricesAPI for {ticker}")
    
    async def _general_get(self, endpoint: str) -> Dict[str, Any]:
        """
        Make a general GET request to the API with the appropriate parameters.
        
        Args:
            endpoint: API endpoint
            
        Returns:
            API response data
        """
        params = {
            "ticker": self.ticker,
            "interval": self.interval,
            "interval_multiplier": self.interval_multiplier,
            "start_date": self.start_date,
            "end_date": self.end_date
        }
        
        # Add limit if specified
        if self.limit is not None:
            params["limit"] = self.limit
        
        # Make the request
        return await self.get(endpoint, params=params)
    
    @require_api_key
    async def get_prices(self) -> List[Dict[str, Any]]:
        """
        Get historical price data for the specified ticker.
        
        Returns:
            List of price data points
        """
        response = await self._general_get("prices")
        success, data, error = await self.process_response(
            response, 
            success_path="prices",
            default_value=[]
        )
        
        if not success:
            logger.warning(f"Failed to get prices for {self.ticker}: {error}")
            return []
            
        return data
    
    @require_api_key
    async def get_live_price(self) -> Dict[str, Any]:
        """
        Get a live price snapshot for the specified ticker.
        
        Returns:
            Live price snapshot data
        """
        params = {"ticker": self.ticker}
        response = await self.get("prices/snapshot", params=params)
        
        success, data, error = await self.process_response(
            response, 
            success_path="snapshot",
            default_value={}
        )
        
        if not success:
            logger.warning(f"Failed to get live price for {self.ticker}: {error}")
            return {}
            
        return data
    

# Backward compatibility wrapper for the original PricesAPI
class PricesAPI:
    """
    Backward compatibility wrapper for the AsyncPricesAPI.
    Allows existing code to use the new async implementation without changes.
    """
    
    def __init__(
        self,
        ticker: str,
        interval: str,
        interval_multiplier: int,
        start_date: str,
        end_date: str,
        limit: Optional[int] = None
    ):
        """
        Initialize the backward compatibility wrapper.
        
        Args:
            ticker: Stock ticker symbol
            interval: Time interval for price data
            interval_multiplier: Multiplier for the interval
            start_date: Start date for historical data
            end_date: End date for historical data
            limit: Limit the number of results
        """
        self.async_api = AsyncPricesAPI(
            ticker, interval, interval_multiplier, start_date, end_date, limit
        )
        self.ticker = ticker
        self.interval = interval
        self.interval_multiplier = interval_multiplier
        self.start_date = start_date
        self.end_date = end_date
        self.limit = limit
    
    def _run_async(self, coroutine):
        """Helper to run async functions synchronously"""
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Create a new event loop if the current one is already running
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete(coroutine)
    
    def get_prices(self):
        """Get historical prices (sync wrapper)"""
        return self._run_async(self.async_api.get_prices())
    
    def get_live_price(self):
        """Get live price snapshot (sync wrapper)"""
        return self._run_async(self.async_api.get_live_price())