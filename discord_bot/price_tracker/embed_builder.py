"""
Discord embed builder for price tracking.
Handles creating and formatting embeds for price data.
"""

from typing import Dict, List, Any, Optional, Tuple
import discord
from datetime import datetime
from loguru import logger

from .tracker_model import TrackedPrice
from utils.embed_utilities import create_price_embed


class EmbedBuilder:
    """Builder for price tracking embeds"""
    
    def build_tracking_embed(self, tracked: TrackedPrice) -> discord.Embed:
        """
        Build a Discord embed for tracked price data.
        
        Args:
            tracked: The TrackedPrice object
            
        Returns:
            Formatted Discord embed
        """
        # Extract price and calculate changes
        current_price = tracked.current_price
        changes = tracked.calculate_changes()
        
        # Prepare price data for the embed utility
        price_data = {
            "price": current_price,
            "bestBid": tracked.price_data.get("bestBid"),
            "bestAsk": tracked.price_data.get("bestAsk")
        }
        
        # Add custom fields for our specific needs
        fields = []
        
        fields.append(("1m Change", f"{'+' if changes['change_1m'] >= 0 else ''}{changes['change_1m']:.2f}%", True))
        fields.append(("5m Change", f"{'+' if changes['change_5m'] >= 0 else ''}{changes['change_5m']:.2f}%", True))
        
        start_price = tracked.starting_price
        if start_price:
            change_since_start = changes["change_since_start"]
            fields.append(("Since Start", f"{'+' if change_since_start >= 0 else ''}{change_since_start:.2f}%", True))
        
        # Format the symbol name for title
        symbol = tracked.symbol
        base_currency, quote_currency = symbol.split("-")
        
        # Add footer with update interval
        interval = tracked.interval
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
    
    def build_stopped_embed(self, tracked: TrackedPrice) -> discord.Embed:
        """
        Build a Discord embed for a stopped price tracker.
        
        Args:
            tracked: The TrackedPrice object
            
        Returns:
            Formatted Discord embed
        """
        # Get the tracking embed and modify it
        embed = self.build_tracking_embed(tracked)
        
        # Update title and color
        embed.title = f"{embed.title} (Stopped)"
        embed.color = discord.Color.light_grey()
        embed.set_footer(text="Tracking stopped")
        
        return embed
    
    def build_details_embed(self, tracked: TrackedPrice) -> discord.Embed:
        """
        Build a detailed view embed with statistics.
        
        Args:
            tracked: The TrackedPrice object
            
        Returns:
            Formatted Discord embed
        """
        # Calculate statistics
        stats = tracked.calculate_stats()
        changes = tracked.calculate_changes()
        history = tracked.history
        
        # Create fields for the detailed view
        fields = []
        
        # Add statistics fields
        if stats:
            fields.append(("Current", f"${tracked.current_price:.2f}", True))
            fields.append(("High", f"${stats['high']:.2f}", True))
            fields.append(("Low", f"${stats['low']:.2f}", True))
            fields.append(("Average", f"${stats['avg']:.2f}", True))
            fields.append(("Range", f"${stats['range']:.2f}", True))
            
            # Add percentage from high/low
            fields.append(("From High/Low", f"{stats['pct_from_high']:.2f}% / {stats['pct_from_low']:.2f}%", True))
            
            # Calculate volatility and trend info
            if len(history) > 2:
                try:
                    import polars as pl
                    df = pl.DataFrame({"price": history})
                    volatility = df.select(pl.col("price").std()).item()
                    
                    # Calculate rolling changes
                    changes = [(history[i] - history[i-1]) / history[i-1] * 100 for i in range(1, len(history))]
                    pos_changes = sum(1 for c in changes if c > 0)
                    neg_changes = sum(1 for c in changes if c < 0)
                    
                    fields.append(("Volatility", f"{volatility:.2f} ({pos_changes} ↑ / {neg_changes} ↓)", True))
                except:
                    # If polars fails, skip this section
                    pass
        
        # Add tracking information
        created_at = tracked.created_at
        time_elapsed = datetime.now() - created_at
        hours, remainder = divmod(int(time_elapsed.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        
        tracking_info = (
            f"Started: {created_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"Running: {hours}h {minutes}m {seconds}s\n"
            f"Interval: {tracked.interval}s\n"
            f"Data points: {len(history)}"
        )
        
        fields.append(("Tracking Info", tracking_info, False))
        
        # Add numeric recent price history (last 10 points)
        if len(history) > 1:
            # Calculate timestamps
            interval = tracked.interval
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
        
        # Create the detailed embed using utility
        embed = discord.Embed(
            title=f"{tracked.symbol} Detailed Price View",
            description="Historical price analysis and statistics",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        
        # Add all fields
        for name, value, inline in fields:
            embed.add_field(name=name, value=value, inline=inline)
            
        return embed