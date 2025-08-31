"""
Cross Margin Trading Bot for Discord
Supports pairs trading across multiple symbols using shared collateral pool
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
        self.bot = bot
        api_key = os.getenv("BINANCE_API_KEY", "")
        api_secret = os.getenv("BINANCE_API_SECRET", "")
        logger.debug("API credentials loaded")
        self.client = Client(api_key=api_key, api_secret=api_secret)
        logger.debug("Binance client initialized for cross margin")

        # Signal approval system
        self.pending_signals = {}
        self.APPROVAL_TIMEOUT = 60  # minutes
        logger.info("Cross margin cog initialized")

    # ==================== ACCOUNT COMMANDS ====================

    @commands.command(name="balance", aliases=['bal'])
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def balance(self, ctx):
        """
        Display cross margin account balance (all assets)
        """
        logger.info(f"Balance command invoked by {ctx.author}")
        
        temp_msg = await ctx.send("Fetching cross margin account data...")
        
        try:
            # Use cross margin endpoint (no isIsolated parameter)
            response = self.client.margin_account()
            logger.debug(f"Cross margin response received")

            # Extract account data
            margin_level = float(response.get("marginLevel", "999"))
            total_asset_btc = float(response.get("totalAssetOfBtc", "0"))
            total_liability_btc = float(response.get("totalLiabilityOfBtc", "0"))
            total_net_asset_btc = float(response.get("totalNetAssetOfBtc", "0"))
            
            # Determine health color
            if margin_level == 999:  # No borrowing
                color = discord.Color.green()
            elif margin_level > 3:
                color = discord.Color.green()
            elif margin_level > 1.5:
                color = discord.Color.gold()
            else:
                color = discord.Color.red()
            
            # Create embed
            embed = discord.Embed(
                title="Cross Margin Account Summary",
                description="All assets in shared collateral pool",
                color=color,
                timestamp=datetime.now()
            )
            
            # Get current BTC price for USD conversion
            ticker = self.client.ticker_price(symbol="BTCUSDT")
            btc_price = float(ticker["price"])
            
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
            
            for asset in significant_assets[:6]:  # Limit to 6 for embed size
                asset_name = asset["asset"]
                free = float(asset.get("free", 0))
                locked = float(asset.get("locked", 0))
                borrowed = float(asset.get("borrowed", 0))
                net = float(asset.get("netAsset", 0))
                
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
            
        except Exception as e:
            logger.error(f"Error in balance command: {str(e)}")
            await temp_msg.edit(content=f"Error fetching account data: {str(e)}")

    # ==================== ORDER QUERY COMMANDS ====================

    @commands.command(name="openorders", aliases=['oo', 'open'])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def open_orders(self, ctx, symbol: Optional[str] = None):
        """
        Display open cross margin orders (all symbols or specific)
        """
        logger.debug(f"Open orders command invoked by {ctx.author}")
        
        try:
            # Get orders - no isIsolated parameter for cross margin
            if symbol:
                orders = self.client.margin_open_orders(symbol=symbol.upper())
            else:
                orders = self.client.margin_open_orders()  # All symbols
            
            if not orders:
                await ctx.send("No open orders found.")
                return
            
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
            
        except Exception as e:
            logger.error(f"Error retrieving orders: {str(e)}")
            await ctx.send(f"❌ Error: {str(e)}")

    @commands.command(name="cancelall", aliases=['canall'])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def cancel_all_orders(self, ctx, symbol: str):
        """Cancel all open orders for a symbol in cross margin"""
        logger.info(f"Cancelling all orders for {symbol}")
        
        try:
            # No isIsolated parameter for cross margin
            response = self.client.margin_open_orders_cancellation(symbol=symbol.upper())
            await ctx.send(f"✅ Cancelled all orders for {symbol.upper()}")
        except Exception as e:
            logger.error(f"Error cancelling orders: {e}")
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
        logger.info(f"Market order: {symbol} {side} {quantity}")
        
        params = {
            "symbol": symbol.upper(),
            "side": side.upper(),
            "type": "MARKET",
            "quantity": str(quantity),
            # NO isIsolated parameter for cross margin
            "sideEffectType": side_effect.upper()
        }
        
        try:
            order = self.client.new_margin_order(**params)
            await ctx.send(f"✅ Order placed! ID: {order['orderId']}")
        except Exception as e:
            logger.error(f"Order failed: {e}")
            await ctx.send(f"❌ Order failed: {str(e)}")

    @commands.has_role("Trading-Authorized")
    @commands.command(name="oco")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def oco_order(self, ctx, symbol: str, side: str, quantity: float, price: float, stop_price: float):
        """Place OCO order in cross margin"""
        
        params = {
            "symbol": symbol.upper(),
            "side": side.upper(),
            "quantity": str(quantity),
            "price": str(price),
            "stopPrice": str(stop_price),
            # NO isIsolated parameter
            "sideEffectType": "AUTO_BORROW_REPAY"
        }
        
        try:
            order = self.client.new_margin_oco_order(**params)
            await ctx.send(f"✅ OCO placed! List ID: {order['orderListId']}")
        except Exception as e:
            logger.error(f"OCO failed: {e}")
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
            
            market_order = self.client.new_margin_order(**params)
            
            # Extract execution details
            executed_qty = float(market_order.get("executedQty", 0))
            executed_quote_qty = float(market_order.get("cummulativeQuoteQty", 0))
            executed_price = executed_quote_qty / executed_qty if executed_qty > 0 else 0
            
            # Step 2: Calculate TP/SL
            direction = 1 if side.lower() == "buy" else -1
            f0 = 0.001  # Entry fee
            ft = 0.001  # Exit fee
            risk = 0.01
            
            tp = (risk * executed_price * rr + executed_price * (f0 + direction)) / (direction - ft)
            sl = (risk * executed_price - executed_price * (f0 + direction)) / (ft - direction)
            
            tp = round(tp, 2)
            sl = round(sl, 2)
            
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
            
            oco_order = self.client.new_margin_oco_order(**oco_params)
            
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
            
        except Exception as e:
            logger.error(f"Full position failed: {e}")
            await processing_msg.edit(content=f"❌ Error: {str(e)}")

    # ==================== PAIRS TRADING ====================

    def extract_total_capital(self, account_info):
        """Extract total USD value from cross margin account"""
        user_assets = account_info.get("userAssets", [])
        total_usd = 0
        
        # Get current prices for conversion
        btc_ticker = self.client.ticker_price(symbol="BTCUSDT")
        btc_price = float(btc_ticker["price"])
        
        eth_ticker = self.client.ticker_price(symbol="ETHUSDT")
        eth_price = float(eth_ticker["price"])
        
        for asset in user_assets:
            asset_name = asset["asset"]
            net_amount = float(asset.get("netAsset", 0))
            
            if asset_name == "USDT" or asset_name == "USDC":
                total_usd += net_amount
            elif asset_name == "BTC":
                total_usd += net_amount * btc_price
            elif asset_name == "ETH":
                total_usd += net_amount * eth_price
            # Add more conversions as needed
        
        return total_usd

    def calculate_pair_positions(self, signal_data: dict, total_capital: float, capital_allocation: float = 0.20) -> dict:
        """Calculate position sizes for pairs trading"""
        beta = signal_data['beta']
        btc_price = signal_data['btc_price']
        eth_price = signal_data['eth_price']
        action = signal_data['action']
        
        allocated_capital = total_capital * capital_allocation
        
        btc_dollar_allocation = allocated_capital / (1 + beta)
        eth_dollar_allocation = beta * btc_dollar_allocation
        
        btc_size = btc_dollar_allocation / btc_price
        eth_size = eth_dollar_allocation / eth_price
        
        # Round to Binance LOT_SIZE requirements
        # BTC: 0.00001 (5 decimals)
        # ETH: 0.001 (3 decimals)
        btc_size = round(btc_size // 0.00001 * 0.00001, 5)
        eth_size = round(eth_size // 0.001 * 0.001, 3)
        
        if action == "LONG":
            btc_side = "BUY"
            eth_side = "SELL"
        else:
            btc_side = "SELL"
            eth_side = "BUY"
        
        return {
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

    async def execute_pairs_trade(self, signal_data, channel):
        """Execute pairs trade using cross margin"""
        
        # Get account balance (cross margin)
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
        
        try:
            btc_order = self.client.new_margin_order(**btc_params)
            eth_order = self.client.new_margin_order(**eth_params)
            
            await channel.send(f"✅ Pairs trade executed:\nBTC: {btc_order['orderId']}\nETH: {eth_order['orderId']}")
            
            # Monitor execution
            await self.monitor_pairs_execution(btc_order, eth_order, signal_data, channel)
            
        except Exception as e:
            logger.error(f"Pairs trade failed: {e}")
            await channel.send(f"❌ Pairs trade failed: {str(e)}")

    async def monitor_pairs_execution(self, btc_order, eth_order, signal_data, channel):
        """Monitor fills and handle partial execution"""
        await asyncio.sleep(5)
        
        # Check status (no isIsolated parameter)
        btc_status = self.client.query_margin_order(
            symbol="BTCUSDC",
            orderId=btc_order['orderId']
        )
        
        eth_status = self.client.query_margin_order(
            symbol="ETHUSDC",
            orderId=eth_order['orderId']
        )
        
        btc_filled = btc_status['status'] == 'FILLED'
        eth_filled = eth_status['status'] == 'FILLED'
        
        if btc_filled and eth_filled:
            await channel.send("✅ Both legs filled")
            # Set up OCO orders here
        elif btc_filled or eth_filled:
            await channel.send("⚠️ Only one leg filled - emergency exit")
            # Handle partial fill
        else:
            await channel.send("⏰ Orders not filled - cancelling")
            self.client.cancel_margin_order(symbol="BTCUSDC", orderId=btc_order['orderId'])
            self.client.cancel_margin_order(symbol="ETHUSDC", orderId=eth_order['orderId'])

    # ==================== PAIRS EXECUTION ====================

    @commands.command(name="pairs")
    async def execute_pairs(self, ctx, btc_amount: float, eth_amount: float, btc_side: str, eth_side: str, tp_percent: float = 1.5, sl_percent: float = 1.0):
        """
        Execute pairs trade with 2 entries + 2 OCOs
        
        Example:
        !pairs 0.0002 0.01 SELL BUY 1.5 1.0
        (Sell 0.0002 BTC, Buy 0.01 ETH, TP at 1.5%, SL at 1%)
        """
        try:
            # Entry orders
            btc_order = self.client.new_margin_order(
                symbol="BTCUSDC",
                side=btc_side.upper(),
                type="MARKET",
                quantity=str(btc_amount),
                sideEffectType="AUTO_BORROW_REPAY"
            )
            await ctx.send(f"✅ BTC {btc_side}: {btc_order['orderId']}")
            
            eth_order = self.client.new_margin_order(
                symbol="ETHUSDC",
                side=eth_side.upper(),
                type="MARKET",
                quantity=str(eth_amount),
                sideEffectType="AUTO_BORROW_REPAY"
            )
            await ctx.send(f"✅ ETH {eth_side}: {eth_order['orderId']}")
            
            # Get executed prices
            btc_price = float(btc_order['cummulativeQuoteQty']) / float(btc_order['executedQty'])
            eth_price = float(eth_order['cummulativeQuoteQty']) / float(eth_order['executedQty'])
            
            # Calculate TP/SL
            btc_tp = btc_price * (1 + tp_percent/100) if btc_side == "BUY" else btc_price * (1 - tp_percent/100)
            btc_sl = btc_price * (1 - sl_percent/100) if btc_side == "BUY" else btc_price * (1 + sl_percent/100)
            
            eth_tp = eth_price * (1 + tp_percent/100) if eth_side == "BUY" else eth_price * (1 - tp_percent/100)
            eth_sl = eth_price * (1 - sl_percent/100) if eth_side == "BUY" else eth_price * (1 + sl_percent/100)
            
            # Place OCOs
            btc_oco = self.client.new_margin_oco_order(
                symbol="BTCUSDC",
                side="SELL" if btc_side == "BUY" else "BUY",
                quantity=str(btc_amount),
                price=str(round(btc_tp, 2)),
                stopPrice=str(round(btc_sl, 2)),
                sideEffectType="AUTO_BORROW_REPAY"
            )
            await ctx.send(f"✅ BTC OCO: {btc_oco['orderListId']}")
            
            eth_oco = self.client.new_margin_oco_order(
                symbol="ETHUSDC",
                side="SELL" if eth_side == "BUY" else "BUY",
                quantity=str(eth_amount),
                price=str(round(eth_tp, 2)),
                stopPrice=str(round(eth_sl, 2)),
                sideEffectType="AUTO_BORROW_REPAY"
            )
            await ctx.send(f"✅ ETH OCO: {eth_oco['orderListId']}")
            
            # Summary
            embed = discord.Embed(title="Pairs Trade Executed", color=discord.Color.green())
            embed.add_field(name="BTC", value=f"{btc_side} @ ${btc_price:.2f}\nTP: ${btc_tp:.2f}\nSL: ${btc_sl:.2f}", inline=True)
            embed.add_field(name="ETH", value=f"{eth_side} @ ${eth_price:.2f}\nTP: ${eth_tp:.2f}\nSL: ${eth_sl:.2f}", inline=True)
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"❌ Error: {e}")

    # ==================== SIGNAL HANDLING ====================

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot and "TRADING SIGNAL APPROVAL NEEDED" in message.content:
            await self.handle_signal_approval(message)

    async def handle_signal_approval(self, message):
        """Parse and store signal for approval"""
        signal_data = self.parse_signal_message(message.content)
        
        if signal_data:
            self.pending_signals[signal_data['signal_id']] = {
                'data': signal_data,
                'message_id': message.id,
                'channel_id': message.channel.id,
                'expires_at': datetime.now() + timedelta(minutes=self.APPROVAL_TIMEOUT)
            }
            await message.add_reaction('✅')
            await message.add_reaction('❌')

    def parse_signal_message(self, content: str) -> Optional[dict]:
        """Parse signal from Discord message"""
        from models import TradingSignalApproval
        signal = TradingSignalApproval.from_discord_message(content)
        return signal.model_dump() if signal else None

    @commands.command(name="checkmarginsymbols")
    async def check_margin_symbols(self, ctx):
        """Check available margin trading pairs"""
        info = self.client.margin_all_pairs()
        usdc_pairs = [p for p in info if 'USDC' in p['symbol']]
        
        await ctx.send(f"Found {len(usdc_pairs)} USDC margin pairs. Showing first 10:")
        for pair in usdc_pairs[:10]:
            await ctx.send(f"{pair['symbol']}: {pair['isMarginTrade']}")
    
    @commands.command(name="testsingletrade")
    async def test_single_trade(self, ctx):
        """Test just BTC side with larger amount"""
        try:
            params = {
                "symbol": "BTCUSDC",
                "side": "SELL",
                "type": "MARKET",
                "quantity": "0.0002",  # ~$20
                "sideEffectType": "AUTO_BORROW_REPAY"
            }
            order = self.client.new_margin_order(**params)
            await ctx.send(f"✅ Order placed: {order['orderId']}")
            
            # Reverse immediately
            await asyncio.sleep(2)
            reverse = {
                "symbol": "BTCUSDC",
                "side": "BUY",
                "type": "MARKET",
                "quantity": "0.0002",
                "sideEffectType": "AUTO_BORROW_REPAY"
            }
            order2 = self.client.new_margin_order(**reverse)
            await ctx.send(f"✅ Reversed: {order2['orderId']}")
        except Exception as e:
            await ctx.send(f"❌ Failed: {e}")
        if user.bot:
            return
        
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
            await self.execute_pairs_trade(signal_entry['data'], reaction.message.channel)
            del self.pending_signals[signal_id]
        elif reaction.emoji == '❌':
            await reaction.message.channel.send(f"❌ Signal {signal_id} rejected")
            del self.pending_signals[signal_id]

    # ==================== TEST COMMANDS ====================

    @commands.command(name="testpairs")
    async def test_pairs_execution(self, ctx, allocation_pct: float = 0.1):
        """Test pairs trading calculations without placing orders"""
        
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
            "eth_price": 3400.0,
            "timestamp": datetime.now(),
            "expires_minutes": 60
        }
        
        try:
            account_info = self.client.margin_account()
            total_capital = self.extract_total_capital(account_info)
            positions = self.calculate_pair_positions(test_signal, total_capital, allocation_pct)
            
            await ctx.send(f"""
