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
    STOP_LOSS = "stop_loss"
    STOP_LOSS_LIMIT = "stop_loss_limit"
    TAKE_PROFIT = "take_profit"
    TAKE_PROFIT_LIMIT = "take_profit_limit"


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
    stop_price: Optional[float] = None  # For stop orders
    
    def validate(self) -> tuple[bool, str]:
        """
        Validate the order request.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not self.symbol:
            return False, "Symbol is required"
            
        if self.amount <= 0:
            return False, "Amount must be positive"
            
        if self.order_type == OrderType.LIMIT and self.price is None:
            return False, "Price is required for limit orders"
            
        if self.order_type == OrderType.LIMIT and self.price <= 0:
            return False, "Price must be positive for limit orders"
            
        # Validate stop orders
        if self.order_type in [OrderType.STOP_LOSS, OrderType.STOP_LOSS_LIMIT, 
                              OrderType.TAKE_PROFIT, OrderType.TAKE_PROFIT_LIMIT]:
            if self.stop_price is None:
                return False, "Stop price is required for stop orders"
            
            if self.stop_price <= 0:
                return False, "Stop price must be positive"
                
            if "LIMIT" in self.order_type.value and self.price is None:
                return False, "Price is required for limit stop orders"
            
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