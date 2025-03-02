import os
import discord
from discord.ext import commands

# Import the setup functions
from stock_commands import setup as setup_stock_commands
from stock_alerts import setup as setup_stock_alerts
from portfolio_tracker import setup as setup_portfolio_tracker
from scheduled_reports import ScheduledReports
from trading_commands import setup as setup_trading_commands

# Setup bot with intents
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    """Called when bot is ready and connected to Discord"""
    print(f"Bot is connected! Logged in as {bot.user}")
    print(f"Bot is in {len(bot.guilds)} servers")
    for guild in bot.guilds:
        print(f"- {guild.name} (id: {guild.id})")
        for channel in guild.text_channels:
            print(f"  - #{channel.name} (id: {channel.id})")

    # Load the cogs
    await setup_stock_commands(bot)
    print("Stock commands loaded!")

    await setup_stock_alerts(bot)
    print("Stock alerts loaded!")

    # Load portfolio tracker first
    portfolio_tracker_cog = await setup_portfolio_tracker(bot)
    print("Portfolio tracker loaded!")

    # Then initialize scheduled reports with access to portfolio tracker
    scheduled_reports = ScheduledReports(bot, portfolio_tracker_cog)
    await bot.add_cog(scheduled_reports)  # Fixed: added 'await' here
    print("Scheduled reports loaded!")

    # Load the new trading commands cog
    await setup_trading_commands(bot)
    print("Trading commands loaded!")


@bot.command(name="ping")
async def ping_command(ctx):
    """Simple ping command to test if bot is responsive"""
    await ctx.send("Pong! Bot is working!")


if __name__ == "__main__":
    # Make sure your token is set correctly
    DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
    if not DISCORD_TOKEN:
        print("ERROR: DISCORD_TOKEN environment variable not set!")
        exit(1)

    bot.run(DISCORD_TOKEN)
