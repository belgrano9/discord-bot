"""
Generator for portfolio reports.
Creates report embeds with performance data.
"""

import discord
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from loguru import logger


class ReportGenerator:
    """Generator for portfolio reports"""
    
    def __init__(self, portfolio_tracker):
        """
        Initialize the report generator.
        
        Args:
            portfolio_tracker: Portfolio tracker instance
        """
        self.portfolio_tracker = portfolio_tracker
        self.historical_data = {}  # {date_str: portfolio_data}
        logger.debug("Initialized ReportGenerator")
    
    async def store_daily_data(self) -> bool:
        """
        Store today's portfolio data for historical comparison.
        
        Returns:
            Whether data was successfully stored
        """
        try:
            # Get portfolio data from tracker
            portfolio_data = self.portfolio_tracker.get_portfolio_summary()
            if not portfolio_data:
                logger.warning("Could not retrieve portfolio data for historical storage")
                return False
                
            # Store daily value
            today = datetime.now().strftime("%Y-%m-%d")
            self.historical_data[today] = portfolio_data
            
            # Keep only last 30 days of data
            keys = sorted(self.historical_data.keys())
            if len(keys) > 30:
                for old_key in keys[:-30]:
                    logger.debug(f"Removing old historical data for {old_key}")
                    del self.historical_data[old_key]
                    
            logger.debug(f"Stored historical data for {today}, now have data for {len(self.historical_data)} days")
            return True
            
        except Exception as e:
            logger.error(f"Error storing historical data: {e}")
            return False
    
    async def _get_comparison_data(self, days_ago: int) -> Optional[Dict[str, Any]]:
        """
        Get portfolio data from a specific number of days ago.
        
        Args:
            days_ago: Number of days ago to retrieve data for
            
        Returns:
            Historical portfolio data or None if not available
        """
        # Calculate target date
        target_date = (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d")
        
        # Check if we have data for that exact date
        if target_date in self.historical_data:
            return self.historical_data[target_date]
            
        # If not, try to find the closest older date
        dates = sorted(self.historical_data.keys())
        for date in dates:
            if date < datetime.now().strftime("%Y-%m-%d"):
                return self.historical_data[date]
                
        return None
    
    async def generate_daily_report(self, channel) -> bool:
        """
        Generate and send a daily portfolio report.
        
        Args:
            channel: Discord channel to send report to
            
        Returns:
            Whether the report was successfully sent
        """
        try:
            # Get current portfolio data
            portfolio_data = self.portfolio_tracker._get_portfolio_data()
            if not portfolio_data:
                logger.warning("Could not retrieve portfolio data for daily report")
                await channel.send(
                    "❌ Could not retrieve current portfolio data for daily report"
                )
                return False
                
            # Get yesterday's data for comparison
            yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
            yesterday_data = self.historical_data.get(yesterday)
            
            # Create embed
            embed = await self._create_performance_report(
                portfolio_data, yesterday_data, "Daily Portfolio Report", "yesterday"
            )
            
            await channel.send(embed=embed)
            logger.info(f"Daily report sent to channel {channel.name}")
            return True
            
        except Exception as e:
            logger.error(f"Error generating daily report: {str(e)}")
            await channel.send(f"❌ Error generating daily report: {str(e)}")
            return False
    
    async def generate_weekly_report(self, channel) -> bool:
        """
        Generate and send a weekly portfolio report.
        
        Args:
            channel: Discord channel to send report to
            
        Returns:
            Whether the report was successfully sent
        """
        try:
            # Get current portfolio data
            portfolio_data = self.portfolio_tracker._get_portfolio_data()
            if not portfolio_data:
                logger.warning("Could not retrieve portfolio data for weekly report")
                await channel.send(
                    "❌ Could not retrieve current portfolio data for weekly report"
                )
                return False
                
            # Get data from 7 days ago
            week_ago_data = await self._get_comparison_data(7)
            
            # Create embed
            embed = await self._create_performance_report(
                portfolio_data, week_ago_data, "Weekly Portfolio Report", "last week"
            )
            
            await channel.send(embed=embed)
            logger.info(f"Weekly report sent to channel {channel.name}")
            return True
            
        except Exception as e:
            logger.error(f"Error generating weekly report: {str(e)}")
            await channel.send(f"❌ Error generating weekly report: {str(e)}")
            return False
    
    async def _create_performance_report(
        self, 
        current_data, 
        previous_data, 
        title, 
        period_name
    ) -> discord.Embed:
        """
        Create a performance report comparing current to previous data.
        
        Args:
            current_data: Current portfolio data
            previous_data: Previous portfolio data
            title: Report title
            period_name: Name of comparison period
            
        Returns:
            Formatted Discord embed
        """
        # Calculate total values
        total_current_value = sum(item["current_value"] for item in current_data)
        
        # Create embed with appropriate color
        embed = discord.Embed(
            title=title,
            description=f"Report generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            color=discord.Color.blue(),
        )
        
        # Add current portfolio summary
        embed.add_field(
            name="Current Total Value", 
            value=f"${total_current_value:.2f}", 
            inline=True
        )
        
        # Compare with previous period if available
        if previous_data:
            previous_value = previous_data["total_value"]
            value_change = total_current_value - previous_value
            value_change_percent = (
                (value_change / previous_value * 100) if previous_value else 0
            )
            
            sign = "+" if value_change >= 0 else ""
            embed.add_field(
                name=f"Change from {period_name}",
                value=f"{sign}${value_change:.2f} ({sign}{value_change_percent:.2f}%)",
                inline=True,
            )
            
            # Update embed color based on performance
            embed.color = (
                discord.Color.green() if value_change >= 0 else discord.Color.red()
            )
            
        # Add positions summary
        positions_text = ""
        for item in current_data:
            ticker = item["ticker"]
            current_price = item["current_price"]
            gain_loss_percent = item["gain_loss_percent"]
            
            # Check if we have previous data for this position
            position_change = "N/A"
            if previous_data:
                prev_position = next(
                    (
                        p
                        for p in previous_data.get("portfolio_data", [])
                        if p["ticker"] == ticker
                    ),
                    None,
                )
                if prev_position:
                    pos_change = current_price - prev_position["current_price"]
                    pos_change_pct = (
                        (pos_change / prev_position["current_price"] * 100)
                        if prev_position["current_price"]
                        else 0
                    )
                    sign = "+" if pos_change >= 0 else ""
                    position_change = f"{sign}{pos_change_pct:.2f}%"
                    
            positions_text += f"• {ticker}: ${current_price:.2f} ({position_change} since {period_name})\n"
            
        if positions_text:
            embed.add_field(name="Position Updates", value=positions_text, inline=False)
            
        return embed