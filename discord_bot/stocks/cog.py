"""
Discord cog for stock data commands.
Registers commands and routes them to handlers.
"""

import discord
from discord.ext import commands
from loguru import logger

from .commands import StockCommands


class StockCommands(commands.Cog):
    """Discord commands for interacting with financial data"""

    def __init__(self, bot):
        """Initialize the cog with command handlers"""
        self.bot = bot
        self.commands = StockCommands()
        logger.info("Stock commands initialized")

    @commands.command(name="stock")
    async def stock_snapshot(self, ctx, ticker: str):
        """Get a snapshot of key financial metrics for a stock"""
        await self.commands.handle_stock_snapshot(ctx, ticker)

    @commands.command(name="price")
    async def stock_price(self, ctx, ticker: str = None, days: int = 1):
        """Get recent price data for a stock

        Usage:
        !price AAPL - Get latest price for Apple
        !price MSFT 7 - Get Microsoft price data for past 7 days
        """
        await self.commands.handle_stock_price(ctx, ticker, days)

    @commands.command(name="live")
    async def live_price(self, ctx, ticker: str = None):
        """Get the latest live price for a stock"""
        await self.commands.handle_live_price(ctx, ticker)

    @commands.command(name="financials")
    async def financials(self, ctx, ticker: str, statement_type: str = "income"):
        """Get financial statements for a company

        statement_type options: income, balance, cash
        """
        await self.commands.handle_financials(ctx, ticker, statement_type)


async def setup(bot):
    """Add the StockCommands cog to the bot"""
    await bot.add_cog(StockCommands(bot))