"""
Binance API service for trading.
Handles interaction with Binance API for orders and account data.
"""

import uuid
from typing import Dict, List, Any, Optional, Tuple
from loguru import logger

from api.binance_connector import AsyncBinanceConnectorAPI
from ..models.order import OrderRequest, OrderResponse, OrderSide, OrderType
from ..models.account import Asset, MarginAccount, TradeInfo


class BinanceService:
    """Service for interacting with Binance API"""
    
    def __init__(self):
        """Initialize the Binance service"""
        self.api = AsyncBinanceConnectorAPI()
        logger.debug("Initialized BinanceService")
    
    async def place_order(self, order: OrderRequest) -> OrderResponse:
        """
        Place an order on Binance.
        
        Args:
            order: Order request data
            
        Returns:
            Order response with result
        """
        try:
            # Generate client_oid if not provided
            if not order.client_oid:
                order.client_oid = str(uuid.uuid4())
                
            # Validate the order
            is_valid, error = order.validate()
            if not is_valid:
                return OrderResponse(
                    success=False,
                    error_message=error
                )
            
            # Convert order side to Binance format (must be uppercase)
            side = order.side.value.upper()
            
            # Convert order type to Binance format
            order_type = order.order_type.value.upper()
            
            # Round quantity to 5 decimal places
            quantity = round(order.amount, 5)
            
            # Log the order request
            logger.info(f"Placing {order_type} {side} order for {order.symbol}: {quantity} @ {order.price if order.price else 'market price'}")
            
            # Use side effect type for auto-borrow if requested
            side_effect_type = "AUTO_BORROW_REPAY" if order.auto_borrow else "NO_SIDE_EFFECT"
            
            if order.order_type == OrderType.MARKET:
                # Market order
                response = await self.api.create_margin_order(
                    symbol=order.symbol,
                    side=side,
                    order_type=order_type,
                    quantity=quantity,
                    is_isolated=order.is_isolated,
                    side_effect_type=side_effect_type,
                    new_client_order_id=order.client_oid
                )
            else:
                # Limit order
                response = await self.api.create_margin_order(
                    symbol=order.symbol,
                    side=side,
                    order_type=order_type,
                    quantity=quantity,
                    price=order.price,
                    time_in_force=order.time_in_force,
                    is_isolated=order.is_isolated,
                    side_effect_type=side_effect_type,
                    new_client_order_id=order.client_oid
                )
                        
            # Check if the order was successful
            if not response.get("error", False):
                order_data = response.get("data", {})
                # Log success
                logger.info(f"Order placed successfully! Order ID: {order_data.get('orderId')}")
                return OrderResponse(
                    success=True,
                    order_id=str(order_data.get("orderId")),
                    client_oid=order_data.get("clientOrderId"),
                    order_data=order_data
                )
            else:
                # Handle error response
                error_msg = response.get("msg", "Unknown error")
                logger.error(f"Order placement failed: {error_msg}")
                return OrderResponse(
                    success=False,
                    error_message=error_msg
                )
                
        except Exception as e:
            logger.error(f"Error placing order: {str(e)}")
            return OrderResponse(
                success=False,
                error_message=f"Error placing order: {str(e)}"
            )
    
    async def place_stop_order(
        self,
        symbol: str,
        side: str,
        stop_price: float,
        quantity: float,
        order_type: str = "STOP_LOSS",
        price: Optional[float] = None,
        is_isolated: bool = False,
        client_oid: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Place a stop order on Binance.
        
        Args:
            symbol: Trading pair symbol (e.g., BTCUSDT)
            side: 'BUY' or 'SELL'
            stop_price: The trigger price
            quantity: Quantity to buy/sell (rounded to 5 decimals)
            order_type: 'STOP_LOSS', 'STOP_LOSS_LIMIT', 'TAKE_PROFIT', 'TAKE_PROFIT_LIMIT'
            price: Price for limit versions of stop orders
            is_isolated: Whether to use isolated margin
            client_oid: Client-generated order ID
            
        Returns:
            Order response
        """
        try:
            # Generate client_oid if not provided
            if not client_oid:
                client_oid = str(uuid.uuid4())
            
            # Round quantity to 5 decimal places
            quantity = round(quantity, 5)
                
            # Place the order via the API
            response = await self.api.create_stop_order(
                symbol=symbol,
                side=side.upper(),
                order_type=order_type,
                quantity=quantity,
                stop_price=stop_price,
                price=price,
                is_isolated=is_isolated,
                new_client_order_id=client_oid
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Error placing stop order: {str(e)}")
            return {"error": True, "msg": f"Error placing stop order: {str(e)}"}

    async def get_margin_account(self, symbol: str) -> Optional[MarginAccount]:
        """
        Get isolated margin account data.
        
        Args:
            symbol: Trading pair symbol
            
        Returns:
            Margin account data or None if failed
        """
        try:
            result = await self.api.get_isolated_margin_account(symbols=symbol)
            
            if result.get("error", False):
                error_msg = result.get("msg", "Unknown error")
                logger.warning(f"Failed to get margin account: {error_msg}")
                return None
                
            # Extract account data - structure differs from KuCoin
            assets = result.get("data", {}).get("assets", [])
            
            if not assets:
                logger.warning(f"No margin account data found for {symbol}")
                return None
                
            # Find the asset that matches the requested symbol
            asset_info = None
            for asset in assets:
                if asset.get("symbol") == symbol:
                    asset_info = asset
                    break
                    
            if not asset_info:
                logger.warning(f"No margin account data found for {symbol}")
                return None
                
            # Create base asset
            base_asset_data = asset_info.get("baseAsset", {})
            base_asset = Asset(
                currency=base_asset_data.get("asset", "Unknown"),
                total=float(base_asset_data.get("totalAsset", 0)),
                available=float(base_asset_data.get("free", 0)),
                borrowed=float(base_asset_data.get("borrowed", 0)),
                interest=float(base_asset_data.get("interest", 0)),
                borrow_enabled=True,  # Binance doesn't provide this directly
                repay_enabled=True    # Binance doesn't provide this directly
            )
            
            # Create quote asset
            quote_asset_data = asset_info.get("quoteAsset", {})
            quote_asset = Asset(
                currency=quote_asset_data.get("asset", "Unknown"),
                total=float(quote_asset_data.get("totalAsset", 0)),
                available=float(quote_asset_data.get("free", 0)),
                borrowed=float(quote_asset_data.get("borrowed", 0)),
                interest=float(quote_asset_data.get("interest", 0)),
                borrow_enabled=True,  # Binance doesn't provide this directly
                repay_enabled=True    # Binance doesn't provide this directly
            )
            
            # Create margin account
            return MarginAccount(
                symbol=symbol,
                status="ACTIVATED",  # Binance uses different status indicators
                debt_ratio=float(asset_info.get("marginRatio", 0)),
                base_asset=base_asset,
                quote_asset=quote_asset,
                total_assets=float(asset_info.get("netAsset", 0)),
                total_liabilities=float(
                    float(base_asset_data.get("borrowed", 0)) + 
                    float(base_asset_data.get("interest", 0)) +
                    float(quote_asset_data.get("borrowed", 0)) + 
                    float(quote_asset_data.get("interest", 0))
                )
            )
            
        except Exception as e:
            logger.error(f"Error getting margin account for {symbol}: {str(e)}")
            return None
    
    async def get_recent_trades(
        self, 
        symbol: str = None, 
        limit: int = 20
    ) -> List[TradeInfo]:
        """
        Get recent trades.
        
        Args:
            symbol: Trading pair symbol (optional)
            limit: Maximum number of trades to return
            
        Returns:
            List of trade information
        """
        try:
            # Binance requires symbol for this endpoint
            if not symbol:
                logger.warning("Symbol is required for getting trade history on Binance")
                return []
                
            # Get margin trades from Binance
            response = await self.api.client._run_client_method(
                'margin_my_trades', 
                symbol=symbol, 
                limit=limit,
                isIsolated="TRUE"  # For isolated margin
            )
            
            if isinstance(response, dict) and response.get("error", False):
                error_msg = response.get("msg", "Unknown error")
                logger.warning(f"Failed to get trade history: {error_msg}")
                return []
                
            # Convert to TradeInfo objects
            trade_info_list = []
            for trade in response:
                try:
                    # Convert Binance trade format to our TradeInfo format
                    trade_info = TradeInfo(
                        symbol=symbol,
                        side=trade.get("isBuyer", False) and "buy" or "sell",
                        price=float(trade.get("price", 0)),
                        size=float(trade.get("qty", 0)),
                        fee=float(trade.get("commission", 0)),
                        fee_currency=trade.get("commissionAsset", ""),
                        timestamp=self._format_timestamp(trade.get("time")),
                        order_id=str(trade.get("orderId")),
                        trade_id=str(trade.get("id")),
                        trade_type="MARGIN_ISOLATED_TRADE"
                    )
                    trade_info_list.append(trade_info)
                except Exception as e:
                    logger.warning(f"Error processing trade item: {str(e)}")
                    
            return trade_info_list
            
        except Exception as e:
            logger.error(f"Error getting trade history: {str(e)}")
            return []
    
    async def cancel_order(self, order_id: str, symbol: str) -> Tuple[bool, str]:
        """
        Cancel an order by ID.
        
        Args:
            order_id: Order ID to cancel
            symbol: Trading pair symbol (required by Binance)
            
        Returns:
            Tuple of (success, message)
        """
        try:
            # Binance requires symbol for cancellation
            result = await self.api.cancel_order(
                symbol=symbol,
                order_id=int(order_id)
            )
            
            if not result.get("error", False):
                return True, f"Order {order_id} cancelled successfully"
            else:
                error_msg = result.get("msg", "Unknown error")
                return False, f"Failed to cancel order: {error_msg}"
                
        except Exception as e:
            logger.error(f"Error cancelling order {order_id}: {str(e)}")
            return False, f"Error cancelling order: {str(e)}"
    
    def _format_timestamp(self, timestamp_ms: Optional[int]) -> Optional[str]:
        """Format a timestamp in milliseconds to a readable string"""
        if not timestamp_ms:
            return None
            
        try:
            from datetime import datetime
            timestamp_sec = int(timestamp_ms) / 1000  # Convert ms to seconds
            dt = datetime.fromtimestamp(timestamp_sec)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except:
            return str(timestamp_ms)