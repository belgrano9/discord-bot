"""
Order formatter for trading commands.
Formats order data into Discord embeds.
"""

import discord
from datetime import datetime
from typing import Dict, List, Any, Optional
from loguru import logger

from utils.embed_utilities import create_order_embed
from ..models.order import OrderRequest, OrderResponse, OrderSide, OrderType


class OrderFormatter:
    """Formatter for order data"""
    
    def format_order_response(
        self, 
        order_response: OrderResponse, 
        order_request: Optional[OrderRequest] = None
    ) -> discord.Embed:
        """
        Format an order response into a Discord embed.
        
        Args:
            order_response: Order response data
            order_request: Original order request (optional)
            
        Returns:
            Formatted Discord embed
        """
        # Determine title and success status
        if order_response.is_success:
            is_success = True
            side = order_request.side.value if order_request else "unknown"
            title = f"✅ {side.upper()} Order Placed"
        else:
            is_success = False
            title = "❌ Order Failed"
            
        # Create the order data dictionary
        order_data = {
            "orderId": order_response.order_id,
            "clientOrderId": order_response.client_oid,
        }
        
        # Add fields from order_request if available
        if order_request:
            # Convert symbol format to display with a / instead of nothing
            symbol = order_request.symbol
            if len(symbol) >= 6:  # Most symbols like BTCUSDT
                # Try to identify the base and quote currency
                for quote in ["USDT", "USDC", "BUSD", "BTC", "ETH", "BNB"]:
                    if symbol.endswith(quote):
                        base = symbol[:-len(quote)]
                        order_data["symbol"] = f"{base}/{quote}"
                        break
                else:
                    order_data["symbol"] = symbol
            else:
                order_data["symbol"] = symbol
                
            order_data["side"] = order_request.side.value
            order_data["type"] = order_request.order_type.value
            
            if order_request.order_type == OrderType.LIMIT and order_request.price:
                order_data["price"] = order_request.price
                
            if order_request.use_funds and order_request.side == OrderSide.BUY:
                order_data["funds"] = order_request.amount
            else:
                order_data["size"] = order_request.amount
                
        # Add any additional data from the response
        if order_response.order_data:
            # Binance specific mappings
            binance_mappings = {
                "executedQty": "filled",
                "origQty": "size",
                "cummulativeQuoteQty": "funds",
                "price": "price",
                "type": "type"
            }
            
            for binance_key, our_key in binance_mappings.items():
                if binance_key in order_response.order_data:
                    order_data[our_key] = order_response.order_data[binance_key]
        
        # Create embed
        embed = create_order_embed(
            order_data=order_data,
            title=title,
            is_success=is_success,
            order_type=order_request.order_type.value if order_request else "unknown",
            side=order_request.side.value if order_request else None,
            include_id=True
        )
        
        # Add error message if failed
        if not is_success and order_response.error_message:
            embed.add_field(
                name="Error",
                value=order_response.error_message,
                inline=False
            )
            
        return embed
    
    def format_test_order(
        self,
        order_request: OrderRequest,
        test_order_id: str
    ) -> discord.Embed:
        """
        Format a test order into a Discord embed.
        
        Args:
            order_request: Test order request
            test_order_id: Generated test order ID
            
        Returns:
            Formatted Discord embed
        """
        # Convert symbol format for display
        symbol = order_request.symbol
        display_symbol = symbol
        if len(symbol) >= 6:
            for quote in ["USDT", "USDC", "BUSD", "BTC", "ETH", "BNB"]:
                if symbol.endswith(quote):
                    base = symbol[:-len(quote)]
                    display_symbol = f"{base}/{quote}"
                    break
        
        # Create order data dictionary
        order_data = {
            "symbol": display_symbol,
            "side": order_request.side.value,
            "type": order_request.order_type.value,
            "orderId": test_order_id,
            "size": str(order_request.amount),
        }
        
        if order_request.order_type == OrderType.LIMIT and order_request.price:
            order_data["price"] = order_request.price
            total_value = order_request.amount * order_request.price
            order_data["total"] = total_value
            
        # Create the embed
        embed = create_order_embed(
            order_data=order_data,
            title=f"🧪 TEST {order_request.side.value.upper()} Order Simulation",
            is_success=True,
            order_type=order_request.order_type.value,
            side=order_request.side.value
        )
        
        # Add test footer
        embed.set_footer(text="This is a test - no actual order was placed")
        
        return embed
    
    def format_cancel_response(
        self,
        success: bool,
        message: str,
        order_id: str
    ) -> discord.Embed:
        """
        Format a cancel order response into a Discord embed.
        
        Args:
            success: Whether cancellation was successful
            message: Response message
            order_id: Order ID that was cancelled
            
        Returns:
            Formatted Discord embed
        """
        if success:
            title = "✅ Order Cancelled Successfully"
            description = "The order has been cancelled."
            color = discord.Color.green()
        else:
            title = "❌ Error Cancelling Order"
            description = f"Failed to cancel order: {message}"
            color = discord.Color.red()
            
        # Create the embed
        embed = discord.Embed(
            title=title,
            description=description,
            color=color,
            timestamp=datetime.now()
        )
        
        # Add order ID field
        embed.add_field(
            name="Order ID", 
            value=f"`{order_id}`", 
            inline=False
        )
        
        return embed