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
import math

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

        # 1. Create an instance of our new sink
        self.log_sink = PandasLogSink()
        # 2. Tell loguru to send all logs (INFO and higher) to our custom sink
        logger.add(self.log_sink._sink, level="INFO", format="{message}")
        
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

        # In-memory storage for active pairs trades
        self.active_pairs_positions = {}

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
            logger.debug("Making API call to margin_account()")
            response = self.client.margin_account()
            logger.debug(f"API response received successfully - account data retrieved")

            margin_level = float(response.get("marginLevel", "999"))
            total_asset_btc = float(response.get("totalAssetOfBtc", "0"))
            total_liability_btc = float(response.get("totalLiabilityOfBtc", "0"))
            total_net_asset_btc = float(response.get("totalNetAssetOfBtc", "0"))
            
            logger.info(f"Account metrics - Margin Level: {margin_level:.2f}×, Net Assets: {total_net_asset_btc:.8f} BTC")
            
            if margin_level == 999:
                color = discord.Color.green()
            elif margin_level > 3:
                color = discord.Color.green()
            elif margin_level > 1.5:
                color = discord.Color.gold()
                logger.warning(f"Account margin level is moderate risk: {margin_level:.2f}×")
            else:
                color = discord.Color.red()
                logger.error(f"CRITICAL: Account margin level is high risk: {margin_level:.2f}×")
            
            embed = discord.Embed(
                title="Cross Margin Account Summary",
                description="All assets in shared collateral pool",
                color=color,
                timestamp=datetime.now()
            )
            
            logger.debug("Fetching BTC price for USD conversion...")
            ticker = self.client.ticker_price(symbol="BTCUSDT")
            btc_price = float(ticker["price"])
            logger.debug(f"BTC price: ${btc_price:.2f}")
            
            embed.add_field(
                name="Account Health",
                value=(
                    f"**Margin Level:** {margin_level:.2f}×\n"
                    f"**Total Assets:** {total_asset_btc:.8f} BTC (${total_asset_btc * btc_price:,.2f})\n"
                    f"**Total Liabilities:** {total_liability_btc:.8f} BTC (${total_liability_btc * btc_price:,.2f})\n"
                    f"**Net Value:** {total_net_asset_btc:.8f} BTC (${total_net_asset_btc * btc_price:,.2f})"
                ),
                inline=False
            )
            
            user_assets = response.get("userAssets", [])
            significant_assets = [a for a in user_assets if float(a.get("netAsset", 0)) > 0.00001]
            logger.debug(f"Found {len(significant_assets)} significant assets out of {len(user_assets)} total")
            
            for asset in significant_assets[:6]:
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
            if symbol:
                logger.debug(f"Querying open orders for specific symbol: {symbol.upper()}")
                orders = self.client.margin_open_orders(symbol=symbol.upper())
            else:
                logger.debug("Querying all open margin orders")
                orders = self.client.margin_open_orders()
            
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
            
            by_symbol = {}
            for order in orders:
                sym = order.get("symbol", "UNKNOWN")
                if sym not in by_symbol:
                    by_symbol[sym] = []
                by_symbol[sym].append(order)
            
            logger.debug(f"Orders grouped across {len(by_symbol)} symbols")
            
            for symbol, symbol_orders in list(by_symbol.items())[:5]:
                orders_text = ""
                for order in symbol_orders[:3]:
                    side = order.get("side", "")
                    qty = order.get("origQty", "0")
                    price = float(order.get("price", 0))
                    emoji = "🟢" if side == "BUY" else "🔴"
                    
                    orders_text += f"{emoji} {side} {qty} @ ${price:,.2f}\n"
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
    @commands.has_role("Trading-Authorized")
    async def cancel_all_orders(self, ctx, symbol: str):
        """Cancel all open orders for a symbol in cross margin"""
        logger.warning(f"CANCEL ALL ORDERS initiated by {ctx.author.name} for {symbol.upper()}")
        
        try:
            logger.debug(f"Executing mass cancellation for {symbol.upper()}")
            response = self.client.margin_open_orders_cancellation(symbol=symbol.upper())
            logger.info(f"Successfully cancelled all orders for {symbol.upper()} - Response: {response}")
            await ctx.send(f"✅ Cancelled all orders for {symbol.upper()}")
        except Exception as e:
            logger.error(f"Failed to cancel orders for {symbol.upper()}: {e}")
            await ctx.send(f"❌ Error: {str(e)}")

    # ==================== ORDER PLACEMENT COMMANDS ====================

    @commands.command(name="order", aliases=["mo"])
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.has_role("Trading-Authorized")
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
            "sideEffectType": side_effect.upper()
        }
        
        logger.debug(f"Order parameters: {params}")
        
        try:
            logger.debug("Sending market order to Binance API...")
            order = self.client.new_margin_order(**params)
            
            order_id = order.get('orderId', 'UNKNOWN')
            executed_qty = order.get('executedQty', '0')
            executed_price = float(order.get('cummulativeQuoteQty', 0)) / float(executed_qty) if float(executed_qty) > 0 else 0
            
            logger.info(f"MARKET ORDER SUCCESS: ID {order_id}, Executed {executed_qty} @ ${executed_price:,.2f}")
            await ctx.send(f"✅ Order placed! ID: {order_id}")
            
        except Exception as e:
            logger.error(f"MARKET ORDER FAILED for {ctx.author.name}: {symbol} {side} {quantity} - Error: {str(e)}")
            await ctx.send(f"❌ Order failed: {str(e)}")

    # ==================== PAIRS TRADING CORE LOGIC ====================

    def extract_total_capital(self, account_info, signal_data=None):
        """Extract total USD value from cross margin account"""
        logger.debug("Extracting total capital from account info...")
        
        user_assets = account_info.get("userAssets", [])
        total_usd = 0
        
        logger.debug("Fetching current prices for capital calculation...")
        prices = {}
        if signal_data:
            pair_str = signal_data.get('pair', 'BTCUSDC/ETHUSDC')
            asset1_symbol, asset2_symbol = self.extract_assets_from_pair(pair_str)
            prices[asset1_symbol] = signal_data.get('asset1_price', 0)
            prices[asset2_symbol] = signal_data.get('asset2_price', 0)
            logger.debug(f"Using signal prices - {asset1_symbol}: ${prices[asset1_symbol]:,.2f}, {asset2_symbol}: ${prices[asset2_symbol]:,.2f}")
        else:
            try:
                btc_ticker = self.client.ticker_price(symbol="BTCUSDT")
                prices["BTC"] = float(btc_ticker["price"])
                eth_ticker = self.client.ticker_price(symbol="ETHUSDT")
                prices["ETH"] = float(eth_ticker["price"])
                logger.debug(f"Using fallback prices - BTC: ${prices['BTC']:,.2f}, ETH: ${prices['ETH']:,.2f}")
            except Exception as e:
                logger.error(f"Could not fetch fallback prices: {e}")
                return 0

        for asset in user_assets:
            asset_name = asset["asset"]
            net_amount = float(asset.get("netAsset", 0))
            
            if net_amount > 0:
                if asset_name in ["USDT", "USDC"]:
                    total_usd += net_amount
                    logger.debug(f"Added ${net_amount:,.2f} from {asset_name}")
                elif asset_name in prices:
                    usd_value = net_amount * prices[asset_name]
                    total_usd += usd_value
                    logger.debug(f"Added ${usd_value:,.2f} from {net_amount:.8f} {asset_name}")
        
        logger.info(f"Total account capital calculated: ${total_usd:,.2f}")
        return total_usd

    def _round_to_lot_size(self, quantity: float, asset_name: str) -> float:
        """Round quantity to appropriate lot size for the asset"""
        lot_sizes = {
            'BTC': 5, 'ETH': 3, 'AVAX': 1, 'POL': 0, 'MATIC': 0,
            'ADA': 0, 'DOT': 1, 'LINK': 1, 'UNI': 1, 'AAVE': 2, 'SOL': 2,
        }
        decimals = lot_sizes.get(asset_name, 3)
        rounded = round(quantity, decimals)
        logger.debug(f"Rounded {asset_name} quantity: {quantity:.8f} → {rounded:.8f}")
        return rounded
    
    def extract_assets_from_pair(self, pair_str: str) -> tuple:
        """Extract asset names from pair string like 'AVAXUSDC/POLUSDC' -> ('AVAX', 'POL')"""
        try:
            symbol1, symbol2 = pair_str.split('/')
            asset1 = re.sub(r'(USDT|USDC)$', '', symbol1)
            asset2 = re.sub(r'(USDT|USDC)$', '', symbol2)
            logger.debug(f"Extracted assets from '{pair_str}': {asset1}, {asset2}")
            return asset1, asset2
        except Exception as e:
            logger.warning(f"Failed to extract assets from '{pair_str}': {e}. Using BTC/ETH fallback.")
            return "BTC", "ETH"
    
    def calculate_pair_positions(self, signal_data: dict, total_capital: float) -> dict:
        """Calculate position sizes for pairs trading"""
        logger.debug(f"Calculating pair positions with capital: ${total_capital:,.2f}, allocation: {self.CAPITAL_ALLOCATION*100}%")
        
        beta = signal_data['beta']
        asset1_price = signal_data['asset1_price'] 
        asset2_price = signal_data['asset2_price']
        action = signal_data['action']
        
        pair_str = signal_data.get('pair', 'BTCUSDC/ETHUSDC')
        asset1_name, asset2_name = self.extract_assets_from_pair(pair_str)
        symbol1, symbol2 = pair_str.split('/')
        
        logger.debug(f"Signal parameters - Beta: {beta:.4f}, {asset1_name}: ${asset1_price:,.2f}, {asset2_name}: ${asset2_price:,.2f}, Action: {action}")
        
        allocated_capital = total_capital * self.CAPITAL_ALLOCATION
        
        asset1_dollar_allocation = allocated_capital / (1 + abs(beta))
        asset2_dollar_allocation = asset1_dollar_allocation * abs(beta)

        asset1_size = self._round_to_lot_size(asset1_dollar_allocation / asset1_price, asset1_name)
        asset2_size = self._round_to_lot_size(asset2_dollar_allocation / asset2_price, asset2_name)
        
        if action == "LONG":
            asset1_side, asset2_side = "SELL", "BUY"
        else:
            asset1_side, asset2_side = "BUY", "SELL"
        
        logger.debug(f"TRUE PAIRS TRADE: {action} spread = {asset1_side} {asset1_name} + {asset2_side} {asset2_name}")
        
        result = {
            "asset1": {"symbol": symbol1, "side": asset1_side, "size": asset1_size, "entry_price": asset1_price, "dollar_value": asset1_dollar_allocation, "name": asset1_name},
            "asset2": {"symbol": symbol2, "side": asset2_side, "size": asset2_size, "entry_price": asset2_price, "dollar_value": asset2_dollar_allocation, "name": asset2_name},
            "total_allocated": allocated_capital,
            "hedge_ratio": beta
        }
        
        logger.info(f"PAIRS TRADE POSITIONS - {asset1_name}: {asset1_side} ${result['asset1']['dollar_value']:,.2f}, {asset2_name}: {asset2_side} ${result['asset2']['dollar_value']:,.2f} (Spread {action})")
        return result

    # ==================== SIGNAL HANDLING ====================

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot and "TRADING SIGNAL APPROVAL NEEDED" in message.content:
            logger.info(f"Trading signal detected in message {message.id}")
            await self.handle_signal_approval(message)

    async def handle_signal_approval(self, message):
        """Parse and store signal for approval"""
        logger.debug(f"Processing signal approval for message {message.id}")
        
        try:
            from models import TradingSignalApproval
            signal = TradingSignalApproval.from_discord_message(message.content)
            if not signal:
                raise ValueError("Signal could not be parsed from message content.")
            signal_data = signal.model_dump()
        except Exception as e:
            logger.error(f"Failed to parse signal from message {message.id}: {e}")
            return
            
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

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        """Handle signal approval and rejection reactions"""
        if user.bot or str(reaction.emoji) not in ['✅', '❌']:
            return
            
        logger.debug(f"Reaction {reaction.emoji} added by {user.name} to message {reaction.message.id}")
        
        signal_id = next((sid for sid, s in self.pending_signals.items() if s['message_id'] == reaction.message.id), None)
        
        if not signal_id:
            logger.debug("No pending signal found for this reaction")
            return
            
        signal_info = self.pending_signals[signal_id]
        signal_data = signal_info['data']
        logger.info(f"Processing signal {signal_id} reaction {reaction.emoji} from {user.name}")
        
        title, color, status = "", None, ""
        if str(reaction.emoji) == '✅':
            title, color, status = "🚀 SIGNAL APPROVED & EXECUTING", discord.Color.green(), "🔥 Executing trade..."
        else: # '❌'
            title, color, status = "🚫 SIGNAL REJECTED", discord.Color.red(), "🚫 No trade executed"

        embed = discord.Embed(
            title=title,
            description=f"Signal `{signal_id}` processed by {user.display_name}",
            color=color,
            timestamp=datetime.now()
        )
        embed.add_field(name="Action", value=signal_data.get('action', 'N/A'), inline=True)
        embed.add_field(name="Pair", value=signal_data.get('pair', 'N/A'), inline=True)
        embed.add_field(name="Status", value=status, inline=True)
        embed.set_footer(text=f"Processed by {user.display_name}", icon_url=user.avatar.url if user.avatar else None)
        
        await reaction.message.channel.send(embed=embed)
        
        try:
            await reaction.message.clear_reactions()
            logger.debug("Reactions cleared successfully")
        except discord.Forbidden:
            logger.warning("Could not remove reactions - insufficient permissions")

        # Execute if approved, then remove from pending list
        if str(reaction.emoji) == '✅':
            logger.info(f"Executing approved signal {signal_id}")
            await self.execute_signal_as_pairs_trade(signal_data, reaction.message.channel)
        
        del self.pending_signals[signal_id]
        logger.debug(f"Signal {signal_id} removed from pending signals")

    # ==================== PAIRS TRADING EXECUTION & MONITORING ====================

    async def execute_signal_as_pairs_trade(self, signal_data, channel):
        """Convert signal parameters to pairs trade execution"""
        logger.info(f"Converting signal {signal_data.get('signal_id', 'UNKNOWN')} to pairs trade")
        
        try:
            account_info = self.client.margin_account()
            total_capital = self.extract_total_capital(account_info, signal_data)
            positions = self.calculate_pair_positions(signal_data, total_capital)
            
            await self.true_pairs_trade_execution(
                asset1_amount=positions['asset1']['size'],
                asset2_amount=positions['asset2']['size'],
                asset1_side=positions['asset1']['side'],
                asset2_side=positions['asset2']['side'],
                channel=channel,
                signal_data=signal_data
            )
        except Exception as e:
            logger.error(f"Failed to execute signal as pairs trade: {e}")
            await channel.send(f"❌ Critical error during trade execution: {str(e)}")

    async def true_pairs_trade_execution(self, asset1_amount: float, asset2_amount: float, asset1_side: str, asset2_side: str, channel, signal_data: dict):
        """Execute TRUE PAIRS TRADE with proper spread hedging and monitoring"""
        logger.info(f"Executing TRUE PAIRS TRADE - Asset1: {asset1_side} {asset1_amount}, Asset2: {asset2_side} {asset2_amount}")
        
        try:
            pair_str = signal_data.get('pair', 'BTCUSDC/ETHUSDC')
            asset1_symbol, asset2_symbol = pair_str.split('/')
            asset1_name, asset2_name = self.extract_assets_from_pair(pair_str)
            
            asset1_price = signal_data.get('asset1_price', 0)
            asset2_price = signal_data.get('asset2_price', 0)

            min_notional = 5.0
            asset1_notional = asset1_amount * asset1_price
            asset2_notional = asset2_amount * asset2_price

            if asset1_notional < min_notional or asset2_notional < min_notional:
                error_msg = f"Order below minimum notional: {asset1_name}=${asset1_notional:,.2f}, {asset2_name}=${asset2_notional:,.2f}"
                logger.error(error_msg)
                await channel.send(f"❌ {error_msg}")
                return

            await channel.send(f"📊 PAIRS TRADE: {asset1_name}=${asset1_notional:,.2f} ({asset1_side}), {asset2_name}=${asset2_notional:,.2f} ({asset2_side})")
        
            first_order = self.client.new_margin_order(symbol=asset1_symbol, side=asset1_side.upper(), type="MARKET", quantity=str(asset1_amount), sideEffectType="AUTO_BORROW_REPAY")
            logger.info(f"PAIRS LEG 1 executed: {asset1_name} {asset1_side} - ID {first_order['orderId']}")
            await channel.send(f"✅ PAIRS LEG 1: {asset1_name} {asset1_side} - {first_order['orderId']}")
            
            second_order = self.client.new_margin_order(symbol=asset2_symbol, side=asset2_side.upper(), type="MARKET", quantity=str(asset2_amount), sideEffectType="AUTO_BORROW_REPAY")
            logger.info(f"PAIRS LEG 2 executed: {asset2_name} {asset2_side} - ID {second_order['orderId']}")
            await channel.send(f"✅ PAIRS LEG 2: {asset2_name} {asset2_side} - {second_order['orderId']}")
            
            executed_asset1_price = float(first_order['cummulativeQuoteQty']) / float(first_order['executedQty'])
            executed_asset2_price = float(second_order['cummulativeQuoteQty']) / float(second_order['executedQty'])
            
            beta = signal_data.get('beta', 1.0)
            executed_spread = math.log(executed_asset1_price) - beta * math.log(executed_asset2_price)
            
            logger.info(f"EXECUTED SPREAD: {executed_spread:.6f} (Target: {signal_data.get('spread', 'N/A'):.6f})")
            
            spread_threshold = signal_data.get('threshold', 0.01)
            action = signal_data.get('action')
            
            if action == 'LONG':
                target_spread_exit = executed_spread + (spread_threshold * self.TAKE_PROFIT_FACTOR)
                stop_spread_exit = executed_spread - (spread_threshold * self.STOP_LOSS_FACTOR)
            else:
                target_spread_exit = executed_spread - (spread_threshold * self.TAKE_PROFIT_FACTOR)
                stop_spread_exit = executed_spread + (spread_threshold * self.STOP_LOSS_FACTOR)
            
            logger.info(f"SPREAD TARGETS - Current: {executed_spread:.6f}, TP: {target_spread_exit:.6f}, SL: {stop_spread_exit:.6f}")
            
            position_id = f"pairs_{int(datetime.now().timestamp())}"
            position_data = {
                'position_id': position_id, 'asset1_symbol': asset1_symbol, 'asset2_symbol': asset2_symbol,
                'asset1_side': asset1_side, 'asset2_side': asset2_side, 'asset1_amount': asset1_amount,
                'asset2_amount': asset2_amount, 'beta': beta, 'entry_spread': executed_spread,
                'entry_price_asset1': executed_asset1_price, 'entry_price_asset2': executed_asset2_price,
                'target_spread': target_spread_exit, 'stop_spread': stop_spread_exit,
                'entry_time': datetime.now(), 'signal_action': action, 'status': 'ACTIVE'
            }
            
            self.active_pairs_positions[position_id] = position_data
            asyncio.create_task(self.monitor_pairs_spread(position_data, channel))
            
            await channel.send(
                f"🎯 **PAIRS TRADE ACTIVE** (ID: {position_id})\n"
                f"📊 Entry Spread: {executed_spread:.6f}\n"
                f"🎯 Profit Target: {target_spread_exit:.6f}\n"
                f"🛑 Stop Loss: {stop_spread_exit:.6f}\n"
                f"🤖 **Automated spread monitoring active**"
            )
            logger.info(f"AUTOMATED PAIRS MONITORING: Position {position_id} started")

        except Exception as e:
            logger.error(f"Pairs trade execution FAILED: {e}")
            await channel.send(f"❌ Pairs trade error: {str(e)}")

    async def monitor_pairs_spread(self, position_data: dict, channel):
        """Monitor spread and automatically exit pairs position when targets hit"""
        position_id = position_data['position_id']
        logger.info(f"Starting spread monitoring for pairs position {position_id}")
        
        check_interval = 60
        max_monitoring_hours = 24
        max_checks = (max_monitoring_hours * 3600) // check_interval
        
        for checks_performed in range(max_checks):
            await asyncio.sleep(check_interval)
            
            if position_id not in self.active_pairs_positions or self.active_pairs_positions[position_id]['status'] != 'ACTIVE':
                logger.info(f"Position {position_id} no longer active, stopping monitoring.")
                return
            
            try:
                asset1_ticker = self.client.ticker_price(symbol=position_data['asset1_symbol'])
                asset2_ticker = self.client.ticker_price(symbol=position_data['asset2_symbol'])
                current_asset1_price = float(asset1_ticker['price'])
                current_asset2_price = float(asset2_ticker['price'])
                
                current_spread = math.log(current_asset1_price) - position_data['beta'] * math.log(current_asset2_price)
                logger.debug(f"Position {position_id}: Current spread {current_spread:.6f}")
                
                exit_reason = None
                if position_data['signal_action'] == 'LONG':
                    if current_spread >= position_data['target_spread']: exit_reason = "PROFIT TARGET"
                    elif current_spread <= position_data['stop_spread']: exit_reason = "STOP LOSS"
                else: # SHORT
                    if current_spread <= position_data['target_spread']: exit_reason = "PROFIT TARGET"
                    elif current_spread >= position_data['stop_spread']: exit_reason = "STOP LOSS"
                
                if exit_reason:
                    logger.info(f"PAIRS EXIT TRIGGERED for {position_id}: {exit_reason}")
                    await self.execute_pairs_exit(position_data, current_spread, exit_reason, channel)
                    return
                
            except Exception as e:
                logger.error(f"Error checking spread for position {position_id}: {e}")
        
        logger.warning(f"Position {position_id} monitoring timeout after {max_monitoring_hours}h")
        await self.execute_pairs_exit(position_data, None, "TIME LIMIT - 24h monitoring timeout", channel)

    async def execute_pairs_exit(self, position_data: dict, exit_spread: float, reason: str, channel):
        """Close both legs of the pairs trade simultaneously"""
        position_id = position_data['position_id']
        
        try:
            logger.info(f"EXECUTING PAIRS EXIT: {position_id} - {reason}")
            
            exit_side1 = "SELL" if position_data['asset1_side'] == "BUY" else "BUY"
            leg1_order = self.client.new_margin_order(symbol=position_data['asset1_symbol'], side=exit_side1, type="MARKET", quantity=str(position_data['asset1_amount']), sideEffectType="AUTO_BORROW_REPAY")
            
            exit_side2 = "SELL" if position_data['asset2_side'] == "BUY" else "BUY"
            leg2_order = self.client.new_margin_order(symbol=position_data['asset2_symbol'], side=exit_side2, type="MARKET", quantity=str(position_data['asset2_amount']), sideEffectType="AUTO_BORROW_REPAY")
            
            exit_price_asset1 = float(leg1_order['cummulativeQuoteQty']) / float(leg1_order['executedQty'])
            exit_price_asset2 = float(leg2_order['cummulativeQuoteQty']) / float(leg2_order['executedQty'])
            entry_price_asset1 = position_data.get('entry_price_asset1', 0)
            entry_price_asset2 = position_data.get('entry_price_asset2', 0)

            exit_time = datetime.now()
            self.active_pairs_positions[position_id].update({
                'status': 'CLOSED', 'exit_spread': exit_spread, 
                'exit_reason': reason, 'exit_time': exit_time
            })
            
            embed = discord.Embed(
                title="🏁 PAIRS TRADE CLOSED",
                description=f"Position `{position_id[:12]}` exited.",
                color=discord.Color.green() if "PROFIT" in reason else discord.Color.orange(),
                timestamp=exit_time
            )
            embed.add_field(name="Exit Reason", value=reason, inline=False)
            embed.add_field(name=f"Asset 1: {position_data['asset1_symbol']}", value=f"Entry: `${entry_price_asset1:,.4f}`\nExit:  `${exit_price_asset1:,.4f}`", inline=True)
            embed.add_field(name=f"Asset 2: {position_data['asset2_symbol']}", value=f"Entry: `${entry_price_asset2:,.4f}`\nExit:  `${exit_price_asset2:,.4f}`", inline=True)
            embed.add_field(name="Orders Executed", value=f"Leg 1: `{leg1_order['orderId']}`\nLeg 2: `{leg2_order['orderId']}`", inline=True)
            
            entry_time = position_data.get('entry_time')
            if entry_time:
                duration = exit_time - entry_time
                hours, rem = divmod(duration.total_seconds(), 3600)
                minutes, seconds = divmod(rem, 60)
                duration_str = f"{int(hours)}h {int(minutes)}m {int(seconds)}s"
                
                embed.add_field(
                    name="Timestamps",
                    value=f"**Entry:** {entry_time.strftime('%Y-%m-%d %H:%M')}\n"
                          f"**Exit:**  {exit_time.strftime('%Y-%m-%d %H:%M')}\n"
                          f"**Duration:** {duration_str}",
                    inline=False
                )
            
            await channel.send(embed=embed)
            logger.info(f"PAIRS EXIT COMPLETE: {position_id} - Both legs closed successfully")
            
        except Exception as e:
            logger.error(f"ERROR IN PAIRS EXIT: {position_id} - {e}")
            await channel.send(f"❌ **CRITICAL**: Failed to close pairs position {position_id[:8]}: {str(e)}")
            if position_id in self.active_pairs_positions:
                self.active_pairs_positions[position_id]['status'] = 'ERROR'
    
    # ==================== UTILITY & MANAGEMENT COMMANDS ====================

    @commands.command(name="pairslist")
    async def list_active_pairs(self, ctx):
        """List all active pairs trading positions"""
        active_positions = [p for p in self.active_pairs_positions.values() if p['status'] == 'ACTIVE']
        
        if not active_positions:
            await ctx.send("No active pairs positions found.")
            return
        
        embed = discord.Embed(title=f"Active Pairs Positions ({len(active_positions)})", color=discord.Color.blue())
        for pos_data in active_positions:
            runtime = datetime.now() - pos_data['entry_time']
            minutes = runtime.total_seconds() // 60
            embed.add_field(
                name=f"ID: {pos_data['position_id'][:8]}",
                value=f"Pair: {pos_data['asset1_symbol']}/{pos_data['asset2_symbol']}\n"
                      f"Action: {pos_data['signal_action']}\n"
                      f"Runtime: {int(minutes)}m",
                inline=True
            )
        await ctx.send(embed=embed)
    
    @commands.command(name="closepairs")
    @commands.has_role("Trading-Authorized")
    async def manual_close_pairs(self, ctx, position_id: str = None):
        """Manually close a specific pairs position or all positions"""
        if not hasattr(self, 'active_pairs_positions'):
            await ctx.send("No pairs positions found.")
            return
        
        positions_to_close = []
        if position_id:
            if position_id in self.active_pairs_positions and self.active_pairs_positions[position_id]['status'] == 'ACTIVE':
                positions_to_close.append(self.active_pairs_positions[position_id])
            else:
                await ctx.send(f"Position ID `{position_id}` not found or is not active.")
                return
        else:
            positions_to_close = [p for p in self.active_pairs_positions.values() if p['status'] == 'ACTIVE']

        if not positions_to_close:
            await ctx.send("No active positions to close.")
            return
            
        await ctx.send(f"Closing {len(positions_to_close)} active pairs position(s)...")
        for pos_data in positions_to_close:
            await self.execute_pairs_exit(pos_data, None, "MANUAL CLOSE - User requested", ctx.channel)
            await asyncio.sleep(1)

    @commands.command(name="savelogs")
    @commands.is_owner()
    async def save_logs(self, ctx):
        """Saves all captured logs to an Excel file and sends it."""
        logger.info(f"Log save command initiated by {ctx.author.name}")
        
        await ctx.send("Saving logs... this may take a moment.")
        
        result_message = self.log_sink.save_to_excel()
        await ctx.send(result_message)
        
        try:
            filename = result_message.split("`")[-2]
            if os.path.exists(filename):
                await ctx.send(file=discord.File(filename))
        except Exception as e:
            logger.warning(f"Could not send log file to Discord: {e}")
            await ctx.send("Could not upload file to Discord (it may be too large).")

async def setup(bot):
    """Add the cross margin cog to the bot"""
    logger.info("Setting up CrossMarginBot cog...")
    await bot.add_cog(CrossMarginBot(bot))
    logger.info("CrossMarginBot cog setup complete")