"""
Account data models for trading.
Defines the structure of account information.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional


@dataclass
class Asset:
    """Data for a single asset in an account"""
    currency: str
    total: float = 0.0
    available: float = 0.0
    borrowed: float = 0.0
    interest: float = 0.0
    borrow_enabled: bool = False
    repay_enabled: bool = False


@dataclass
class MarginAccount:
    """Data for a margin account"""
    symbol: str
    status: str
    debt_ratio: float = 0.0
    base_asset: Optional[Asset] = None
    quote_asset: Optional[Asset] = None
    total_assets: float = 0.0
    total_liabilities: float = 0.0
    
    @property
    def risk_level(self) -> str:
        """Get the risk level based on debt ratio"""
        ratio_pct = self.debt_ratio * 100
        
        if ratio_pct > 80:
            return "High"
        elif ratio_pct > 50:
            return "Medium"
        elif ratio_pct > 30:
            return "Moderate"
        else:
            return "Low"
    
    @property
    def risk_color(self) -> str:
        """Get emoji color indicator based on risk level"""
        ratio_pct = self.debt_ratio * 100
        
        if ratio_pct > 80:
            return "🔴"  # High risk
        elif ratio_pct > 50:
            return "🟠"  # Medium risk
        elif ratio_pct > 30:
            return "🟡"  # Moderate risk
        else:
            return "🟢"  # Low risk


@dataclass
class TradeInfo:
    """Data for a single trade/fill"""
    symbol: str
    side: str
    price: float
    size: float
    fee: float
    fee_currency: str
    timestamp: Optional[str] = None
    order_id: Optional[str] = None
    trade_id: Optional[str] = None
    trade_type: str = "MARGIN_ISOLATED_TRADE"
    
    @property
    def total_value(self) -> float:
        """Get the total value of the trade"""
        return self.price * self.size