**Test Position Calculation:**
Total Capital: ${total_capital:.2f}
Allocated ({allocation_pct*100}%): ${positions['total_allocated']:.2f}
BTC: {positions['btc']['side']} {positions['btc']['size']:.8f} @ ${positions['btc']['entry_price']}
ETH: {positions['eth']['side']} {positions['eth']['size']:.8f} @ ${positions['eth']['entry_price']}
Beta: {positions['hedge_ratio']:.4f}
            """)
            
        except Exception as e:
            await ctx.send(f"❌ Test failed: {e}")

    @commands.command(name="testpairslive")
    async def test_pairs_live(self, ctx, allocation_pct: float = 0.5):
        """Execute real pairs orders with custom allocation"""
        
        # Check minimums first
        info = self.client.exchange_info()
        for s in info['symbols']:
            if s['symbol'] in ['BTCUSDC', 'ETHUSDC']:
                for f in s['filters']:
                    if f['filterType'] == 'MIN_NOTIONAL' or f['filterType'] == 'NOTIONAL':
                        await ctx.send(f"{s['symbol']}: Min notional = ${f.get('minNotional', f.get('notional', 'N/A'))}")
        
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
            "btc_price": 108010.0,
            "eth_price": 3400.0,
            "timestamp": datetime.now(),
            "expires_minutes": 60
        }
        
        await ctx.send(f"⚠️ Using BTCUSDT/ETHUSDT with {allocation_pct*100}% allocation...")
        
        try:
            account_info = self.client.margin_account()
            total_capital = self.extract_total_capital(account_info)
            
            # Override symbols to USDT pairs
            positions = self.calculate_pair_positions(test_signal, total_capital, allocation_pct)
            positions["btc"]["symbol"] = "BTCUSDT"
            positions["eth"]["symbol"] = "ETHUSDT"
            
            await ctx.send(f"""
