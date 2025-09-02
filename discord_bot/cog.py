"""
Cross Margin Trading Bot for Discord
Supports pairs trading across multiple symbols using shared collateral pool
Enhanced with comprehensive logging for production trading operations
"""

import discord
from discord.ext import commands
from loguru import logger
import os
from binance.spot import Spot as Client
from typing import Optional
from datetime import datetime, timedelta
import asyncio
import re
import uuid


class CrossMarginBot(commands.Cog):
    """Discord cog for cross margin trading operations"""
    
    def __init__(self, bot):
        logger.info("Initializing CrossMarginBot cog...")
        self.bot = bot
        api_key = os.getenv("BINANCE_API_KEY", "")
        api_secret = os.getenv("BINANCE_API_SECRET", "")
        
        if not api_key or not api_secret:
            logger.critical("Missing Binance API credentials - bot will not function")
        else:
            logger.debug("API credentials loaded successfully")
            
        self.client = Client(api_key=api_key, api_secret=api_secret)
        logger.debug("Binance client initialized for cross margin trading")

        # Signal approval system
        self.pending_signals = {}
        self.APPROVAL_TIMEOUT = 60  # minutes
        logger.info(f"Signal approval system initialized with {self.APPROVAL_TIMEOUT}min timeout")
        logger.info("Cross margin cog initialization complete")

    # ==================== ACCOUNT COMMANDS ====================

    @commands.command(name="balance", aliases=['bal'])
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def balance(self, ctx):
        """
        Display cross margin account balance (all assets)
        """
        logger.info(f"Balance command invoked by {ctx.author.name} (ID: {ctx.author.id}) in {ctx.guild.name}")
        
        temp_msg = await ctx.send("Fetching cross margin account data...")
        logger.debug("Temporary status message sent, querying Binance API...")
        
        try:
            # Use cross margin endpoint (no isIsolated parameter)
            logger.debug("Making API call to margin_account()")
            response = self.client.margin_account()
            logger.debug(f"API response received successfully - account data retrieved")

            # Extract account data
            margin_level = float(response.get("marginLevel", "999"))
            total_asset_btc = float(response.get("totalAssetOfBtc", "0"))
            total_liability_btc = float(response.get("totalLiabilityOfBtc", "0"))
            total_net_asset_btc = float(response.get("totalNetAssetOfBtc", "0"))
            
            logger.info(f"Account metrics - Margin Level: {margin_level:.2f}×, Net Assets: {total_net_asset_btc:.8f} BTC")
            
            # Determine health color
            if margin_level == 999:  # No borrowing
                color = discord.Color.green()
                health_status = "HEALTHY_NO_DEBT"
            elif margin_level > 3:
                color = discord.Color.green()
                health_status = "HEALTHY"
            elif margin_level > 1.5:
                color = discord.Color.gold()
                health_status = "MODERATE_RISK"
                logger.warning(f"Account margin level is moderate risk: {margin_level:.2f}×")
            else:
                color = discord.Color.red()
                health_status = "HIGH_RISK"
                logger.error(f"CRITICAL: Account margin level is high risk: {margin_level:.2f}×")
            
            logger.debug(f"Account health classified as: {health_status}")
            
            # Create embed
            embed = discord.Embed(
                title="Cross Margin Account Summary",
                description="All assets in shared collateral pool",
                color=color,
                timestamp=datetime.now()
            )
            
            # Get current BTC price for USD conversion
            logger.debug("Fetching BTC price for USD conversion...")
            ticker = self.client.ticker_price(symbol="BTCUSDT")
            btc_price = float(ticker["price"])
            logger.debug(f"BTC price: ${btc_price:.2f}")
            
            # Add account metrics
            embed.add_field(
                name="Account Health",
                value=(
                    f"**Margin Level:** {margin_level:.2f}×\n"
                    f"**Total Assets:** {total_asset_btc:.8f} BTC (${total_asset_btc * btc_price:.2f})\n"
                    f"**Total Liabilities:** {total_liability_btc:.8f} BTC (${total_liability_btc * btc_price:.2f})\n"
                    f"**Net Value:** {total_net_asset_btc:.8f} BTC (${total_net_asset_btc * btc_price:.2f})"
                ),
                inline=False
            )
            
            # Show individual assets
            user_assets = response.get("userAssets", [])
            significant_assets = [a for a in user_assets if float(a.get("netAsset", 0)) > 0.00001]
            logger.debug(f"Found {len(significant_assets)} significant assets out of {len(user_assets)} total")
            
            for asset in significant_assets[:6]:  # Limit to 6 for embed size
                asset_name = asset["asset"]
                free = float(asset.get("free", 0))
                locked = float(asset.get("locked", 0))
                borrowed = float(asset.get("borrowed", 0))
                net = float(asset.get("netAsset", 0))
                
                if borrowed > 0:
                    logger.info(f"Asset {asset_name}: Borrowed {borrowed:.8f}")
                
                embed.add_field(
                    name=f"{asset_name}",
                    value=(
                        f"Free: {free:.8f}\n"
                        f"Locked: {locked:.8f}\n"
                        f"Borrowed: {borrowed:.8f}\n"
                        f"Net: {net:.8f}"
                    ),
                    inline=True
                )
            
            embed.set_footer(
                text=f"Requested by {ctx.author.display_name}",
                icon_url=ctx.author.avatar.url if ctx.author.avatar else None
            )
            
            await temp_msg.delete()
            await ctx.send(embed=embed)
            logger.info(f"Balance display completed successfully for {ctx.author.name}")
            
        except Exception as e:
            logger.error(f"Error in balance command for {ctx.author.name}: {str(e)}")
            await temp_msg.edit(content=f"Error fetching account data: {str(e)}")

    # ==================== ORDER QUERY COMMANDS ====================

    @commands.command(name="openorders", aliases=['oo', 'open'])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def open_orders(self, ctx, symbol: Optional[str] = None):
        """
        Display open cross margin orders (all symbols or specific)
        """
        logger.info(f"Open orders command invoked by {ctx.author.name} for symbol: {symbol or 'ALL'}")
        
        try:
            # Get orders - no isIsolated parameter for cross margin
            if symbol:
                logger.debug(f"Querying open orders for specific symbol: {symbol.upper()}")
                orders = self.client.margin_open_orders(symbol=symbol.upper())
            else:
                logger.debug("Querying all open margin orders")
                orders = self.client.margin_open_orders()  # All symbols
            
            logger.debug(f"API returned {len(orders)} open orders")
            
            if not orders:
                logger.info(f"No open orders found for {ctx.author.name}")
                await ctx.send("No open orders found.")
                return
            
            logger.info(f"Found {len(orders)} open orders for {ctx.author.name}")
            
            embed = discord.Embed(
                title=f"Open Cross Margin Orders",
                description=f"Found {len(orders)} active orders",
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )
            
            # Group by symbol
            by_symbol = {}
            for order in orders:
                sym = order.get("symbol", "UNKNOWN")
                if sym not in by_symbol:
                    by_symbol[sym] = []
                by_symbol[sym].append(order)
            
            logger.debug(f"Orders grouped across {len(by_symbol)} symbols")
            
            for symbol, symbol_orders in list(by_symbol.items())[:5]:  # Limit for embed size
                orders_text = ""
                for order in symbol_orders[:3]:  # Max 3 per symbol
                    side = order.get("side", "")
                    qty = order.get("origQty", "0")
                    price = float(order.get("price", 0))
                    emoji = "🟢" if side == "BUY" else "🔴"
                    
                    orders_text += f"{emoji} {side} {qty} @ ${price:.2f}\n"
                    orders_text += f"ID: `{order.get('orderId', 'N/A')}`\n\n"
                
                embed.add_field(
                    name=f"{symbol} ({len(symbol_orders)} orders)",
                    value=orders_text,
                    inline=False
                )
            
            await ctx.send(embed=embed)
            logger.info(f"Open orders display completed for {ctx.author.name}")
            
        except Exception as e:
            logger.error(f"Error retrieving open orders for {ctx.author.name}: {str(e)}")
            await ctx.send(f"❌ Error: {str(e)}")

    @commands.command(name="cancelall", aliases=['canall'])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def cancel_all_orders(self, ctx, symbol: str):
        """Cancel all open orders for a symbol in cross margin"""
        logger.warning(f"CANCEL ALL ORDERS initiated by {ctx.author.name} for {symbol.upper()}")
        
        try:
            # No isIsolated parameter for cross margin
            logger.debug(f"Executing mass cancellation for {symbol.upper()}")
            response = self.client.margin_open_orders_cancellation(symbol=symbol.upper())
            logger.info(f"Successfully cancelled all orders for {symbol.upper()} - Response: {response}")
            await ctx.send(f"✅ Cancelled all orders for {symbol.upper()}")
        except Exception as e:
            logger.error(f"Failed to cancel orders for {symbol.upper()}: {e}")
            await ctx.send(f"❌ Error: {str(e)}")

    # ==================== ORDER PLACEMENT COMMANDS ====================

    @commands.has_role("Trading-Authorized")
    @commands.command(name="order", aliases=["mo"])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def market_order(self, ctx, symbol: str, side: str, quantity: float, side_effect: str = "AUTO_BORROW_REPAY"):
        """
        Place cross margin market order on ANY symbol
        
        Examples:
        !order BTCUSDC BUY 0.001
        !order ETHUSDC SELL 0.5
        """
        logger.info(f"MARKET ORDER initiated: {symbol.upper()} {side.upper()} {quantity} by {ctx.author.name}")
        
        params = {
            "symbol": symbol.upper(),
            "side": side.upper(),
            "type": "MARKET",
            "quantity": str(quantity),
            # NO isIsolated parameter for cross margin
            "sideEffectType": side_effect.upper()
        }
        
        logger.debug(f"Order parameters: {params}")
        
        try:
            logger.debug("Sending market order to Binance API...")
            order = self.client.new_margin_order(**params)
            
            order_id = order.get('orderId', 'UNKNOWN')
            executed_qty = order.get('executedQty', '0')
            executed_price = float(order.get('cummulativeQuoteQty', 0)) / float(executed_qty) if float(executed_qty) > 0 else 0
            
            logger.info(f"MARKET ORDER SUCCESS: ID {order_id}, Executed {executed_qty} @ ${executed_price:.2f}")
            await ctx.send(f"✅ Order placed! ID: {order_id}")
            
        except Exception as e:
            logger.error(f"MARKET ORDER FAILED for {ctx.author.name}: {symbol} {side} {quantity} - Error: {str(e)}")
            await ctx.send(f"❌ Order failed: {str(e)}")

    @commands.has_role("Trading-Authorized")
    @commands.command(name="oco")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def oco_order(self, ctx, symbol: str, side: str, quantity: float, price: float, stop_price: float):
        """Place OCO order in cross margin"""
        logger.info(f"OCO ORDER initiated: {symbol.upper()} {side.upper()} {quantity} TP:{price} SL:{stop_price} by {ctx.author.name}")
        
        params = {
            "symbol": symbol.upper(),
            "side": side.upper(),
            "quantity": str(quantity),
            "price": str(price),
            "stopPrice": str(stop_price),
            # NO isIsolated parameter
            "sideEffectType": "AUTO_BORROW_REPAY"
        }
        
        logger.debug(f"OCO parameters: {params}")
        
        try:
            logger.debug("Sending OCO order to Binance API...")
            order = self.client.new_margin_oco_order(**params)
            
            order_list_id = order.get('orderListId', 'UNKNOWN')
            logger.info(f"OCO ORDER SUCCESS: List ID {order_list_id}")
            await ctx.send(f"✅ OCO placed! List ID: {order_list_id}")
            
        except Exception as e:
            logger.error(f"OCO ORDER FAILED for {ctx.author.name}: {str(e)}")
            await ctx.send(f"❌ OCO failed: {str(e)}")

    # ==================== FULL POSITION COMMAND ====================

    @commands.has_role("Trading-Authorized")
    @commands.command(name="fullpos", aliases=["fp"])
    async def full_position(self, ctx, symbol: str, side: str, amount: float, rr: float = 1.5):
        """
        Open position with automatic TP/SL
        Works with ANY cross margin pair
        
        Examples:
        !fullpos BTCUSDC buy 0.001 1.5
        !fullpos ETHUSDC sell 0.5 2.0
        """
        logger.info(f"FULL POSITION initiated: {symbol.upper()} {side.upper()} {amount} R/R:{rr} by {ctx.author.name}")
        
        processing_msg = await ctx.send(f"⏳ Creating position for {symbol}...")
        
        try:
            # Step 1: Market entry
            params = {
                "symbol": symbol.upper(),
                "side": side.upper(),
                "type": "MARKET",
                "quantity": str(amount),
                "sideEffectType": "AUTO_BORROW_REPAY"
            }
            
            logger.debug(f"Step 1 - Market entry parameters: {params}")
            logger.debug("Placing market order for position entry...")
            
            market_order = self.client.new_margin_order(**params)
            
            # Extract execution details
            executed_qty = float(market_order.get("executedQty", 0))
            executed_quote_qty = float(market_order.get("cummulativeQuoteQty", 0))
            executed_price = executed_quote_qty / executed_qty if executed_qty > 0 else 0
            
            logger.info(f"Market entry filled: {executed_qty} @ ${executed_price:.2f}")
            
            # Step 2: Calculate TP/SL
            direction = 1 if side.lower() == "buy" else -1
            f0 = 0.001  # Entry fee
            ft = 0.001  # Exit fee
            risk = 0.01
            
            logger.debug(f"Calculating TP/SL with direction:{direction}, risk:{risk}, R/R:{rr}")
            
            tp = (risk * executed_price * rr + executed_price * (f0 + direction)) / (direction - ft)
            sl = (risk * executed_price - executed_price * (f0 + direction)) / (ft - direction)
            
            tp = round(tp, 2)
            sl = round(sl, 2)
            
            logger.info(f"Calculated levels - TP: ${tp:.2f}, SL: ${sl:.2f}")
            
            # Step 3: Place OCO
            opposite_side = "SELL" if side.upper() == "BUY" else "BUY"
            
            oco_params = {
                "symbol": symbol.upper(),
                "side": opposite_side,
                "quantity": str(executed_qty),
                "price": str(tp),
                "stopPrice": str(sl),
                "sideEffectType": "AUTO_BORROW_REPAY"
            }
            
            logger.debug(f"Step 2 - OCO parameters: {oco_params}")
            logger.debug("Placing OCO for risk management...")
            
            oco_order = self.client.new_margin_oco_order(**oco_params)
            
            logger.info(f"OCO placed successfully: List ID {oco_order.get('orderListId', 'UNKNOWN')}")
            
            # Send result
            embed = discord.Embed(
                title=f"✅ Position Created: {symbol}",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
            
            embed.add_field(name="Entry", value=f"${executed_price:.2f}", inline=True)
            embed.add_field(name="Size", value=f"{executed_qty:.8f}", inline=True)
            embed.add_field(name="Side", value=side.upper(), inline=True)
            embed.add_field(name="Take Profit", value=f"${tp:.2f}", inline=True)
            embed.add_field(name="Stop Loss", value=f"${sl:.2f}", inline=True)
            embed.add_field(name="Risk/Reward", value=f"{rr}", inline=True)
            
            await processing_msg.edit(content=None, embed=embed)
            logger.info(f"FULL POSITION SUCCESS for {ctx.author.name}: {symbol} position created")
            
        except Exception as e:
            logger.error(f"FULL POSITION FAILED for {ctx.author.name}: {str(e)}")
            await processing_msg.edit(content=f"❌ Error: {str(e)}")

    # ==================== PAIRS TRADING ====================

    def extract_total_capital(self, account_info):
        """Extract total USD value from cross margin account"""
        logger.debug("Extracting total capital from account info...")
        
        user_assets = account_info.get("userAssets", [])
        total_usd = 0
        
        # Get current prices for conversion
        logger.debug("Fetching current prices for capital calculation...")
        btc_ticker = self.client.ticker_price(symbol="BTCUSDT")
        btc_price = float(btc_ticker["price"])
        
        eth_ticker = self.client.ticker_price(symbol="ETHUSDT")
        eth_price = float(eth_ticker["price"])
        
        logger.debug(f"Current prices - BTC: ${btc_price:.2f}, ETH: ${eth_price:.2f}")
        
        for asset in user_assets:
            asset_name = asset["asset"]
            net_amount = float(asset.get("netAsset", 0))
            
            if net_amount > 0:  # Only log positive balances
                if asset_name == "USDT" or asset_name == "USDC":
                    total_usd += net_amount
                    logger.debug(f"Added ${net_amount:.2f} from {asset_name}")
                elif asset_name == "BTC":
                    usd_value = net_amount * btc_price
                    total_usd += usd_value
                    logger.debug(f"Added ${usd_value:.2f} from {net_amount:.8f} BTC")
                elif asset_name == "ETH":
                    usd_value = net_amount * eth_price
                    total_usd += usd_value
                    logger.debug(f"Added ${usd_value:.2f} from {net_amount:.8f} ETH")
                # Add more conversions as needed
        
        logger.info(f"Total account capital calculated: ${total_usd:.2f}")
        return total_usd

    def calculate_pair_positions(self, signal_data: dict, total_capital: float, capital_allocation: float = 0.20) -> dict:
        """Calculate position sizes for pairs trading"""
        logger.debug(f"Calculating pair positions with capital: ${total_capital:.2f}, allocation: {capital_allocation*100}%")
        
        beta = signal_data['beta']
        btc_price = signal_data['asset1_price'] 
        eth_price = signal_data['asset2_price']
        action = signal_data['action']
        
        logger.debug(f"Signal parameters - Beta: {beta:.4f}, BTC: ${btc_price:.2f}, ETH: ${eth_price:.2f}, Action: {action}")
        
        allocated_capital = total_capital * capital_allocation
        
        btc_dollar_allocation = allocated_capital / (1 + beta)
        eth_dollar_allocation = beta * btc_dollar_allocation
        
        btc_size = btc_dollar_allocation / btc_price
        eth_size = eth_dollar_allocation / eth_price
        
        logger.debug(f"Raw calculations - BTC size: {btc_size:.8f}, ETH size: {eth_size:.8f}")
        
        # Round to Binance LOT_SIZE requirements
        # BTC: 0.00001 (5 decimals)
        # ETH: 0.001 (3 decimals)
        btc_size = round(btc_size // 0.00001 * 0.00001, 5)
        eth_size = round(eth_size // 0.001 * 0.001, 3)
        
        logger.debug(f"Rounded sizes - BTC: {btc_size:.8f}, ETH: {eth_size:.8f}")
        
        if action == "LONG":
            btc_side = "BUY"
            eth_side = "SELL"
        else:
            btc_side = "SELL"
            eth_side = "BUY"
        
        result = {
            "btc": {
                "symbol": "BTCUSDC",
                "side": btc_side,
                "size": btc_size,
                "entry_price": btc_price,
                "dollar_value": btc_size * btc_price
            },
            "eth": {
                "symbol": "ETHUSDC",
                "side": eth_side,
                "size": eth_size,
                "entry_price": eth_price,
                "dollar_value": eth_size * eth_price
            },
            "total_allocated": allocated_capital,
            "hedge_ratio": beta
        }
        
        logger.info(f"Position calculation complete - BTC: {btc_side} ${result['btc']['dollar_value']:.2f}, ETH: {eth_side} ${result['eth']['dollar_value']:.2f}")
        return result

    async def execute_pairs_trade(self, signal_data, channel):
        """Execute pairs trade using cross margin"""
        logger.info(f"Executing pairs trade for signal: {signal_data.get('signal_id', 'UNKNOWN')}")
        
        # Get account balance (cross margin)
        logger.debug("Fetching account information for capital calculation...")
        account_info = self.client.margin_account()
        total_capital = self.extract_total_capital(account_info)
        
        positions = self.calculate_pair_positions(signal_data, total_capital)
        logger.debug(f"Calculated positions: {positions}")
        
        # Place both orders - use MARKET for testing with small capital
        btc_params = {
            "symbol": positions["btc"]["symbol"],
            "side": positions["btc"]["side"],
            "type": "MARKET",
            "quantity": str(positions["btc"]["size"]),
            "sideEffectType": "AUTO_BORROW_REPAY"
        }
        
        eth_params = {
            "symbol": positions["eth"]["symbol"],
            "side": positions["eth"]["side"],
            "type": "MARKET",
            "quantity": str(positions["eth"]["size"]),
            "sideEffectType": "AUTO_BORROW_REPAY"
        }
        
        logger.debug(f"BTC order params: {btc_params}")
        logger.debug(f"ETH order params: {eth_params}")
        
        try:
            logger.info("Placing BTC leg of pairs trade...")
            btc_order = self.client.new_margin_order(**btc_params)
            logger.info(f"BTC order filled: ID {btc_order.get('orderId', 'UNKNOWN')}")
            
            logger.info("Placing ETH leg of pairs trade...")
            eth_order = self.client.new_margin_order(**eth_params)
            logger.info(f"ETH order filled: ID {eth_order.get('orderId', 'UNKNOWN')}")
            
            await channel.send(f"✅ Pairs trade executed:\nBTC: {btc_order['orderId']}\nETH: {eth_order['orderId']}")
            
            # Monitor execution
            logger.debug("Starting execution monitoring...")
            await self.monitor_pairs_execution(btc_order, eth_order, signal_data, channel)
            
        except Exception as e:
            logger.error(f"Pairs trade execution failed: {e}")
            await channel.send(f"❌ Pairs trade failed: {str(e)}")

    async def monitor_pairs_execution(self, btc_order, eth_order, signal_data, channel):
        """Monitor fills and handle partial execution"""
        logger.debug("Monitoring pairs execution status...")
        await asyncio.sleep(5)
        
        try:
            # Check status (no isIsolated parameter)
            logger.debug("Checking BTC order status...")
            btc_status = self.client.query_margin_order(
                symbol="BTCUSDC",
                orderId=btc_order['orderId']
            )
            
            logger.debug("Checking ETH order status...")
            eth_status = self.client.query_margin_order(
                symbol="ETHUSDC",
                orderId=eth_order['orderId']
            )
            
            btc_filled = btc_status['status'] == 'FILLED'
            eth_filled = eth_status['status'] == 'FILLED'
            
            logger.info(f"Order status - BTC: {btc_status['status']}, ETH: {eth_status['status']}")
            
            if btc_filled and eth_filled:
                logger.info("Both legs filled successfully")
                await channel.send("✅ Both legs filled")
                # Set up OCO orders here
            elif btc_filled or eth_filled:
                logger.warning("PARTIAL FILL DETECTED - Only one leg filled")
                await channel.send("⚠️ Only one leg filled - emergency exit")
                # Handle partial fill
            else:
                logger.warning("Orders not filled - executing cancellation")
                await channel.send("⏰ Orders not filled - cancelling")
                self.client.cancel_margin_order(symbol="BTCUSDC", orderId=btc_order['orderId'])
                self.client.cancel_margin_order(symbol="ETHUSDC", orderId=eth_order['orderId'])
                logger.info("Both orders cancelled successfully")
                
        except Exception as e:
            logger.error(f"Error monitoring pairs execution: {e}")
            await channel.send(f"❌ Error monitoring execution: {str(e)}")

    # ==================== PAIRS EXECUTION ====================

    @commands.command(name="pairs")
    async def execute_pairs(self, ctx, btc_amount: float, eth_amount: float, btc_side: str, eth_side: str, tp_percent: float = 1.5, sl_percent: float = 1.0):
        """
        Execute pairs trade with 2 entries + 2 OCOs
        
        Example:
        !pairs 0.0002 0.01 SELL BUY 1.5 1.0
        (Sell 0.0002 BTC, Buy 0.01 ETH, TP at 1.5%, SL at 1%)
        """
        logger.info(f"PAIRS TRADE initiated by {ctx.author.name}: BTC {btc_side} {btc_amount}, ETH {eth_side} {eth_amount}, TP:{tp_percent}%, SL:{sl_percent}%")
        
        try:
            # Entry orders
            logger.debug("Placing BTC entry order...")
            btc_order = self.client.new_margin_order(
                symbol="BTCUSDC",
                side=btc_side.upper(),
                type="MARKET",
                quantity=str(btc_amount),
                sideEffectType="AUTO_BORROW_REPAY"
            )
            logger.info(f"BTC entry filled: ID {btc_order['orderId']}")
            await ctx.send(f"✅ BTC {btc_side}: {btc_order['orderId']}")
            
            logger.debug("Placing ETH entry order...")
            eth_order = self.client.new_margin_order(
                symbol="ETHUSDC",
                side=eth_side.upper(),
                type="MARKET",
                quantity=str(eth_amount),
                sideEffectType="AUTO_BORROW_REPAY"
            )
            logger.info(f"ETH entry filled: ID {eth_order['orderId']}")
            await ctx.send(f"✅ ETH {eth_side}: {eth_order['orderId']}")
            
            # Get executed prices
            btc_price = float(btc_order['cummulativeQuoteQty']) / float(btc_order['executedQty'])
            eth_price = float(eth_order['cummulativeQuoteQty']) / float(eth_order['executedQty'])
            
            logger.debug(f"Executed prices - BTC: ${btc_price:.2f}, ETH: ${eth_price:.2f}")
            
            # Calculate TP/SL
            btc_tp = btc_price * (1 + tp_percent/100) if btc_side == "BUY" else btc_price * (1 - tp_percent/100)
            btc_sl = btc_price * (1 - sl_percent/100) if btc_side == "BUY" else btc_price * (1 + sl_percent/100)
            
            eth_tp = eth_price * (1 + tp_percent/100) if eth_side == "BUY" else eth_price * (1 - tp_percent/100)
            eth_sl = eth_price * (1 - sl_percent/100) if eth_side == "BUY" else eth_price * (1 + sl_percent/100)
            
            logger.info(f"Calculated TP/SL levels - BTC TP:${btc_tp:.2f} SL:${btc_sl:.2f}, ETH TP:${eth_tp:.2f} SL:${eth_sl:.2f}")
            
            # Place OCOs
            logger.debug("Placing BTC OCO order...")
            btc_oco = self.client.new_margin_oco_order(
                symbol="BTCUSDC",
                side="SELL" if btc_side == "BUY" else "BUY",
                quantity=str(btc_amount),
                price=str(round(btc_tp, 2)),
                stopPrice=str(round(btc_sl, 2)),
                sideEffectType="AUTO_BORROW_REPAY"
            )
            logger.info(f"BTC OCO placed: List ID {btc_oco['orderListId']}")
            await ctx.send(f"✅ BTC OCO: {btc_oco['orderListId']}")
            
            logger.debug("Placing ETH OCO order...")
            eth_oco = self.client.new_margin_oco_order(
                symbol="ETHUSDC",
                side="SELL" if eth_side == "BUY" else "BUY",
                quantity=str(eth_amount),
                price=str(round(eth_tp, 2)),
                stopPrice=str(round(eth_sl, 2)),
                sideEffectType="AUTO_BORROW_REPAY"
            )
            logger.info(f"ETH OCO placed: List ID {eth_oco['orderListId']}")
            await ctx.send(f"✅ ETH OCO: {eth_oco['orderListId']}")
            
            # Summary
            embed = discord.Embed(title="Pairs Trade Executed", color=discord.Color.green())
            embed.add_field(name="BTC", value=f"{btc_side} @ ${btc_price:.2f}\nTP: ${btc_tp:.2f}\nSL: ${btc_sl:.2f}", inline=True)
            embed.add_field(name="ETH", value=f"{eth_side} @ ${eth_price:.2f}\nTP: ${eth_tp:.2f}\nSL: ${eth_sl:.2f}", inline=True)
            await ctx.send(embed=embed)
            
            logger.info(f"PAIRS TRADE SUCCESS for {ctx.author.name}: Complete execution with OCOs")
            
        except Exception as e:
            logger.error(f"PAIRS TRADE FAILED for {ctx.author.name}: {e}")
            await ctx.send(f"❌ Error: {e}")

    # ==================== SIGNAL HANDLING ====================

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot and "TRADING SIGNAL APPROVAL NEEDED" in message.content:
            logger.info(f"Trading signal detected in message {message.id}")
            await self.handle_signal_approval(message)

    async def handle_signal_approval(self, message):
        """Parse and store signal for approval"""
        logger.debug(f"Processing signal approval for message {message.id}")
        
        signal_data = self.parse_signal_message(message.content)
        
        if signal_data:
            signal_id = signal_data['signal_id']
            logger.info(f"Signal {signal_id} parsed successfully, awaiting approval")
            
            self.pending_signals[signal_id] = {
                'data': signal_data,
                'message_id': message.id,
                'channel_id': message.channel.id,
                'expires_at': datetime.now() + timedelta(minutes=self.APPROVAL_TIMEOUT)
            }
            
            await message.add_reaction('✅')
            await message.add_reaction('❌')
            logger.debug(f"Approval reactions added to signal {signal_id}")
        else:
            logger.error(f"Failed to parse signal from message {message.id}")

    def parse_signal_message(self, content: str) -> Optional[dict]:
        """Parse signal from Discord message"""
        logger.debug("Parsing signal message content...")
        
        try:
            from models import TradingSignalApproval
            signal = TradingSignalApproval.from_discord_message(content)
            
            if signal:
                logger.debug(f"Signal parsed successfully: {signal.signal_id}")
                return signal.model_dump()
            else:
                logger.warning("Signal parsing returned None")
                return None
                
        except Exception as e:
            logger.error(f"Error parsing signal message: {e}")
            return None

    @commands.command(name="checkmarginsymbols")
    async def check_margin_symbols(self, ctx):
        """Check available margin trading pairs"""
        logger.info(f"Checking margin symbols requested by {ctx.author.name}")
        
        try:
            info = self.client.margin_all_pairs()
            usdc_pairs = [p for p in info if 'USDC' in p['symbol']]
            
            logger.info(f"Found {len(usdc_pairs)} USDC margin pairs out of {len(info)} total pairs")
            
            await ctx.send(f"Found {len(usdc_pairs)} USDC margin pairs. Showing first 10:")
            for pair in usdc_pairs[:10]:
                await ctx.send(f"{pair['symbol']}: {pair['isMarginTrade']}")
                
        except Exception as e:
            logger.error(f"Error checking margin symbols: {e}")
            await ctx.send(f"❌ Error: {str(e)}")
    
    @commands.command(name="testsingletrade")
    async def test_single_trade(self, ctx):
        """Test just BTC side with larger amount"""
        logger.warning(f"TEST TRADE initiated by {ctx.author.name} - This will place real orders")
        
        try:
            params = {
                "symbol": "BTCUSDC",
                "side": "SELL",
                "type": "MARKET",
                "quantity": "0.0002",  # ~$20
                "sideEffectType": "AUTO_BORROW_REPAY"
            }
            
            logger.debug(f"Test order params: {params}")
            order = self.client.new_margin_order(**params)
            logger.info(f"Test order placed: ID {order['orderId']}")
            await ctx.send(f"✅ Order placed: {order['orderId']}")
            
            # Reverse immediately
            logger.debug("Waiting 2 seconds before reversal...")
            await asyncio.sleep(2)
            
            reverse = {
                "symbol": "BTCUSDC",
                "side": "BUY",
                "type": "MARKET",
                "quantity": "0.0002",
                "sideEffectType": "AUTO_BORROW_REPAY"
            }
            
            logger.debug(f"Reverse order params: {reverse}")
            order2 = self.client.new_margin_order(**reverse)
            logger.info(f"Reverse order placed: ID {order2['orderId']}")
            await ctx.send(f"✅ Reversed: {order2['orderId']}")
            
        except Exception as e:
            logger.error(f"Test trade failed: {e}")
            await ctx.send(f"❌ Failed: {e}")

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        """Handle signal approval and rejection reactions"""
        # Ignore bot reactions and only process ✅ or ❌
        if user.bot or str(reaction.emoji) not in ['✅', '❌']:
            return
            
        logger.debug(f"Reaction {reaction.emoji} added by {user.name} to message {reaction.message.id}")
        
        # Find the pending signal for this message
        signal_data = None
        signal_id = None
        
        for sid, stored_signal in self.pending_signals.items():
            if stored_signal['message_id'] == reaction.message.id:
                signal_data = stored_signal['data']
                signal_id = sid
                break
        
        # If no pending signal found, ignore
        if not signal_data:
            logger.debug("No pending signal found for this reaction")
            return
            
        logger.info(f"Processing signal {signal_id} reaction {reaction.emoji} from {user.name}")
        
        # Handle approval (✅)
        if str(reaction.emoji) == '✅':
            logger.info(f"Signal {signal_id} APPROVED by {user.name}")
            
            # Create approval status embed
            approval_embed = discord.Embed(
                title="🚀 SIGNAL APPROVED & EXECUTING",
                description=f"Signal `{signal_id}` approved by {user.display_name}",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
            approval_embed.add_field(
                name="Action", 
                value=signal_data.get('action', 'Unknown'), 
                inline=True
            )
            approval_embed.add_field(
                name="Pair", 
                value=signal_data.get('pair', 'Unknown'), 
                inline=True
            )
            approval_embed.add_field(
                name="Status", 
                value="🔥 Executing trade...", 
                inline=True
            )
            approval_embed.set_footer(
                text=f"Approved by {user.display_name}",
                icon_url=user.avatar.url if user.avatar else None
            )
            
            await reaction.message.channel.send(embed=approval_embed)
            
            # Try to clean up reactions (might work even if editing doesn't)
            try:
                await reaction.message.clear_reactions()
                logger.debug("Reactions cleared successfully")
            except discord.Forbidden:
                # If can't clear all, try to remove just the bot's reactions
                try:
                    await reaction.message.remove_reaction('✅', reaction.message.guild.me)
                    await reaction.message.remove_reaction('❌', reaction.message.guild.me)
                    logger.debug("Bot reactions removed")
                except discord.Forbidden:
                    logger.warning("Could not remove reactions - insufficient permissions")
                    pass  # Silently continue if no reaction permissions
            
            # Execute the pairs trade
            logger.info(f"Executing approved signal {signal_id}")
            await self.execute_signal_as_pairs_trade(signal_data, reaction.message.channel)
        
        # Handle rejection (❌)  
        elif str(reaction.emoji) == '❌':
            logger.info(f"Signal {signal_id} REJECTED by {user.name}")
            
            # Create rejection status embed
            rejection_embed = discord.Embed(
                title="🚫 SIGNAL REJECTED",
                description=f"Signal `{signal_id}` rejected by {user.display_name}",
                color=discord.Color.red(),
                timestamp=datetime.now()
            )
            rejection_embed.add_field(
                name="Action", 
                value=signal_data.get('action', 'Unknown'), 
                inline=True
            )
            rejection_embed.add_field(
                name="Pair", 
                value=signal_data.get('pair', 'Unknown'), 
                inline=True
            )
            rejection_embed.add_field(
                name="Reason", 
                value="❌ Manually rejected", 
                inline=True
            )
            rejection_embed.add_field(
                name="Status", 
                value="🚫 No trade executed", 
                inline=False
            )
            rejection_embed.set_footer(
                text=f"Rejected by {user.display_name}",
                icon_url=user.avatar.url if user.avatar else None
            )
            
            await reaction.message.channel.send(embed=rejection_embed)
            
            # Try to clean up reactions
            try:
                await reaction.message.clear_reactions()
                logger.debug("Reactions cleared after rejection")
            except discord.Forbidden:
                # If can't clear all, try to remove just the bot's reactions
                try:
                    await reaction.message.remove_reaction('✅', reaction.message.guild.me)
                    await reaction.message.remove_reaction('❌', reaction.message.guild.me)
                    logger.debug("Bot reactions removed after rejection")
                except discord.Forbidden:
                    logger.warning("Could not remove reactions after rejection")
                    pass  # Silently continue if no reaction permissions
        
        # Clean up the pending signal from memory (for both cases)
        if signal_id in self.pending_signals:
            del self.pending_signals[signal_id]
            logger.debug(f"Signal {signal_id} removed from pending signals")

    async def execute_signal_as_pairs_trade(self, signal_data, channel):
        """Convert signal parameters to pairs trade execution"""
        logger.info(f"Converting signal {signal_data.get('signal_id', 'UNKNOWN')} to pairs trade")
        
        action = signal_data['action']  # "LONG" or "SHORT" 
        beta = signal_data['beta']      # 2.3695
        btc_price = signal_data['asset1_price']
        eth_price = signal_data['asset2_price']
        
        logger.debug(f"Signal parameters - Action: {action}, Beta: {beta}, BTC: ${btc_price}, ETH: ${eth_price}")
        
        # Calculate position sizes based on your capital allocation
        account_info = self.client.margin_account()
        total_capital = self.extract_total_capital(account_info)
        positions = self.calculate_pair_positions(signal_data, total_capital, capital_allocation=0.25)
        
        # Extract the calculated amounts and sides
        btc_amount = positions['btc']['size']
        eth_amount = positions['eth']['size'] 
        btc_side = positions['btc']['side']
        eth_side = positions['eth']['side']
        
        logger.info(f"Executing signal as pairs trade: BTC {btc_side} {btc_amount}, ETH {eth_side} {eth_amount}")
        
        # Execute using your existing pairs command logic
        await self.pairs_trade_execution(btc_amount, eth_amount, btc_side, eth_side, channel=channel, sl_percent=0.05)

    async def pairs_trade_execution(self, btc_amount: float, eth_amount: float, btc_side: str, eth_side: str, tp_percent: float, sl_percent: float, channel):
        """
        Execute pairs trade with 2 entries + 2 OCOs
        
        Args:
            btc_amount: Amount of BTC to trade
            eth_amount: Amount of ETH to trade  
            btc_side: BTC side (BUY/SELL)
            eth_side: ETH side (BUY/SELL)
            tp_percent: Take profit percentage
            sl_percent: Stop loss percentage
            channel: Discord channel to send updates to
        """
        logger.info(f"Executing pairs trade - BTC: {btc_side} {btc_amount}, ETH: {eth_side} {eth_amount}")
        
        try:
            # Check minimum notionals first
            logger.debug("Checking minimum notional requirements...")
            btc_ticker = self.client.ticker_price(symbol="BTCUSDC")
            eth_ticker = self.client.ticker_price(symbol="ETHUSDC")
            
            btc_price = float(btc_ticker["price"])
            eth_price = float(eth_ticker["price"])
            
            btc_notional = btc_amount * btc_price
            eth_notional = eth_amount * eth_price
            
            min_notional = 5  # Binance minimum is usually ~$5
            
            logger.debug(f"Order notionals - BTC: ${btc_notional:.2f}, ETH: ${eth_notional:.2f}")
            
            if btc_notional < min_notional:
                logger.error(f"BTC order below minimum notional: ${btc_notional:.2f} < ${min_notional}")
                await channel.send(f"❌ BTC order too small: ${btc_notional:.2f} < ${min_notional}")
                return {"success": False, "error": "BTC notional too small"}
                
            if eth_notional < min_notional:
                logger.error(f"ETH order below minimum notional: ${eth_notional:.2f} < ${min_notional}")
                await channel.send(f"❌ ETH order too small: ${eth_notional:.2f} < ${min_notional}")
                return {"success": False, "error": "ETH notional too small"}
            
            await channel.send(f"📊 Order sizes: BTC=${btc_notional:.2f}, ETH=${eth_notional:.2f}")
        
            # Entry orders
            logger.info("Placing BTC entry order for pairs trade...")
            btc_order = self.client.new_margin_order(
                symbol="BTCUSDC",
                side=btc_side.upper(),
                type="MARKET",
                quantity=str(btc_amount),
                sideEffectType="AUTO_BORROW_REPAY"
            )
            logger.info(f"BTC entry executed: ID {btc_order['orderId']}")
            await channel.send(f"✅ BTC {btc_side}: {btc_order['orderId']}")
            
            logger.info("Placing ETH entry order for pairs trade...")
            eth_order = self.client.new_margin_order(
                symbol="ETHUSDC",
                side=eth_side.upper(),
                type="MARKET",
                quantity=str(eth_amount),
                sideEffectType="AUTO_BORROW_REPAY"
            )
            logger.info(f"ETH entry executed: ID {eth_order['orderId']}")
            await channel.send(f"✅ ETH {eth_side}: {eth_order['orderId']}")
            
            # Get executed prices
            btc_price = float(btc_order['cummulativeQuoteQty']) / float(btc_order['executedQty'])
            eth_price = float(eth_order['cummulativeQuoteQty']) / float(eth_order['executedQty'])
            
            logger.debug(f"Entry execution prices - BTC: ${btc_price:.2f}, ETH: ${eth_price:.2f}")
            
            # Calculate TP/SL levels
            btc_tp = btc_price * (1 + tp_percent/100) if btc_side.upper() == "BUY" else btc_price * (1 - tp_percent/100)
            btc_sl = btc_price * (1 - sl_percent/100) if btc_side.upper() == "BUY" else btc_price * (1 + sl_percent/100)
            
            eth_tp = eth_price * (1 + tp_percent/100) if eth_side.upper() == "BUY" else eth_price * (1 - tp_percent/100)
            eth_sl = eth_price * (1 - sl_percent/100) if eth_side.upper() == "BUY" else eth_price * (1 + sl_percent/100)
            
            logger.info(f"Risk management levels - BTC TP:${btc_tp:.2f} SL:${btc_sl:.2f}, ETH TP:${eth_tp:.2f} SL:${eth_sl:.2f}")
            
            # Place OCO orders
            logger.info("Placing BTC OCO for risk management...")
            btc_oco = self.client.new_margin_oco_order(
                symbol="BTCUSDC",
                side="SELL" if btc_side.upper() == "BUY" else "BUY",
                quantity=str(btc_amount),
                price=str(round(btc_tp, 2)),
                stopPrice=str(round(btc_sl, 2)),
                sideEffectType="AUTO_BORROW_REPAY"
            )
            logger.info(f"BTC OCO placed: List ID {btc_oco['orderListId']}")
            await channel.send(f"✅ BTC OCO: {btc_oco['orderListId']}")
            
            logger.info("Placing ETH OCO for risk management...")
            eth_oco = self.client.new_margin_oco_order(
                symbol="ETHUSDC",
                side="SELL" if eth_side.upper() == "BUY" else "BUY",
                quantity=str(eth_amount),
                price=str(round(eth_tp, 2)),
                stopPrice=str(round(eth_sl, 2)),
                sideEffectType="AUTO_BORROW_REPAY"
            )
            logger.info(f"ETH OCO placed: List ID {eth_oco['orderListId']}")
            await channel.send(f"✅ ETH OCO: {eth_oco['orderListId']}")
            
            # Create summary embed
            embed = discord.Embed(
                title="Pairs Trade Executed", 
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
            embed.add_field(
                name="BTC", 
                value=f"{btc_side.upper()} @ ${btc_price:.2f}\nTP: ${btc_tp:.2f}\nSL: ${btc_sl:.2f}", 
                inline=True
            )
            embed.add_field(
                name="ETH", 
                value=f"{eth_side.upper()} @ ${eth_price:.2f}\nTP: ${eth_tp:.2f}\nSL: ${eth_sl:.2f}", 
                inline=True
            )
            
            await channel.send(embed=embed)
            
            result = {
                "success": True,
                "btc_order_id": btc_order['orderId'],
                "eth_order_id": eth_order['orderId'],
                "btc_oco_id": btc_oco['orderListId'],
                "eth_oco_id": eth_oco['orderListId'],
                "btc_price": btc_price,
                "eth_price": eth_price
            }
            
            logger.info(f"Pairs trade execution completed successfully")
            return result
            
        except Exception as e:
            logger.error(f"Pairs trade execution FAILED: {e}")
            await channel.send(f"❌ Pairs trade error: {str(e)}")
            return {"success": False, "error": str(e)}

    # ==================== TEST COMMANDS ====================

    @commands.command(name="testpairs")
    async def test_pairs_execution(self, ctx, allocation_pct: float = 0.1):
        """Test pairs trading calculations without placing orders"""
        logger.info(f"Test pairs calculation requested by {ctx.author.name} with {allocation_pct*100}% allocation")
        
        test_signal = {
            "signal_id": "test_001",
            "action": "LONG",
            "pair": "BTCUSDC/ETHUSDC",
            "confidence": 0.5,
            "spread": 0.001499,
            "threshold": 0.000866,
            "beta": 2.3695,
            "mu": -1.341093,
            "asset1_price": 108010.0,
            "asset2_price": 3400.0,
            "timestamp": datetime.now(),
            "expires_minutes": 60
        }
        
        logger.debug(f"Test signal parameters: {test_signal}")
        
        try:
            account_info = self.client.margin_account()
            total_capital = self.extract_total_capital(account_info)
            positions = self.calculate_pair_positions(test_signal, total_capital, allocation_pct)
            
            result_message = f"""
**Test Position Calculation:**
Total Capital: ${total_capital:.2f}
Allocated ({allocation_pct*100}%): ${positions['total_allocated']:.2f}
BTC: {positions['btc']['side']} {positions['btc']['size']:.8f} @ ${positions['btc']['entry_price']}
ETH: {positions['eth']['side']} {positions['eth']['size']:.8f} @ ${positions['eth']['entry_price']}
Beta: {positions['hedge_ratio']:.4f}
            """
            
            await ctx.send(result_message)
            logger.info(f"Test calculation completed successfully for {ctx.author.name}")
            
        except Exception as e:
            logger.error(f"Test pairs calculation failed: {e}")
            await ctx.send(f"❌ Test failed: {e}")

    @commands.command(name="testpairslive")
    async def test_pairs_live(self, ctx, allocation_pct: float = 0.5):
        """Execute real pairs orders with custom allocation"""
        logger.warning(f"LIVE TEST PAIRS initiated by {ctx.author.name} with {allocation_pct*100}% allocation - REAL MONEY")
        
        # Check minimums first
        logger.debug("Checking exchange info for minimum requirements...")
        info = self.client.exchange_info()
        for s in info['symbols']:
            if s['symbol'] in ['BTCUSDC', 'ETHUSDC']:
                for f in s['filters']:
                    if f['filterType'] == 'MIN_NOTIONAL' or f['filterType'] == 'NOTIONAL':
                        min_notional = f.get('minNotional', f.get('notional', 'N/A'))
                        logger.debug(f"{s['symbol']}: Min notional = ${min_notional}")
                        await ctx.send(f"{s['symbol']}: Min notional = ${min_notional}")
        
        # Use BTCUSDT and ETHUSDT instead (lower minimums)
        test_signal = {
            "signal_id": f"live_test_{datetime.now().strftime('%H%M%S')}",
            "action": "SHORT",
            "pair": "BTCUSDT/ETHUSDT",
            "confidence": 0.5,
            "spread": 0.001499,
            "threshold": 0.000866,
            "beta": 2.3695,
            "mu": -1.341093,
            "asset1_price": 108010.0,
            "asset2_price": 3400.0,
            "timestamp": datetime.now(),
            "expires_minutes": 60
        }
        
        logger.info(f"Using BTCUSDT/ETHUSDT for live test with signal ID: {test_signal['signal_id']}")
        await ctx.send(f"⚠️ Using BTCUSDT/ETHUSDT with {allocation_pct*100}% allocation...")
        
        try:
            account_info = self.client.margin_account()
            total_capital = self.extract_total_capital(account_info)
            
            # Override symbols to USDT pairs
            positions = self.calculate_pair_positions(test_signal, total_capital, allocation_pct)
            positions["btc"]["symbol"] = "BTCUSDT"
            positions["eth"]["symbol"] = "ETHUSDT"
            
            logger.info(f"Calculated positions for live test: BTC {positions['btc']['side']} ${positions['btc']['dollar_value']:.2f}, ETH {positions['eth']['side']} ${positions['eth']['dollar_value']:.2f}")
            
            await ctx.send(f"""
**About to place:**
BTC: {positions['btc']['side']} {positions['btc']['size']:.8f} (${positions['btc']['dollar_value']:.2f})
ETH: {positions['eth']['side']} {positions['eth']['size']:.8f} (${positions['eth']['dollar_value']:.2f})
            """)
            
            # Place orders sequentially with error handling
            try:
                logger.info("Placing live BTC order...")
                btc_params = {
                    "symbol": "BTCUSDT",
                    "side": positions["btc"]["side"],
                    "type": "MARKET",
                    "quantity": str(positions["btc"]["size"]),
                    "sideEffectType": "AUTO_BORROW_REPAY"
                }
                btc_order = self.client.new_margin_order(**btc_params)
                logger.info(f"Live BTC order successful: ID {btc_order['orderId']}")
                await ctx.send(f"✅ BTC order placed: {btc_order['orderId']}")
            except Exception as e:
                logger.error(f"Live BTC order failed: {e}")
                await ctx.send(f"❌ BTC failed: {e}")
                return
            
            try:
                logger.info("Placing live ETH order...")
                eth_params = {
                    "symbol": "ETHUSDT",
                    "side": positions["eth"]["side"],
                    "type": "MARKET",
                    "quantity": str(positions["eth"]["size"]),
                    "sideEffectType": "AUTO_BORROW_REPAY"
                }
                eth_order = self.client.new_margin_order(**eth_params)
                logger.info(f"Live ETH order successful: ID {eth_order['orderId']}")
                await ctx.send(f"✅ ETH order placed: {eth_order['orderId']}")
            except Exception as e:
                logger.error(f"Live ETH order failed, reversing BTC: {e}")
                await ctx.send(f"❌ ETH failed: {e}")
                # Reverse BTC if ETH fails
                reverse_params = {
                    "symbol": "BTCUSDT",
                    "side": "BUY" if positions["btc"]["side"] == "SELL" else "SELL",
                    "type": "MARKET",
                    "quantity": str(positions["btc"]["size"]),
                    "sideEffectType": "AUTO_BORROW_REPAY"
                }
                self.client.new_margin_order(**reverse_params)
                logger.warning("BTC position reversed due to ETH failure")
                await ctx.send("🔄 Reversed BTC position")
                
            logger.info(f"Live pairs test completed for {ctx.author.name}")
            
        except Exception as e:
            logger.error(f"Live test failed for {ctx.author.name}: {e}")
            await ctx.send(f"❌ Test failed: {e}")

async def setup(bot):
    """Add the cross margin cog to the bot"""
    logger.info("Setting up CrossMarginBot cog...")
    await bot.add_cog(CrossMarginBot(bot))
    logger.info("CrossMarginBot cog setup complete")