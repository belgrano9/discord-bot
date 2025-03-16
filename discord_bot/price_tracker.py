import discord
from discord.ext import commands, tasks
import asyncio
from datetime import datetime
from typing import Optional, Dict, Any, List
import polars as pl
from loguru import logger

# Import async API
from api.kucoin import AsyncKucoinAPI

# Import utility functions
from utils.embed_utilities import create_price_embed, create_alert_embed


class PriceTracker(commands.Cog):
    """Discord cog for tracking cryptocurrency prices in real-time"""

    def __init__(self, bot):
        self.bot = bot
        # Initialize the KuCoin API client
        self.kucoin = AsyncKucoinAPI()
        self.tracked_prices = {}  # {symbol: {price_data, last_update, message_id}}
        self.track_interval = 10  # Default update interval in seconds
        self.price_tracker.start()
        logger.info("Price tracker initialized")

    def cog_unload(self):
        """Clean up when the cog is unloaded"""
        self.price_tracker.cancel()
        logger.info("Price tracker unloaded")

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
            # Get initial price data
            ticker_data = await self.get_symbol_data(symbol)
            
            if not ticker_data:
                await message.edit(content=f"❌ Could not retrieve price data for {symbol}")
                return
            
            # Store tracking info
            self.tracked_prices[symbol] = {
                "price_data": ticker_data,
                "last_update": datetime.now(),
                "message_id": message.id,
                "channel_id": ctx.channel.id,
                "interval": interval,
                "history": [float(ticker_data["price"])],  # Store price history
                "created_at": datetime.now()
            }
            
            # Update the message with the initial data
            embed = self._create_price_embed(symbol, ticker_data)
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
        
        if symbol in self.tracked_prices:
            # Get the message info
            message_id = self.tracked_prices[symbol]["message_id"]
            channel_id = self.tracked_prices[symbol]["channel_id"]
            
            # Try to update the message if possible
            try:
                channel = self.bot.get_channel(channel_id)
                if channel:
                    message = await channel.fetch_message(message_id)
                    await message.edit(content=f"🛑 Price tracking for {symbol} has been stopped")
                    await message.clear_reactions()
            except:
                pass
            
            # Remove from tracked prices
            del self.tracked_prices[symbol]
            await ctx.send(f"✅ Stopped tracking {symbol}")
            logger.info(f"Stopped tracking {symbol}")
        else:
            await ctx.send(f"❌ Not currently tracking {symbol}")
    
    @commands.command(name="tracking")
    async def list_tracking(self, ctx):
        """Show all currently tracked symbols"""
        if not self.tracked_prices:
            await ctx.send("No symbols are currently being tracked")
            return
        
        # Create fields for the embed
        fields = []
        for symbol, data in self.tracked_prices.items():
            # Calculate time since started
            time_elapsed = datetime.now() - data["created_at"]
            hours, remainder = divmod(int(time_elapsed.total_seconds()), 3600)
            minutes, seconds = divmod(remainder, 60)
            time_str = f"{hours}h {minutes}m {seconds}s"
            
            # Get latest price and calculate change since start
            current_price = float(data["price_data"]["price"])
            start_price = data["history"][0]
            change_pct = ((current_price - start_price) / start_price) * 100 if start_price else 0
            
            value = (
                f"Current: ${current_price:.2f}\n"
                f"Change: {'+' if change_pct >= 0 else ''}{change_pct:.2f}%\n"
                f"Interval: {data['interval']}s\n"
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
    
    async def get_symbol_data(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get ticker data for a symbol asynchronously"""
        try:
            # Use our async API client
            ticker_data = await self.kucoin.get_ticker(symbol)
            
            if ticker_data and ticker_data.get("code") == "200000":
                return ticker_data.get("data", {})
            
            logger.warning(f"Failed to get ticker data for {symbol}: {ticker_data.get('msg', 'Unknown error')}")
            return None
            
        except Exception as e:
            logger.error(f"Error fetching data for {symbol}: {str(e)}")
            return None
    
    def _create_price_embed(self, symbol: str, ticker_data: Dict[str, Any]) -> discord.Embed:
        """Create a Discord embed with price information"""
        # Extract price and calculate changes if history exists
        current_price = float(ticker_data["price"])
        
        # Get price history for this symbol
        history = self.tracked_prices[symbol]["history"]
        
        # Calculate changes
        change_1m = 0
        change_5m = 0
        change_since_start = 0
        
        if len(history) > 1:
            if len(history) > 1:  # 1-minute change
                change_1m = ((current_price - history[-2]) / history[-2]) * 100
            
            if len(history) > 5:  # 5-minute change
                change_5m = ((current_price - history[-6]) / history[-6]) * 100
            
            # Change since tracking started
            change_since_start = ((current_price - history[0]) / history[0]) * 100
        
        # Prepare price data for the embed utility
        price_data = {
            "price": current_price,
            "bestBid": ticker_data.get("bestBid"),
            "bestAsk": ticker_data.get("bestAsk")
        }
        
        # Add custom fields for our specific needs
        fields = []
        
        fields.append(("1m Change", f"{'+' if change_1m >= 0 else ''}{change_1m:.2f}%", True))
        fields.append(("5m Change", f"{'+' if change_5m >= 0 else ''}{change_5m:.2f}%", True))
        
        if len(history) > 1:
            fields.append(("Since Start", f"{'+' if change_since_start >= 0 else ''}{change_since_start:.2f}%", True))
        
        # Use our utility to create the embed
        color = discord.Color.green() if change_1m >= 0 else discord.Color.red()
        
        # Format the symbol name for title
        base_currency, quote_currency = symbol.split("-")
        
        # Add footer with update interval
        interval = self.tracked_prices[symbol]["interval"]
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
        if not self.tracked_prices:
            return
        
        current_time = datetime.now()
        update_tasks = []
        
        for symbol, data in list(self.tracked_prices.items()):
            # Check if it's time to update based on the interval
            time_diff = (current_time - data["last_update"]).total_seconds()
            
            if time_diff >= data["interval"]:
                # Create a task for each symbol that needs updating
                update_tasks.append(self.update_symbol_price(symbol, data))
        
        # Run all updates concurrently
        if update_tasks:
            await asyncio.gather(*update_tasks, return_exceptions=True)
    
    async def update_symbol_price(self, symbol: str, data: Dict[str, Any]):
        """Update price data for a specific symbol"""
        try:
            # Get updated price data
            updated_data = await self.get_symbol_data(symbol)
            
            if not updated_data:
                logger.warning(f"Failed to update price for {symbol}")
                return
            
            # Update tracked data
            self.tracked_prices[symbol]["price_data"] = updated_data
            self.tracked_prices[symbol]["last_update"] = datetime.now()
            
            # Update price history (keep last 60 entries - ~ 1 hour at 60s interval)
            self.tracked_prices[symbol]["history"].append(float(updated_data["price"]))
            if len(self.tracked_prices[symbol]["history"]) > 60:
                self.tracked_prices[symbol]["history"] = self.tracked_prices[symbol]["history"][-60:]
            
            # Update the message if possible
            try:
                channel = self.bot.get_channel(data["channel_id"])
                if channel:
                    message = await channel.fetch_message(data["message_id"])
                    embed = self._create_price_embed(symbol, updated_data)
                    await message.edit(embed=embed)
                    logger.debug(f"Updated price for {symbol}: ${float(updated_data['price']):.2f}")
            except Exception as e:
                logger.error(f"Error updating message for {symbol}: {str(e)}")
                # Remove tracking if message is gone
                if "Unknown Message" in str(e):
                    del self.tracked_prices[symbol]
                    logger.info(f"Removed tracking for {symbol} due to missing message")
        
        except Exception as e:
            logger.error(f"Error in price tracker for {symbol}: {str(e)}")
    
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
        
        # Check if this message is one of our tracking messages
        tracked_symbol = None
        for symbol, data in self.tracked_prices.items():
            if data["message_id"] == message.id:
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
            del self.tracked_prices[tracked_symbol]
            await message.clear_reactions()
            logger.info(f"User {user.name} stopped tracking {tracked_symbol}")
        
        # Handle chart/details reaction
        elif str(reaction.emoji) == "📊":
            # Get the historical data
            history = self.tracked_prices[tracked_symbol]["history"]
            
            # Create fields for the detailed view
            fields = []
            
            # Calculate some statistics
            if len(history) > 1:
                current = history[-1]
                high = max(history)
                low = min(history)
                avg = sum(history) / len(history)
                
                # Add statistics fields
                fields.append(("Current", f"${current:.2f}", True))
                fields.append(("High", f"${high:.2f}", True))
                fields.append(("Low", f"${low:.2f}", True))
                fields.append(("Average", f"${avg:.2f}", True))
                fields.append(("Range", f"${high-low:.2f}", True))
                
                # Add percentage from high/low
                pct_from_high = ((current - high) / high) * 100
                pct_from_low = ((current - low) / low) * 100
                fields.append(("From High/Low", f"{pct_from_high:.2f}% / {pct_from_low:.2f}%", True))
                
                # Calculate volatility (standard deviation) using polars
                if len(history) > 2:
                    df = pl.DataFrame({"price": history})
                    volatility = df.select(pl.col("price").std()).item()
                    
                    # Calculate rolling changes
                    changes = [(history[i] - history[i-1]) / history[i-1] * 100 for i in range(1, len(history))]
                    pos_changes = sum(1 for c in changes if c > 0)
                    neg_changes = sum(1 for c in changes if c < 0)
                    
                    fields.append(("Volatility", f"{volatility:.2f} ({pos_changes} ↑ / {neg_changes} ↓)", True))
            
            # Add tracking information
            created_at = self.tracked_prices[tracked_symbol]["created_at"]
            time_elapsed = datetime.now() - created_at
            hours, remainder = divmod(int(time_elapsed.total_seconds()), 3600)
            minutes, seconds = divmod(remainder, 60)
            
            tracking_info = (
                f"Started: {created_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"Running: {hours}h {minutes}m {seconds}s\n"
                f"Interval: {self.tracked_prices[tracked_symbol]['interval']}s\n"
                f"Data points: {len(history)}"
            )
            
            fields.append(("Tracking Info", tracking_info, False))
            
            # Add numeric recent price history (last 10 points)
            if len(history) > 1:
                # Calculate timestamps
                interval = self.tracked_prices[tracked_symbol]["interval"]
                recent_history = history[-10:]
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