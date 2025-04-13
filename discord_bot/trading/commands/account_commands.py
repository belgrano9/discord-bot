# account_commands.py:

"""
Account related commands.
Handles fetching account balance and other info.
"""

import discord
from discord.ext import commands
from loguru import logger
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple

# Import the service and potentially API key error
from ..services.binance_service import BinanceService

class AccountCommands:
    """Command handlers for account information"""

    def __init__(self, binance_service: BinanceService):
        """
        Initialize account commands.

        Args:
            binance_service: The BinanceService instance to use for API calls.
        """
        self.binance_service = binance_service
        logger.debug("Initialized AccountCommands")

    async def handle_balance(self, ctx: commands.Context, margin_type: str = "isolated", symbol: Optional[str] = None):
        """
        Handle the balance command: Fetch and display margin account summary.

        Args:
            ctx: Discord context
            margin_type: Type of margin account ("isolated" or "cross")
            symbol: Trading pair symbol for isolated margin (optional)
        """
        # Security check remains the same
        required_role = discord.utils.get(ctx.guild.roles, name="Trading-Authorized") 
        if required_role is None or required_role not in ctx.author.roles:
            await ctx.send("⛔ You don't have permission to view account balances.")
            return

        logger.info(f"User {ctx.author} requested {margin_type} margin account balance with symbol={symbol}")
        await ctx.send(f"⏳ Fetching {margin_type} margin account balance...", delete_after=5.0)


        try:
            if margin_type.lower() == "cross":
                # Existing cross margin implementation
                summary_data = await self.binance_service.get_cross_margin_account_summary()
                
                # Process cross margin response...
                # [existing code for cross margin]
                
            else:  # isolated margin
                logger.info(f"Calling get_isolated_margin_account_summary with symbol={symbol}")
                summary_data = await self.binance_service.get_isolated_margin_account_summary(symbol)

                logger.info(f"get_isolated_margin_account_summary returned: {summary_data}")
                
                # Log keys in the response to help debugging
                if isinstance(summary_data, dict):
                    logger.debug(f"Response keys: {list(summary_data.keys())}")
                    if "accounts" in summary_data:
                        logger.debug(f"Found {len(summary_data['accounts'])} accounts in response")
                        if summary_data['accounts']:
                            logger.debug(f"First account keys: {list(summary_data['accounts'][0].keys())}")
                    if "error" in summary_data:
                        logger.debug(f"Error status: {summary_data['error']}")
                    if "all_response_keys" in summary_data:
                        logger.debug(f"All response keys found: {summary_data['all_response_keys']}")
                


                if not summary_data.get("error", False):
                    # Create an embed for isolated margin
                    embed = discord.Embed(
                        title="📊 Binance Isolated Margin Balance",
                        color=discord.Color.blue(),
                        timestamp=datetime.now()
                    )
                    
                    # Get the accounts list
                    accounts = summary_data.get("accounts", [])
                    
                    logger.info(accounts)

                    if not accounts:
                        embed.description = "No isolated margin accounts found."
                    else:
                        # Add total values
                        total_btc_value = float(accounts[0]["baseAsset"]["totalAsset"])
                        total_liability = float(accounts[0]["baseAsset"]['borrowed'])

                        total_usdc_value =  float(accounts[0]["quoteAsset"]["totalAsset"])
                        total_usdc_liability = float(accounts[0]["quoteAsset"]["borrowed"])

                        embed.add_field(
                            name="Total Assets (BTC)",
                            value=f"{total_btc_value:.8f} BTC",
                            inline=True
                        )
                        
                        embed.add_field(
                            name="Total Liabilities (BTC)",
                            value=f"{total_liability:.8f} BTC",
                            inline=True
                        )

                        embed.add_field(
                            name="Total Assets (USDC)",
                            value=f"{total_usdc_value:.8f} USDC",
                            inline=True
                        )
                        
                        embed.add_field(
                            name="Total Liabilities (USDC)",
                            value=f"{total_usdc_liability:.8f} USDC",
                            inline=True
                        )
                        
                        for account in accounts[:10]:
                            symbol = account.get("symbol", "Unknown")
                            base_asset = account.get("baseAsset", {})
                            quote_asset = account.get("quoteAsset", {})
                            
                            # Get margin level or ratio (different field names possible)
                            margin_level = account.get("marginLevel", account.get("marginRatio", "0"))
                            margin_status = account.get("marginLevelStatus", "Unknown")
                            
                            # Get liquidation price if available
                            liquidate_price = account.get("liquidatePrice", "N/A")
                            
                            field_value = (
                                f"Status: {account.get('marginLevelStatus', 'Unknown')}\n"
                                f"Margin Level: {margin_level}\n"
                                f"Base: {base_asset.get('borrowed', '0')} {base_asset.get('asset', '')}\n"
                                f"Quote: {quote_asset.get('borrowed', '0')} {quote_asset.get('asset', '')}\n"
                                f"Liquidate Price: {liquidate_price}"
                            )
                            
                            embed.add_field(
                                name=f"{symbol}",
                                value=field_value,
                                inline=True
                            )
                    
                    embed.set_footer(text=f"Requested by {ctx.author.display_name}", icon_url=ctx.author.avatar.url if ctx.author.avatar else None)
                    logger.info(f"Successfully fetched and formatted isolated margin balance for {ctx.author}.")
                    await ctx.send(embed=embed)
                else:
                    # Handle error reported by the service
                    error_msg = summary_data.get("msg", "Unknown error fetching/parsing balance.")
                    logger.error(f"Service layer failed to get/parse isolated balance for {ctx.author}: {error_msg}")
                    embed = discord.Embed(
                        title="❌ Error Fetching Balance",
                        description=f"Could not retrieve or process isolated margin account balance.\n```\n{error_msg}\n```",
                        color=discord.Color.red(),
                        timestamp=datetime.now()
                    )
                    embed.set_footer(text=f"Requested by {ctx.author.display_name}")
                    await ctx.send(embed=embed)

        except Exception as e:
            logger.exception(f"Unexpected error in handle_balance command for {ctx.author}: {e}")
            await ctx.send(f"❌ An unexpected error occurred while fetching the balance: {e}")


    async def handle_open_orders(self, ctx: commands.Context, symbol: Optional[str] = None):
        """
        Handle the openorders command: Fetch and display open margin orders.

        Args:
            ctx: Discord context
            symbol: Optional symbol to filter orders by (e.g., BTCUSDT).
        """
        # Security measure: Check role
        required_role = discord.utils.get(ctx.guild.roles, name="Trading-Authorized")
        if required_role is None or required_role not in ctx.author.roles:
            await ctx.send("⛔ You don't have permission to view open orders. You need the 'Trading-Authorized' role.")
            logger.warning(f"User {ctx.author} tried to use !openorders without 'Trading-Authorized' role.")
            return

        # Determine filter text for logging/display
        filter_text = f"for symbol `{symbol.upper()}`" if symbol else "for all symbols"
        logger.info(f"User {ctx.author} requested open margin orders {filter_text}.")
        await ctx.send(f"⏳ Fetching open orders {filter_text}...", delete_after=10.0)

        try:
            # Call the service to get open orders
            # For now, we assume Cross Margin (is_isolated=False or default)
            # If you want to support isolated, add an is_isolated param to the command/handler
            result = await self.binance_service.get_open_orders(symbol=symbol) # is_isolated defaults to False/None
            # --- ADDED DEBUGGING ---
            logger.debug(f"[HANDLE_OPEN_ORDERS] Service Response Type: {type(result)}")
            logger.debug(f"[HANDLE_OPEN_ORDERS] Service Response Value: {result}")
            # --- END DEBUGGING ---
            # Check if the service returned an error
            if result.get("error"):
                error_msg = result.get("msg", "Unknown error fetching open orders.")
                logger.error(f"Failed to fetch open orders for {ctx.author}: {error_msg}")
                embed = discord.Embed(
                    title=f"❌ Error Fetching Open Orders {filter_text.capitalize()}",
                    description=f"Could not retrieve open orders.\n```\n{error_msg}\n```",
                    color=discord.Color.red(),
                    timestamp=datetime.now()
                )
                embed.set_footer(text=f"Requested by {ctx.author.display_name}")
                await ctx.send(embed=embed)
                return

            # Extract the list of orders from the 'data' key
            open_orders_list = result.get("data") # Use get without default first

            # --- ADDED DEBUGGING ---
            logger.debug(f"[HANDLE_OPEN_ORDERS] Extracted 'data' Type: {type(open_orders_list)}")
            logger.debug(f"[HANDLE_OPEN_ORDERS] Extracted 'data' Value: {open_orders_list}")
            # Check if 'data' key was missing
            if open_orders_list is None:
                 logger.error(f"The 'data' key was missing in the service response. Full service response: {result}")
                 await ctx.send("❌ Received invalid data format for open orders (missing 'data' key).")
                 return
            # --- END DEBUGGING ---

            # --- Create Success Embed ---
            open_orders = open_orders_list # Use the correctly validated list

            if not open_orders: # This correctly handles an empty list
                embed = discord.Embed(
                    title=f"📖 Open Margin Orders {filter_text.capitalize()}",
                    color=discord.Color.orange(), # Orange for no orders found
                    timestamp=datetime.now(),
                    description="No open margin orders found matching your criteria."
                 )
            else:
                embed = discord.Embed(
                    title=f"📖 Open Margin Orders {filter_text.capitalize()}",
                    color=discord.Color.green(), # Green now that we have orders
                    timestamp=datetime.now()
                 )
                embed.description = f"Found {len(open_orders)} open order(s)."
                # ... (rest of the embed formatting using open_orders list - unchanged) ...
                # Limit displayed orders to avoid huge embeds (e.g., max 10)
                display_limit = 10
                orders_to_display = open_orders[:display_limit]

                for i, order in enumerate(orders_to_display):
                    # ... (formatting logic for each order - unchanged) ...
                    order_id = order.get('orderId', 'N/A')
                    order_symbol = order.get('symbol', 'N/A')
                    side = order.get('side', 'N/A').upper()
                    order_type = order.get('type', 'N/A').upper()
                    price = order.get('price', 'N/A')
                    quantity = order.get('origQty', 'N/A') # Original quantity
                    stop_price = order.get('stopPrice', None) # Check if it's a stop order
                    time_ms = order.get('time', None) # Order creation time
                    formatted_time = self.binance_service._format_timestamp(time_ms) if time_ms else "N/A" # Use service helper

                    try: price_str = f"{float(price):.2f}" if price != 'N/A' and float(price) > 0 else order_type
                    except: price_str = str(price)
                    try: qty_str = f"{float(quantity):.5f}" if quantity != 'N/A' else "N/A"
                    except: qty_str = str(quantity)

                    field_name = f"#{i+1}: {side} {order_symbol}"
                    field_value = (
                        f"**ID:** `{order_id}`\n"
                        f"**Type:** `{order_type}` | **Price:** ${price_str}\n"
                        f"**Qty:** {qty_str}"
                    )
                    if stop_price and float(stop_price) > 0:
                        try:
                            field_value += f"\n**Stop:** ${float(stop_price):.2f}"
                        except:
                             field_value += f"\n**Stop:** {stop_price}" # Fallback if conversion fails
                    field_value += f"\n**Time:** {formatted_time}"

                    embed.add_field(name=field_name, value=field_value, inline=True)

                 # Add padding fields if needed for alignment
                if len(orders_to_display) % 3 == 1:
                    embed.add_field(name="\u200b", value="\u200b", inline=True)
                    embed.add_field(name="\u200b", value="\u200b", inline=True)
                elif len(orders_to_display) % 3 == 2:
                    embed.add_field(name="\u200b", value="\u200b", inline=True)


                if len(open_orders) > display_limit:
                    embed.add_field(name="Note", value=f"Displaying first {display_limit} of {len(open_orders)} orders.", inline=False)


            embed.set_footer(text=f"Requested by {ctx.author.display_name}", icon_url=ctx.author.avatar.url if ctx.author.avatar else None)
            await ctx.send(embed=embed)
            logger.info(f"Successfully displayed {len(open_orders)} open orders for {ctx.author}.")

        except Exception as e:
            logger.exception(f"Unexpected error handling openorders command for {ctx.author}: {e}")
            await ctx.send(f"❌ An unexpected error occurred while fetching open orders: {e}")