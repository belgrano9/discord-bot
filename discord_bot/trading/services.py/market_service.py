"""
Market data service for trading.
Retrieves and processes market data from exchange APIs.
"""

from typing import Dict, List, Any, Optional, Tuple
from loguru import logger

from api.kucoin import AsyncKucoinAPI


class MarketService:
    """Service for retrieving market data"""
    
    def __init__(self):
        """Initialize the market service"""
        self.api = AsyncKucoinAPI()
        logger.debug("Initialized MarketService")
    
    async def get_ticker(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get current ticker data for a symbol.
        
        Args:
            symbol: Trading pair symbol
            
        Returns:
            Ticker data or None if failed
        """
        try:
            ticker_data = await self.api.get_ticker(symbol)
            
            if not ticker_data or ticker_data.get("code") != "200000":
                error_msg = ticker_data.get("msg", "Unknown error") if ticker_data else "No response"
                logger.warning(f"Failed to get ticker data for {symbol}: {error_msg}")
                return None
                
            return ticker_data.get("data", {})
            
        except Exception as e:
            logger.error(f"Error getting ticker for {symbol}: {str(e)}")
            return None
    
    async def get_trade_fees(self, symbol: str) -> List[Dict[str, Any]]:
        """
        Get trading fees for a symbol.
        
        Args:
            symbol: Trading pair symbol
            
        Returns:
            List of fee data items
        """
        try:
            fees_data = await self.api.get_trade_fees(symbol)
            
            if not fees_data or fees_data.get("code") != "200000":
                error_msg = fees_data.get("msg", "Unknown error") if fees_data else "No response"
                logger.warning(f"Failed to get fee data: {error_msg}")
                return []
                
            return fees_data.get("data", [])
            
        except Exception as e:
            logger.error(f"Error getting trade fees for {symbol}: {str(e)}")
            return []
    
    async def get_24h_stats(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get 24-hour market statistics for a symbol.
        
        Args:
            symbol: Trading pair symbol
            
        Returns:
            Market statistics or None if failed
        """
        try:
            stats_data = await self.api.get_24h_stats(symbol)
            
            if not stats_data or stats_data.get("code") != "200000":
                error_msg = stats_data.get("msg", "Unknown error") if stats_data else "No response"
                logger.warning(f"Failed to get 24h stats for {symbol}: {error_msg}")
                return None
                
            return stats_data.get("data", {})
            
        except Exception as e:
            logger.error(f"Error getting 24h stats for {symbol}: {str(e)}")
            return None