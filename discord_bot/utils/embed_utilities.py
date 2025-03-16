"""
Utility functions for creating standardized Discord embeds across the bot.
This module centralizes embed creation to ensure consistent styling and behavior.
"""

import discord
from datetime import datetime
from typing import Dict, List, Any, Optional, Union, Tuple


def create_price_embed(
    symbol: str,
    price_data: Dict[str, Any],
    title_prefix: str = "",
    show_additional_fields: bool = True,
    timestamp: bool = True,
    color_based_on_change: bool = True,
    footer_text: str = None
) -> discord.Embed:
    """
    Create an embed for displaying price information.
    
    Args:
        symbol: Trading pair symbol (e.g., "BTC-USDT")
        price_data: Dictionary containing price information
        title_prefix: Optional prefix for the embed title
        show_additional_fields: Whether to show bid/ask and other additional fields
        timestamp: Whether to add the current timestamp to the embed
        color_based_on_change: Color the embed based on price change direction
        footer_text: Custom footer text
        
    Returns:
        Formatted Discord embed with price information
    """
    # Extract symbol parts if it contains a separator
    if "-" in symbol:
        base_currency, quote_currency = symbol.split("-")
    else:
        base_currency, quote_currency = symbol, ""
    
    # Determine color based on price change if available
    color = discord.Color.blue()  # Default color
    if color_based_on_change and "change_percent" in price_data:
        change_percent = float(price_data.get("change_percent", 0))
        color = discord.Color.green() if change_percent >= 0 else discord.Color.red()
    
    # Create title with appropriate formatting
    if title_prefix:
        title = f"{title_prefix} {base_currency}"
        if quote_currency:
            title += f"/{quote_currency}"
    else:
        title = f"{base_currency}/{quote_currency}" if quote_currency else base_currency
        title += " Price"
    
    # Create the embed
    embed = discord.Embed(
        title=title,
        color=color,
        timestamp=datetime.now() if timestamp else None
    )
    
    # Add current price as the primary field
    current_price = price_data.get("price") or price_data.get("close")
    if current_price is not None:
        try:
            embed.add_field(
                name="Current Price",
                value=f"${float(current_price):.2f}",
                inline=True
            )
        except (ValueError, TypeError):
            embed.add_field(name="Current Price", value=str(current_price), inline=True)
    
    # Add price change if available
    if "change" in price_data and "change_percent" in price_data:
        change = float(price_data["change"])
        change_percent = float(price_data["change_percent"])
        sign = "+" if change >= 0 else ""
        
        embed.add_field(
            name="Change",
            value=f"{sign}${change:.2f} ({sign}{change_percent:.2f}%)",
            inline=True
        )
    
    # Add additional fields if requested
    if show_additional_fields:
        # Add volume if available
        if "volume" in price_data:
            volume = format_large_number(float(price_data["volume"]))
            embed.add_field(name="Volume", value=volume, inline=True)
        
        # Add high/low if available
        if "high" in price_data and "low" in price_data:
            high = float(price_data["high"])
            low = float(price_data["low"])
            embed.add_field(name="High", value=f"${high:.2f}", inline=True)
            embed.add_field(name="Low", value=f"${low:.2f}", inline=True)
        
        # Add bid/ask spread if available
        if "bestBid" in price_data and "bestAsk" in price_data:
            best_bid = float(price_data["bestBid"])
            best_ask = float(price_data["bestAsk"])
            spread = ((best_ask - best_bid) / best_bid) * 100
            
            embed.add_field(
                name="Bid/Ask",
                value=f"${best_bid:.2f} / ${best_ask:.2f}",
                inline=True
            )
            
            embed.add_field(
                name="Spread",
                value=f"{spread:.2f}%",
                inline=True
            )
    
    # Add footer if provided
    if footer_text:
        embed.set_footer(text=footer_text)
    
    return embed


