import discord
from discord.ext import commands, tasks
import asyncio
from datetime import datetime
from api import PricesAPI
from config import PORTFOLIO, PORTFOLIO_UPDATE_INTERVAL, PORTFOLIO_CHANNEL_ID
from logging_setup import get_logger

# Create module logger
logger = get_logger("portfolio_tracker")

class PortfolioTracker(commands.Cog):
    """Discord cog for tracking stock portfolio value"""

    def __init__(self, bot):
        self.bot = bot
        self.portfolio = PORTFOLIO
        self.last_portfolio_value = None
        logger.info("Initializing PortfolioTracker cog")
        logger.debug(f"Portfolio update interval: {PORTFOLIO_UPDATE_INTERVAL} seconds")
        logger.debug(f"Portfolio channel ID: {PORTFOLIO_CHANNEL_ID}")
        self.track_portfolio.start()
        logger.info("Started portfolio tracking task")

    def cog_unload(self):
        logger.info("Unloading PortfolioTracker cog")
        self.track_portfolio.cancel()

    @commands.command(name="portfolio")
    async def show_portfolio(self, ctx):
        """Show current portfolio status"""
        logger.info(f"{ctx.author} requested portfolio status")
        await self._send_portfolio_update(ctx.channel)

    @tasks.loop(seconds=PORTFOLIO_UPDATE_INTERVAL)
    async def track_portfolio(self):
        """Track portfolio value at regular intervals"""
        logger.debug("Running scheduled portfolio update")
        channel = self.bot.get_channel(PORTFOLIO_CHANNEL_ID)
        if channel:
            logger.debug(f"Sending portfolio update to channel {PORTFOLIO_CHANNEL_ID}")
            await self._send_portfolio_update(channel)
        else:
            logger.warning(f"Portfolio channel {PORTFOLIO_CHANNEL_ID} not found")

    @track_portfolio.before_loop
    async def before_track_portfolio(self):
        """Wait until the bot is ready before starting the portfolio tracking"""
        logger.debug("Waiting for bot to be ready before starting portfolio tracking")
        await self.bot.wait_until_ready()
        logger.debug("Bot is ready, portfolio tracking can start")

    async def _send_portfolio_update(self, channel):
        """Send portfolio update to the specified channel"""
        try:
            logger.debug("Getting portfolio data")
            portfolio_data = await self._get_portfolio_data()

            if not portfolio_data:
                logger.warning("Could not retrieve current portfolio data")
                await channel.send("❌ Could not retrieve current portfolio data")
                return

            # Calculate total values
            total_current_value = sum(item["current_value"] for item in portfolio_data)
            total_initial_value = sum(item["initial_value"] for item in portfolio_data)
            total_gain_loss = total_current_value - total_initial_value
            total_gain_loss_percent = (
                (total_gain_loss / total_initial_value) * 100
                if total_initial_value
                else 0
            )

            logger.debug(f"Portfolio summary - Current: ${total_current_value:.2f}, Initial: ${total_initial_value:.2f}")
            logger.debug(f"Gain/Loss: ${total_gain_loss:.2f} ({total_gain_loss_percent:.2f}%)")

            # Track value change since last update
            value_change = 0
            value_change_percent = 0

            if self.last_portfolio_value is not None:
                value_change = total_current_value - self.last_portfolio_value
                value_change_percent = (
                    (value_change / self.last_portfolio_value) * 100
                    if self.last_portfolio_value
                    else 0
                )
                logger.debug(f"Change since last update: ${value_change:.2f} ({value_change_percent:.2f}%)")

            self.last_portfolio_value = total_current_value
            logger.debug(f"Updated last portfolio value to ${total_current_value:.2f}")

            # Create embed for portfolio summary
            color = (
                discord.Color.green() if total_gain_loss >= 0 else discord.Color.red()
            )
            embed = discord.Embed(
                title="Portfolio Update",
                description=f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                color=color,
            )

            # Add portfolio summary
            embed.add_field(
                name="Total Value", value=f"${total_current_value:.2f}", inline=True
            )
            embed.add_field(
                name="Initial Investment",
                value=f"${total_initial_value:.2f}",
                inline=True,
            )
            embed.add_field(
                name="Total Gain/Loss",
                value=f"${total_gain_loss:.2f} ({total_gain_loss_percent:.2f}%)",
                inline=True,
            )

            # Add change since last update if available
            if value_change != 0:
                sign = "+" if value_change >= 0 else ""
                embed.add_field(
                    name="Change Since Last Update",
                    value=f"{sign}${value_change:.2f} ({sign}{value_change_percent:.2f}%)",
                    inline=False,
                )

            # Add individual positions
            logger.debug(f"Adding {len(portfolio_data)} positions to embed")
            for item in portfolio_data:
                ticker = item["ticker"]
                current_price = item["current_price"]
                shares = item["shares"]
                entry_price = item["entry_price"]
                gain_loss = item["gain_loss"]
                gain_loss_percent = item["gain_loss_percent"]

                logger.debug(f"Position: {ticker} - ${current_price:.2f} × {shares} = ${item['current_value']:.2f}")
                logger.debug(f"Entry: ${entry_price:.2f}, P/L: ${gain_loss:.2f} ({gain_loss_percent:.2f}%)")

                sign = "+" if gain_loss >= 0 else ""
                position_value = (
                    f"${current_price:.2f} × {shares} = ${item['current_value']:.2f}\n"
                )
                position_value += f"Entry: ${entry_price:.2f}\n"
                position_value += (
                    f"P/L: {sign}${gain_loss:.2f} ({sign}{gain_loss_percent:.2f}%)"
                )

                embed.add_field(name=ticker, value=position_value, inline=True)

            await channel.send(embed=embed)
            logger.info("Sent portfolio update to channel")

        except Exception as e:
            logger.error(f"Error updating portfolio: {str(e)}")
            await channel.send(f"❌ Error updating portfolio: {str(e)}")

    async def _get_portfolio_data(self):
        """Get current data for all portfolio positions"""
        logger.debug("Getting current data for all portfolio positions")
        portfolio_data = []

        for ticker, position in self.portfolio.items():
            try:
                shares = position["shares"]
                entry_price = position["entry_price"]
                initial_value = shares * entry_price
                logger.debug(f"Processing position: {ticker} - {shares} shares at ${entry_price}")

                # Get current price
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
                    continue

                current_price = price_data["price"]
                current_value = shares * current_price
                gain_loss = current_value - initial_value
                gain_loss_percent = (
                    (gain_loss / initial_value) * 100 if initial_value else 0
                )

                logger.debug(f"{ticker} current price: ${current_price}")
                logger.debug(f"Current value: ${current_value:.2f}, Initial: ${initial_value:.2f}")
                logger.debug(f"Gain/Loss: ${gain_loss:.2f} ({gain_loss_percent:.2f}%)")

                portfolio_data.append(
                    {
                        "ticker": ticker,
                        "shares": shares,
                        "entry_price": entry_price,
                        "current_price": current_price,
                        "initial_value": initial_value,
                        "current_value": current_value,
                        "gain_loss": gain_loss,
                        "gain_loss_percent": gain_loss_percent,
                    }
                )

            except Exception as e:
                logger.error(f"Error getting data for {ticker}: {str(e)}")

        logger.debug(f"Portfolio data collected for {len(portfolio_data)} positions")
        return portfolio_data


async def setup(bot):
    """Add the PortfolioTracker cog to the bot"""
    logger.info("Setting up PortfolioTracker cog")
    cog = PortfolioTracker(bot)
    await bot.add_cog(cog)
    logger.info("PortfolioTracker cog setup complete")
    return cog