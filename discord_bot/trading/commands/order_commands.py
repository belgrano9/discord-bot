"""
Order commands for trading.
Handles order creation, testing, and cancellation.
"""

import discord
from discord.ext import commands
from datetime import datetime
from typing import Optional
from loguru import logger
import time 

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

    async def handle_oco_order(
        self,
        ctx: commands.Context,
        market: Optional[str] = None,
        side: Optional[str] = None,
        quantity: Optional[str] = None,
        limit_price: Optional[str] = None,
        stop_price: Optional[str] = None,
        stop_limit_price: Optional[str] = None,
        auto_borrow: bool = False
    ) -> None:
        """
        Handle OCO (One-Cancels-the-Other) order command.
        
        Args:
            ctx: Discord context
            market: Trading pair symbol
            side: Buy or sell
            quantity: Amount to trade
            limit_price: Price for the limit order
            stop_price: Trigger price for the stop order
            stop_limit_price: Optional limit price for the stop (if None, uses market stop)
            auto_borrow: Whether to enable auto-borrowing
        """
        # Generate tracking ID for this command
        cmd_id = f"{ctx.author.id}_{int(time.time())}"
        logger.info(f"[OCO_CMD:{cmd_id}] User {ctx.author} ({ctx.author.id}) initiated OCO order command")
        logger.debug(f"[OCO_CMD:{cmd_id}] Raw params: market={market}, side={side}, quantity={quantity}, limit_price={limit_price}, stop_price={stop_price}, stop_limit_price={stop_limit_price}, auto_borrow={auto_borrow}")
        
        # Security check
        required_role = discord.utils.get(ctx.guild.roles, name="Trading-Authorized")
        if required_role is None or required_role not in ctx.author.roles:
            logger.warning(f"[OCO_CMD:{cmd_id}] Permission denied - user lacks 'Trading-Authorized' role")
            await ctx.send("⛔ You don't have permission to place orders. You need the 'Trading-Authorized' role.")
            return
        
        # Validate inputs
        if not all([market, side, quantity, limit_price, stop_price]):
            logger.warning(f"[OCO_CMD:{cmd_id}] Missing required parameters")
            await ctx.send("❌ Missing required parameters. Format: `!oco <market> <side> <quantity> <limit_price> <stop_price> [stop_limit_price] [auto_borrow]`")
            return
        
        # Log important information about market stop vs stop limit
        market_stop = stop_limit_price is None or stop_limit_price.lower() in ['0', 'none', 'null', 'market'] or (stop_limit_price.isdigit() and float(stop_limit_price) == 0)

        logger.info(f"[OCO_CMD:{cmd_id}] Order type: {'Market Stop' if market_stop else 'Stop Limit'} OCO with auto_borrow={auto_borrow}")
        
        try:
            # Process side
            side = side.lower()
            if side not in ["buy", "sell"]:
                await ctx.send("❌ Invalid side. Must be 'buy' or 'sell'.")
                return
            
            # Process quantity
            try:
                quantity_float = float(quantity)
                if quantity_float <= 0:
                    await ctx.send("❌ Quantity must be positive.")
                    return
            except ValueError:
                await ctx.send("❌ Invalid quantity. Must be a number.")
                return
            
            # Process limit price
            try:
                limit_price_float = float(limit_price)
                if limit_price_float <= 0:
                    await ctx.send("❌ Limit price must be positive.")
                    return
            except ValueError:
                await ctx.send("❌ Invalid limit price. Must be a number.")
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
            
            # Process optional stop limit price
            stop_limit_price_float = None
            if stop_limit_price:
                # Check if user is trying to specify "0" or "null" to indicate market stop
                if stop_limit_price.lower() in ['0', 'null', 'none', 'market'] or stop_limit_price == '0':
                    # This indicates they want a market stop
                    stop_limit_price_float = None
                    logger.debug(f"[OCO] User specified '{stop_limit_price}' for stop_limit_price - interpreting as market stop")
                else:
                    try:
                        stop_limit_price_float = float(stop_limit_price)
                        if stop_limit_price_float <= 0:
                            await ctx.send("❌ Stop limit price must be positive.")
                            return
                    except ValueError:
                        await ctx.send("❌ Invalid stop limit price. Must be a number.")
                        return
            
            # Get confirmation
            if side == "buy":
                description = (
                    f"You are about to place an OCO BUY order:\n"
                    f"- **Market:** {market.upper()}\n"
                    f"- **Quantity:** {quantity_float}\n"
                    f"- **Limit Price:** ${limit_price_float}\n"
                    f"- **Stop Price:** ${stop_price_float}\n"
                )
                if stop_limit_price_float:
                    description += f"- **Stop Limit Price:** ${stop_limit_price_float}\n"
                if auto_borrow:
                    description += "\n⚠️ **This order will automatically borrow funds if necessary.**"
            else:
                description = (
                    f"You are about to place an OCO SELL order:\n"
                    f"- **Market:** {market.upper()}\n"
                    f"- **Quantity:** {quantity_float}\n"
                    f"- **Limit Price:** ${limit_price_float}\n"
                    f"- **Stop Price:** ${stop_price_float}\n"
                )
                if stop_limit_price_float:
                    description += f"- **Stop Limit Price:** ${stop_limit_price_float}\n"
                if auto_borrow:
                    description += "\n⚠️ **This order will automatically borrow assets if necessary.**"
            
            logger.info(f"[OCO_CMD:{cmd_id}] Requesting user confirmation")
            confirmed = await self.input_manager.confirm_action(
                ctx,
                title="⚠️ Confirm OCO Order",
                description=description,
                color=discord.Color.gold(),
                use_reactions=True
            )
            
            if not confirmed:
                await ctx.send("🛑 OCO order cancelled.")
                return
            
            """ 
            # --- Estimate Margin Level Impact IF Auto Borrow is True ---
            if auto_borrow:
                logger.info(f"[OCO_CMD:{cmd_id}] Auto-borrow enabled. Estimating potential margin impact...")
                try:
                    # 1. Fetch current cross margin account summary
                    account_summary = await self.binance_service.get_cross_margin_account_summary()

                    if account_summary and not account_summary.get("error"):
                        current_assets_btc = account_summary.get('total_asset_btc')
                        current_liabilities_btc = account_summary.get('total_liability_btc')
                        current_margin_level = account_summary.get('current_margin_level')

                        # 2. Fetch current market price for conversion/valuation
                        # Ensure market is uppercase for API/service calls
                        market_upper = market.upper() if market else None
                        if not market_upper:
                            raise ValueError("Market symbol is missing for price lookup.")

                        ticker_data = await self.market_service.get_ticker(market_upper)
                        if ticker_data and not ticker_data.get("error"):
                            # Adapt based on your get_ticker response structure
                            current_price_str = ticker_data.get("data", {}).get("price")
                            if not current_price_str:
                                raise ValueError(f"Could not extract price from ticker data for {market_upper}")
                            current_price = float(current_price_str)

                            # Convert current assets/liabilities to USD equivalent
                            current_assets_usd = current_assets_btc * current_price
                            current_liabilities_usd = current_liabilities_btc * current_price

                            # 3. Estimate the value of the new borrow in USD
                            new_borrow_value_usd = 0
                            calculation_note = ""
                            base_asset = market_upper[:3] # e.g., BTC
                            quote_asset = market_upper[3:] # e.g., USDC

                            if side.lower() == 'sell':
                                # Borrowing BASE asset (e.g., BTC)
                                new_borrow_value_usd = quantity_float * current_price
                                calculation_note = f" (Estimating borrow of {quantity_float} {base_asset} @ ${current_price:.2f})"
                            elif side.lower() == 'buy':
                                # Borrowing QUOTE asset (e.g., USDC) - estimate worst case (full cost)
                                estimated_cost = quantity_float * limit_price_float # Use limit price as estimate
                                # Need to estimate how much USDC is actually borrowed (cost - available USDC)
                                # This is complex without fetching USDC balance. Simple approach: assume potentially borrowing full cost.
                                new_borrow_value_usd = estimated_cost # Assume full cost is borrowed for worst-case estimate
                                calculation_note = f" (Estimating potential borrow of up to ${estimated_cost:.2f} {quote_asset})"

                            # 4. Calculate projected values
                            projected_liabilities_usd = current_liabilities_usd + new_borrow_value_usd
                            projected_margin_level = float('inf') # Handle division by zero
                            if projected_liabilities_usd > 0:
                                # Assume assets don't change instantly for this pre-check
                                projected_margin_level = current_assets_usd / projected_liabilities_usd

                            # 5. Log the estimation
                            logger.info(f"[OCO_CMD:{cmd_id}] ESTIMATED Margin Impact{calculation_note}:")
                            logger.info(f"[OCO_CMD:{cmd_id}]   Current Assets (USD Equiv.): ~${current_assets_usd:.2f} ({current_assets_btc} {base_asset})")
                            logger.info(f"[OCO_CMD:{cmd_id}]   Current Liabilities (USD Equiv.): ~${current_liabilities_usd:.2f} ({current_liabilities_btc} {base_asset})")
                            logger.info(f"[OCO_CMD:{cmd_id}]   New Potential Borrow (USD Equiv.): ~${new_borrow_value_usd:.2f}")
                            logger.info(f"[OCO_CMD:{cmd_id}]   Projected Liabilities (USD Equiv.): ~${projected_liabilities_usd:.2f}")
                            logger.info(f"[OCO_CMD:{cmd_id}]   Current Margin Level (Reported): {current_margin_level or 'N/A'}")
                            logger.info(f"[OCO_CMD:{cmd_id}]   PROJECTED Margin Level (Calculated): ~{projected_margin_level:.2f}")
                            if projected_margin_level < 1.5: # Example threshold warning
                                logger.warning(f"[OCO_CMD:{cmd_id}] Projected Margin Level is low (< 1.5), risk of borrow denial or quick liquidation.")

                        else:
                            logger.warning(f"[OCO_CMD:{cmd_id}] Could not get ticker price for {market_upper} to estimate margin level.")

                    else:
                        error_msg = account_summary.get("msg", "Unknown error") if isinstance(account_summary, dict) else "Invalid response"
                        logger.warning(f"[OCO_CMD:{cmd_id}] Could not fetch margin account details for estimation: {error_msg}")

                except Exception as e:
                    logger.error(f"[OCO_CMD:{cmd_id}] Error during margin level estimation: {e}", exc_info=True)
            # --- End of Estimation Block ---
            """

            logger.info(f"[OCO_CMD:{cmd_id}] User confirmed order, proceeding to execution")
            # Process the order
            response = await self.binance_service.place_oco_order(
                symbol=market.upper(),
                side=side,
                quantity=quantity_float,
                price=limit_price_float,
                stop_price=stop_price_float,
                stop_limit_price=stop_limit_price_float,
                auto_borrow=auto_borrow
            )
            
            # Handle response
            if isinstance(response, dict) and not response.get("error", False):
                order_data = response.get("data", {})
                order_list_id = order_data.get("orderListId", "unknown")
                logger.info(f"[OCO_CMD:{cmd_id}] Order successfully placed with OrderListId: {order_list_id}")
            
                # Create embed
                embed = discord.Embed(
                    title=f"✅ OCO {side.upper()} Order Placed",
                    description=f"OCO order placed successfully for {market.upper()}",
                    color=discord.Color.green(),
                    timestamp=datetime.now()
                )
                
                # Add fields with order details
                embed.add_field(name="Market", value=market.upper(), inline=True)
                embed.add_field(name="Side", value=side.upper(), inline=True)
                embed.add_field(name="Quantity", value=str(quantity_float), inline=True)
                embed.add_field(name="Limit Price", value=f"${limit_price_float}", inline=True)
                embed.add_field(name="Stop Price", value=f"${stop_price_float}", inline=True)
                
                if stop_limit_price_float:
                    embed.add_field(name="Stop Limit Price", value=f"${stop_limit_price_float}", inline=True)
                
                # Add order IDs if available
                if "orderListId" in order_data:
                    embed.add_field(name="Order List ID", value=f"`{order_data['orderListId']}`", inline=False)
                
                if "orders" in order_data and isinstance(order_data["orders"], list):
                    for i, order in enumerate(order_data["orders"]):
                        if "orderId" in order:
                            embed.add_field(name=f"Order {i+1} ID", value=f"`{order['orderId']}`", inline=True)
                
                # Send the embed
                message = await ctx.send(embed=embed)
                
                # Add clipboard reaction if we have an order list ID
                if "orderListId" in order_data:
                    await message.add_reaction("📋")
                    # Register with reaction handler
                    self.reaction_handler.register_message(message.id, str(order_data["orderListId"]))
                    
            else:
                # Handle error
                error_msg = response.get("msg", "Unknown error") if isinstance(response, dict) else str(response)
                await ctx.send(f"❌ Failed to place OCO order: {error_msg}")
                
        except Exception as e:
            logger.exception(f"Error handling OCO order: {str(e)}")
            await ctx.send(f"❌ An error occurred: {str(e)}")

    async def handle_close_all_positions(self, ctx: commands.Context):
        """
        Handle the closeall command to close all active positions.
        
        Args:
            ctx: Discord context
        """
        command_id = f"cmd_{ctx.message.id}"
        logger.info(f"[{command_id}] User {ctx.author} ({ctx.author.id}) invoked close_all_positions command")
        
        # Security check: only users with Trading-Authorized role can close positions
        required_role = discord.utils.get(ctx.guild.roles, name="Trading-Authorized")
        if required_role is None or required_role not in ctx.author.roles:
            logger.warning(f"[{command_id}] User {ctx.author} lacks required role 'Trading-Authorized'")
            await ctx.send("⛔ You don't have permission to close positions. You need the 'Trading-Authorized' role.")
            return
        
        logger.info(f"[{command_id}] User {ctx.author} has required permissions, proceeding to confirmation")
        
        # Get confirmation from user
        confirmed = await self.input_manager.confirm_action(
            ctx,
            title="⚠️ Confirm Closing All Positions",
            description="You are about to close ALL active margin positions. This will create market orders to close each position immediately.\n\nThis action cannot be undone.",
            color=discord.Color.red(),
            use_reactions=True
        )
        
        if not confirmed:
            logger.info(f"[{command_id}] User {ctx.author} cancelled the operation")
            await ctx.send("🛑 Operation canceled. No positions were closed.")
            return
        
        logger.info(f"[{command_id}] User {ctx.author} confirmed, executing close all positions")
        
        # Send processing message
        processing_msg = await ctx.send("⏳ Closing all positions... This might take a moment.")
        logger.debug(f"[{command_id}] Sent processing message")
        
        try:
            # Call the service to close all positions
            logger.info(f"[{command_id}] Calling binance_service.close_all_positions()")
            start_time = time.time()
            results = await self.binance_service.close_all_positions()
            execution_time = time.time() - start_time
            logger.info(f"[{command_id}] Service call completed in {execution_time:.2f} seconds")
            
            if results.get("error", False):
                # Handle service error
                error_msg = results.get("msg", "Unknown error")
                logger.error(f"[{command_id}] Service returned error: {error_msg}")
                await processing_msg.edit(content=f"❌ Error: {error_msg}")
                return
            
            logger.debug(f"[{command_id}] Processing service results: {results}")
            
            # Create results embed
            summary = results["summary"]
            succeeded = summary['succeeded']
            failed = summary['failed']
            total = summary['total']
            
            logger.info(f"[{command_id}] Position closure summary: {succeeded}/{total} succeeded, {failed}/{total} failed")
            
            embed = discord.Embed(
                title="Position Closure Results",
                description=f"Attempted to close {total} positions.\n✅ {succeeded} succeeded\n❌ {failed} failed",
                color=discord.Color.green() if failed == 0 else discord.Color.gold(),
                timestamp=datetime.now()
            )
            
            # Add successful closures
            if results["success"]:
                success_details = []
                for pos in results["success"]:
                    symbol = pos["symbol"]
                    pos_type = pos["position_type"].capitalize()
                    size = pos["size"]
                    asset = pos["base_asset"]
                    success_details.append(f"• {symbol}: {pos_type} position of {size} {asset}")
                    logger.debug(f"[{command_id}] Successfully closed: {symbol} {pos_type} position of {size} {asset}")
                
                embed.add_field(
                    name=f"✅ Successfully Closed ({len(results['success'])})",
                    value="\n".join(success_details) if success_details else "None",
                    inline=False
                )
            
            # Add failed closures
            if results["failed"]:
                failed_details = []
                for pos in results["failed"]:
                    symbol = pos["symbol"]
                    pos_type = pos["position_type"].capitalize()
                    size = pos["size"]
                    asset = pos["base_asset"]
                    error = pos.get("error", "Unknown error")
                    failed_details.append(f"• {symbol}: {pos_type} position of {size} {asset}\n  Error: {error}")
                    logger.warning(f"[{command_id}] Failed to close: {symbol} {pos_type} position of {size} {asset}. Error: {error}")
                
                embed.add_field(
                    name=f"❌ Failed to Close ({len(results['failed'])})",
                    value="\n".join(failed_details) if failed_details else "None",
                    inline=False
                )
            
            # Set footer
            embed.set_footer(text=f"Requested by: {ctx.author} | Duration: {execution_time:.2f}s")
            
            # Update the message with the results
            logger.info(f"[{command_id}] Sending final results to user")
            await processing_msg.edit(content=None, embed=embed)
            logger.info(f"[{command_id}] Command execution completed")
            
        except Exception as e:
            logger.exception(f"[{command_id}] Unexpected error in handle_close_all_positions: {str(e)}")
            await processing_msg.edit(content=f"❌ An unexpected error occurred: {str(e)}")
        

    async def handle_cancel_all_orders(
        self,
        ctx: commands.Context,
        symbol: str,
        is_isolated: bool = False,
        tracking_id: str = None
    ) -> None:
        """
        Handle cancelling all open margin orders for a symbol.
        
        Args:
            ctx: Discord context
            symbol: Trading pair symbol (e.g., BTCUSDC)
            is_isolated: Whether to cancel isolated margin orders (default: False for cross margin)
            tracking_id: Optional tracking ID for logging continuity
        """
        # Generate tracking ID if not provided
        tracking_id = tracking_id or f"auto_{int(time.time())}"
        logger.info(f"[CANCELALL:{tracking_id}] Handler started for symbol={symbol}, is_isolated={is_isolated}")
        
        # Security check: only users with Trading-Authorized role can cancel orders
        required_role = discord.utils.get(ctx.guild.roles, name="Trading-Authorized")
        if required_role is None or required_role not in ctx.author.roles:
            logger.warning(f"[CANCELALL:{tracking_id}] Permission denied - user lacks 'Trading-Authorized' role")
            await ctx.send("⛔ You don't have permission to cancel orders. You need the 'Trading-Authorized' role.")
            return
        
        # Get confirmation from user
        margin_type = "Isolated" if is_isolated else "Cross"
        logger.debug(f"[CANCELALL:{tracking_id}] Requesting user confirmation for {margin_type} margin orders")
        confirmed = await self.input_manager.confirm_action(
            ctx,
            title="⚠️ Confirm Cancellation",
            description=f"You are about to cancel ALL open {margin_type} margin orders for **{symbol}**.\n\nThis action cannot be undone.",
            color=discord.Color.red(),
            use_reactions=True
        )
        
        if not confirmed:
            logger.info(f"[CANCELALL:{tracking_id}] User cancelled the operation")
            await ctx.send("🛑 Cancellation aborted.")
            return
        
        # Send processing message
        logger.debug(f"[CANCELALL:{tracking_id}] User confirmed, sending processing message")
        processing_msg = await ctx.send(f"⏳ Cancelling all {margin_type} margin orders for {symbol}...")
        
        try:
            # Call the binance service to cancel all orders
            logger.info(f"[CANCELALL:{tracking_id}] Calling BinanceService.cancel_all_margin_orders")
            response = await self.binance_service.cancel_all_margin_orders(
                symbol=symbol,
                is_isolated=is_isolated,
                tracking_id=tracking_id
            )
            
            # Log the raw response for debugging
            logger.debug(f"[CANCELALL:{tracking_id}] Raw service response: {response}")
            
            # Check if the cancellation was successful
            if not response.get("error", False):
                # Extract the response data
                cancelled_data = response.get("data", {})
                logger.info(f"[CANCELALL:{tracking_id}] Cancellation successful, data: {cancelled_data}")
                
                # Count how many orders were cancelled
                cancelled_count = 0
                if isinstance(cancelled_data, list):
                    cancelled_count = len(cancelled_data)
                elif isinstance(cancelled_data, dict):
                    # Sometimes the API returns a dict with a count
                    cancelled_count = cancelled_data.get("count", 0)
                
                # Create success embed
                embed = discord.Embed(
                    title="✅ Orders Cancelled",
                    description=f"Successfully cancelled all {margin_type} margin orders for **{symbol}**.",
                    color=discord.Color.green(),
                    timestamp=datetime.now()
                )
                
                # Add order count
                embed.add_field(
                    name="Orders Cancelled",
                    value=f"{cancelled_count} order(s)",
                    inline=False
                )
                
                # Add detailed order IDs if available and not too many
                if isinstance(cancelled_data, list) and len(cancelled_data) > 0:
                    if len(cancelled_data) <= 10:  # Only show details if reasonable number
                        order_ids = []
                        for order in cancelled_data:
                            order_id = order.get("orderId", "Unknown")
                            order_type = order.get("type", "Unknown")
                            order_ids.append(f"`{order_id}` ({order_type})")
                        
                        embed.add_field(
                            name="Cancelled Order IDs",
                            value="\n".join(order_ids),
                            inline=False
                        )
                    else:
                        embed.add_field(
                            name="Note",
                            value=f"Cancelled {len(cancelled_data)} orders. Too many to display individual IDs.",
                            inline=False
                        )
                
                # Update the message
                await processing_msg.edit(content=None, embed=embed)
                logger.info(f"[CANCELALL:{tracking_id}] Successfully displayed cancellation results to user")
                
            else:
                # Handle error
                error_msg = response.get("msg", "Unknown error")
                logger.error(f"[CANCELALL:{tracking_id}] Cancellation failed: {error_msg}")
                
                embed = discord.Embed(
                    title="❌ Cancellation Failed",
                    description=f"Failed to cancel {margin_type} margin orders for **{symbol}**.",
                    color=discord.Color.red(),
                    timestamp=datetime.now()
                )
                
                embed.add_field(
                    name="Error Details",
                    value=f"```\n{error_msg}\n```",
                    inline=False
                )
                
                # If there's a traceback, log it but don't show to user
                if "traceback" in response:
                    logger.error(f"[CANCELALL:{tracking_id}] Error traceback:\n{response['traceback']}")
                
                await processing_msg.edit(content=None, embed=embed)
                logger.info(f"[CANCELALL:{tracking_id}] Displayed error message to user")
                
        except Exception as e:
            logger.exception(f"[CANCELALL:{tracking_id}] Error cancelling {margin_type} margin orders for {symbol}: {str(e)}")
            await processing_msg.edit(content=f"❌ An unexpected error occurred: {str(e)}")
            logger.info(f"[CANCELALL:{tracking_id}] Displayed exception message to user") 