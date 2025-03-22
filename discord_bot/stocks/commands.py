"""
Command handlers for stock data commands.
Coordinates services and formatters to process user commands.
"""

import discord
from discord.ext import commands
import polars as pl
from typing import Dict, List, Any, Optional
from datetime import datetime
from loguru import logger

from .services.financial_service import FinancialService
from .services.price_service import PriceService
from .formatters.finance_formatter import FinanceFormatter
from .formatters.price_formatter import PriceFormatter


class StockCommands:
    """Command handlers for stock data"""
    
    def __init__(self):
        """Initialize services and formatters"""
        self.financial_service = FinancialService()
        self.price_service = PriceService()
        self.finance_formatter = FinanceFormatter()
        self.price_formatter = PriceFormatter()
        logger.debug("Initialized StockCommands")
    
    async def handle_stock_snapshot(self, ctx: commands.Context, ticker: str) -> None:
        """
        Handle the stock snapshot command.
        
        Args:
            ctx: Discord context
            ticker: Stock ticker symbol
        """
        await ctx.send(f"Fetching data for {ticker}...")
        
        try:
            # Get financial snapshot
            snapshot = await self.financial_service.get_financial_snapshot(ticker)
            
            if not snapshot:
                await ctx.send(f"No data found for {ticker}.")
                return
            
            # Create and send the embed
            embed = self.finance_formatter.format_snapshot_data(ticker, snapshot)
            await ctx.send(embed=embed)
            logger.info(f"Successfully sent financial snapshot for {ticker}")
            
        except Exception as e:
            logger.error(f"Error in stock snapshot command for {ticker}: {str(e)}")
            await ctx.send(f"Error fetching data: {str(e)}")
    
    async def handle_stock_price(self, ctx: commands.Context, ticker: str, days: int) -> None:
        """
        Handle the stock price command.
        
        Args:
            ctx: Discord context
            ticker: Stock ticker symbol
            days: Number of days of history
        """
        if not ticker:
            await ctx.send("Please provide a ticker symbol. Example: !price AAPL")
            return
            
        await ctx.send(f"Fetching price data for {ticker}...")
        
        try:
            # For one day, just get the latest price
            if days == 1:
                price_data = await self.price_service.get_current_price(ticker)
                
                if not price_data:
                    await ctx.send(f"No price data found for {ticker}.")
                    return
                    
                embed = self.price_formatter.format_current_price(ticker, price_data)
                await ctx.send(embed=embed)
                logger.info(f"Successfully sent price data for {ticker}")
                return
                
            # For historical data
            prices = await self.price_service.get_historical_prices(ticker, days)
            
            if not prices:
                await ctx.send(f"No historical price data found for {ticker}.")
                return
                
            # Calculate price changes
            price_changes = await self.price_service.calculate_price_changes(prices)
            
            # Get date for footer if available
            date_str = None
            if prices and len(prices) > 0:
                df = pl.DataFrame(prices)
                date_column = next(
                    (col for col in df.columns if "date" in col.lower() or "time" in col.lower()),
                    None
                )
                if date_column:
                    latest = df.sort(date_column, descending=True).head(1)
                    date_str = str(latest[date_column][0])
            
            # Create and send the embed
            embed = self.price_formatter.format_historical_price(ticker, price_changes, days, date_str)
            await ctx.send(embed=embed)
            logger.info(f"Successfully sent {days}-day price data for {ticker}")
            
        except Exception as e:
            logger.error(f"Error in stock price command for {ticker}: {str(e)}")
            await ctx.send(f"Error fetching price data: {str(e)}")
    
    async def handle_live_price(self, ctx: commands.Context, ticker: str) -> None:
        """
        Handle the live price command.
        
        Args:
            ctx: Discord context
            ticker: Stock ticker symbol
        """
        if not ticker:
            await ctx.send("Please provide a ticker symbol. Example: !live AAPL")
            return
            
        await ctx.send(f"Fetching live price for {ticker}...")
        
        try:
            # Get live price data
            price_data = await self.price_service.get_current_price(ticker)
            
            if not price_data:
                await ctx.send(f"No live price data found for {ticker}.")
                return
                
            # Create and send the embed
            embed = self.price_formatter.format_live_price(ticker, price_data)
            await ctx.send(embed=embed)
            logger.info(f"Successfully sent live price for {ticker}")
            
        except Exception as e:
            logger.error(f"Error in live price command for {ticker}: {str(e)}")
            await ctx.send(f"Error fetching live price: {str(e)}")
    
    async def handle_financials(self, ctx: commands.Context, ticker: str, statement_type: str) -> None:
        """
        Handle the financials command.
        
        Args:
            ctx: Discord context
            ticker: Stock ticker symbol
            statement_type: Type of statement (income, balance, cash)
        """
        await ctx.send(f"Fetching {statement_type} statement for {ticker}...")
        
        valid_types = ["income", "balance", "cash"]
        if statement_type not in valid_types:
            await ctx.send(f"Invalid statement type. Choose from: {', '.join(valid_types)}")
            return
            
        try:
            # Get appropriate statement type
            if statement_type == "income":
                data = await self.financial_service.get_income_statement(ticker)
                title = "Income Statement"
            elif statement_type == "balance":
                data = await self.financial_service.get_balance_sheet(ticker)
                title = "Balance Sheet"
            else:  # cash
                data = await self.financial_service.get_cash_flow_statement(ticker)
                title = "Cash Flow Statement"
                
            if not data:
                await ctx.send(f"No {statement_type} statement data found for {ticker}.")
                return
                
            # Take most recent statement
            statement = data[0] if isinstance(data, list) and len(data) > 0 else data
            
            # Create and send the embed
            embed = self.finance_formatter.format_financial_statement(ticker, statement, statement_type)
            await ctx.send(embed=embed)
            logger.info(f"Successfully sent {statement_type} statement for {ticker}")
            
        except Exception as e:
            logger.error(f"Error in financials command for {ticker}: {str(e)}")
            await ctx.send(f"Error fetching financial data: {str(e)}")