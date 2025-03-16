import discord
from discord.ext import commands
from datetime import datetime
import os
from kucoin_handler import KucoinAPI
import uuid

# Import utility functions
from utils.embed_utilities import (
    create_price_embed,
    create_order_embed,
    create_alert_embed,
)

from utils.validation_utilities import (
    validate_symbol,
    validate_side,
    validate_order_type,
    validate_positive_number,
    get_user_input,
    confirm_action
)


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
        # Dictionary to store order IDs for reactions
        self.order_id_messages = {}

    async def _collect_trade_parameters(self, ctx, is_real=False):
        """Collect trade parameters interactively

        Args:
            ctx: Discord context
            is_real: Whether this is for a real trade

        Returns:
            dict: Trade parameters or None if canceled
        """
        trade_data = {}

        # 1. Ask for market/trading pair
        market = await get_user_input(
            ctx,
            "📊 Enter the trading pair (e.g., BTC-USDT):",
            validator=validate_symbol,
            timeout=60
        )
        if not market:
            return None
        trade_data["market"] = market.upper()

        # 2. Ask for order type (market or limit)
        order_type = await get_user_input(
            ctx,
            "📝 Order type (market or limit)?",
            validator=validate_order_type,
            timeout=60
        )
        if not order_type:
            return None
        trade_data["order_type"] = order_type.lower()

        # 3. Ask for side (buy/sell)
        side = await get_user_input(
            ctx,
            "📈 Buy or sell?",
            validator=validate_side,
            timeout=60
        )
        if not side:
            return None
        trade_data["side"] = side.lower()

        # 4. Ask for amount
        def validate_amount(value):
            return validate_positive_number(value, min_value=0)

        amount = await get_user_input(
            ctx,
            "💰 Enter the amount to trade:",
            validator=validate_amount,
            timeout=60
        )
        if not amount:
            return None
        trade_data["amount"] = float(amount)

        # 5. For limit orders, we need price
        if trade_data["order_type"] == "limit":
            def validate_price(value):
                return validate_positive_number(value, min_value=0)

            price = await get_user_input(
                ctx,
                "💲 Enter the price for your limit order:",
                validator=validate_price,
                timeout=60
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

    async def _process_real_trade(self, ctx, market: str, side: str, amount: float, price: float = None, order_type: str = "limit", use_funds: bool = False):
        """Process a real trade on KuCoin

        Args:
            ctx: Discord context
            market: Trading pair
            side: buy or sell
            amount: Amount to trade (interpreted as size or funds based on use_funds)
            price: Price for limit orders (optional for market orders)
            order_type: Type of order (market or limit)
            use_funds: If True, treat amount as funds (total value) for market buy orders

        Returns:
            bool: Whether the trade was completed successfully
        """
        try:
            # Prepare order parameters
            side = side.lower()
            order_type = order_type.lower()
            market = market.upper()
            client_oid = str(uuid.uuid4())
            
            # Create an order based on the type
            if order_type == "limit":
                if price is None:
                    await ctx.send("❌ Price is required for limit orders.")
                    return False
                    
                response = self.kucoin.add_margin_order(
                    symbol=market,
                    side=side,
                    client_oid=client_oid,
                    order_type="limit",
                    price=str(price),
                    size=str(amount),
                    is_isolated=True,  # Using isolated margin trading
                    auto_borrow=False,  # Auto-borrow if needed
                    time_in_force="GTC"  # Good Till Canceled
                )
            else:  # market order
                if use_funds and side == "buy":
                    # Use funds parameter for market buy
                    response = self.kucoin.add_margin_order(
                        symbol=market,
                        side=side,
                        client_oid=client_oid,
                        order_type="market",
                        funds=str(amount),  # Use amount as funds
                        is_isolated=True,
                        auto_borrow=False
                    )
                else:
                    # Use size parameter (default behavior, and required for sell)
                    response = self.kucoin.add_margin_order(
                        symbol=market,
                        side=side,
                        client_oid=client_oid,
                        order_type="market",
                        size=str(amount),  # Use amount as size
                        is_isolated=True,
                        auto_borrow=False
                    )
            
            # Check if the order was successful
            if response.get("code") == "200000":
                # Use the utility function to create a success embed
                order_data = {
                    "market": market,
                    "side": side,
                    "type": order_type,
                    "price": price if order_type == "limit" else None,
                }
                
                # Add amount or funds based on order type
                if order_type == "market" and use_funds and side == "buy":
                    order_data["funds"] = amount
                else:
                    order_data["size"] = amount
                
                # Add response data
                if "data" in response:
                    order_data.update(response["data"])
                
                # Create the embed
                embed = create_order_embed(
                    order_data=order_data,
                    title=f"✅ {side.upper()} Order Placed",
                    is_success=True,
                    order_type=order_type,
                    side=side,
                    include_id=True
                )
                
                # Add footer for copying
                order_id = response.get("data", {}).get("orderId")
                if order_id:
                    embed.set_footer(text="Click 📋 below to copy the Order ID")
                
                # Send the message with the embed
                message = await ctx.send(embed=embed)
                
                # If we have an order ID, add the clipboard emoji reaction
                if order_id:
                    await message.add_reaction("📋")
                    # Store the message ID and order ID for later use
                    self.order_id_messages[message.id] = order_id
                
                return True
                
            else:
                # Handle error response
                error_msg = response.get("msg", "Unknown error")
                await ctx.send(f"❌ Failed to place order: {error_msg}")
                return False
                
        except Exception as e:
            await ctx.send(f"❌ Error placing order: {str(e)}")
            return False
    
    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        """Handle reaction adds for copying order IDs"""
        # Ignore bot's own reactions
        if user.bot:
            return
            
        # Check if this is a clipboard emoji on one of our order messages
        if str(reaction.emoji) == "📋" and reaction.message.id in self.order_id_messages:
            order_id = self.order_id_messages[reaction.message.id]
            
            # Send the order ID as a private message to the user
            try:
                await user.send(f"**Order ID for reference:** `{order_id}`\nYou can use this ID with the !cancel_order command.")
                # Also notify in the channel that the ID was sent
                await reaction.message.channel.send(
                    f"{user.mention} I've sent you the order ID in a private message.",
                    delete_after=10
                )
            except discord.Forbidden:
                # If we can't DM the user, just post it in the channel
                await reaction.message.channel.send(
                    f"{user.mention} Here's the order ID for reference: `{order_id}`",
                    delete_after=20
                )

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

        # Since this is a test trade, create a simulated response
        client_oid = str(uuid.uuid4())
        test_order_id = f"test-{int(datetime.now().timestamp())}"
        
        # Create order data for the embed
        order_data = {
            "market": market.upper(),
            "side": side,
            "type": order_type,
            "orderId": test_order_id,
            "size": str(amount),
        }
        
        if order_type == "limit" and price:
            order_data["price"] = price
            total_value = amount * price
            order_data["total"] = total_value
        
        # Create the embed using utility function
        embed = create_order_embed(
            order_data=order_data,
            title=f"🧪 TEST {side.upper()} Order Simulation",
            is_success=True,
            order_type=order_type,
            side=side
        )
        
        # Add test footer
        embed.set_footer(text="This is a test - no actual order was placed")
        
        # Send the message with the embed
        message = await ctx.send(embed=embed)
        
        # Add the clipboard emoji reaction for testing purposes
        await message.add_reaction("📋")
        # Store the test order ID
        self.order_id_messages[message.id] = test_order_id

    @commands.command(name="realorder")
    async def real_order(self, ctx, market: str = None, side: str = None, amount: str = None, 
                        price_or_type: str = None, order_type: str = "limit"):
        """
        Create a real order on KuCoin with direct parameters
        
        Usage: !realorder <market> <side> <amount> [price_or_type] [order_type]
        
        Examples:
        !realorder BTC-USDT buy 0.001 50000         (limit order to buy 0.001 BTC at $50000)
        !realorder BTC-USDT sell 0.001 market       (market order to sell 0.001 BTC)
        !realorder ETH-USDT buy 0.05 2000           (limit order to buy 0.05 ETH at $2000)
        !realorder ETH-USDT sell 0.05 market        (market order to sell 0.05 ETH)
        !realorder BTC-USDT buy 100 market funds    (market order to buy $100 worth of BTC)
        """
        # Security measure: Check if user has the correct role before proceeding
        required_role = discord.utils.get(ctx.guild.roles, name="Trading-Authorized")
        if required_role is None or required_role not in ctx.author.roles:
            await ctx.send("⛔ You don't have permission to place real orders. You need the 'Trading-Authorized' role.")
            return

        # Check if we have all required parameters
        if not all([market, side, amount]):
            await ctx.send("❌ Missing required parameters. Use: !realorder <market> <side> <amount> [price_or_type] [order_type]")
            return
        
        # Process parameters
        side = side.lower()
        if side not in ["buy", "sell"]:
            await ctx.send("❌ Invalid side. Must be 'buy' or 'sell'.")
            return
        
        # Check if using funds for market order
        use_funds = False
        if order_type.lower() == "funds":
            use_funds = True
            order_type = "market"
        
        # Check if the price_or_type parameter indicates market order
        if price_or_type and price_or_type.lower() == "market":
            order_type = "market"
            price = None
        else:
            if order_type.lower() == "market":
                price = None
            else:
                order_type = "limit"
                price = price_or_type
        
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
        
        # For market orders with no price specified, get current price for display
        if order_type == "market" and price is None:
            # Get current price for display purposes
            try:
                ticker_data = self.kucoin.get_ticker(market)
                if ticker_data and ticker_data.get("code") == "200000":
                    price = float(ticker_data["data"]["price"])
            except:
                pass

        # Create fields for confirmation embed
        fields = [
            ("Market", market.upper(), True),
            ("Side", side.upper(), True),
            ("Order Type", order_type.capitalize(), True),
        ]
        
        if order_type == "market" and use_funds and side == "buy":
            fields.append(("Funds to Use", f"${amount} USDT", True))
        else:
            # Specify what the amount refers to (BTC, ETH, etc.)
            base_currency = market.split("-")[0]  # Extract base currency from market pair
            fields.append(("Amount", f"{amount} {base_currency}", True))
        
        if order_type == "limit" and price is not None:
            fields.append(("Price", f"${price:.2f}", True))
        elif price is not None:
            fields.append(("Current Market Price", f"${price:.2f} (approximate)", True))
        
        # Use confirm_action utility for validation
        confirmed = await confirm_action(
            ctx,
            title="⚠️ WARNING: REAL ORDER REQUEST ⚠️",
            description="You are about to place an order using REAL funds. Are you sure you want to proceed?",
            color=discord.Color.red(),
            use_reactions=True
        )
        
        if confirmed:
            # Process the real trade
            await self._process_real_trade(
                ctx,
                market,
                side,
                amount,
                price,
                order_type,
                use_funds
            )
        else:
            await ctx.send("🛑 Order creation cancelled.")

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
            
            # Format timestamp if available
            if "time" in ticker:
                try:
                    timestamp = int(ticker["time"]) / 1000  # Convert ms to seconds
                    formatted_time = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
                    ticker["formattedTime"] = formatted_time
                except:
                    pass
            
            # Use the utility to create the price embed
            embed = create_price_embed(
                symbol=symbol,
                price_data=ticker,
                title_prefix="Market Data",
                show_additional_fields=True,
                footer_text=f"Data from KuCoin | Time: {ticker.get('formattedTime', 'N/A')}"
            )
            
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
            
            # Create fields for the embed
            fields = []
            for fee_info in fees:
                symbol_name = fee_info.get("symbol", "Unknown")
                
                fee_details = ""
                if "takerFeeRate" in fee_info:
                    fee_details += f"Taker Fee: {float(fee_info['takerFeeRate'])*100:.4f}%\n"
                if "makerFeeRate" in fee_info:
                    fee_details += f"Maker Fee: {float(fee_info['makerFeeRate'])*100:.4f}%\n"
                
                fields.append((symbol_name, fee_details or "No fee data", False))
            
            # Create the embed using utility
            embed = create_alert_embed(
                title="Trading Fees",
                description="Fee information for requested symbols",
                fields=fields,
                color=discord.Color.blue()
            )
            
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
                
                # Create fields for the embed
                fields = []
                
                # Add account status and debt ratio
                if "status" in asset_info:
                    status_value = asset_info["status"]
                    status_text = "Active" if status_value == "ACTIVATED" else status_value
                    fields.append(("Status", status_text, True))
                
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
                    
                    fields.append(("Debt Ratio", f"{debt_color} {debt_ratio:.2f}%", True))
                
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
                    
                    fields.append((f"{base_currency} (Base Asset)", "\n".join(base_info), False))
                
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
                    
                    fields.append((f"{quote_currency} (Quote Asset)", "\n".join(quote_info), False))
                
                # Add portfolio summary if available
                if "totalAssetOfQuoteCurrency" in account_data:
                    fields.append((
                        "Total Assets (Quote Currency)",
                        f"${float(account_data['totalAssetOfQuoteCurrency']):.2f}",
                        True
                    ))
                
                if "totalLiabilityOfQuoteCurrency" in account_data:
                    fields.append((
                        "Total Liabilities (Quote Currency)",
                        f"${float(account_data['totalLiabilityOfQuoteCurrency']):.2f}",
                        True
                    ))
                
                # Create timestamp footer if available
                footer_text = None
                if "timestamp" in account_data:
                    timestamp = int(account_data["timestamp"]) / 1000  # Convert ms to seconds
                    date_str = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
                    footer_text = f"Last updated: {date_str}"
                
                # Create the embed using utility
                embed = create_alert_embed(
                    title=f"🏦 {symbol} Isolated Margin Account",
                    description="Your KuCoin isolated margin account information",
                    fields=fields,
                    color=discord.Color.blue(),
                    footer_text=footer_text
                )
                
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
                
            # Create fields for trades
            fields = []
            
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
                fields.append((field_title, value, False))
                
                # If we're showing many trades, limit to avoid exceeding Discord's limits
                if i >= 9 and len(trades) > 10:
                    remaining = len(trades) - 10
                    fields.append((
                        f"+ {remaining} more trades", 
                        f"Use `!list_trades {symbol} {min(10, remaining)}` to see fewer trades at once",
                        False
                    ))
                    break
            
            # Add pagination info for footer
            footer_text = None
            if "totalNum" in trades_data.get("data", {}):
                total = trades_data["data"]["totalNum"]
                current_page = trades_data["data"].get("currentPage", 1)
                total_pages = trades_data["data"].get("totalPage", 1)
                footer_text = f"Page {current_page} of {total_pages} (Total: {total} trades)"
            
            # Create the embed using utility
            embed = create_alert_embed(
                title=f"Isolated Margin Trades for {symbol}",
                description=f"Showing up to {limit} recent trades",
                fields=fields,
                color=discord.Color.gold(),
                footer_text=footer_text
            )
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"❌ Error processing request: {str(e)}")

    @commands.command(name="filter_trades")
    async def filter_trades(self, ctx):
        """
        Interactive command to filter and display your isolated margin trade history
        """
        # Ask for symbol (optional)
        symbol_prompt = "Enter the trading pair (e.g., BTC-USDT) or type 'skip' to see all symbols:"
        def validate_symbol_or_skip(value):
            if value.lower() == "skip":
                return True, ""
            return validate_symbol(value)
        
        symbol_response = await get_user_input(
            ctx, 
            symbol_prompt, 
            validator=validate_symbol_or_skip
        )
        
        if symbol_response is None:
            return
        
        symbol = None if symbol_response.lower() == "skip" else symbol_response.upper()
        
        # Ask for side (optional)
        def validate_side_or_skip(value):
            if value.lower() == "skip":
                return True, ""
            return validate_side(value)
        
        side_response = await get_user_input(
            ctx,
            "Filter by side? Enter 'buy', 'sell', or 'skip' to see both:",
            validator=validate_side_or_skip
        )
        
        if side_response is None:
            return
        
        side = None if side_response.lower() == "skip" else side_response.lower()
        
        # Ask for time period (optional)
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
        
        days_response = await get_user_input(
            ctx,
            "Enter time period in days (e.g., 7 for past week) or 'skip' for default:",
            validator=validate_days
        )
        
        if days_response is None:
            return
        
        days = None if days_response.lower() == "skip" else int(days_response)
        
        # Ask for limit (optional)
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
        
        limit_response = await get_user_input(
            ctx,
            "Enter maximum number of trades to show (1-20) or 'skip' for default:",
            validator=validate_limit
        )
        
        if limit_response is None:
            return
        
        limit = None if limit_response.lower() == "skip" else int(limit_response)
        
        # Calculate time range if days parameter is provided
        start_at = None
        end_at = None
        if days:
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
                
            # Create title with filters info
            title = f"Filtered Isolated Margin Trades ({len(trades)})"
            if symbol:
                title += f" for {symbol}"
            if side:
                title += f" - {side.upper()}"
                
            # Create fields with filter info
            filter_info = []
            if symbol:
                filter_info.append(f"Symbol: {symbol}")
            if side:
                filter_info.append(f"Side: {side.upper()}")
            if days:
                filter_info.append(f"Time period: Last {days} days")
            if limit:
                filter_info.append(f"Limit: {limit} trades")
                
            field_list = []
            if filter_info:
                field_list.append(("Applied Filters", "\n".join(filter_info), False))
            
            # Format and add trade information to the fields
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
                
                field_list.append((field_title, value, False))
                
                # If we're showing many trades, limit to avoid exceeding Discord's limits
                if i >= 9 and len(trades) > 10:
                    remaining = len(trades) - 10
                    field_list.append((
                        f"+ {remaining} more trades", 
                        f"Run this command again with a smaller limit to see fewer trades at once",
                        False
                    ))
                    break
            
            # Add pagination info for footer
            footer_text = None
            if "totalNum" in trades_data.get("data", {}):
                total = trades_data["data"]["totalNum"]
                current_page = trades_data["data"].get("currentPage", 1)
                total_pages = trades_data["data"].get("totalPage", 1)
                footer_text = f"Page {current_page} of {total_pages} (Total: {total} trades)"
            
            # Create the embed using utility
            embed = create_alert_embed(
                title=title,
                description="Your KuCoin isolated margin trade history",
                fields=field_list,
                color=discord.Color.gold(),
                footer_text=footer_text
            )
            
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
            side = trade.get("side", "unknown")
            
            # Calculate time since trade
            timestamp = int(trade.get("createdAt", datetime.now().timestamp() * 1000)) / 1000
            trade_time = datetime.fromtimestamp(timestamp)
            time_diff = datetime.now() - trade_time
            
            # Format time difference in a human-readable way
            if time_diff.days > 0:
                time_ago = f"{time_diff.days} days ago"
            elif time_diff.seconds >= 3600:
                time_ago = f"{time_diff.seconds // 3600} hours ago"
            elif time_diff.seconds >= 60:
                time_ago = f"{time_diff.seconds // 60} minutes ago"
            else:
                time_ago = f"{time_diff.seconds} seconds ago"
            
            # Create order data for the embed
            order_data = {
                "symbol": symbol,
                "side": side,
                "type": trade.get("type", "unknown"),
                "price": trade.get("price", 0),
                "size": trade.get("size", 0),
                "funds": trade.get("funds", 0),
                "fee": trade.get("fee", 0),
                "feeCurrency": trade.get("feeCurrency", ""),
                "liquidity": trade.get("liquidity", ""),
                "orderId": trade.get("orderId", "")
            }
            
            # Format timestamp
            date_str = trade_time.strftime("%Y-%m-%d %H:%M:%S")
            footer_text = f"{date_str} ({time_ago})"
            
            # Create the embed using utility
            side_emoji = "🟢" if side == "buy" else "🔴" if side == "sell" else "⚪"
            embed = create_order_embed(
                order_data=order_data,
                title=f"{side_emoji} Last {symbol} Trade: {side.upper()}",
                is_success=True,
                order_type=trade.get("type", "unknown"),
                side=side,
                include_id=True
            )
            
            # Set the footer with time information
            embed.set_footer(text=footer_text)
            
            # Send the message and add clipboard reaction if there's an order ID
            if "orderId" in trade:
                message = await ctx.send(embed=embed)
                await message.add_reaction("📋")
                # Store the order ID
                self.order_id_messages[message.id] = trade["orderId"]
            else:
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
            order_id = await get_user_input(
                ctx,
                "Please enter the order ID you want to cancel:",
                timeout=30
            )
            
            if not order_id:
                return  # User cancelled or timed out
        
        # Confirmation before proceeding
        confirmed = await confirm_action(
            ctx,
            title="⚠️ Confirm Order Cancellation",
            description=f"Are you sure you want to cancel order ID: `{order_id}`?",
            color=discord.Color.gold(),
            use_reactions=False  # Use text confirmation instead
        )
        
        if not confirmed:
            await ctx.send("🛑 Order cancellation aborted.")
            return
        
        # Process the cancellation
        try:
            # Start with a processing message
            processing_message = await ctx.send("⏳ Processing order cancellation...")
            
            # Call the KuCoin API to cancel the order
            result = self.kucoin.cancel_order_by_id(order_id)
            
            # Check if the API call was successful
            if result and result.get("code") == "200000":
                # Create fields for success message
                fields = []
                
                # Add cancelled order ID if available
                if "data" in result:
                    cancelled_id = result["data"]
                    if cancelled_id:
                        fields.append(("Cancelled Order ID", f"`{cancelled_id}`", False))
                
                # Create success embed using utility
                embed = create_alert_embed(
                    title="✅ Order Cancelled Successfully",
                    description="The order has been cancelled.",
                    fields=fields,
                    color=discord.Color.green()
                )
                
                # Edit the processing message with success info
                await processing_message.edit(content=None, embed=embed)
            else:
                # Error message
                error_msg = result.get("msg", "Unknown error") if result else "No response from server"
                
                # Create error embed using utility
                embed = create_alert_embed(
                    title="❌ Error Cancelling Order",
                    description=f"Failed to cancel order: {error_msg}",
                    fields=[("Order ID", f"`{order_id}`", False)],
                    color=discord.Color.red()
                )
                
                # Edit the processing message with error info
                await processing_message.edit(content=None, embed=embed)
        
        except Exception as e:
            # Handle any exceptions during the process
            await ctx.send(f"❌ Error during order cancellation: {str(e)}")


async def setup(bot):
    """Add the TradingCommands cog to the bot"""
    await bot.add_cog(TradingCommands(bot))