"""
Discord commands for managing stock price alerts.
Handles user interactions for creating, viewing, and removing alerts.
"""

import discord
from discord.ext import commands
import asyncio
from datetime import datetime
from typing import Optional, Dict, List, Any
from loguru import logger

from api.prices import AsyncPricesAPI
from .alert_model import PriceAlert
from .alert_storage import AlertStorage
from utils.embed_utilities import create_alert_embed


class AlertCommands:
    """Command handlers for stock price alerts"""
    
    def __init__(self, storage: AlertStorage):
        """
        Initialize alert commands.
        
        Args:
            storage: Alert storage instance
        """
        self.storage = storage
        logger.debug("Initialized AlertCommands")
    
    async def add_alert(self, ctx: commands.Context, ticker: str, alert_type: str, value: float) -> None:
        """Add a new price alert"""
        logger.info(f"{ctx.author} adding {alert_type} alert for {ticker} with value {value}")
        ticker = ticker.upper()
        channel_id = ctx.channel.id
        
        if alert_type not in ["percent", "price"]:
            await ctx.send("Alert type must be either 'percent' or 'price'")
            return
        
        # Get current price as reference
        try:
            logger.debug(f"Getting current price for {ticker}")
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
                await ctx.send(f"Could not get current price for {ticker}")
                return
                
            current_price = float(price_data["price"])
            logger.debug(f"Current price for {ticker}: ${current_price}")
            
            # Create alert object
            alert = PriceAlert(
                ticker=ticker,
                alert_type=alert_type,
                value=value,
                reference_price=current_price,
                created_at=datetime.now(),
                channel_id=channel_id
            )
            
            # Add to storage
            self.storage.add_alert(alert)
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
    
    async def remove_alert(self, ctx: commands.Context, index: Optional[int] = None) -> None:
        """Remove a stock price alert by index"""
        logger.debug(f"{ctx.author} attempting to remove alert {index}")
        channel_id = ctx.channel.id
        
        alerts = self.storage.get_channel_alerts(channel_id)
        if not alerts:
            logger.debug(f"No alerts found for channel {channel_id}")
            await ctx.send("No alerts set for this channel")
            return
            
        if index is None:
            # List alerts with indices for removal
            logger.debug(f"Listing alerts with indices for channel {channel_id}")
            embed = discord.Embed(
                title="Stock Price Alerts",
                description="Use `!alert remove INDEX` to remove an alert",
                color=discord.Color.blue(),
            )
            
            for i, alert in enumerate(alerts):
                ticker = alert.ticker
                if alert.alert_type == "percent":
                    description = f"{ticker}: +{alert.value}% from ${alert.reference_price:.2f}"
                else:  # price
                    description = f"{ticker}: reaches ${alert.value:.2f}"
                    
                embed.add_field(name=f"Alert #{i}", value=description, inline=False)
                
            await ctx.send(embed=embed)
            return
            
        # Remove the alert at the specified index
        removed = self.storage.remove_alert(channel_id, index)
        if removed:
            logger.info(f"Removed alert #{index} for {removed.ticker} in channel {channel_id}")
            await ctx.send(f"Removed alert for {removed.ticker}")
        else:
            logger.warning(f"Invalid alert index {index} for channel {channel_id}")
            await ctx.send(f"Invalid index. Use `!alert remove` to see valid indices")
    
    async def list_alerts(self, ctx: commands.Context) -> None:
        """List all stock price alerts for this channel"""
        logger.debug(f"{ctx.author} listing alerts")
        channel_id = ctx.channel.id
        
        alerts = self.storage.get_channel_alerts(channel_id)
        if not alerts:
            logger.debug(f"No alerts found for channel {channel_id}")
            await ctx.send("No alerts set for this channel")
            return
            
        logger.debug(f"Displaying {len(alerts)} alerts for channel {channel_id}")
        embed = discord.Embed(
            title="Active Stock Price Alerts", color=discord.Color.blue()
        )
        
        for i, alert in enumerate(alerts):
            ticker = alert.ticker
            alert_type = alert.alert_type
            value = alert.value
            ref_price = alert.reference_price
            
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