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
    async def real_order(self, ctx, market: str = None, side: str = None, amount: str = None, 
                        price: str = None, order_type: str = "limit"):
        """
        Create a real order on KuCoin with direct parameters
        
        Usage: !realorder <market> <side> <amount> [price] [order_type]
        
        Examples:
        !realorder BTC-USDT buy 0.001 50000     (limit order to buy BTC at $50000)
        !realorder ETH-USDT sell 0.1 market     (market order to sell 0.1 ETH)
        """
        # Security measure: Check if user has the correct role before proceeding
        required_role = discord.utils.get(ctx.guild.roles, name="Trading-Authorized")
        if required_role is None or required_role not in ctx.author.roles:
            await ctx.send("⛔ You don't have permission to place real orders. You need the 'Trading-Authorized' role.")
            return

        # Check if we got direct parameters or need to collect interactively
        if not all([market, side, amount]):
            await ctx.send("⚠️ Missing required parameters. Starting interactive mode instead...")
            trade_data = await self._collect_trade_parameters(ctx, is_real=True)
            if not trade_data:
                return
            
            market = trade_data["market"]
            side = trade_data["side"]
            amount = trade_data["amount"]
            price = trade_data.get("price")
            order_type = trade_data["order_type"]
        else:
            # Process direct parameters
            side = side.lower()
            if side not in ["buy", "sell"]:
                await ctx.send("❌ Invalid side. Must be 'buy' or 'sell'.")
                return
            
            # Check if the last parameter is order type
            if price and price.lower() == "market":
                order_type = "market"
                price = None
            else:
                order_type = order_type.lower()
                if order_type not in ["limit", "market"]:
                    await ctx.send("❌ Invalid order type. Must be 'limit' or 'market'.")
                    return
                
                # If order type is market, price is not needed
                if order_type == "market":
                    price = None
            
            # Validate amount
            try:
                amount = float(amount)
                if amount <= 0:
                    await ctx.send("❌ Amount must be positive.")
                    return
            except ValueError:
                await ctx.send("❌ Invalid amount. Must be a number.")
                return
            
            # Validate price for limit orders
            if order_type == "limit" and price is not None:
                try:
                    price = float(price)
                    if price <= 0:
                        await ctx.send("❌ Price must be positive.")
                        return
                except ValueError:
                    await ctx.send("❌ Invalid price. Must be a number.")
                    return
            
            # For market orders with no price specified
            if order_type == "market" and price is None:
                # Get current price for display purposes
                try:
                    ticker_data = self.kucoin.get_ticker(market)
                    if ticker_data and ticker_data.get("code") == "200000":
                        price = float(ticker_data["data"]["price"])
                except:
                    pass

        # Show warning and get confirmation before proceeding
        warning = discord.Embed(
            title="⚠️ WARNING: REAL ORDER REQUEST ⚠️",
            description="You are about to place an order using REAL funds. Are you sure you want to proceed?",
            color=discord.Color.red()
        )
        
        # Add order details to the warning
        warning.add_field(name="Market", value=market.upper(), inline=True)
        warning.add_field(name="Side", value=side.upper(), inline=True)
        warning.add_field(name="Order Type", value=order_type.capitalize(), inline=True)
        warning.add_field(name="Amount", value=f"{amount}", inline=True)
        
        if order_type == "limit" and price is not None:
            warning.add_field(name="Price", value=f"${price:.8f}", inline=True)
        
        warning.set_footer(text="Reply with 'yes' to continue or 'no' to cancel")
        
        await ctx.send(embed=warning)
        
        def check(message):
            return message.author == ctx.author and message.channel == ctx.channel and message.content.lower() in ["yes", "no"]
        
        try:
            response = await self.bot.wait_for("message", timeout=30, check=check)
            if response.content.lower() != "yes":
                await ctx.send("🛑 Order creation cancelled.")
                return
        except asyncio.TimeoutError:
            await ctx.send("⏱️ No response received. Order creation cancelled.")
            return
        
        # Process the real trade
        await self._process_real_trade(
            ctx,
            market,
            side,
            amount,
            price,
            order_type
        )

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
    async def show_balance(self, ctx, symbol: str = "BTC-USDT"):
        """
        Show your KuCoin isolated margin account information
        
        Parameters:
        symbol: Trading pair to show balance for (default: BTC-USDT)
        
        Example: !balance ETH-USDT
        """
        # Security measure: Check if user has the correct role before proceeding
        required_role = discord.utils.get(ctx.guild.roles, name="Trading-Authorized")
        if required_role is None or required_role not in ctx.author.roles:
            await ctx.send("⛔ You don't have permission to view balance information. You need the 'Trading-Authorized' role.")
            return
        
        # Show processing message
        processing_message = await ctx.send(f"⏳ Retrieving isolated margin account information for {symbol}...")
        
        try:
            # Call the KuCoin API to get isolated margin account info
            result = self.kucoin.get_isolated_margin_accounts(symbol=symbol)
            
            # Check if the API call was successful
            if result and result.get("code") == "200000":
                # Extract the data
                account_data = result.get("data", {})
                assets = account_data.get("assets", [])
                
                if not assets:
                    await processing_message.edit(content=f"No isolated margin account data found for {symbol}.")
                    return
                
                # Find the asset that matches the requested symbol
                asset_info = None
                for asset in assets:
                    if asset.get("symbol") == symbol:
                        asset_info = asset
                        break
                
                if not asset_info:
                    await processing_message.edit(content=f"No isolated margin account data found for {symbol}.")
                    return
                
                # Create embed with account information
                embed = discord.Embed(
                    title=f"🏦 {symbol} Isolated Margin Account",
                    description="Your KuCoin isolated margin account information",
                    color=discord.Color.blue()
                )
                
                # Add account status and debt ratio
                if "status" in asset_info:
                    status_value = asset_info["status"]
                    status_text = "Active" if status_value == "ACTIVATED" else status_value
                    embed.add_field(
                        name="Status",
                        value=status_text,
                        inline=True
                    )
                
                if "debtRatio" in asset_info:
                    debt_ratio = float(asset_info["debtRatio"]) * 100
                    # Color-code debt ratio based on risk level
                    debt_color = "🟢"  # Low risk
                    if debt_ratio > 80:
                        debt_color = "🔴"  # High risk
                    elif debt_ratio > 50:
                        debt_color = "🟠"  # Medium risk
                    elif debt_ratio > 30:
                        debt_color = "🟡"  # Moderate risk
                    
                    embed.add_field(
                        name="Debt Ratio",
                        value=f"{debt_color} {debt_ratio:.2f}%",
                        inline=True
                    )
                
                # Add base asset information (e.g., BTC)
                if "baseAsset" in asset_info:
                    base_asset = asset_info["baseAsset"]
                    base_currency = base_asset.get("currency", "Unknown")
                    
                    base_info = []
                    if "total" in base_asset:
                        base_info.append(f"Total: {float(base_asset['total']):.8f}")
                    if "available" in base_asset:
                        base_info.append(f"Available: {float(base_asset['available']):.8f}")
                    if "borrowed" in base_asset:
                        base_info.append(f"Borrowed: {float(base_asset['borrowed']):.8f}")
                    if "interest" in base_asset:
                        base_info.append(f"Interest: {float(base_asset['interest']):.8f}")
                    if "borrowEnabled" in base_asset:
                        borrow_status = "Enabled" if base_asset['borrowEnabled'] else "Disabled"
                        base_info.append(f"Borrowing: {borrow_status}")
                    if "repayEnabled" in base_asset:
                        repay_status = "Enabled" if base_asset['repayEnabled'] else "Disabled"
                        base_info.append(f"Repayment: {repay_status}")
                    
                    embed.add_field(
                        name=f"{base_currency} (Base Asset)",
                        value="\n".join(base_info),
                        inline=False
                    )
                
                # Add quote asset information (e.g., USDT)
                if "quoteAsset" in asset_info:
                    quote_asset = asset_info["quoteAsset"]
                    quote_currency = quote_asset.get("currency", "Unknown")
                    
                    quote_info = []
                    if "total" in quote_asset:
                        quote_info.append(f"Total: {float(quote_asset['total']):.2f}")
                    if "available" in quote_asset:
                        quote_info.append(f"Available: {float(quote_asset['available']):.2f}")
                    if "borrowed" in quote_asset:
                        quote_info.append(f"Borrowed: {float(quote_asset['borrowed']):.2f}")
                    if "interest" in quote_asset:
                        quote_info.append(f"Interest: {float(quote_asset['interest']):.2f}")
                    if "borrowEnabled" in quote_asset:
                        borrow_status = "Enabled" if quote_asset['borrowEnabled'] else "Disabled"
                        quote_info.append(f"Borrowing: {borrow_status}")
                    if "repayEnabled" in quote_asset:
                        repay_status = "Enabled" if quote_asset['repayEnabled'] else "Disabled"
                        quote_info.append(f"Repayment: {repay_status}")
                    
                    embed.add_field(
                        name=f"{quote_currency} (Quote Asset)",
                        value="\n".join(quote_info),
                        inline=False
                    )
                
                # Add portfolio summary if available
                if "totalAssetOfQuoteCurrency" in account_data:
                    embed.add_field(
                        name="Total Assets (Quote Currency)",
                        value=f"${float(account_data['totalAssetOfQuoteCurrency']):.2f}",
                        inline=True
                    )
                
                if "totalLiabilityOfQuoteCurrency" in account_data:
                    embed.add_field(
                        name="Total Liabilities (Quote Currency)",
                        value=f"${float(account_data['totalLiabilityOfQuoteCurrency']):.2f}",
                        inline=True
                    )
                
                # Add timestamp if available
                if "timestamp" in account_data:
                    from datetime import datetime
                    timestamp = int(account_data["timestamp"]) / 1000  # Convert ms to seconds
                    date_str = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
                    embed.set_footer(text=f"Last updated: {date_str}")
                
                # Edit the processing message with the embed
                await processing_message.edit(content=None, embed=embed)
            else:
                # Error message
                error_msg = result.get("msg", "Unknown error") if result else "No response from server"
                await processing_message.edit(content=f"❌ Error retrieving account information: {error_msg}")
        
        except Exception as e:
            # Handle any exceptions during the process
            await processing_message.edit(content=f"❌ Error retrieving account information: {str(e)}")

    @commands.command(name="list_trades")
    async def list_trades(self, ctx, symbol: str = "BTC-USDT", limit: int = 20):
        """
        Show your isolated margin trade history on KuCoin
        
        Parameters:
        symbol: Trading pair (e.g., BTC-USDT) - optional, defaults to BTC-USDT
        limit: Maximum number of trades to show - optional, defaults to 20
        
        Example: !list_trades ETH-USDT 10
        """
        try:
            # Call the API to get isolated margin trade fills
            trades_data = self.kucoin.get_filled_list(
                symbol=symbol,
                limit=limit,
                trade_type="MARGIN_ISOLATED_TRADE"  # Set to isolated margin trading
            )
            
            if not trades_data or trades_data.get("code") != "200000":
                await ctx.send(f"❌ Error retrieving trade history: {trades_data.get('msg', 'Unknown error')}")
                return
                
            # Extract the items from the response
            trades = trades_data.get("data", {}).get("items", [])
            
            if not trades:
                await ctx.send("No trades found matching your criteria.")
                return
                
            # Create embed for displaying trades
            embed = discord.Embed(
                title=f"Isolated Margin Trades for {symbol}",
                description=f"Showing up to {limit} recent trades",
                color=discord.Color.gold(),
            )
            
            # Add pagination info if available
            if "totalNum" in trades_data.get("data", {}):
                total = trades_data["data"]["totalNum"]
                current_page = trades_data["data"].get("currentPage", 1)
                total_pages = trades_data["data"].get("totalPage", 1)
                
                embed.set_footer(text=f"Page {current_page} of {total_pages} (Total: {total} trades)")
            
            # Format and add trade information to the embed
            for i, trade in enumerate(trades):
                # Create a field title with trade number and symbol
                field_title = f"Trade #{i+1}: {trade.get('symbol', 'Unknown')}"
                
                # Format trade details
                details = []
                
                # Add side with emoji
                trade_side = trade.get("side", "unknown")
                side_emoji = "🟢" if trade_side == "buy" else "🔴" if trade_side == "sell" else "⚪"
                details.append(f"{side_emoji} {trade_side.upper()}")
                
                # Add price and size
                if "price" in trade and "size" in trade:
                    details.append(f"Price: ${float(trade['price']):.8f}")
                    details.append(f"Size: {float(trade['size']):.8f}")
                    
                # Add total funds
                if "funds" in trade:
                    details.append(f"Total: ${float(trade['funds']):.8f}")
                    
                # Add fee information
                if "fee" in trade and "feeCurrency" in trade:
                    details.append(f"Fee: {float(trade['fee']):.8f} {trade['feeCurrency']}")
                    
                # Add order type
                if "type" in trade:
                    details.append(f"Type: {trade['type']}")
                    
                # Add liquidity role (maker/taker)
                if "liquidity" in trade:
                    details.append(f"Role: {trade['liquidity']}")
                    
                # Add timestamp
                if "createdAt" in trade:
                    from datetime import datetime
                    timestamp = int(trade["createdAt"]) / 1000  # Convert ms to seconds
                    date_str = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
                    details.append(f"Time: {date_str}")
                    
                # Add order ID (shortened)
                if "orderId" in trade:
                    order_id = trade["orderId"]
                    short_id = f"{order_id[:8]}...{order_id[-8:]}" if len(order_id) > 16 else order_id
                    details.append(f"Order ID: {short_id}")
                    
                # Join all details with newlines
                value = "\n".join(details)
                
                # Add field to embed
                embed.add_field(name=field_title, value=value, inline=False)
                
                # If we're showing many trades, limit to avoid exceeding Discord's limits
                if i >= 9 and len(trades) > 10:
                    remaining = len(trades) - 10
                    embed.add_field(
                        name=f"+ {remaining} more trades", 
                        value=f"Use `!list_trades {symbol} {min(10, remaining)}` to see fewer trades at once",
                        inline=False
                    )
                    break
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"❌ Error processing request: {str(e)}")

    @commands.command(name="filter_trades")
    async def filter_trades(self, ctx):
        """
        Interactive command to filter and display your isolated margin trade history
        """
        # Helper function for collecting user input
        async def get_user_input(prompt, timeout=60, validator=None):
            prompt_msg = await ctx.send(prompt)

            def check(message):
                return message.author == ctx.author and message.channel == ctx.channel

            try:
                user_response = await self.bot.wait_for(
                    "message", timeout=timeout, check=check
                )
                if user_response.content.lower() in ["cancel", "exit", "quit"]:
                    await ctx.send("🛑 Command cancelled.")
                    return None
                    
                if validator:
                    result, error_msg = validator(user_response.content)
                    if not result:
                        await ctx.send(f"❌ {error_msg} Please try again or type 'cancel' to exit.")
                        return await get_user_input(prompt, timeout, validator)
                return user_response.content
            except asyncio.TimeoutError:
                await ctx.send("⏱️ No input received. Command cancelled.")
                return None

        # Ask for symbol (optional)
        symbol_prompt = "Enter the trading pair (e.g., BTC-USDT) or type 'skip' to see all symbols:"
        def validate_symbol(value):
            if value.lower() == "skip":
                return True, ""
            value = value.upper()
            if "-" in value and len(value.split("-")) == 2:
                return True, ""
            return False, f"Symbol {value} doesn't seem to be in the correct format (e.g., BTC-USDT)."
        
        symbol_response = await get_user_input(symbol_prompt, validator=validate_symbol)
        if symbol_response is None:
            return
        
        symbol = None if symbol_response.lower() == "skip" else symbol_response.upper()
        
        # Ask for side (optional)
        side_prompt = "Filter by side? Enter 'buy', 'sell', or 'skip' to see both:"
        def validate_side(value):
            if value.lower() in ["buy", "sell", "skip"]:
                return True, ""
            return False, "Invalid side. Please enter 'buy', 'sell', or 'skip'."
        
        side_response = await get_user_input(side_prompt, validator=validate_side)
        if side_response is None:
            return
        
        side = None if side_response.lower() == "skip" else side_response.lower()
        
        # Ask for time period (optional)
        time_prompt = "Enter time period in days (e.g., 7 for past week) or 'skip' for default:"
        def validate_days(value):
            if value.lower() == "skip":
                return True, ""
            try:
                days = int(value)
                if days < 1 or days > 30:
                    return False, "Days must be between 1 and 30."
                return True, ""
            except:
                return False, "Invalid number. Please enter a number between 1 and 30."
        
        days_response = await get_user_input(time_prompt, validator=validate_days)
        if days_response is None:
            return
        
        days = None if days_response.lower() == "skip" else int(days_response)
        
        # Ask for limit (optional)
        limit_prompt = "Enter maximum number of trades to show (1-20) or 'skip' for default:"
        def validate_limit(value):
            if value.lower() == "skip":
                return True, ""
            try:
                limit = int(value)
                if limit < 1 or limit > 20:
                    return False, "Limit must be between 1 and 20."
                return True, ""
            except:
                return False, "Invalid number. Please enter a number between 1 and 20."
        
        limit_response = await get_user_input(limit_prompt, validator=validate_limit)
        if limit_response is None:
            return
        
        limit = None if limit_response.lower() == "skip" else int(limit_response)
        
        # Calculate time range if days parameter is provided
        start_at = None
        end_at = None
        if days:
            from datetime import datetime, timedelta
            end_at = int(datetime.now().timestamp() * 1000)
            start_at = int((datetime.now() - timedelta(days=days)).timestamp() * 1000)
        
        # Set default symbol if none specified
        if not symbol:
            symbol = "BTC-USDT"
        
        # Set default limit if none specified
        if not limit:
            limit = 20
        
        # Call the API to get filtered trades
        try:
            trades_data = self.kucoin.get_filled_list(
                symbol=symbol,
                side=side,
                start_at=start_at,
                end_at=end_at,
                limit=limit,
                trade_type="MARGIN_ISOLATED_TRADE"  # Set to isolated margin trading
            )
            
            if not trades_data or trades_data.get("code") != "200000":
                await ctx.send(f"❌ Error retrieving trade history: {trades_data.get('msg', 'Unknown error')}")
                return
                
            # Extract the items from the response
            trades = trades_data.get("data", {}).get("items", [])
            
            if not trades:
                await ctx.send("No trades found matching your criteria.")
                return
                
            # Create embed for displaying trades
            title = f"Filtered Isolated Margin Trades ({len(trades)})"
            if symbol:
                title += f" for {symbol}"
            if side:
                title += f" - {side.upper()}"
                
            embed = discord.Embed(
                title=title,
                description="Your KuCoin isolated margin trade history",
                color=discord.Color.gold(),
            )
            
            # Add filter information
            filter_info = []
            if symbol:
                filter_info.append(f"Symbol: {symbol}")
            if side:
                filter_info.append(f"Side: {side.upper()}")
            if days:
                filter_info.append(f"Time period: Last {days} days")
            if limit:
                filter_info.append(f"Limit: {limit} trades")
                
            if filter_info:
                embed.add_field(
                    name="Applied Filters",
                    value="\n".join(filter_info),
                    inline=False
                )
            
            # Add pagination info if available
            if "totalNum" in trades_data.get("data", {}):
                total = trades_data["data"]["totalNum"]
                current_page = trades_data["data"].get("currentPage", 1)
                total_pages = trades_data["data"].get("totalPage", 1)
                
                embed.set_footer(text=f"Page {current_page} of {total_pages} (Total: {total} trades)")
            
            # Format and add trade information to the embed (same as in list_trades)
            for i, trade in enumerate(trades):
                # Create a field title with trade number and symbol
                field_title = f"Trade #{i+1}: {trade.get('symbol', 'Unknown')}"
                
                # Format trade details
                details = []
                
                # Add side with emoji
                trade_side = trade.get("side", "unknown")
                side_emoji = "🟢" if trade_side == "buy" else "🔴" if trade_side == "sell" else "⚪"
                details.append(f"{side_emoji} {trade_side.upper()}")
                
                # Add price and size
                if "price" in trade and "size" in trade:
                    details.append(f"Price: ${float(trade['price']):.8f}")
                    details.append(f"Size: {float(trade['size']):.8f}")
                    
                # Add total funds
                if "funds" in trade:
                    details.append(f"Total: ${float(trade['funds']):.8f}")
                    
                # Add fee information
                if "fee" in trade and "feeCurrency" in trade:
                    details.append(f"Fee: {float(trade['fee']):.8f} {trade['feeCurrency']}")
                    
                # Add order type
                if "type" in trade:
                    details.append(f"Type: {trade['type']}")
                    
                # Add liquidity role (maker/taker)
                if "liquidity" in trade:
                    details.append(f"Role: {trade['liquidity']}")
                    
                # Add timestamp
                if "createdAt" in trade:
                    from datetime import datetime
                    timestamp = int(trade["createdAt"]) / 1000  # Convert ms to seconds
                    date_str = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
                    details.append(f"Time: {date_str}")
                    
                # Add order ID (shortened)
                if "orderId" in trade:
                    order_id = trade["orderId"]
                    short_id = f"{order_id[:8]}...{order_id[-8:]}" if len(order_id) > 16 else order_id
                    details.append(f"Order ID: {short_id}")
                    
                # Join all details with newlines
                value = "\n".join(details)
                
                # Add field to embed
                embed.add_field(name=field_title, value=value, inline=False)
                
                # If we're showing many trades, limit to avoid exceeding Discord's limits
                if i >= 9 and len(trades) > 10:
                    remaining = len(trades) - 10
                    embed.add_field(
                        name=f"+ {remaining} more trades", 
                        value=f"Run this command again with a smaller limit to see fewer trades at once",
                        inline=False
                    )
                    break
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"❌ Error processing request: {str(e)}")


    @commands.command(name="last_trade")
    async def last_trade(self, ctx, symbol: str = "BTC-USDT"):
        """
        Show your most recent isolated margin trade for a symbol
        
        Parameters:
        symbol: Trading pair (e.g., BTC-USDT) - optional, defaults to BTC-USDT
        
        Example: !last_trade ETH-USDT
        """
        try:
            # Call the API to get just the last trade
            trades_data = self.kucoin.get_filled_list(
                symbol=symbol,
                limit=10,  # Minimum required by API
                trade_type="MARGIN_ISOLATED_TRADE"
            )
            
            if not trades_data or trades_data.get("code") != "200000":
                await ctx.send(f"❌ Error retrieving trade history: {trades_data.get('msg', 'Unknown error')}")
                return
                
            # Extract the items from the response
            trades = trades_data.get("data", {}).get("items", [])
            
            if not trades:
                await ctx.send(f"No recent trades found for {symbol}.")
                return
            
            # Get just the most recent trade
            trade = trades[0]
            
            # Create a compact embed for the single trade
            side = trade.get("side", "unknown")
            side_emoji = "🟢" if side == "buy" else "🔴" if side == "sell" else "⚪"
            
            embed = discord.Embed(
                title=f"{side_emoji} Last {symbol} Trade: {side.upper()}",
                color=discord.Color.green() if side == "buy" else discord.Color.red(),
            )
            
            # Add core trade details
            if "price" in trade and "size" in trade:
                embed.add_field(
                    name="Price",
                    value=f"${float(trade['price']):.8f}",
                    inline=True
                )
                embed.add_field(
                    name="Size",
                    value=f"{float(trade['size']):.8f}",
                    inline=True
                )
            
            # Add total value
            if "funds" in trade:
                embed.add_field(
                    name="Total Value",
                    value=f"${float(trade['funds']):.8f}",
                    inline=True
                )
            
            # Add fee details
            if "fee" in trade and "feeCurrency" in trade:
                embed.add_field(
                    name="Fee",
                    value=f"{float(trade['fee']):.8f} {trade['feeCurrency']}",
                    inline=True
                )
            
            # Add order type and liquidity role
            if "type" in trade:
                embed.add_field(
                    name="Type",
                    value=f"{trade['type']}",
                    inline=True
                )
            
            if "liquidity" in trade:
                embed.add_field(
                    name="Role",
                    value=f"{trade['liquidity']}",
                    inline=True
                )
            
            # Add timestamp
            if "createdAt" in trade:
                from datetime import datetime
                timestamp = int(trade["createdAt"]) / 1000  # Convert ms to seconds
                date_str = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
                
                # Calculate time since trade
                now = datetime.now()
                trade_time = datetime.fromtimestamp(timestamp)
                time_diff = now - trade_time
                
                # Format time difference in a human-readable way
                if time_diff.days > 0:
                    time_ago = f"{time_diff.days} days ago"
                elif time_diff.seconds >= 3600:
                    time_ago = f"{time_diff.seconds // 3600} hours ago"
                elif time_diff.seconds >= 60:
                    time_ago = f"{time_diff.seconds // 60} minutes ago"
                else:
                    time_ago = f"{time_diff.seconds} seconds ago"
                
                embed.set_footer(text=f"{date_str} ({time_ago})")
            
            # Add order ID as a smaller note
            if "orderId" in trade:
                order_id = trade["orderId"]
                embed.description = f"Order ID: {order_id}"
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"❌ Error retrieving last trade: {str(e)}")

    @commands.command(name="cancel_order")
    async def cancel_order(self, ctx, order_id: str = None):
        """
        Cancel an existing order on KuCoin by its order ID
        
        Parameters:
        order_id: The unique ID of the order to cancel
        
        Example: !cancel_order 5bd6e9286d99522a52e458de
        """
        # Security measure: Check if user has the correct role before proceeding
        required_role = discord.utils.get(ctx.guild.roles, name="Trading-Authorized")
        if required_role is None or required_role not in ctx.author.roles:
            await ctx.send("⛔ You don't have permission to cancel orders. You need the 'Trading-Authorized' role.")
            return
        
        # If no order ID was provided, ask for it interactively
        if not order_id:
            await ctx.send("Please enter the order ID you want to cancel:")
            
            def check(message):
                return message.author == ctx.author and message.channel == ctx.channel
            
            try:
                response = await self.bot.wait_for("message", timeout=30, check=check)
                order_id = response.content.strip()
            except asyncio.TimeoutError:
                await ctx.send("⏱️ No response received. Cancellation aborted.")
                return
        
        # Confirmation before proceeding
        confirm_embed = discord.Embed(
            title="⚠️ Confirm Order Cancellation",
            description=f"Are you sure you want to cancel order ID: `{order_id}`?",
            color=discord.Color.gold()
        )
        confirm_embed.set_footer(text="Reply with 'yes' to confirm or 'no' to abort")
        
        await ctx.send(embed=confirm_embed)
        
        def confirm_check(message):
            return message.author == ctx.author and message.channel == ctx.channel and message.content.lower() in ["yes", "no"]
        
        try:
            response = await self.bot.wait_for("message", timeout=30, check=confirm_check)
            if response.content.lower() != "yes":
                await ctx.send("🛑 Order cancellation aborted.")
                return
        except asyncio.TimeoutError:
            await ctx.send("⏱️ No confirmation received. Cancellation aborted.")
            return
        
        # Process the cancellation
        try:
            # Start with a processing message
            processing_message = await ctx.send("⏳ Processing order cancellation...")
            
            # Call the KuCoin API to cancel the order
            result = self.kucoin.cancel_order_by_id(order_id)
            
            # Check if the API call was successful
            if result and result.get("code") == "200000":
                # Success message
                success_embed = discord.Embed(
                    title="✅ Order Cancelled Successfully",
                    description=f"The order has been cancelled.",
                    color=discord.Color.green()
                )
                
                # Add any additional information returned by the API
                if "data" in result:
                    # The API might return the cancelled order ID in the data field
                    cancelled_id = result["data"]
                    if cancelled_id:
                        success_embed.add_field(
                            name="Cancelled Order ID", 
                            value=f"`{cancelled_id}`",
                            inline=False
                        )
                
                # Edit the processing message with success info
                await processing_message.edit(content=None, embed=success_embed)
            else:
                # Error message
                error_msg = result.get("msg", "Unknown error") if result else "No response from server"
                error_embed = discord.Embed(
                    title="❌ Error Cancelling Order",
                    description=f"Failed to cancel order: {error_msg}",
                    color=discord.Color.red()
                )
                error_embed.add_field(
                    name="Order ID", 
                    value=f"`{order_id}`",
                    inline=False
                )
                
                # Edit the processing message with error info
                await processing_message.edit(content=None, embed=error_embed)
        
        except Exception as e:
            # Handle any exceptions during the process
            await ctx.send(f"❌ Error during order cancellation: {str(e)}")

async def setup(bot):
    """Add the TradingCommands cog to the bot"""
    await bot.add_cog(TradingCommands(bot))