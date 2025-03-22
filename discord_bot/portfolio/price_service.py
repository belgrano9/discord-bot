"""
Price service for portfolio tracking.
Retrieves current prices for portfolio positions.
"""

from typing import Dict, List, Any, Optional
import asyncio
from datetime import datetime
from loguru import logger

from api.prices import AsyncPricesAPI
from .models import Position


class PortfolioPriceService:
    """Service for retrieving portfolio position prices"""
    
    async def get_position_price(self, ticker: str) -> Optional[float]:
        """
        Get the current price for a position.
        
        Args:
            ticker: Stock ticker symbol
            
        Returns:
            Current price or None if unavailable
        """
        try:
            # Get current price using async API
            price_api = AsyncPricesAPI(
                ticker=ticker,
                interval="day",
                interval_multiplier=1,
                start_date=datetime.now().strftime("%Y-%m-%d"),
                end_date=datetime.now().strftime("%Y-%m-%d"),
                limit=1
            )
            
            price_data = await price_api.get_live_price()
            
            if not price_data or "price" not in price_data:
                logger.warning(f"Could not get current price for {ticker}")
                return None
                
            return float(price_data["price"])
            
        except Exception as e:
            logger.error(f"Error getting price for {ticker}: {str(e)}")
            return None
    
    async def update_position(self, position: Position) -> bool:
        """
        Update a position with current price data.
        
        Args:
            position: Position to update
            
        Returns:
            Whether the update was successful
        """
        current_price = await self.get_position_price(position.ticker)
        
        if current_price is None:
            return False
            
        position.update_price(current_price)
        return True
        
    async def update_positions_batch(self, positions: List[Position]) -> List[Position]:
        """
        Update multiple positions in parallel.
        
        Args:
            positions: List of positions to update
            
        Returns:
            List of successfully updated positions
        """
        update_tasks = []
        
        # Create tasks for all price lookups
        for position in positions:
            task = self.update_position(position)
            update_tasks.append(task)
            
        # Wait for all tasks to complete
        results = await asyncio.gather(*update_tasks, return_exceptions=True)
        
        # Filter successful updates
        updated_positions = []
        for position, result in zip(positions, results):
            if result is True:
                updated_positions.append(position)
            elif not isinstance(result, Exception):
                logger.warning(f"Failed to update position for {position.ticker}")
            else:
                logger.error(f"Error updating position for {position.ticker}: {str(result)}")
                
        return updated_positions