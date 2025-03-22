"""
Data models for portfolio tracking.
Defines the structure of portfolio positions and related data.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime


@dataclass
class Position:
    """Data model for a portfolio position"""
    ticker: str
    shares: float
    entry_price: float
    current_price: float = 0.0
    current_value: float = 0.0
    initial_value: float = 0.0
    gain_loss: float = 0.0
    gain_loss_percent: float = 0.0
    
    def __post_init__(self):
        """Calculate derived values if not provided"""
        if self.initial_value == 0.0:
            self.initial_value = self.shares * self.entry_price
            
        if self.current_price > 0 and self.current_value == 0.0:
            self.current_value = self.shares * self.current_price
            
        if self.gain_loss == 0.0:
            self.gain_loss = self.current_value - self.initial_value
            
        if self.gain_loss_percent == 0.0 and self.initial_value > 0:
            self.gain_loss_percent = (self.gain_loss / self.initial_value) * 100
    
    def update_price(self, new_price: float) -> None:
        """Update the position with a new price"""
        self.current_price = new_price
        self.current_value = self.shares * new_price
        self.gain_loss = self.current_value - self.initial_value
        
        if self.initial_value > 0:
            self.gain_loss_percent = (self.gain_loss / self.initial_value) * 100


@dataclass
class Portfolio:
    """Data model for the entire portfolio"""
    positions: Dict[str, Position] = field(default_factory=dict)
    last_update: Optional[datetime] = None
    
    @property
    def total_current_value(self) -> float:
        """Get the total current value of the portfolio"""
        return sum(position.current_value for position in self.positions.values())
    
    @property
    def total_initial_value(self) -> float:
        """Get the total initial value of the portfolio"""
        return sum(position.initial_value for position in self.positions.values())
    
    @property
    def total_gain_loss(self) -> float:
        """Get the total gain/loss for the portfolio"""
        return self.total_current_value - self.total_initial_value
    
    @property
    def total_gain_loss_percent(self) -> float:
        """Get the total gain/loss percentage for the portfolio"""
        if self.total_initial_value > 0:
            return (self.total_gain_loss / self.total_initial_value) * 100
        return 0.0
    
    def update_last_update(self) -> None:
        """Update the last update timestamp"""
        self.last_update = datetime.now()