import discord
from discord.ext import commands, tasks
import asyncio
from datetime import datetime, time, timedelta
import json
import os
from typing import Dict, List, Optional
from api import PricesAPI

# Default configuration
DEFAULT_DAILY_REPORT_TIME = time(hour=22, minute=0)  # 10:00 PM
DEFAULT_WEEKLY_REPORT_DAY = 4  # Friday (0 = Monday, 4 = Friday)
DEFAULT_ENABLE_REPORTS = True


class ScheduledReports(commands.Cog):
    """Discord cog for scheduled portfolio performance reports"""

    def __init__(self, bot, portfolio_tracker):
        self.bot = bot
        self.portfolio_tracker = portfolio_tracker
        self.reports_config = {}
        self.load_config()
        self.daily_report_task.start()
        self.weekly_report_task.start()
        self.historical_data = {}  # Store historical portfolio values for comparison
        self.last_daily_report = None
        self.last_weekly_report = None

    def cog_unload(self):
        self.daily_report_task.cancel()
        self.weekly_report_task.cancel()
        self.save_config()

    def load_config(self):
        """Load report configuration from file"""
        try:
            if os.path.exists("reports_config.json"):
                with open("reports_config.json", "r") as f:
                    self.reports_config = json.load(f)
                print(
                    f"Loaded reports configuration for {len(self.reports_config)} channels"
                )
        except Exception as e:
            print(f"Error loading reports configuration: {e}")
            self.reports_config = {}

    def save_config(self):
        """Save reports configuration to file"""
        try:
            with open("reports_config.json", "w") as f:
                json.dump(self.reports_config, f)
        except Exception as e:
            print(f"Error saving reports configuration: {e}")

    @commands.group(name="report", invoke_without_command=True)
    async def report(self, ctx):
        """Command group for scheduled portfolio reports"""
        await ctx.send(
            "Use `!report setup`, `!report status`, `!report daily`, `!report weekly`, or `!report disable` to manage scheduled reports"
        )

    @report.command(name="setup")
    async def setup_reports(self, ctx, report_type="both", time=None, day=None):
        """Set up scheduled portfolio reports

        Examples:
        !report setup both 17:00      - Setup both daily and weekly reports at 5:00 PM
        !report setup daily 09:30     - Setup daily reports at 9:30 AM
        !report setup weekly 17:00 Friday - Setup weekly reports at 5:00 PM on Fridays
        """
        channel_id = str(ctx.channel.id)

        if channel_id not in self.reports_config:
            self.reports_config[channel_id] = {
                "daily": {
                    "enabled": False,
                    "hour": DEFAULT_DAILY_REPORT_TIME.hour,
                    "minute": DEFAULT_DAILY_REPORT_TIME.minute,
                },
                "weekly": {
                    "enabled": False,
                    "hour": DEFAULT_DAILY_REPORT_TIME.hour,
                    "minute": DEFAULT_DAILY_REPORT_TIME.minute,
                    "day": DEFAULT_WEEKLY_REPORT_DAY,
                },
            }

        # Process time if provided
        if time:
            try:
                hour, minute = map(int, time.split(":"))
                if not (0 <= hour < 24 and 0 <= minute < 60):
                    await ctx.send("❌ Invalid time format. Use HH:MM (24-hour format)")
                    return
            except:
                await ctx.send("❌ Invalid time format. Use HH:MM (24-hour format)")
                return
        else:
            hour = DEFAULT_DAILY_REPORT_TIME.hour
            minute = DEFAULT_DAILY_REPORT_TIME.minute

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
        if day:
            day = day.lower()
            if day in day_map:
                weekday = day_map[day]
            else:
                await ctx.send("❌ Invalid day. Choose from Monday-Sunday")
                return
        else:
            weekday = DEFAULT_WEEKLY_REPORT_DAY

        # Update config based on report type
        if report_type in ["both", "daily"]:
            self.reports_config[channel_id]["daily"]["enabled"] = True
            self.reports_config[channel_id]["daily"]["hour"] = hour
            self.reports_config[channel_id]["daily"]["minute"] = minute

        if report_type in ["both", "weekly"]:
            self.reports_config[channel_id]["weekly"]["enabled"] = True
            self.reports_config[channel_id]["weekly"]["hour"] = hour
            self.reports_config[channel_id]["weekly"]["minute"] = minute
            self.reports_config[channel_id]["weekly"]["day"] = weekday

        self.save_config()

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

    @report.command(name="status")
    async def report_status(self, ctx):
        """Check the status of scheduled reports for this channel"""
        channel_id = str(ctx.channel.id)

        if channel_id not in self.reports_config:
            await ctx.send("❌ No reports are configured for this channel")
            return

        config = self.reports_config[channel_id]

        # Create embed with report status
        embed = discord.Embed(
            title="Scheduled Report Status",
            description="Current configuration for this channel",
            color=discord.Color.blue(),
        )

        # Daily report status
        daily = config["daily"]
        daily_status = "✅ Enabled" if daily["enabled"] else "❌ Disabled"
        daily_time = f"{daily['hour']:02d}:{daily['minute']:02d}"
        embed.add_field(
            name="Daily Report",
            value=f"Status: {daily_status}\nTime: {daily_time}",
            inline=True,
        )

        # Weekly report status
        weekly = config["weekly"]
        weekly_status = "✅ Enabled" if weekly["enabled"] else "❌ Disabled"
        weekly_time = f"{weekly['hour']:02d}:{weekly['minute']:02d}"
        day_map = {
            0: "Monday",
            1: "Tuesday",
            2: "Wednesday",
            3: "Thursday",
            4: "Friday",
            5: "Saturday",
            6: "Sunday",
        }
        weekly_day = day_map.get(weekly["day"], "Unknown")
        embed.add_field(
            name="Weekly Report",
            value=f"Status: {weekly_status}\nDay: {weekly_day}\nTime: {weekly_time}",
            inline=True,
        )

        # Last report times
        if self.last_daily_report:
            embed.add_field(
                name="Last Daily Report",
                value=self.last_daily_report.strftime("%Y-%m-%d %H:%M:%S"),
                inline=False,
            )

        if self.last_weekly_report:
            embed.add_field(
                name="Last Weekly Report",
                value=self.last_weekly_report.strftime("%Y-%m-%d %H:%M:%S"),
                inline=False,
            )

        await ctx.send(embed=embed)

    @report.command(name="daily")
    async def toggle_daily(self, ctx, enable="toggle"):
        """Enable or disable daily reports

        Examples:
        !report daily on     - Enable daily reports
        !report daily off    - Disable daily reports
        !report daily        - Toggle daily reports
        """
        channel_id = str(ctx.channel.id)

        if channel_id not in self.reports_config:
            await ctx.send("❌ Reports not configured. Use `!report setup` first.")
            return

        current = self.reports_config[channel_id]["daily"]["enabled"]

        if enable.lower() in ["toggle", "t"]:
            self.reports_config[channel_id]["daily"]["enabled"] = not current
        elif enable.lower() in ["on", "enable", "true", "yes", "y"]:
            self.reports_config[channel_id]["daily"]["enabled"] = True
        elif enable.lower() in ["off", "disable", "false", "no", "n"]:
            self.reports_config[channel_id]["daily"]["enabled"] = False
        else:
            await ctx.send("❌ Invalid option. Use 'on', 'off', or 'toggle'")
            return

        self.save_config()
        status = (
            "enabled"
            if self.reports_config[channel_id]["daily"]["enabled"]
            else "disabled"
        )
        await ctx.send(f"✅ Daily reports {status} for this channel")

    @report.command(name="weekly")
    async def toggle_weekly(self, ctx, enable="toggle"):
        """Enable or disable weekly reports

        Examples:
        !report weekly on    - Enable weekly reports
        !report weekly off   - Disable weekly reports
        !report weekly       - Toggle weekly reports
        """
        channel_id = str(ctx.channel.id)

        if channel_id not in self.reports_config:
            await ctx.send("❌ Reports not configured. Use `!report setup` first.")
            return

        current = self.reports_config[channel_id]["weekly"]["enabled"]

        if enable.lower() in ["toggle", "t"]:
            self.reports_config[channel_id]["weekly"]["enabled"] = not current
        elif enable.lower() in ["on", "enable", "true", "yes", "y"]:
            self.reports_config[channel_id]["weekly"]["enabled"] = True
        elif enable.lower() in ["off", "disable", "false", "no", "n"]:
            self.reports_config[channel_id]["weekly"]["enabled"] = False
        else:
            await ctx.send("❌ Invalid option. Use 'on', 'off', or 'toggle'")
            return

        self.save_config()
        status = (
            "enabled"
            if self.reports_config[channel_id]["weekly"]["enabled"]
            else "disabled"
        )
        await ctx.send(f"✅ Weekly reports {status} for this channel")

    @report.command(name="now")
    async def generate_report_now(self, ctx, report_type="daily"):
        """Generate a portfolio report immediately

        Examples:
        !report now         - Generate a daily report
        !report now daily   - Generate a daily report
        !report now weekly  - Generate a weekly report
        """
        if report_type.lower() == "daily":
            await self.send_daily_report(ctx.channel)
            self.last_daily_report = datetime.now()
        elif report_type.lower() == "weekly":
            await self.send_weekly_report(ctx.channel)
            self.last_weekly_report = datetime.now()
        else:
            await ctx.send("❌ Invalid report type. Use 'daily' or 'weekly'")

    async def store_historical_data(self):
        """Store today's portfolio value for historical comparison"""
        try:
            portfolio_data = await self.portfolio_tracker._get_portfolio_data()
            if not portfolio_data:
                return

            today = datetime.now().strftime("%Y-%m-%d")
            total_value = sum(item["current_value"] for item in portfolio_data)

            # Store daily value
            self.historical_data[today] = {
                "total_value": total_value,
                "portfolio_data": portfolio_data,
            }

            # Save only last 30 days of data
            keys = sorted(self.historical_data.keys())
            if len(keys) > 30:
                for old_key in keys[:-30]:
                    del self.historical_data[old_key]

        except Exception as e:
            print(f"Error storing historical data: {e}")

    @tasks.loop(minutes=60)
    async def daily_report_task(self):
        """Task to send daily reports at the configured time"""
        now = datetime.now()

        # First store today's data for historical comparisons
        await self.store_historical_data()

        # Check each channel's configuration
        for channel_id, config in self.reports_config.items():
            if not config["daily"]["enabled"]:
                continue

            scheduled_hour = config["daily"]["hour"]
            scheduled_minute = config["daily"]["minute"]

            # Check if it's time to send the report (within this hour)
            if now.hour == scheduled_hour and now.minute < 60:
                # Only send if we haven't sent a report in the last 12 hours
                if (
                    self.last_daily_report is None
                    or (now - self.last_daily_report).total_seconds() >= 12 * 3600
                ):
                    channel = self.bot.get_channel(int(channel_id))
                    if channel:
                        await self.send_daily_report(channel)
                        self.last_daily_report = now

    @tasks.loop(minutes=60)
    async def weekly_report_task(self):
        """Task to send weekly reports at the configured day and time"""
        now = datetime.now()

        # Check each channel's configuration
        for channel_id, config in self.reports_config.items():
            if not config["weekly"]["enabled"]:
                continue

            scheduled_day = config["weekly"]["day"]  # 0=Monday, 6=Sunday
            scheduled_hour = config["weekly"]["hour"]
            scheduled_minute = config["weekly"]["minute"]

            # Check if it's the right day and approximately the right time
            if (
                now.weekday() == scheduled_day
                and now.hour == scheduled_hour
                and now.minute < 60
            ):
                # Only send if we haven't sent a report in the last 24 hours
                if (
                    self.last_weekly_report is None
                    or (now - self.last_weekly_report).total_seconds() >= 24 * 3600
                ):
                    channel = self.bot.get_channel(int(channel_id))
                    if channel:
                        await self.send_weekly_report(channel)
                        self.last_weekly_report = now

    @daily_report_task.before_loop
    @weekly_report_task.before_loop
    async def before_report_tasks(self):
        """Wait until the bot is ready before starting report tasks"""
        await self.bot.wait_until_ready()

    async def send_daily_report(self, channel):
        """Send daily portfolio performance report"""
        try:
            # Get current portfolio data
            portfolio_data = await self.portfolio_tracker._get_portfolio_data()
            if not portfolio_data:
                await channel.send(
                    "❌ Could not retrieve current portfolio data for daily report"
                )
                return

            # Calculate yesterday's date
            yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
            yesterday_data = self.historical_data.get(yesterday)

            # Create report
            embed = await self._create_performance_report(
                portfolio_data, yesterday_data, "Daily Portfolio Report", "yesterday"
            )

            await channel.send(embed=embed)

        except Exception as e:
            await channel.send(f"❌ Error generating daily report: {str(e)}")

    async def send_weekly_report(self, channel):
        """Send weekly portfolio performance report"""
        try:
            # Get current portfolio data
            portfolio_data = await self.portfolio_tracker._get_portfolio_data()
            if not portfolio_data:
                await channel.send(
                    "❌ Could not retrieve current portfolio data for weekly report"
                )
                return

            # Calculate date from 7 days ago
            week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
            week_ago_data = self.historical_data.get(week_ago)

            # If we don't have exactly 7 days ago, try to find the closest date
            if not week_ago_data:
                dates = sorted(self.historical_data.keys())
                for date in dates:
                    if date < datetime.now().strftime("%Y-%m-%d"):
                        week_ago_data = self.historical_data[date]

            # Create report
            embed = await self._create_performance_report(
                portfolio_data, week_ago_data, "Weekly Portfolio Report", "last week"
            )

            await channel.send(embed=embed)

        except Exception as e:
            await channel.send(f"❌ Error generating weekly report: {str(e)}")

    async def _create_performance_report(
        self, current_data, previous_data, title, period_name
    ):
        """Create a portfolio performance report comparing current to previous period"""
        # Calculate total values
        total_current_value = sum(item["current_value"] for item in current_data)

        # Create embed with appropriate color
        embed = discord.Embed(
            title=title,
            description=f"Report generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            color=discord.Color.blue(),
        )

        # Add current portfolio summary
        embed.add_field(
            name="Current Total Value", value=f"${total_current_value:.2f}", inline=True
        )

        # Compare with previous period if available
        if previous_data:
            previous_value = previous_data["total_value"]
            value_change = total_current_value - previous_value
            value_change_percent = (
                (value_change / previous_value * 100) if previous_value else 0
            )

            sign = "+" if value_change >= 0 else ""
            embed.add_field(
                name=f"Change from {period_name}",
                value=f"{sign}${value_change:.2f} ({sign}{value_change_percent:.2f}%)",
                inline=True,
            )

            # Update embed color based on performance
            embed.color = (
                discord.Color.green() if value_change >= 0 else discord.Color.red()
            )

        # Add top performers and worst performers
        if len(current_data) > 1:
            # Sort by performance
            sorted_positions = sorted(
                current_data, key=lambda x: x["gain_loss_percent"], reverse=True
            )

            # Top performers
            top_performers = sorted_positions[: min(3, len(sorted_positions))]
            top_text = ""
            for pos in top_performers:
                sign = "+" if pos["gain_loss"] >= 0 else ""
                top_text += f"• {pos['ticker']}: {sign}{pos['gain_loss_percent']:.2f}% (${pos['current_value']:.2f})\n"

            embed.add_field(
                name="Top Performers", value=top_text or "No data", inline=False
            )

            # Worst performers
            if len(sorted_positions) > 3:
                worst_performers = sorted_positions[-3:]
                worst_text = ""
                for pos in reversed(worst_performers):
                    sign = "+" if pos["gain_loss"] >= 0 else ""
                    worst_text += f"• {pos['ticker']}: {sign}{pos['gain_loss_percent']:.2f}% (${pos['current_value']:.2f})\n"

                embed.add_field(
                    name="Underperforming Positions", value=worst_text, inline=False
                )

        # Add individual position updates
        positions_text = ""
        for item in current_data:
            ticker = item["ticker"]
            current_price = item["current_price"]
            gain_loss_percent = item["gain_loss_percent"]

            # Check if we have previous data for this position
            position_change = "N/A"
            if previous_data:
                prev_position = next(
                    (
                        p
                        for p in previous_data["portfolio_data"]
                        if p["ticker"] == ticker
                    ),
                    None,
                )
                if prev_position:
                    pos_change = current_price - prev_position["current_price"]
                    pos_change_pct = (
                        (pos_change / prev_position["current_price"] * 100)
                        if prev_position["current_price"]
                        else 0
                    )
                    sign = "+" if pos_change >= 0 else ""
                    position_change = f"{sign}{pos_change_pct:.2f}%"

            positions_text += f"• {ticker}: ${current_price:.2f} ({position_change} since {period_name})\n"

        if positions_text:
            embed.add_field(name="Position Updates", value=positions_text, inline=False)

        return embed
