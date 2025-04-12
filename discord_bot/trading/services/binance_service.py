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
    
    
    async def place_oco_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        stop_price: float,
        stop_limit_price: Optional[float] = None,
        is_isolated: bool = False,
        auto_borrow: bool = False
    ) -> Dict[str, Any]:
        """
        Place a One-Cancels-the-Other (OCO) order on Binance.
        
        Args:
            symbol: Trading pair symbol (e.g., BTCUSDT)
            side: 'buy' or 'sell'  
            quantity: Quantity to trade
            price: Limit order price
            stop_price: Stop trigger price
            stop_limit_price: Price for stop limit (if None, uses market stop)
            is_isolated: Whether to use isolated margin
            auto_borrow: Whether to enable auto-borrowing
            
        Returns:
            Dictionary containing the OCO order response
        """
        order_id = f"oco_{uuid.uuid4().hex[:8]}"  # Generate short ID for logging
        logger.info(f"[OCO:{order_id}] Processing new OCO order request: {symbol} {side} quantity={quantity}")
    
        try:
            # Generate client order IDs
            list_client_order_id = uuid.uuid4().hex
            limit_client_order_id = uuid.uuid4().hex
            stop_client_order_id = uuid.uuid4().hex
                        
            logger.debug(f"[OCO:{order_id}] Generated client IDs: list={list_client_order_id}, limit={limit_client_order_id}, stop={stop_client_order_id}")
            
            # Determine side effect type based on auto_borrow
            side_effect_type = "AUTO_BORROW_REPAY" if auto_borrow else "NO_SIDE_EFFECT"
            logger.debug(f"[OCO:{order_id}] Side effect type: {side_effect_type} (auto_borrow={auto_borrow})")
            
            # Prepare params for the OCO order
            params = {
                "symbol": symbol,
                "side": side.upper(),
                "quantity": quantity,
                "price": price,
                "stop_price": stop_price,
                "is_isolated": is_isolated,
                "list_client_order_id": list_client_order_id,
                "limit_client_order_id": limit_client_order_id,
                "stop_client_order_id": stop_client_order_id,
                "side_effect_type": side_effect_type
            }
            
            # Add stop limit price if provided
            if stop_limit_price:
                params["stop_limit_price"] = stop_limit_price
                params["stop_limit_time_in_force"] = "GTC"
                
            logger.debug(f"[OCO:{order_id}] Request parameters prepared: {params}")
        
            # Call the API to create the OCO order
            logger.info(f"[OCO:{order_id}] Calling API method create_margin_oco_order")
            response = await self.api.create_margin_oco_order(**params)
            
            if not response.get("error", False):
                order_data = response.get("data", {})
                order_list_id = order_data.get("orderListId", "unknown")
                logger.info(f"[OCO:{order_id}] Order successfully placed! OrderListId: {order_list_id}")
                
                # Log individual orders if available
                if "orders" in order_data and isinstance(order_data["orders"], list):
                    for i, order in enumerate(order_data["orders"]):
                        logger.info(f"[OCO:{order_id}] Sub-order {i+1}: ID={order.get('orderId')}, type={order.get('type')}")
            else:
                error_msg = response.get("msg", "Unknown error")
                logger.error(f"[OCO:{order_id}] Order placement failed: {error_msg}")
                logger.debug(f"[OCO:{order_id}] Full error response: {response}")
            
            return response
            
        except Exception as e:
            logger.exception(f"[OCO:{order_id}] Unexpected error placing OCO order: {str(e)}")
            return {"error": True, "msg": f"Error placing OCO order: {str(e)}"}


    async def get_cross_margin_account_summary(self) -> Dict[str, Any]:
        """Fetches and parses key cross margin account details for estimation."""
        try:
            logger.debug("Fetching cross margin account details...")
            # This returns the {'code': ..., 'data': {...}} structure from AsyncBinanceConnectorAPI
            full_api_response_wrapped = await self.api.get_margin_account()
            api_response_wrapped = full_api_response_wrapped["data"]["data"]
            if full_api_response_wrapped:
                # (Remove or change back the forced log level)
                logger.debug(f"Content of actual_account_data to be parsed: {api_response_wrapped}")

                # --- Parse directly from the 'actual_account_data' variable ---
                margin_level_str = api_response_wrapped.get('marginLevel')
                total_asset_btc_str = api_response_wrapped.get('totalAssetOfBtc')
                total_liability_btc_str = api_response_wrapped.get('totalLiabilityOfBtc')
                total_net_asset_btc_str = api_response_wrapped.get('totalNetAssetOfBtc')

                # --- Check if parsing worked ---
                if margin_level_str and total_asset_btc_str and total_liability_btc_str:
                    try:
                        summary = {
                            "error": False,
                            "current_margin_level": float(margin_level_str),
                            "total_asset_btc": float(total_asset_btc_str),
                            "total_liability_btc": float(total_liability_btc_str),
                            "total_net_asset_btc": float(total_net_asset_btc_str) if total_net_asset_btc_str else None,
                        }
                        logger.info(f"Parsed margin summary: {summary}")
                        return summary
                    except (ValueError, TypeError) as parse_err:
                        logger.error(f"Error parsing margin account numeric fields: {parse_err}")
                        return {"error": True, "msg": "Failed to parse account data fields"}
                else:
                    # Log what was actually found (or None)
                    logger.warning(f"Values found in actual_account_data: marginLevel='{margin_level_str}', totalAssetOfBtc='{total_asset_btc_str}', totalLiabilityOfBtc='{total_liability_btc_str}'")
                    missing = [k for k, v in {
                        'marginLevel': margin_level_str,
                        'totalAssetOfBtc': total_asset_btc_str,
                        'totalLiabilityOfBtc': total_liability_btc_str
                        }.items() if not v]
                    logger.warning(f"Missing required fields ({', '.join(missing)}) in actual account data part of margin response.")
                    return {"error": True, "msg": f"Missing required fields ({', '.join(missing)}) in account response data"}
            else:
                # If actual_account_data is still None after checks
                logger.error(f"Could not determine account data structure from response: {full_api_response_wrapped}")
                return {"error": True, "msg": "Invalid or unrecognized structure in account response"}

        except Exception as e:
            logger.exception(f"Unexpected error in get_cross_margin_account_summary: {e}")
            return {"error": True, "msg": f"Service error fetching account summary: {str(e)}"}


    async def get_open_orders(self, symbol: Optional[str] = None, is_isolated: Optional[bool] = None) -> Dict[str, Any]:
        """
        Fetch open margin orders from the Binance API.

        Args:
            symbol: Optional symbol filter.
            is_isolated: Optional isolated margin filter.

        Returns:
            A dictionary containing the list of orders under the 'data' key on success,
            or an error dictionary {'error': True, 'msg': ...} on failure.
        """
        try:
            logger.debug(f"Service call: get_open_orders(symbol={symbol}, is_isolated={is_isolated})")
            # Call the corresponding method in the API connector layer
            response = await self.api.get_open_margin_orders(symbol=symbol, is_isolated=is_isolated)

            # The API layer already standardizes the response format
            if response.get("error"):
                logger.warning(f"Error fetching open orders via service: {response.get('msg')}")
                return response # Return the error dict directly
            else:
                logger.info(f"Service successfully retrieved open orders data.")
                return response # Return the success dict {'code': ..., 'data': [...]}

        except Exception as e:
            logger.exception(f"Unexpected error in BinanceService.get_open_orders: {e}")
            return {"error": True, "msg": f"Service layer error fetching open orders: {str(e)}"}

    def _format_timestamp(self, timestamp_ms: Optional[int]) -> Optional[str]:
        """Format a timestamp in milliseconds to a readable string"""
        # Ensure this helper is still here if needed for formatting below
        if not timestamp_ms:
            return None
        try:
            from datetime import datetime, timezone # Make sure timezone is imported if using UTC
            timestamp_sec = int(timestamp_ms) / 1000  # Convert ms to seconds
            dt = datetime.fromtimestamp(timestamp_sec, tz=timezone.utc) # Assume UTC
            return dt.strftime("%Y-%m-%d %H:%M:%S %Z") # Example format
        except Exception as e:
            logger.warning(f"Could not format timestamp {timestamp_ms}: {e}")
            return str(timestamp_ms)