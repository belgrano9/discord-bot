"""
Price Service module for handling cryptocurrency price data.
Provides a service layer for fetching and processing price information from exchanges.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
import asyncio
from loguru import logger

# Import API client
from discord_bot.api.kucoin import AsyncKucoinAPI


class PriceService:
    """
    Service for fetching and processing cryptocurrency price data.
    Handles the interaction with exchange APIs and provides methods
    for retrieving formatted price information.
    """
    
    def __init__(self):
        """Initialize the price service with API clients"""
        # Initialize the KuCoin API client
        self.kucoin = AsyncKucoinAPI()
        logger.debug("PriceService initialized")
    
    async def get_symbol_data(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get ticker data for a symbol asynchronously.
        
        Args:
            symbol: Trading pair symbol (e.g. "BTC-USDT")
            
        Returns:
            Dictionary with ticker data or None if unavailable
        """
        try:
            # Use our async API client to fetch ticker data
            ticker_data = await self.kucoin.get_ticker(symbol)
            
            if ticker_data and ticker_data.get("code") == "200000":
                return ticker_data.get("data", {})
            
            logger.warning(f"Failed to get ticker data for {symbol}: {ticker_data.get('msg', 'Unknown error')}")
            return None
            
        except Exception as e:
            logger.error(f"Error fetching data for {symbol}: {str(e)}")
            return None
    
    async def get_markets(self) -> List[Dict[str, Any]]:
        """
        Get list of available trading pairs.
        
        Returns:
            List of available markets or empty list if unavailable
        """
        try:
            # Get market list from KuCoin
            markets_data = await self.kucoin.get_market_list()
            
            if markets_data and markets_data.get("code") == "200000":
                return markets_data.get("data", [])
            
            logger.warning(f"Failed to get market list: {markets_data.get('msg', 'Unknown error')}")
            return []
            
        except Exception as e:
            logger.error(f"Error fetching market list: {str(e)}")
            return []
    
    async def get_24h_stats(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get 24-hour trading statistics for a symbol.
        
        Args:
            symbol: Trading pair symbol (e.g. "BTC-USDT")
            
        Returns:
            Dictionary with 24h stats or None if unavailable
        """
        try:
            # Get 24h stats from KuCoin
            stats_data = await self.kucoin.get_24h_stats(symbol)
            
            if stats_data and stats_data.get("code") == "200000":
                return stats_data.get("data", {})
            
            logger.warning(f"Failed to get 24h stats for {symbol}: {stats_data.get('msg', 'Unknown error')}")
            return None
            
        except Exception as e:
            logger.error(f"Error fetching 24h stats for {symbol}: {str(e)}")
            return None
    
    def calculate_price_changes(self, current_price: float, history: List[float]) -> Dict[str, float]:
        """
        Calculate price changes over different time periods.
        
        Args:
            current_price: Current price value
            history: List of historical price points (oldest first)
            
        Returns:
            Dictionary with calculated changes
        """
        changes = {
            "change_1m": 0.0,
            "change_5m": 0.0,
            "change_15m": 0.0,
            "change_since_start": 0.0
        }
        
        if not history or len(history) < 2:
            return changes
        
        # Calculate changes for different timeframes
        if len(history) > 1:  # 1-minute change (or last interval)
            changes["change_1m"] = ((current_price - history[-2]) / history[-2]) * 100
        
        if len(history) > 5:  # 5-minute change (or 5 intervals)
            changes["change_5m"] = ((current_price - history[-6]) / history[-6]) * 100
        
        if len(history) > 15:  # 15-minute change (or 15 intervals)
            changes["change_15m"] = ((current_price - history[-16]) / history[-16]) * 100
        
        # Change since tracking started
        changes["change_since_start"] = ((current_price - history[0]) / history[0]) * 100
        
        return changes
    
    def calculate_statistics(self, history: List[float]) -> Dict[str, float]:
        """
        Calculate statistical metrics for price history.
        
        Args:
            history: List of price history points
            
        Returns:
            Dictionary with statistical values
        """
        if not history:
            return {
                "high": 0.0,
                "low": 0.0,
                "avg": 0.0,
                "range": 0.0,
                "volatility": 0.0
            }
        
        # Basic statistics
        high = max(history)
        low = min(history)
        avg = sum(history) / len(history)
        price_range = high - low
        
        # Calculate volatility (standard deviation)
        if len(history) > 1:
            # Calculate mean
            mean = sum(history) / len(history)
            # Calculate sum of squared differences from mean
            sq_diff_sum = sum((x - mean) ** 2 for x in history)
            # Calculate variance and then standard deviation
            variance = sq_diff_sum / len(history)
            volatility = variance ** 0.5
        else:
            volatility = 0.0
        
        return {
            "high": high,
            "low": low,
            "avg": avg,
            "range": price_range,
            "volatility": volatility
        }
    
    def format_price_change(self, change: float) -> str:
        """
        Format a price change with sign and percentage.
        
        Args:
            change: Price change percentage
            
        Returns:
            Formatted string with sign and percentage
        """
        sign = "+" if change >= 0 else ""
        return f"{sign}{change:.2f}%"
    
    def categorize_movement(self, history: List[float]) -> Dict[str, int]:
        """
        Categorize price movements as up, down, or sideways.
        
        Args:
            history: List of price history points
            
        Returns:
            Dictionary with counts of different movement types
        """
        if len(history) < 2:
            return {"up": 0, "down": 0, "sideways": 0}
        
        # Calculate consecutive price changes
        changes = []
        for i in range(1, len(history)):
            change_pct = ((history[i] - history[i-1]) / history[i-1]) * 100
            changes.append(change_pct)
        
        # Count movement types
        up_moves = sum(1 for c in changes if c > 0.1)  # More than 0.1% up
        down_moves = sum(1 for c in changes if c < -0.1)  # More than 0.1% down
        sideways_moves = sum(1 for c in changes if -0.1 <= c <= 0.1)  # Between -0.1% and 0.1%
        
        return {
            "up": up_moves,
            "down": down_moves,
            "sideways": sideways_moves
        }