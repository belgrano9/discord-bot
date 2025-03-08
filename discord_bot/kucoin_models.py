from enum import Enum
from dataclasses import dataclass
from typing import Optional, List

class Stp(Enum):
    """Self Trade Prevention is divided into strategies: CN, CO, CB, and DC"""
    CB = "CB"
    CN = "CN"
    CO = "CO"
    DC = "DC"

class TimeInForce(Enum):
    """Time in force"""
    FOK = "FOK"
    GTC = "GTC"
    GTT = "GTT"
    IOC = "IOC"

class TypeEnum(Enum):
    """Specify if the order is a 'limit' order or 'market' order."""
    LIMIT = "limit"
    MARKET = "market"

@dataclass
class Item:
    """Order item with all its properties"""
    active: bool
    cancel_after: int
    cancel_exist: bool
    cancelled_funds: str
    cancelled_size: str
    channel: str
    client_oid: str
    created_at: int
    deal_funds: str
    deal_size: str
    fee: str
    fee_currency: str
    funds: str
    hidden: bool
    iceberg: bool
    id: str
    in_order_book: bool
    last_updated_at: int
    op_type: str
    post_only: bool
    price: str
    remain_funds: str
    remain_size: str
    side: str
    size: str
    stop_price: str
    stop_triggered: bool
    symbol: str
    tax: str
    time_in_force: str  # Changed from TimeInForce to str for easier parsing
    trade_type: str
    type: str  # Changed from TypeEnum to str for easier parsing
    visible_size: str
    remark: Optional[str] = None
    stop: Optional[str] = None
    stp: Optional[str] = None  # Changed from Stp to str for easier parsing
    tags: Optional[str] = None

@dataclass
class Data:
    items: List[Item]
    last_id: int

@dataclass
class ApidogModel:
    code: str
    data: Data