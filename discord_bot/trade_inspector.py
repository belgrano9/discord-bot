"""
Trade inspector cog for Discord bot.
Extracts and displays specific trade data from the most recent trade.
"""

import discord
from discord.ext import commands
from typing import Dict, Any, Optional
from loguru import logger

from trading.services.kucoin_service import KuCoinService


class TradeInspector(commands.Cog):
    """Discord cog for inspecting recent trade details"""

    def __init__(self, bot):
        """Initialize the trade inspector cog"""
        self.bot = bot
        self.kucoin_service = KuCoinService()
        logger.info("Trade Inspector cog initialized")

    @commands.command(name="inspect_last_trade")
    async def inspect_last_trade(self, ctx, symbol: Optional[str] = None):
        """
        Extract and display data from the most recent trade
        
        Parameters:
        symbol: Trading pair (optional, e.g., BTC-USDT)
        
        Example: !inspect_last_trade BTC-USDT
        """
        try:
            # Show processing message
            processing_msg = await ctx.send("⏳ Retrieving latest trade data...")
            
            # Get only the most recent trade
            trades = await self.kucoin_service.get_recent_trades(symbol, limit=10) #TODO update to just last
            margin_account = await self.kucoin_service.get_margin_account(symbol)

            if not trades:
                await processing_msg.edit(content=f"No recent trades found{' for ' + symbol if symbol else ''}.")
                return
            
            # Extract data from the most recent trade
            trade = trades[0]
            
            # Create a concise embed with just the requested data
            embed = discord.Embed(
                title=f"Last Trade Details for {trade.symbol}",
                color=discord.Color.blue(),
            )
            
            #Variables Needed
            d = {"buy": 1 , "sell": -1 }
            #base_asset = margin_account.base_asset
            quote_asset = margin_account.quote_asset
            #pretrade = float(quote_asset.currency) + trade.fee  + trade.total_value
            m = 102.18296751

            # Fees and Risk
            f0 = 0.001
            ft = 0.001
            risk = 0.01 * m
            rr = 1.5

            # Take profit & Stop Loss
            tp = (risk * rr + trade.size *  trade.price * (f0 + d[trade.side])) / (trade.size * (d[trade.side] - ft))
            sl = (risk - trade.size *  trade.price * (f0 + d[trade.side])) / (trade.size * (ft - d[trade.side]))

            # Add only the requested fields
            embed.add_field(name="Side", value=f"{trade.side}", inline=True)
            embed.add_field(name="Price", value=f"${trade.price:.8f}", inline=True)

            embed.add_field(name="Size", value=f"{trade.size:.8f}", inline=True)
            embed.add_field(name="Total", value=f"${trade.total_value:.8f}", inline=True)
            embed.add_field(name="Take Profit", value=f"${tp:.8f}", inline=True)
            embed.add_field(name="Stop Loss", value=f"${sl:.8f}", inline=True)
            
            #embed.add_field(
            #    name=f"Dollar Balance ({quote_asset.currency})",
            #    value=f"Available: ${quote_asset.available:.2f}\nTotal: ${pretrade:.2f}",
            #    inline=False
            #)
            

            # Update the message with the embed
            await processing_msg.edit(content=None, embed=embed)
            
        except Exception as e:
            logger.error(f"Error in inspect_last_trade: {str(e)}")
            await ctx.send(f"❌ Error retrieving trade data: {str(e)}")


async def setup(bot):
    """Add the TradeInspector cog to the bot"""
    await bot.add_cog(TradeInspector(bot))