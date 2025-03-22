"""
Calculator for portfolio statistics.
Performs calculations on portfolio data.
"""

from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from loguru import logger

from .models import Portfolio, Position


class PortfolioCalculator:
    """Calculator for portfolio statistics and analytics"""
    
    def calculate_portfolio_summary(self, portfolio: Portfolio) -> Dict[str, Any]:
        """
        Calculate portfolio summary statistics.
        
        Args:
            portfolio: Portfolio to analyze
            
        Returns:
            Dictionary with summary statistics
        """
        if not portfolio.positions:
            return {
                "total_value": 0.0,
                "initial_value": 0.0,
                "gain_loss": 0.0,
                "gain_loss_percent": 0.0,
                "position_count": 0,
                "last_update": None
            }
            
        return {
            "total_value": portfolio.total_current_value,
            "initial_value": portfolio.total_initial_value,
            "gain_loss": portfolio.total_gain_loss,
            "gain_loss_percent": portfolio.total_gain_loss_percent,
            "position_count": len(portfolio.positions),
            "last_update": portfolio.last_update
        }
    
    def calculate_position_performance(self, portfolio: Portfolio) -> Tuple[List[Position], List[Position]]:
        """
        Calculate top and bottom performing positions.
        
        Args:
            portfolio: Portfolio to analyze
            
        Returns:
            Tuple of (top_performers, underperformers)
        """
        if not portfolio.positions:
            return [], []
            
        # Sort positions by performance
        sorted_positions = sorted(
            portfolio.positions.values(),
            key=lambda p: p.gain_loss_percent,
            reverse=True
        )
        
        # Get top 3 performers
        top_performers = sorted_positions[:min(3, len(sorted_positions))]
        
        # Get bottom 3 performers
        underperformers = sorted_positions[-min(3, len(sorted_positions)):]
        underperformers.reverse()  # Reverse so worst is first
        
        return top_performers, underperformers
    
    def calculate_value_change(
        self,
        current_value: float,
        previous_value: Optional[float]
    ) -> Dict[str, float]:
        """
        Calculate change in portfolio value.
        
        Args:
            current_value: Current portfolio value
            previous_value: Previous portfolio value
            
        Returns:
            Dictionary with change metrics
        """
        if previous_value is None or previous_value == 0:
            return {
                "value_change": 0.0,
                "value_change_percent": 0.0
            }
            
        value_change = current_value - previous_value
        value_change_percent = (value_change / previous_value) * 100
        
        return {
            "value_change": value_change,
            "value_change_percent": value_change_percent
        }