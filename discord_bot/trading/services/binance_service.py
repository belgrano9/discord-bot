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
        """ Place an order on Binance. """
        try:
            # Generate client_oid if not provided
            if not order.client_oid:
                order.client_oid = str(uuid.uuid4())

            # Validate the order (assuming this works)
            is_valid, error = order.validate()
            if not is_valid:
                return OrderResponse(success=False, error_message=error)

            # --- Build Base Parameters ---
            params = {
                "symbol": order.symbol,
                "side": order.side.value.upper(),  # Use .value
                "order_type": order.order_type.value.upper(), # Use .value
                "is_isolated": False,  # Hardcoded Cross, adjust if needed based on order.is_isolated
                "side_effect_type": "AUTO_BORROW_REPAY" if order.auto_borrow else "NO_SIDE_EFFECT",
                "new_client_order_id": order.client_oid
            }

            # --- Add Type-Specific Parameters ---
            if order.order_type == OrderType.MARKET:
                # Ensure 'quantity' is present, remove price/timeInForce
                if order.amount is None:
                    return OrderResponse(success=False, error_message="Amount is required for MARKET orders.")
                params["quantity"] = round(order.amount, 5) # Use amount for MARKET
                params.pop("price", None)
                params.pop("time_in_force", None)
                # Add quoteOrderQty if using funds? Check your logic
                # if order.use_funds and order.amount:
                #    params["quoteOrderQty"] = order.amount # Assuming amount means funds here
                #    params.pop("quantity", None)

            elif order.order_type == OrderType.LIMIT:
                # Ensure quantity, price, timeInForce are present
                if order.amount is None or order.price is None:
                    return OrderResponse(success=False, error_message="Amount and Price are required for LIMIT orders.")
                params["quantity"] = round(order.amount, 5)
                params["price"] = str(order.price)
                # Add time_in_force (assuming OrderRequest has it, defaulting to GTC)
                params["time_in_force"] = getattr(order, 'time_in_force', "GTC") or "GTC"
                params.pop("quoteOrderQty", None)
            else:
                return OrderResponse(success=False, error_message=f"Unsupported order type: {order.order_type}")


            # --- Make the API Call ---
            logger.debug(f"Calling create_margin_order with final params: {params}") # Add log here
            response = await self.api.create_margin_order(**params) # Pass the dictionary

            # --- Process Response ---
            if not response.get("error", False):
                order_data = response.get("data", {})
                logger.info(f"Order placed successfully! Order ID: {order_data.get('orderId')}")
                return OrderResponse(
                    success=True,
                    order_id=str(order_data.get("orderId")),
                    client_oid=order_data.get("clientOrderId"),
                    order_data=order_data
                )
            else:
                error_msg = response.get("msg", "Unknown error")
                logger.error(f"Order placement failed: {error_msg}")
                return OrderResponse(
                    success=False,
                    error_message=error_msg
                )

        except Exception as e:
            logger.exception(f"Error placing order: {str(e)}") # Use logger.exception for stack trace
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
        order_type: str, # STOP_LOSS, STOP_LOSS_LIMIT, TAKE_PROFIT, TAKE_PROFIT_LIMIT
        price: Optional[float] = None,
        is_isolated: bool = False,
        client_oid: Optional[str] = None,
        side_effect_type: str = "NO_SIDE_EFFECT" # <-- ADD THIS parameter with default
    ) -> Dict[str, Any]:
        """ Place a stop order on Binance. """
        try:
            if not client_oid:
                client_oid = str(uuid.uuid4())
            quantity = round(quantity, 5) # Keep rounding

            # Call the API layer's method, passing side_effect_type
            response = await self.api.create_stop_order( # Assuming create_stop_order passes it down
                symbol=symbol,
                side=side.upper(),
                order_type=order_type,
                quantity=quantity,
                stop_price=stop_price,
                price=price,
                is_isolated=is_isolated,
                new_client_order_id=client_oid,
                side_effect_type=side_effect_type # <-- PASS IT HERE
            )
            return response # Return the raw dict response

        except Exception as e:
            logger.error(f"Error placing stop order: {str(e)}")
            return {"error": True, "msg": f"Error placing stop order: {str(e)}"}



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