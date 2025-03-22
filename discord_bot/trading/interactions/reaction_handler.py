"""
Reaction handler for trading commands.
Handles user reactions on message embeds.
"""

import discord
from typing import Dict, Optional
from loguru import logger


class ReactionHandler:
    """Handler for user reactions on trading messages"""
    
    def __init__(self):
        """Initialize the reaction handler"""
        self.order_id_messages = {}  # {message_id: order_id}
        logger.debug("Initialized ReactionHandler")
    
    def register_message(self, message_id: int, order_id: str) -> None:
        """
        Register a message ID with an order ID for clipboard reactions.
        
        Args:
            message_id: Discord message ID
            order_id: Order ID to copy
        """
        self.order_id_messages[message_id] = order_id
        logger.debug(f"Registered message {message_id} with order ID {order_id}")
    
    def unregister_message(self, message_id: int) -> None:
        """
        Unregister a message ID.
        
        Args:
            message_id: Discord message ID to unregister
        """
        if message_id in self.order_id_messages:
            del self.order_id_messages[message_id]
            logger.debug(f"Unregistered message {message_id}")
    
    async def handle_reaction(self, reaction: discord.Reaction, user: discord.User) -> None:
        """
        Handle a reaction being added to a message.
        
        Args:
            reaction: Discord reaction
            user: User who added the reaction
        """
        # Ignore bot's own reactions
        if user.bot:
            return
            
        # Check if this is a clipboard emoji on one of our order messages
        if str(reaction.emoji) == "📋" and reaction.message.id in self.order_id_messages:
            await self._handle_clipboard(reaction, user)
    
    async def _handle_clipboard(self, reaction: discord.Reaction, user: discord.User) -> None:
        """
        Handle clipboard emoji reaction for copying order IDs.
        
        Args:
            reaction: Discord reaction
            user: User who added the reaction
        """
        message = reaction.message
        order_id = self.order_id_messages.get(message.id)
        
        if not order_id:
            return
            
        # Send the order ID as a private message to the user
        try:
            await user.send(f"**Order ID for reference:** `{order_id}`\nYou can use this ID with the !cancel_order command.")
            
            # Also notify in the channel that the ID was sent
            notification = await message.channel.send(
                f"{user.mention} I've sent you the order ID in a private message.",
            )
            
            # Delete the notification after a delay
            await notification.delete(delay=10)
            
        except discord.Forbidden:
            # If we can't DM the user, just post it in the channel
            notification = await message.channel.send(
                f"{user.mention} Here's the order ID for reference: `{order_id}`",
            )
            
            # Delete the notification after a delay
            await notification.delete(delay=20)