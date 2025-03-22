"""
Discord cog for cryptocurrency price tracking.
Provides real-time price tracking and updates.
"""

import discord
from discord.ext import commands, tasks
import asyncio
from typing import Optional
from loguru import logger

from .tracker_manager import TrackerManager
from .commands import TrackerCommands
from .reaction_handler import ReactionHandler


class PriceTracker(commands.Cog):
    """Discord cog for tracking cryptocurrency prices in real-time"""
    
    def __init__(self, bot):
        """Initialize the price tracker cog"""
        self.bot = bot
        
        # Initialize components
        self.manager = TrackerManager(bot)
        self.commands = TrackerCommands(self.manager)
        self.reaction_handler = ReactionHandler(self.manager)
        
        # Start the update task
        self.price_update_task.start()
        logger.info("Price tracker initialized")
    
    def cog_unload(self):
        """Clean up when the cog is unloaded"""
        self.price_update_task.cancel()
        logger.info("Price tracker unloaded")
    

    @commands.command(name="track")
    async def track_price(self, ctx, symbol: str = "BTC-USDT", interval: int = 60):
        """
        Start tracking a cryptocurrency price with regular updates
        
        Parameters:
        symbol: Trading pair to track (default: BTC-USDT)
        interval: Update interval in seconds (default: 60)
        
        Example: !track ETH-USDT 30
        """
        await self.commands.track_command(ctx, symbol, interval)
    
    @commands.command(name="untrack")
    async def untrack_price(self, ctx, symbol: str = "BTC-USDT"):
        """Stop tracking a specific symbol price"""
        await self.commands.untrack_command(ctx, symbol)
    
    @commands.command(name="tracking")
    async def list_tracking(self, ctx):
        """Show all currently tracked symbols"""
        await self.commands.list_tracking_command(ctx)
    
    @tasks.loop(seconds=1)
    async def price_update_task(self):
        """Task to update tracked prices at their configured intervals"""
        if self.manager.storage.count() == 0:
            return
            
        try:
            await self.manager.update_prices()
        except Exception as e:
            logger.error(f"Error in price update task: {str(e)}")
    
    @price_update_task.before_loop
    async def before_price_update_task(self):
        """Wait until the bot is ready before starting the price tracker"""
        await self.bot.wait_until_ready()
    
    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        """Handle reactions on price tracking messages"""
        await self.reaction_handler.handle_reaction(reaction, user)


async def setup(bot):
    """Add the PriceTracker cog to the bot"""
    await bot.add_cog(PriceTracker(bot))