"""
Utilities for validating command parameters across the bot.
Provides standardized validators and response formatters.
"""

from typing import Tuple, Optional, Any, Dict, Callable, Union
import asyncio
import discord
from discord.ext import commands


class ValidationError(Exception):
    """Exception raised when command validation fails."""
    pass


def validate_positive_number(value: str, min_value: float = 0) -> Tuple[bool, str]:
    """
    Validate that a string can be converted to a positive number.
    
    Args:
        value: String to validate
        min_value: Minimum acceptable value (default: 0)
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        num = float(value)
        if num <= min_value:
            return False, f"Value must be greater than {min_value}."
        return True, ""
    except ValueError:
        return False, "Invalid number format."


def validate_symbol(value: str) -> Tuple[bool, str]:
    """
    Validate a trading symbol/pair format.
    
    Args:
        value: Symbol to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        value = value.upper()
        if "-" in value and len(value.split("-")) == 2:
            base, quote = value.split("-")
            if base and quote:  # Ensure both parts are non-empty
                return True, ""
        return False, f"Symbol {value} doesn't seem to be in the correct format (e.g., BTC-USDT)."
    except Exception as e:
        return False, f"Error validating symbol: {str(e)}"


def validate_side(value: str) -> Tuple[bool, str]:
    """
    Validate a trading side (buy/sell).
    
    Args:
        value: Side to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if value.lower() in ["buy", "sell"]:
        return True, ""
    return False, "Invalid side. Please enter 'buy' or 'sell'."


def validate_order_type(value: str) -> Tuple[bool, str]:
    """
    Validate order type (market/limit).
    
    Args:
        value: Order type to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if value.lower() in ["market", "limit"]:
        return True, ""
    return False, "Invalid order type. Please enter 'market' or 'limit'."


def validate_choice(value: str, choices: list) -> Tuple[bool, str]:
    """
    Validate that a value is one of the allowed choices.
    
    Args:
        value: Value to validate
        choices: List of allowed choices
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if value.lower() in [c.lower() for c in choices]:
        return True, ""
    return False, f"Invalid choice. Please enter one of: {', '.join(choices)}."


def validate_interval(value: str, min_interval: int = 10, max_interval: int = 3600) -> Tuple[bool, str]:
    """
    Validate a time interval.
    
    Args:
        value: Interval to validate
        min_interval: Minimum allowed interval in seconds
        max_interval: Maximum allowed interval in seconds
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        interval = int(value)
        if interval < min_interval:
            return False, f"Interval must be at least {min_interval} seconds to avoid rate limiting."
        if interval > max_interval:
            return False, f"Interval must be at most {max_interval} seconds."
        return True, ""
    except ValueError:
        return False, "Invalid interval format. Please enter a number."


async def get_user_input(
    ctx: commands.Context,
    prompt: str,
    validator: Optional[Callable[[str], Tuple[bool, str]]] = None,
    timeout: int = 60,
    delete_prompt: bool = False,
    allow_cancel: bool = True
) -> Optional[str]:
    """
    Collect and validate user input interactively.
    
    Args:
        ctx: Discord context
        prompt: Prompt message to display
        validator: Optional validation function
        timeout: Timeout in seconds
        delete_prompt: Whether to delete the prompt message after response
        allow_cancel: Whether to allow the user to cancel
        
    Returns:
        Validated input or None if cancelled/timed out
    """
    prompt_msg = await ctx.send(prompt)

    def check(message):
        return message.author == ctx.author and message.channel == ctx.channel

    try:
        user_response = await ctx.bot.wait_for("message", timeout=timeout, check=check)
        
        # Check for cancel command if allowed
        if allow_cancel and user_response.content.lower() in ["cancel", "exit", "quit"]:
            await ctx.send("🛑 Command cancelled.")
            return None
            
        # Validate the response
        if validator:
            result, error_msg = validator(user_response.content)
            if not result:
                await ctx.send(f"❌ {error_msg} Please try again or type 'cancel' to exit.")
                # Delete the original prompt and invalid response if requested
                if delete_prompt:
                    await prompt_msg.delete()
                    await user_response.delete()
                # Try again
                return await get_user_input(ctx, prompt, validator, timeout, delete_prompt, allow_cancel)
                
        # Delete messages if requested
        if delete_prompt:
            await prompt_msg.delete()
            await user_response.delete()
            
        return user_response.content
        
    except asyncio.TimeoutError:
        await ctx.send("⏱️ No input received. Command cancelled.")
        return None


async def confirm_action(
    ctx: commands.Context,
    title: str,
    description: str,
    color: discord.Color = discord.Color.red(),
    timeout: int = 30,
    use_reactions: bool = True
) -> bool:
    """
    Get confirmation for an action via reaction or message.
    
    Args:
        ctx: Discord context
        title: Confirmation embed title
        description: Confirmation embed description
        color: Embed color
        timeout: Timeout in seconds
        use_reactions: Whether to use reactions (✅/❌) instead of text response
        
    Returns:
        True if confirmed, False otherwise
    """
    # Create confirmation embed
    embed = discord.Embed(
        title=title,
        description=description,
        color=color
    )
    
    if use_reactions:
        embed.set_footer(text="React with ✅ to confirm or ❌ to cancel")
        message = await ctx.send(embed=embed)
        await message.add_reaction("✅")
        await message.add_reaction("❌")
        
        # Wait for reaction
        def check(reaction, user):
            return (
                user == ctx.author
                and reaction.message.id == message.id
                and str(reaction.emoji) in ["✅", "❌"]
            )
        
        try:
            reaction, user = await ctx.bot.wait_for("reaction_add", timeout=timeout, check=check)
            return str(reaction.emoji) == "✅"
        except asyncio.TimeoutError:
            await ctx.send("⏱️ No response received. Action cancelled.")
            return False
    else:
        # Use text response
        embed.set_footer(text="Reply with 'yes' to confirm or 'no' to cancel")
        await ctx.send(embed=embed)
        
        def check(message):
            return (
                message.author == ctx.author
                and message.channel == ctx.channel
                and message.content.lower() in ["yes", "no"]
            )
        
        try:
            response = await ctx.bot.wait_for("message", timeout=timeout, check=check)
            return response.content.lower() == "yes"
        except asyncio.TimeoutError:
            await ctx.send("⏱️ No response received. Action cancelled.")
            return False