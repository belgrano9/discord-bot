import discord
from discord.ext import commands
from loguru import logger
import os
from binance.spot import Spot as Client
from typing import Optional
import json
from datetime import datetime
import decimal 


class SimpleBot(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        api_key = os.getenv("BINANCE_API_KEY", "")
        api_secret = os.getenv("BINANCE_API_SECRET", "")
        logger.debug("Both API_KEY and API_SECRET loaded")
        self.client = Client(api_key=api_key, api_secret=api_secret)
        logger.debug("Client initialized")

        logger.info("Simple cog initialized")


    @commands.command(name="balance", aliases=['bal'])
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def balance(self, ctx, symbol: Optional[str] = None):
        """
        Displays your margin account balance summary.
        
        Parameters:
        margin_type: Type of margin account ("isolated" or "cross") [default: isolated]
        symbol: Trading pair symbol for isolated margin (e.g., BTCUSDT) [optional]
        
        Examples:
        !balance           - Show isolated margin accounts
        !balance BTCUSDT - Show specific isolated margin account
        """
        logger.debug(f"Balance command invoked by {ctx.author} with type=isIsolated, symbol={symbol}")
        response = self.client.isolated_margin_account() 
        
        logger.debug(response)

        # Find the assets in the response
        assets = None
        if "assets" in response:
            assets = response["assets"]
        elif "data" in response and "assets" in response["data"]:
            assets = response["data"]["assets"]
        
        if not assets:
            await ctx.send("Error: Could not find account data in the response")
            return
        
        # Get summary totals
        data_root = response["data"] if "data" in response else response
        total_asset = data_root.get("totalAssetOfBtc", "0")
        total_liability = data_root.get("totalLiabilityOfBtc", "0")
        total_net_asset = data_root.get("totalNetAssetOfBtc", "0")
        
        await ctx.send(f"Account Summary:\n"
                      f"Total Asset (BTC): {total_asset}\n"
                      f"Total Liability (BTC): {total_liability}\n"
                      f"Total Net Asset (BTC): {total_net_asset}\n"
                      f"Number of margin positions: {len(assets)}")
        logger.info(f"Show balance command completed for {ctx.author}")


    ######################## Query orders: Open, Cancel All &  Close All ########################

    @commands.command(name="openorders", aliases=['oo', 'open']) # Added aliases
    @commands.cooldown(1, 5, commands.BucketType.user) # Cooldown: 1 use per 5 sec per user
    async def open_orders(self, ctx, symbol: Optional[str] = "BTCUSDC"):
        """
        Displays your currently open Binance Margin orders.

        Optionally filters by symbol (e.g., !openorders BTCUSDT).
        Requires the 'Trading-Authorized' role.
        """
        logger.debug(f"Open orders command invoked by {ctx.author} for symbol: {symbol}")
        # Convert symbol to uppercase if provided before passing
        symbol_upper = symbol.upper() #if symbol else None
        await ctx.send(self.client.margin_open_orders(symbol = symbol_upper, isIsolated = True))
        logger.info(f"Display all open orders command completed for {ctx.author}")


    @commands.command(name="cancel")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def cancel_a_order(self, ctx, symbol: str = "BTCUSDC"):
        """
        TODO

        using:

        self.client.cancel_margin_order()
        """
        return None
    
    @commands.command(name="canceloco")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def cancel_a_order(self, ctx, symbol: str = "BTCUSDC"):
        """
        TODO

        using:

        self.cancel_margin_oco_order()
        """
        return None



    @commands.command(name="cancelall", aliases=['canall', 'call'])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def cancel_all_orders(self, ctx, symbol: str = "BTCUSDC"):
        """
        Cancel all open margin orders for a specific symbol.
        
        Parameters:
        symbol: Trading pair (e.g., BTCUSDC)
        
        Example:
        !cancelall BTCUSDC
        !cancelall BTCUSDC 
        """
        logger.info(f"[CANCELALL] Command invoked by {ctx.author} for symbol: {symbol}")
        
        
        symbol_upper = symbol.upper() 
        response = self.client.margin_open_orders_cancellation(symbol=symbol_upper, isIsolated=True)
        logger.info(f"Cancel all open orders command completed for {ctx.author}")
        logger.debug(response)
        await ctx.send(f"Cancelled all open orders for {symbol_upper}. Response: {response}")




    ######################## Place Orders: Open & Close + OCO ########################
    @commands.has_role("Trading-Authorized") 
    @commands.command(name="order", aliases=["marketorder", "mo"]) 
    @commands.cooldown(1, 5, commands.BucketType.user) 
    async def add_margin_order_btcusdc(self, ctx, side: str, quantity: float, side_effect_type: str = "NO_SIDE_EFFECT"):
        """
        Places a new BTCUSDC isolated margin MARKET order.

        Parameters:
        side:             BUY or SELL
        quantity:         Amount of BTC
        side_effect_type: NO_SIDE_EFFECT, MARGIN_BUY, AUTO_REPAY, AUTO_BORROW_REPAY [default: AUTO_BORROW_REPAY]

        Examples:
        !order BUY 0.01
        !mo SELL 0.005
        !order BUY 0.001 AUTO_BORROW_REPAY
        """
        fixed_symbol = "BTCUSDC" # Hardcoded symbol
        command_name = f"{fixed_symbol} Market Order" # For logging/embeds
        logger.info(f"[{command_name}] Command invoked by {ctx.author}: Side={side}, Qty={quantity}, SideEffect={side_effect_type}")

        # --- Input Validation ---
        side_upper = side.upper()
        side_effect_upper = side_effect_type.upper()


        # --- Prepare API Parameters ---
        params = {
            "symbol": fixed_symbol, # Use the hardcoded symbol
            "side": side_upper,
            "type": "MARKET", # Hardcoded as MARKET
            "quantity": str(quantity), # Send quantity as a string
            "isIsolated": "TRUE", # Crucial for isolated margin
            "sideEffectType": side_effect_upper # Use the validated user input or default
        }

        logger.debug(f"[{command_name}] Prepared order params for {ctx.author}: {params}")
        

        # --- Place Order ---
        try:
            order = self.client.new_margin_order(**params)
            logger.info(f"[{command_name}] Placed margin order: {order}")
            await ctx.send(f"✅ Margin order placed successfully! ID: {order['orderId']}, Symbol: {order['symbol']}, Quantity: {order['fills'][0]['qty']}")
        except Exception as e:
            logger.error(f"[{command_name}] Error placing margin order: {e}")
            await ctx.send("❌ Failed to place margin order. Please try again later.")


    @commands.has_role("Trading-Authorized")  
    @commands.command(name="ocoorder", aliases=["oco"])  
    @commands.cooldown(1, 5, commands.BucketType.user)  
    async def add_oco_order_btcusdc(self, ctx, side: str, quantity: float, price: float, stop_price: float, side_effect_type: str = "NO_SIDE_EFFECT"):
        """
        Places a new BTCUSDC OCO isolated margin order.

        Parameters:
        side:             BUY or SELL
        quantity:         Amount of BTC
        price:            Limit price (target price for taking profit)
        stop_price:       Stop trigger price (where stop order activates)
        stop_limit_price: Optional price for the stop-limit order (defaults to stop_price if not provided)
        side_effect_type: NO_SIDE_EFFECT, MARGIN_BUY, AUTO_REPAY, AUTO_BORROW_REPAY [default: NO_SIDE_EFFECT]

        Examples:
        !oco BUY 0.0001 50000 90000  # For buying: limit price < stop price
        !ocoorder SELL 0.0005 90000 50000 AUTO_BORROW_REPAY  # For selling: limit price > stop price
        """
        fixed_symbol = "BTCUSDC"  # Hardcoded symbol
        command_name = f"{fixed_symbol} OCO Order"  # For logging/embeds
        
                
        logger.info(f"[{command_name}] Command invoked by {ctx.author}: Side={side}, Qty={quantity}, Price={price}, StopPrice={stop_price}, SideEffect={side_effect_type}")

        # --- Input Validation ---
        side_upper = side.upper()
        side_effect_upper = side_effect_type.upper()
        
        # Validate price relationships
        if side_upper == "BUY" and price >= stop_price:
            await ctx.send("❌ For BUY orders, limit price must be lower than stop price.")
            return
        elif side_upper == "SELL" and price <= stop_price:
            await ctx.send("❌ For SELL orders, limit price must be higher than stop price.")
            return

        # Create unique client order IDs
        import uuid
        limit_client_order_id = f"limit_{str(uuid.uuid4())[:13]}"
        stop_client_order_id = f"stop_{str(uuid.uuid4())[:13]}"

        params = {
            "symbol": fixed_symbol,
            "side": side_upper,
            "quantity": str(quantity),
            "price": str(price),                  # Limit price
            "stopPrice": str(stop_price),         # Stop trigger price
            "listClientOrderId": f"oco_{str(uuid.uuid4())[:13]}",  # Main OCO order ID
            "limitClientOrderId": limit_client_order_id,
            "stopClientOrderId": stop_client_order_id,
            "isIsolated": "TRUE",                 # Crucial for isolated margin
            "sideEffectType": side_effect_upper
        }

        logger.debug(f"[{command_name}] Prepared OCO order params for {ctx.author}: {params}")

        # --- Place Order ---
        try:
            order = self.client.new_margin_oco_order(**params)
            logger.info(f"[{command_name}] Placed OCO margin order: {order}")
            
            # Format response based on OCO response
            order_ids = [str(order.get('orderListId', 'N/A'))]
            for o in order.get('orderReports', []):
                order_ids.append(str(o.get('orderId', 'N/A')))
            
            await ctx.send(f"✅ OCO margin order placed successfully! List ID: {order_ids[0]}, Orders: {', '.join(order_ids[1:])}, Symbol: {fixed_symbol}, Quantity: {quantity}")
        except Exception as e:
            logger.error(f"[{command_name}] Error placing OCO margin order: {e}")
            await ctx.send(f"❌ Failed to place OCO margin order: {str(e)}")
   
        
        
        
    

    ######################## Place full position: Open + OCO ########################
    #copied and adapted from TradeInspector.py

    @commands.has_role("Trading-Authorized")  
    @commands.command(name="fullpos", aliases=["fp"])
    async def full_position_command(
        self, 
        ctx, 
        side: str, 
        amount: str, 
        rr: float = 1.5,
        side_effect_type: str = "NO_SIDE_EFFECT"
    ):
        """
        Create a full position with market entry and OCO exit orders
        
        Parameters:
        side: buy or sell
        amount: Amount to trade
        auto_borrow: Whether to enable auto-borrowing (optional, default: True)
        rr: Risk/reward ratio (optional, default: 1.5)
        
        Examples:
        !fullpos buy 0.001         (default 1.5 R:R ratio)
        !fullpos sell 0.01 2.0 AUTO_BORROW_REPAY(2.0 R:R ratio)
        """
        await self.full_position(ctx, side, amount, rr, side_effect_type)
        



    async def full_position(self, ctx, side: str = "buy", amount: str = "0.001", rr: Optional[float] = 1.5, side_effect_type: str = "NO_SIDE_EFFECT"):
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
            side_effect_type: NO_SIDE_EFFECT, MARGIN_BUY, AUTO_REPAY, AUTO_BORROW_REPAY [default: NO_SIDE_EFFECT]
        """
        symbol = "BTCUSDC"
        command_name = "full_position"
        try:
            logger.info(f"Starting full position for {symbol}, side: {side}, amount: {amount}")
        
            # Show processing message
            processing_msg = await ctx.send(f"⏳ Creating full position for {symbol}...")
            
            params = {
                "symbol": symbol.upper(), # Use the hardcoded symbol
                "side": side.upper(),
                "type": "MARKET", # Hardcoded as MARKET
                "quantity":float(amount),
                "isIsolated": "TRUE", # Crucial for isolated margin
                "sideEffectType": side_effect_type.upper() # Use the validated user input or default
            }

            logger.debug(f"[{command_name}] Prepared order params for {ctx.author}: {params}")
        
            market_order_response = self.client.new_margin_order(**params)
            logger.info(f"[{command_name}] Placed margin order: {market_order_response}")
                       
            # Extract order data from the response
            logger.debug(market_order_response)
            # Get executed price and quantity from the fills
            fills = market_order_response.get("fills", [])
            if not fills:
                await processing_msg.edit(content="❌ No fill information in market order response")
                return
            
            # Calculate weighted average price if multiple fills
            executed_qty = float(market_order_response.get("executedQty", 0))
            executed_quote_qty = float(market_order_response.get("cummulativeQuoteQty", 0))
            executed_price = executed_quote_qty / executed_qty if executed_qty > 0 else 0
            
            #logger.info(type(executed_qty), type(executed_quote_qty), type(executed_price))

            # Map direction based on side (1 for buy, -1 for sell)
            d = {"buy": 1, "sell": -1}
            direction = d.get(side.lower(), 0)

            # Step 2: Calculate TP and SL levels using the provided formula
            logger.info(f"[{command_name}] Computing TP and SL levels...")

            # Fees and Risk
            #m = 10  # You can adjust this or make it a parameter
            f0 = 0.001  # Fee for market entry
            ft = 0.001  # Fee for OCO exit
            risk = 0.01  # Risk amount
            rr = float(rr)  # Risk/reward ratio
            
            # Calculate take profit and stop loss prices
            tp = (risk * executed_price * rr + executed_price * (f0 + direction)) / (direction - ft)
            sl = (risk * executed_price - executed_price * (f0 + direction)) / (ft - direction)

            tp = round(tp, 2)
            sl = round(sl, 2)

            gained_value = direction * executed_qty * (tp - executed_price) - executed_qty * executed_price * f0 - executed_qty * tp * ft
            lost_value = direction * executed_qty * (sl - executed_price) - executed_qty * executed_price * f0 - executed_qty * sl * ft
            real_rr = round(- gained_value / lost_value, 3)
            no_fees_rr = round((tp - executed_price) / (executed_price-sl), 3)

            logger.info(f"Calculated TP: {tp}, SL: {sl} for {symbol} position")
            logger.info(f"Potential gains: {gained_value}\t - \t Potential losses: {lost_value}")
            logger.info(f"Real RR: {real_rr} (without fees: {no_fees_rr})")

            if real_rr != rr:
                logger.error("RR doesn't match! Check formulas.")
            
            # Step 3: Create OCO order
            opposite_side = "sell" if side.lower() == "buy" else "buy"
            
            import uuid
            limit_client_order_id = f"limit_{str(uuid.uuid4())[:13]}"
            stop_client_order_id = f"stop_{str(uuid.uuid4())[:13]}"

            params = {
                "symbol": symbol.upper(),
                "side": opposite_side.upper(),
                "quantity": str(executed_qty),
                "price": str(tp),                  # Limit price
                "stopPrice": str(sl),         # Stop trigger price
                "listClientOrderId": f"oco_{str(uuid.uuid4())[:13]}",  # Main OCO order ID
                "limitClientOrderId": limit_client_order_id,
                "stopClientOrderId": stop_client_order_id,
                "isIsolated": "TRUE",                 # Crucial for isolated margin
                "sideEffectType": side_effect_type.upper()
            }

            logger.debug(f"[{command_name}] Prepared OCO order params for {ctx.author}: {params}")

            # --- Place Order ---
            
            oco_order = self.client.new_margin_oco_order(**params)
            logger.info(f"[{command_name}] Placed OCO margin order: {oco_order}")


            if oco_order.get("error", False):
                await processing_msg.edit(content=f"❌ Market order placed but OCO order failed: {oco_order.get('msg', 'Unknown error')}")
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
            embed.add_field(name="Risk/Reward", value=f"{real_rr} (Theory: {rr})", inline=True)

            market_order_id = str(market_order_response.get('orderId', 'Unknown'))
            embed.add_field(
                name="Market Order ID", 
                value=f"`{market_order_id}`", 
                inline=False
            )

            embed.set_footer(text=f"Requested by {ctx.author.display_name}", icon_url=ctx.author.avatar.url if ctx.author.avatar else None)
            logger.info(f"Successfully opened and formatted full position for {ctx.author} using service.")
            # Update the processing message with the completed embed
            await processing_msg.edit(content=None, embed=embed)


        except Exception as e:
            logger.error(f"Error in full_position: {str(e)}")
            await ctx.send(f"❌ Error creating full position: {str(e)}")







    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        """Handle reactions on messages"""
        await self.reaction_handler.handle_reaction(reaction, user)


async def setup(bot):
    """Add the TradingCommands cog to the bot"""
    await bot.add_cog(SimpleBot(bot))
    
        