**About to place:**
BTC: {positions['btc']['side']} {positions['btc']['size']:.8f} (${positions['btc']['dollar_value']:.2f})
ETH: {positions['eth']['side']} {positions['eth']['size']:.8f} (${positions['eth']['dollar_value']:.2f})
            """)
            
            # Place orders sequentially with error handling
            try:
                btc_params = {
                    "symbol": "BTCUSDT",
                    "side": positions["btc"]["side"],
                    "type": "MARKET",
                    "quantity": str(positions["btc"]["size"]),
                    "sideEffectType": "AUTO_BORROW_REPAY"
                }
                btc_order = self.client.new_margin_order(**btc_params)
                await ctx.send(f"✅ BTC order placed: {btc_order['orderId']}")
            except Exception as e:
                await ctx.send(f"❌ BTC failed: {e}")
                return
            
            try:
                eth_params = {
                    "symbol": "ETHUSDT",
                    "side": positions["eth"]["side"],
                    "type": "MARKET",
                    "quantity": str(positions["eth"]["size"]),
                    "sideEffectType": "AUTO_BORROW_REPAY"
                }
                eth_order = self.client.new_margin_order(**eth_params)
                await ctx.send(f"✅ ETH order placed: {eth_order['orderId']}")
            except Exception as e:
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
                await ctx.send("🔄 Reversed BTC position")
            
        except Exception as e:
            await ctx.send(f"❌ Test failed: {e}")

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        """Handle signal approval reactions"""
        if user.bot or str(reaction.emoji) != '✅':
            return
            
        # Find the pending signal for this message
        signal_data = None
        signal_id = None
        
        for sid, stored_signal in self.pending_signals.items():
            if stored_signal['message_id'] == reaction.message.id:
                signal_data = stored_signal['data']
                signal_id = sid
                break
        
        if not signal_data:
            return
            
        # Convert signal to pairs trade execution
        await self.execute_signal_as_pairs_trade(signal_data, reaction.message.channel)
        
        # Clean up
        del self.pending_signals[signal_id]

    async def execute_signal_as_pairs_trade(self, signal_data, channel):
        """Convert signal parameters to pairs trade execution"""
        
        action = signal_data['action']  # "LONG" or "SHORT" 
        beta = signal_data['beta']      # 2.3695
        btc_price = signal_data['btc_price']
        eth_price = signal_data['eth_price']
        
        # Calculate position sizes based on your capital allocation
        account_info = self.client.margin_account()
        total_capital = self.extract_total_capital(account_info)
        positions = self.calculate_pair_positions(signal_data, total_capital,capital_allocation=0.5)
        
        # Extract the calculated amounts and sides
        btc_amount = positions['btc']['size']
        eth_amount = positions['eth']['size'] 
        btc_side = positions['btc']['side']
        eth_side = positions['eth']['side']
        
        # Execute using your existing pairs command logic
        await self.pairs_trade_execution(btc_amount, eth_amount, btc_side, eth_side, channel)


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
        try:
            # Check minimum notionals first
            btc_ticker = self.client.ticker_price(symbol="BTCUSDC")
            eth_ticker = self.client.ticker_price(symbol="ETHUSDC")
            
            btc_price = float(btc_ticker["price"])
            eth_price = float(eth_ticker["price"])
            
            btc_notional = btc_amount * btc_price
            eth_notional = eth_amount * eth_price
            
            min_notional = 5  # Binance minimum is usually ~$5
            
            if btc_notional < min_notional:
                await channel.send(f"❌ BTC order too small: ${btc_notional:.2f} < ${min_notional}")
                return {"success": False, "error": "BTC notional too small"}
                
            if eth_notional < min_notional:
                await channel.send(f"❌ ETH order too small: ${eth_notional:.2f} < ${min_notional}")
                return {"success": False, "error": "ETH notional too small"}
            
            await channel.send(f"📊 Order sizes: BTC=${btc_notional:.2f}, ETH=${eth_notional:.2f}")
        
            # Entry orders
            btc_order = self.client.new_margin_order(
                symbol="BTCUSDC",
                side=btc_side.upper(),
                type="MARKET",
                quantity=str(btc_amount),
                sideEffectType="AUTO_BORROW_REPAY"
            )
            await channel.send(f"✅ BTC {btc_side}: {btc_order['orderId']}")
            
            eth_order = self.client.new_margin_order(
                symbol="ETHUSDC",
                side=eth_side.upper(),
                type="MARKET",
                quantity=str(eth_amount),
                sideEffectType="AUTO_BORROW_REPAY"
            )
            await channel.send(f"✅ ETH {eth_side}: {eth_order['orderId']}")
            
            # Get executed prices
            btc_price = float(btc_order['cummulativeQuoteQty']) / float(btc_order['executedQty'])
            eth_price = float(eth_order['cummulativeQuoteQty']) / float(eth_order['executedQty'])
            
            # Calculate TP/SL levels
            btc_tp = btc_price * (1 + tp_percent/100) if btc_side.upper() == "BUY" else btc_price * (1 - tp_percent/100)
            btc_sl = btc_price * (1 - sl_percent/100) if btc_side.upper() == "BUY" else btc_price * (1 + sl_percent/100)
            
            eth_tp = eth_price * (1 + tp_percent/100) if eth_side.upper() == "BUY" else eth_price * (1 - tp_percent/100)
            eth_sl = eth_price * (1 - sl_percent/100) if eth_side.upper() == "BUY" else eth_price * (1 + sl_percent/100)
            
            # Place OCO orders
            btc_oco = self.client.new_margin_oco_order(
                symbol="BTCUSDC",
                side="SELL" if btc_side.upper() == "BUY" else "BUY",
                quantity=str(btc_amount),
                price=str(round(btc_tp, 2)),
                stopPrice=str(round(btc_sl, 2)),
                sideEffectType="AUTO_BORROW_REPAY"
            )
            await channel.send(f"✅ BTC OCO: {btc_oco['orderListId']}")
            
            eth_oco = self.client.new_margin_oco_order(
                symbol="ETHUSDC",
                side="SELL" if eth_side.upper() == "BUY" else "BUY",
                quantity=str(eth_amount),
                price=str(round(eth_tp, 2)),
                stopPrice=str(round(eth_sl, 2)),
                sideEffectType="AUTO_BORROW_REPAY"
            )
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
            
            return {
                "success": True,
                "btc_order_id": btc_order['orderId'],
                "eth_order_id": eth_order['orderId'],
                "btc_oco_id": btc_oco['orderListId'],
                "eth_oco_id": eth_oco['orderListId'],
                "btc_price": btc_price,
                "eth_price": eth_price
            }
            
        except Exception as e:
            logger.error(f"Pairs trade execution failed: {e}")
            await channel.send(f"❌ Pairs trade error: {str(e)}")
            return {"success": False, "error": str(e)}


    async def execute_signal_as_pairs_trade(self, signal_data, channel):
        """Convert signal to pairs trade"""
        account_info = self.client.margin_account()
        total_capital = self.extract_total_capital(account_info)
        positions = self.calculate_pair_positions(signal_data, total_capital)
        
        # Default TP/SL for signals (configurable)
        tp_percent = 1.5
        sl_percent = 1.0
        
        result = await self.pairs_trade_execution(
            positions['btc']['size'],
            positions['eth']['size'], 
            positions['btc']['side'],
            positions['eth']['side'],
            tp_percent,
            sl_percent,
            channel
        )
        
        if result["success"]:
            await channel.send(f"🎯 Signal executed successfully: {signal_data['signal_id']}")
        else:
            await channel.send(f"❌ Signal execution failed: {signal_data['signal_id']}")

    @commands.command(name="pairs")
    async def execute_pairs(self, ctx, btc_amount: float, eth_amount: float, btc_side: str, eth_side: str, tp_percent: float = 1.5, sl_percent: float = 1.0):
        """
        Execute pairs trade with 2 entries + 2 OCOs
        
        Example:
        !pairs 0.0002 0.01 SELL BUY 1.5 1.0
        """
        await self.pairs_trade_execution(btc_amount, eth_amount, btc_side, eth_side, tp_percent, sl_percent, ctx)

async def setup(bot):
    """Add the cross margin cog to the bot"""
    await bot.add_cog(CrossMarginBot(bot))