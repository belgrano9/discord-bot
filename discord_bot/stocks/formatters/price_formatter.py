"""
Formatter for price data.
Converts raw price data into formatted output for display.
"""

import discord
from typing import Dict, List, Any, Optional
from datetime import datetime
from loguru import logger

from utils.embed_utilities import create_price_embed


class PriceFormatter:
    """Formatter for price data"""
    
    def format_current_price(
        self,
        ticker: str,
        price_data: Dict[str, Any],
        prefix: str = "Latest"
    ) -> discord.Embed:
        """
        Format current price data into a Discord embed.
        
        Args:
            ticker: Stock ticker symbol
            price_data: Price data dictionary
            prefix: Title prefix
            
        Returns:
            Formatted Discord embed
        """
        # Find the date field in the data
        date_field = next(
            (k for k in price_data.keys() if "date" in k.lower() or "time" in k.lower()),
            None
        )
        
        # Create footer text with date if available
        footer_text = f"Date: {price_data[date_field]}" if date_field else None
        
        # Use the utility function to create price embed
        embed = create_price_embed(
            symbol=ticker.upper(),
            price_data=price_data,
            title_prefix=prefix,
            footer_text=footer_text
        )
        
        return embed
    
    def format_historical_price(
        self,
        ticker: str,
        price_changes: Dict[str, float],
        days: int,
        date_str: Optional[str] = None
    ) -> discord.Embed:
        """
        Format historical price data into a Discord embed.
        
        Args:
            ticker: Stock ticker symbol
            price_changes: Price change dictionary
            days: Number of days of history
            date_str: Date string for footer
            
        Returns:
            Formatted Discord embed
        """
        # Prepare data for the price embed
        price_data = {
            "price": price_changes["latest_price"],
            "change": price_changes["price_change"],
            "change_percent": price_changes["price_change_pct"],
        }
        
        # Create embed with the utility function
        embed = create_price_embed(
            symbol=ticker.upper(),
            price_data=price_data,
            title_prefix=f"{days}-Day",
            footer_text=f"Date: {date_str}" if date_str else None,
            color_based_on_change=True
        )
        
        return embed
    
    def format_live_price(
        self,
        ticker: str,
        price_data: Dict[str, Any]
    ) -> discord.Embed:
        """
        Format live price data into a Discord embed.
        
        Args:
            ticker: Stock ticker symbol
            price_data: Price data dictionary
            
        Returns:
            Formatted Discord embed
        """
        # Use utility function to create the embed
        embed = create_price_embed(
            symbol=ticker.upper(),
            price_data=price_data,
            title_prefix="Live",
            footer_text=f"Last updated: {price_data.get('timestamp', 'N/A')}",
            show_additional_fields=True
        )
        
        return embed