"""
Formatter for financial data.
Converts raw financial data into formatted output for display.
"""

import discord
from typing import Dict, List, Any, Tuple
from loguru import logger

from utils.embed_utilities import create_alert_embed, format_large_number, format_field_name


class FinanceFormatter:
    """Formatter for financial data"""
    
    def format_snapshot_data(self, ticker: str, snapshot: Dict[str, Any]) -> discord.Embed:
        """
        Format financial snapshot data into a Discord embed.
        
        Args:
            ticker: Stock ticker symbol
            snapshot: Financial snapshot data
            
        Returns:
            Formatted Discord embed
        """
        # Create fields for the embed
        fields = []
        metrics = [
            ("Market Cap", "market_cap", "$"),
            ("P/E Ratio", "pe_ratio", ""),
            ("EPS", "eps", "$"),
            ("Dividend Yield", "dividend_yield", "%"),
            ("52-Week High", "fifty_two_week_high", "$"),
            ("52-Week Low", "fifty_two_week_low", "$"),
            ("ROE", "return_on_equity", "%"),
            ("ROA", "return_on_assets", "%"),
            ("Debt to Equity", "debt_to_equity", ""),
        ]

        for label, key, prefix in metrics:
            if key in snapshot:
                value = snapshot[key]
                if value is not None:
                    # Format the value appropriately
                    if isinstance(value, (int, float)):
                        if key in ["market_cap"]:
                            value = f"{prefix}{format_large_number(value)}"
                        elif key in [
                            "dividend_yield",
                            "return_on_equity",
                            "return_on_assets",
                        ]:
                            value = f"{prefix}{value:.2f}"
                        else:
                            value = f"{prefix}{value:.2f}"
                    fields.append((label, value, True))

        # Create embed with custom fields
        embed = create_alert_embed(
            title=f"{ticker.upper()} Financial Snapshot",
            description="Key financial metrics and ratios",
            fields=fields,
            color=discord.Color.blue()
        )

        return embed
    
    def format_financial_statement(
        self, 
        ticker: str, 
        statement: Dict[str, Any], 
        statement_type: str
    ) -> discord.Embed:
        """
        Format financial statement data into a Discord embed.
        
        Args:
            ticker: Stock ticker symbol
            statement: Financial statement data
            statement_type: Type of statement (income, balance, cash)
            
        Returns:
            Formatted Discord embed
        """
        # Map statement type to title
        title_map = {
            "income": "Income Statement",
            "balance": "Balance Sheet",
            "cash": "Cash Flow Statement"
        }
        
        title = title_map.get(statement_type, "Financial Statement")
        
        # Create fields for the statement
        fields = []
        counter = 0
        
        for key, value in statement.items():
            if key in ["ticker", "period", "fiscal_year", "fiscal_period"]:
                continue

            if counter >= 25:
                break

            if isinstance(value, (int, float)) and value is not None:
                formatted_value = format_large_number(value)
                fields.append(
                    (format_field_name(key), f"${formatted_value}", True)
                )
                counter += 1
                
        # Create the embed
        description = f"Period: {statement.get('period', 'Annual')}"
        if "fiscal_year" in statement:
            footer_text = f"Fiscal Year: {statement['fiscal_year']}"
        else:
            footer_text = None
            
        embed = create_alert_embed(
            title=f"{ticker.upper()} {title}",
            description=description,
            fields=fields,
            color=discord.Color.blue(),
            footer_text=footer_text
        )
        
        return embed