"""
Discord commands for price tracking functionality.
Handles user interactions for tracking cryptocurrency prices.
"""

import discord
from discord.ext import commands
from typing import Dict, Any, Optional
from loguru import logger

from .tracker_manager import TrackerManager


class TrackerCommands:
    """Command handlers for price tracking"""
    
    def __init__(self, manager: TrackerManager):
        """
        Initialize tracker commands.
        
        Args:
            manager: Tracker manager instance
        """
        self.manager = manager
        logger.debug("Initialized TrackerCommands")
    
    async def track_command(
        self, 
        ctx: commands.Context, 
        symbol: str = "BTC-USDT", 
        interval: int = 60
    ) -> None:
        """
        Handle the track command to start tracking a price.
        
        Args:
            ctx: Discord context
            symbol: Trading pair to track
            interval: Update interval in seconds
        """
        # Validate interval
        if interval < 5:
            await ctx.send("⚠️ Interval too short. Setting to minimum of 5 seconds.")
            interval = 5
        elif interval > 3600:
            await ctx.send("⚠️ Interval too long. Setting to maximum of 1 hour.")
            interval = 3600
        
        await self.manager.start_tracking(ctx, symbol, interval)
    
    async def untrack_command(self, ctx: commands.Context, symbol: str = "BTC-USDT") -> None:
        """
        Handle the untrack command to stop tracking a price.
        
        Args:
            ctx: Discord context
            symbol: Trading pair to stop tracking
        """
        symbol = symbol.upper()
        
        success = await self.manager.stop_tracking(symbol)
        if success:
            await ctx.send(f"✅ Stopped tracking {symbol}")
            logger.info(f"Stopped tracking {symbol}")
        else:
            await ctx.send(f"❌ Not currently tracking {symbol}")
    
    async def list_tracking_command(self, ctx: commands.Context) -> None:
        """
        Handle the tracking command to list all tracked symbols.
        
        Args:
            ctx: Discord context
        """
        tracked_prices = self.manager.storage.get_all_tracked_prices()
        
        if not tracked_prices:
            await ctx.send("No symbols are currently being tracked")
            return
        
        # Create embed for the list
        embed = discord.Embed(
            title="Currently Tracked Symbols",
            description="List of all price trackers currently active",
            color=discord.Color.blue()
        )
        
        # Add fields for each tracked symbol
        for symbol, tracked in tracked_prices.items():
            # Calculate time since started
            time_elapsed = discord.utils.format_dt(tracked.created_at, style='R')
            
            # Get latest price and calculate change since start
            current_price = tracked.current_price
            changes = tracked.calculate_changes()
            
            value = (
                f"Current: ${current_price:.2f}\n"
                f"Change: {'+' if changes['change_since_start'] >= 0 else ''}{changes['change_since_start']:.2f}%\n"
                f"Interval: {tracked.interval}s\n"
                f"Started: {time_elapsed}"
            )
            
            embed.add_field(name=symbol, value=value, inline=True)
        
        await ctx.send(embed=embed)
        logger.debug(f"Listed {len(tracked_prices)} tracked symbols")