"""
Handler for Discord reactions on price tracking messages.
Manages user interactions with tracked price embeds.
"""

import discord
from typing import Optional
from loguru import logger

from .tracker_manager import TrackerManager


class ReactionHandler:
    """Handler for reactions on price tracking messages"""
    
    def __init__(self, manager: TrackerManager):
        """
        Initialize the reaction handler.
        
        Args:
            manager: Tracker manager instance
        """
        self.manager = manager
        logger.debug("Initialized ReactionHandler")
    
    async def handle_reaction(
        self, 
        reaction: discord.Reaction, 
        user: discord.User
    ) -> None:
        """
        Handle a reaction being added to a message.
        
        Args:
            reaction: Discord reaction
            user: User who added the reaction
        """
        # Ignore bot's own reactions
        if user.bot:
            return
        
        message = reaction.message
        emoji = str(reaction.emoji)
        
        # Try to find which symbol this message is for
        tracked_symbol = None
        for symbol, tracked in self.manager.storage.get_all_tracked_prices().items():
            if tracked.message_id == message.id:
                tracked_symbol = symbol
                break
        
        if not tracked_symbol:
            return
        
        # Handle stop tracking reaction
        if emoji == "⏹️":
            await self._handle_stop_tracking(reaction, user, tracked_symbol)
        
        # Handle chart/details reaction
        elif emoji == "📊":
            await self._handle_show_details(reaction, user, tracked_symbol)
    
    async def _handle_stop_tracking(
        self, 
        reaction: discord.Reaction, 
        user: discord.User, 
        symbol: str
    ) -> None:
        """
        Handle the stop tracking reaction.
        
        Args:
            reaction: Discord reaction
            user: User who added the reaction
            symbol: Symbol being tracked
        """
        message = reaction.message
        embed = message.embeds[0] if message.embeds else None
        
        # Stop tracking
        await self.manager.stop_tracking(symbol)
        logger.info(f"User {user.name} stopped tracking {symbol}")
    
    async def _handle_show_details(
        self, 
        reaction: discord.Reaction, 
        user: discord.User, 
        symbol: str
    ) -> None:
        """
        Handle the show details reaction.
        
        Args:
            reaction: Discord reaction
            user: User who added the reaction
            symbol: Symbol being tracked
        """
        message = reaction.message
        channel = message.channel
        
        # Show detailed view
        await self.manager.show_details(channel, symbol)
        
        # Remove the user's reaction to allow clicking again
        try:
            await message.remove_reaction("📊", user)
        except:
            pass