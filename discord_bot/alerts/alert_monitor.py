"""
Price monitoring for stock alerts.
Handles checking current prices against alert conditions.
"""

import asyncio
from datetime import datetime
from typing import Dict, List, Any, Optional, Set, Tuple
import discord
from loguru import logger

from api.prices import AsyncPricesAPI
from .alert_model import PriceAlert
from .alert_storage import AlertStorage
from utils.embed_utilities import create_alert_embed


class AlertMonitor:
    """Monitor stock prices and trigger alerts"""
    
    def __init__(self, bot: discord.ext.commands.Bot, storage: AlertStorage, check_interval: int = 180):
        """
        Initialize the alert monitor.
        
        Args:
            bot: Discord bot instance
            storage: Alert storage instance
            check_interval: Interval in seconds between price checks
        """
        self.bot = bot
        self.storage = storage
        self.check_interval = check_interval
        logger.info(f"Initialized AlertMonitor with {check_interval}s check interval")
    
    async def check_alerts(self) -> List[Tuple[PriceAlert, float]]:
        """
        Check all alerts against current prices.
        
        Returns:
            List of (alert, current_price) tuples for triggered alerts
        """
        if not self.storage.alerts_by_channel:
            return []
            
        triggered = []
        
        # Group alerts by ticker to minimize API calls
        ticker_alerts: Dict[str, List[Tuple[int, int, PriceAlert]]] = {}
        
        for channel_id, alerts in self.storage.alerts_by_channel.items():
            for i, alert in enumerate(alerts):
                if alert.ticker not in ticker_alerts:
                    ticker_alerts[alert.ticker] = []
                ticker_alerts[alert.ticker].append((channel_id, i, alert))
        
        # Check each ticker once
        for ticker, alert_list in ticker_alerts.items():
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
                    logger.warning(f"Could not get current price for {ticker}")
                    continue
                    
                current_price = float(price_data["price"])
                logger.debug(f"Current price for {ticker}: ${current_price}")
                
                # Check each alert for this ticker
                for channel_id, index, alert in alert_list:
                    if alert.check_triggered(current_price):
                        triggered.append((alert, current_price))
                        
            except Exception as e:
                logger.error(f"Error checking alerts for {ticker}: {str(e)}")
        
        return triggered
    
    async def handle_triggered_alerts(self, triggered_alerts: List[Tuple[PriceAlert, float]]) -> None:
        """Send notifications for triggered alerts and remove them"""
        if not triggered_alerts:
            return
            
        # Group by channel for efficient removal
        triggered_by_channel: Dict[int, List[Tuple[int, PriceAlert, float]]] = {}
        
        for alert, current_price in triggered_alerts:
            # Find the index of this alert in storage
            channel_id = alert.channel_id
            if channel_id not in self.storage.alerts_by_channel:
                continue
                
            try:
                index = self.storage.alerts_by_channel[channel_id].index(alert)
                
                if channel_id not in triggered_by_channel:
                    triggered_by_channel[channel_id] = []
                    
                triggered_by_channel[channel_id].append((index, alert, current_price))
                
            except ValueError:
                logger.warning(f"Alert for {alert.ticker} not found in storage")
        
        # Handle alerts for each channel
        for channel_id, alert_data in triggered_by_channel.items():
            channel = self.bot.get_channel(channel_id)
            if not channel:
                # Channel was deleted or bot no longer has access
                logger.warning(f"Channel {channel_id} not found, removing its alerts")
                if channel_id in self.storage.alerts_by_channel:
                    del self.storage.alerts_by_channel[channel_id]
                continue
            
            # Send notification for each triggered alert
            for index, alert, current_price in alert_data:
                await self._send_alert_notification(channel, alert, current_price)
            
            # Remove all triggered alerts for this channel
            indices = [index for index, _, _ in alert_data]
            self.storage.remove_alerts(channel_id, indices)
            
        self.storage.save()
        
    async def _send_alert_notification(self, channel: discord.TextChannel, alert: PriceAlert, current_price: float) -> None:
        """Send a notification for a triggered alert"""
        ticker = alert.ticker
        reference_price = alert.reference_price
        
        try:
            if alert.alert_type == "percent":
                percent_change = ((current_price - reference_price) / reference_price) * 100
                
                embed = discord.Embed(
                    title=f"🚀 {ticker} Price Alert Triggered!",
                    description=f"{ticker} has grown by {percent_change:.2f}% (target: {alert.value}%)",
                    color=discord.Color.green(),
                )
                embed.add_field(
                    name="Reference Price",
                    value=f"${reference_price:.2f}",
                    inline=True,
                )
                embed.add_field(
                    name="Current Price",
                    value=f"${current_price:.2f}",
                    inline=True,
                )
                embed.add_field(
                    name="Gain",
                    value=f"${current_price - reference_price:.2f} (+{percent_change:.2f}%)",
                    inline=True,
                )
                
            else:  # price alert
                direction = "increased to" if alert.value > reference_price else "decreased to"
                
                embed = discord.Embed(
                    title=f"⚠️ {ticker} Price Alert Triggered!",
                    description=f"{ticker} has {direction} ${current_price:.2f} (target: ${alert.value:.2f})",
                    color=discord.Color.gold(),
                )
                embed.add_field(
                    name="Reference Price",
                    value=f"${reference_price:.2f}",
                    inline=True,
                )
                embed.add_field(
                    name="Current Price",
                    value=f"${current_price:.2f}",
                    inline=True,
                )
                
            await channel.send(embed=embed)
            logger.info(f"Sent alert notification for {ticker} to channel {channel.id}")
            
        except Exception as e:
            logger.error(f"Error sending alert notification: {str(e)}")