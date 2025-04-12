"""
Discord cog for trading commands.
Provides functionality for crypto trading and market data.
"""

from discord.ext import commands
from typing import Optional
from loguru import logger

from .interactions.reaction_handler import ReactionHandler
from .commands.order_commands import OrderCommands
from .commands.account_commands import AccountCommands
from .commands.market_commands import MarketCommands
from .services.binance_service import BinanceService


class TradingCommands(commands.Cog):
    """Discord cog for cryptocurrency trading on Binance"""

    def __init__(self, bot):
        """Initialize the trading commands cog"""
        self.bot = bot
        
        # Initialize components
        self.binance_service = BinanceService()
        self.reaction_handler = ReactionHandler()
        self.order_commands = OrderCommands(self.reaction_handler)
        self.account_commands = AccountCommands(self.binance_service)
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
        # Command parameters reordered for user input convenience:
        auto_borrow_input: bool = False, # Renamed temporarily for clarity
        order_type_input: str = "limit"
    ):
        """
        Create a real order on Binance

        Parameters:
        market: Trading pair (e.g., BTCUSDT)
        side: buy or sell
        amount: Amount to trade
        price_or_type: Price for limit orders or "market" for market orders
        auto_borrow: Whether to auto-borrow for short selling (True/False) [Optional, default: False]
        order_type: Type of order (limit, market) [Optional, default: limit, usually inferred]

        Examples:
        !realorder BTCUSDT buy 0.001 50000         (limit order)
        !realorder BTCUSDT sell 0.001 market       (market order, auto_borrow=False)
        !realorder BTCUSDC sell 0.0001 market True  (market order, auto_borrow=True)
        """
        await self.order_commands.handle_real_order(
            ctx,
            market,
            side,
            amount,
            price_or_type,
            order_type_input,   
            auto_borrow_input   
        )


    @commands.command(name="stoporder")
    async def stop_order(
        self,
        ctx,
        # --- Core Required Args ---
        market: str,
        side: str,
        stop_price: str,
        # --- Optional Args with Defaults ---
        stop_type: str = "loss",
        order_type: str = "limit",
        # --- Capture all remaining arguments ---
        *remaining_args
    ):
        """
        Create a stop order (Stop-Loss/Take-Profit). Manual parsing for trailing args.
        Args: market, side, stop_price, [stop_type], [order_type], [price_or_size], [size_or_funds], [auto_borrow]

        Examples:
        !stoporder BTCUSDC sell 60000 loss limit 59500 0.001 False
        !stoporder BTCUSDC buy 20000 entry market 0.001 True
        !stoporder BTCUSDC sell 76924 loss market 0.00013 True
        !stoporder BTCUSDC sell 80000 entry market 0.00015
        """
        price_or_size = None
        size_or_funds = None
        auto_borrow = False # Default

        args_list = list(remaining_args) # Make it mutable
        num_extra_args = len(args_list)

        logger.debug(f"[COG *ARGS v2] Received remaining_args: {args_list}")

        # --- Step 1: Manually Check the VERY LAST argument for boolean string ---
        if num_extra_args > 0:
            potential_bool_str = args_list[-1].lower() # Get last arg, lowercase it

            # Check common true/false strings
            true_values = {'true', 'yes', '1', 'on', 'enable', 'enabled'}
            false_values = {'false', 'no', '0', 'off', 'disable', 'disabled'}

            if potential_bool_str in true_values:
                auto_borrow = True
                args_list.pop() # Remove the last element as it was parsed
                num_extra_args -= 1
                logger.info(f"[COG *ARGS v2] Parsed trailing argument '{args_list[-1] if num_extra_args >= 0 else potential_bool_str}' as auto_borrow=True")
            elif potential_bool_str in false_values:
                auto_borrow = False
                args_list.pop() # Remove the last element as it was parsed
                num_extra_args -= 1
                logger.info(f"[COG *ARGS v2] Parsed trailing argument '{args_list[-1] if num_extra_args >= 0 else potential_bool_str}' as auto_borrow=False")
            else:
                # Last argument wasn't a recognizable boolean string.
                # Assume auto_borrow remains False (its default).
                logger.info(f"[COG *ARGS v2] Trailing argument '{args_list[-1]}' not a boolean string. auto_borrow remains False.")
                # Do not pop the argument, it might be price/size.
                pass # auto_borrow already defaults to False

        # --- Step 2: Parse remaining args based on order_type ---
        # Now args_list contains only price/size/funds arguments (if any)
        order_type_lower = order_type.lower()

        if order_type_lower == "market":
            if num_extra_args >= 1:
                price_or_size = args_list[0] # This is the SIZE for market orders
                logger.debug(f"[COG *ARGS v2] Assigned '{price_or_size}' to price_or_size (for market size)")
            if num_extra_args >= 2:
                logger.warning(f"[COG *ARGS v2] Extra argument provided after size for market stop order: '{args_list[1]}'. Ignoring.")

        elif order_type_lower == "limit":
            if num_extra_args >= 1:
                price_or_size = args_list[0] # This is the PRICE for limit orders
                logger.debug(f"[COG *ARGS v2] Assigned '{price_or_size}' to price_or_size (for limit price)")
            if num_extra_args >= 2:
                size_or_funds = args_list[1] # This is the SIZE for limit orders
                logger.debug(f"[COG *ARGS v2] Assigned '{size_or_funds}' to size_or_funds (for limit size)")
            # You might want validation here: if limit, price_or_size and size_or_funds should not be None
            if price_or_size is None or size_or_funds is None:
                 logger.warning(f"Limit stop order might be missing price or size. Price='{price_or_size}', Size='{size_or_funds}'")
                 # Optionally send error to user: await ctx.send("❌ Price and Size are required for limit stop orders.") return


        else:
            logger.error(f"Unsupported order_type '{order_type}' encountered during *args parsing.")
            await ctx.send(f"❌ Internal error: Unsupported order type '{order_type}'.")
            return


        # <<< --- Logging (Final Values) --- >>>
        logger.info(f"[COG *ARGS v2 DEBUG] Final Parsed Values:")
        logger.info(f"  market        : {market}")
        logger.info(f"  side          : {side}")
        logger.info(f"  stop_price    : {stop_price}")
        logger.info(f"  stop_type     : {stop_type}")
        logger.info(f"  order_type    : {order_type}")
        logger.info(f"  price_or_size : {price_or_size}")
        logger.info(f"  size_or_funds : {size_or_funds}")
        logger.info(f"  auto_borrow   : {auto_borrow}")
        # <<< --- End Logging --- >>>

        # Ensure the handler call matches the handler signature
        await self.order_commands.handle_stop_order(
            ctx,
            market, side, stop_price, stop_type,
            order_type, price_or_size, size_or_funds, auto_borrow # Pass the manually parsed values
        )

    @commands.command(name="oco")
    async def oco_order(
        self,
        ctx,
        market: Optional[str] = None,
        side: Optional[str] = None,
        quantity: Optional[str] = None,
        limit_price: Optional[str] = None,
        stop_price: Optional[str] = None,
        stop_limit_price: Optional[str] = None,
        auto_borrow: bool = False
    ):
        """
        Create a One-Cancels-the-Other (OCO) order on Binance
        
        Parameters:
        market: Trading pair (e.g., BTCUSDT)
        side: 'buy' or 'sell'
        quantity: Amount to trade
        limit_price: Price for the limit order portion
        stop_price: Trigger price for the stop order portion
        stop_limit_price: Optional limit price for the stop (for stop-limit orders)
        auto_borrow: Whether to enable auto-borrowing (True/False)
        
        Examples:
        !oco BTCUSDT buy 0.001 50000 49000        (OCO with market stop)
        !oco BTCUSDT sell 0.001 52000 49000 48500 (OCO with stop-limit)
        !oco BTCUSDT sell 0.001 50000 48000 True  (OCO with auto-borrowing)
        """


        # Add this before calling the API
        logger.info(f"[OCO_ORDER] Final parameter values:")
        logger.info(f"  symbol          : {market}")
        logger.info(f"  side            : {side}")
        logger.info(f"  quantity        : {quantity}")
        logger.info(f"  stop_price      : {stop_price}")
        logger.info(f"  stop_limit_price: {stop_limit_price}")
        logger.info(f"  auto_borrow     : {auto_borrow}")


        await self.order_commands.handle_oco_order(
            ctx, market, side, quantity, limit_price, 
            stop_price, stop_limit_price, auto_borrow
        )

    @commands.command(name="balance", aliases=['bal'])
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def balance(self, ctx):
        """Displays your Binance Cross Margin account balance summary."""
        logger.debug(f"Balance command invoked by {ctx.author}")
        await self.account_commands.handle_balance(ctx) # Delegate


    # --- Add Open Orders Command ---
    @commands.command(name="openorders", aliases=['oo', 'open']) # Added aliases
    @commands.cooldown(1, 5, commands.BucketType.user) # Cooldown: 1 use per 5 sec per user
    async def open_orders(self, ctx, symbol: Optional[str] = None):
        """
        Displays your currently open Binance Margin orders.

        Optionally filters by symbol (e.g., !openorders BTCUSDT).
        Requires the 'Trading-Authorized' role.
        """
        logger.debug(f"Open orders command invoked by {ctx.author} for symbol: {symbol}")
        # Convert symbol to uppercase if provided before passing
        symbol_upper = symbol.upper() if symbol else None
        await self.account_commands.handle_open_orders(ctx, symbol_upper) # Delegate

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        """Handle reactions on messages"""
        await self.reaction_handler.handle_reaction(reaction, user)


async def setup(bot):
    """Add the TradingCommands cog to the bot"""
    await bot.add_cog(TradingCommands(bot))