def create_portfolio_embed(
    portfolio_data: List[Dict[str, Any]],
    title: str = "Portfolio Summary",
    description: str = None,
    show_positions: bool = True,
    previous_data: Dict[str, Any] = None,
    comparison_label: str = "previous period",
    max_positions: int = 10
) -> discord.Embed:
    """
    Create an embed for displaying portfolio information.
    
    Args:
        portfolio_data: List of portfolio position dictionaries
        title: Title for the embed
        description: Optional description text
        show_positions: Whether to include individual positions
        previous_data: Optional previous portfolio data for comparison
        comparison_label: Label for the comparison period
        max_positions: Maximum number of positions to display
        
    Returns:
        Formatted Discord embed with portfolio information
    """
    # Calculate total values
    total_current_value = sum(item["current_value"] for item in portfolio_data)
    total_initial_value = sum(item["initial_value"] for item in portfolio_data)
    total_gain_loss = total_current_value - total_initial_value
    total_gain_loss_percent = (
        (total_gain_loss / total_initial_value) * 100
        if total_initial_value else 0
    )
    
    # Determine color based on overall performance
    color = discord.Color.green() if total_gain_loss >= 0 else discord.Color.red()
    
    # Create embed
    embed = discord.Embed(
        title=title,
        description=description or f"Portfolio summary as of {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        color=color,
    )
    
    # Add portfolio summary
    embed.add_field(
        name="Total Value", 
        value=f"${total_current_value:.2f}", 
        inline=True
    )
    embed.add_field(
        name="Initial Investment",
        value=f"${total_initial_value:.2f}",
        inline=True
    )
    
    # Format the gain/loss
    sign = "+" if total_gain_loss >= 0 else ""
    embed.add_field(
        name="Total Gain/Loss",
        value=f"{sign}${total_gain_loss:.2f} ({sign}{total_gain_loss_percent:.2f}%)",
        inline=True
    )
    
    # Compare with previous period if available
    if previous_data and "total_value" in previous_data:
        previous_value = previous_data["total_value"]
        value_change = total_current_value - previous_value
        value_change_percent = (
            (value_change / previous_value * 100) if previous_value else 0
        )
        
        sign = "+" if value_change >= 0 else ""
        embed.add_field(
            name=f"Change from {comparison_label}",
            value=f"{sign}${value_change:.2f} ({sign}{value_change_percent:.2f}%)",
            inline=True
        )
    
    # Add individual positions if requested
    if show_positions and portfolio_data:
        # Limit to max_positions
        positions_to_show = portfolio_data[:max_positions]
        position_overflowed = len(portfolio_data) > max_positions
        
        for item in positions_to_show:
            ticker = item["ticker"]
            current_price = item["current_price"]
            shares = item["shares"]
            entry_price = item["entry_price"]
            gain_loss = item["gain_loss"]
            gain_loss_percent = item["gain_loss_percent"]
            
            sign = "+" if gain_loss >= 0 else ""
            position_value = (
                f"${current_price:.2f} × {shares} = ${item['current_value']:.2f}\n"
                f"Entry: ${entry_price:.2f}\n"
                f"P/L: {sign}${gain_loss:.2f} ({sign}{gain_loss_percent:.2f}%)"
            )
            
            embed.add_field(name=ticker, value=position_value, inline=True)
        
        if position_overflowed:
            overflow_count = len(portfolio_data) - max_positions
            embed.add_field(
                name=f"+ {overflow_count} more positions",
                value="Use a more specific command to see all positions",
                inline=False
            )
    
    return embed


