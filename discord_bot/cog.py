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
import pandas as pd

class PandasLogSink:
    """A custom loguru sink to capture logs in memory for Excel export."""
    def __init__(self):
        self.logs = []

    def _sink(self, message):
        """The function that loguru will call for each new log record."""
        record = message.record
        
        # Extract the relevant data into a structured dictionary
        log_entry = {
            "timestamp": record["time"].strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
            "level": record["level"].name,
            "message": record["message"],
            "function": record["function"],
            "line": record["line"],
            "name": record["name"],
        }
        self.logs.append(log_entry)

    def save_to_excel(self, filename: str = None) -> str:
        """Converts the captured logs to a DataFrame and saves to Excel."""
        if not self.logs:
            return "No logs have been captured yet."

        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"bot_logs_{timestamp}.xlsx"
            
        # Create a pandas DataFrame from our list of log dictionaries
        df = pd.DataFrame(self.logs)
        
        try:
            # Save the DataFrame to an Excel file
            df.to_excel(filename, index=False, engine='openpyxl')
            logger.info(f"Successfully saved {len(self.logs)} log entries to {filename}")
            return f"Successfully saved {len(self.logs)} log entries to `{filename}`"
        except Exception as e:
            logger.error(f"Failed to save logs to Excel: {e}")
            return f"Error saving logs to Excel: {e}"

