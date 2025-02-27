import discord
from discord.ext import commands, tasks
import asyncio
from datetime import datetime
from api import PricesAPI
from config import PORTFOLIO, PORTFOLIO_UPDATE_INTERVAL, PORTFOLIO_CHANNEL_ID


class PortfolioTracker(commands.Cog):
    """Discord cog for tracking stock portfolio value"""

    def __init__(self, bot):
        self.bot = bot
        self.portfolio = PORTFOLIO
        self.last_portfolio_value = None
        self.track_portfolio.start()

    def cog_unload(self):
        self.track_portfolio.cancel()

    @commands.command(name="portfolio")
    async def show_portfolio(self, ctx):
        """Show current portfolio status"""
        await self._send_portfolio_update(ctx.channel)

    @tasks.loop(seconds=PORTFOLIO_UPDATE_INTERVAL)
    async def track_portfolio(self):
        """Track portfolio value at regular intervals"""
        channel = self.bot.get_channel(PORTFOLIO_CHANNEL_ID)
        if channel:
            await self._send_portfolio_update(channel)
        else:
            print(f"Warning: Portfolio channel {PORTFOLIO_CHANNEL_ID} not found")

    @track_portfolio.before_loop
    async def before_track_portfolio(self):
        """Wait until the bot is ready before starting the portfolio tracking"""
        await self.bot.wait_until_ready()

    async def _send_portfolio_update(self, channel):
        """Send portfolio update to the specified channel"""
        try:
            portfolio_data = await self._get_portfolio_data()

            if not portfolio_data:
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

            self.last_portfolio_value = total_current_value

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
            for item in portfolio_data:
                ticker = item["ticker"]
                current_price = item["current_price"]
                shares = item["shares"]
                entry_price = item["entry_price"]
                gain_loss = item["gain_loss"]
                gain_loss_percent = item["gain_loss_percent"]

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

        except Exception as e:
            await channel.send(f"❌ Error updating portfolio: {str(e)}")

    async def _get_portfolio_data(self):
        """Get current data for all portfolio positions"""
        portfolio_data = []

        for ticker, position in self.portfolio.items():
            try:
                shares = position["shares"]
                entry_price = position["entry_price"]
                initial_value = shares * entry_price

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
                    print(f"Could not get current price for {ticker}")
                    continue

                current_price = price_data["price"]
                current_value = shares * current_price
                gain_loss = current_value - initial_value
                gain_loss_percent = (
                    (gain_loss / initial_value) * 100 if initial_value else 0
                )

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
                print(f"Error getting data for {ticker}: {e}")

        return portfolio_data


async def setup(bot):
    """Add the PortfolioTracker cog to the bot and return it for use by other cogs"""
    cog = PortfolioTracker(bot)
    await bot.add_cog(cog)
    return cog
