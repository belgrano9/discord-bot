"""
Data models for cryptocurrency price tracking.
Defines the structure of tracked prices and their properties.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional


@dataclass
class TrackedPrice:
    """Data model for a tracked cryptocurrency price"""
    symbol: str
    price_data: Dict[str, Any]
    last_update: datetime
    message_id: int
    channel_id: int
    interval: int
    created_at: datetime
    history: List[float] = field(default_factory=list)
    
    @property
    def current_price(self) -> float:
        """Get the current price"""
        return float(self.price_data.get("price", 0))
    
    @property
    def starting_price(self) -> Optional[float]:
        """Get the starting price from history"""
        if self.history and len(self.history) > 0:
            return self.history[0]
        return None
    
    def update_price_data(self, new_data: Dict[str, Any]) -> None:
        """Update the price data and history"""
        self.price_data = new_data
        self.last_update = datetime.now()
        
        # Add to price history
        current = float(new_data.get("price", 0))
        self.history.append(current)
        
        # Keep history limited to last 60 entries
        if len(self.history) > 60:
            self.history = self.history[-60:]
    
    def calculate_changes(self) -> Dict[str, float]:
        """Calculate price changes for different timeframes"""
        current = self.current_price
        changes = {
            "change_1m": 0.0,
            "change_5m": 0.0,
            "change_since_start": 0.0
        }
        
        if len(self.history) > 1:
            # 1-minute change (or whatever the interval represents)
            if len(self.history) > 1:
                changes["change_1m"] = ((current - self.history[-2]) / self.history[-2]) * 100
            
            # 5-minute change
            if len(self.history) > 5:
                changes["change_5m"] = ((current - self.history[-6]) / self.history[-6]) * 100
            
            # Change since tracking started
            start_price = self.history[0]
            changes["change_since_start"] = ((current - start_price) / start_price) * 100
            
        return changes
    
    def calculate_stats(self) -> Dict[str, float]:
        """Calculate statistics based on price history"""
        stats = {}
        
        if len(self.history) > 1:
            stats["high"] = max(self.history)
            stats["low"] = min(self.history)
            stats["avg"] = sum(self.history) / len(self.history)
            stats["range"] = stats["high"] - stats["low"]
            
            # Percentage from high/low
            stats["pct_from_high"] = ((self.current_price - stats["high"]) / stats["high"]) * 100
            stats["pct_from_low"] = ((self.current_price - stats["low"]) / stats["low"]) * 100
            
        return stats