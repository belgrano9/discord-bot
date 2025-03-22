"""
Account commands for trading.
Handles account and balance information.
"""

import discord
from discord.ext import commands
from typing import Optional
from loguru import logger

from ..services.kucoin_service import KuCoinService
from ..formatters.account_formatter import AccountFormatter


class AccountCommands:
    """Command handlers for account information"""
    
    def __init__(self):
        """Initialize account commands"""
        self.kucoin_service = KuCoinService()
        self.account_formatter = AccountFormatter()
        logger.debug("Initialized AccountCommands")
    
    async def handle_balance(self, ctx: commands.Context, symbol: str = "BTC-USDT") -> None:
        """
        Handle the balance command.
        
        Args:
            ctx: Discord context
            symbol: Trading pair symbol
        """
        # Security measure: Check if user has the correct role
        required_role = discord.utils.get(ctx.guild.roles, name="Trading-Authorized")
        if required_role is None or required_role not in ctx.author.roles:
            await ctx.send("⛔ You don't have permission to view balance information. You need the 'Trading-Authorized' role.")
            return
        
        # Show processing message
        processing_message = await ctx.send(f"⏳ Retrieving isolated margin account information for {symbol}...")
        
        try:
            # Get the margin account information
            account = await self.kucoin_service.get_margin_account(symbol)
            
            if not account:
                await processing_message.edit(content=f"No isolated margin account data found for {symbol}.")
                return
            
            # Create the embed
            embed = self.account_formatter.format_margin_account(account)
            
            # Send the embed
            await processing_message.edit(content=None, embed=embed)
            
        except Exception as e:
            # Handle any exceptions
            await processing_message.edit(content=f"❌ Error retrieving account information: {str(e)}")
    
    async def handle_last_trade(self, ctx: commands.Context, symbol: str = "BTC-USDT") -> None:
        """
        Handle the last trade command.
        
        Args:
            ctx: Discord context
            symbol: Trading pair symbol
        """
        try:
            # Get recent trades and take the most recent
            trades = await self.kucoin_service.get_recent_trades(symbol, limit=1)
            
            if not trades:
                await ctx.send(f"No recent trades found for {symbol}.")
                return
            
            # Get the most recent trade
            trade = trades[0]
            
            # Create the embed
            embed = self.account_formatter.format_single_trade(trade)
            
            # Send the embed
            message = await ctx.send(embed=embed)
            
            # Add clipboard reaction if there's an order ID
            if trade.order_id:
                await message.add_reaction("📋")
                # This would be handled by the cog to register the message ID
                
        except Exception as e:
            await ctx.send(f"❌ Error retrieving last trade: {str(e)}")
    
    async def handle_list_trades(
        self,
        ctx: commands.Context,
        symbol: Optional[str] = None,
        limit: int = 20
    ) -> None:
        """
        Handle the list trades command.
        
        Args:
            ctx: Discord context
            symbol: Trading pair symbol (optional)
            limit: Maximum number of trades to show
        """
        try:
            # Normalize symbol if provided
            if symbol:
                symbol = symbol.upper()
            
            # Cap limit to avoid excessive data
            limit = min(limit, 100)
            
            # Get the trade history
            trades = await self.kucoin_service.get_recent_trades(symbol, limit)
            
            # Create the embed
            embed = self.account_formatter.format_trade_list(trades, symbol, limit)
            
            # Send the embed
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"❌ Error listing trades: {str(e)}")