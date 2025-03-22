"""
Functionality for checking stocks defined in configuration.
Handles monitoring configured stocks against defined thresholds.
"""

import discord
from discord.ext import commands
import asyncio
from datetime import datetime
from typing import Dict, Any, List, Optional
from loguru import logger

from api.prices import AsyncPricesAPI
from utils.embed_utilities import create_alert_embed


class ConfigChecker:
    """Check configured stocks against thresholds"""
    
    def __init__(self, bot: discord.ext.commands.Bot, alert_channel_id: int, stocks_config: Dict[str, Dict[str, float]]):
        """
        Initialize the config checker.
        
        Args:
            bot: Discord bot instance
            alert_channel_id: Channel ID for alert notifications
            stocks_config: Dictionary of stocks and their thresholds
        """
        self.bot = bot
        self.alert_channel_id = alert_channel_id
        self.stocks_config = stocks_config
        logger.info(f"Initialized ConfigChecker with {len(stocks_config)} stocks")
    
    async def check_stocks(self) -> None:
        """Check configured stocks from config.py against thresholds"""
        logger.debug("Checking configured stocks from config")
        
        # Get default alert channel from config
        channel = self.bot.get_channel(self.alert_channel_id)
        if not channel:
            logger.warning(f"Alert channel {self.alert_channel_id} not found")
            return
            
        for ticker, thresholds in self.stocks_config.items():
            logger.debug(f"Checking config stock {ticker}")
            try:
                # Get current price
                price_api = AsyncPricesAPI(
                    ticker=ticker,
                    interval="day",
                    interval_multiplier=1,
                    start_date=datetime.now().strftime("%Y-%m-%d"),
                    end_date=datetime.now().strftime("%Y-%m-%d"),
                    limit=1,
                )
                price_data = await price_api.get_live_price()
                
                if not price_data or "price" not in price_data:
                    logger.warning(f"Could not get current price for config stock {ticker}")
                    continue
                    
                current_price = float(price_data["price"])
                low_threshold = thresholds["low"]
                high_threshold = thresholds["high"]
                logger.debug(f"{ticker} price: ${current_price}, thresholds: ${low_threshold}-${high_threshold}")
                
                # Check if price is outside thresholds
                if current_price <= low_threshold:
                    await self._send_threshold_alert(
                        channel, ticker, current_price, low_threshold, "below"
                    )
                
                elif current_price >= high_threshold:
                    await self._send_threshold_alert(
                        channel, ticker, current_price, high_threshold, "above"
                    )
                    
            except Exception as e:
                logger.error(f"Error checking config stock {ticker}: {str(e)}")
    
    async def _send_threshold_alert(
        self, 
        channel: discord.TextChannel,
        ticker: str,
        current_price: float,
        threshold: float,
        direction: str
    ) -> None:
        """Send threshold alert notification"""
        try:
            if direction == "below":
                logger.info(f"{ticker} below threshold alert: ${current_price} <= ${threshold}")
                embed = discord.Embed(
                    title=f"📉 {ticker} Below Threshold Alert",
                    description=f"{ticker} has fallen below the configured threshold",
                    color=discord.Color.red(),
                )
            else:  # above
                logger.info(f"{ticker} above threshold alert: ${current_price} >= ${threshold}")
                embed = discord.Embed(
                    title=f"📈 {ticker} Above Threshold Alert",
                    description=f"{ticker} has risen above the configured threshold",
                    color=discord.Color.green(),
                )
                
            embed.add_field(
                name="Current Price", value=f"${current_price:.2f}", inline=True
            )
            embed.add_field(
                name="Threshold", value=f"${threshold:.2f}", inline=True
            )
            
            await channel.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error sending threshold alert: {str(e)}")