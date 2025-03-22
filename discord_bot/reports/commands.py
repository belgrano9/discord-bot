"""
Command handlers for report commands.
Processes user commands for report configuration.
"""

import discord
from discord.ext import commands
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, time
from loguru import logger

from .models import ChannelReportConfig, ReportConfig, WeeklyReportConfig
from .storage import ReportStorage
from .report_generator import ReportGenerator


class ReportCommands:
    """Command handlers for report commands"""
    
    def __init__(self, storage: ReportStorage, generator: ReportGenerator):
        """
        Initialize report commands.
        
        Args:
            storage: Report storage manager
            generator: Report generator
        """
        self.storage = storage
        self.generator = generator
        logger.debug("Initialized ReportCommands")
    
    async def setup_reports(
        self, 
        ctx: commands.Context, 
        report_type: str = "both", 
        time_str: Optional[str] = None, 
        day: Optional[str] = None
    ) -> None:
        """
        Set up scheduled reports.
        
        Args:
            ctx: Discord context
            report_type: Type of reports to set up ("both", "daily", or "weekly")
            time_str: Time in HH:MM format
            day: Day of week for weekly reports
        """
        channel_id = ctx.channel.id
        
        # Get existing config or create new one
        config = self.storage.get_channel_config(channel_id)
        if not config:
            # Create new default config
            config = ChannelReportConfig(channel_id=channel_id)
            
        # Process time if provided
        hour = 22  # Default to 10 PM
        minute = 0
        
        if time_str:
            try:
                hour, minute = map(int, time_str.split(":"))
                if not (0 <= hour < 24 and 0 <= minute < 60):
                    logger.warning(f"Invalid time format: {time_str}")
                    await ctx.send("❌ Invalid time format. Use HH:MM (24-hour format)")
                    return
            except Exception:
                logger.warning(f"Invalid time format: {time_str}")
                await ctx.send("❌ Invalid time format. Use HH:MM (24-hour format)")
                return
                
        # Process day if provided
        day_map = {
            "monday": 0,
            "tuesday": 1,
            "wednesday": 2,
            "thursday": 3,
            "friday": 4,
            "saturday": 5,
            "sunday": 6,
        }
        
        weekday = 4  # Default to Friday
        
        if day:
            day = day.lower()
            if day in day_map:
                weekday = day_map[day]
            else:
                logger.warning(f"Invalid day: {day}")
                await ctx.send("❌ Invalid day. Choose from Monday-Sunday")
                return
                
        # Update config based on report type
        if report_type in ["both", "daily"]:
            config.daily.enabled = True
            config.daily.hour = hour
            config.daily.minute = minute
            
        if report_type in ["both", "weekly"]:
            config.weekly.enabled = True
            config.weekly.hour = hour
            config.weekly.minute = minute
            config.weekly.day = weekday
            
        # Save updated config
        self.storage.set_channel_config(config)
        
        # Confirmation message
        confirmation = f"✅ Scheduled reports configured for this channel:\n"
        if report_type in ["both", "daily"]:
            confirmation += f"• Daily report at {hour:02d}:{minute:02d}\n"
        if report_type in ["both", "weekly"]:
            day_name = list(day_map.keys())[
                list(day_map.values()).index(weekday)
            ].capitalize()
            confirmation += f"• Weekly report on {day_name} at {hour:02d}:{minute:02d}"
            
        await ctx.send(confirmation)
        logger.info(f"Reports setup completed for channel {channel_id}")
    
    async def report_status(self, ctx: commands.Context) -> None:
        """
        Show report status for the current channel.
        
        Args:
            ctx: Discord context
        """
        channel_id = ctx.channel.id
        
        config = self.storage.get_channel_config(channel_id)
        if not config:
            logger.debug(f"No reports configured for channel {channel_id}")
            await ctx.send("❌ No reports are configured for this channel")
            return
            
        # Create embed with report status
        embed = discord.Embed(
            title="Scheduled Report Status",
            description="Current configuration for this channel",
            color=discord.Color.blue(),
        )
        
        # Daily report status
        daily = config.daily
        daily_status = "✅ Enabled" if daily.enabled else "❌ Disabled"
        daily_time = daily.format_time()
        
        embed.add_field(
            name="Daily Report",
            value=f"Status: {daily_status}\nTime: {daily_time}",
            inline=True,
        )
        
        # Weekly report status
        weekly = config.weekly
        weekly_status = "✅ Enabled" if weekly.enabled else "❌ Disabled"
        weekly_time = weekly.format_time()
        
        day_map = {
            0: "Monday",
            1: "Tuesday",
            2: "Wednesday",
            3: "Thursday",
            4: "Friday",
            5: "Saturday",
            6: "Sunday",
        }
        weekly_day = day_map.get(weekly.day, "Unknown")
        
        embed.add_field(
            name="Weekly Report",
            value=f"Status: {weekly_status}\nDay: {weekly_day}\nTime: {weekly_time}",
            inline=True,
        )
        
        # Add last report times if available
        if self.generator.tracker.last_daily:
            embed.add_field(
                name="Last Daily Report",
                value=self.generator.tracker.last_daily.strftime("%Y-%m-%d %H:%M:%S"),
                inline=False,
            )
            
        if self.generator.tracker.last_weekly:
            embed.add_field(
                name="Last Weekly Report",
                value=self.generator.tracker.last_weekly.strftime("%Y-%m-%d %H:%M:%S"),
                inline=False,
            )
            
        await ctx.send(embed=embed)
        logger.info(f"Sent report status for channel {channel_id}")
    
    async def toggle_report(
        self, 
        ctx: commands.Context, 
        report_type: str, 
        enable: str = "toggle"
    ) -> None:
        """
        Toggle a report type on or off.
        
        Args:
            ctx: Discord context
            report_type: Type of report to toggle ("daily" or "weekly")
            enable: Whether to enable, disable, or toggle ("on", "off", or "toggle")
        """
        channel_id = ctx.channel.id
        
        config = self.storage.get_channel_config(channel_id)
        if not config:
            logger.warning(f"Reports not configured for channel {channel_id}")
            await ctx.send("❌ Reports not configured. Use `!report setup` first.")
            return
            
        # Determine which report type to toggle
        if report_type == "daily":
            current = config.daily.enabled
            
            if enable.lower() in ["toggle", "t"]:
                config.daily.enabled = not current
            elif enable.lower() in ["on", "enable", "true", "yes", "y"]:
                config.daily.enabled = True
            elif enable.lower() in ["off", "disable", "false", "no", "n"]:
                config.daily.enabled = False
            else:
                await ctx.send("❌ Invalid option. Use 'on', 'off', or 'toggle'")
                return
                
            new_status = config.daily.enabled
                
        elif report_type == "weekly":
            current = config.weekly.enabled
            
            if enable.lower() in ["toggle", "t"]:
                config.weekly.enabled = not current
            elif enable.lower() in ["on", "enable", "true", "yes", "y"]:
                config.weekly.enabled = True