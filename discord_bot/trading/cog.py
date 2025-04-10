"""
Discord cog for trading commands.
Provides functionality for crypto trading and market data.
"""

import discord
from discord.ext import commands
from typing import Optional
from loguru import logger

from .interactions.reaction_handler import ReactionHandler
from .commands.order_commands import OrderCommands
from .commands.account_commands import AccountCommands
from .commands.market_commands import MarketCommands


class TradingCommands(commands.Cog):
    """Discord cog for cryptocurrency trading on Binance"""

    def __init__(self, bot):
        """Initialize the trading commands cog"""
        self.bot = bot
        
        # Initialize components
        self.reaction_handler = ReactionHandler()
        self.order_commands = OrderCommands(self.reaction_handler)
        self.account_commands = AccountCommands()
        self.market_commands = MarketCommands()
        
        logger.info("Trading commands initialized")

    @commands.command(name="realorder")
    async def real_order(
        self, 
        ctx, 
        market: Optional[str] = None, 
        side: Optional[str] = None, 
        amount: Optional[str] = None, 
        price_or_type: Optional[str] = None, 
        order_type: str = "limit",
        auto_borrow: bool = False
    ):
        """
        Create a real order on Binance

        Parameters:
        market: Trading pair (e.g., BTCUSDT)
        side: buy or sell
        amount: Amount to trade
        price_or_type: Price for limit orders or "market" for market orders
        order_type: Type of order (limit, market)
        auto_borrow: Whether to auto-borrow for short selling

        Examples:
        !realorder BTCUSDT buy 0.001 50000         (limit order to buy 0.001 BTC at $50000)
        !realorder BTCUSDT sell 0.001 market       (market order to sell 0.001 BTC)
        !realorder BTCUSDT sell 0.001 market True  (market order to short sell with auto-borrowing)
        """
        await self.order_commands.handle_real_order(ctx, market, side, amount, price_or_type, order_type, auto_borrow)

    @commands.command(name="stoporder")
    async def stop_order(
        self, 
        ctx, 
        market: Optional[str] = None, 
        side: Optional[str] = None, 
        stop_price: Optional[str] = None, 
        stop_type: str = "loss",
        order_type: str = "limit", 
        price_or_size: Optional[str] = None,
        size_or_funds: Optional[str] = None
    ):
        """
        Create a stop order on Binance
        
        Parameters:
        market: Trading pair (e.g., BTCUSDT)
        side: buy or sell
        stop_price: Trigger price
        stop_type: Type of stop order - 'loss' or 'entry' (default: 'loss')
        order_type: Type of order (market or limit, default is limit)
        price_or_size: Price for limit orders, or size for market orders
        size_or_funds: Size for limit orders
        
        Examples:
        !stoporder BTCUSDT sell 60000 loss limit 59500 0.001  (Sell 0.001 BTC at $59,500 if price reaches $60,000)
        !stoporder BTCUSDT buy 20000 entry market 0.001      (Buy 0.001 BTC at market price if price rises to $20,000)
        """
        await self.order_commands.handle_stop_order(ctx, market, side, stop_price, stop_type, order_type, price_or_size, size_or_funds)

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        """Handle reactions on messages"""
        await self.reaction_handler.handle_reaction(reaction, user)


async def setup(bot):
    """Add the TradingCommands cog to the bot"""
    await bot.add_cog(TradingCommands(bot))