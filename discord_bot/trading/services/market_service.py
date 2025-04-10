"""
Market service for trading.
Retrieves and processes market data from Binance.
"""

from typing import Dict, List, Any, Optional, Tuple
from loguru import logger

from api.binance_connector import AsyncBinanceConnectorAPI


class MarketService:
    """Service for retrieving market data"""
    
    def __init__(self):
        """Initialize the market service"""
        self.api = AsyncBinanceConnectorAPI()
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
            # Get ticker data from Binance
            ticker_data = await self.api.get_ticker(symbol)
            
            # Check if we have 24hr data available
            if not ticker_data.get("error", False):
                # If we just have price, get 24hr data for more info
                if len(ticker_data.get("data", {})) < 3:
                    ticker_24hr = await self.api.get_ticker_24hr(symbol)
                    if not ticker_24hr.get("error", False):
                        # Merge the data
                        ticker_data["data"].update(ticker_24hr.get("data", {}))
                        
                return ticker_data.get("data", {})
                
            error_msg = ticker_data.get("msg", "Unknown error")
            logger.warning(f"Failed to get ticker data for {symbol}: {error_msg}")
            return None
            
        except Exception as e:
            logger.error(f"Error getting ticker for {symbol}: {str(e)}")
            return None
    
    async def get_trade_fees(self, symbol: str = None) -> Optional[List[Dict[str, Any]]]:
        """
        Get trade fees for specific symbols.
        
        Args:
            symbol: Trading pair symbol (optional)
            
        Returns:
            List of fee data items or None if failed
        """
        try:
            # For Binance, we need to call a different endpoint
            response = await self.api.client._run_client_method(
                'margin_fee', 
                symbols=symbol if symbol else None,
                incIsolated="TRUE"  # For isolated margin
            )
            
            if isinstance(response, dict) and response.get("error", False):
                error_msg = response.get("msg", "Unknown error")
                logger.warning(f"Failed to get trade fees: {error_msg}")
                return None
                
            # Return the list of fee data
            return response
            
        except Exception as e:
            logger.error(f"Error getting trade fees: {str(e)}")
            return None
    
    async def get_markets(self, filter_str: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get available trading pairs.
        
        Args:
            filter_str: Optional string to filter markets
            
        Returns:
            List of market data
        """
        try:
            # Get exchange info from Binance
            exchange_info = await self.api.get_exchange_info()
            
            if exchange_info.get("error", False):
                error_msg = exchange_info.get("msg", "Unknown error")
                logger.warning(f"Failed to get exchange info: {error_msg}")
                return []
                
            # Extract symbols from exchange info
            symbols = exchange_info.get("data", {}).get("symbols", [])
            
            # Filter symbols if requested
            if filter_str:
                upper_filter = filter_str.upper()
                symbols = [
                    s for s in symbols 
                    if upper_filter in s.get("symbol", "") or 
                       upper_filter in s.get("baseAsset", "") or 
                       upper_filter in s.get("quoteAsset", "")
                ]
                
            # Filter out non-spot and non-trading pairs
            symbols = [
                s for s in symbols 
                if s.get("status") == "TRADING" and 
                   (s.get("isMarginTradingAllowed", False) or s.get("isIsolatedMargin", False))
            ]
            
            return symbols
            
        except Exception as e:
            logger.error(f"Error getting markets: {str(e)}")
            return []
    
    async def get_24h_stats(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get 24-hour statistics for a symbol.
        
        Args:
            symbol: Trading pair symbol
            
        Returns:
            24-hour statistics or None if failed
        """
        try:
            # Get 24hr ticker data
            stats_data = await self.api.get_ticker_24hr(symbol)
            
            if stats_data.get("error", False):
                error_msg = stats_data.get("msg", "Unknown error")
                logger.warning(f"Failed to get 24h stats for {symbol}: {error_msg}")
                return None
                
            return stats_data.get("data", {})
            
        except Exception as e:
            logger.error(f"Error getting 24h stats for {symbol}: {str(e)}")
            return None