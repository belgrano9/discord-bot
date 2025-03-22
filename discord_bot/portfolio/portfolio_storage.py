"""
Storage manager for portfolio data.
Handles loading portfolio configuration and caching data.
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
import asyncio
from loguru import logger

from .models import Portfolio, Position
from .price_service import PortfolioPriceService


class PortfolioStorage:
    """Manager for portfolio data storage"""
    
    def __init__(self, portfolio_config: Dict[str, Dict[str, Any]]):
        """
        Initialize portfolio storage with configuration.
        
        Args:
            portfolio_config: Dictionary mapping ticker -> position data
        """
        self.config = portfolio_config
        self.portfolio = Portfolio()
        self.price_service = PortfolioPriceService()
        self.cache_age = 0  # Cache age in seconds
        logger.debug("Initialized PortfolioStorage")
    
    async def load_portfolio(self) -> Portfolio:
        """
        Load portfolio from configuration.
        
        Returns:
            Loaded portfolio with current prices
        """
        positions = {}
        
        # Create position objects from config
        for ticker, position_data in self.config.items():
            position = Position(
                ticker=ticker,
                shares=position_data["shares"],
                entry_price=position_data["entry_price"]
            )
            positions[ticker] = position
            
        # Create portfolio
        self.portfolio = Portfolio(positions=positions)
        
        # Update prices
        await self.update_prices()
        
        return self.portfolio
    
    async def update_prices(self) -> bool:
        """
        Update all position prices.
        
        Returns:
            Whether the update was successful
        """
        try:
            # Update all positions in parallel
            positions = list(self.portfolio.positions.values())
            updated = await self.price_service.update_positions_batch(positions)
            
            if updated:
                self.portfolio.update_last_update()
                self.cache_age = 0  # Reset cache age
                logger.debug(f"Updated prices for {len(updated)} positions")
                return True
                
            return False
            
        except Exception as e:
            logger.error(f"Error updating portfolio prices: {str(e)}")
            return False
    
    async def get_portfolio(self, use_cache: bool = True, max_cache_age: int = 60) -> Portfolio:
        """
        Get the current portfolio.
        
        Args:
            use_cache: Whether to use cached data if available
            max_cache_age: Maximum age of cache in seconds
            
        Returns:
            Current portfolio with up-to-date prices
        """
        # Check if we need to load or update
        if not self.portfolio.positions:
            return await self.load_portfolio()
            
        # Check cache age
        if not use_cache or self.cache_age > max_cache_age:
            await self.update_prices()
            
        self.cache_age += 1  # Increment cache age
        return self.portfolio