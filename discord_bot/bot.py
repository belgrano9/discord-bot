"""
Main Discord bot application.
Initializes and runs the bot with all modules.
"""

import os
import discord
from discord.ext import commands
from logging_setup import get_logger
from dotenv import load_dotenv
from cog import setup as setup_simple_cog

load_dotenv()

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
        logger.info("Trading cog loaded!")
    except Exception as e:
        logger.error(f"Error loading trading cog: {e}")
    


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