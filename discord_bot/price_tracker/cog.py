"""
Price Tracker cog for Discord bot.
Provides commands to track cryptocurrency prices in real-time.
"""

import discord
from discord.ext import commands, tasks
import asyncio
from datetime import datetime
from typing import Optional, Dict, Any, List
import polars as pl
from loguru import logger

# Import our tracker manager
from .tracker_manager import TrackerManager

# Import utility functions
from discord_bot.utils.embed_utilities import create_price_embed, create_alert_embed


class PriceTracker(commands.Cog):
    """Discord cog for tracking cryptocurrency prices in real-time"""

    def __init__(self, bot):
        self.bot = bot
        # Initialize the tracker manager
        self.tracker_manager = TrackerManager(bot)
        self.track_interval = 1  # Check for updates every second
        # Start the update task
        self.price_tracker.start()
        logger.info("PriceTracker cog initialized")

    def cog_unload(self):
        """Clean up when the cog is unloaded"""
        self.price_tracker.cancel()
        logger.info("PriceTracker cog unloaded")

    @commands.command(name="track")
    async def track_price(self, ctx, symbol: str = "BTC-USDT", interval: int = 60):
        """
        Start tracking a cryptocurrency price with regular updates
        
        Parameters:
        symbol: Trading pair to track (default: BTC-USDT)
        interval: Update interval in seconds (default: 60)
        
        Example: !track ETH-USDT 30
        """
        
        symbol = symbol.upper()
        
        # Start with a processing message
        message = await ctx.send(f"⏳ Starting price tracker for {symbol}...")
        
        try:
            # Start tracking with the tracker manager
            success = await self.tracker_manager.start_tracking(
                symbol=symbol,
                channel_id=ctx.channel.id,
                message_id=message.id,
                interval=interval
            )
            
            if not success:
                await message.edit(content=f"❌ Could not retrieve price data for {symbol}")
                return
            
            # Get the initial data for display
            tracking_info = self.tracker_manager.get_tracking_info(symbol)
            ticker_data = tracking_info["price_data"]
            
            # Create and update the embed
            embed = self._create_price_embed(symbol, ticker_data, tracking_info)
            await message.edit(content=None, embed=embed)
            
            # Add control reactions
            await message.add_reaction("⏹️")  # Stop tracking
            await message.add_reaction("📊")  # Show chart/detailed view
            
            logger.info(f"Started tracking {symbol} with {interval}s interval")
            
        except Exception as e:
            await message.edit(content=f"❌ Error starting price tracker: {str(e)}")
            logger.error(f"Error tracking {symbol}: {str(e)}")
    
    @commands.command(name="untrack")
    async def untrack_price(self, ctx, symbol: str = "BTC-USDT"):
        """Stop tracking a specific symbol price"""
        symbol = symbol.upper()
        
        # Get tracking info before stopping
        tracking_info = self.tracker_manager.get_tracking_info(symbol)
        
        if tracking_info:
            # Try to update the message if possible
            try:
                channel_id = tracking_info["channel_id"]
                message_id = tracking_info["message_id"]
                
                channel = self.bot.get_channel(channel_id)
                if channel:
                    message = await channel.fetch_message(message_id)
                    await message.edit(content=f"🛑 Price tracking for {symbol} has been stopped")
                    await message.clear_reactions()
            except:
                pass
            
            # Stop tracking
            self.tracker_manager.stop_tracking(symbol)
            await ctx.send(f"✅ Stopped tracking {symbol}")
            logger.info(f"Stopped tracking {symbol}")
        else:
            await ctx.send(f"❌ Not currently tracking {symbol}")
    
    @commands.command(name="tracking")
    async def list_tracking(self, ctx):
        """Show all currently tracked symbols"""
        tracked_symbols = self.tracker_manager.get_tracked_symbols()
        
        if not tracked_symbols:
            await ctx.send("No symbols are currently being tracked")
            return
        
        # Create fields for the embed
        fields = []
        for symbol in tracked_symbols:
            # Get price statistics for this symbol
            stats = self.tracker_manager.get_price_statistics(symbol)
            
            if not stats:
                continue
                
            current_price = stats["current_price"]
            changes = stats["changes"]
            tracking_info = stats["tracking_info"]
            
            # Format elapsed time
            elapsed = tracking_info["elapsed"]
            time_str = f"{elapsed['hours']}h {elapsed['minutes']}m {elapsed['seconds']}s"
            
            # Create field value
            value = (
                f"Current: ${current_price:.2f}\n"
                f"Change: {'+' if changes['change_since_start'] >= 0 else ''}{changes['change_since_start']:.2f}%\n"
                f"Interval: {tracking_info['interval']}s\n"
                f"Running for: {time_str}"
            )
            
            fields.append((symbol, value, True))
        
        # Create the embed using utility
        embed = create_alert_embed(
            title="Currently Tracked Symbols",
            description="List of all price trackers currently active",
            fields=fields,
            color=discord.Color.blue()
        )
        
        await ctx.send(embed=embed)
    
    def _create_price_embed(self, symbol: str, ticker_data: Dict[str, Any], tracking_info: Dict[str, Any]) -> discord.Embed:
        """
        Create a Discord embed with price information.
        
        Args:
            symbol: Trading pair symbol
            ticker_data: Current ticker data
            tracking_info: Tracking information
            
        Returns:
            Formatted Discord embed
        """
        # Extract price and get stats
        current_price = float(ticker_data["price"])
        stats = self.tracker_manager.get_price_statistics(symbol)
        
        # Prepare price data for the embed utility
        price_data = {
            "price": current_price,
            "bestBid": ticker_data.get("bestBid"),
            "bestAsk": ticker_data.get("bestAsk")
        }
        
        # Add custom fields for our specific needs
        fields = []
        
        # Add change fields if available
        if stats and "changes" in stats:
            changes = stats["changes"]
            fields.append(("1m Change", f"{'+' if changes['change_1m'] >= 0 else ''}{changes['change_1m']:.2f}%", True))
            fields.append(("5m Change", f"{'+' if changes['change_5m'] >= 0 else ''}{changes['change_5m']:.2f}%", True))
            
            if changes["change_since_start"] != 0:
                fields.append(("Since Start", f"{'+' if changes['change_since_start'] >= 0 else ''}{changes['change_since_start']:.2f}%", True))
        
        # Format the symbol name for title
        base_currency, quote_currency = symbol.split("-")
        
        # Add footer with update interval
        interval = tracking_info["interval"]
        footer_text = f"Updates every {interval} seconds • React with ⏹️ to stop tracking"
        
        # Create the embed
        embed = create_price_embed(
            symbol=symbol,
            price_data=price_data,
            title_prefix=f"{base_currency}/{quote_currency} Price Tracker",
            show_additional_fields=True,
            color_based_on_change=True,
            footer_text=footer_text
        )
        
        # Add our custom fields
        for name, value, inline in fields:
            embed.add_field(name=name, value=value, inline=inline)
        
        return embed
    
    @tasks.loop(seconds=1)
    async def price_tracker(self):
        """Task to update tracked prices at their configured intervals"""
        try:
            # Use the tracker manager to update all tracked prices
            await self.tracker_manager.update_all_tracked_prices()
        except Exception as e:
            logger.error(f"Error in price tracker task: {str(e)}")
    
    @price_tracker.before_loop
    async def before_price_tracker(self):
        """Wait until the bot is ready before starting the price tracker"""
        await self.bot.wait_until_ready()
    
    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        """Handle reactions on price tracking messages"""
        # Ignore bot's own reactions
        if user.bot:
            return
        
        message = reaction.message
        
        # Get all tracked symbols
        tracked_symbols = self.tracker_manager.get_tracked_symbols()
        
        # Find which symbol this message is tracking
        tracked_symbol = None
        for symbol in tracked_symbols:
            info = self.tracker_manager.get_tracking_info(symbol)
            if info and info["message_id"] == message.id:
                tracked_symbol = symbol
                break
        
        if not tracked_symbol:
            return
        
        # Handle stop tracking reaction
        if str(reaction.emoji) == "⏹️":
            # Mark as stopped in the message
            embed = message.embeds[0] if message.embeds else None
            if embed:
                embed.title = f"{embed.title} (Stopped)"
                embed.color = discord.Color.light_grey()
                embed.set_footer(text="Tracking stopped")
                await message.edit(embed=embed)
            else:
                await message.edit(content=f"🛑 Price tracking for {tracked_symbol} has been stopped")
            
            # Remove from tracked prices
            self.tracker_manager.stop_tracking(tracked_symbol)
            await message.clear_reactions()
            logger.info(f"User {user.name} stopped tracking {tracked_symbol}")
        
        # Handle chart/details reaction
        elif str(reaction.emoji) == "📊":
            # Get the price statistics
            stats = self.tracker_manager.get_price_statistics(tracked_symbol)
            
            if not stats:
                return
            
            # Create fields for the detailed view
            fields = []
            
            # Add statistics fields
            if "stats" in stats:
                stat_data = stats["stats"]
                fields.append(("Current", f"${stats['current_price']:.2f}", True))
                fields.append(("High", f"${stat_data['high']:.2f}", True))
                fields.append(("Low", f"${stat_data['low']:.2f}", True))
                fields.append(("Average", f"${stat_data['avg']:.2f}", True))
                fields.append(("Range", f"${stat_data['range']:.2f}", True))
                
                # Add percentage from high/low
                current = stats['current_price']
                high = stat_data['high']
                low = stat_data['low']
                
                if high > 0 and low > 0:
                    pct_from_high = ((current - high) / high) * 100
                    pct_from_low = ((current - low) / low) * 100
                    fields.append(("From High/Low", f"{pct_from_high:.2f}% / {pct_from_low:.2f}%", True))
                
                # Add volatility info
                if "movements" in stats:
                    movements = stats["movements"]
                    fields.append((
                        "Price Movements", 
                        f"Up: {movements['up']} | Down: {movements['down']} | Sideways: {movements['sideways']}", 
                        True
                    ))
                
                if stat_data["volatility"] > 0:
                    fields.append(("Volatility", f"{stat_data['volatility']:.2f}", True))
            
            # Add tracking information
            if "tracking_info" in stats:
                tracking_info = stats["tracking_info"]
                
                tracking_details = (
                    f"Started: {tracking_info['started_at'].strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"Running: {tracking_info['elapsed']['hours']}h {tracking_info['elapsed']['minutes']}m {tracking_info['elapsed']['seconds']}s\n"
                    f"Interval: {tracking_info['interval']}s\n"
                    f"Data points: {tracking_info['data_points']}"
                )
                
                fields.append(("Tracking Info", tracking_details, False))
            
            # Add recent price history if available
            if "history" in self.tracker_manager.get_tracking_info(tracked_symbol):
                history = self.tracker_manager.get_tracking_info(tracked_symbol)["history"]
                
                if len(history) > 1:
                    # Get the most recent prices (last 10)
                    recent_history = history[-10:]
                    interval = self.tracker_manager.get_tracking_info(tracked_symbol)["interval"]
                    
                    history_str = ""
                    for i, price in enumerate(recent_history):
                        time_ago = (len(recent_history) - i - 1) * interval
                        minutes, seconds = divmod(time_ago, 60)
                        time_str = f"{minutes}m {seconds}s ago" if minutes > 0 else f"{seconds}s ago"
                        change = ""
                        
                        if i > 0:
                            pct_change = ((price - recent_history[i-1]) / recent_history[i-1]) * 100
                            change = f" ({'+' if pct_change >= 0 else ''}{pct_change:.2f}%)"
                        
                        history_str += f"• {time_str}: ${price:.2f}{change}\n"
                    
                    fields.append(("Recent Price History", history_str, False))
            
            # Create the detailed embed
            detailed_embed = create_alert_embed(
                title=f"{tracked_symbol} Detailed Price View",
                description="Historical price analysis and statistics",
                fields=fields,
                color=discord.Color.blue(),
                timestamp=True
            )
            
            # Send as a new message
            await message.channel.send(embed=detailed_embed)
            
            # Remove the user's reaction
            await message.remove_reaction("📊", user)


async def setup(bot):
    """Add the PriceTracker cog to the bot"""
    await bot.add_cog(PriceTracker(bot))
