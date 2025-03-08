import discord
from discord.ext import commands
import asyncio
from datetime import datetime
import os
from kucoin_handler import KucoinAPI


class TradingCommands(commands.Cog):
    """Discord cog for trading cryptocurrency with KuCoin API"""

    def __init__(self, bot):
        self.bot = bot
        # Initialize the KuCoin API client
        self.kucoin = KucoinAPI(
            api_key=os.getenv("KUCOIN_API_KEY", ""),
            api_secret=os.getenv("KUCOIN_API_SECRET", ""),
            passphrase=os.getenv("KUCOIN_API_PASSPHRASE", "")
        )

    async def _collect_trade_parameters(self, ctx, is_real=False):
        """Collect trade parameters interactively

        Args:
            ctx: Discord context
            is_real: Whether this is for a real trade

        Returns:
            dict: Trade parameters or None if canceled
        """
        trade_data = {}

        # Helper function for collecting user input
        async def get_user_input(prompt, timeout=60, validator=None):
            prompt_msg = await ctx.send(prompt)

            def check(message):
                return message.author == ctx.author and message.channel == ctx.channel

            try:
                user_response = await self.bot.wait_for(
                    "message", timeout=timeout, check=check
                )
                if validator:
                    result, error_msg = validator(user_response.content)
                    if not result:
                        await ctx.send(f"❌ {error_msg} Please try again.")
                        return await get_user_input(prompt, timeout, validator)
                return user_response.content
            except asyncio.TimeoutError:
                await ctx.send("⏱️ No input received. Trade cancelled.")
                return None

        # 1. Ask for market/trading pair
        def validate_market(value):
            try:
                # KuCoin doesn't have a direct "get markets" method like Bitvavo
                # We'll accept any string in the format "XXX-YYY" for now
                value = value.upper()
                if "-" in value and len(value.split("-")) == 2:
                    return True, ""
                return False, f"Market {value} doesn't seem to be in the correct format (e.g., BTC-USDT)."
            except Exception as e:
                return False, f"Error validating market: {str(e)}"

        market = await get_user_input(
            "📊 Enter the trading pair (e.g., BTC-USDT):", validator=validate_market
        )
        if not market:
            return None
        trade_data["market"] = market.upper()

        # 2. Ask for order type (market or limit)
        def validate_order_type(value):
            if value.lower() in ["market", "limit"]:
                return True, ""
            return False, "Invalid order type. Please enter 'market' or 'limit'."

        order_type = await get_user_input(
            "📝 Order type (market or limit)?", validator=validate_order_type
        )
        if not order_type:
            return None
        trade_data["order_type"] = order_type.lower()

        # 3. Ask for side (buy/sell)
        def validate_side(value):
            if value.lower() in ["buy", "sell"]:
                return True, ""
            return False, "Invalid side. Please enter 'buy' or 'sell'."

        side = await get_user_input("📈 Buy or sell?", validator=validate_side)
        if not side:
            return None
        trade_data["side"] = side.lower()

        # 4. Ask for amount
        def validate_amount(value):
            try:
                amount = float(value)
                if amount <= 0:
                    return False, "Amount must be positive."
                return True, ""
            except:
                return False, "Invalid amount. Please enter a valid number."

        amount = await get_user_input(
            "💰 Enter the amount to trade:", validator=validate_amount
        )
        if not amount:
            return None
        trade_data["amount"] = float(amount)

        # 5. For limit orders, we need price
        if trade_data["order_type"] == "limit":
            def validate_price(value):
                try:
                    price = float(value)
                    if price <= 0:
                        return False, "Price must be positive."
                    return True, ""
                except:
                    return False, "Invalid price. Please enter a valid number."

            price = await get_user_input(
                "💲 Enter the price for your limit order:", validator=validate_price
            )
            if not price:
                return None
            trade_data["price"] = float(price)
        else:
            # For market orders, we'll get the current price for display purposes
            try:
                ticker_data = self.kucoin.get_ticker(trade_data["market"])
                if ticker_data and ticker_data.get("code") == "200000":
                    trade_data["price"] = float(ticker_data["data"]["price"])
                else:
                    # Use a placeholder if we can't get the current price
                    trade_data["price"] = 0.0
            except:
                trade_data["price"] = 0.0

        return trade_data

    async def _process_trade(self, ctx, market, side, amount, price=None, order_type="limit", is_real=False):
        """Process a trade with confirmation and execution

        Args:
            ctx: Discord context
            market: Trading pair
            side: buy or sell
            amount: Amount to trade
            price: Price for the order (required for limit orders)
            order_type: Type of order (market or limit)
            is_real: Whether this is a real trade

        Returns:
            bool: Whether the trade was completed
        """
        market = market.upper()
        side = side.lower()
        order_type = order_type.lower()

        # For market orders without a provided price, get current price for display
        if order_type == "market" and price is None:
            try:
                ticker_data = self.kucoin.get_ticker(market)
                if ticker_data and ticker_data.get("code") == "200000":
                    price = float(ticker_data["data"]["price"])
                else:
                    price = 0.0
            except:
                price = 0.0

        # Validate inputs for different order types
        if order_type == "limit" and price is None:
            await ctx.send("❌ Price is required for limit orders.")
            return False

        # Create confirmation embed
        if is_real:
            embed = discord.Embed(
                title="⚠️ REAL ORDER CONFIRMATION ⚠️",
                description="**WARNING: This will place a REAL order using REAL funds!**",
                color=discord.Color.red(),
            )
        else:
            embed = discord.Embed(
                title="📋 Confirm Test Trade",
                description="Please confirm you want to place the following order:",
                color=discord.Color.gold(),
            )

        try:
            # Get current price from KuCoin API for comparison
            ticker_data = self.kucoin.get_ticker(market)
            
            # Check if we got valid data
            if not ticker_data or ticker_data.get("code") != "200000":
                await ctx.send(f"❌ Error getting market data for {market}")
                return False
                
            current_price = float(ticker_data["data"]["price"])

            # Calculate total value based on order type
            if order_type == "limit":
                total_value = amount * price
            else:  # market order
                total_value = amount * current_price

            embed.add_field(name="Market", value=market, inline=True)
            embed.add_field(name="Side", value=side.upper(), inline=True)
            embed.add_field(name="Order Type", value=order_type.capitalize(), inline=True)
            embed.add_field(name="Amount", value=f"{amount}", inline=True)
            
            if order_type == "limit":
                embed.add_field(
                    name="Your Order Price", value=f"${price:.2f}", inline=True
                )
            
            embed.add_field(
                name="Current Market Price", value=f"${current_price:.2f}", inline=True
            )
            
            embed.add_field(
                name="Estimated Value", value=f"${total_value:.2f}", inline=True
            )

            # Add confirmation instructions using reactions
            footer = (
                "⚠️ React with ✅ to CONFIRM or ❌ to CANCEL ⚠️"
                if is_real
                else "React with ✅ to confirm or ❌ to cancel"
            )
            embed.set_footer(text=footer)

            # Send the embed and add reaction buttons
            message = await ctx.send(embed=embed)
            await message.add_reaction("✅")
            await message.add_reaction("❌")

            # Wait for user to click a reaction
            def check(reaction, user):
                return (
                    user == ctx.author
                    and reaction.message.id == message.id
                    and str(reaction.emoji) in ["✅", "❌"]
                )

            try:
                reaction, user = await self.bot.wait_for(
                    "reaction_add", timeout=60.0, check=check
                )

                if str(reaction.emoji) == "✅":
                    if is_real:
                        # Placeholder for real order - not implementing for safety
                        await ctx.send("⚠️ Real orders not implemented for safety reasons")
                        return False
                    else:
                        # Use the test order endpoint from KuCoin
                        if order_type == "limit":
                            order_result = self.kucoin.test_order(
                                order_type="limit",
                                symbol=market,
                                side=side,
                                price=str(price),
                                size=str(amount),
                                remark="Discord bot test order"
                            )
                        else:  # market order
                            # For market orders, use size for buy/sell amount
                            order_result = self.kucoin.test_order(
                                order_type="market",
                                symbol=market,
                                side=side,
                                size=str(amount),
                                price=None,  # No price for market orders
                                remark="Discord bot test order"
                            )

                        if order_result.get("code") == "200000":
                            success_embed = discord.Embed(
                                title="✅ Test Order Validated",
                                description="Order parameters have been validated by KuCoin",
                                color=discord.Color.green(),
                            )
                            
                            # Add order details from the API response
                            success_embed.add_field(
                                name="Market", value=market, inline=True
                            )
                            success_embed.add_field(
                                name="Side", value=side.upper(), inline=True
                            )
                            success_embed.add_field(
                                name="Order Type", value=order_type.capitalize(), inline=True
                            )
                            success_embed.add_field(
                                name="Amount", value=f"{amount}", inline=True
                            )
                            
                            if order_type == "limit":
                                success_embed.add_field(
                                    name="Price", value=f"${price:.2f}", inline=True
                                )
                                success_embed.add_field(
                                    name="Total", value=f"${total_value:.2f}", inline=True
                                )
                            
                            success_embed.add_field(
                                name="Status", value="VALIDATED (test)", inline=True
                            )

                            # Add KuCoin response data
                            if "data" in order_result:
                                for key, value in order_result["data"].items():
                                    success_embed.add_field(
                                        name=key.capitalize(), 
                                        value=str(value), 
                                        inline=True
                                    )
                        else:
                            # Handle API error
                            error_msg = order_result.get("msg", "Unknown error")
                            success_embed = discord.Embed(
                                title="❌ Test Order Error",
                                description=f"Error validating order: {error_msg}",
                                color=discord.Color.red(),
                            )

                        await ctx.send(embed=success_embed)
                        return True
                else:
                    await ctx.send("❌ Order canceled.")
                    return False

            except asyncio.TimeoutError:
                await ctx.send("⏱️ Confirmation timed out. Order canceled.")
                return False

        except Exception as e:
            await ctx.send(f"❌ Error creating order: {str(e)}")
            return False

    @commands.command(name="testtrade")
    async def test_trade(
        self, ctx, market: str = "BTC-USDT", side: str = "buy", amount: float = 0.001, 
        price: float = None, order_type: str = "limit"
    ):
        """
        Create a test trade with KuCoin API

        Parameters:
        market: Trading pair (e.g., BTC-USDT)
        side: buy or sell
        amount: Amount to trade
        price: Price for limit orders (optional for market orders)
        order_type: Type of order (market or limit, default is limit)

        Example: !testtrade BTC-USDT buy 0.001 50000 limit
        Example: !testtrade BTC-USDT sell 0.001 market
        """
        order_type = order_type.lower()
        
        # Set default price for limit orders if not provided
        if order_type == "limit" and price is None:
            try:
                ticker_data = self.kucoin.get_ticker(market)
                if ticker_data and ticker_data.get("code") == "200000":
                    price = float(ticker_data["data"]["price"])
                else:
                    await ctx.send("❌ Price is required for limit orders.")
                    return
            except Exception as e:
                await ctx.send(f"❌ Error getting current price: {str(e)}")
                return

        await self._process_trade(ctx, market, side, amount, price, order_type, is_real=False)

    @commands.command(name="interactivetrade")
    async def interactive_trade(self, ctx):
        """Interactive trading command that asks for each trade parameter including order type"""
        trade_data = await self._collect_trade_parameters(ctx, is_real=False)
        if trade_data:
            await self._process_trade(
                ctx,
                trade_data["market"],
                trade_data["side"],
                trade_data["amount"],
                trade_data.get("price"),  # Price might be None for market orders
                trade_data["order_type"],
                is_real=False,
            )

    @commands.command(name="realorder")
    async def real_order(self, ctx):
        """
        Create a real order on KuCoin (currently disabled for safety)
        """
        await ctx.send("⚠️ Real orders have been disabled for safety reasons in this implementation.")

    @commands.command(name="ticker")
    async def get_ticker(self, ctx, symbol: str = "BTC-USDT"):
        """Get ticker information for a trading pair on KuCoin"""
        try:
            ticker_data = self.kucoin.get_ticker(symbol)
            
            if not ticker_data or ticker_data.get("code") != "200000":
                await ctx.send(f"❌ Error getting ticker data for {symbol}: {ticker_data.get('msg', 'Unknown error')}")
                return

            # Extract the data part of the response
            ticker = ticker_data.get("data", {})
            
            embed = discord.Embed(
                title=f"{symbol} Ticker",
                description="Current market data from KuCoin",
                color=discord.Color.blue(),
            )
            
            # Add relevant ticker fields
            fields = [
                ("Sequence", "sequence"),
                ("Price", "price"),
                ("Size", "size"),
                ("Best Bid", "bestBid"),
                ("Best Bid Size", "bestBidSize"),
                ("Best Ask", "bestAsk"),
                ("Best Ask Size", "bestAskSize"),
                ("Time", "time")
            ]
            
            for label, key in fields:
                if key in ticker:
                    value = ticker[key]
                    # Format prices and sizes to look nicer
                    if key in ["price", "bestBid", "bestAsk"]:
                        try:
                            value = f"${float(value):.2f}"
                        except:
                            pass
                    # Format time if available
                    if key == "time":
                        try:
                            timestamp = int(value) / 1000  # Convert ms to seconds
                            value = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
                        except:
                            pass
                    embed.add_field(name=label, value=value, inline=True)
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"❌ Error fetching ticker: {str(e)}")

    @commands.command(name="fees")
    async def get_fees(self, ctx, symbol: str = "BTC-USDT"):
        """Get trading fees for a specific symbol on KuCoin"""
        try:
            fees_data = self.kucoin.get_trade_fees(symbol)
            
            if not fees_data or fees_data.get("code") != "200000":
                await ctx.send(f"❌ Error getting fee data: {fees_data.get('msg', 'Unknown error')}")
                return
            
            # Extract the fee data
            fees = fees_data.get("data", [])
            
            if not fees:
                await ctx.send(f"No fee data found for {symbol}")
                return
            
            embed = discord.Embed(
                title=f"Trading Fees",
                description=f"Fee information for requested symbols",
                color=discord.Color.blue(),
            )
            
            for fee_info in fees:
                symbol = fee_info.get("symbol", "Unknown")
                
                fee_details = ""
                if "takerFeeRate" in fee_info:
                    fee_details += f"Taker Fee: {float(fee_info['takerFeeRate'])*100:.4f}%\n"
                if "makerFeeRate" in fee_info:
                    fee_details += f"Maker Fee: {float(fee_info['makerFeeRate'])*100:.4f}%\n"
                
                embed.add_field(name=symbol, value=fee_details or "No fee data", inline=False)
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"❌ Error fetching fee data: {str(e)}")

    @commands.command(name="balance")
    async def show_balance(self, ctx):
        """Show your KuCoin account information (placeholder)"""
        await ctx.send("⚠️ Balance retrieval is not implemented in this simplified version for security reasons.")


async def setup(bot):
    """Add the TradingCommands cog to the bot"""
    await bot.add_cog(TradingCommands(bot))