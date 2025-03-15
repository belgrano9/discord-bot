import os
import discord
from discord.ext import commands
from logging_setup import get_logger

# Import the setup functions
from stock_commands import setup as setup_stock_commands
from stock_alerts import setup as setup_stock_alerts
from portfolio_tracker import setup as setup_portfolio_tracker
from scheduled_reports import ScheduledReports
from trading_commands import setup as setup_trading_commands

# Create module logger
logger = get_logger("bot")

# Setup bot with intents
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    """Called when bot is ready and connected to Discord"""
    logger.info(f"Bot is connected! Logged in as {bot.user}")
    logger.info(f"Bot is in {len(bot.guilds)} servers")
    for guild in bot.guilds:
        logger.info(f"- {guild.name} (id: {guild.id})")
        for channel in guild.text_channels:
            logger.debug(f"  - #{channel.name} (id: {channel.id})")

    # Load the cogs
    logger.debug("Loading cogs...")
    
    try:
        await setup_stock_commands(bot)
        logger.info("Stock commands loaded!")
    except Exception as e:
        logger.error(f"Error loading stock commands: {e}")

    try:
        await setup_stock_alerts(bot)
        logger.info("Stock alerts loaded!")
    except Exception as e:
        logger.error(f"Error loading stock alerts: {e}")

    # Load portfolio tracker first
    try:
        portfolio_tracker_cog = await setup_portfolio_tracker(bot)
        logger.info("Portfolio tracker loaded!")
    except Exception as e:
        logger.error(f"Error loading portfolio tracker: {e}")
        portfolio_tracker_cog = None

    # Then initialize scheduled reports with access to portfolio tracker
    try:
        if portfolio_tracker_cog:
            logger.debug("Initializing scheduled reports cog")
            scheduled_reports = ScheduledReports(bot, portfolio_tracker_cog)
            await bot.add_cog(scheduled_reports)
            logger.info("Scheduled reports loaded!")
        else:
            logger.error("Cannot load scheduled reports: portfolio tracker is None")
    except Exception as e:
        logger.error(f"Error loading scheduled reports: {e}")

    # Load the new trading commands cog
    try:
        await setup_trading_commands(bot)
        logger.info("Trading commands loaded!")
    except Exception as e:
        logger.error(f"Error loading trading commands: {e}")


@bot.command(name="ping")
async def ping_command(ctx):
    """Simple ping command to test if bot is responsive"""
    logger.debug(f"Ping command received from {ctx.author}")
    await ctx.send("Pong! Bot is working!")
    logger.debug("Ping command response sent")


if __name__ == "__main__":
    # Make sure your token is set correctly
    DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
    if not DISCORD_TOKEN:
        logger.critical("ERROR: DISCORD_TOKEN environment variable not set!")
        exit(1)

    logger.info("Starting bot...")
    try:
        bot.run(DISCORD_TOKEN)
    except Exception as e:
        logger.critical(f"Failed to start bot: {e}")