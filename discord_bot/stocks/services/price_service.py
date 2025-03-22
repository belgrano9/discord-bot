"""
Service for retrieving price data from APIs.
Handles requests for current and historical price data.
"""

import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from loguru import logger

from api.prices import AsyncPricesAPI


class PriceService:
    """Service for retrieving price data"""
    
    async def get_current_price(self, ticker: str) -> Dict[str, Any]:
        """
        Get the current price for a ticker.
        
        Args:
            ticker: Stock ticker symbol
            
        Returns:
            Dictionary with price data or empty dict if failed
        """
        try:
            # Get today's date
            today = datetime.now().strftime("%Y-%m-%d")
            
            price_api = AsyncPricesAPI(
                ticker=ticker.upper(),
                interval="day",
                interval_multiplier=1,
                start_date=today,
                end_date=today,
                limit=1
            )
            
            price_data = await price_api.get_live_price()
            
            if not price_data or "price" not in price_data:
                logger.warning(f"No price data found for {ticker}")
                return {}
                
            return price_data
            
        except Exception as e:
            logger.error(f"Error fetching current price for {ticker}: {str(e)}")
            return {}
    
    async def get_historical_prices(self, ticker: str, days: int = 1) -> List[Dict[str, Any]]:
        """
        Get historical price data for a ticker.
        
        Args:
            ticker: Stock ticker symbol
            days: Number of days of history to retrieve
            
        Returns:
            List of price data dictionaries
        """
        try:
            # Calculate date range
            end_date = datetime.now().strftime("%Y-%m-%d")
            start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
            
            price_api = AsyncPricesAPI(
                ticker=ticker.upper(),
                interval="day",
                interval_multiplier=1,
                start_date=start_date,
                end_date=end_date,
                limit=days
            )
            
            prices = await price_api.get_prices()
            
            if not prices:
                logger.warning(f"No historical price data found for {ticker}")
                return []
                
            return prices
            
        except Exception as e:
            logger.error(f"Error fetching historical prices for {ticker}: {str(e)}")
            return []
    
    async def calculate_price_changes(self, prices: List[Dict[str, Any]]) -> Dict[str, float]:
        """
        Calculate price changes from a list of price data.
        
        Args:
            prices: List of price data dictionaries
            
        Returns:
            Dictionary with price change metrics
        """
        if not prices or len(prices) < 1:
            return {
                "latest_price": 0.0,
                "price_change": 0.0,
                "price_change_pct": 0.0
            }
            
        try:
            import polars as pl
            
            # Convert to DataFrame
            df = pl.DataFrame(prices)
            
            # Get the date column name
            date_column = next(
                (
                    col
                    for col in df.columns
                    if "date" in col.lower() or "time" in col.lower()
                ),
                None,
            )
            
            if not date_column:
                return {
                    "latest_price": float(prices[0].get("close", 0)),
                    "price_change": 0.0,
                    "price_change_pct": 0.0
                }
                
            # Get latest price
            latest = df.sort(date_column, descending=True).head(1)
            latest_price = latest["close"][0]
            
            # Calculate price change
            if len(df) > 1:
                prev_close = df.sort(date_column, descending=True).slice(1, 2)["close"][0]
                price_change = latest_price - prev_close
                price_change_pct = (price_change / prev_close) * 100
            else:
                price_change = 0.0
                price_change_pct = 0.0
                
            return {
                "latest_price": latest_price,
                "price_change": price_change,
                "price_change_pct": price_change_pct
            }
            
        except Exception as e:
            logger.error(f"Error calculating price changes: {str(e)}")
            return {
                "latest_price": float(prices[0].get("close", 0)),
                "price_change": 0.0,
                "price_change_pct": 0.0
            }