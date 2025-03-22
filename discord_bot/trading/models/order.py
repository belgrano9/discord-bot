"""
Order data models for trading.
Defines the structure of orders and related data.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Any, Optional, Literal
from enum import Enum


class OrderSide(str, Enum):
    """Order side (buy/sell)"""
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    """Order type (market/limit)"""
    MARKET = "market"
    LIMIT = "limit"


@dataclass
class OrderRequest:
    """Data for creating a new order"""
    symbol: str
    side: OrderSide
    order_type: OrderType
    amount: float
    price: Optional[float] = None
    client_oid: Optional[str] = None
    is_isolated: bool = True
    auto_borrow: bool = False
    auto_repay: bool = False
    use_funds: bool = False  # If True, amount is interpreted as funds rather than size
    time_in_force: str = "GTC"  # Good Till Canceled
    
    def validate(self) -> tuple[bool, str]:
        """
        Validate the order request.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not self.symbol or not "-" in self.symbol:
            return False, "Invalid symbol format. Must be in format BASE-QUOTE (e.g., BTC-USDT)"
            
        if self.amount <= 0:
            return False, "Amount must be positive"
            
        if self.order_type == OrderType.LIMIT and self.price is None:
            return False, "Price is required for limit orders"
            
        if self.order_type == OrderType.LIMIT and self.price <= 0:
            return False, "Price must be positive for limit orders"
            
        return True, ""


@dataclass
class OrderResponse:
    """Data from a processed order"""
    success: bool
    order_id: Optional[str] = None
    client_oid: Optional[str] = None
    error_message: Optional[str] = None
    order_data: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_success(self) -> bool:
        """Whether the order was successful"""
        return self.success and self.order_id is not None