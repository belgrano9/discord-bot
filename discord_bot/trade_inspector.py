"""
Trade inspector cog for Discord bot.
Extracts and displays specific trade data from the most recent trade.
"""

import discord
from discord.ext import commands
from typing import Optional
from loguru import logger
from datetime import datetime

from trading.services.kucoin_service import KuCoinService
from trading.interactions.reaction_handler import ReactionHandler
from trading.commands.order_commands import OrderCommands
from trading.commands.account_commands import AccountCommands
from trading.commands.market_commands import MarketCommands
from trading.services.binance_service import BinanceService
from trading.models.order import OrderRequest, OrderSide, OrderType


class TradeInspector(commands.Cog):
    """Discord cog for inspecting recent trade details"""

    def __init__(self, bot):
        """Initialize the trade inspector cog"""
        self.bot = bot
        self.kucoin_service = KuCoinService()
        self.binance_service = BinanceService()

        logger.info("Trade Inspector cog initialized")
        # Initialize components
        self.reaction_handler = ReactionHandler()
        self.order_commands = OrderCommands(self.reaction_handler)
        self.account_commands = AccountCommands(self.binance_service)
        self.market_commands = MarketCommands()

    
    async def full_position(self, ctx, symbol: Optional[str] = None, side: str = "buy", amount: str = "0.001", auto_borrow: bool = True, rr: Optional[float] = 1.5):
        """
        Place a full position consisting of:
        1. A market margin order to open the position
        2. An OCO order for take-profit and stop-loss to manage risk
        
        Args:
            ctx: Discord context
            symbol: Trading pair (e.g., BTCUSDT)
            side: buy or sell
            amount: Amount to trade
            auto_borrow: Whether to enable auto-borrowing (default: True)
        """
        try:
            logger.info(f"Starting full position for {symbol}, side: {side}, amount: {amount}")
        
            # Show processing message
            processing_msg = await ctx.send(f"⏳ Creating full position for {symbol}...")
            
            # Step 1: Create the market order to enter the position using the binance_service            
            # Create order request object
            order_request = OrderRequest(
                symbol=symbol.upper(),
                side=OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL,
                order_type=OrderType.MARKET,
                amount=float(amount),
                price=None,  # Not needed for market order
                use_funds=False,
                auto_borrow=auto_borrow,
                is_isolated=False  # Using cross margin
            )
            
            # Place the market order
            market_order_response = await self.binance_service.place_order(order_request)
            
            if not market_order_response.is_success:
                await processing_msg.edit(content=f"❌ Market order failed: {market_order_response.error_message}")
                return
            
            # Extract order data from the response
            order_data = market_order_response.order_data["data"]
            logger.info(order_data)
            # Get executed price and quantity from the fills
            fills = order_data.get("fills", [])
            if not fills:
                await processing_msg.edit(content="❌ No fill information in market order response")
                return
            
            # Calculate weighted average price if multiple fills
            executed_qty = float(order_data.get("executedQty", 0))
            executed_quote_qty = float(order_data.get("cummulativeQuoteQty", 0))
            executed_price = executed_quote_qty / executed_qty if executed_qty > 0 else 0
            
            # Map direction based on side (1 for buy, -1 for sell)
            d = {"buy": 1, "sell": -1}
            direction = d.get(side.lower(), 0)

            # Step 2: Calculate TP and SL levels using the provided formula
            # Fees and Risk
            m = 10  # You can adjust this or make it a parameter
            f0 = 0.001  # Fee for market entry
            ft = 0.001  # Fee for OCO exit
            risk = 0.01 * m  # Risk amount
            rr = rr  # Risk/reward ratio
            
            # Calculate take profit and stop loss prices
            tp = (risk * rr + executed_qty * executed_price * (f0 + direction)) / (executed_qty * (direction - ft))
            sl = (risk - executed_qty * executed_price * (f0 + direction)) / (executed_qty * (ft - direction))
            
            logger.info(f"Calculated TP: {tp}, SL: {sl} for {symbol} position")

            # Step 3: Create OCO order
            opposite_side = "sell" if side.lower() == "buy" else "buy"
            
            # Place OCO order
            oco_response = await self.binance_service.place_oco_order(
                symbol=symbol.upper(),
                side=opposite_side,
                quantity=executed_qty,
                price=tp,
                stop_price=sl,
                stop_limit_price=None,  # Using market stops
                is_isolated=False,  # Using cross margin
                auto_borrow=auto_borrow
            )
            
            logger.info(oco_response)
            if oco_response.get("error", False):
                await processing_msg.edit(content=f"❌ Market order placed but OCO order failed: {oco_response.get('msg', 'Unknown error')}")
                return

            # Step 4: Send completion message with position details
            embed = discord.Embed(
                title=f"✅ Full Position Created for {symbol}",
                description=f"{side.upper()} position opened with take-profit and stop-loss",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
            
            embed.add_field(name="Entry Price", value=f"${executed_price:.8f}", inline=True)
            embed.add_field(name="Position Size", value=f"{executed_qty:.8f}", inline=True)
            embed.add_field(name="Side", value=f"{side.upper()}", inline=True)
            
            embed.add_field(name="Take Profit", value=f"${tp:.8f}", inline=True)
            embed.add_field(name="Stop Loss", value=f"${sl:.8f}", inline=True)
            embed.add_field(name="Risk/Reward", value=f"{rr:.1f}", inline=True)

            market_order_id = str(order_data.get('orderId', 'Unknown'))
            embed.add_field(
                name="Market Order ID", 
                value=f"`{market_order_id}`", 
                inline=False
            )

            embed.set_footer(text=f"Requested by {ctx.author.display_name} | Today at {datetime.now().strftime('%H:%M')}")

            logger.info("Position opened succesfully!")
            # Update the processing message with the completed embed
            await processing_msg.edit(content=None, embed=embed)


        except Exception as e:
            logger.error(f"Error in full_position: {str(e)}")
            await ctx.send(f"❌ Error creating full position: {str(e)}")

    @commands.command(name="fullpos", aliases=["fp"])
    async def full_position_command(
        self, 
        ctx, 
        market: str, 
        side: str, 
        amount: str, 
        auto_borrow: bool = True,
        rr: float = 1.5
    ):
        """
        Create a full position with market entry and OCO exit orders
        
        Parameters:
        market: Trading pair (e.g., BTCUSDT)
        side: buy or sell
        amount: Amount to trade
        auto_borrow: Whether to enable auto-borrowing (optional, default: True)
        rr: Risk/reward ratio (optional, default: 1.5)
        
        Examples:
        !fullpos BTCUSDT buy 0.001         (default 1.5 R:R ratio)
        !fullpos ETHUSDT sell 0.01 True 2.0  (2.0 R:R ratio)
        """
        # Call the full_position method with all parameters
        await self.full_position(ctx, market, side, amount, auto_borrow, rr)
    

    
    
    
async def setup(bot):
    """Add the TradeInspector cog to the bot"""
    await bot.add_cog(TradeInspector(bot))