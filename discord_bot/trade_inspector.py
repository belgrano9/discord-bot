"""
Trade inspector cog for Discord bot.
Extracts and displays specific trade data from the most recent trade.
"""

import discord
from discord.ext import commands
from typing import Dict, Any, Optional
from loguru import logger

from trading.services.kucoin_service import KuCoinService
from trading.interactions.reaction_handler import ReactionHandler
from trading.commands.order_commands import OrderCommands
from trading.commands.account_commands import AccountCommands
from trading.commands.market_commands import MarketCommands

class TradeInspector(commands.Cog):
    """Discord cog for inspecting recent trade details"""

    def __init__(self, bot):
        """Initialize the trade inspector cog"""
        self.bot = bot
        self.kucoin_service = KuCoinService()
        logger.info("Trade Inspector cog initialized")
        # Initialize components
        self.reaction_handler = ReactionHandler()
        self.order_commands = OrderCommands(self.reaction_handler)
        self.account_commands = AccountCommands()
        self.market_commands = MarketCommands()

    @commands.command(name="inspect_last_trade")
    async def inspect_last_trade(self, ctx, symbol: Optional[str] = None):
        """
        Extract and display data from the most recent trade
        
        Parameters:
        symbol: Trading pair (optional, e.g., BTC-USDT)
        
        Example: !inspect_last_trade BTC-USDT
        """
        try:
            logger.info("Accessed inspect_last_trade...")
            # Show processing message
            processing_msg = await ctx.send("⏳ Retrieving latest trade data...")
            
            logger.info("Getting trades...")
            # Get only the most recent trade
            trades = await self.kucoin_service.get_recent_trades(symbol, limit=10) #TODO update to just last
            margin_account = await self.kucoin_service.get_margin_account(symbol)

            if not trades:
                await processing_msg.edit(content=f"No recent trades found{' for ' + symbol if symbol else ''}.")
                return
            
            # Extract data from the most recent trade
            trade = trades[0]
            id = trade.trade_id
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
            m = 102

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
            
            opposite_side = "buy" if trade.side == "sell" else "sell"

            st1 = await self.kucoin_service.place_stop_order(symbol, order_type="market", side = opposite_side, stop_price=tp, stop_type="entry", size = trade.size)
            st2 = await self.kucoin_service.place_stop_order(symbol, order_type="market", side = opposite_side, stop_price=sl, stop_type="loss", size = trade.size)
            logger.info("Placed stop orders")

            # Add feedback on stop order placement
            if st1.get("code") == "200000" and st2.get("code") == "200000":
                embed.add_field(name="Stop Orders", value="✅ Take-profit and stop-loss orders placed", inline=False)
            else:
                error_msg = "❌ Failed to place one or more stop orders"
                embed.add_field(name="Stop Orders", value=error_msg, inline=False)
                logger.error(f"Stop order error: TP: {st1.get('msg', 'Unknown')}, SL: {st2.get('msg', 'Unknown')}")
            
            # Update the message with the embed
            await processing_msg.edit(content=None, embed=embed)
            
        except Exception as e:
            logger.error(f"Error in inspect_last_trade: {str(e)}")
            await ctx.send(f"❌ Error retrieving trade data: {str(e)}")

    @commands.command(name="place_full_order")
    async def place_full_order(
        self, 
        ctx, 
        market: Optional[str] = None, 
        side: Optional[str] = None, 
        amount: Optional[str] = None, 
        price_or_type: Optional[str] = None, 
        order_type: str = "limit",
        auto_borrow: bool = False
    ):
        """
        Create a real order on KuCoin with direct parameters
        
        Usage: !realorder <market> <side> <amount> [price_or_type] [order_type] [auto_borrow]
        
        Examples:
        !realorder BTC-USDT buy 0.001 50000         (limit order to buy 0.001 BTC at $50000)
        !realorder BTC-USDT sell 0.001 market       (market order to sell 0.001 BTC)
        !realorder BTC-USDT buy 0.05 2000           (limit order to buy 0.05 BTC at $2000)
        !realorder BTC-USDT sell 0.05 market        (market order to sell 0.05 BTC)
        !realorder BTC-USDT buy 100 market funds    (market order to buy $100 worth of BTC)
        !realorder BTC-USDT sell 0.001 market True  (short sell with auto-borrowing)
        """
        await self.order_commands.handle_full_order(ctx, market, side, amount, price_or_type, order_type, auto_borrow)

async def setup(bot):
    """Add the TradeInspector cog to the bot"""
    await bot.add_cog(TradeInspector(bot))