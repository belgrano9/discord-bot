"""
Tracker Manager module for managing cryptocurrency price tracking.
Handles tracking state, updates, and message management.
"""

from typing import Dict, Any, List, Optional
import asyncio
from datetime import datetime
import discord
from loguru import logger

from .price_service import PriceService


class TrackerManager:
    """
    Manager for cryptocurrency price tracking operations.
    Maintains tracking state, handles updates, and manages Discord messages.
    """
    
    def __init__(self, bot):
        """
        Initialize the tracker manager.
        
        Args:
            bot: Discord bot instance
        """
        self.bot = bot
        self.price_service = PriceService()
        self.tracked_prices = {}  # {symbol: {price_data, last_update, message_id, channel_id, etc.}}
        logger.debug("TrackerManager initialized")
    
    async def start_tracking(
        self,
        symbol: str,
        channel_id: int,
        message_id: int,
        interval: int = 60
    ) -> bool:
        """
        Start tracking a symbol's price.
        
        Args:
            symbol: Trading pair symbol (e.g., "BTC-USDT")
            channel_id: Discord channel ID for updates
            message_id: Discord message ID to update
            interval: Update interval in seconds
            
        Returns:
            Success status
        """
        try:
            # Get initial price data
            ticker_data = await self.price_service.get_symbol_data(symbol)
            
            if not ticker_data:
                logger.warning(f"Could not retrieve price data for {symbol}")
                return False
            
            # Store tracking info
            self.tracked_prices[symbol] = {
                "price_data": ticker_data,
                "last_update": datetime.now(),
                "message_id": message_id,
                "channel_id": channel_id,
                "interval": interval,
                "history": [float(ticker_data["price"])],  # Store price history
                "created_at": datetime.now()
            }
            
            logger.info(f"Started tracking {symbol} with {interval}s interval")
            return True
            
        except Exception as e:
            logger.error(f"Error starting to track {symbol}: {str(e)}")
            return False
    
    def stop_tracking(self, symbol: str) -> bool:
        """
        Stop tracking a symbol's price.
        
        Args:
            symbol: Trading pair symbol to stop tracking
            
        Returns:
            Success status
        """
        if symbol in self.tracked_prices:
            del self.tracked_prices[symbol]
            logger.info(f"Stopped tracking {symbol}")
            return True
        
        logger.warning(f"Cannot stop tracking {symbol}: not being tracked")
        return False
    
    def get_tracked_symbols(self) -> List[str]:
        """
        Get list of currently tracked symbols.
        
        Returns:
            List of symbols being tracked
        """
        return list(self.tracked_prices.keys())
    
    def get_tracking_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get tracking information for a symbol.
        
        Args:
            symbol: Trading pair symbol
            
        Returns:
            Tracking information or None if not tracked
        """
        return self.tracked_prices.get(symbol)
    
    async def update_all_tracked_prices(self) -> Dict[str, bool]:
        """
        Update all tracked prices and their Discord messages.
        
        Returns:
            Dictionary mapping symbols to update success status
        """
        if not self.tracked_prices:
            return {}
        
        current_time = datetime.now()
        update_results = {}
        update_tasks = []
        
        for symbol, data in list(self.tracked_prices.items()):
            # Check if it's time to update based on the interval
            time_diff = (current_time - data["last_update"]).total_seconds()
            
            if time_diff >= data["interval"]:
                # Create a task for each symbol that needs updating
                task = self.update_symbol(symbol)
                update_tasks.append(task)
        
        # Run all updates concurrently
        if update_tasks:
            results = await asyncio.gather(*update_tasks, return_exceptions=True)
            
            # Process results
            for i, symbol in enumerate(self.tracked_prices.keys()):
                if i < len(results):
                    if isinstance(results[i], Exception):
                        logger.error(f"Error updating {symbol}: {str(results[i])}")
                        update_results[symbol] = False
                    else:
                        update_results[symbol] = results[i]
        
        return update_results
    
    async def update_symbol(self, symbol: str) -> bool:
        """
        Update price data for a specific symbol and its Discord message.
        
        Args:
            symbol: Trading pair symbol to update
            
        Returns:
            Success status
        """
        if symbol not in self.tracked_prices:
            logger.warning(f"Cannot update {symbol}: not being tracked")
            return False
        
        try:
            # Get tracking data
            tracking_data = self.tracked_prices[symbol]
            
            # Get updated price data
            updated_data = await self.price_service.get_symbol_data(symbol)
            
            if not updated_data:
                logger.warning(f"Failed to update price for {symbol}")
                return False
            
            # Update tracked data
            self.tracked_prices[symbol]["price_data"] = updated_data
            self.tracked_prices[symbol]["last_update"] = datetime.now()
            
            # Update price history (keep last 60 entries - ~ 1 hour at 60s interval)
            price = float(updated_data["price"])
            self.tracked_prices[symbol]["history"].append(price)
            if len(self.tracked_prices[symbol]["history"]) > 60:
                self.tracked_prices[symbol]["history"] = self.tracked_prices[symbol]["history"][-60:]
            
            # Update the message if possible
            try:
                channel = self.bot.get_channel(tracking_data["channel_id"])
                if channel:
                    message = await channel.fetch_message(tracking_data["message_id"])
                    
                    # Create embed content (implementation would be in the cog)
                    # Since this is the manager, we'll return success and let the cog
                    # handle the message update with proper formatting
                    
                    logger.debug(f"Updated price for {symbol}: ${price:.2f}")
                    return True
            except Exception as e:
                logger.error(f"Error updating message for {symbol}: {str(e)}")
                # Remove tracking if message is gone
                if "Unknown Message" in str(e):
                    self.stop_tracking(symbol)
                    logger.info(f"Removed tracking for {symbol} due to missing message")
                return False
        
        except Exception as e:
            logger.error(f"Error in price tracker for {symbol}: {str(e)}")
            return False
        
        return True
    
    def get_price_statistics(self, symbol: str) -> Dict[str, Any]:
        """
        Get statistical information about tracked price.
        
        Args:
            symbol: Trading pair symbol
            
        Returns:
            Dictionary with price statistics or empty dict if not tracked
        """
        if symbol not in self.tracked_prices:
            return {}
        
        tracking_data = self.tracked_prices[symbol]
        history = tracking_data["history"]
        
        if not history:
            return {}
        
        # Get current price
        current_price = float(tracking_data["price_data"]["price"])
        
        # Calculate price changes
        changes = self.price_service.calculate_price_changes(current_price, history)
        
        # Calculate statistics
        stats = self.price_service.calculate_statistics(history)
        
        # Get movement patterns
        movements = self.price_service.categorize_movement(history)
        
        # Add tracking info
        created_at = tracking_data["created_at"]
        time_elapsed = datetime.now() - created_at
        hours, remainder = divmod(int(time_elapsed.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        
        # Combine all information
        return {
            "current_price": current_price,
            "changes": changes,
            "stats": stats,
            "movements": movements,
            "tracking_info": {
                "started_at": created_at,
                "elapsed": {
                    "hours": hours,
                    "minutes": minutes,
                    "seconds": seconds,
                    "total_seconds": time_elapsed.total_seconds()
                },
                "interval": tracking_data["interval"],
                "data_points": len(history)
            }
        }