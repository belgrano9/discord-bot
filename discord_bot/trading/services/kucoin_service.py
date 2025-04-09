"""
KuCoin API service for trading.
Handles interaction with KuCoin API for orders and account data.
"""

import uuid
from typing import Dict, List, Any, Optional, Tuple
from loguru import logger
from discord.ext import commands
import asyncio

from api.kucoin import AsyncKucoinAPI
from ..models.order import OrderRequest, OrderResponse, OrderSide, OrderType
from ..models.account import Asset, MarginAccount, TradeInfo


class KuCoinService:
    """Service for interacting with KuCoin API"""
    
    def __init__(self):
        """Initialize the KuCoin service"""
        self.api = AsyncKucoinAPI()
        logger.debug("Initialized KuCoinService")
            
    async def place_order(self, order: OrderRequest) -> OrderResponse:
        """
        Place an order on KuCoin.
        
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
            
            # Log the order request
            logger.info(f"Placing {order.order_type.value} {order.side.value} order for {order.symbol}: {order.amount} @ {order.price if order.price else 'market price'}")
            
            # Use v3 API only for borrowing/short selling
            # Use v1 API for all normal orders (buying and selling existing assets)
            if order.auto_borrow:
                logger.debug(f"Using v3 API for borrowing/short selling")
                # Use v3 API for borrowing (short selling)
                if order.order_type == OrderType.LIMIT:
                    # Limit order
                    response = await self.api.add_margin_order(
                        symbol=order.symbol,
                        side=order.side.value,
                        client_oid=order.client_oid,
                        order_type=order.order_type.value,
                        price=str(order.price),
                        size=str(order.amount),
                        is_isolated=order.is_isolated,
                        auto_borrow=order.auto_borrow,
                        auto_repay=order.auto_repay,
                        time_in_force=order.time_in_force
                    )
                else:  # market order
                    response = await self.api.add_margin_order(
                        symbol=order.symbol,
                        side=order.side.value,
                        client_oid=order.client_oid,
                        order_type=order.order_type.value,
                        size=str(order.amount),  # Use amount as size
                        is_isolated=order.is_isolated,
                        auto_borrow=order.auto_borrow,
                        auto_repay=order.auto_repay
                    )
            else:
                logger.debug(f"Using v1 API for normal {order.side.value} order")
                # Use v1 API for normal buying and selling
                response = await self.api.add_margin_order_v1(
                    symbol=order.symbol,
                    side=order.side.value,
                    client_oid=order.client_oid,
                    order_type=order.order_type.value,
                    price=str(order.price) if order.price else None,
                    size=str(order.amount) if not order.use_funds else None,
                    funds=str(order.amount) if order.use_funds else None,
                    margin_model="isolated" if order.is_isolated else "cross",
                    auto_borrow=order.auto_borrow,
                    auto_repay=order.auto_repay,
                    time_in_force=order.time_in_force
                )
                        
            # Check if the order was successful
            if response.get("code") == "200000":
                order_data = response.get("data", {})
                # Log success
                logger.info(f"Order placed successfully! Order ID: {order_data.get('orderId')}")
                return OrderResponse(
                    success=True,
                    order_id=order_data.get("orderId"),
                    client_oid=order_data.get("clientOid"),
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
        
    async def place_full_order(self, ctx: commands.Context, order: OrderRequest) -> OrderResponse:
        """
        Place an order on KuCoin and set up stop orders with monitoring.
        
        Args:
            ctx: Discord context
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
            
            # Log the order request
            logger.info(f"Placing {order.order_type.value} {order.side.value} order for {order.symbol}: {order.amount} @ {order.price if order.price else 'market price'}")
            
            # Use appropriate API endpoint based on order type
            if order.auto_borrow:
                logger.debug(f"Using v3 API for borrowing/short selling")
                # Use v3 API for borrowing (short selling)
                if order.order_type == OrderType.LIMIT:
                    # Limit order
                    response = await self.api.add_margin_order(
                        symbol=order.symbol,
                        side=order.side.value,
                        client_oid=order.client_oid,
                        order_type=order.order_type.value,
                        price=str(order.price),
                        size=str(order.amount),
                        is_isolated=order.is_isolated,
                        auto_borrow=order.auto_borrow,
                        auto_repay=order.auto_repay,
                        time_in_force=order.time_in_force
                    )
                else:  # market order
                    response = await self.api.add_margin_order(
                        symbol=order.symbol,
                        side=order.side.value,
                        client_oid=order.client_oid,
                        order_type=order.order_type.value,
                        size=str(order.amount),  # Use amount as size
                        is_isolated=order.is_isolated,
                        auto_borrow=order.auto_borrow,
                        auto_repay=order.auto_repay
                    )
            else:
                logger.debug(f"Using v1 API for normal {order.side.value} order")
                # Use v1 API for normal buying and selling
                response = await self.api.add_margin_order_v1(
                    symbol=order.symbol,
                    side=order.side.value,
                    client_oid=order.client_oid,
                    order_type=order.order_type.value,
                    price=str(order.price) if order.price else None,
                    size=str(order.amount) if not order.use_funds else None,
                    funds=str(order.amount) if order.use_funds else None,
                    margin_model="isolated" if order.is_isolated else "cross",
                    auto_borrow=order.auto_borrow,
                    auto_repay=order.auto_repay,
                    time_in_force=order.time_in_force
                )
                        
            # Check if the order was successful
            if response.get("code") == "200000":
                order_data = response.get("data", {})
                # Log success
                logger.info(f"Order placed successfully! Order ID: {order_data.get('orderId')}")
                
                # Wait for the trade to be processed in the system
                await asyncio.sleep(2)  # Add a 2-second delay
                
                # Get the TradeInspector cog and call inspect_last_trade
                try:
                    trade_inspector = ctx.bot.get_cog("TradeInspector")
                    if trade_inspector:
                        # This will place and monitor stop orders
                        await trade_inspector.inspect_last_trade(ctx, order.symbol)
                        logger.info(f"Triggered trade inspection for {order.symbol}")
                    else:
                        logger.warning("TradeInspector cog not found")
                except Exception as e:
                    logger.error(f"Failed to trigger trade inspection: {str(e)}")

                # Return the original order response
                return OrderResponse(
                    success=True,
                    order_id=order_data.get("orderId"),
                    client_oid=order_data.get("clientOid"),
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
        stop_price: str,
        order_type: str = "limit",
        price: Optional[str] = None,
        size: Optional[str] = None,
        funds: Optional[str] = None,
        stop_type: str = "loss",
        client_oid: Optional[str] = None,
        trade_type: str = "MARGIN_ISOLATED_TRADE",
        remark: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Place a stop order on KuCoin.
        
        Args:
            symbol: Trading pair symbol (e.g., BTC-USDT)
            side: 'buy' or 'sell'
            stop_price: The trigger price
            order_type: Order type - 'limit' or 'market'
            price: Price for limit orders
            size: Quantity to buy/sell
            funds: Funds to use (for market orders, alternative to size)
            stop_type: 'loss' or 'entry'
            client_oid: Client-generated order ID
            trade_type: Type of trading - 'TRADE', 'MARGIN_TRADE', 'MARGIN_ISOLATED_TRADE'
            remark: Order remarks
            
        Returns:
            Order response
        """
        try:
            # Generate client_oid if not provided
            if not client_oid:
                client_oid = str(uuid.uuid4())
                
            # Place the order via the API
            response = await self.api.add_stop_order(
                symbol=symbol,
                side=side,
                stop_price=stop_price,
                stop_type=stop_type,
                order_type=order_type,
                price=price,
                size=size,
                funds=funds,
                client_oid=client_oid,
                trade_type=trade_type,
                remark=remark or "Bot stop order"
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Error placing stop order: {str(e)}")
            return {"code": "999999", "msg": f"Error placing stop order: {str(e)}"}

    async def get_margin_account(self, symbol: str) -> Optional[MarginAccount]:
        """
        Get isolated margin account data.
        
        Args:
            symbol: Trading pair symbol
            
        Returns:
            Margin account data or None if failed
        """
        try:
            result = await self.api.get_isolated_margin_accounts(symbol=symbol)
            
            if not result or result.get("code") != "200000":
                error_msg = result.get("msg", "Unknown error") if result else "No response"
                logger.warning(f"Failed to get margin account: {error_msg}")
                return None
                
            account_data = result.get("data", {})
            assets = account_data.get("assets", [])
            
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
                currency=base_asset_data.get("currency", "Unknown"),
                total=float(base_asset_data.get("total", 0)),
                available=float(base_asset_data.get("available", 0)),
                borrowed=float(base_asset_data.get("borrowed", 0)),
                interest=float(base_asset_data.get("interest", 0)),
                borrow_enabled=base_asset_data.get("borrowEnabled", False),
                repay_enabled=base_asset_data.get("repayEnabled", False)
            )
            
            # Create quote asset
            quote_asset_data = asset_info.get("quoteAsset", {})
            quote_asset = Asset(
                currency=quote_asset_data.get("currency", "Unknown"),
                total=float(quote_asset_data.get("total", 0)),
                available=float(quote_asset_data.get("available", 0)),
                borrowed=float(quote_asset_data.get("borrowed", 0)),
                interest=float(quote_asset_data.get("interest", 0)),
                borrow_enabled=quote_asset_data.get("borrowEnabled", False),
                repay_enabled=quote_asset_data.get("repayEnabled", False)
            )
            
            # Create margin account
            return MarginAccount(
                symbol=symbol,
                status=asset_info.get("status", "Unknown"),
                debt_ratio=float(asset_info.get("debtRatio", 0)),
                base_asset=base_asset,
                quote_asset=quote_asset,
                total_assets=float(account_data.get("totalAssetOfQuoteCurrency", 0)),
                total_liabilities=float(account_data.get("totalLiabilityOfQuoteCurrency", 0))
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
            trades_data = await self.api.get_filled_list(
                symbol=symbol,
                limit=limit,
                trade_type="MARGIN_ISOLATED_TRADE"
            )
            
            if not trades_data or trades_data.get("code") != "200000":
                error_msg = trades_data.get("msg", "Unknown error") if trades_data else "No response"
                logger.warning(f"Failed to get trade history: {error_msg}")
                return []
                
            # Extract the trade items
            trades = trades_data.get("data", {}).get("items", [])
            
            # Convert to TradeInfo objects
            trade_info_list = []
            for trade in trades:
                try:
                    trade_info = TradeInfo(
                        symbol=trade.get("symbol", "Unknown"),
                        side=trade.get("side", "unknown"),
                        price=float(trade.get("price", 0)),
                        size=float(trade.get("size", 0)),
                        fee=float(trade.get("fee", 0)),
                        fee_currency=trade.get("feeCurrency", ""),
                        timestamp=self._format_timestamp(trade.get("createdAt")),
                        order_id=trade.get("orderId"),
                        trade_id=trade.get("tradeId"),
                        trade_type=trade.get("tradeType", "MARGIN_ISOLATED_TRADE")
                    )
                    trade_info_list.append(trade_info)
                except Exception as e:
                    logger.warning(f"Error processing trade item: {str(e)}")
                    
            return trade_info_list
            
        except Exception as e:
            logger.error(f"Error getting trade history: {str(e)}")
            return []
    
    async def cancel_order(self, order_id: str) -> Tuple[bool, str]:
        """
        Cancel an order by ID.
        
        Args:
            order_id: Order ID to cancel
            
        Returns:
            Tuple of (success, message)
        """
        try:
            result = await self.api.cancel_order_by_id(order_id)
            
            if result and result.get("code") == "200000":
                cancelled_id = result.get("data")
                return True, f"Order {cancelled_id} cancelled successfully"
            else:
                error_msg = result.get("msg", "Unknown error") if result else "No response"
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