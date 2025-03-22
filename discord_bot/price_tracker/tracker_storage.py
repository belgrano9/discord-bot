"""
Storage manager for price tracking.
Handles storing and retrieving tracked price data.
"""

from typing import Dict, List, Any, Optional, Set
from datetime import datetime
import asyncio
from loguru import logger

from .tracker_model import TrackedPrice


class TrackerStorage:
    """Manage storing and retrieving tracked price data"""
    
    def __init__(self):
        """Initialize the tracker storage"""
        self.tracked_prices: Dict[str, TrackedPrice] = {}
        logger.debug("Initialized TrackerStorage")
    
    def add_tracked_price(self, tracked: TrackedPrice) -> None:
        """
        Add a new tracked price.
        
        Args:
            tracked: The TrackedPrice object to add
        """
        self.tracked_prices[tracked.symbol] = tracked
        logger.info(f"Added price tracker for {tracked.symbol} with {tracked.interval}s interval")
    
    def remove_tracked_price(self, symbol: str) -> Optional[TrackedPrice]:
        """
        Remove a tracked price by symbol.
        
        Args:
            symbol: The symbol to remove
            
        Returns:
            The removed TrackedPrice object or None if not found
        """
        if symbol in self.tracked_prices:
            tracked = self.tracked_prices.pop(symbol)
            logger.info(f"Removed price tracker for {symbol}")
            return tracked
        
        return None
    
    def get_tracked_price(self, symbol: str) -> Optional[TrackedPrice]:
        """
        Get a tracked price by symbol.
        
        Args:
            symbol: The symbol to retrieve
            
        Returns:
            The TrackedPrice object or None if not found
        """
        return self.tracked_prices.get(symbol)
    
    def get_all_tracked_prices(self) -> Dict[str, TrackedPrice]:
        """
        Get all tracked prices.
        
        Returns:
            Dictionary of symbol -> TrackedPrice objects
        """
        return self.tracked_prices
    
    def get_symbols_to_update(self) -> List[str]:
        """
        Get symbols that need updating based on their interval.
        
        Returns:
            List of symbols that need updating
        """
        current_time = datetime.now()
        symbols_to_update = []
        
        for symbol, tracked in self.tracked_prices.items():
            # Check if it's time to update based on the interval
            time_diff = (current_time - tracked.last_update).total_seconds()
            
            if time_diff >= tracked.interval:
                symbols_to_update.append(symbol)
                
        return symbols_to_update
    
    def remove_by_message(self, message_id: int) -> Optional[str]:
        """
        Remove a tracked price by message ID.
        
        Args:
            message_id: The Discord message ID
            
        Returns:
            The symbol that was removed or None if not found
        """
        for symbol, tracked in list(self.tracked_prices.items()):
            if tracked.message_id == message_id:
                del self.tracked_prices[symbol]
                logger.info(f"Removed price tracker for {symbol} by message ID")
                return symbol
                
        return None
    
    def count(self) -> int:
        """
        Get the number of tracked prices.
        
        Returns:
            Number of tracked prices
        """
        return len(self.tracked_prices)