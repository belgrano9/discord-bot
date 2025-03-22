"""
Data models for stock price alerts.
Defines the structure of alerts and their properties.
"""

from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional, Literal, Dict, Any, List, Union


@dataclass
class PriceAlert:
    """Data model for a price alert"""
    ticker: str
    alert_type: Literal["percent", "price"]
    value: float
    reference_price: float
    created_at: datetime
    channel_id: int
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        data = asdict(self)
        # Convert datetime to string
        data["created_at"] = data["created_at"].strftime("%Y-%m-%d %H:%M:%S")
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PriceAlert":
        """Create from dictionary after deserialization"""
        # Convert string back to datetime
        if isinstance(data["created_at"], str):
            data["created_at"] = datetime.strptime(data["created_at"], "%Y-%m-%d %H:%M:%S")
        return cls(**data)
    
    def check_triggered(self, current_price: float) -> bool:
        """Check if the alert should be triggered based on current price"""
        if self.alert_type == "percent":
            percent_change = ((current_price - self.reference_price) / self.reference_price) * 100
            return percent_change >= self.value
        else:  # price alert
            if self.value > self.reference_price:
                return current_price >= self.value
            else:
                return current_price <= self.value
    
    def get_target_price(self) -> float:
        """Calculate the target price for this alert"""
        if self.alert_type == "percent":
            return self.reference_price * (1 + self.value / 100)
        else:
            return self.value