def create_order_embed(
    order_data: Dict[str, Any],
    title: str = "Order Details",
    is_success: bool = True,
    order_type: str = "limit",
    side: str = None,
    include_id: bool = True
) -> discord.Embed:
    """
    Create an embed for displaying order information.
    
    Args:
        order_data: Dictionary containing order information
        title: Title for the embed
        is_success: Whether the order was successful
        order_type: Type of order (market, limit)
        side: Order side (buy, sell)
        include_id: Whether to include order ID
        
    Returns:
        Formatted Discord embed with order information
    """
    # Determine color based on side or success
    if side:
        side = side.lower()
        color = discord.Color.green() if side == "buy" else discord.Color.red()
    else:
        color = discord.Color.green() if is_success else discord.Color.red()
    
    # Get side from order_data if not provided
    if not side and "side" in order_data:
        side = order_data["side"].lower()
        color = discord.Color.green() if side == "buy" else discord.Color.red()
    
    # Create the embed
    embed = discord.Embed(
        title=title,
        color=color,
        timestamp=datetime.now()
    )
    
    # Add symbol/market if available
    if "symbol" in order_data or "market" in order_data:
        symbol = order_data.get("symbol") or order_data.get("market")
        embed.add_field(name="Market", value=symbol, inline=True)
    
    # Add order type
    if "type" in order_data:
        order_type = order_data["type"]
    embed.add_field(name="Type", value=order_type.capitalize(), inline=True)
    
    # Add side if available
    if side:
        embed.add_field(name="Side", value=side.upper(), inline=True)
    
    # Add price if available
    if "price" in order_data:
        try:
            price = float(order_data["price"])
            embed.add_field(name="Price", value=f"${price:.2f}", inline=True)
        except (ValueError, TypeError):
            embed.add_field(name="Price", value=str(order_data["price"]), inline=True)
    
    # Add amount/size if available
    if "size" in order_data:
        embed.add_field(name="Amount", value=str(order_data["size"]), inline=True)
    elif "amount" in order_data:
        embed.add_field(name="Amount", value=str(order_data["amount"]), inline=True)
    
    # Add funds if available
    if "funds" in order_data:
        try:
            funds = float(order_data["funds"])
            embed.add_field(name="Funds", value=f"${funds:.2f}", inline=True)
        except (ValueError, TypeError):
            embed.add_field(name="Funds", value=str(order_data["funds"]), inline=True)
    
    # Add order ID if requested and available
    if include_id:
        order_id = None
        id_keys = ["orderId", "order_id", "id"]
        
        for key in id_keys:
            if key in order_data:
                order_id = order_data[key]
                break
                
        if "data" in order_data and isinstance(order_data["data"], dict):
            for key in id_keys:
                if key in order_data["data"]:
                    order_id = order_data["data"][key]
                    break
        
        if order_id:
            embed.add_field(name="Order ID", value=f"`{order_id}`", inline=False)
    
    return embed


def create_alert_embed(
    title: str,
    description: str,
    fields: List[Tuple[str, str, bool]] = None,
    color: discord.Color = None,
    timestamp: bool = True,
    footer_text: str = None
) -> discord.Embed:
    """
    Create a standardized alert/notification embed.
    
    Args:
        title: Title for the embed
        description: Description text
        fields: List of (name, value, inline) tuples for fields
        color: Discord color for the embed (defaults to blue)
        timestamp: Whether to add the current timestamp
        footer_text: Optional footer text
        
    Returns:
        Formatted Discord embed for alerts and notifications
    """
    embed = discord.Embed(
        title=title,
        description=description,
        color=color or discord.Color.blue(),
        timestamp=datetime.now() if timestamp else None
    )
    
    # Add fields if provided
    if fields:
        for name, value, inline in fields:
            embed.add_field(name=name, value=value, inline=inline)
    
    # Add footer if provided
    if footer_text:
        embed.set_footer(text=footer_text)
    
    return embed


def format_large_number(num: float) -> str:
    """
    Format large numbers with K, M, B suffixes.
    
    Args:
        num: Number to format
        
    Returns:
        Formatted string with appropriate suffix
    """
    if num is None:
        return "N/A"
    
    abs_num = abs(num)
    sign = "-" if num < 0 else ""
    
    if abs_num >= 1_000_000_000:
        return f"{sign}{abs_num/1_000_000_000:.2f}B"
    elif abs_num >= 1_000_000:
        return f"{sign}{abs_num/1_000_000:.2f}M"
    elif abs_num >= 1_000:
        return f"{sign}{abs_num/1_000:.2f}K"
    else:
        return f"{sign}{abs_num:.2f}"


def format_field_name(name: str) -> str:
    """
    Convert snake_case to Title Case with spaces.
    
    Args:
        name: Field name in snake_case
        
    Returns:
        Formatted field name in Title Case
    """
    return " ".join(word.capitalize() for word in name.split("_"))