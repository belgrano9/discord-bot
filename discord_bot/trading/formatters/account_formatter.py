"""
Account formatter for trading commands.
Formats account data into Discord embeds.
"""

import discord
from datetime import datetime
from typing import Dict, List, Any, Optional
from loguru import logger

from ..models.account import MarginAccount, Asset, TradeInfo


class AccountFormatter:
    """Formatter for account data"""
    
    def format_margin_account(self, account: MarginAccount) -> discord.Embed:
        """
        Format margin account data into a Discord embed.
        
        Args:
            account: Margin account data
            
        Returns:
            Formatted Discord embed
        """
        # Create embed
        embed = discord.Embed(
            title=f"🏦 {account.symbol} Isolated Margin Account",
            description="Your KuCoin isolated margin account information",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        
        # Add account status and debt ratio
        status_text = "Active" if account.status == "ACTIVATED" else account.status
        embed.add_field(name="Status", value=status_text, inline=True)
        
        debt_ratio_pct = account.debt_ratio * 100
        embed.add_field(
            name="Debt Ratio",
            value=f"{account.risk_color} {debt_ratio_pct:.2f}%",
            inline=True
        )
        
        # Add base asset information
        if account.base_asset:
            base_asset = account.base_asset
            base_currency = base_asset.currency
            
            base_info = []
            base_info.append(f"Total: {base_asset.total:.8f}")
            base_info.append(f"Available: {base_asset.available:.8f}")
            
            if base_asset.borrowed > 0:
                base_info.append(f"Borrowed: {base_asset.borrowed:.8f}")
                
            if base_asset.interest > 0:
                base_info.append(f"Interest: {base_asset.interest:.8f}")
                
            borrow_status = "Enabled" if base_asset.borrow_enabled else "Disabled"
            base_info.append(f"Borrowing: {borrow_status}")
            
            repay_status = "Enabled" if base_asset.repay_enabled else "Disabled"
            base_info.append(f"Repayment: {repay_status}")
            
            embed.add_field(
                name=f"{base_currency} (Base Asset)",
                value="\n".join(base_info),
                inline=False
            )
            
        # Add quote asset information
        if account.quote_asset:
            quote_asset = account.quote_asset
            quote_currency = quote_asset.currency
            
            quote_info = []
            quote_info.append(f"Total: {quote_asset.total:.2f}")
            quote_info.append(f"Available: {quote_asset.available:.2f}")
            
            if quote_asset.borrowed > 0:
                quote_info.append(f"Borrowed: {quote_asset.borrowed:.2f}")
                
            if quote_asset.interest > 0:
                quote_info.append(f"Interest: {quote_asset.interest:.2f}")
                
            borrow_status = "Enabled" if quote_asset.borrow_enabled else "Disabled"
            quote_info.append(f"Borrowing: {borrow_status}")
            
            repay_status = "Enabled" if quote_asset.repay_enabled else "Disabled"
            quote_info.append(f"Repayment: {repay_status}")
            
            embed.add_field(
                name=f"{quote_currency} (Quote Asset)",
                value="\n".join(quote_info),
                inline=False
            )
            
        # Add portfolio summary
        embed.add_field(
            name="Total Assets (Quote Currency)",
            value=f"${account.total_assets:.2f}",
            inline=True
        )
        
        embed.add_field(
            name="Total Liabilities (Quote Currency)",
            value=f"${account.total_liabilities:.2f}",
            inline=True
        )
        
        return embed
    
    def format_trade_list(
        self,
        trades: List[TradeInfo],
        symbol: Optional[str] = None,
        limit: int = 20
    ) -> discord.Embed:
        """
        Format a list of trades into a Discord embed.
        
        Args:
            trades: List of trades
            symbol: Trading pair symbol (optional)
            limit: Maximum number of trades to display
            
        Returns:
            Formatted Discord embed
        """
        # Create title with filters info
        title = f"Isolated Margin Trades"
        if symbol:
            title += f" for {symbol}"
            
        # Create embed
        embed = discord.Embed(
            title=title,
            description=f"Showing up to {limit} recent trades",
            color=discord.Color.gold(),
            timestamp=datetime.now()
        )
        
        if not trades:
            embed.add_field(
                name="No trades found",
                value="No trades matching your criteria were found.",
                inline=False
            )
            return embed
            
        # Add fields for each trade
        for i, trade in enumerate(trades):
            if i >= 10 and len(trades) > 10:
                # If we're showing many trades, limit to avoid exceeding Discord's limits
                remaining = len(trades) - 10
                embed.add_field(
                    name=f"+ {remaining} more trades",
                    value=f"Run this command again with a smaller limit to see fewer trades at once",
                    inline=False
                )
                break
                
            # Create field title with trade number and symbol
            field_title = f"Trade #{i+1}: {trade.symbol}"
            
            # Format trade details
            details = []
            
            # Add side with emoji
            side_emoji = "🟢" if trade.side == "buy" else "🔴" if trade.side == "sell" else "⚪"
            details.append(f"{side_emoji} {trade.side.upper()}")
            
            # Add price and size
            details.append(f"Price: ${trade.price:.8f}")
            details.append(f"Size: {trade.size:.8f}")
            
            # Add total value
            details.append(f"Total: ${trade.total_value:.8f}")
            
            # Add fee information
            details.append(f"Fee: {trade.fee:.8f} {trade.fee_currency}")
            
            # Add timestamp
            if trade.timestamp:
                details.append(f"Time: {trade.timestamp}")
                
            # Add order ID (shortened)
            if trade.order_id:
                order_id = trade.order_id
                short_id = f"{order_id[:8]}...{order_id[-8:]}" if len(order_id) > 16 else order_id
                details.append(f"Order ID: {short_id}")
                
            # Join all details with newlines
            value = "\n".join(details)
            
            # Add field to embed
            embed.add_field(name=field_title, value=value, inline=False)
            
        return embed
    
    def format_single_trade(self, trade: TradeInfo) -> discord.Embed:
        """
        Format a single trade into a Discord embed.
        
        Args:
            trade: Trade information
            
        Returns:
            Formatted Discord embed
        """
        # Determine side and color
        side = trade.side
        side_emoji = "🟢" if side == "buy" else "🔴" if side == "sell" else "⚪"
        color = discord.Color.green() if side == "buy" else discord.Color.red()
        
        # Create embed
        embed = discord.Embed(
            title=f"{side_emoji} Last {trade.symbol} Trade: {side.upper()}",
            description=f"Trade details for {trade.symbol}",
            color=color,
            timestamp=datetime.now()
        )
        
        # Add trade details
        embed.add_field(name="Price", value=f"${trade.price:.8f}", inline=True)
        embed.add_field(name="Amount", value=f"{trade.size:.8f}", inline=True)
        embed.add_field(name="Total", value=f"${trade.total_value:.8f}", inline=True)
        
        # Add fee
        embed.add_field(
            name="Fee",
            value=f"{trade.fee:.8f} {trade.fee_currency}",
            inline=True
        )
        
        # Add timestamp if available
        if trade.timestamp:
            embed.set_footer(text=f"Trade time: {trade.timestamp}")
            
        # Add order ID if available
        if trade.order_id:
            embed.add_field(
                name="Order ID",
                value=f"`{trade.order_id}`",
                inline=False
            )
            
        return embed