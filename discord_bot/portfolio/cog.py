"""
Discord cog for portfolio tracking.
Provides commands and background tasks for portfolio monitoring.
"""

import discord
from discord.ext import commands, tasks
import asyncio
from datetime import datetime
from typing import Optional
from loguru import logger

from config import PORTFOLIO, PORTFOLIO_UPDATE_INTERVAL, PORTFOLIO_CHANNEL_ID
from .portfolio_storage import PortfolioStorage
from .commands import PortfolioCommands


class PortfolioTracker(commands.Cog):
    """Discord cog for tracking stock portfolio value"""

    def __init__(self, bot):
        """Initialize the portfolio tracker cog"""
        self.bot = bot
        
        # Initialize storage and commands
        self.storage = PortfolioStorage(PORTFOLIO)
        self.commands = PortfolioCommands(self.storage)
        
        # Start background task
        self.track_portfolio.start()
        logger.info("Portfolio tracker initialized")

    def cog_unload(self):
        """Clean up when the cog is unloaded"""
        self.track_portfolio.cancel()
        logger.info("Portfolio tracker stopped")

    @commands.command(name="portfolio")
    async def show_portfolio(self, ctx):
        """Show current portfolio status"""
        await self.commands.handle_show_portfolio(ctx)

    @tasks.loop(seconds=PORTFOLIO_UPDATE_INTERVAL)
    async def track_portfolio(self):
        """Track portfolio value at regular intervals"""
        channel = self.bot.get_channel(PORTFOLIO_CHANNEL_ID)
        if channel:
            await self.commands._send_portfolio_update(channel)
        else:
            logger.warning(f"Portfolio channel {PORTFOLIO_CHANNEL_ID} not found")

    @track_portfolio.before_loop
    async def before_track_portfolio(self):
        """Wait until the bot is ready before starting the portfolio tracking"""
        await self.bot.wait_until_ready()
        
        # Ensure portfolio is loaded
        await self.storage.load_portfolio()

    def get_portfolio_summary(self) -> Optional[dict]:
        """
        Get a summary of the portfolio for use by other cogs.
        
        Returns:
            Dictionary with portfolio summary data or None if no data available
        """
        return self.commands.get_portfolio_summary()


async def setup(bot):
    """Add the PortfolioTracker cog to the bot"""
    portfolio_tracker = PortfolioTracker(bot)
    await bot.add_cog(portfolio_tracker)
    return portfolio_tracker  # Return the instance for other cogs to access