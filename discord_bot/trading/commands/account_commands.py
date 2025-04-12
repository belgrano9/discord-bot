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

    async def handle_balance(self, ctx: commands.Context):
        """
        Handle the balance command: Fetch and display margin account summary using the service.

        Args:
            ctx: Discord context
        """
        # Security measure: Check role
        required_role = discord.utils.get(ctx.guild.roles, name="Trading-Authorized")
        if required_role is None or required_role not in ctx.author.roles:
            await ctx.send("⛔ You don't have permission to view account balances. You need the 'Trading-Authorized' role.")
            logger.warning(f"User {ctx.author} tried to use !balance without 'Trading-Authorized' role.")
            return

        logger.info(f"User {ctx.author} requested margin account balance.")
        await ctx.send("⏳ Fetching margin account balance...", delete_after=5.0) # Give feedback

        try:
            # --- Step 1: Call the service method which fetches AND parses ---
            summary_data = await self.binance_service.get_cross_margin_account_summary()
            logger.debug(f"Received summary data from service: {summary_data}")

            # --- Step 2: Check the result from the service ---
            if not summary_data.get("error", False):
                # Success - Create embed using already parsed data
                embed = discord.Embed(
                    title="📊 Binance Cross Margin Balance",
                    color=discord.Color.blue(),
                    timestamp=datetime.now()
                )

                # Extract data (ALREADY floats from the service method)
                margin_level = summary_data.get("current_margin_level")
                total_asset_btc = summary_data.get("total_asset_btc")
                total_liability_btc = summary_data.get("total_liability_btc")
                total_net_asset_btc = summary_data.get("total_net_asset_btc")

                # Format and add fields (checking for None in case service parsing failed subtly)
                embed.add_field(
                    name="Margin Level",
                    value=f"{margin_level:.2f}" if margin_level is not None else "N/A",
                    inline=True
                )
                embed.add_field(
                    name="Total Assets (BTC)",
                    value=f"{total_asset_btc:.8f} BTC" if total_asset_btc is not None else "N/A",
                    inline=True
                )
                embed.add_field(
                    name="Total Liabilities (BTC)",
                    value=f"{total_liability_btc:.8f} BTC" if total_liability_btc is not None else "N/A",
                    inline=True
                )
                if total_net_asset_btc is not None:
                     embed.add_field(
                        name="Net Assets (BTC)",
                        value=f"{total_net_asset_btc:.8f} BTC",
                        inline=True
                    )
                else: # Placeholder for alignment
                     embed.add_field(name="\u200b", value="\u200b", inline=True)

                embed.set_footer(text=f"Requested by {ctx.author.display_name}", icon_url=ctx.author.avatar.url if ctx.author.avatar else None)
                logger.info(f"Successfully fetched and formatted balance for {ctx.author} using service.")
                await ctx.send(embed=embed)

            else:
                # Handle error reported BY THE SERVICE
                error_msg = summary_data.get("msg", "Unknown error fetching/parsing balance.")
                logger.error(f"Service layer failed to get/parse balance for {ctx.author}: {error_msg}")
                embed = discord.Embed(
                    title="❌ Error Fetching Balance",
                    description=f"Could not retrieve or process margin account balance.\n```\n{error_msg}\n```",
                    color=discord.Color.red(),
                    timestamp=datetime.now()
                )
                embed.set_footer(text=f"Requested by {ctx.author.display_name}")
                await ctx.send(embed=embed)

        except Exception as e:
            # Catch unexpected errors during the process (e.g., service not available)
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