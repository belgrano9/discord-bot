import discord
from discord.ext import commands, tasks
import asyncio
import json
import os
from api.prices import PricesAPI
from datetime import datetime
from config import ALERT_CHANNEL_ID, CHECK_INTERVAL
from logging_setup import get_logger

# Create module logger
logger = get_logger("stock_alerts")

class StockAlerts(commands.Cog):
    """Discord cog for monitoring stock prices and sending alerts"""

    def __init__(self, bot):
        self.bot = bot
        self.alerts = {}  # {channel_id: [alert_configs]}
        self.test_tasks = {}  # {channel_id: task}
        logger.info("Initializing StockAlerts cog")
        self.load_alerts()
        self.check_price_alerts.start()
        logger.info("Started price alert checker")

    def cog_unload(self):
        logger.info("Unloading StockAlerts cog")
        self.check_price_alerts.cancel()
        self.save_alerts()
        # Cancel any running test tasks
        for task in self.test_tasks.values():
            if not task.done():
                logger.debug("Cancelling running test task")
                task.cancel()

    def load_alerts(self):
        """Load saved alerts from file"""
        logger.debug("Loading alerts from file")
        try:
            if os.path.exists("stock_alerts.json"):
                with open("stock_alerts.json", "r") as f:
                    data = json.load(f)
                    # Convert string keys back to integers for channel IDs
                    self.alerts = {int(k): v for k, v in data.items()}
                    alert_count = sum(len(alerts) for alerts in self.alerts.values())
                    logger.info(f"Loaded {alert_count} price alerts")
            else:
                logger.info("No alerts file found, starting with empty alerts")
        except Exception as e:
            logger.error(f"Error loading stock alerts: {str(e)}")
            self.alerts = {}

    def save_alerts(self):
        """Save alerts to file"""
        logger.debug("Saving alerts to file")
        try:
            with open("stock_alerts.json", "w") as f:
                json.dump(self.alerts, f)
                alert_count = sum(len(alerts) for alerts in self.alerts.values())
                logger.info(f"Saved {alert_count} price alerts")
        except Exception as e:
            logger.error(f"Error saving stock alerts: {str(e)}")

    @commands.group(name="alert", invoke_without_command=True)
    async def alert(self, ctx):
        """Command group for stock price alerts"""
        logger.debug(f"Alert command invoked by {ctx.author}")
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
        logger.info(f"{ctx.author} adding {alert_type} alert for {ticker} with value {value}")
        ticker = ticker.upper()
        channel_id = ctx.channel.id

        if alert_type not in ["percent", "price"]:
            logger.warning(f"Invalid alert type: {alert_type}")
            await ctx.send("Alert type must be either 'percent' or 'price'")
            return

        # Get current price as reference
        try:
            logger.debug(f"Getting current price for {ticker}")
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
                logger.warning(f"Could not get current price for {ticker}")
                await ctx.send(f"Could not get current price for {ticker}")
                return

            current_price = price_data["price"]
            logger.debug(f"Current price for {ticker}: ${current_price}")

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
            logger.info(f"Alert added for {ticker} in channel {channel_id}")

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
            logger.error(f"Error adding alert for {ticker}: {str(e)}")
            await ctx.send(f"Error adding alert: {str(e)}")

    @alert.command(name="remove")
    async def remove_alert(self, ctx, index: int = None):
        """Remove a stock price alert by index

        Example:
        !alert remove 2    - Removes alert at index 2
        !alert remove      - Lists alerts with indexes
        """
        logger.debug(f"{ctx.author} attempting to remove alert {index}")
        channel_id = ctx.channel.id

        if channel_id not in self.alerts or not self.alerts[channel_id]:
            logger.debug(f"No alerts found for channel {channel_id}")
            await ctx.send("No alerts set for this channel")
            return

        if index is None:
            # List alerts with indices for removal
            logger.debug(f"Listing alerts with indices for channel {channel_id}")
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
            logger.info(f"Removed alert #{index} for {removed['ticker']} in channel {channel_id}")
            await ctx.send(f"Removed alert for {removed['ticker']}")
        else:
            logger.warning(f"Invalid alert index {index} for channel {channel_id}")
            await ctx.send(f"Invalid index. Use `!alert remove` to see valid indices")

    @alert.command(name="list")
    async def list_alerts(self, ctx):
        """List all stock price alerts for this channel"""
        logger.debug(f"{ctx.author} listing alerts")
        channel_id = ctx.channel.id

        if channel_id not in self.alerts or not self.alerts[channel_id]:
            logger.debug(f"No alerts found for channel {channel_id}")
            await ctx.send("No alerts set for this channel")
            return

        logger.debug(f"Displaying {len(self.alerts[channel_id])} alerts for channel {channel_id}")
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
        logger.info(f"{ctx.author} starting alert system test")
        channel_id = ctx.channel.id

        # Check if a test is already running in this channel
        if channel_id in self.test_tasks and not self.test_tasks[channel_id].done():
            logger.warning(f"Test already running in channel {channel_id}")
            await ctx.send(
                "❌ A test is already running in this channel. Use `!end test` to stop it."
            )
            return

        await ctx.send(
            "✅ Starting alert system test. Will send a message every second. Type `!end test` to stop."
        )

        # Start the test task
        self.test_tasks[channel_id] = asyncio.create_task(self._run_test(ctx))
        logger.info(f"Test task started for channel {channel_id}")

    @commands.command(name="end")
    async def end_test(self, ctx, command_type: str):
        """End a running test"""
        if command_type.lower() != "test":
            return

        logger.info(f"{ctx.author} ending alert system test")
        channel_id = ctx.channel.id

        if channel_id in self.test_tasks and not self.test_tasks[channel_id].done():
            self.test_tasks[channel_id].cancel()
            logger.info(f"Test task cancelled for channel {channel_id}")
            await ctx.send("✅ Alert system test stopped.")
        else:
            logger.debug(f"No test running in channel {channel_id}")
            await ctx.send("❌ No test is currently running in this channel.")

    async def _run_test(self, ctx):
        """Run the alert test, sending a message every second"""
        counter = 1
        channel_id = ctx.channel.id
        logger.debug(f"Starting test message loop for channel {channel_id}")
        try:
            while True:
                embed = discord.Embed(
                    title="🔔 Alert System Test",
                    description=f"This is test message #{counter}",
                    color=discord.Color.gold(),
                )
                embed.set_footer(text="Type !end test to stop this test")

                await ctx.send(embed=embed)
                logger.debug(f"Sent test message #{counter} to channel {channel_id}")
                counter += 1
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            # Task was cancelled by end_test command
            logger.debug(f"Test task was cancelled for channel {channel_id}")
            pass
        except Exception as e:
            logger.error(f"Error in test task for channel {channel_id}: {str(e)}")
            await ctx.send(f"❌ Test stopped due to error: {str(e)}")

    @commands.command(name="watchlist")
    async def show_watchlist(self, ctx):
        """Show configured stocks to monitor from config.py"""
        logger.debug(f"{ctx.author} viewing watchlist")
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
            logger.debug(f"Added {ticker} to watchlist display")

        await ctx.send(embed=embed)
        logger.debug("Watchlist displayed")

    @tasks.loop(seconds=CHECK_INTERVAL)
    async def check_price_alerts(self):
        """Check current prices against alerts periodically based on config"""
        logger.debug("Running periodic price alert check")
        if not self.alerts:
            logger.debug("No alerts to check")
            return

        for channel_id, alert_list in list(self.alerts.items()):
            logger.debug(f"Checking alerts for channel {channel_id}")
            channel = self.bot.get_channel(channel_id)
            if not channel:
                # Channel was deleted or bot no longer has access
                logger.warning(f"Channel {channel_id} not found, removing its alerts")
                del self.alerts[channel_id]
                continue

            triggered_indices = []

            for i, alert in enumerate(alert_list):
                ticker = alert["ticker"]
                alert_type = alert["type"]
                value = alert["value"]
                ref_price = alert["reference_price"]
                logger.debug(f"Checking alert #{i} for {ticker}")

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
                        logger.warning(f"Could not get current price for {ticker}")
                        continue

                    current_price = price_data["price"]
                    logger.debug(f"Current price for {ticker}: ${current_price}")

                    # Check if alert conditions are met
                    if alert_type == "percent":
                        percent_change = ((current_price - ref_price) / ref_price) * 100
                        logger.debug(f"{ticker} percent change: {percent_change:.2f}% (target: {value}%)")
                        if percent_change >= value:
                            # Alert triggered
                            logger.info(f"Percent alert triggered for {ticker}: {percent_change:.2f}% (target: {value}%)")
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
                        target_condition = (value > ref_price and current_price >= value) or (
                            value < ref_price and current_price <= value
                        )
                        logger.debug(f"{ticker} current price: ${current_price} (target: ${value})")
                        if target_condition:
                            # Alert triggered
                            direction = "increased to" if value > ref_price else "decreased to"
                            logger.info(f"Price alert triggered for {ticker}: {direction} ${current_price:.2f} (target: ${value:.2f})")
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
                    logger.error(f"Error checking alert for {ticker}: {str(e)}")

            # Remove triggered alerts (in reverse order to maintain indices)
            if triggered_indices:
                logger.info(f"Removing {len(triggered_indices)} triggered alerts from channel {channel_id}")
                for index in sorted(triggered_indices, reverse=True):
                    ticker = alert_list[index]["ticker"]
                    logger.debug(f"Removing triggered alert #{index} for {ticker}")
                    alert_list.pop(index)

            # If no alerts left for this channel, remove entry
            if not alert_list:
                logger.debug(f"No alerts left for channel {channel_id}, removing entry")
                del self.alerts[channel_id]

        # Save changes
        if triggered_indices:
            self.save_alerts()

    async def check_config_stocks(self):
        """Check configured stocks from config.py against thresholds"""
        logger.debug("Checking configured stocks from config")
        from config import STOCKS

        # Get default alert channel from config
        channel = self.bot.get_channel(ALERT_CHANNEL_ID)
        if not channel:
            logger.warning(f"Alert channel {ALERT_CHANNEL_ID} not found")
            return

        for ticker, thresholds in STOCKS.items():
            logger.debug(f"Checking config stock {ticker}")
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
                    logger.warning(f"Could not get current price for config stock {ticker}")
                    continue

                current_price = price_data["price"]
                low_threshold = thresholds["low"]
                high_threshold = thresholds["high"]
                logger.debug(f"{ticker} price: ${current_price}, thresholds: ${low_threshold}-${high_threshold}")

                # Check if price is outside thresholds
                if current_price <= low_threshold:
                    logger.info(f"{ticker} below threshold alert: ${current_price} <= ${low_threshold}")
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
                    logger.info(f"{ticker} above threshold alert: ${current_price} >= ${high_threshold}")
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
                logger.error(f"Error checking config stock {ticker}: {str(e)}")

    @check_price_alerts.before_loop
    async def before_check_price_alerts(self):
        """Wait until the bot is ready before starting the alert loop"""
        logger.debug("Waiting for bot to be ready before starting alert loop")
        await self.bot.wait_until_ready()
        logger.debug("Bot is ready, checking config stocks")
        # Also check config stocks whenever the task runs
        self.bot.loop.create_task(self.check_config_stocks())


async def setup(bot):
    """Add the StockAlerts cog to the bot"""
    logger.info("Setting up StockAlerts cog")
    await bot.add_cog(StockAlerts(bot))
    logger.info("StockAlerts cog setup complete")