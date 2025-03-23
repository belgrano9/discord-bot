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
from ..services.kucoin_service import KuCoinService
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
        self.kucoin_service = KuCoinService()
        self.market_service = MarketService()
        self.order_formatter = OrderFormatter()
        self.input_manager = InputManager()
        self.reaction_handler = reaction_handler
        logger.debug("Initialized OrderCommands")
    
    async def handle_test_trade(
        self,
        ctx: commands.Context,
        market: str = "BTC-USDT",
        side: str = "buy",
        amount: float = 0.001,
        price: Optional[float] = None,
        order_type: str = "limit"
    ) -> None:
        """
        Handle the test trade command.
        
        Args:
            ctx: Discord context
            market: Trading pair
            side: Buy or sell
            amount: Amount to trade
            price: Price for limit orders
            order_type: Type of order (market or limit)
        """
        # Normalize inputs
        market = market.upper()
        order_type = order_type.lower()
        side_enum = OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL
        order_type_enum = OrderType.LIMIT if order_type == "limit" else OrderType.MARKET
        
        # Set default price for limit orders if not provided
        if order_type_enum == OrderType.LIMIT and price is None:
            try:
                ticker_data = await self.market_service.get_ticker(market)
                if ticker_data:
                    price = float(ticker_data.get("price", 0))
                else:
                    await ctx.send("❌ Price is required for limit orders.")
                    return
            except Exception as e:
                await ctx.send(f"❌ Error getting current price: {str(e)}")
                return
        
        # Create the order request
        order_request = OrderRequest(
            symbol=market,
            side=side_enum,
            order_type=order_type_enum,
            amount=amount,
            price=price
        )
        
        # Create a simulated order ID
        test_order_id = f"test-{int(datetime.now().timestamp())}"
        
        # Create the embed
        embed = self.order_formatter.format_test_order(order_request, test_order_id)
        
        # Send the message
        message = await ctx.send(embed=embed)
        
        # Add the clipboard emoji reaction for testing purposes
        await message.add_reaction("📋")
        
        # Register with reaction handler
        self.reaction_handler.register_message(message.id, test_order_id)
    
    async def handle_real_order(
    self,
    ctx: commands.Context,
    market: Optional[str] = None,
    side: Optional[str] = None,
    amount: Optional[str] = None,
    price_or_type: Optional[str] = None,
    order_type: str = "limit",
    auto_borrow: bool = False
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
                
                # For market orders with no price specified, get current price for display
                if order_type_enum == OrderType.MARKET and price is None:
                    # Get current price for display purposes
                    try:
                        ticker_data = await self.market_service.get_ticker(market)
                        if ticker_data:
                            price = float(ticker_data.get("price", 0))
                    except:
                        pass
                
                # Create the order request
                order_request = OrderRequest(
                    symbol=market.upper(),
                    side=side_enum,
                    order_type=order_type_enum,
                    amount=amount_float,
                    price=price,
                    use_funds=use_funds,
                    auto_borrow=auto_borrow,  # Use the parameter
                    is_isolated=True  # Always use isolated margin
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
        order_response = await self.kucoin_service.place_order(order_request)
        
        # Create the embed
        embed = self.order_formatter.format_order_response(order_response, order_request)
        
        # Send the message
        message = await ctx.send(embed=embed)
        
        # Add clipboard reaction if we have an order ID
        if order_response.order_id:
            await message.add_reaction("📋")
            # Register with reaction handler
            self.reaction_handler.register_message(message.id, order_response.order_id)

    async def handle_full_order(
    self,
    ctx: commands.Context,
    market: Optional[str] = None,
    side: Optional[str] = None,
    amount: Optional[str] = None,
    price_or_type: Optional[str] = None,
    order_type: str = "limit",
    auto_borrow: bool = False
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
                
                # For market orders with no price specified, get current price for display
                if order_type_enum == OrderType.MARKET and price is None:
                    # Get current price for display purposes
                    try:
                        ticker_data = await self.market_service.get_ticker(market)
                        if ticker_data:
                            price = float(ticker_data.get("price", 0))
                    except:
                        pass
                
                # Create the order request
                order_request = OrderRequest(
                    symbol=market.upper(),
                    side=side_enum,
                    order_type=order_type_enum,
                    amount=amount_float,
                    price=price,
                    use_funds=use_funds,
                    auto_borrow=auto_borrow,  # Use the parameter
                    is_isolated=True  # Always use isolated margin
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
        order_response = await self.kucoin_service.place_full_order(ctx, order_request)
        
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
        stop_type: str = "loss",
        order_type: str = "limit",
        price_or_size: Optional[str] = None,
        size_or_funds: Optional[str] = None
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
            price_or_size: Price for limit orders or size for all orders
            size_or_funds: Size or funds depending on context
        """
        # Security measure: Check if user has the correct role
        required_role = discord.utils.get(ctx.guild.roles, name="Trading-Authorized")
        if required_role is None or required_role not in ctx.author.roles:
            await ctx.send("⛔ You don't have permission to place stop orders. You need the 'Trading-Authorized' role.")
            return
        
        # If no parameters were provided, collect them interactively
        if not all([market, side, stop_price]):
            await ctx.send("❌ Missing required parameters. Format: !stoporder <market> <side> <stop_price> [stop_type] [order_type] [price_or_size] [size_or_funds]")
            return
        
        try:
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
            
            # Process remaining parameters based on order type
            if order_type == "limit":
                # For limit orders, we need price and size
                if not price_or_size:
                    await ctx.send("❌ Price is required for limit orders.")
                    return
                
                try:
                    price = float(price_or_size)
                    if price <= 0:
                        await ctx.send("❌ Price must be positive.")
                        return
                except ValueError:
                    await ctx.send("❌ Invalid price. Must be a number.")
                    return
                
                if not size_or_funds:
                    await ctx.send("❌ Size is required for limit orders.")
                    return
                
                try:
                    size = float(size_or_funds)
                    if size <= 0:
                        await ctx.send("❌ Size must be positive.")
                        return
                except ValueError:
                    await ctx.send("❌ Invalid size. Must be a number.")
                    return
                
                # Get confirmation
                stop_type_description = "stop-loss" if stop_type == "loss" else "stop-entry"
                confirmed = await self.input_manager.confirm_action(
                    ctx,
                    title=f"⚠️ Confirm {stop_type_description.capitalize()} Limit Order",
                    description=f"You are about to place a {stop_type_description} {side} limit order for {size} {market} at price ${price} when triggered at ${stop_price}.",
                    color=discord.Color.gold()
                )
                
                if not confirmed:
                    await ctx.send("🛑 Stop order cancelled.")
                    return
                
                # Place the order
                response = await self.kucoin_service.place_stop_order(
                    symbol=market,
                    side=side,
                    stop_price=str(stop_price_float),
                    stop_type=stop_type,
                    order_type="limit",
                    price=str(price),
                    size=str(size)
                )
            else:
                # For market orders, we need either size or funds
                if not price_or_size:
                    await ctx.send("❌ Either size or funds is required for market orders.")
                    return
                
                # Determine if we're using size or funds
                use_size = True
                if side == "buy" and size_or_funds and size_or_funds.lower() == "funds":
                    use_size = False
                    
                if use_size:
                    # Using size
                    try:
                        size = float(price_or_size)
                        if size <= 0:
                            await ctx.send("❌ Size must be positive.")
                            return
                    except ValueError:
                        await ctx.send("❌ Invalid size. Must be a number.")
                        return
                    
                    # Get confirmation
                    stop_type_description = "stop-loss" if stop_type == "loss" else "stop-entry"
                    confirmed = await self.input_manager.confirm_action(
                        ctx,
                        title=f"⚠️ Confirm {stop_type_description.capitalize()} Market Order",
                        description=f"You are about to place a {stop_type_description} {side} market order for {size} {market} when triggered at ${stop_price}.",
                        color=discord.Color.gold()
                    )
                    
                    if not confirmed:
                        await ctx.send("🛑 Stop order cancelled.")
                        return
                    
                    # Place the order
                    response = await self.kucoin_service.place_stop_order(
                        symbol=market,
                        side=side,
                        stop_price=str(stop_price_float),
                        stop_type=stop_type,
                        order_type="market",
                        size=str(size)
                    )
                else:
                    # Using funds
                    try:
                        funds = float(price_or_size)
                        if funds <= 0:
                            await ctx.send("❌ Funds must be positive.")
                            return
                    except ValueError:
                        await ctx.send("❌ Invalid funds. Must be a number.")
                        return
                    
                    # Get confirmation
                    stop_type_description = "stop-loss" if stop_type == "loss" else "stop-entry"
                    confirmed = await self.input_manager.confirm_action(
                        ctx,
                        title=f"⚠️ Confirm {stop_type_description.capitalize()} Market Order",
                        description=f"You are about to place a {stop_type_description} {side} market order using ${funds} when triggered at ${stop_price}.",
                        color=discord.Color.gold()
                    )
                    
                    if not confirmed:
                        await ctx.send("🛑 Stop order cancelled.")
                        return
                    
                    # Place the order
                    response = await self.kucoin_service.place_stop_order(
                        symbol=market,
                        side=side,
                        stop_price=str(stop_price_float),
                        stop_type=stop_type,
                        order_type="market",
                        funds=str(funds)
                    )
            
            # Create and send the response embed
            if response["code"] == "200000":
                order_id = response["data"]
                stop_type_description = "Stop-Loss" if stop_type == "loss" else "Stop-Entry"
                embed = discord.Embed(
                    title=f"✅ {stop_type_description} {side.capitalize()} Order Placed",
                    description=f"{stop_type_description} {order_type} order placed successfully for {market}",
                    color=discord.Color.green(),
                    timestamp=datetime.now()
                )
                
                embed.add_field(name="Side", value=side.upper(), inline=True)
                embed.add_field(name="Type", value=f"{stop_type_description} {order_type.capitalize()}", inline=True)
                embed.add_field(name="Trigger Price", value=f"${stop_price_float}", inline=True)
                
                if order_type == "limit":
                    embed.add_field(name="Order Price", value=f"${price}", inline=True)
                    embed.add_field(name="Size", value=size, inline=True)
                elif use_size:
                    embed.add_field(name="Size", value=size, inline=True)
                else:
                    embed.add_field(name="Funds", value=f"${funds}", inline=True)
                
                embed.add_field(name="Order ID", value=f"`{order_id}`", inline=False)
                
                message = await ctx.send(embed=embed)
                await message.add_reaction("📋")
                self.reaction_handler.register_message(message.id, order_id)
            else:
                error_msg = response.get("msg", "Unknown error")
                embed = discord.Embed(
                    title="❌ Stop Order Failed",
                    description=f"Failed to place stop order: {error_msg}",
                    color=discord.Color.red(),
                    timestamp=datetime.now()
                )
                await ctx.send(embed=embed)
                
        except Exception as e:
            logger.error(f"Error placing stop order: {str(e)}")
            await ctx.send(f"❌ Error placing stop order: {str(e)}")


    async def handle_cancel_order(self, ctx: commands.Context, order_id: Optional[str] = None) -> None:
        """
        Handle the cancel order command.
        
        Args:
            ctx: Discord context
            order_id: Order ID to cancel
        """
        # Security measure: Check if user has the correct role
        required_role = discord.utils.get(ctx.guild.roles, name="Trading-Authorized")
        if required_role is None or required_role not in ctx.author.roles:
            await ctx.send("⛔ You don't have permission to cancel orders. You need the 'Trading-Authorized' role.")
            return
        
        # If no order ID was provided, ask for it interactively
        if not order_id:
            order_id = await self.input_manager.collect_input(
                ctx,
                "Please enter the order ID you want to cancel:",
                timeout=30
            )
            
            if not order_id:
                return  # User cancelled or timed out
        
        # Confirmation before proceeding
        confirmed = await self.input_manager.confirm_action(
            ctx,
            title="⚠️ Confirm Order Cancellation",
            description=f"Are you sure you want to cancel order ID: `{order_id}`?",
            color=discord.Color.gold(),
            use_reactions=False  # Use text confirmation instead
        )
        
        if not confirmed:
            await ctx.send("🛑 Order cancellation aborted.")
            return
        
        # Process the cancellation
        processing_message = await ctx.send("⏳ Processing order cancellation...")
        
        # Call the API to cancel the order
        success, message = await self.kucoin_service.cancel_order(order_id)
        
        # Create and send the embed
        embed = self.order_formatter.format_cancel_response(success, message, order_id)
        await processing_message.edit(content=None, embed=embed)