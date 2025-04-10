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
    
    async def handle_ticker(self, ctx: commands.Context, symbol: str = "BTCUSDT") -> None:
        """
        Handle the ticker command.
        
        Args:
            ctx: Discord context
            symbol: Trading pair symbol
        """
        try:
            # Normalize symbol for Binance (uppercase, no dash)
            symbol = symbol.upper().replace("-", "")
            
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
    
    async def handle_fees(self, ctx: commands.Context, symbol: str = "BTCUSDT") -> None:
        """
        Handle the fees command.
        
        Args:
            ctx: Discord context
            symbol: Trading pair symbol
        """
        try:
            # Normalize symbol for Binance (uppercase, no dash)
            symbol = symbol.upper().replace("-", "")
            
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
    
    async def handle_markets(self, ctx: commands.Context, filter_str: Optional[str] = None) -> None:
        """
        Handle the markets command to list available trading pairs.
        
        Args:
            ctx: Discord context
            filter_str: Optional string to filter markets
        """
        try:
            # Get available markets
            markets = await self.market_service.get_markets(filter_str)
            
            if not markets:
                await ctx.send("❌ No markets found" + (f" matching '{filter_str}'" if filter_str else ""))
                return
            
            # Create embeds (paginate if necessary)
            num_markets = len(markets)
            embed = discord.Embed(
                title="Available Markets",
                description=f"Found {num_markets} markets" + (f" matching '{filter_str}'" if filter_str else ""),
                color=discord.Color.blue()
            )
            
            # If too many markets, just summarize
            if num_markets > 50:
                # Group markets by quote currency
                quote_currencies = {}
                for market in markets:
                    symbol = market.get("symbol", "")
                    for quote in ["USDT", "USDC", "BTC", "ETH", "BNB"]:
                        if symbol.endswith(quote):
                            if quote not in quote_currencies:
                                quote_currencies[quote] = []
                            quote_currencies[quote].append(symbol)
                            break
                
                # Add fields for each group
                for quote, symbols in quote_currencies.items():
                    if len(symbols) > 0:
                        embed.add_field(
                            name=f"{quote} Pairs ({len(symbols)})",
                            value=", ".join(symbols[:10]) + (f" and {len(symbols)-10} more..." if len(symbols) > 10 else ""),
                            inline=False
                        )
                
                embed.set_footer(text="Use a filter to see specific markets. Example: !markets BTC")
            else:
                # Show all markets in groups of 15
                chunks = [markets[i:i+15] for i in range(0, len(markets), 15)]
                for i, chunk in enumerate(chunks):
                    field_value = "\n".join([market.get("symbol", "") for market in chunk])
                    embed.add_field(
                        name=f"Markets {i*15+1}-{i*15+len(chunk)}",
                        value=field_value,
                        inline=True
                    )
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"❌ Error fetching markets: {str(e)}")