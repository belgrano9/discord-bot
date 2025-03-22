"""
Command handlers for portfolio commands.
Coordinates services and formatters to process user commands.
"""

import discord
from discord.ext import commands
from typing import Dict, List, Any, Optional
from loguru import logger

from .models import Portfolio
from .portfolio_storage import PortfolioStorage
from .calculator import PortfolioCalculator
from .embed_builder import PortfolioEmbedBuilder


class PortfolioCommands:
    """Command handlers for portfolio tracking"""
    
    def __init__(self, storage: PortfolioStorage):
        """
        Initialize with required services.
        
        Args:
            storage: Portfolio storage manager
        """
        self.storage = storage
        self.calculator = PortfolioCalculator()
        self.embed_builder = PortfolioEmbedBuilder()
        self.last_portfolio_value = None
        logger.debug("Initialized PortfolioCommands")
    
    async def handle_show_portfolio(self, ctx: commands.Context) -> None:
        """
        Handle the portfolio command.
        
        Args:
            ctx: Discord context
        """
        await self._send_portfolio_update(ctx.channel)
    
    async def _send_portfolio_update(self, channel) -> None:
        """
        Send portfolio update to the specified channel.
        
        Args:
            channel: Discord channel
        """
        try:
            # Get portfolio data
            portfolio = await self.storage.get_portfolio(use_cache=False)
            
            if not portfolio.positions:
                await channel.send("❌ Could not retrieve current portfolio data")
                return
                
            # Calculate value change since last update
            value_change = None
            if self.last_portfolio_value is not None:
                value_change = self.calculator.calculate_value_change(
                    portfolio.total_current_value,
                    self.last_portfolio_value
                )
                
            # Update the last portfolio value
            self.last_portfolio_value = portfolio.total_current_value
            
            # Calculate top and bottom performers
            top_performers, underperformers = self.calculator.calculate_position_performance(portfolio)
            
            # Create regular portfolio embed
            portfolio_embed = self.embed_builder.build_portfolio_embed(portfolio)
            
            # Create performance embed if we have enough positions
            if len(portfolio.positions) >= 3:
                performance_embed = self.embed_builder.build_performance_embed(
                    portfolio, 
                    top_performers, 
                    underperformers,
                    value_change=value_change
                )
                # Send both embeds
                await channel.send(embed=portfolio_embed)
                await channel.send(embed=performance_embed)
            else:
                # Just send the main embed
                await channel.send(embed=portfolio_embed)
                
            logger.info(f"Portfolio update sent to channel {channel.id}")
            
        except Exception as e:
            logger.error(f"Error updating portfolio: {str(e)}")
            await channel.send(f"❌ Error updating portfolio: {str(e)}")
    
    def get_portfolio_summary(self) -> Optional[Dict[str, Any]]:
        """
        Get portfolio summary for other cogs.
        
        Returns:
            Dictionary with portfolio summary data
        """
        if not hasattr(self, '_cached_portfolio') or not self._cached_portfolio:
            return None
            
        portfolio = self._cached_portfolio
        return self.calculator.calculate_portfolio_summary(portfolio)