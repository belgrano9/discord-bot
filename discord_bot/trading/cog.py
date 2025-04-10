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

    @commands.command(name="testtrade")
    async def test_trade(
        self, 
        ctx, 
        market: str = "BTCUSDT", 
        side: str = "buy", 
        amount: float = 0.001, 
        price: Optional[float] = None, 
        order_type: str = "limit"
    ):
        """
        Create a test trade with Binance API

        Parameters:
        market: Trading pair (e.g., BTCUSDT)
        side: buy or sell
        amount: Amount to trade
        price: Price for limit orders (optional for market orders)
        order_type: Type of order (market or limit, default is limit)

        Example: !testtrade BTCUSDT buy 0.001 50000 limit
        Example: !testtrade BTCUSDT sell 0.001 market
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

    @commands.command(name="short")
    async def short_position(
        self,
        ctx,
        market: str = "BTCUSDT",
        amount: float = 0.001,
        price: Optional[float] = None,
        tp_price: Optional[float] = None,
        sl_price: Optional[float] = None
    ):
        """
        Create a short position with take profit and stop loss orders
        
        Parameters:
        market: Trading pair (e.g., BTCUSDT)
        amount: Amount to trade
        price: Price for limit orders (optional for market orders)
        tp_price: Take profit price
        sl_price: Stop loss price
        
        Example: !short BTCUSDT 0.001 150000 50000 160000
        (Sell 0.001 BTC at $150000, with take profit at $50000 and stop loss at $160000)
        """
        await self._place_position(ctx, market, "sell", amount, price, tp_price, sl_price)

    @commands.command(name="long")
    async def long_position(
        self,
        ctx,
        market: str = "BTCUSDT",
        amount: float = 0.001,
        price: Optional[float] = None,
        tp_price: Optional[float] = None,
        sl_price: Optional[float] = None
    ):
        """
        Create a long position with take profit and stop loss orders
        
        Parameters:
        market: Trading pair (e.g., BTCUSDT)
        amount: Amount to trade
        price: Price for limit orders (optional for market orders)
        tp_price: Take profit price
        sl_price: Stop loss price
        
        Example: !long BTCUSDT 0.001 50000 60000 45000
        (Buy 0.001 BTC at $50000, with take profit at $60000 and stop loss at $45000)
        """
        await self._place_position(ctx, market, "buy", amount, price, tp_price, sl_price)

    async def _place_position(
        self,
        ctx,
        market: str,
        side: str,
        amount: float,
        price: Optional[float] = None,
        tp_price: Optional[float] = None,
        sl_price: Optional[float] = None
    ):
        """
        Place a position with take profit and stop loss orders
        """
        # Security check
        required_role = discord.utils.get(ctx.guild.roles, name="Trading-Authorized")
        if required_role is None or required_role not in ctx.author.roles:
            await ctx.send("⛔ You don't have permission to place real orders. You need the 'Trading-Authorized' role.")
            return

        # Ensure amounts are properly rounded
        amount = round(amount, 5)
        
        # Check if this is a short or long position
        is_short = side.lower() == "sell"
        auto_borrow = is_short  # Auto borrow for short positions
        
        # Create confirmation message
        position_type = "Short" if is_short else "Long"
        price_str = f" at {price}" if price else " at market price"
        tp_str = f", Take Profit: ${tp_price}" if tp_price else ""
        sl_str = f", Stop Loss: ${sl_price}" if sl_price else ""
        
        confirmed = await self.order_commands.input_manager.confirm_action(
            ctx,
            title=f"⚠️ Confirm {position_type} Position",
            description=f"You are about to open a {position_type} position for {amount} {market}{price_str}{tp_str}{sl_str}.\n\nDo you want to proceed?",
            color=discord.Color.red()
        )
        
        if not confirmed:
            await ctx.send("🛑 Position creation cancelled.")
            return
        
        # Place main order
        order_type = "limit" if price else "market"
        
        if order_type == "limit":
            main_order_msg = await ctx.send(f"⏳ Placing {position_type} {order_type} order at ${price}...")
        else:
            main_order_msg = await ctx.send(f"⏳ Placing {position_type} {order_type} order...")
            
        # Delegate to order commands for the main order
        if order_type == "limit":
            await self.order_commands.handle_real_order(
                ctx, market, side, str(amount), str(price), "limit", auto_borrow
            )
        else:
            await self.order_commands.handle_real_order(
                ctx, market, side, str(amount), "market", "market", auto_borrow
            )
        
        # Place take profit order if specified
        if tp_price:
            # Take profit side is opposite of entry side
            tp_side = "buy" if side.lower() == "sell" else "sell"
            tp_type = "entry" if is_short else "loss"  # For shorts, TP is an entry; for longs, TP is a loss
            
            await ctx.send(f"⏳ Placing Take Profit order at ${tp_price}...")
            
            # Place take profit order
            await self.order_commands.handle_stop_order(
                ctx, market, tp_side, str(tp_price), tp_type, "market", str(amount), None
            )
            
        # Place stop loss order if specified
        if sl_price:
            # Stop loss side is opposite of entry side
            sl_side = "buy" if side.lower() == "sell" else "sell"
            sl_type = "loss" if is_short else "entry"  # For shorts, SL is a loss; for longs, SL is an entry
            
            await ctx.send(f"⏳ Placing Stop Loss order at ${sl_price}...")
            
            # Place stop loss order
            await self.order_commands.handle_stop_order(
                ctx, market, sl_side, str(sl_price), sl_type, "market", str(amount), None
            )
            
        # Final confirmation message
        await ctx.send(f"✅ {position_type} position setup completed with {amount} {market}!")

    @commands.command(name="ticker")
    async def get_ticker(self, ctx, symbol: str = "BTCUSDT"):
        """Get ticker information for a trading pair on Binance"""
        await self.market_commands.handle_ticker(ctx, symbol)

    @commands.command(name="fees")
    async def get_fees(self, ctx, symbol: str = "BTCUSDT"):
        """Get trading fees for a specific symbol on Binance"""
        await self.market_commands.handle_fees(ctx, symbol)

    @commands.command(name="markets")
    async def get_markets(self, ctx, filter_str: Optional[str] = None):
        """Get list of available trading pairs on Binance"""
        await self.market_commands.handle_markets(ctx, filter_str)

    @commands.command(name="balance")
    async def show_balance(self, ctx, symbol: str = "BTCUSDT"):
        """
        Show your Binance isolated margin account information
        
        Parameters:
        symbol: Trading pair to show balance for (default: BTCUSDT)
        
        Example: !balance ETHUSDT
        """
        await self.account_commands.handle_balance(ctx, symbol)

    @commands.command(name="last_trade")
    async def last_trade(self, ctx, symbol: str = "BTCUSDT"):
        """
        Show your most recent isolated margin trade for a symbol
        
        Parameters:
        symbol: Trading pair (e.g., BTCUSDT) - required for Binance
        
        Example: !last_trade ETHUSDT
        """
        await self.account_commands.handle_last_trade(ctx, symbol)

    @commands.command(name="list_trades")
    async def list_trades(self, ctx, symbol: str = "BTCUSDT", limit: int = 20):
        """
        Show your isolated margin trade history on Binance
        
        Parameters:
        symbol: Trading pair (e.g., BTCUSDT) - required for Binance
        limit: Maximum number of trades to show - optional, defaults to 20
        
        Example: !list_trades ETHUSDT 10
        """
        await self.account_commands.handle_list_trades(ctx, symbol, limit)

    @commands.command(name="cancel_order")
    async def cancel_order(self, ctx, order_id: Optional[str] = None, symbol: Optional[str] = None):
        """
        Cancel an existing order on Binance by its order ID
        
        Parameters:
        order_id: The unique ID of the order to cancel
        symbol: The trading pair symbol (required for Binance)
        
        Example: !cancel_order 12345678 BTCUSDT
        """
        await self.order_commands.handle_cancel_order(ctx, order_id, symbol)

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        """Handle reactions on messages"""
        await self.reaction_handler.handle_reaction(reaction, user)


async def setup(bot):
    """Add the TradingCommands cog to the bot"""
    await bot.add_cog(TradingCommands(bot))