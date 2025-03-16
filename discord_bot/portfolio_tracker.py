from discord.ext import commands, tasks
import asyncio
from datetime import datetime
from typing import Dict, List, Any, Optional
from loguru import logger

# Import our async API
from api.prices import AsyncPricesAPI

# Import our utility functions
from utils.embed_utilities import create_portfolio_embed

# Import configuration
from config import PORTFOLIO, PORTFOLIO_UPDATE_INTERVAL, PORTFOLIO_CHANNEL_ID


class PortfolioTracker(commands.Cog):
    """Discord cog for tracking stock portfolio value"""

    def __init__(self, bot):
        self.bot = bot
        self.portfolio = PORTFOLIO
        self.last_portfolio_value = None
        self.portfolio_data_cache = None
        self.last_update_time = None
        self.track_portfolio.start()
        logger.info("Portfolio tracker initialized")

    def cog_unload(self):
        """Clean up when the cog is unloaded"""
        self.track_portfolio.cancel()
        logger.info("Portfolio tracker stopped")

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
            logger.warning(f"Portfolio channel {PORTFOLIO_CHANNEL_ID} not found")

    @track_portfolio.before_loop
    async def before_track_portfolio(self):
        """Wait until the bot is ready before starting the portfolio tracking"""
        await self.bot.wait_until_ready()

    async def _send_portfolio_update(self, channel):
        """Send portfolio update to the specified channel"""
        try:
            # Get portfolio data
            portfolio_data = await self._get_portfolio_data()
            if not portfolio_data:
                await channel.send("❌ Could not retrieve current portfolio data")
                return

            # Calculate total values
            total_current_value = sum(item["current_value"] for item in portfolio_data)
            
            # Track value change since last update
            value_change = 0
            value_change_percent = 0
            change_data = None

            if self.last_portfolio_value is not None:
                value_change = total_current_value - self.last_portfolio_value
                value_change_percent = (
                    (value_change / self.last_portfolio_value) * 100
                    if self.last_portfolio_value
                    else 0
                )
                
                # Create change data for the embed utility
                if value_change != 0:
                    sign = "+" if value_change >= 0 else ""
                    change_data = {
                        "value_change": value_change,
                        "value_change_percent": value_change_percent,
                        "formatted_change": f"{sign}${value_change:.2f} ({sign}{value_change_percent:.2f}%)"
                    }
            
            # Update the last portfolio value
            self.last_portfolio_value = total_current_value
            self.last_update_time = datetime.now()
            
            # Generate description with timestamp
            description = f"Last updated: {self.last_update_time.strftime('%Y-%m-%d %H:%M:%S')}"
            
            # Create embed using our utility function
            embed = create_portfolio_embed(
                portfolio_data=portfolio_data,
                title="Portfolio Update",
                description=description,
                show_positions=True
            )
            
            # Add change since last update if available
            if change_data:
                embed.add_field(
                    name="Change Since Last Update",
                    value=change_data["formatted_change"],
                    inline=False
                )

            # Send the embed
            await channel.send(embed=embed)
            logger.info(f"Portfolio update sent to channel {channel.id}")

        except Exception as e:
            logger.error(f"Error updating portfolio: {str(e)}")
            await channel.send(f"❌ Error updating portfolio: {str(e)}")

    async def _get_portfolio_data(self, use_cache: bool = False, max_cache_age: int = 60) -> List[Dict[str, Any]]:
        """
        Get current data for all portfolio positions
        
        Args:
            use_cache: Whether to use cached data if available
            max_cache_age: Maximum age of cache in seconds
            
        Returns:
            List of portfolio position data dictionaries
        """
        # Check if we can use cached data
        if use_cache and self.portfolio_data_cache and self.last_update_time:
            cache_age = (datetime.now() - self.last_update_time).total_seconds()
            if cache_age <= max_cache_age:
                logger.debug(f"Using cached portfolio data ({cache_age:.1f}s old)")
                return self.portfolio_data_cache
        
        portfolio_data = []
        tasks = []

        # Create async tasks for all price lookups
        for ticker, position in self.portfolio.items():
            task = self._get_position_data(ticker, position)
            tasks.append(task)
        
        # Wait for all tasks to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Error fetching position data: {str(result)}")
            elif result:  # Only add non-None results
                portfolio_data.append(result)
        
        # Update cache
        self.portfolio_data_cache = portfolio_data
        
        return portfolio_data
    
    async def _get_position_data(self, ticker: str, position: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Get data for a single portfolio position
        
        Args:
            ticker: Stock ticker symbol
            position: Position data from portfolio config
            
        Returns:
            Position data dictionary or None if data couldn't be retrieved
        """
        try:
            shares = position["shares"]
            entry_price = position["entry_price"]
            initial_value = shares * entry_price

            # Get current price using our async API
            price_api = AsyncPricesAPI(
                ticker=ticker,
                interval="day",
                interval_multiplier=1,
                start_date=datetime.now().strftime("%Y-%m-%d"),
                end_date=datetime.now().strftime("%Y-%m-%d"),
                limit=1
            )
            
            price_data = await price_api.get_live_price()

            if not price_data or "price" not in price_data:
                logger.warning(f"Could not get current price for {ticker}")
                return None

            current_price = float(price_data["price"])
            current_value = shares * current_price
            gain_loss = current_value - initial_value
            gain_loss_percent = (gain_loss / initial_value) * 100 if initial_value else 0

            # Return structured position data
            return {
                "ticker": ticker,
                "shares": shares,
                "entry_price": entry_price,
                "current_price": current_price,
                "initial_value": initial_value,
                "current_value": current_value,
                "gain_loss": gain_loss,
                "gain_loss_percent": gain_loss_percent,
            }

        except Exception as e:
            logger.error(f"Error getting data for {ticker}: {str(e)}")
            return None

    def get_portfolio_summary(self) -> Optional[Dict[str, Any]]:
        """
        Get a summary of the portfolio (for use by other cogs)
        
        Returns:
            Dictionary with portfolio summary data or None if no data available
        """
        if not self.portfolio_data_cache:
            return None
        
        total_current_value = sum(item["current_value"] for item in self.portfolio_data_cache)
        total_initial_value = sum(item["initial_value"] for item in self.portfolio_data_cache)
        total_gain_loss = total_current_value - total_initial_value
        total_gain_loss_percent = (
            (total_gain_loss / total_initial_value) * 100
            if total_initial_value
            else 0
        )
        
        return {
            "total_value": total_current_value,
            "initial_value": total_initial_value,
            "gain_loss": total_gain_loss,
            "gain_loss_percent": total_gain_loss_percent,
            "last_update": self.last_update_time,
            "portfolio_data": self.portfolio_data_cache,
        }


async def setup(bot):
    """Add the PortfolioTracker cog to the bot"""
    portfolio_tracker = PortfolioTracker(bot)
    await bot.add_cog(portfolio_tracker)
    return portfolio_tracker  # Return the instance for other cogs to access