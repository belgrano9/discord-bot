import discord
from discord.ext import commands
from loguru import logger
import os
from binance.spot import Spot as Client
from typing import Optional
from datetime import datetime
import re
from datetime import datetime, timedelta
import asyncio



class SimpleBot(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        api_key = os.getenv("BINANCE_API_KEY", "")
        api_secret = os.getenv("BINANCE_API_SECRET", "")
        logger.debug("Both API_KEY and API_SECRET loaded")
        self.client = Client(api_key=api_key, api_secret=api_secret)
        logger.debug("Client initialized")

                # Add after existing attributes in __init__
        self.pending_signals = {}  # Store pending approvals
        self.APPROVAL_TIMEOUT = 60  # minutes
        logger.info("Simple cog initialized")





    @commands.command(name="balance", aliases=['bal'])
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def balance(self, ctx):
        """
        Displays your BTCUSDC isolated margin account balance.
        
        Examples:
        !balance - Show BTCUSDC isolated margin account details
        """
        logger.info(f"Balance command invoked by {ctx.author}")
        
        # Send a temporary message to indicate processing
        temp_msg = await ctx.send("Fetching margin account data...")
        
        try:
            response = self.client.isolated_margin_account() 
            logger.debug(f"Margin account response: {response}")

            # Find the assets in the response
            assets = None
            if "assets" in response:
                assets = response["assets"]
            elif "data" in response and "assets" in response["data"]:
                assets = response["data"]["assets"]
            
            if not assets:
                await temp_msg.edit(content="Error: Could not find account data in the response")
                return
            
            # Filter for BTCUSDC only
            btc_assets = [asset for asset in assets if asset.get("symbol") == "BTCUSDC"]
            
            if not btc_assets:
                await temp_msg.edit(content="No BTCUSDC isolated margin account found.")
                return
                
            # We'll work with the first (and only) BTCUSDC asset
            btc_asset = btc_assets[0]
            
            # Get account summary totals
            data_root = response["data"] if "data" in response else response
            total_asset_btc = float(data_root.get("totalAssetOfBtc", "0"))
            total_liability_btc = float(data_root.get("totalLiabilityOfBtc", "0"))
            total_net_asset_btc = float(data_root.get("totalNetAssetOfBtc", "0"))
            
            # Get BTC price
            btc_price = float(btc_asset.get("indexPrice", 0))
            
            # Determine color based on margin level
            margin_level = btc_asset.get("marginLevel", "999")
            if margin_level == "999":  # Infinite margin level (no borrowing)
                color = discord.Color.green()
            else:
                margin_level_float = float(margin_level)
                if margin_level_float > 3:
                    color = discord.Color.green()
                elif margin_level_float > 1.5:
                    color = discord.Color.gold()
                else:
                    color = discord.Color.red()
            
            # Create embed for balance information
            embed = discord.Embed(
                title="BTCUSDC Isolated Margin Account",
                description="Your current BTCUSDC margin position details",
                color=color,
                timestamp=datetime.now()
            )
            
            # Get asset details
            base_asset = btc_asset.get("baseAsset", {})
            quote_asset = btc_asset.get("quoteAsset", {})
            
            # Base asset (BTC)
            base_free = float(base_asset.get("free", 0))
            base_locked = float(base_asset.get("locked", 0))
            base_borrowed = float(base_asset.get("borrowed", 0))
            base_total = float(base_asset.get("totalAsset", 0))
            base_net = float(base_asset.get("netAsset", 0))
            
            # Quote asset (USDC)
            quote_free = float(quote_asset.get("free", 0))
            quote_locked = float(quote_asset.get("locked", 0))
            quote_borrowed = float(quote_asset.get("borrowed", 0))
            quote_total = float(quote_asset.get("totalAsset", 0))
            quote_net = float(quote_asset.get("netAsset", 0))
            
            # Calculate USD value
            btc_usd_value = base_total * btc_price
            total_usd_value = btc_usd_value + quote_total
            
            # Add BTC information
            embed.add_field(
                name="Bitcoin (BTC)",
                value=(
                    f"**Free:** {base_free:.8f} BTC\n"
                    f"**Locked:** {base_locked:.8f} BTC\n"
                    f"**Borrowed:** {base_borrowed:.8f} BTC\n"
                    f"**Total:** {base_total:.8f} BTC\n"
                    f"**Value:** ${btc_usd_value:.2f}"
                ),
                inline=True
            )
            
            # Add USDC information
            embed.add_field(
                name="USD Coin (USDC)",
                value=(
                    f"**Free:** ${quote_free:.2f}\n"
                    f"**Locked:** ${quote_locked:.2f}\n"
                    f"**Borrowed:** ${quote_borrowed:.2f}\n"
                    f"**Total:** ${quote_total:.2f}"
                ),
                inline=True
            )
            
            # Add position information
            # Format margin level for display
            margin_level_display = "∞" if margin_level == "999" else f"{float(margin_level):.2f}×"
            
            embed.add_field(
                name="Position Details",
                value=(
                    f"**Current BTC Price:** ${btc_price:.2f}\n"
                    f"**Total Position Value:** ${total_usd_value:.2f}\n"
                    f"**Margin Level:** {margin_level_display}\n"
                    f"**Margin Status:** {btc_asset.get('marginLevelStatus', 'Unknown')}"
                ),
                inline=False
            )
            
            # Add account summary
            total_usd_value_all = total_net_asset_btc * btc_price
            
            embed.add_field(
                name="Account Summary",
                value=(
                    f"**Total Assets:** {total_asset_btc:.8f} BTC (${total_asset_btc * btc_price:.2f})\n"
                    f"**Total Liabilities:** {total_liability_btc:.8f} BTC (${total_liability_btc * btc_price:.2f})\n"
                    f"**Net Value:** {total_net_asset_btc:.8f} BTC (${total_usd_value_all:.2f})"
                ),
                inline=False
            )
            
            # Add footer with user avatar
            embed.set_footer(
                text=f"Requested by {ctx.author.display_name}", 
                icon_url=ctx.author.avatar.url if ctx.author.avatar else None
            )
            
            # Send the embed and delete the temporary message
            await temp_msg.delete()
            await ctx.send(embed=embed)
            logger.info(f"Balance command completed for {ctx.author}")
            
        except Exception as e:
            logger.error(f"Error in balance command: {str(e)}")
            await temp_msg.edit(content=f"Error fetching margin account data: {str(e)}")
    
    ############### CHECK MINIMUM ###########
    @commands.command(name="checkminimums")
    async def check_minimums(self, ctx):
        btc_info = self.client.exchange_info(symbol="BTCUSDC")
        eth_info = self.client.exchange_info(symbol="ETHUSDC")
        
        for symbol, info in [("BTCUSDC", btc_info), ("ETHUSDC", eth_info)]:
            lot_size = next(f for f in info['symbols'][0]['filters'] if f['filterType'] == 'LOT_SIZE')
            await ctx.send(f"{symbol}: minQty={lot_size['minQty']}, stepSize={lot_size['stepSize']}")



    ######################## Query orders: Open, Cancel All &  Close All ########################

    @commands.command(name="openorders", aliases=['oo', 'open'])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def open_orders(self, ctx, symbol: Optional[str] = "BTCUSDC"):
        """
        Displays your currently open Binance Margin orders.

        Optionally filters by symbol (e.g., !openorders BTCUSDT).
        Requires the 'Trading-Authorized' role.
        """
        logger.debug(f"Open orders command invoked by {ctx.author} for symbol: {symbol}")
        
        # Convert symbol to uppercase
        symbol_upper = symbol.upper()
        
        # Get open orders from Binance
        try:
            orders = self.client.margin_open_orders(symbol=symbol_upper, isIsolated=True)
            logger.debug(f"Retrieved {len(orders)} open orders for {symbol_upper}")
            
            if not orders:
                await ctx.send(f"No open orders found for {symbol_upper}.")
                return
                
            # Create an embed for the order summary
            embed = discord.Embed(
                title=f"Open Orders for {symbol_upper}",
                description=f"Found {len(orders)} active orders",
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )
            
            # Group orders by type for better organization
            order_types = {}
            for order in orders:
                order_type = order.get('type', 'UNKNOWN')
                if order_type not in order_types:
                    order_types[order_type] = []
                order_types[order_type].append(order)
            
            # Add each order group to the embed
            for order_type, type_orders in order_types.items():
                # Create a formatted string for all orders of this type
                orders_text = ""
                for i, order in enumerate(type_orders):
                    # Format price with proper precision
                    price = order.get('price', '0')
                    if float(price) == 0 and 'stopPrice' in order:
                        price = order.get('stopPrice', '0')  # Use stop price for STOP orders
                    
                    try:
                        price_float = float(price)
                        price_formatted = f"${price_float:.2f}"
                    except (ValueError, TypeError):
                        price_formatted = price
                    
                    # Format time to be readable
                    timestamp = order.get('time', 0)
                    time_str = datetime.fromtimestamp(timestamp / 1000).strftime('%Y-%m-%d %H:%M:%S') if timestamp else 'Unknown'
                    
                    # Create a concise order summary
                    side = order.get('side', 'UNKNOWN')
                    qty = order.get('origQty', '0')
                    status = order.get('status', 'UNKNOWN')
                    
                    # Add emoji based on side
                    emoji = "🟢" if side == "BUY" else "🔴" if side == "SELL" else "⚪"
                    
                    orders_text += f"{emoji} **{side}** {qty} @ {price_formatted}\n"
                    orders_text += f"   ID: `{order.get('orderId', 'N/A')}` • Status: {status} • Time: {time_str}\n\n"
                
                # Add this order type as a field in the embed
                embed.add_field(
                    name=f"📊 {order_type} Orders ({len(type_orders)})",
                    value=orders_text if orders_text else "None",
                    inline=False
                )
            
            embed.set_footer(
                text=f"Requested by {ctx.author.display_name}", 
                icon_url=ctx.author.avatar.url if ctx.author.avatar else None
            )
            
            await ctx.send(embed=embed)
            logger.info(f"Display all open orders command completed for {ctx.author}")
            
        except Exception as e:
            logger.error(f"Error retrieving open orders: {str(e)}")
            await ctx.send(f"❌ Error retrieving open orders: {str(e)}")


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
        await ctx.send(f"✅ Cancelled all open orders for {symbol_upper}. Response: {response}")




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
    async def on_message(self, message):
        # Debug every message to see the actual author details
        print(f"Message from: '{message.author.name}' (ID: {message.author.id}, Bot: {message.author.bot})")
        
        if "TRADING SIGNAL APPROVAL NEEDED" in message.content:
            print(f"Found signal message from: {message.author.name}")
            await self.handle_signal_approval(message)


    async def handle_signal_approval(self, message):
        """Parse signal and add reactions"""
        print(f"FULL MESSAGE CONTENT:\\n{repr(message.content)}")  # Add this line
        signal_data = self.parse_signal_message(message.content)
        print(f"Parsed signal_data: {signal_data}")  # Debug
        
        if signal_data:
            self.pending_signals[signal_data['signal_id']] = {
                'data': signal_data,
                'message_id': message.id,
                'channel_id': message.channel.id,
                'expires_at': datetime.now() + timedelta(minutes=self.APPROVAL_TIMEOUT)
            }
            await message.add_reaction('✅')
            await message.add_reaction('❌')
            print(f"Signal stored: {signal_data['signal_id']}")  # Debug

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        if user.bot:
            return
        await self.handle_signal_reaction(reaction, user)

    async def handle_signal_reaction(self, reaction, user):
        message_id = reaction.message.id
        
        signal_entry = None
        signal_id = None
        for sid, data in self.pending_signals.items():
            if data['message_id'] == message_id:
                signal_entry = data
                signal_id = sid
                break
        
        if not signal_entry or datetime.now() > signal_entry['expires_at']:
            return
        
        if reaction.emoji == '✅':
            await self.execute_signal(signal_entry['data'], reaction.message.channel)
            del self.pending_signals[signal_id]
        elif reaction.emoji == '❌':
            await reaction.message.channel.send(f"❌ Signal {signal_id} rejected")
            del self.pending_signals[signal_id]

    
    def parse_signal_message(self, content: str) -> Optional[dict]:
        """Parse signal using Pydantic model"""
        from models import TradingSignalApproval
        signal = TradingSignalApproval.from_discord_message(content)
        if signal:
            return signal.model_dump()
        return None

    @commands.command(name="pending")
    async def show_pending_signals(self, ctx):
        """Show all pending signals"""
        if not self.pending_signals:
            await ctx.send("No pending signals")
            return
        
        for signal_id, data in self.pending_signals.items():
            expires_str = data['expires_at'].strftime('%H:%M:%S')
            await ctx.send(f"Signal: `{signal_id}` expires at {expires_str}")

    ################## after reacting ###################
    async def execute_signal(self, signal_data, channel):
        """Execute real pairs trading instead of mock"""
        try:
            # Replace mock with real execution
            await self.execute_pairs_trade(signal_data, channel)
        except Exception as e:
            logger.error(f"Pairs trade execution failed: {e}")
            await channel.send(f"❌ Execution failed: {str(e)}")

    ################## REAL EXECUITON #################

    def spread_to_prices(self, target_spread, stop_spread, asset, beta):
        """Convert spread levels to individual asset prices"""
        # Placeholder - needs your spread calculation formula
        # Depends on how spread is defined (log? arithmetic?)
        pass

    async def execute_pairs_trade(self, signal_data, channel):
        """Execute actual pairs trading strategy"""
        
        # Step 1: Get account balance
        account_info = self.client.isolated_margin_account()
        total_capital = self.extract_total_capital(account_info)  
        
        # Step 2: Calculate positions
        positions = self.calculate_pair_positions(signal_data, total_capital)
        logger.debug(f"Calculated positions: {positions}")

        # Step 3: Place both limit orders simultaneously
        btc_result, eth_result = await asyncio.gather(
        self.place_pairs_limit_order(positions["btc"]),
        self.place_pairs_limit_order(positions["eth"]),
        return_exceptions=True
        )
        
        # Check results
        if isinstance(btc_result, Exception):
            await channel.send(f"BTC order failed: {btc_result}")
        else:
            await channel.send(f"BTC order placed: {btc_result.get('orderId', 'Unknown')}")
            
        if isinstance(eth_result, Exception):
            await channel.send(f"ETH order failed: {eth_result}")
        else:
            await channel.send(f"ETH order placed: {eth_result.get('orderId', 'Unknown')}")

    async def place_pairs_limit_order(self, position_data):
        """Place limit order for one leg of the pair"""
        try:
            params = {
                "symbol": position_data["symbol"],
                "side": position_data["side"],
                "type": "LIMIT",
                "quantity": str(position_data["size"]),
                "price": str(position_data["entry_price"]),
                "isIsolated": "TRUE",
                "sideEffectType": "AUTO_BORROW_REPAY",
                "timeInForce": "GTC"
            }
            
            order = self.client.new_margin_order(**params)
            logger.info(f"Placed {position_data['side']} order for {position_data['symbol']}: {order['orderId']}")
            return order
            
        except Exception as e:
            logger.error(f"Failed to place order for {position_data['symbol']}: {e}")
            raise

    def extract_total_capital(self, account_info):
        """Extract total USD value from isolated margin account"""
        assets = account_info.get("assets", [])
        for asset in assets:
            if asset.get("symbol") == "BTCUSDC":
                btc_asset = asset.get("baseAsset", {})
                usdc_asset = asset.get("quoteAsset", {})
                btc_price = float(asset.get("indexPrice", 108000))
                
                btc_total = float(btc_asset.get("totalAsset", 0))
                usdc_total = float(usdc_asset.get("totalAsset", 0))
                
                return (btc_total * btc_price) + usdc_total
        return 0

    async def monitor_pairs_execution(self, btc_order, eth_order, signal_data, channel):
        """Monitor fills and handle partial execution"""
        
        # Wait 5 seconds for initial fills
        await asyncio.sleep(5)
        
        # Check order status
        btc_status = self.client.query_margin_order(
            symbol="BTCUSDC", 
            orderId=btc_order['orderId'],
            isIsolated=True
        )
        
        eth_status = self.client.query_margin_order(
            symbol="ETHUSDC",
            orderId=eth_order['orderId'], 
            isIsolated=True
        )
        
        btc_filled = btc_status['status'] == 'FILLED'
        eth_filled = eth_status['status'] == 'FILLED'
        
        if btc_filled and eth_filled:
            # Both filled - set up OCO orders
            await channel.send("✅ Both legs filled. Setting up OCO orders...")
            # Placeholder for OCO setup
            await self.setup_pairs_oco(btc_order, eth_order, signal_data)
            
        elif btc_filled or eth_filled:
            # Only one filled - emergency exit
            await channel.send("⚠️ Only one leg filled. Executing emergency exit...")
            await self.emergency_exit_single_leg(
                btc_order if btc_filled else None,
                eth_order if eth_filled else None,
                channel
            )
        else:
            # Neither filled - cancel both
            await channel.send("⏰ Orders not filled. Cancelling...")
            self.client.cancel_margin_order(symbol="BTCUSDC", orderId=btc_order['orderId'], isIsolated=True)
            self.client.cancel_margin_order(symbol="ETHUSDC", orderId=eth_order['orderId'], isIsolated=True)

    async def emergency_exit_single_leg(self, filled_order, unfilled_order, channel):
        """Close the filled position immediately"""
        if filled_order:
            symbol = "BTCUSDC" if "BTC" in str(filled_order) else "ETHUSDC"
            
            # Reverse the position with market order
            original_side = filled_order['side']
            reverse_side = "SELL" if original_side == "BUY" else "BUY"
            
            params = {
                "symbol": symbol,
                "side": reverse_side,
                "type": "MARKET",
                "quantity": filled_order['executedQty'],
                "isIsolated": "TRUE",
                "sideEffectType": "AUTO_BORROW_REPAY"
            }
            
            self.client.new_margin_order(**params)
            await channel.send(f"🔄 Reversed {symbol} position")
        
        # Cancel the unfilled order
        if unfilled_order:
            symbol = "BTCUSDC" if "BTC" in str(unfilled_order) else "ETHUSDC"
            self.client.cancel_margin_order(
                symbol=symbol,
                orderId=unfilled_order['orderId'],
                isIsolated=True
            )

    async def setup_pairs_oco(self, btc_order, eth_order, signal_data):
        """Set up OCO orders for pairs trade based on spread levels"""
        
        # Extract spread parameters
        entry_spread = signal_data['spread']
        threshold = signal_data['threshold']
        mu = signal_data['mu']
        action = signal_data['action']
        
        # Calculate spread-based TP/SL levels
        # For LONG spread: profit when spread decreases, loss when increases
        # For SHORT spread: opposite
        
        if action == "LONG":
            # Target: spread returns toward mean
            target_spread = entry_spread - (threshold * 0.5)  # 50% mean reversion
            stop_spread = entry_spread + (threshold * 1.5)    # 150% further divergence
        else:  # SHORT
            target_spread = entry_spread + (threshold * 0.5)
            stop_spread = entry_spread - (threshold * 1.5)
        
        # Convert spread levels back to individual asset prices
        # This requires solving: spread = btc_price - beta * eth_price
        btc_filled_price = float(btc_order['fills'][0]['price'])
        eth_filled_price = float(eth_order['fills'][0]['price'])
        beta = signal_data['beta']
        
        # Calculate individual TP/SL prices maintaining the hedge ratio
        # Placeholder for complex calculation - depends on spread definition
        btc_tp, btc_sl = self.spread_to_prices(target_spread, stop_spread, "BTC", beta)
        eth_tp, eth_sl = self.spread_to_prices(target_spread, stop_spread, "ETH", beta)
        
        # Place OCO for BTC
        btc_oco_params = {
            "symbol": "BTCUSDC",
            "side": "SELL" if btc_order['side'] == "BUY" else "BUY",
            "quantity": btc_order['executedQty'],
            "price": str(btc_tp),
            "stopPrice": str(btc_sl),
            "isIsolated": "TRUE",
            "sideEffectType": "AUTO_BORROW_REPAY"
        }
        
        # Place OCO for ETH
        eth_oco_params = {
            "symbol": "ETHUSDC", 
            "side": "SELL" if eth_order['side'] == "BUY" else "BUY",
            "quantity": eth_order['executedQty'],
            "price": str(eth_tp),
            "stopPrice": str(eth_sl),
            "isIsolated": "TRUE",
            "sideEffectType": "AUTO_BORROW_REPAY"
        }
        
        btc_oco = self.client.new_margin_oco_order(**btc_oco_params)
        eth_oco = self.client.new_margin_oco_order(**eth_oco_params)
        
        logger.info(f"OCO orders placed for spread TP: {target_spread}, SL: {stop_spread}")
    
    def calculate_pair_positions(self, signal_data: dict, total_capital: float , capital_allocation:float = 0.10) -> dict:
        """
        Calculate position sizes for pairs trading based on beta hedge ratio

        For LONG spread: Buy BTC, Sell ETH
        For SHORT spread: Sell BTC, Buy ETH
        """
        # Extract parameters
        beta = signal_data['beta']
        btc_price = signal_data['btc_price'] 
        eth_price = signal_data['eth_price']
        action = signal_data['action']  # LONG or SHORT

        # 10% capital allocation
        allocated_capital = total_capital * capital_allocation

        # Calculate dollar allocation for each leg
        # Total = btc_allocation + eth_allocation
        # eth_allocation = beta * btc_allocation (in dollar terms)
        # So: allocated_capital = btc_allocation * (1 + beta)

        btc_dollar_allocation = allocated_capital / (1 + beta)
        eth_dollar_allocation = beta * btc_dollar_allocation

        # Convert to position sizes
        btc_size = btc_dollar_allocation / btc_price
        eth_size = eth_dollar_allocation / eth_price

        def round_to_step_size(quantity, step_size):
            return round(quantity / step_size) * step_size

        btc_size = round_to_step_size(btc_size, 0.00001)
        eth_size = round_to_step_size(eth_size, 0.0001)

        # Determine sides based on signal
        if action == "LONG":  # Long the spread
            btc_side = "BUY"
            eth_side = "SELL"
        else:  # SHORT spread
            btc_side = "SELL" 
            eth_side = "BUY"

        # In calculate_pair_positions, before return:
        logger.info(f"Calculated BTC size: {btc_size:.8f}, ETH size: {eth_size:.8f}")
        logger.info(f"BTC dollar allocation: ${btc_dollar_allocation:.2f}")
        logger.info(f"ETH dollar allocation: ${eth_dollar_allocation:.2f}")

        return {
            "btc": {
                "symbol": "BTCUSDC",
                "side": btc_side,
                "size": round(btc_size, 8),  # Round to 8 decimals
                "entry_price": btc_price,
                "dollar_value": btc_dollar_allocation
            },
            "eth": {
                "symbol": "ETHUSDC",
                "side": eth_side,
                "size": round(eth_size, 8),
                "entry_price": eth_price,
                "dollar_value": eth_dollar_allocation
            },
            "total_allocated": allocated_capital,
            "hedge_ratio": beta
        }


    @commands.command(name="testpairs")
    async def test_pairs_execution(self, ctx):
        """Test pairs trading with dummy signal"""
        
        # Create test signal with small allocation
        test_signal = {
            "signal_id": "test_001",
            "action": "LONG",
            "pair": "BTCUSDC/ETHUSDC",
            "confidence": 0.5,
            "spread": 0.001499,
            "threshold": 0.000866,
            "beta": 2.3695,
            "mu": -1.341093,
            "btc_price": 108010.0,
            "eth_price": 2702.6,
            "timestamp": datetime.now(),
            "expires_minutes": 60
        }
        
        # Test position calculation
        try:
            account_info = self.client.isolated_margin_account()
            total_capital = self.extract_total_capital(account_info)
            positions = self.calculate_pair_positions(test_signal, total_capital)
            
            await ctx.send(f"""
    **Test Position Calculation:**
    Total Capital: ${total_capital:.2f}
    Allocated (1%): ${positions['total_allocated']:.2f}
    BTC: {positions['btc']['side']} {positions['btc']['size']:.8f} @ ${positions['btc']['entry_price']}
    ETH: {positions['eth']['side']} {positions['eth']['size']:.8f} @ ${positions['eth']['entry_price']}
    Beta: {positions['hedge_ratio']:.4f}
            """)
            
        except Exception as e:
            await ctx.send(f"❌ Test failed: {e}")

    @commands.command(name="testpairslive")
    async def test_pairs_live(self, ctx):
        """Test with real limit orders (small amounts)"""
        
        test_signal = {
            "signal_id": "test_live_001",
            "action": "LONG",
            "pair": "BTCUSDC/ETHUSDC",
            "confidence": 0.5,
            "spread": 0.001499,
            "threshold": 0.000866,
            "beta": 2.3695,
            "mu": -1.341093,
            "btc_price": 108010.0,
            "eth_price": 2702.6,
            "timestamp": datetime.now(),
            "expires_minutes": 60
        }
        
        await ctx.send("⚠️ Placing REAL test orders with 10% allocation...")
        
        try:
            await self.execute_pairs_trade(test_signal, ctx.channel)
        except Exception as e:
            await ctx.send(f"Test failed: {e}")

async def setup(bot):
    """Add the TradingCommands cog to the bot"""
    await bot.add_cog(SimpleBot(bot))
    
        
