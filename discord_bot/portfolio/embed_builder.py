"""
Embed builder for portfolio data.
Creates formatted Discord embeds for portfolio displays.
"""

import discord
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from loguru import logger

from utils.embed_utilities import create_portfolio_embed
from .models import Portfolio, Position


class PortfolioEmbedBuilder:
    """Builder for portfolio embeds"""
    
    def build_portfolio_embed(
        self,
        portfolio: Portfolio,
        title: str = "Portfolio Summary",
        description: Optional[str] = None,
        previous_value: Optional[float] = None,
        comparison_label: str = "previous update",
        max_positions: int = 10
    ) -> discord.Embed:
        """
        Build a portfolio summary embed.
        
        Args:
            portfolio: Portfolio to display
            title: Embed title
            description: Optional description
            previous_value: Optional previous value for comparison
            comparison_label: Label for comparison period
            max_positions: Maximum positions to display
            
        Returns:
            Formatted Discord embed
        """
        # Convert Portfolio to format expected by embed utility
        portfolio_data = []
        
        for ticker, position in portfolio.positions.items():
            portfolio_data.append({
                "ticker": ticker,
                "shares": position.shares,
                "entry_price": position.entry_price,
                "current_price": position.current_price,
                "initial_value": position.initial_value,
                "current_value": position.current_value,
                "gain_loss": position.gain_loss,
                "gain_loss_percent": position.gain_loss_percent
            })
            
        # Create previous data if available
        previous_data = None
        if previous_value is not None:
            previous_data = {"total_value": previous_value}
            
        # Create description with timestamp if not provided
        if description is None:
            timestamp = portfolio.last_update or datetime.now()
            description = f"Portfolio summary as of {timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
            
        # Use utility function to create embed
        embed = create_portfolio_embed(
            portfolio_data=portfolio_data,
            title=title,
            description=description,
            show_positions=True,
            previous_data=previous_data,
            comparison_label=comparison_label,
            max_positions=max_positions
        )
        
        return embed
    
    def build_performance_embed(
        self,
        portfolio: Portfolio,
        top_performers: List[Position],
        underperformers: List[Position],
        title: str = "Portfolio Performance",
        value_change: Optional[Dict[str, float]] = None
    ) -> discord.Embed:
        """
        Build a portfolio performance embed.
        
        Args:
            portfolio: Portfolio to display
            top_performers: List of top performing positions
            underperformers: List of underperforming positions
            title: Embed title
            value_change: Optional value change metrics
            
        Returns:
            Formatted Discord embed
        """
        # Determine color based on overall performance
        color = discord.Color.green() if portfolio.total_gain_loss >= 0 else discord.Color.red()
        
        # Create embed
        embed = discord.Embed(
            title=title,
            description=f"Portfolio performance as of {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            color=color,
        )
        
        # Add overall performance
        embed.add_field(
            name="Total Value", 
            value=f"${portfolio.total_current_value:.2f}", 
            inline=True
        )
        
        # Add change if available
        if value_change:
            change = value_change["value_change"]
            change_pct = value_change["value_change_percent"]
            sign = "+" if change >= 0 else ""
            
            embed.add_field(
                name="Change",
                value=f"{sign}${change:.2f} ({sign}{change_pct:.2f}%)",
                inline=True
            )
        
        # Add top performers
        if top_performers:
            top_text = ""
            for pos in top_performers:
                sign = "+" if pos.gain_loss >= 0 else ""
                top_text += f"• {pos.ticker}: {sign}{pos.gain_loss_percent:.2f}% (${pos.current_value:.2f})\n"
                
            embed.add_field(
                name="Top Performers", 
                value=top_text or "No data", 
                inline=False
            )
        
        # Add underperformers
        if underperformers:
            under_text = ""
            for pos in underperformers:
                sign = "+" if pos.gain_loss >= 0 else ""
                under_text += f"• {pos.ticker}: {sign}{pos.gain_loss_percent:.2f}% (${pos.current_value:.2f})\n"
                
            embed.add_field(
                name="Underperforming Positions", 
                value=under_text, 
                inline=False
            )
            
        return embed