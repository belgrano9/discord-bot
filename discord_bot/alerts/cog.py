"""
Discord cog for stock price alerts functionality.
Integrates alert monitoring, commands, and test functionality.
"""

import discord
from discord.ext import commands, tasks
import asyncio
from datetime import datetime
from typing import Dict, List, Any, Optional
from loguru import logger

from config import ALERT_CHANNEL_ID, CHECK_INTERVAL, STOCKS
from .alert_model import PriceAlert
from .alert_storage import AlertStorage
from .alert_commands import AlertCommands
from .alert_monitor import AlertMonitor
from .config_checker import ConfigChecker
from .test_handler import TestHandler


class StockAlerts(commands.Cog):
    """Discord cog for monitoring stock prices and sending alerts"""
    
    def __init__(self, bot):
        """Initialize the stock alerts cog"""
        self.bot = bot
        logger.info("Initializing StockAlerts cog")
        
        # Initialize components
        self.storage = AlertStorage()
        self.storage.load()
        
        self.commands = AlertCommands(self.storage)
        self.monitor = AlertMonitor(bot, self.storage, CHECK_INTERVAL)
        self.config_checker = ConfigChecker(bot, ALERT_CHANNEL_ID, STOCKS)
        self.test_handler = TestHandler(bot)
        
        # Start the price checker
        self.check_price_alerts.start()
        logger.info("Started price alert checker")
    
    def cog_unload(self):
        """Clean up when the cog is unloaded"""
        logger.info("Unloading StockAlerts cog")
        self.check_price_alerts.cancel()
        self.storage.save()
        
        # Cancel any running test tasks
        for channel_id, task in self.test_handler.test_tasks.items():
            if not task.done():
                logger.debug(f"Cancelling running test task for channel {channel_id}")
                task.cancel()
    
    @commands.group(name="alert", invoke_without_command=True)
    async def alert(self, ctx):
        """Command group for stock price alerts"""
        logger.debug(f"Alert command invoked by {ctx.author}")
        await ctx.send(
            "Use `!alert add`, `!alert remove`, `!alert list`, or `!alert test` to manage stock alerts"
        )

    @alert.command(name="add")
    async def add_alert(self, ctx, ticker: str, alert_type: str, value: float):
        """Add a stock price alert
        
        Example:
        !alert add AAPL percent 5    - Alert when AAPL grows by 5%
        !alert add MSFT price 150    - Alert when MSFT reaches $150
        """
        await self.commands.add_alert(ctx, ticker, alert_type, value)
    
    @alert.command(name="remove")
    async def remove_alert(self, ctx, index: int = None):
        """Remove a stock price alert by index
        
        Example:
        !alert remove 2    - Removes alert at index 2
        !alert remove      - Lists alerts with indexes
        """
        await self.commands.remove_alert(ctx, index)
    
    @alert.command(name="list")
    async def list_alerts(self, ctx):
        """List all stock price alerts for this channel"""
        await self.commands.list_alerts(ctx)
    
    @alert.command(name="test")
    async def test_alerts(self, ctx):
        """Start a test to verify alert functionality by sending messages every second"""
        await self.test_handler.start_test(ctx)
    
    @commands.command(name="end")
    async def end_test(self, ctx, command_type: str):
        """End a running test"""
        if command_type.lower() != "test":
            return
        
        await self.test_handler.end_test(ctx)
    
    @commands.command(name="watchlist")
    async def show_watchlist(self, ctx):
        """Show configured stocks to monitor from config.py"""
        logger.debug(f"{ctx.author} viewing watchlist")
        
        embed = discord.Embed(
            title="Stock Watchlist",
            description="Configured stocks with price thresholds",
            color=discord.Color.blue(),
        )
        
        for ticker, thresholds in STOCKS.items():
            low = thresholds["low"]
            high = thresholds["high"]
            description = f"Low: ${low:.2f}\nHigh: ${high:.2f}"
            embed.add_field(name=ticker, value=description, inline=True)
            logger.debug(f"Added {ticker} to watchlist display")
        
        await ctx.send(embed=embed)
        logger.debug("Watchlist displayed")
    
    @tasks.loop(seconds=CHECK_INTERVAL)
    async def check_price_alerts(self):
        """Check current prices against alerts periodically based on config"""
        logger.debug("Running periodic price alert check")
        
        # Check user-defined alerts
        triggered_alerts = await self.monitor.check_alerts()
        await self.monitor.handle_triggered_alerts(triggered_alerts)
        
        # Also check config stocks
        await self.config_checker.check_stocks()
    
    @check_price_alerts.before_loop
    async def before_check_price_alerts(self):
        """Wait until the bot is ready before starting the alert loop"""
        logger.debug("Waiting for bot to be ready before starting alert loop")
        await self.bot.wait_until_ready()
        logger.debug("Bot is ready, alert checker starting")


async def setup(bot):
    """Add the StockAlerts cog to the bot"""
    logger.info("Setting up StockAlerts cog")
    await bot.add_cog(StockAlerts(bot))
    logger.info("StockAlerts cog setup complete")