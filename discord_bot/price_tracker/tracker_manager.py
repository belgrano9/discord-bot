"""
Manager for cryptocurrency price tracking.
Coordinates updates, storage, and message handling.
"""

from typing import Dict, List, Any, Optional, Tuple
import discord
import asyncio
from datetime import datetime
from loguru import logger

from .tracker_model import TrackedPrice
from .tracker_storage import TrackerStorage
from .price_service import PriceService
from .embed_builder import EmbedBuilder


class TrackerManager:
    """Manager for price tracking functionality"""
    
    def __init__(self, bot: discord.ext.commands.Bot):
        """
        Initialize the tracker manager.
        
        Args:
            bot: Discord bot instance
        """
        self.bot = bot
        self.storage = TrackerStorage()
        self.price_service = PriceService()
        self.embed_builder = EmbedBuilder()
        logger.debug("Initialized TrackerManager")
    
    async def start_tracking(
        self, 
        ctx: discord.ext.commands.Context, 
        symbol: str, 
        interval: int = 60
    ) -> Optional[discord.Message]:
        """
        Start tracking a cryptocurrency price.
        
        Args:
            ctx: Discord context
            symbol: Trading pair to track
            interval: Update interval in seconds
            
        Returns:
            The message object or None if failed
        """
        symbol = symbol.upper()
        
        # Check if already tracking this symbol
        if self.storage.get_tracked_price(symbol):
            await ctx.send(f"Already tracking {symbol}. Use !untrack {symbol} to stop first.")
            return None
        
        # Start with a processing message
        message = await ctx.send(f"⏳ Starting price tracker for {symbol}...")
        
        try:
            # Get initial price data
            ticker_data = await self.price_service.get_current_price(symbol)
            
            if not ticker_data:
                await message.edit(content=f"❌ Could not retrieve price data for {symbol}")
                return None
            
            # Create tracked price object
            current_time = datetime.now()
            tracked = TrackedPrice(
                symbol=symbol,
                price_data=ticker_data,
                last_update=current_time,
                message_id=message.id,
                channel_id=ctx.channel.id,
                interval=interval,
                created_at=current_time,
                history=[float(ticker_data.get("price", 0))]
            )
            
            # Add to storage
            self.storage.add_tracked_price(tracked)
            
            # Update the message with the initial data
            embed = self.embed_builder.build_tracking_embed(tracked)
            await message.edit(content=None, embed=embed)
            
            # Add control reactions
            await message.add_reaction("⏹️")  # Stop tracking
            await message.add_reaction("📊")  # Show chart/detailed view
            
            logger.info(f"Started tracking {symbol} with {interval}s interval")
            return message
            
        except Exception as e:
            error_msg = f"❌ Error starting price tracker: {str(e)}"
            await message.edit(content=error_msg)
            logger.error(f"Error tracking {symbol}: {str(e)}")
            return None
    
    async def stop_tracking(self, symbol: str) -> bool:
        """
        Stop tracking a symbol.
        
        Args:
            symbol: Symbol to stop tracking
            
        Returns:
            Whether tracking was stopped successfully
        """
        symbol = symbol.upper()
        
        tracked = self.storage.remove_tracked_price(symbol)
        if not tracked:
            return False
        
        # Try to update the message if possible
        try:
            channel = self.bot.get_channel(tracked.channel_id)
            if channel:
                message = await channel.fetch_message(tracked.message_id)
                
                # Create stopped embed
                embed = self.embed_builder.build_stopped_embed(tracked)
                await message.edit(embed=embed)
                await message.clear_reactions()
                
        except Exception as e:
            logger.error(f"Error updating message for stopped tracker {symbol}: {str(e)}")
            
        return True
    
    async def update_prices(self) -> List[str]:
        """
        Update all prices that need updating based on their intervals.
        
        Returns:
            List of symbols that were updated
        """
        # Get symbols that need updating
        symbols = self.storage.get_symbols_to_update()
        if not symbols:
            return []
        
        updated = []
        
        # Get prices in batch for efficiency
        price_data = await self.price_service.get_prices_batch(symbols)
        
        # Process each symbol
        for symbol in symbols:
            ticker_data = price_data.get(symbol)
            if not ticker_data:
                continue
            
            tracked = self.storage.get_tracked_price(symbol)
            if not tracked:
                continue
            
            # Update the tracked price
            tracked.update_price_data(ticker_data)
            updated.append(symbol)
            
            # Update the message if possible
            try:
                channel = self.bot.get_channel(tracked.channel_id)
                if channel:
                    message = await channel.fetch_message(tracked.message_id)
                    embed = self.embed_builder.build_tracking_embed(tracked)
                    await message.edit(embed=embed)
                    logger.debug(f"Updated price for {symbol}: ${tracked.current_price:.2f}")
            except Exception as e:
                logger.error(f"Error updating message for {symbol}: {str(e)}")
                # Remove tracking if message is gone
                if "Unknown Message" in str(e):
                    self.storage.remove_tracked_price(symbol)
                    logger.info(f"Removed tracking for {symbol} due to missing message")
        
        return updated
    
    async def show_details(self, channel: discord.TextChannel, symbol: str) -> None:
        """
        Show detailed price statistics in a new message.
        
        Args:
            channel: Discord channel
            symbol: Symbol to show details for
        """
        tracked = self.storage.get_tracked_price(symbol)
        if not tracked:
            await channel.send(f"Not currently tracking {symbol}")
            return
        
        # Create detailed embed
        embed = self.embed_builder.build_details_embed(tracked)
        await channel.send(embed=embed)
        logger.debug(f"Sent detailed view for {symbol}")