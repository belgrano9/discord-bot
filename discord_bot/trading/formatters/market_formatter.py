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
        # Format symbol for display
        display_symbol = symbol
        if len(symbol) >= 6:
            for quote in ["USDT", "USDC", "BUSD", "BTC", "ETH", "BNB"]:
                if symbol.endswith(quote):
                    base = symbol[:-len(quote)]
                    display_symbol = f"{base}/{quote}"
                    break
        
        # Extract price data from Binance format
        price_data = {
            "price": float(ticker_data.get("price", 0))
        }
        
        # Get 24h data if available
        if "priceChangePercent" in ticker_data:
            price_data["change_percent"] = float(ticker_data.get("priceChangePercent", 0))
            price_data["change"] = float(ticker_data.get("priceChange", 0))
            
        if "volume" in ticker_data:
            price_data["volume"] = float(ticker_data.get("volume", 0))
            
        if "highPrice" in ticker_data and "lowPrice" in ticker_data:
            price_data["high"] = float(ticker_data.get("highPrice", 0))
            price_data["low"] = float(ticker_data.get("lowPrice", 0))
            
        if "bidPrice" in ticker_data and "askPrice" in ticker_data:
            price_data["bestBid"] = float(ticker_data.get("bidPrice", 0))
            price_data["bestAsk"] = float(ticker_data.get("askPrice", 0))
            
        # Format timestamp if available
        formatted_time = None
        if "time" in ticker_data or "closeTime" in ticker_data:
            try:
                timestamp = int(ticker_data.get("time", ticker_data.get("closeTime", 0))) / 1000
                formatted_time = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
            except:
                pass
                
        # Use the utility to create the price embed
        embed = create_price_embed(
            symbol=display_symbol,
            price_data=price_data,
            title_prefix="Market Data",
            show_additional_fields=True,
            footer_text=f"Data from Binance | Time: {formatted_time or 'N/A'}"
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
        # Format symbol for display
        display_symbol = symbol
        if len(symbol) >= 6:
            for quote in ["USDT", "USDC", "BUSD", "BTC", "ETH", "BNB"]:
                if symbol.endswith(quote):
                    base = symbol[:-len(quote)]
                    display_symbol = f"{base}/{quote}"
                    break
        
        # Create fields for the embed
        fields = []
        
        for fee_info in fees_data:
            symbol_name = fee_info.get("symbol", display_symbol)
            
            fee_details = ""
            # Binance uses different fee structure keys
            if "takerCommission" in fee_info:
                taker_fee = float(fee_info["takerCommission"]) * 100
                fee_details += f"Taker Fee: {taker_fee:.4f}%\n"
                
            if "makerCommission" in fee_info:
                maker_fee = float(fee_info["makerCommission"]) * 100
                fee_details += f"Maker Fee: {maker_fee:.4f}%\n"
                
            # For spot trading levels
            if "tier" in fee_info:
                fee_details += f"Tier: {fee_info['tier']}\n"
                
            # VIP level if available
            if "vipLevel" in fee_info:
                fee_details += f"VIP Level: {fee_info['vipLevel']}\n"
                
            fields.append((symbol_name, fee_details or "No fee data", False))
            
        # Create the embed
        embed = create_alert_embed(
            title="Trading Fees",
            description="Fee information for requested symbols",
            fields=fields,
            color=discord.Color.blue()
        )
        
        return embed
    
    def format_markets(self, markets: List[Dict[str, Any]], filter_str: Optional[str] = None) -> discord.Embed:
        """
        Format list of available markets into a Discord embed.
        
        Args:
            markets: List of market data
            filter_str: Optional filter string
            
        Returns:
            Formatted Discord embed
        """
        num_markets = len(markets)
        
        # Create the embed
        embed = discord.Embed(
            title="Available Markets on Binance",
            description=f"Found {num_markets} markets" + (f" matching '{filter_str}'" if filter_str else ""),
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        
        # Group markets by quote asset
        quote_markets = {}
        for market in markets:
            symbol = market.get("symbol", "")
            
            # Try to extract base and quote
            for quote in ["USDT", "USDC", "BUSD", "BTC", "ETH", "BNB"]:
                if symbol.endswith(quote):
                    if quote not in quote_markets:
                        quote_markets[quote] = []
                    quote_markets[quote].append(symbol)
                    break
            else:
                # If no known quote asset is found
                if "OTHER" not in quote_markets:
                    quote_markets["OTHER"] = []
                quote_markets["OTHER"].append(symbol)
        
        # Add fields for each quote asset group, limiting to reasonable sizes
        for quote, symbols in quote_markets.items():
            if len(symbols) > 0:
                value = ", ".join(symbols[:20])
                if len(symbols) > 20:
                    value += f" and {len(symbols)-20} more..."
                
                embed.add_field(
                    name=f"{quote} Markets ({len(symbols)})",
                    value=value,
                    inline=False
                )
        
        # Add footer with instructions
        embed.set_footer(text="Use a filter to see specific markets. Example: !markets BTC")
        
        return embed