import discord
from discord.ext import commands
import asyncio
from datetime import datetime
import os
from bitvavo_handler import BitvavoHandler


class TradingCommands(commands.Cog):
    """Discord cog for trading cryptocurrency with Bitvavo API"""

    def __init__(self, bot):
        self.bot = bot
        self.bitvavo = BitvavoHandler()

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
                markets = self.bitvavo.get_markets()
                available_markets = [m["market"] for m in markets]
                if value.upper() in available_markets:
                    return True, ""
                return False, f"Market {value} not found in available markets."
            except Exception as e:
                return False, f"Error validating market: {str(e)}"

        market = await get_user_input(
            "📊 Enter the trading pair (e.g., BTC-EUR):", validator=validate_market
        )
        if not market:
            return None
        trade_data["market"] = market.upper()

        # 2. Ask for side (buy/sell)
        def validate_side(value):
            if value.lower() in ["buy", "sell"]:
                return True, ""
            return False, "Invalid side. Please enter 'buy' or 'sell'."

        side = await get_user_input("📈 Buy or sell?", validator=validate_side)
        if not side:
            return None
        trade_data["side"] = side.lower()

        # 3. Ask for amount
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

        return trade_data

    async def _process_trade(self, ctx, market, side, amount, is_real=False):
        """Process a trade with confirmation and execution

        Args:
            ctx: Discord context
            market: Trading pair
            side: buy or sell
            amount: Amount to trade
            is_real: Whether this is a real trade

        Returns:
            bool: Whether the trade was completed
        """
        market = market.upper()
        side = side.lower()

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
            # Get current price
            ticker = self.bitvavo.get_ticker(market)
            current_price = float(ticker["price"])

            # Calculate total value
            total_value = amount * current_price

            embed.add_field(name="Market", value=market, inline=True)
            embed.add_field(name="Side", value=side.upper(), inline=True)
            embed.add_field(name="Amount", value=f"{amount}", inline=True)
            embed.add_field(
                name="Current Price", value=f"€{current_price:.2f}", inline=True
            )
            embed.add_field(
                name="Total Value", value=f"€{total_value:.2f}", inline=True
            )
            embed.add_field(
                name="Order Type", value="Market" if is_real else "Limit", inline=True
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
                        # Place a real market order
                        order = self.bitvavo.place_real_market_order(
                            market, side, amount
                        )

                        success_embed = discord.Embed(
                            title="✅ Real Order Placed",
                            description="A real order has been placed on Bitvavo",
                            color=discord.Color.green(),
                        )

                        # Add order details from the API response
                        success_embed.add_field(
                            name="Order ID",
                            value=order.get("orderId", "N/A"),
                            inline=False,
                        )
                        success_embed.add_field(
                            name="Market", value=market, inline=True
                        )
                        success_embed.add_field(
                            name="Side", value=side.upper(), inline=True
                        )
                        success_embed.add_field(
                            name="Amount", value=f"{amount}", inline=True
                        )
                        success_embed.add_field(
                            name="Order Type", value="Market", inline=True
                        )
                        success_embed.add_field(
                            name="Status",
                            value=order.get("status", "PLACED"),
                            inline=True,
                        )

                        # Add fills if available
                        if "fills" in order and order["fills"]:
                            fills = order["fills"]
                            for i, fill in enumerate(fills[:3]):  # Show up to 3 fills
                                fill_info = f"Price: {fill.get('price', 'N/A')}\n"
                                fill_info += f"Amount: {fill.get('amount', 'N/A')}\n"
                                fill_info += f"Fee: {fill.get('fee', 'N/A')} {fill.get('feeCurrency', '')}"
                                success_embed.add_field(
                                    name=f"Fill #{i+1}", value=fill_info, inline=True
                                )
                    else:
                        # Simulate placing an order
                        order = self.bitvavo.simulate_order(market, side, amount)

                        success_embed = discord.Embed(
                            title="✅ Test Order Placed",
                            description="A placeholder order has been created",
                            color=discord.Color.green(),
                        )
                        success_embed.add_field(
                            name="Order ID", value=order["orderId"], inline=False
                        )
                        success_embed.add_field(
                            name="Market", value=order["market"], inline=True
                        )
                        success_embed.add_field(
                            name="Side", value=side.upper(), inline=True
                        )
                        success_embed.add_field(
                            name="Amount", value=f"{amount}", inline=True
                        )
                        success_embed.add_field(
                            name="Price", value=f"€{current_price:.2f}", inline=True
                        )
                        success_embed.add_field(
                            name="Total", value=f"€{total_value:.2f}", inline=True
                        )
                        success_embed.add_field(
                            name="Status", value="PLACED (test)", inline=True
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
        self, ctx, market: str = "BTC-EUR", side: str = "buy", amount: float = 0.001
    ):
        """
        Create a test trade with Bitvavo API

        Parameters:
        market: Trading pair (e.g., BTC-EUR)
        side: buy or sell
        amount: Amount to trade

        Example: !testtrade BTC-EUR buy 0.001
        """
        await self._process_trade(ctx, market, side, amount, is_real=False)

    @commands.command(name="interactivetrade")
    async def interactive_trade(self, ctx):
        """Interactive trading command that asks for each trade parameter"""
        trade_data = await self._collect_trade_parameters(ctx, is_real=False)
        if trade_data:
            await self._process_trade(
                ctx,
                trade_data["market"],
                trade_data["side"],
                trade_data["amount"],
                is_real=False,
            )

    @commands.command(name="realorder")
    async def real_order(
        self, ctx, market: str = None, side: str = None, amount: str = None
    ):
        """
        Create a real order on Bitvavo

        Parameters:
        market: Trading pair (e.g., BTC-EUR)
        side: buy or sell
        amount: Amount to trade

        Example: !realorder BTC-EUR buy 0.001
           or   !realorder (for interactive mode)
        """
        # Interactive mode if parameters are not provided
        if not all([market, side, amount]):
            await ctx.send(
                "⚠️ **REAL ORDER MODE** - This will place actual orders with real funds!"
            )
            trade_data = await self._collect_trade_parameters(ctx, is_real=True)
            if trade_data:
                await self._process_trade(
                    ctx,
                    trade_data["market"],
                    trade_data["side"],
                    trade_data["amount"],
                    is_real=True,
                )
            return

        # Direct mode with parameters
        try:
            amount_float = float(amount)
            await self._process_trade(ctx, market, side, amount_float, is_real=True)
        except ValueError:
            await ctx.send("❌ Invalid amount. Please enter a valid number.")

    @commands.command(name="markets")
    async def list_markets(self, ctx, filter_str: str = None):
        """List available markets on Bitvavo"""
        try:
            markets = self.bitvavo.get_markets(filter_str)
            markets = markets[
                :25
            ]  # Limit to 25 results to avoid Discord message limits

            embed = discord.Embed(
                title="Bitvavo Markets",
                description=f"Showing {len(markets)} markets"
                + (f" containing '{filter_str}'" if filter_str else ""),
                color=discord.Color.blue(),
            )

            for market in markets:
                market_name = market["market"]
                status = market["status"]
                embed.add_field(
                    name=market_name,
                    value=f"Status: {status}\nBase: {market['base']}\nQuote: {market['quote']}",
                    inline=True,
                )

            await ctx.send(embed=embed)

        except Exception as e:
            await ctx.send(f"❌ Error fetching markets: {str(e)}")

    @commands.command(name="balance")
    async def show_balance(self, ctx, symbol: str = None):
        """Show your Bitvavo account balance"""
        try:
            if symbol:
                balance = self.bitvavo.get_balance(symbol.upper())

                embed = discord.Embed(
                    title=f"Bitvavo {symbol.upper()} Balance",
                    color=discord.Color.blue(),
                )

                # Safely access dictionary keys
                embed.add_field(
                    name="Symbol", value=balance.get("symbol", "N/A"), inline=True
                )
                embed.add_field(
                    name="Available", value=balance.get("available", "0"), inline=True
                )
                embed.add_field(
                    name="In Order", value=balance.get("inOrder", "0"), inline=True
                )

                await ctx.send(embed=embed)
            else:
                balances = self.bitvavo.get_balance()

                if not balances:
                    await ctx.send("No balances found or unable to retrieve balances")
                    return

                # Filter out zero balances if we have valid data
                try:
                    non_zero_balances = [
                        b
                        for b in balances
                        if float(b.get("available", "0")) > 0
                        or float(b.get("inOrder", "0")) > 0
                    ]
                except (ValueError, TypeError):
                    await ctx.send("Error processing balance data")
                    return

                if not non_zero_balances:
                    await ctx.send("No non-zero balances found")
                    return

                embed = discord.Embed(
                    title="Bitvavo Account Balance",
                    description=f"Showing {len(non_zero_balances)} currencies with non-zero balance",
                    color=discord.Color.blue(),
                )

                for balance in non_zero_balances[:25]:
                    symbol = balance.get("symbol", "Unknown")
                    available = balance.get("available", "0")
                    in_order = balance.get("inOrder", "0")

                    embed.add_field(
                        name=symbol,
                        value=f"Available: {available}\nIn Order: {in_order}",
                        inline=True,
                    )

                await ctx.send(embed=embed)

        except Exception as e:
            await ctx.send(f"❌ Error fetching balance: {str(e)}")
            import traceback

            traceback.print_exc()  # Print full error to console for debugging

    @commands.command(name="orders")
    async def list_orders(self, ctx, market: str = None):
        """List your open orders on Bitvavo"""
        try:
            if not market:
                await ctx.send("Please provide a market symbol (e.g., BTC-EUR)")
                return

            orders = self.bitvavo.get_orders(market.upper())

            if not orders:
                await ctx.send(f"No open orders found for {market.upper()}")
                return

            embed = discord.Embed(
                title=f"Open Orders for {market.upper()}",
                description=f"Showing {len(orders)} open orders",
                color=discord.Color.blue(),
            )

            for order in orders:
                order_id = order["orderId"]
                side = order["side"].upper()
                amount = order["amount"]
                price = order["price"]
                status = order["status"]
                remaining = order.get("remaining", "N/A")

                embed.add_field(
                    name=f"{side} Order #{order_id[:8]}...",
                    value=f"Amount: {amount}\nPrice: {price}\nRemaining: {remaining}\nStatus: {status}",
                    inline=True,
                )

            await ctx.send(embed=embed)

        except Exception as e:
            await ctx.send(f"❌ Error fetching orders: {str(e)}")


async def setup(bot):
    """Add the TradingCommands cog to the bot"""
    await bot.add_cog(TradingCommands(bot))
