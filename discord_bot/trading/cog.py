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
    """Discord cog for cryptocurrency trading on KuCoin"""

    def __init__(self, bot):
        """Initialize the trading commands cog"""
        self.bot = bot
        
        # Initialize components
        self.reaction_handler = ReactionHandler()
        self.order_commands = OrderCommands(self.reaction_handler)
        self.account_commands = AccountCommands()
        self.market_commands = MarketCommands()
        
        logger.info("Trading commands initialized")

    @commands.command(name="testtrade")
    async def test_trade(
        self, 
        ctx, 
        market: str = "BTC-USDT", 
        side: str = "buy", 
        amount: float = 0.001, 
        price: Optional[float] = None, 
        order_type: str = "limit"
    ):
        """
        Create a test trade with KuCoin API

        Parameters:
        market: Trading pair (e.g., BTC-USDT)
        side: buy or sell
        amount: Amount to trade
        price: Price for limit orders (optional for market orders)
        order_type: Type of order (market or limit, default is limit)

        Example: !testtrade BTC-USDT buy 0.001 50000 limit
        Example: !testtrade BTC-USDT sell 0.001 market
        """
        await self.order_commands.handle_test_trade(ctx, market, side, amount, price, order_type)

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
        Create a real order on KuCoin with direct parameters
        
        Usage: !realorder <market> <side> <amount> [price_or_type] [order_type] [auto_borrow]
        
        Examples:
        !realorder BTC-USDT buy 0.001 50000         (limit order to buy 0.001 BTC at $50000)
        !realorder BTC-USDT sell 0.001 market       (market order to sell 0.001 BTC)
        !realorder BTC-USDT buy 0.05 2000           (limit order to buy 0.05 BTC at $2000)
        !realorder BTC-USDT sell 0.05 market        (market order to sell 0.05 BTC)
        !realorder BTC-USDT buy 100 market funds    (market order to buy $100 worth of BTC)
        !realorder BTC-USDT sell 0.001 market True  (short sell with auto-borrowing)
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
        Create a stop order on KuCoin
        
        Parameters:
        market: Trading pair (e.g., BTC-USDT)
        side: buy or sell
        stop_price: Trigger price
        stop_type: Type of stop order - 'loss' or 'entry' (default: 'loss')
        order_type: Type of order (market or limit, default is limit)
        price_or_size: Price for limit orders, or size for market orders
        size_or_funds: Size for limit orders, 'funds' keyword for market buy
        
        Examples:
        !stoporder BTC-USDT sell 60000 loss limit 59500 0.001  (Sell 0.001 BTC at $59,500 if price reaches $60,000)
        !stoporder BTC-USDT buy 20000 entry market 0.001      (Buy 0.001 BTC at market price if price rises to $20,000)
        !stoporder BTC-USDT buy 20000 loss market 100 funds    (Buy $100 worth of BTC at market price if price drops to $20,000)
        """
        await self.order_commands.handle_stop_order(ctx, market, side, stop_price, stop_type, order_type, price_or_size, size_or_funds)


    @commands.command(name="ticker")
    async def get_ticker(self, ctx, symbol: str = "BTC-USDT"):
        """Get ticker information for a trading pair on KuCoin"""
        await self.market_commands.handle_ticker(ctx, symbol)

    @commands.command(name="fees")
    async def get_fees(self, ctx, symbol: str = "BTC-USDT"):
        """Get trading fees for a specific symbol on KuCoin"""
        await self.market_commands.handle_fees(ctx, symbol)

    @commands.command(name="balance")
    async def show_balance(self, ctx, symbol: str = "BTC-USDT"):
        """
        Show your KuCoin isolated margin account information
        
        Parameters:
        symbol: Trading pair to show balance for (default: BTC-USDT)
        
        Example: !balance ETH-USDT
        """
        await self.account_commands.handle_balance(ctx, symbol)

    @commands.command(name="last_trade")
    async def last_trade(self, ctx, symbol: str = "BTC-USDT"):
        """
        Show your most recent isolated margin trade for a symbol
        
        Parameters:
        symbol: Trading pair (e.g., BTC-USDT) - optional, defaults to BTC-USDT
        
        Example: !last_trade ETH-USDT
        """
        await self.account_commands.handle_last_trade(ctx, symbol)

    @commands.command(name="list_trades")
    async def list_trades(self, ctx, symbol: Optional[str] = None, limit: int = 20):
        """
        Show your isolated margin trade history on KuCoin
        
        Parameters:
        symbol: Trading pair (e.g., BTC-USDT) - optional, defaults to all pairs
        limit: Maximum number of trades to show - optional, defaults to 20
        
        Example: !list_trades ETH-USDT 10
        """
        await self.account_commands.handle_list_trades(ctx, symbol, limit)

    @commands.command(name="cancel_order")
    async def cancel_order(self, ctx, order_id: Optional[str] = None):
        """
        Cancel an existing order on KuCoin by its order ID
        
        Parameters:
        order_id: The unique ID of the order to cancel
        
        Example: !cancel_order 5bd6e9286d99522a52e458de
        """
        await self.order_commands.handle_cancel_order(ctx, order_id)

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        """Handle reactions on messages"""
        await self.reaction_handler.handle_reaction(reaction, user)


async def setup(bot):
    """Add the TradingCommands cog to the bot"""
    await bot.add_cog(TradingCommands(bot))