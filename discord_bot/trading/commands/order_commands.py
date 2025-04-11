"""
Order commands for trading.
Handles order creation, testing, and cancellation.
"""

import discord
from discord.ext import commands
from datetime import datetime
from typing import Optional
from loguru import logger

from ..models.order import OrderRequest, OrderSide, OrderType
from ..services.binance_service import BinanceService
from ..services.market_service import MarketService
from ..formatters.order_formatter import OrderFormatter
from ..interactions.input_manager import InputManager


class OrderCommands:
    """Command handlers for orders"""
    
    def __init__(self, reaction_handler):
        """
        Initialize order commands.
        
        Args:
            reaction_handler: Reaction handler for message reactions
        """
        self.binance_service = BinanceService()
        self.market_service = MarketService()
        self.order_formatter = OrderFormatter()
        self.input_manager = InputManager()
        self.reaction_handler = reaction_handler
        logger.debug("Initialized OrderCommands")
    
    
    async def handle_real_order(
        self,
        ctx: commands.Context,
        market: Optional[str] = None,
        side: Optional[str] = None,
        amount: Optional[str] = None,
        price_or_type: Optional[str] = None,
        order_type: str = "limit",  # <--- Expects order_type here
        auto_borrow: bool = False   # <--- Expects auto_borrow here
    ) -> None:
        """
        Handle the real order command.
        
        Args:
            ctx: Discord context
            market: Trading pair
            side: Buy or sell
            amount: Amount to trade
            price_or_type: Price for limit orders or "market" for market orders
            order_type: Type of order (limit, market, funds)
            auto_borrow: Whether to enable auto-borrowing (for short selling)
        """
        # Security measure: Check if user has the correct role
        required_role = discord.utils.get(ctx.guild.roles, name="Trading-Authorized")
        if required_role is None or required_role not in ctx.author.roles:
            await ctx.send("⛔ You don't have permission to place real orders. You need the 'Trading-Authorized' role.")
            return
        
        # If no parameters were provided, collect them interactively
        if not all([market, side, amount]):
            order_request = await self.input_manager.collect_trade_parameters(ctx, is_real=True)
            if not order_request:
                return
        else:
            # Process provided parameters
            try:
                # Process side
                side = side.lower()
                if side not in ["buy", "sell"]:
                    await ctx.send("❌ Invalid side. Must be 'buy' or 'sell'.")
                    return
                
                side_enum = OrderSide.BUY if side == "buy" else OrderSide.SELL
                
                # Check if using funds for market order
                use_funds = False
                if order_type.lower() == "funds":
                    use_funds = True
                    order_type = "market"
                
                # Check if price_or_type indicates market order
                if price_or_type and price_or_type.lower() == "market":
                    order_type_enum = OrderType.MARKET
                    price = None
                else:
                    if order_type.lower() == "market":
                        order_type_enum = OrderType.MARKET
                        price = None
                    else:
                        order_type_enum = OrderType.LIMIT
                        # For limit orders, price_or_type is the price
                        try:
                            price = float(price_or_type) if price_or_type else None
                            if price is not None and price <= 0:
                                await ctx.send("❌ Price must be positive.")
                                return
                        except ValueError:
                            await ctx.send("❌ Invalid price. Must be a number.")
                            return
                
                # Validate amount
                try:
                    amount_float = float(amount)
                    if amount_float <= 0:
                        await ctx.send("❌ Amount must be positive.")
                        return
                except ValueError:
                    await ctx.send("❌ Invalid amount. Must be a number.")
                    return
                
                # Round amount to 5 decimal places (Binance requirement)
                amount_float = round(amount_float, 5)
                
                # For market orders with no price specified, get current price for display
                if order_type_enum == OrderType.MARKET and price is None:
                    # Get current price for display purposes
                    try:
                        ticker_data = await self.market_service.get_ticker(market)
                        if ticker_data:
                            price = float(ticker_data.get("price", 0))
                    except:
                        pass

                logger.info(f"Value of 'auto_borrow' before creating OrderRequest: {auto_borrow} (Type: {type(auto_borrow)})") # <-- ADD THIS LINE

                # Create the order request
                order_request = OrderRequest(
                    symbol=market.upper(),
                    side=side_enum,
                    order_type=order_type_enum,
                    amount=amount_float,
                    price=price,
                    use_funds=use_funds,
                    auto_borrow=auto_borrow,  # Use the parameter
                    is_isolated=False  # Always use isolated margin
                )
            except Exception as e:
                await ctx.send(f"❌ Error processing order parameters: {str(e)}")
                return
        
        # Get confirmation before proceeding
        confirmed = await self.input_manager.confirm_action(
            ctx,
            title="⚠️ WARNING: REAL ORDER REQUEST ⚠️",
            description="You are about to place an order using REAL funds. Are you sure you want to proceed?",
            color=discord.Color.red(),
            use_reactions=True
        )
        
        if not confirmed:
            await ctx.send("🛑 Order creation cancelled.")
            return
        
        # Process the order
        order_response = await self.binance_service.place_order(order_request)
        
        # Create the embed
        embed = self.order_formatter.format_order_response(order_response, order_request)
        
        # Send the message
        message = await ctx.send(embed=embed)
        
        # Add clipboard reaction if we have an order ID
        if order_response.order_id:
            await message.add_reaction("📋")
            # Register with reaction handler
            self.reaction_handler.register_message(message.id, order_response.order_id)

    async def handle_stop_order(
        self,
        ctx: commands.Context,
        market: Optional[str] = None,
        side: Optional[str] = None,
        stop_price: Optional[str] = None,
        stop_type: str = "loss",      # 'loss' or 'entry'
        order_type: str = "limit",    # 'limit' or 'market'
        price_or_size: Optional[str] = None, # Price for LIMIT, Size for MARKET
        size_or_funds: Optional[str] = None, # Size for LIMIT
        auto_borrow: bool = False      # <<< Added parameter
    ) -> None:
        """
        Handle the stop order command.

        Args:
            ctx: Discord context
            market: Trading pair symbol
            side: Buy or sell
            stop_price: Trigger price for the stop order
            stop_type: Type of stop order - 'loss' or 'entry' (default: 'loss')
            order_type: Order type (market or limit)
            price_or_size: Price for limit orders, or size for market orders
            size_or_funds: Size for limit orders
            auto_borrow: Whether to enable auto-borrowing (True/False)
        """
        # Security measure: Check if user has the correct role
        required_role = discord.utils.get(ctx.guild.roles, name="Trading-Authorized")
        if required_role is None or required_role not in ctx.author.roles:
            await ctx.send("⛔ You don't have permission to place stop orders. You need the 'Trading-Authorized' role.")
            return

        # If no parameters were provided, collect them interactively (or provide better format guidance)
        if not all([market, side, stop_price]):
            # Consider adding interactive input collection here similar to handle_real_order
            # For now, just show format help
            await ctx.send("❌ Missing required parameters. Format: `!stoporder <market> <side> <stop_price> [stop_type] [order_type] [price_or_size] [size_or_funds] [auto_borrow]`")
            return

        try:
            # --- Parameter Processing ---
            market = market.upper() # Ensure uppercase

            # Process side
            side = side.lower()
            if side not in ["buy", "sell"]:
                await ctx.send("❌ Invalid side. Must be 'buy' or 'sell'.")
                return

            # Process stop type
            stop_type = stop_type.lower()
            if stop_type not in ["loss", "entry"]:
                await ctx.send("❌ Invalid stop type. Must be 'loss' or 'entry'.")
                return

            # Process order type
            order_type = order_type.lower()
            if order_type not in ["limit", "market"]:
                await ctx.send("❌ Invalid order type. Must be 'limit' or 'market'.")
                return

            # Process stop price
            try:
                stop_price_float = float(stop_price)
                if stop_price_float <= 0:
                    await ctx.send("❌ Stop price must be positive.")
                    return
            except ValueError:
                await ctx.send("❌ Invalid stop price. Must be a number.")
                return

            # --- Determine Side Effect Type ---
            side_effect = "AUTO_BORROW_REPAY" if auto_borrow else "NO_SIDE_EFFECT"
            logger.debug(f"Handling stop order for {market}. Side: {side}, Stop Type: {stop_type}, Order Type: {order_type}, Auto Borrow: {auto_borrow}, Side Effect: {side_effect}")

            # --- (Optional but Recommended) 10% Price Check ---
            try:
                ticker_data = await self.market_service.get_ticker(market)
                if ticker_data and not ticker_data.get("error"):
                    current_price = float(ticker_data["data"].get("price", 0))
                    if current_price > 0:
                        diff_percent = abs((stop_price_float - current_price) / current_price) * 100
                        # Allow larger difference for TP/SL farther away? Adjust threshold if needed.
                        if diff_percent > 10:
                            logger.warning(f"Stop price {stop_price_float} is >10% away from current price {current_price} for {market}. Proceeding anyway.")
                            # Decide if you want to block this or just warn
                            # await ctx.send(f"⚠️ Stop price must be within 10% of the current price. Current: ${current_price:.2f}, Stop: ${stop_price_float:.2f}, Difference: {diff_percent:.2f}%")
                            # return
                else:
                    logger.warning(f"Could not get current price for {market} to perform 10% check.")
            except Exception as price_check_error:
                logger.warning(f"Error during price check for 10% rule: {price_check_error}")


            # Determine the Binance API order type
            # Note: Your API examples used TAKE_PROFIT/STOP_LOSS directly, not _LIMIT versions
            # If you want _LIMIT functionality, adjust logic here and parameter requirements
            if stop_type == "loss":
                if order_type == "limit":
                    binance_order_type = "STOP_LOSS_LIMIT"
                else: # Market
                    binance_order_type = "STOP_LOSS" # API uses this for market stop loss
            else:  # entry ('take_profit' from user perspective)
                if order_type == "limit":
                    binance_order_type = "TAKE_PROFIT_LIMIT"
                else: # Market
                    binance_order_type = "TAKE_PROFIT" # API uses this for market take profit

            logger.debug(f"Mapped to Binance API order type: {binance_order_type}")

            # Process remaining parameters based on limit/market
            price: Optional[float] = None
            size: Optional[float] = None

            if order_type == "limit":
                # For LIMIT stops, we need price and size
                if not price_or_size:
                    await ctx.send("❌ Price (as `price_or_size`) is required for LIMIT stop orders.")
                    return
                try:
                    price = float(price_or_size)
                    if price <= 0:
                        await ctx.send("❌ Limit price must be positive.")
                        return
                except ValueError:
                    await ctx.send("❌ Invalid limit price. Must be a number.")
                    return

                if not size_or_funds:
                    await ctx.send("❌ Size (as `size_or_funds`) is required for LIMIT stop orders.")
                    return
                try:
                    size = float(size_or_funds)
                    if size <= 0:
                        await ctx.send("❌ Size must be positive.")
                        return
                    size = round(size, 5) # Round quantity
                except ValueError:
                    await ctx.send("❌ Invalid size. Must be a number.")
                    return

                # --- Limit Order Confirmation ---
                stop_type_description = "Stop-Loss" if stop_type == "loss" else "Take-Profit/Entry"
                confirmation_details = (
                    f"You are about to place a **{stop_type_description} {side.upper()} LIMIT** order:\n"
                    f"- **Market:** {market}\n"
                    f"- **Quantity:** {size}\n"
                    f"- **Trigger Price:** ${stop_price_float:.2f}\n"
                    f"- **Order Price:** ${price:.2f}\n"
                    f"- **Side Effect:** `{side_effect}`"
                )
                if auto_borrow:
                    confirmation_details += "\n\n⚠️ **This order will automatically borrow assets if necessary.**"

                confirmed = await self.input_manager.confirm_action(
                    ctx,
                    title=f"⚠️ Confirm {stop_type_description} Limit Order",
                    description=confirmation_details,
                    color=discord.Color.gold(),
                    use_reactions=True # Or False if you prefer text confirm
                )

                if not confirmed:
                    await ctx.send("🛑 Stop order cancelled.")
                    return

                # --- Place Limit Stop Order via Service ---
                response = await self.binance_service.place_stop_order(
                    symbol=market,
                    side=side,
                    stop_price=stop_price_float,
                    quantity=size,
                    order_type=binance_order_type,
                    price=price, # Pass limit price
                    is_isolated=False, # Defaulting to Cross Margin, adjust if needed
                    side_effect_type=side_effect # Pass the determined side effect
                )

            else: # Market Order Path
                # For MARKET stops, we need size (passed as price_or_size)
                if not price_or_size:
                    await ctx.send("❌ Size (as `price_or_size`) is required for MARKET stop orders.")
                    return
                try:
                    size = float(price_or_size)
                    if size <= 0:
                        await ctx.send("❌ Size must be positive.")
                        return
                    size = round(size, 5) # Round quantity
                except ValueError:
                    await ctx.send("❌ Invalid size. Must be a number.")
                    return

                # --- Market Order Confirmation ---
                stop_type_description = "Stop-Loss" if stop_type == "loss" else "Take-Profit/Entry"
                confirmation_details = (
                    f"You are about to place a **{stop_type_description} {side.upper()} MARKET** order:\n"
                    f"- **Market:** {market}\n"
                    f"- **Quantity:** {size}\n"
                    f"- **Trigger Price:** ${stop_price_float:.2f}\n"
                    f"- **Side Effect:** `{side_effect}`"
                )
                if auto_borrow:
                    confirmation_details += "\n\n⚠️ **This order will automatically borrow assets if necessary.**"

                confirmed = await self.input_manager.confirm_action(
                    ctx,
                    title=f"⚠️ Confirm {stop_type_description} Market Order",
                    description=confirmation_details,
                    color=discord.Color.gold(),
                    use_reactions=True # Or False if you prefer text confirm
                )

                if not confirmed:
                    await ctx.send("🛑 Stop order cancelled.")
                    return

                # --- Place Market Stop Order via Service ---
                response = await self.binance_service.place_stop_order(
                    symbol=market,
                    side=side,
                    stop_price=stop_price_float,
                    quantity=size,
                    order_type=binance_order_type,
                    price=None, # No limit price for market
                    is_isolated=False, # Defaulting to Cross Margin, adjust if needed
                    side_effect_type=side_effect # Pass the determined side effect
                )

            # --- Process and Send Response ---
            if isinstance(response, dict) and not response.get("error", False):
                # Assuming response['data'] contains the order details if successful
                order_data = response.get("data", {})
                order_id = order_data.get("orderId")
                client_order_id = order_data.get("clientOrderId")
                status = order_data.get("status", "UNKNOWN") # Status might be NEW for stops

                stop_type_display = "Stop-Loss" if stop_type == "loss" else "Take-Profit/Entry"
                embed = discord.Embed(
                    title=f"✅ {stop_type_display} Order Placed/Accepted",
                    description=f"{stop_type_display} {order_type.upper()} order accepted for `{market}`.",
                    color=discord.Color.green(),
                    timestamp=datetime.now()
                )

                embed.add_field(name="Market", value=market, inline=True)
                embed.add_field(name="Side", value=side.upper(), inline=True)
                embed.add_field(name="Trigger Price", value=f"${stop_price_float:.2f}", inline=True)

                if order_type == "limit":
                    embed.add_field(name="Order Type", value=f"LIMIT (Stop)", inline=True)
                    embed.add_field(name="Order Price", value=f"${price:.2f}", inline=True)
                    embed.add_field(name="Quantity", value=f"{size}", inline=True)
                else: # Market
                    embed.add_field(name="Order Type", value=f"MARKET (Stop)", inline=True)
                    embed.add_field(name="Quantity", value=f"{size}", inline=True)
                    embed.add_field(name=" ", value=" ", inline=True) # Placeholder for alignment

                embed.add_field(name="Binance Type", value=f"`{binance_order_type}`", inline=True)
                embed.add_field(name="Side Effect", value=f"`{side_effect}`", inline=True)
                embed.add_field(name="Status", value=status, inline=True)

                if order_id:
                    embed.add_field(name="Order ID", value=f"`{order_id}`", inline=False)
                if client_order_id:
                    embed.add_field(name="Client OID", value=f"`{client_order_id}`", inline=False)

                embed.set_footer(text=f"Requested by {ctx.author.display_name}", icon_url=ctx.author.avatar.url if ctx.author.avatar else None)

                message = await ctx.send(embed=embed)
                # Add reaction for copying ID if needed
                if order_id:
                    await message.add_reaction("📋")
                    self.reaction_handler.register_message(message.id, str(order_id)) # Ensure ID is string

            else:
                # Handle API errors or unexpected responses
                error_msg = response.get("msg", "Unknown error during stop order placement.") if isinstance(response, dict) else str(response)
                logger.error(f"Stop order failed for {market}: {error_msg}")
                embed = discord.Embed(
                    title="❌ Stop Order Failed",
                    description=f"Failed to place stop order for `{market}`.",
                    color=discord.Color.red(),
                    timestamp=datetime.now()
                )
                embed.add_field(name="Error Details", value=f"```{error_msg}```", inline=False)
                await ctx.send(embed=embed)

        except ValueError as ve:
             logger.warning(f"Value error processing stop order command: {ve}")
             await ctx.send(f"❌ Input Error: {ve}")
        except Exception as e:
            logger.exception(f"Unexpected error handling stop order for {market}: {e}") # Use exception for stack trace
            await ctx.send(f"❌ An unexpected error occurred: {e}")

