import discord
from discord.ext import commands, tasks
import asyncio
import json
import os
from api import PricesAPI
from datetime import datetime
from config import ALERT_CHANNEL_ID, CHECK_INTERVAL


class StockAlerts(commands.Cog):
    """Discord cog for monitoring stock prices and sending alerts"""

    def __init__(self, bot):
        self.bot = bot
        self.alerts = {}  # {channel_id: [alert_configs]}
        self.test_tasks = {}  # {channel_id: task}
        self.load_alerts()
        self.check_price_alerts.start()

    def cog_unload(self):
        self.check_price_alerts.cancel()
        self.save_alerts()
        # Cancel any running test tasks
        for task in self.test_tasks.values():
            if not task.done():
                task.cancel()

    def load_alerts(self):
        """Load saved alerts from file"""
        try:
            # Create data directory if it doesn't exist
            os.makedirs("data", exist_ok=True)

            if os.path.exists("data/stock_alerts.json"):
                with open("data/stock_alerts.json", "r") as f:
                    data = json.load(f)
                    # Convert string keys back to integers for channel IDs
                    self.alerts = {int(k): v for k, v in data.items()}
                    print(
                        f"Loaded {sum(len(alerts) for alerts in self.alerts.values())} price alerts"
                    )
        except Exception as e:
            print(f"Error loading stock alerts: {e}")
            self.alerts = {}

    def save_alerts(self):
        """Save alerts to file"""
        try:
            # Create data directory if it doesn't exist
            os.makedirs("data", exist_ok=True)

            with open("data/stock_alerts.json", "w") as f:
                json.dump(self.alerts, f)
        except Exception as e:
            print(f"Error saving stock alerts: {e}")

    @commands.group(name="alert", invoke_without_command=True)
    async def alert(self, ctx):
        """Command group for stock price alerts"""
        await ctx.send(
            "Use `!alert add`, `!alert remove`, `!alert list`, or `!alert test` to manage stock alerts"
        )

    @alert.command(name="add")
    async def add_alert(self, ctx, ticker: str, alert_type: str, value: float):
        """Add a stock price alert

        Example:
        !alert add AAPL percent 5    - Alert when AAPL grows by 5%
        !alert add MSFT price 150    - Alert when MSFT reaches $150
        """
        ticker = ticker.upper()
        channel_id = ctx.channel.id

        if alert_type not in ["percent", "price"]:
            await ctx.send("Alert type must be either 'percent' or 'price'")
            return

        # Get current price as reference
        try:
            price_api = PricesAPI(
                ticker=ticker,
                interval="day",
                interval_multiplier=1,
                start_date=datetime.now().strftime("%Y-%m-%d"),
                end_date=datetime.now().strftime("%Y-%m-%d"),
                limit=1,
            )
            price_data = price_api.get_live_price()

            if not price_data or "price" not in price_data:
                await ctx.send(f"Could not get current price for {ticker}")
                return

            current_price = price_data["price"]

            # Create alert config
            alert_config = {
                "ticker": ticker,
                "type": alert_type,
                "value": value,
                "reference_price": current_price,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }

            # Add to alerts dict
            if channel_id not in self.alerts:
                self.alerts[channel_id] = []

            self.alerts[channel_id].append(alert_config)
            self.save_alerts()

            # Show confirmation
            if alert_type == "percent":
                target_price = current_price * (1 + value / 100)
                await ctx.send(
                    f"✅ Alert added: {ticker} grows by {value}% from ${current_price:.2f} to ${target_price:.2f}"
                )
            else:  # price
                direction = "reaches" if value > current_price else "drops to"
                await ctx.send(
                    f"✅ Alert added: {ticker} {direction} ${value:.2f} (currently ${current_price:.2f})"
                )

        except Exception as e:
            await ctx.send(f"Error adding alert: {str(e)}")

    @alert.command(name="remove")
    async def remove_alert(self, ctx, index: int = None):
        """Remove a stock price alert by index

        Example:
        !alert remove 2    - Removes alert at index 2
        !alert remove      - Lists alerts with indexes
        """
        channel_id = ctx.channel.id

        if channel_id not in self.alerts or not self.alerts[channel_id]:
            await ctx.send("No alerts set for this channel")
            return

        if index is None:
            # List alerts with indices for removal
            alert_list = self.alerts[channel_id]
            embed = discord.Embed(
                title="Stock Price Alerts",
                description="Use `!alert remove INDEX` to remove an alert",
                color=discord.Color.blue(),
            )

            for i, alert in enumerate(alert_list):
                ticker = alert["ticker"]
                if alert["type"] == "percent":
                    description = f"{ticker}: +{alert['value']}% from ${alert['reference_price']:.2f}"
                else:  # price
                    description = f"{ticker}: reaches ${alert['value']:.2f}"

                embed.add_field(name=f"Alert #{i}", value=description, inline=False)

            await ctx.send(embed=embed)
            return

        # Remove the alert at the specified index
        if 0 <= index < len(self.alerts[channel_id]):
            removed = self.alerts[channel_id].pop(index)
            self.save_alerts()
            await ctx.send(f"Removed alert for {removed['ticker']}")
        else:
            await ctx.send(f"Invalid index. Use `!alert remove` to see valid indices")

    @alert.command(name="list")
    async def list_alerts(self, ctx):
        """List all stock price alerts for this channel"""
        channel_id = ctx.channel.id

        if channel_id not in self.alerts or not self.alerts[channel_id]:
            await ctx.send("No alerts set for this channel")
            return

        embed = discord.Embed(
            title="Active Stock Price Alerts", color=discord.Color.blue()
        )

        for i, alert in enumerate(self.alerts[channel_id]):
            ticker = alert["ticker"]
            alert_type = alert["type"]
            value = alert["value"]
            ref_price = alert["reference_price"]

            if alert_type == "percent":
                target_price = ref_price * (1 + value / 100)
                description = (
                    f"+{value}% from ${ref_price:.2f}\nTarget: ${target_price:.2f}"
                )
            else:  # price
                direction = "above" if value > ref_price else "below"
                description = (
                    f"Price ${value:.2f} ({direction} reference ${ref_price:.2f})"
                )

            embed.add_field(name=f"#{i}: {ticker}", value=description, inline=True)

        await ctx.send(embed=embed)

    @alert.command(name="test")
    async def test_alerts(self, ctx):
        """Start a test to verify alert functionality by sending messages every second"""
        channel_id = ctx.channel.id

        # Check if a test is already running in this channel
        if channel_id in self.test_tasks and not self.test_tasks[channel_id].done():
            await ctx.send(
                "❌ A test is already running in this channel. Use `!end test` to stop it."
            )
            return

        await ctx.send(
            "✅ Starting alert system test. Will send a message every second. Type `!end test` to stop."
        )

        # Start the test task
        self.test_tasks[channel_id] = asyncio.create_task(self._run_test(ctx))

    @commands.command(name="end")
    async def end_test(self, ctx, command_type: str):
        """End a running test"""
        if command_type.lower() != "test":
            return

        channel_id = ctx.channel.id

        if channel_id in self.test_tasks and not self.test_tasks[channel_id].done():
            self.test_tasks[channel_id].cancel()
            await ctx.send("✅ Alert system test stopped.")
        else:
            await ctx.send("❌ No test is currently running in this channel.")

    async def _run_test(self, ctx):
        """Run the alert test, sending a message every second"""
        counter = 1
        try:
            while True:
                embed = discord.Embed(
                    title="🔔 Alert System Test",
                    description=f"This is test message #{counter}",
                    color=discord.Color.gold(),
                )
                embed.set_footer(text="Type !end test to stop this test")

                await ctx.send(embed=embed)
                counter += 1
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            # Task was cancelled by end_test command
            pass
        except Exception as e:
            await ctx.send(f"❌ Test stopped due to error: {str(e)}")

    @commands.command(name="watchlist")
    async def show_watchlist(self, ctx):
        """Show configured stocks to monitor from config.py"""
        from config import STOCKS

        embed = discord.Embed(
            title="Stock Watchlist",
            description="Configured stocks with price thresholds",
            color=discord.Color.blue(),
        )

        for ticker, thresholds in STOCKS.items():
            low = thresholds["low"]
            high = thresholds["high"]
            description = f"Low: ${low:.2f}\nHigh: ${high:.2f}"
            embed.add_field(name=ticker, value=description, inline=True)

        await ctx.send(embed=embed)

    @tasks.loop(seconds=CHECK_INTERVAL)
    async def check_price_alerts(self):
        """Check current prices against alerts periodically based on config"""
        if not self.alerts:
            return

        for channel_id, alert_list in list(self.alerts.items()):
            channel = self.bot.get_channel(channel_id)
            if not channel:
                # Channel was deleted or bot no longer has access
                del self.alerts[channel_id]
                continue

            triggered_indices = []

            for i, alert in enumerate(alert_list):
                ticker = alert["ticker"]
                alert_type = alert["type"]
                value = alert["value"]
                ref_price = alert["reference_price"]

                try:
                    # Get current price
                    price_api = PricesAPI(
                        ticker=ticker,
                        interval="day",
                        interval_multiplier=1,
                        start_date=datetime.now().strftime("%Y-%m-%d"),
                        end_date=datetime.now().strftime("%Y-%m-%d"),
                        limit=1,
                    )
                    price_data = price_api.get_live_price()

                    if not price_data or "price" not in price_data:
                        continue

                    current_price = price_data["price"]

                    # Check if alert conditions are met
                    if alert_type == "percent":
                        percent_change = ((current_price - ref_price) / ref_price) * 100
                        if percent_change >= value:
                            # Alert triggered
                            embed = discord.Embed(
                                title=f"🚀 {ticker} Price Alert Triggered!",
                                description=f"{ticker} has grown by {percent_change:.2f}% (target: {value}%)",
                                color=discord.Color.green(),
                            )
                            embed.add_field(
                                name="Reference Price",
                                value=f"${ref_price:.2f}",
                                inline=True,
                            )
                            embed.add_field(
                                name="Current Price",
                                value=f"${current_price:.2f}",
                                inline=True,
                            )
                            embed.add_field(
                                name="Gain",
                                value=f"${current_price - ref_price:.2f} (+{percent_change:.2f}%)",
                                inline=True,
                            )

                            await channel.send(embed=embed)
                            triggered_indices.append(i)

                    else:  # price alert
                        if (value > ref_price and current_price >= value) or (
                            value < ref_price and current_price <= value
                        ):
                            # Alert triggered
                            direction = (
                                "increased to" if value > ref_price else "decreased to"
                            )
                            embed = discord.Embed(
                                title=f"⚠️ {ticker} Price Alert Triggered!",
                                description=f"{ticker} has {direction} ${current_price:.2f} (target: ${value:.2f})",
                                color=discord.Color.gold(),
                            )
                            embed.add_field(
                                name="Reference Price",
                                value=f"${ref_price:.2f}",
                                inline=True,
                            )
                            embed.add_field(
                                name="Current Price",
                                value=f"${current_price:.2f}",
                                inline=True,
                            )

                            await channel.send(embed=embed)
                            triggered_indices.append(i)

                except Exception as e:
                    print(f"Error checking alert for {ticker}: {e}")

            # Remove triggered alerts (in reverse order to maintain indices)
            for index in sorted(triggered_indices, reverse=True):
                alert_list.pop(index)

            # If no alerts left for this channel, remove entry
            if not alert_list:
                del self.alerts[channel_id]

        # Save changes
        if triggered_indices:
            self.save_alerts()

    async def check_config_stocks(self):
        """Check configured stocks from config.py against thresholds"""
        from config import STOCKS

        # Get default alert channel from config
        channel = self.bot.get_channel(ALERT_CHANNEL_ID)
        if not channel:
            print(f"Warning: Alert channel {ALERT_CHANNEL_ID} not found")
            return

        for ticker, thresholds in STOCKS.items():
            try:
                # Get current price
                price_api = PricesAPI(
                    ticker=ticker,
                    interval="day",
                    interval_multiplier=1,
                    start_date=datetime.now().strftime("%Y-%m-%d"),
                    end_date=datetime.now().strftime("%Y-%m-%d"),
                    limit=1,
                )
                price_data = price_api.get_live_price()

                if not price_data or "price" not in price_data:
                    continue

                current_price = price_data["price"]
                low_threshold = thresholds["low"]
                high_threshold = thresholds["high"]

                # Check if price is outside thresholds
                if current_price <= low_threshold:
                    embed = discord.Embed(
                        title=f"📉 {ticker} Below Threshold Alert",
                        description=f"{ticker} has fallen below the configured threshold",
                        color=discord.Color.red(),
                    )
                    embed.add_field(
                        name="Current Price", value=f"${current_price:.2f}", inline=True
                    )
                    embed.add_field(
                        name="Threshold", value=f"${low_threshold:.2f}", inline=True
                    )
                    await channel.send(embed=embed)

                elif current_price >= high_threshold:
                    embed = discord.Embed(
                        title=f"📈 {ticker} Above Threshold Alert",
                        description=f"{ticker} has risen above the configured threshold",
                        color=discord.Color.green(),
                    )
                    embed.add_field(
                        name="Current Price", value=f"${current_price:.2f}", inline=True
                    )
                    embed.add_field(
                        name="Threshold", value=f"${high_threshold:.2f}", inline=True
                    )
                    await channel.send(embed=embed)

            except Exception as e:
                print(f"Error checking config stock {ticker}: {e}")

    @check_price_alerts.before_loop
    async def before_check_price_alerts(self):
        """Wait until the bot is ready before starting the alert loop"""
        await self.bot.wait_until_ready()
        # Also check config stocks whenever the task runs
        self.bot.loop.create_task(self.check_config_stocks())


async def setup(bot):
    """Add the StockAlerts cog to the bot"""
    await bot.add_cog(StockAlerts(bot))
