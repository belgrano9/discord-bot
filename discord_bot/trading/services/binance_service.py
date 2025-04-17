"""
Binance API service for trading.
Handles interaction with Binance API for orders and account data.
"""

import uuid
from typing import Dict, List, Any, Optional, Tuple
from loguru import logger
import asyncio
import json 
from api.binance_connector import AsyncBinanceConnectorAPI
from ..models.order import OrderRequest, OrderResponse, OrderSide, OrderType
from ..models.account import Asset, MarginAccount, TradeInfo
import time

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
                "is_isolated": order.is_isolated,
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

    async def get_isolated_margin_account_summary(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        """Fetches and parses key isolated margin account details."""
        try:
            logger.info(f"Fetching isolated margin account details for symbol: {symbol}")
            
            # This returns the isolated margin account data
            response = await self.api.get_isolated_margin_account(symbols=symbol)
            logger.debug(f"API response type: {type(response)}")
            logger.debug(f"API response structure: {json.dumps(response, indent=2) if response else 'None'}")
            
            # Check for API error
            if response.get("error", False):
                logger.error(f"API returned error: {response.get('msg')}")
                return {"error": True, "msg": response.get("msg", "Unknown error fetching isolated margin account")}
            
            # Log response structure to understand what we're working with
            has_data_key = "data" in response
            data_type = type(response.get("data", None)).__name__
            has_assets_in_data = False
            has_assets_in_root = False
            
            if has_data_key and isinstance(response["data"], dict):
                has_assets_in_data = "assets" in response["data"]
                logger.debug(f"Response has 'data' key: {has_data_key}, with type: {data_type}")
                logger.debug(f"Response has 'assets' in data: {has_assets_in_data}")
                if has_assets_in_data:
                    logger.debug(f"Number of assets in data: {len(response['data'].get('assets', []))}")
            
            has_assets_in_root = "assets" in response
            logger.debug(f"Response has 'assets' in root: {has_assets_in_root}")
            if has_assets_in_root:
                logger.debug(f"Number of assets in root: {len(response.get('assets', []))}")
            
            # Try to find assets in all possible locations
            account_data = []
            if has_data_key and isinstance(response["data"], dict):
                if "assets" in response["data"]:
                    account_data = response["data"]["assets"]
                    logger.debug("Found assets in response['data']['assets']")
                elif "data" in response["data"] and isinstance(response["data"]["data"], dict):
                    if "assets" in response["data"]["data"]:
                        account_data = response["data"]["data"]["assets"]
                        logger.debug("Found assets in response['data']['data']['assets']")
            elif "assets" in response:
                account_data = response["assets"]
                logger.debug("Found assets in response['assets']")
            
            # If still not found, extract raw response if available for debugging
            if not account_data and "raw_response" in response:
                logger.debug(f"Examining raw_response: {json.dumps(response['raw_response'], indent=2)}")
                if isinstance(response["raw_response"], dict):
                    if "assets" in response["raw_response"]:
                        account_data = response["raw_response"]["assets"]
                        logger.debug("Found assets in raw_response")
                
            # Check if we found any data
            if not account_data:
                all_keys = set()
                
                def collect_keys(d, prefix=""):
                    if isinstance(d, dict):
                        for k, v in d.items():
                            all_keys.add(f"{prefix}.{k}" if prefix else k)
                            collect_keys(v, f"{prefix}.{k}" if prefix else k)
                    elif isinstance(d, list) and d:
                        collect_keys(d[0], f"{prefix}[0]")
                
                collect_keys(response)
                logger.error(f"No isolated margin account data found. All keys in response: {sorted(all_keys)}")
                return {"error": True, "msg": "No isolated margin account data found", "all_response_keys": sorted(all_keys)}
            
            logger.info(f"Found {len(account_data)} isolated margin accounts")
            
            # Extract the totalAssetOfBtc values (could be in different locations)
            total_asset = "0"
            total_liability = "0"
            total_net_asset = "0"
            
            # Try different locations
            if has_data_key and isinstance(response["data"], dict):
                total_asset = response["data"].get("totalAssetOfBtc", "0")
                total_liability = response["data"].get("totalLiabilityOfBtc", "0")
                total_net_asset = response["data"].get("totalNetAssetOfBtc", "0")
            else:
                total_asset = response.get("totalAssetOfBtc", "0")
                total_liability = response.get("totalLiabilityOfBtc", "0")
                total_net_asset = response.get("totalNetAssetOfBtc", "0")
            
            # Create summary with all the data we found
            summary = {
                "error": False,
                "accounts": account_data,
                "total_asset_of_btc": total_asset,
                "total_liability_of_btc": total_liability,
                "total_net_asset_of_btc": total_net_asset,
            }
            
            logger.debug(f"Returning account summary with {len(account_data)} accounts")
            return summary
            
        except Exception as e:
            logger.exception(f"Unexpected error in get_isolated_margin_account_summary: {e}")
            import traceback
            return {
                "error": True, 
                "msg": f"Service error fetching isolated account summary: {str(e)}",
                "traceback": traceback.format_exc()
            }
   

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

    async def cancel_all_margin_orders(
        self,
        symbol: str,
        is_isolated: bool = False,
        tracking_id: str = None
    ) -> Dict[str, Any]:
        """
        Cancel all open margin orders for a specific symbol.
        
        Args:
            symbol: Trading pair symbol (e.g., BTCUSDT)
            is_isolated: Whether to cancel isolated margin orders
            tracking_id: Optional tracking ID for logging continuity
            
        Returns:
            API response including cancelled orders
        """
        tracking_id = tracking_id or f"auto_{int(time.time())}"
        logger.info(f"[CANCELALL:{tracking_id}] Service method started for {symbol} (isolated={is_isolated})")
        
        try:
            # First, check if there are any open orders for this symbol
            logger.info(f"[CANCELALL:{tracking_id}] Checking for open {symbol} margin orders")
            open_orders = await self.get_open_orders(symbol=symbol, is_isolated=is_isolated)
            
            # Log the open orders response
            logger.debug(f"[CANCELALL:{tracking_id}] get_open_orders response: {open_orders}")
            
            # If no orders or error getting orders, return appropriate response
            if open_orders.get("error", False):
                logger.warning(f"[CANCELALL:{tracking_id}] Error checking open orders: {open_orders.get('msg')}")
                return open_orders
            
            open_orders_list = open_orders.get("data", [])
            order_count = len(open_orders_list) if isinstance(open_orders_list, list) else "unknown"
            logger.info(f"[CANCELALL:{tracking_id}] Found {order_count} open orders to cancel")
            
            if not open_orders_list or len(open_orders_list) == 0:
                logger.info(f"[CANCELALL:{tracking_id}] No open {symbol} margin orders to cancel")
                return {"code": "200000", "data": [], "msg": "No open orders to cancel"}
            
            # Log sample of orders to be cancelled (first 3)
            if isinstance(open_orders_list, list) and len(open_orders_list) > 0:
                order_sample = open_orders_list[:3]
                logger.debug(f"[CANCELALL:{tracking_id}] Sample of orders to cancel: {order_sample}")
            
            # Prepare parameters
            params = {
                "symbol": symbol,
            }
            
            # Add isIsolated parameter only for isolated margin
            if is_isolated:
                params["isIsolated"] = "TRUE"
            
            logger.debug(f"[CANCELALL:{tracking_id}] Calling method 'margin_open_orders_cancellation' with params: {params}")
            
            # Try to directly access the client object's method
            try:
                # Get direct reference to the client object
                client = self.api.client.client
                
                # Log available attributes/methods on the client object
                client_attrs = dir(client)
                logger.debug(f"[CANCELALL:{tracking_id}] Client object attributes: {client_attrs}")
                
                # Check if the method exists
                has_method = hasattr(client, 'margin_open_orders_cancellation')
                logger.info(f"[CANCELALL:{tracking_id}] Client has 'margin_open_orders_cancellation' method: {has_method}")
                
                # Look for similar methods that might be used instead
                margin_methods = [attr for attr in client_attrs if 'margin' in attr.lower() and 'cancel' in attr.lower()]
                logger.info(f"[CANCELALL:{tracking_id}] Similar margin cancellation methods found: {margin_methods}")
                
                if has_method:
                    # Log method information if possible
                    import inspect
                    if inspect.ismethod(getattr(client, 'margin_open_orders_cancellation')):
                        method_info = inspect.signature(client.margin_open_orders_cancellation)
                        logger.debug(f"[CANCELALL:{tracking_id}] Method signature: {method_info}")
                    
                    # Call the method directly on the client
                    logger.info(f"[CANCELALL:{tracking_id}] Calling client.margin_open_orders_cancellation")
                    response = await asyncio.to_thread(client.margin_open_orders_cancellation, **params)
                    logger.debug(f"[CANCELALL:{tracking_id}] Direct method call response: {response}")
                    
                    return {"code": "200000", "data": response}
                else:
                    # If the exact method doesn't exist, try an alternative if available
                    if margin_methods:
                        alt_method_name = margin_methods[0]
                        logger.info(f"[CANCELALL:{tracking_id}] Trying alternative method: {alt_method_name}")
                        alt_method = getattr(client, alt_method_name)
                        try:
                            # Attempt to call the alternative method
                            alt_response = await asyncio.to_thread(alt_method, **params)
                            logger.debug(f"[CANCELALL:{tracking_id}] Alternative method response: {alt_response}")
                            return {"code": "200000", "data": alt_response}
                        except Exception as alt_error:
                            logger.error(f"[CANCELALL:{tracking_id}] Alternative method failed: {str(alt_error)}")
                    
                    # If we get here, no suitable method was found
                    logger.error(f"[CANCELALL:{tracking_id}] Method 'margin_open_orders_cancellation' not found on client object")
                    return {"error": True, "msg": "API method not available on client object", "available_methods": margin_methods}
                    
            except Exception as api_error:
                logger.error(f"[CANCELALL:{tracking_id}] Direct API method error: {str(api_error)}")
                # Try to get a more detailed traceback
                import traceback
                tb = traceback.format_exc()
                logger.error(f"[CANCELALL:{tracking_id}] API error traceback:\n{tb}")
                return {"error": True, "msg": f"API method error: {str(api_error)}", "traceback": tb}
                    
        except Exception as e:
            logger.exception(f"[CANCELALL:{tracking_id}] Unexpected error in cancel_all_margin_orders: {str(e)}")
            import traceback
            tb = traceback.format_exc()
            return {"error": True, "msg": f"Service error: {str(e)}", "traceback": tb}
    

    async def close_all_positions(self) -> Dict[str, Any]:
        """
        Close all active isolated margin positions.
        
        Returns:
            Dictionary containing results for each position closure attempt
        """
        logger.info("==== STARTING CLOSE ALL POSITIONS OPERATION ====")
        operation_id = f"close_all_{int(time.time())}"  # Generate unique operation ID for tracking
        logger.info(f"[{operation_id}] Operation started")
        
        results = {
            "success": [],
            "failed": [],
            "summary": {"total": 0, "succeeded": 0, "failed": 0}
        }
        
        try:
            # Step 1: Get all isolated margin accounts (positions)
            logger.info(f"[{operation_id}] Fetching all isolated margin accounts to identify positions")
            account_data = await self.get_isolated_margin_account_summary()
            
            if account_data.get("error", False):
                logger.error(f"[{operation_id}] Error fetching margin accounts: {account_data.get('msg')}")
                return {"error": True, "msg": f"Error fetching margin accounts: {account_data.get('msg')}"}
            
            accounts = account_data.get("accounts", [])
            logger.info(f"[{operation_id}] Found {len(accounts)} isolated margin accounts")
            logger.debug(f"[{operation_id}] Account symbols: {[account.get('symbol', 'N/A') for account in accounts]}")
            
            # Log count of accounts by status
            statuses = {}
            for account in accounts:
                status = account.get("marginLevelStatus", "Unknown")
                statuses[status] = statuses.get(status, 0) + 1
            logger.info(f"[{operation_id}] Account status breakdown: {statuses}")
            
            # Step 2: Identify active positions and close them
            position_count = 0
            for idx, account in enumerate(accounts):
                symbol = account.get("symbol")
                if not symbol:
                    logger.warning(f"[{operation_id}] Account #{idx+1} missing symbol: {account}")
                    continue
                    
                logger.debug(f"[{operation_id}] Processing account for {symbol} ({idx+1}/{len(accounts)})")
                
                # Get base and quote assets
                base_asset = account.get("baseAsset", {})
                quote_asset = account.get("quoteAsset", {})
                
                base_borrowed = float(base_asset.get("borrowed", "0"))
                base_total = float(base_asset.get("totalAsset", "0"))
                quote_borrowed = float(quote_asset.get("borrowed", "0"))
                quote_total = float(quote_asset.get("totalAsset", "0"))
                
                # Log the account balance details
                logger.debug(f"[{operation_id}] {symbol} Base asset ({base_asset.get('asset')}): Total={base_total}, Borrowed={base_borrowed}")
                logger.debug(f"[{operation_id}] {symbol} Quote asset ({quote_asset.get('asset')}): Total={quote_total}, Borrowed={quote_borrowed}")
                
                position_info = {
                    "symbol": symbol,
                    "base_asset": base_asset.get("asset"),
                    "quote_asset": quote_asset.get("asset")
                }
                
                results["summary"]["total"] += 1
                
                # Check for long position (holding base asset)
                if base_total > 0.00001:  # Small threshold to avoid dust
                    position_count += 1
                    # Prepare to sell base asset
                    logger.info(f"[{operation_id}] Found long position #{position_count} for {symbol}: selling {base_total} {base_asset.get('asset')}")
                    
                    position_info["position_type"] = "long"
                    position_info["size"] = base_total
                    
                    try:
                        # Log the order request details
                        logger.debug(f"[{operation_id}] Creating SELL market order for {symbol}: amount={base_total}")
                        
                        # Create market sell order
                        order_request = OrderRequest(
                            symbol=symbol,
                            side=OrderSide.SELL,
                            order_type=OrderType.MARKET,
                            amount=base_total,
                            price=None,
                            auto_borrow=False,
                            is_isolated=True
                        )
                        
                        # Log order request validation
                        is_valid, validation_error = order_request.validate()
                        if not is_valid:
                            logger.error(f"[{operation_id}] Order validation failed for {symbol}: {validation_error}")
                        
                        # Place the order
                        logger.info(f"[{operation_id}] Submitting SELL market order for {symbol}")
                        order_response = await self.place_order(order_request)
                        
                        if order_response.is_success:
                            position_info["order_id"] = order_response.order_id
                            position_info["status"] = "closed"
                            results["success"].append(position_info)
                            results["summary"]["succeeded"] += 1
                            
                            # Log detailed success info
                            logger.info(f"[{operation_id}] Successfully closed long position for {symbol}, order ID: {order_response.order_id}")
                            if order_response.order_data:
                                executed_qty = order_response.order_data.get("executedQty", "unknown")
                                executed_price = order_response.order_data.get("price", "market")
                                logger.debug(f"[{operation_id}] Order filled: {executed_qty} @ {executed_price}")
                        else:
                            position_info["error"] = order_response.error_message
                            position_info["status"] = "failed"
                            results["failed"].append(position_info)
                            results["summary"]["failed"] += 1
                            
                            # Log detailed error info
                            logger.error(f"[{operation_id}] Failed to close long position for {symbol}: {order_response.error_message}")
                            logger.debug(f"[{operation_id}] Full error response: {order_response.order_data}")
                            
                    except Exception as e:
                        logger.exception(f"[{operation_id}] Exception while closing long position for {symbol}: {str(e)}")
                        position_info["error"] = str(e)
                        position_info["status"] = "failed"
                        results["failed"].append(position_info)
                        results["summary"]["failed"] += 1
                
                # Check for short position (borrowed base asset)
                elif base_borrowed > 0.00001:
                    position_count += 1
                    # Prepare to buy back base asset
                    logger.info(f"[{operation_id}] Found short position #{position_count} for {symbol}: buying back {base_borrowed} {base_asset.get('asset')}")
                    
                    position_info["position_type"] = "short"
                    position_info["size"] = base_borrowed
                    
                    try:
                        # Log the order request details
                        logger.debug(f"[{operation_id}] Creating BUY market order for {symbol}: amount={base_borrowed}")
                        
                        # Create market buy order
                        order_request = OrderRequest(
                            symbol=symbol,
                            side=OrderSide.BUY,
                            order_type=OrderType.MARKET,
                            amount=base_borrowed,
                            price=None,
                            auto_borrow=False,
                            is_isolated=True
                        )
                        
                        # Log order request validation
                        is_valid, validation_error = order_request.validate()
                        if not is_valid:
                            logger.error(f"[{operation_id}] Order validation failed for {symbol}: {validation_error}")
                        
                        # Place the order
                        logger.info(f"[{operation_id}] Submitting BUY market order for {symbol}")
                        order_response = await self.place_order(order_request)
                        
                        if order_response.is_success:
                            position_info["order_id"] = order_response.order_id
                            position_info["status"] = "closed"
                            results["success"].append(position_info)
                            results["summary"]["succeeded"] += 1
                            
                            # Log detailed success info
                            logger.info(f"[{operation_id}] Successfully closed short position for {symbol}, order ID: {order_response.order_id}")
                            if order_response.order_data:
                                executed_qty = order_response.order_data.get("executedQty", "unknown")
                                executed_price = order_response.order_data.get("price", "market")
                                logger.debug(f"[{operation_id}] Order filled: {executed_qty} @ {executed_price}")
                        else:
                            position_info["error"] = order_response.error_message
                            position_info["status"] = "failed"
                            results["failed"].append(position_info)
                            results["summary"]["failed"] += 1
                            
                            # Log detailed error info
                            logger.error(f"[{operation_id}] Failed to close short position for {symbol}: {order_response.error_message}")
                            logger.debug(f"[{operation_id}] Full error response: {order_response.order_data}")
                            
                    except Exception as e:
                        logger.exception(f"[{operation_id}] Exception while closing short position for {symbol}: {str(e)}")
                        position_info["error"] = str(e)
                        position_info["status"] = "failed"
                        results["failed"].append(position_info)
                        results["summary"]["failed"] += 1
                else:
                    # No position for this symbol
                    logger.debug(f"[{operation_id}] No active position for {symbol} (base_total={base_total}, base_borrowed={base_borrowed})")
            
            # Log final summary
            logger.info(f"[{operation_id}] Position closure operation completed")
            logger.info(f"[{operation_id}] Summary: Attempted={results['summary']['total']}, Succeeded={results['summary']['succeeded']}, Failed={results['summary']['failed']}")
            
            if position_count == 0:
                logger.info(f"[{operation_id}] No active positions found to close")
            
            return results
        
        except Exception as e:
            logger.exception(f"[{operation_id}] Unexpected error in close_all_positions: {str(e)}")
            return {"error": True, "msg": f"Service error: {str(e)}"}
    
    
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