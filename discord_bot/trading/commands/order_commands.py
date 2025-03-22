"""
Order commands for trading.
Handles order creation, testing, and cancellation.
"""

import discord
from discord.ext import commands
from datetime import datetime
import uuid
from typing import Dict, Optional
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
        order_type: str = "limit"
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
                    use_funds=use_funds
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