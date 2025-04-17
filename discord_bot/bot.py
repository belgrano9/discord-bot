"""
Main Discord bot application.
Initializes and runs the bot with all modules.
"""

import os
import discord
from discord.ext import commands
from logging_setup import get_logger

# Import modularized setups
from alerts import setup as setup_stock_alerts
from price_tracker import setup as setup_price_tracker
from stocks import setup as setup_stock_commands
from portfolio import setup as setup_portfolio_tracker
from reports import setup as setup_scheduled_reports
from trading import setup as setup_trading_commands
from trade_inspector import setup as setup_trade_inspector
from dotenv import load_dotenv
from trading.simple_cog import setup as setup_simple_cog

# Load variables from .env file into environment variables
load_dotenv()

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

    # Load the cogs in a specific order
    logger.debug("Loading cogs...")
     
    try:
        await setup_simple_cog(bot)
        logger.info("Simple cog loaded!")
    except Exception as e:
        logger.error(f"Error loading simple cog: {e}")

    
    """
    # 1. Load stock commands (no dependencies)
    try:
        await setup_stock_commands(bot)
        logger.info("Stock commands loaded!")
    except Exception as e:
        logger.error(f"Error loading stock commands: {e}")

    # 2. Load alerts (no dependencies)
    try:
        await setup_stock_alerts(bot)
        logger.info("Stock alerts loaded!")
    except Exception as e:
        logger.error(f"Error loading stock alerts: {e}")

    # 3. Load portfolio tracker (no dependencies)
    try:
        portfolio_tracker_cog = await setup_portfolio_tracker(bot)
        logger.info("Portfolio tracker loaded!")
    except Exception as e:
        logger.error(f"Error loading portfolio tracker: {e}")
        portfolio_tracker_cog = None

    # 4. Load price tracker (no dependencies)
    try:
        await setup_price_tracker(bot)
        logger.info("Price tracker loaded!")
    except Exception as e:
        logger.error(f"Error loading price tracker: {e}")

    # 5. Load scheduled reports (depends on portfolio tracker)
    try:
        if portfolio_tracker_cog:
            await setup_scheduled_reports(bot)
            logger.info("Scheduled reports loaded!")
        else:
            logger.error("Cannot load scheduled reports: portfolio tracker is None")
    except Exception as e:
        logger.error(f"Error loading scheduled reports: {e}")

    # 6. Load trading commands (no dependencies)
    try:
        await setup_trading_commands(bot)
        logger.info("Trading commands loaded!")
    except Exception as e:
        logger.error(f"Error loading trading commands: {e}")

    # 7. Load trading inspector (no dependencies)
    try:
        await setup_trade_inspector(bot)
        logger.info("Trade inspector loaded!")
    except Exception as e:
        logger.error(f"Error loading Trade inspector: {e}")
    """
    


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