class CrossMarginBot(commands.Cog):
    """Discord cog for cross margin trading operations"""
    
    def __init__(self, bot):
        logger.info("Initializing CrossMarginBot cog...")
        self.bot = bot

        # =======================================================================
        # 1. Create an instance of our new sink
        self.log_sink = PandasLogSink()
        # 2. Tell loguru to send all logs (INFO and higher) to our custom sink
        logger.add(self.log_sink._sink, level="INFO", format="{message}")
        # =======================================================================


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
        self.TAKE_PROFIT_FACTOR = 0.5  # Exit when 50% of the signal's threshold is met
        self.STOP_LOSS_FACTOR = 0.5
        self.CAPITAL_ALLOCATION = 0.5

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

    def extract_total_capital(self, account_info, signal_data=None):
        """Extract total USD value from cross margin account"""
        logger.debug("Extracting total capital from account info...")
        
        user_assets = account_info.get("userAssets", [])
        total_usd = 0
        
        # Get current prices for conversion - use signal prices if available
        logger.debug("Fetching current prices for capital calculation...")
        if signal_data:
            # Extract asset names from signal pair (e.g., "AVAXUSDC/POLUSDC" -> "AVAX", "POL")
            pair_str = signal_data.get('pair', 'BTCUSDC/ETHUSDC')
            asset1_symbol, asset2_symbol = self.extract_assets_from_pair(pair_str)
            
            # Use prices from signal data
            asset1_price = signal_data.get('asset1_price', 0)
            asset2_price = signal_data.get('asset2_price', 0)
            
            logger.debug(f"Using signal prices - {asset1_symbol}: ${asset1_price:.2f}, {asset2_symbol}: ${asset2_price:.2f}")
        else:
            # Fallback to BTC/ETH for backward compatibility
            asset1_symbol, asset2_symbol = "BTC", "ETH"
            btc_ticker = self.client.ticker_price(symbol="BTCUSDT")
            asset1_price = float(btc_ticker["price"])
            
            eth_ticker = self.client.ticker_price(symbol="ETHUSDT")
            asset2_price = float(eth_ticker["price"])
            
            logger.debug(f"Using fallback prices - BTC: ${asset1_price:.2f}, ETH: ${asset2_price:.2f}")
        
        
        for asset in user_assets:
            asset_name = asset["asset"]
            net_amount = float(asset.get("netAsset", 0))
            
            if net_amount > 0:  # Only log positive balances
                if asset_name == "USDT" or asset_name == "USDC":
                    total_usd += net_amount
                    logger.debug(f"Added ${net_amount:.2f} from {asset_name}")
                elif asset_name == asset1_symbol:
                    usd_value = net_amount * asset1_price
                    total_usd += usd_value
                    logger.debug(f"Added ${usd_value:.2f} from {net_amount:.8f} {asset1_symbol}")
                elif asset_name == asset2_symbol:
                    usd_value = net_amount * asset2_price
                    total_usd += usd_value
                    logger.debug(f"Added ${usd_value:.2f} from {net_amount:.8f} {asset2_symbol}")
                # Add fallback for other major assets
                elif asset_name == "BTC" and asset1_symbol != "BTC":
                    btc_ticker = self.client.ticker_price(symbol="BTCUSDT")
                    btc_price = float(btc_ticker["price"])
                    usd_value = net_amount * btc_price
                    total_usd += usd_value
                    logger.debug(f"Added ${usd_value:.2f} from {net_amount:.8f} BTC (fallback)")
        
        logger.info(f"Total account capital calculated: ${total_usd:.2f}")
        return total_usd

    def _round_to_lot_size(self, quantity: float, asset_name: str) -> float:
        """Round quantity to appropriate lot size for the asset"""
        # Common lot size rules for major assets
        lot_sizes = {
            'BTC': 5,    # 0.00001
            'ETH': 3,    # 0.001  
            'AVAX': 1,   # 0.1
            'POL': 0,    # 1 (whole numbers)
            'MATIC': 0,  # 1 (POL was MATIC)
            'ADA': 0,    # 1
            'DOT': 1,    # 0.1
            'LINK': 1,   # 0.1
            'UNI': 1,    # 0.1
            'AAVE': 2,   # 0.01
            'SOL': 2,    # 0.01
        }
        
        decimals = lot_sizes.get(asset_name, 3)  # Default to 3 decimals
        rounded = round(quantity, decimals)
        
        logger.debug(f"Rounded {asset_name} quantity: {quantity:.8f} → {rounded:.8f}")
        return rounded
    
    def extract_assets_from_pair(self, pair_str: str) -> tuple:
        """Extract asset names from pair string like 'AVAXUSDC/POLUSDC' -> ('AVAX', 'POL')"""
        try:
            symbol1, symbol2 = pair_str.split('/')
            # Remove USDC/USDT suffix to get base assets
            asset1 = symbol1.replace('USDC', '').replace('USDT', '')
            asset2 = symbol2.replace('USDC', '').replace('USDT', '')
            logger.debug(f"Extracted assets from '{pair_str}': {asset1}, {asset2}")
            return asset1, asset2
        except Exception as e:
            logger.warning(f"Failed to extract assets from '{pair_str}': {e}. Using BTC/ETH fallback.")
            return "BTC", "ETH"
    
    def calculate_pair_positions(self, signal_data: dict, total_capital: float) -> dict:
        """Calculate position sizes for pairs trading"""
        logger.debug(f"Calculating pair positions with capital: ${total_capital:.2f}, allocation: {self.CAPITAL_ALLOCATION*100}%")
        
        beta = signal_data['beta']
        asset1_price = signal_data['asset1_price'] 
        asset2_price = signal_data['asset2_price']
        action = signal_data['action']
        
        # Extract trading symbols from signal
        pair_str = signal_data.get('pair', 'BTCUSDC/ETHUSDC')
        asset1_name, asset2_name = self.extract_assets_from_pair(pair_str)
        symbol1, symbol2 = pair_str.split('/')
        
        logger.debug(f"Signal parameters - Beta: {beta:.4f}, {asset1_name}: ${asset1_price:.2f}, {asset2_name}: ${asset2_price:.2f}, Action: {action}")
        logger.debug(f"Trading symbols: {symbol1}, {symbol2}")
        
        allocated_capital = total_capital * self.CAPITAL_ALLOCATION
        
        # Corrected calculation to handle negative beta and ensure positive position sizes
        asset1_dollar_allocation = allocated_capital / (1 + abs(beta))
        asset2_dollar_allocation = asset1_dollar_allocation * abs(beta)

        asset1_size = asset1_dollar_allocation / asset1_price
        asset2_size = asset2_dollar_allocation / asset2_price
        
        logger.debug(f"Raw calculations - {asset1_name} size: {asset1_size:.8f}, {asset2_name} size: {asset2_size:.8f}")
        
        # Round to proper lot sizes for different assets
        asset1_size = self._round_to_lot_size(asset1_size, asset1_name)
        asset2_size = self._round_to_lot_size(asset2_size, asset2_name)
        
        logger.debug(f"Rounded sizes - {asset1_name}: {asset1_size:.8f}, {asset2_name}: {asset2_size:.8f}")
        
        # TRUE PAIRS TRADING: Trade the spread, not individual assets
        # LONG signal = spread too LOW → BUY asset1, SELL asset2 (expecting spread to increase)
        # SHORT signal = spread too HIGH → SELL asset1, BUY asset2 (expecting spread to decrease)
        
        if action == "LONG":  # Long the spread (buy asset1 relative to asset2)
            asset1_side = "BUY"   # Always buy the numerator
            asset2_side = "SELL"  # Always sell the denominator (hedged)
        else:  # SHORT the spread (sell asset1 relative to asset2)
            asset1_side = "SELL"  # Always sell the numerator  
            asset2_side = "BUY"   # Always buy the denominator (hedged)
        
        logger.debug(f"TRUE PAIRS TRADE: {action} spread = {asset1_side} {asset1_name} + {asset2_side} {asset2_name}")
        
        result = {
            "asset1": {
                "symbol": symbol1,
                "side": asset1_side,
                "size": asset1_size,
                "entry_price": asset1_price,
                "dollar_value": asset1_dollar_allocation,
                "name": asset1_name
            },
            "asset2": {
                "symbol": symbol2,
                "side": asset2_side,
                "size": asset2_size,
                "entry_price": asset2_price,
                "dollar_value": asset2_dollar_allocation,
                "name": asset2_name
            },
            # Backward compatibility aliases
            "btc": {
                "symbol": symbol1,
                "side": asset1_side,
                "size": asset1_size,
                "entry_price": asset1_price,
                "dollar_value": asset1_dollar_allocation
            },
            "eth": {
                "symbol": symbol2,
                "side": asset2_side,
                "size": asset2_size,
                "entry_price": asset2_price,
                "dollar_value": asset2_dollar_allocation
            },
            "total_allocated": allocated_capital,
            "hedge_ratio": beta
        }
        
        logger.info(f"PAIRS TRADE POSITIONS - {asset1_name}: {asset1_side} ${result['asset1']['dollar_value']:.2f}, {asset2_name}: {asset2_side} ${result['asset2']['dollar_value']:.2f} (Spread {action})")
        return result

    async def execute_pairs_trade(self, signal_data, channel):
        """Execute pairs trade using cross margin"""
        logger.info(f"Executing pairs trade for signal: {signal_data.get('signal_id', 'UNKNOWN')}")
        
        # Get account balance (cross margin)
        logger.debug("Fetching account information for capital calculation...")
        account_info = self.client.margin_account()
        total_capital = self.extract_total_capital(account_info, signal_data)
        
        positions = self.calculate_pair_positions(signal_data, total_capital)
        logger.debug(f"Calculated positions: {positions}")
        
        # Place both orders - use MARKET for testing with small capital
        asset1_params = {
            "symbol": positions["asset1"]["symbol"],
            "side": positions["asset1"]["side"],
            "type": "MARKET",
            "quantity": str(positions["asset1"]["size"]),
            "sideEffectType": "AUTO_BORROW_REPAY"
        }
        
        asset2_params = {
            "symbol": positions["asset2"]["symbol"],
            "side": positions["asset2"]["side"],
            "type": "MARKET",
            "quantity": str(positions["asset2"]["size"]),
            "sideEffectType": "AUTO_BORROW_REPAY"
        }
        
        logger.debug(f"Asset1 ({positions['asset1']['name']}) order params: {asset1_params}")
        logger.debug(f"Asset2 ({positions['asset2']['name']}) order params: {asset2_params}")
        
        try:
            logger.info(f"Placing {positions['asset1']['name']} leg of pairs trade...")
            asset1_order = self.client.new_margin_order(**asset1_params)
            logger.info(f"{positions['asset1']['name']} order filled: ID {asset1_order.get('orderId', 'UNKNOWN')}")
            
            logger.info(f"Placing {positions['asset2']['name']} leg of pairs trade...")
            asset2_order = self.client.new_margin_order(**asset2_params)
            logger.info(f"{positions['asset2']['name']} order filled: ID {asset2_order.get('orderId', 'UNKNOWN')}")
            
            await channel.send(f"✅ Pairs trade executed:\n{positions['asset1']['name']}: {asset1_order['orderId']}\n{positions['asset2']['name']}: {asset2_order['orderId']}")
            
            # Monitor execution  
            logger.debug("Starting execution monitoring...")
            await self.monitor_pairs_execution(asset1_order, asset2_order, signal_data, channel, positions)
            
        except Exception as e:
            logger.error(f"Pairs trade execution failed: {e}")
            await channel.send(f"❌ Pairs trade failed: {str(e)}")

    async def monitor_pairs_execution(self, asset1_order, asset2_order, signal_data, channel, positions):
        """Monitor fills and handle partial execution"""
        logger.debug("Monitoring pairs execution status...")
        await asyncio.sleep(5)
        
        try:
            # Check status (no isIsolated parameter)
            asset1_symbol = positions["asset1"]["symbol"]
            asset2_symbol = positions["asset2"]["symbol"]
            asset1_name = positions["asset1"]["name"]
            asset2_name = positions["asset2"]["name"]
            
            logger.debug(f"Checking {asset1_name} order status...")
            asset1_status = self.client.query_margin_order(
                symbol=asset1_symbol,
                orderId=asset1_order['orderId']
            )
            
            logger.debug(f"Checking {asset2_name} order status...")
            asset2_status = self.client.query_margin_order(
                symbol=asset2_symbol,
                orderId=asset2_order['orderId']
            )
            
            asset1_filled = asset1_status['status'] == 'FILLED'
            asset2_filled = asset2_status['status'] == 'FILLED'
            
            logger.info(f"Order status - {asset1_name}: {asset1_status['status']}, {asset2_name}: {asset2_status['status']}")
            
            if asset1_filled and asset2_filled:
                logger.info("Both legs filled successfully")
                await channel.send("✅ Both legs filled")
                # Set up OCO orders here
            elif asset1_filled or asset2_filled:
                logger.warning("PARTIAL FILL DETECTED - Only one leg filled")
                await channel.send("⚠️ Only one leg filled - emergency exit")
                # Handle partial fill
            else:
                logger.warning("Orders not filled - executing cancellation")
                await channel.send("⏰ Orders not filled - cancelling")
                self.client.cancel_margin_order(symbol=asset1_symbol, orderId=asset1_order['orderId'])
                self.client.cancel_margin_order(symbol=asset2_symbol, orderId=asset2_order['orderId'])
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
        
        # Calculate TRUE PAIRS TRADING positions with proper hedging
        account_info = self.client.margin_account()
        total_capital = self.extract_total_capital(account_info, signal_data)
        positions = self.calculate_pair_positions(signal_data, total_capital)
        
        # Extract the calculated amounts and sides (now properly hedged)
        asset1_amount = positions['asset1']['size']
        asset2_amount = positions['asset2']['size'] 
        asset1_side = positions['asset1']['side']
        asset2_side = positions['asset2']['side']
        
        logger.info(f"Executing TRUE PAIRS TRADE: {asset1_side} {asset1_amount} {positions['asset1']['name']} + {asset2_side} {asset2_amount} {positions['asset2']['name']}")
        
        # Execute TRUE pairs trade with spread monitoring
        await self.true_pairs_trade_execution(asset1_amount, asset2_amount, asset1_side, asset2_side, channel=channel, signal_data=signal_data)

    async def true_pairs_trade_execution(self, asset1_amount: float, asset2_amount: float, asset1_side: str, asset2_side: str, channel, signal_data: dict):
        """
        Execute TRUE PAIRS TRADE with proper spread hedging
        
        This implements actual pairs trading by:
        1. Taking opposite positions in two correlated assets
        2. Using beta hedge ratio to maintain market neutrality
        3. Profiting from spread convergence, not directional moves
        4. Monitoring the spread for exit conditions
        
        Args:
            asset1_amount: Amount of first asset (numerator)
            asset2_amount: Amount of second asset (denominator, beta-adjusted)
            asset1_side: First asset side (opposite of asset2_side)
            asset2_side: Second asset side (opposite of asset1_side) 
            channel: Discord channel to send updates to
            signal_data: Signal data containing spread info and thresholds
        """
        logger.info(f"Executing TRUE PAIRS TRADE - Asset1: {asset1_side} {asset1_amount}, Asset2: {asset2_side} {asset2_amount}")
        
        try:
            # Extract symbols from signal data - NO MORE DUMMY SIGNALS!
            if signal_data:
                pair_str = signal_data.get('pair', 'BTCUSDC/ETHUSDC')
                asset1_symbol, asset2_symbol = pair_str.split('/')
                asset1_name = asset1_symbol.replace('USDC', '').replace('USDT', '')
                asset2_name = asset2_symbol.replace('USDC', '').replace('USDT', '')
                
                # Use prices from signal data (more accurate and faster)
                asset1_price = signal_data.get('asset1_price', 0)
                asset2_price = signal_data.get('asset2_price', 0)
                
                logger.debug(f"Using signal symbols: {asset1_symbol}, {asset2_symbol}")
                logger.debug(f"Using signal prices: {asset1_name} ${asset1_price:.2f}, {asset2_name} ${asset2_price:.2f}")
            else:
                # Fallback to BTC/ETH for backward compatibility
                asset1_symbol, asset2_symbol = "BTCUSDC", "ETHUSDC"
                asset1_name, asset2_name = "BTC", "ETH"
                
                # Fetch live prices
                asset1_ticker = self.client.ticker_price(symbol=asset1_symbol)
                asset2_ticker = self.client.ticker_price(symbol=asset2_symbol)
                asset1_price = float(asset1_ticker["price"])
                asset2_price = float(asset2_ticker["price"])
                
                logger.warning("No signal data provided, using BTC/ETH fallback")
            
            # Check minimum notionals
            logger.debug("Checking minimum notional requirements...")
            
            asset1_notional = asset1_amount * asset1_price
            asset2_notional = asset2_amount * asset2_price
            
            min_notional = 5  # Binance minimum is usually ~$5
            
            logger.debug(f"Order notionals - {asset1_name}: ${asset1_notional:.2f}, {asset2_name}: ${asset2_notional:.2f}")
            
            if asset1_notional < min_notional:
                logger.error(f"{asset1_name} order below minimum notional: ${asset1_notional:.2f} < ${min_notional}")
                await channel.send(f"❌ {asset1_name} order too small: ${asset1_notional:.2f} < ${min_notional}")
                return {"success": False, "error": f"{asset1_name} notional too small"}
                
            if asset2_notional < min_notional:
                logger.error(f"{asset2_name} order below minimum notional: ${asset2_notional:.2f} < ${min_notional}")
                await channel.send(f"❌ {asset2_name} order too small: ${asset2_notional:.2f} < ${min_notional}")
                return {"success": False, "error": f"{asset2_name} notional too small"}
            
            await channel.send(f"📊 PAIRS TRADE: {asset1_name}=${asset1_notional:.2f} ({asset1_side}), {asset2_name}=${asset2_notional:.2f} ({asset2_side})")
        
            # PAIRS ENTRY: Execute both legs simultaneously for proper hedging
            logger.info(f"Placing PAIRS TRADE LEG 1: {asset1_name} {asset1_side} {asset1_amount}")
            first_order = self.client.new_margin_order(
                symbol=asset1_symbol,
                side=asset1_side.upper(),
                type="MARKET",
                quantity=str(asset1_amount),
                sideEffectType="AUTO_BORROW_REPAY"
            )
            logger.info(f"PAIRS LEG 1 executed: {asset1_name} {asset1_side} - ID {first_order['orderId']}")
            await channel.send(f"✅ PAIRS LEG 1: {asset1_name} {asset1_side} - {first_order['orderId']}")
            
            logger.info(f"Placing PAIRS TRADE LEG 2: {asset2_name} {asset2_side} {asset2_amount}")
            second_order = self.client.new_margin_order(
                symbol=asset2_symbol,
                side=asset2_side.upper(),
                type="MARKET",
                quantity=str(asset2_amount),
                sideEffectType="AUTO_BORROW_REPAY"
            )
            logger.info(f"PAIRS LEG 2 executed: {asset2_name} {asset2_side} - ID {second_order['orderId']}")
            await channel.send(f"✅ PAIRS LEG 2: {asset2_name} {asset2_side} - {second_order['orderId']}")
            
            # Calculate executed spread for monitoring
            executed_asset1_price = float(first_order['cummulativeQuoteQty']) / float(first_order['executedQty'])
            executed_asset2_price = float(second_order['cummulativeQuoteQty']) / float(second_order['executedQty'])
            
            # Calculate actual spread at execution
            import math
            beta = signal_data.get('beta', 1.0)
            executed_spread = math.log(executed_asset1_price) - beta * math.log(executed_asset2_price)
            
            logger.info(f"PAIRS EXECUTION - {asset1_name}: ${executed_asset1_price:.4f}, {asset2_name}: ${executed_asset2_price:.4f}")
            logger.info(f"EXECUTED SPREAD: {executed_spread:.6f} (Target: {signal_data.get('spread', 'N/A'):.6f})")
            
            # PAIRS TRADING: Set spread-based exit targets (not individual asset TP/SL)
            current_spread = executed_spread
            target_spread = signal_data.get('mu', 0)  # Mean reversion target
            spread_threshold = signal_data.get('threshold', 0.01)
            
            # Calculate spread-based exit levels
            if signal_data.get('action') == 'LONG':  # Long spread
                target_spread_exit = current_spread + (spread_threshold * self.TAKE_PROFIT_FACTOR)
                stop_spread_exit = current_spread - (spread_threshold * self.STOP_LOSS_FACTOR)
            else:  # Short spread
                target_spread_exit = current_spread - (spread_threshold * self.TAKE_PROFIT_FACTOR)
                stop_spread_exit = current_spread + (spread_threshold * self.STOP_LOSS_FACTOR)
            
            logger.info(f"SPREAD TARGETS - Current: {current_spread:.6f}, TP: {target_spread_exit:.6f}, SL: {stop_spread_exit:.6f}")
            
            # AUTOMATED SPREAD-BASED EXIT SYSTEM
            # Store position data for spread monitoring
            position_id = f"pairs_{int(datetime.now().timestamp())}"
            
            position_data = {
                'position_id': position_id,
                'asset1_symbol': asset1_symbol,
                'asset2_symbol': asset2_symbol,
                'asset1_side': asset1_side,
                'asset2_side': asset2_side,
                'asset1_amount': asset1_amount,
                'asset2_amount': asset2_amount,
                'beta': beta,
                'entry_spread': current_spread,
                'target_spread': target_spread_exit,
                'stop_spread': stop_spread_exit,
                'entry_time': datetime.now(),
                'signal_action': signal_data.get('action'),
                'status': 'ACTIVE'
            }
            
            # Store for monitoring (you'd save this to a database in production)
            if not hasattr(self, 'active_pairs_positions'):
                self.active_pairs_positions = {}
            self.active_pairs_positions[position_id] = position_data
            
            # Start automated monitoring
            asyncio.create_task(self.monitor_pairs_spread(position_data, channel))
            
            await channel.send(
                f"🎯 **PAIRS TRADE ACTIVE** (ID: {position_id})\n"
                f"📊 Entry Spread: {current_spread:.6f}\n"
                f"🎯 Profit Target: {target_spread_exit:.6f}\n"
                f"🛑 Stop Loss: {stop_spread_exit:.6f}\n"
                f"🤖 **Automated spread monitoring active**"
            )
            
            logger.info(f"AUTOMATED PAIRS MONITORING: Position {position_id} started")
            logger.info(f"Will exit when spread hits {target_spread_exit:.6f} (profit) or {stop_spread_exit:.6f} (stop)")
            
            # Create TRUE PAIRS TRADE summary
            embed = discord.Embed(
                title="🔄 TRUE PAIRS TRADE EXECUTED", 
                description="Spread-based hedged position",
                color=discord.Color.gold(),
                timestamp=datetime.now()
            )
            embed.add_field(
                name=f"LEG 1: {asset1_name}", 
                value=f"{asset1_side} @ ${executed_asset1_price:.4f}\nSize: {asset1_amount:.6f}", 
                inline=True
            )
            embed.add_field(
                name=f"LEG 2: {asset2_name}", 
                value=f"{asset2_side} @ ${executed_asset2_price:.4f}\nSize: {asset2_amount:.6f}", 
                inline=True
            )
            embed.add_field(
                name="Spread Analysis", 
                value=f"Entry: {current_spread:.6f}\nTarget: {target_spread_exit:.6f}\nBeta: {beta:.4f}", 
                inline=True
            )
            
            await channel.send(embed=embed)
            
            result = {
                "success": True,
                "pairs_trade": True,
                "asset1_order_id": first_order['orderId'],
                "asset2_order_id": second_order['orderId'],
                "asset1_price": executed_asset1_price,
                "asset2_price": executed_asset2_price,
                "executed_spread": executed_spread,
                "target_spread": target_spread_exit,
                "stop_spread": stop_spread_exit,
                "beta": beta
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
            total_capital = self.extract_total_capital(account_info, test_signal)
            positions = self.calculate_pair_positions(test_signal, total_capital, allocation_pct)
            
            result_message = f"""
**Test Position Calculation:**
Total Capital: ${total_capital:.2f}
Allocated ({allocation_pct*100}%): ${positions['total_allocated']:.2f}
{positions['asset1']['name']}: {positions['asset1']['side']} {positions['asset1']['size']:.8f} @ ${positions['asset1']['entry_price']}
{positions['asset2']['name']}: {positions['asset2']['side']} {positions['asset2']['size']:.8f} @ ${positions['asset2']['entry_price']}
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
            total_capital = self.extract_total_capital(account_info, test_signal)
            
            # Calculate positions (will use BTCUSDT/ETHUSDT from test_signal)
            positions = self.calculate_pair_positions(test_signal, total_capital, allocation_pct)
            # Symbols are already set correctly from test_signal pair data
            
            logger.info(f"Calculated positions for live test: BTC {positions['btc']['side']} ${positions['btc']['dollar_value']:.2f}, ETH {positions['eth']['side']} ${positions['eth']['dollar_value']:.2f}")
            
            await ctx.send(f"""
**About to place:**
{positions['asset1']['name']}: {positions['asset1']['side']} {positions['asset1']['size']:.8f} (${positions['asset1']['dollar_value']:.2f})
{positions['asset2']['name']}: {positions['asset2']['side']} {positions['asset2']['size']:.8f} (${positions['asset2']['dollar_value']:.2f})
            """)
            
            # Place orders sequentially with error handling
            try:
                logger.info(f"Placing live {positions['asset1']['name']} order...")
                asset1_params = {
                    "symbol": positions["asset1"]["symbol"],
                    "side": positions["asset1"]["side"],
                    "type": "MARKET",
                    "quantity": str(positions["asset1"]["size"]),
                    "sideEffectType": "AUTO_BORROW_REPAY"
                }
                asset1_order = self.client.new_margin_order(**asset1_params)
                logger.info(f"Live {positions['asset1']['name']} order successful: ID {asset1_order['orderId']}")
                await ctx.send(f"✅ {positions['asset1']['name']} order placed: {asset1_order['orderId']}")
            except Exception as e:
                logger.error(f"Live {positions['asset1']['name']} order failed: {e}")
                await ctx.send(f"❌ {positions['asset1']['name']} failed: {e}")
                return
            
            try:
                logger.info(f"Placing live {positions['asset2']['name']} order...")
                asset2_params = {
                    "symbol": positions["asset2"]["symbol"],
                    "side": positions["asset2"]["side"],
                    "type": "MARKET",
                    "quantity": str(positions["asset2"]["size"]),
                    "sideEffectType": "AUTO_BORROW_REPAY"
                }
                asset2_order = self.client.new_margin_order(**asset2_params)
                logger.info(f"Live {positions['asset2']['name']} order successful: ID {asset2_order['orderId']}")
                await ctx.send(f"✅ {positions['asset2']['name']} order placed: {asset2_order['orderId']}")
            except Exception as e:
                logger.error(f"Live {positions['asset2']['name']} order failed, reversing {positions['asset1']['name']}: {e}")
                await ctx.send(f"❌ {positions['asset2']['name']} failed: {e}")
                # Reverse first asset if second asset fails
                reverse_params = {
                    "symbol": positions["asset1"]["symbol"],
                    "side": "BUY" if positions["asset1"]["side"] == "SELL" else "SELL",
                    "type": "MARKET",
                    "quantity": str(positions["asset1"]["size"]),
                    "sideEffectType": "AUTO_BORROW_REPAY"
                }
                self.client.new_margin_order(**reverse_params)
                logger.warning(f"{positions['asset1']['name']} position reversed due to {positions['asset2']['name']} failure")
                await ctx.send(f"🔄 Reversed {positions['asset1']['name']} position")
                
            logger.info(f"Live pairs test completed for {ctx.author.name}")
            
        except Exception as e:
            logger.error(f"Live test failed for {ctx.author.name}: {e}")
            await ctx.send(f"❌ Test failed: {e}")

    async def monitor_pairs_spread(self, position_data: dict, channel):
        """Monitor spread and automatically exit pairs position when targets hit"""
        position_id = position_data['position_id']
        logger.info(f"Starting spread monitoring for pairs position {position_id}")
        
        check_interval = 60  # Check every minute
        max_monitoring_hours = 24  # Stop monitoring after 24 hours
        checks_performed = 0
        max_checks = (max_monitoring_hours * 3600) // check_interval
        
        try:
            while checks_performed < max_checks:
                await asyncio.sleep(check_interval)
                checks_performed += 1
                
                # Check if position still exists and is active
                if (position_id not in self.active_pairs_positions or 
                    self.active_pairs_positions[position_id]['status'] != 'ACTIVE'):
                    logger.info(f"Position {position_id} no longer active, stopping monitoring")
                    break
                
                # Get current prices
                try:
                    asset1_ticker = self.client.ticker_price(symbol=position_data['asset1_symbol'])
                    asset2_ticker = self.client.ticker_price(symbol=position_data['asset2_symbol'])
                    
                    current_asset1_price = float(asset1_ticker['price'])
                    current_asset2_price = float(asset2_ticker['price'])
                    
                    # Calculate current spread
                    import math
                    current_spread = math.log(current_asset1_price) - position_data['beta'] * math.log(current_asset2_price)
                    
                    logger.debug(f"Position {position_id}: Current spread {current_spread:.6f} (Entry: {position_data['entry_spread']:.6f})")
                    
                    # Check exit conditions
                    should_exit = False
                    exit_reason = ""
                    
                    # Profit target hit
                    if position_data['signal_action'] == 'LONG':
                        if current_spread >= position_data['target_spread']:
                            should_exit = True
                            exit_reason = "PROFIT TARGET - Spread increased as expected"
                        elif current_spread <= position_data['stop_spread']:
                            should_exit = True
                            exit_reason = "STOP LOSS - Spread decreased against position"
                    else:  # SHORT
                        if current_spread <= position_data['target_spread']:
                            should_exit = True
                            exit_reason = "PROFIT TARGET - Spread decreased as expected"
                        elif current_spread >= position_data['stop_spread']:
                            should_exit = True
                            exit_reason = "STOP LOSS - Spread increased against position"
                    
                    # Execute exit if conditions met
                    if should_exit:
                        logger.info(f"PAIRS EXIT TRIGGERED: {exit_reason}")
                        await self.execute_pairs_exit(position_data, current_spread, exit_reason, channel)
                        break
                    
                    # Progress update every 2 minutes
                    if checks_performed % 2 == 0:
                        spread_move = current_spread - position_data['entry_spread']
                        await channel.send(
                            f"📊 Pairs Monitor ({position_id[:8]}): Spread {current_spread:.6f} "
                            f"({spread_move:+.6f} from entry)"
                        )
                    
                except Exception as e:
                    logger.error(f"Error checking spread for position {position_id}: {e}")
                    await asyncio.sleep(check_interval)  # Wait before retry
                    continue
            
            # Timeout exit
            if checks_performed >= max_checks:
                logger.warning(f"Position {position_id} monitoring timeout after {max_monitoring_hours}h")
                await self.execute_pairs_exit(position_data, None, "TIME LIMIT - 24h monitoring timeout", channel)
                
        except Exception as e:
            logger.error(f"Critical error in pairs monitoring for {position_id}: {e}")
            await channel.send(f"❌ Monitoring error for {position_id[:8]}: {str(e)}")
    
    async def execute_pairs_exit(self, position_data: dict, exit_spread: float, reason: str, channel):
        """Close both legs of the pairs trade simultaneously"""
        position_id = position_data['position_id']
        
        try:
            logger.info(f"EXECUTING PAIRS EXIT: {position_id} - {reason}")
            
            # Close both positions simultaneously
            # Leg 1: Close first asset position
            exit_side1 = "SELL" if position_data['asset1_side'] == "BUY" else "BUY"
            leg1_order = self.client.new_margin_order(
                symbol=position_data['asset1_symbol'],
                side=exit_side1,
                type="MARKET",
                quantity=str(position_data['asset1_amount']),
                sideEffectType="AUTO_BORROW_REPAY"
            )
            
            # Leg 2: Close second asset position  
            exit_side2 = "SELL" if position_data['asset2_side'] == "BUY" else "BUY"
            leg2_order = self.client.new_margin_order(
                symbol=position_data['asset2_symbol'],
                side=exit_side2,
                type="MARKET",
                quantity=str(position_data['asset2_amount']),
                sideEffectType="AUTO_BORROW_REPAY"
            )
            
            # Calculate P&L
            entry_spread = position_data['entry_spread']
            spread_change = exit_spread - entry_spread if exit_spread else 0
            
            # Update position status
            self.active_pairs_positions[position_id]['status'] = 'CLOSED'
            self.active_pairs_positions[position_id]['exit_spread'] = exit_spread
            self.active_pairs_positions[position_id]['exit_reason'] = reason
            self.active_pairs_positions[position_id]['exit_time'] = datetime.now()
            
            # Send completion message
            embed = discord.Embed(
                title="🏁 PAIRS TRADE CLOSED",
                description=f"Position {position_id[:8]} exited",
                color=discord.Color.green() if "PROFIT" in reason else discord.Color.orange(),
                timestamp=datetime.now()
            )
            
            embed.add_field(
                name="Exit Reason", 
                value=reason, 
                inline=False
            )
            
            if exit_spread:
                embed.add_field(
                    name="Spread Performance",
                    value=f"Entry: {entry_spread:.6f}\nExit: {exit_spread:.6f}\nChange: {spread_change:+.6f}",
                    inline=True
                )
            
            embed.add_field(
                name="Orders Executed",
                value=f"Leg 1: {leg1_order['orderId']}\nLeg 2: {leg2_order['orderId']}",
                inline=True
            )
            
            await channel.send(embed=embed)
            
            logger.info(f"PAIRS EXIT COMPLETE: {position_id} - Both legs closed successfully")
            
        except Exception as e:
            logger.error(f"ERROR IN PAIRS EXIT: {position_id} - {e}")
            await channel.send(f"❌ **CRITICAL**: Failed to close pairs position {position_id[:8]}: {str(e)}")
            # Mark as error for manual intervention
            if position_id in self.active_pairs_positions:
                self.active_pairs_positions[position_id]['status'] = 'ERROR'
    
    @commands.command(name="pairslist")
    async def list_active_pairs(self, ctx):
        """List all active pairs trading positions"""
        if not hasattr(self, 'active_pairs_positions') or not self.active_pairs_positions:
            await ctx.send("No active pairs positions")
            return
        
        embed = discord.Embed(title="Active Pairs Positions", color=discord.Color.blue())
        
        for pos_id, pos_data in self.active_pairs_positions.items():
            if pos_data['status'] == 'ACTIVE':
                runtime = datetime.now() - pos_data['entry_time']
                embed.add_field(
                    name=f"Position {pos_id[:8]}",
                    value=f"Pair: {pos_data['asset1_symbol']}/{pos_data['asset2_symbol']}\n"
                          f"Action: {pos_data['signal_action']}\n"
                          f"Runtime: {runtime.seconds//60}m",
                    inline=True
                )
        
        await ctx.send(embed=embed)
    
    @commands.command(name="closepairs")
    async def manual_close_pairs(self, ctx, position_id: str = None):
        """Manually close a specific pairs position or all positions"""
        if not hasattr(self, 'active_pairs_positions'):
            await ctx.send("No pairs positions found")
            return
        
        if position_id:
            # Close specific position
            if position_id not in self.active_pairs_positions:
                await ctx.send(f"Position {position_id} not found")
                return
            
            pos_data = self.active_pairs_positions[position_id]
            if pos_data['status'] != 'ACTIVE':
                await ctx.send(f"Position {position_id} is not active (status: {pos_data['status']})")
                return
            
            await self.execute_pairs_exit(pos_data, None, "MANUAL CLOSE - User requested", ctx.channel)
        else:
            # Close all active positions
            active_positions = [p for p in self.active_pairs_positions.values() if p['status'] == 'ACTIVE']
            if not active_positions:
                await ctx.send("No active pairs positions to close")
                return
            
            await ctx.send(f"Closing {len(active_positions)} active pairs positions...")
            
            for pos_data in active_positions:
                await self.execute_pairs_exit(pos_data, None, "MANUAL CLOSE ALL - User requested", ctx.channel)
                await asyncio.sleep(1)  # Small delay between closures


    # Command to log trades
    @commands.command(name="savelogs")
    @commands.is_owner()  # Restrict this command to the bot owner for safety
    async def save_logs(self, ctx):
        """Saves all captured logs to an Excel file."""
        logger.info(f"Log save command initiated by {ctx.author.name}")
        
        # This message is helpful for long-running bots with many logs
        await ctx.send("Saving logs... this may take a moment.")
        
        # Call the method from our sink instance
        result_message = self.log_sink.save_to_excel()
        
        await ctx.send(result_message)
        
        # Optional: If you want to also send the file to Discord
        try:
            # The filename is the last word in the success message
            filename = result_message.split("`")[-2]
            await ctx.send(file=discord.File(filename))
        except Exception as e:
            logger.warning(f"Could not send log file to Discord: {e}")
            # This might fail if the file is too large for Discord's limits
            await ctx.send("Could not upload file to Discord (it may be too large).")

async def setup(bot):
    """Add the cross margin cog to the bot"""
    logger.info("Setting up CrossMarginBot cog...")
    await bot.add_cog(CrossMarginBot(bot))
    logger.info("CrossMarginBot cog setup complete")
