"""
Input manager for trading commands.
Handles collecting and validating user input.
"""

import discord
from discord.ext import commands
import asyncio
from typing import Dict, List, Any, Optional, Callable, Tuple, Generic, TypeVar
from loguru import logger

from ..models.order import OrderRequest, OrderSide, OrderType


T = TypeVar('T')  # Generic type for collect_input result


class InputManager:
    """Manager for user input collection and validation"""
    
    async def collect_input(
        self,
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
                    return await self.collect_input(ctx, prompt, validator, timeout, delete_prompt, allow_cancel)
                    
            # Delete messages if requested
            if delete_prompt:
                await prompt_msg.delete()
                await user_response.delete()
                
            return user_response.content
            
        except asyncio.TimeoutError:
            await ctx.send("⏱️ No input received. Command cancelled.")
            return None
    
    async def confirm_action(
        self,
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
    
    async def collect_trade_parameters(
        self, 
        ctx: commands.Context, 
        is_real: bool = False
    ) -> Optional[OrderRequest]:
        """
        Collect trade parameters interactively.
        
        Args:
            ctx: Discord context
            is_real: Whether this is for a real trade
            
        Returns:
            OrderRequest object or None if cancelled
        """
        # Define validators
        def validate_symbol(value):
            value = value.upper()
            if "-" in value and len(value.split("-")) == 2:
                base, quote = value.split("-")
                if base and quote:  # Ensure both parts are non-empty
                    return True, ""
            return False, f"Symbol {value} doesn't seem to be in the correct format (e.g., BTC-USDT)."
            
        def validate_order_type(value):
            if value.lower() in ["market", "limit"]:
                return True, ""
            return False, "Invalid order type. Please enter 'market' or 'limit'."
            
        def validate_side(value):
            if value.lower() in ["buy", "sell"]:
                return True, ""
            return False, "Invalid side. Please enter 'buy' or 'sell'."
            
        def validate_amount(value):
            try:
                amount = float(value)
                if amount <= 0:
                    return False, "Amount must be greater than 0."
                return True, ""
            except ValueError:
                return False, "Invalid number format. Please enter a valid amount."
                
        def validate_price(value):
            try:
                price = float(value)
                if price <= 0:
                    return False, "Price must be greater than 0."
                return True, ""
            except ValueError:
                return False, "Invalid number format. Please enter a valid price."
        
        # 1. Ask for market/trading pair
        symbol = await self.collect_input(
            ctx,
            "📊 Enter the trading pair (e.g., BTC-USDT):",
            validator=validate_symbol,
            timeout=60
        )
        if not symbol:
            return None
            
        # 2. Ask for order type (market or limit)
        order_type_str = await self.collect_input(
            ctx,
            "📝 Order type (market or limit)?",
            validator=validate_order_type,
            timeout=60
        )
        if not order_type_str:
            return None
            
        order_type = OrderType.MARKET if order_type_str.lower() == "market" else OrderType.LIMIT
            
        # 3. Ask for side (buy/sell)
        side_str = await self.collect_input(
            ctx,
            "📈 Buy or sell?",
            validator=validate_side,
            timeout=60
        )
        if not side_str:
            return None
            
        side = OrderSide.BUY if side_str.lower() == "buy" else OrderSide.SELL
            
        # 4. Ask for amount
        amount_str = await self.collect_input(
            ctx,
            "💰 Enter the amount to trade:",
            validator=validate_amount,
            timeout=60
        )
        if not amount_str:
            return None
            
        amount = float(amount_str)
            
        # 5. For limit orders, we need price
        price = None
        if order_type == OrderType.LIMIT:
            price_str = await self.collect_input(
                ctx,
                "💲 Enter the price for your limit order:",
                validator=validate_price,
                timeout=60
            )
            if not price_str:
                return None
                
            price = float(price_str)
                
        # Create the order request
        return OrderRequest(
            symbol=symbol.upper(),
            side=side,
            order_type=order_type,
            amount=amount,
            price=price,
            is_isolated=True,
            auto_borrow=False
        )