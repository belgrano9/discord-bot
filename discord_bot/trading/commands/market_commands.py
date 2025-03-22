"""
Market commands for trading.
Handles market data and information.
"""

import discord
from discord.ext import commands
from typing import Optional
from loguru import logger

from ..services.market_service import MarketService
from ..formatters.market_formatter import MarketFormatter


class MarketCommands:
    """Command handlers for market information"""
    
    def __init__(self):
        """Initialize market commands"""
        self.market_service = MarketService()
        self.market_formatter = MarketFormatter()
        logger.debug("Initialized MarketCommands")
    
    async def handle_ticker(self, ctx: commands.Context, symbol: str = "BTC-USDT") -> None:
        """
        Handle the ticker command.
        
        Args:
            ctx: Discord context
            symbol: Trading pair symbol
        """
        try:
            # Get the ticker data
            ticker_data = await self.market_service.get_ticker(symbol)
            
            if not ticker_data:
                await ctx.send(f"❌ Error getting ticker data for {symbol}")
                return
            
            # Create the embed
            embed = self.market_formatter.format_ticker(symbol, ticker_data)
            
            # Send the embed
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"❌ Error fetching ticker: {str(e)}")
    
    async def handle_fees(self, ctx: commands.Context, symbol: str = "BTC-USDT") -> None:
        """
        Handle the fees command.
        
        Args:
            ctx: Discord context
            symbol: Trading pair symbol
        """
        try:
            # Get the fee data
            fees_data = await self.market_service.get_trade_fees(symbol)
            
            if not fees_data:
                await ctx.send(f"❌ Error getting fee data for {symbol}")
                return
            
            # Create the embed
            embed = self.market_formatter.format_fees(symbol, fees_data)
            
            # Send the embed
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"❌ Error fetching fee data: {str(e)}")