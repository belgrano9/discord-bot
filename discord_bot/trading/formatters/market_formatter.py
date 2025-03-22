"""
Market formatter for trading commands.
Formats market data into Discord embeds.
"""

import discord
from datetime import datetime
from typing import Dict, List, Any, Optional
from loguru import logger

from utils.embed_utilities import create_price_embed, create_alert_embed


class MarketFormatter:
    """Formatter for market data"""
    
    def format_ticker(self, symbol: str, ticker_data: Dict[str, Any]) -> discord.Embed:
        """
        Format ticker data into a Discord embed.
        
        Args:
            symbol: Trading pair symbol
            ticker_data: Ticker data
            
        Returns:
            Formatted Discord embed
        """
        # Format timestamp if available
        formatted_time = None
        if "time" in ticker_data:
            try:
                timestamp = int(ticker_data["time"]) / 1000  # Convert ms to seconds
                formatted_time = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
            except:
                pass
                
        # Use the utility to create the price embed
        embed = create_price_embed(
            symbol=symbol,
            price_data=ticker_data,
            title_prefix="Market Data",
            show_additional_fields=True,
            footer_text=f"Data from KuCoin | Time: {formatted_time or 'N/A'}"
        )
        
        return embed
    
    def format_fees(self, symbol: str, fees_data: List[Dict[str, Any]]) -> discord.Embed:
        """
        Format trading fees data into a Discord embed.
        
        Args:
            symbol: Trading pair symbol
            fees_data: List of fee data items
            
        Returns:
            Formatted Discord embed
        """
        # Create fields for the embed
        fields = []
        
        for fee_info in fees_data:
            symbol_name = fee_info.get("symbol", "Unknown")
            
            fee_details = ""
            if "takerFeeRate" in fee_info:
                taker_fee = float(fee_info["takerFeeRate"]) * 100
                fee_details += f"Taker Fee: {taker_fee:.4f}%\n"
                
            if "makerFeeRate" in fee_info:
                maker_fee = float(fee_info["makerFeeRate"]) * 100
                fee_details += f"Maker Fee: {maker_fee:.4f}%\n"
                
            fields.append((symbol_name, fee_details or "No fee data", False))
            
        # Create the embed
        embed = create_alert_embed(
            title="Trading Fees",
            description="Fee information for requested symbols",
            fields=fields,
            color=discord.Color.blue()
        )
        
        return embed