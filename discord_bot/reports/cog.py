"""
Discord cog for scheduled portfolio reports.
Provides commands and scheduling for portfolio reports.
"""

import discord
from discord.ext import commands, tasks
import asyncio
from datetime import datetime
from typing import Optional
from loguru import logger

from .storage import ReportStorage
from .scheduler import ReportScheduler
from .report_generator import ReportGenerator
from .commands import ReportCommands


class ScheduledReports(commands.Cog):
    """Discord cog for scheduled portfolio performance reports"""

    def __init__(self, bot, portfolio_tracker):
        """
        Initialize the scheduled reports cog.
        
        Args:
            bot: Discord bot instance
            portfolio_tracker: Portfolio tracker instance
        """
        self.bot = bot
        self.portfolio_tracker = portfolio_tracker
        
        # Initialize components
        self.storage = ReportStorage()
        self.storage.load()
        
        self.scheduler = ReportScheduler()
        self.generator = ReportGenerator(portfolio_tracker)
        self.commands = ReportCommands(self.storage, self.generator)
        
        # Start scheduled tasks
        self.daily_report_task.start()
        self.weekly_report_task.start()
        
        logger.info("Scheduled reports cog initialized")

    def cog_unload(self):
        """Clean up when the cog is unloaded"""
        logger.info("Unloading ScheduledReports cog")
        self.daily_report_task.cancel()
        self.weekly_report_task.cancel()
        self.storage.save()

    @commands.group(name="report", invoke_without_command=True)
    async def report(self, ctx):
        """Command group for scheduled portfolio reports"""
        logger.debug(f"{ctx.author} used report command without subcommand")
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
        await self.commands.setup_reports(ctx, report_type, time, day)


    @report.command(name="status")
    async def report_status(self, ctx):
        """Check the status of scheduled reports for this channel"""
        await self.commands.report_status(ctx)

    @report.command(name="daily")
    async def toggle_daily(self, ctx, enable="toggle"):
        """Enable or disable daily reports

        Examples:
        !report daily on     - Enable daily reports
        !report daily off    - Disable daily reports
        !report daily        - Toggle daily reports
        """
        await self.commands.toggle_report(ctx, "daily", enable)

    @report.command(name="weekly")
    async def toggle_weekly(self, ctx, enable="toggle"):
        """Enable or disable weekly reports

        Examples:
        !report weekly on    - Enable weekly reports
        !report weekly off   - Disable weekly reports
        !report weekly       - Toggle weekly reports
        """
        await self.commands.toggle_report(ctx, "weekly", enable)

    @report.command(name="now")
    async def generate_report_now(self, ctx, report_type="daily"):
        """Generate a portfolio report immediately

        Examples:
        !report now         - Generate a daily report
        !report now daily   - Generate a daily report
        !report now weekly  - Generate a weekly report
        """
        await self.commands.generate_report_now(ctx, report_type)

    @tasks.loop(minutes=60)
    async def daily_report_task(self):
        """Task to send daily reports at configured times"""
        now = datetime.now()
        logger.debug(f"Checking daily report task at {now.strftime('%Y-%m-%d %H:%M:%S')}")

        # First store today's data for historical comparisons
        await self.generator.store_daily_data()

        # Check which channels should receive reports
        channels_to_run = self.scheduler.check_daily_reports(self.storage.get_all_configs())
        
        # Send reports to those channels
        for channel_id in channels_to_run:
            channel = self.bot.get_channel(channel_id)
            if channel:
                logger.info(f"Sending scheduled daily report to channel {channel.name}")
                await self.generator.generate_daily_report(channel)
            else:
                logger.warning(f"Could not find channel {channel_id}")

    @tasks.loop(minutes=60)
    async def weekly_report_task(self):
        """Task to send weekly reports at configured times"""
        now = datetime.now()
        logger.debug(f"Checking weekly report task at {now.strftime('%Y-%m-%d %H:%M:%S')}")

        # Check which channels should receive reports
        channels_to_run = self.scheduler.check_weekly_reports(self.storage.get_all_configs())
        
        # Send reports to those channels
        for channel_id in channels_to_run:
            channel = self.bot.get_channel(channel_id)
            if channel:
                logger.info(f"Sending scheduled weekly report to channel {channel.name}")
                await self.generator.generate_weekly_report(channel)
            else:
                logger.warning(f"Could not find channel {channel_id}")

    @daily_report_task.before_loop
    @weekly_report_task.before_loop
    async def before_report_tasks(self):
        """Wait until the bot is ready before starting report tasks"""
        logger.debug("Waiting for bot to be ready before starting report tasks")
        await self.bot.wait_until_ready()
        logger.debug("Bot is ready, report tasks can start")


async def setup(bot):
    """Add the ScheduledReports cog to the bot"""
    # We need to get the portfolio tracker instance
    portfolio_tracker = bot.get_cog("PortfolioTracker")
    if not portfolio_tracker:
        logger.error("Cannot setup ScheduledReports: PortfolioTracker cog not found")
        return None
        
    scheduled_reports = ScheduledReports(bot, portfolio_tracker)
    await bot.add_cog(scheduled_reports)
    return scheduled_reports