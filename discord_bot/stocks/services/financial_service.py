"""
Service for retrieving financial data from APIs.
Handles requests for financial statements, metrics, and market data.
"""

import asyncio
from typing import Dict, List, Any, Optional
from loguru import logger

from api.financial import AsyncFinancialAPI


class FinancialService:
    """Service for retrieving financial data"""
    
    async def get_financial_snapshot(self, ticker: str) -> Dict[str, Any]:
        """
        Get a snapshot of key financial metrics for a ticker.
        
        Args:
            ticker: Stock ticker symbol
            
        Returns:
            Dictionary of financial metrics or empty dict if failed
        """
        try:
            fin_api = AsyncFinancialAPI(ticker=ticker.upper())
            snapshot = await fin_api.get_snapshots()
            
            if not snapshot:
                logger.warning(f"No snapshot data found for {ticker}")
                return {}
                
            return snapshot
            
        except Exception as e:
            logger.error(f"Error fetching financial snapshot for {ticker}: {str(e)}")
            return {}
    
    async def get_income_statement(self, ticker: str, period: str = "annual", limit: int = 1) -> List[Dict[str, Any]]:
        """
        Get income statements for a ticker.
        
        Args:
            ticker: Stock ticker symbol
            period: Time period ("annual" or "quarterly")
            limit: Number of statements to retrieve
            
        Returns:
            List of income statement dictionaries
        """
        try:
            fin_api = AsyncFinancialAPI(ticker=ticker.upper(), period=period, limit=limit)
            statements = await fin_api.get_income_statements()
            
            if not statements:
                logger.warning(f"No income statement data found for {ticker}")
                return []
                
            return statements
            
        except Exception as e:
            logger.error(f"Error fetching income statements for {ticker}: {str(e)}")
            return []
    
    async def get_balance_sheet(self, ticker: str, period: str = "annual", limit: int = 1) -> List[Dict[str, Any]]:
        """
        Get balance sheets for a ticker.
        
        Args:
            ticker: Stock ticker symbol
            period: Time period ("annual" or "quarterly")
            limit: Number of statements to retrieve
            
        Returns:
            List of balance sheet dictionaries
        """
        try:
            fin_api = AsyncFinancialAPI(ticker=ticker.upper(), period=period, limit=limit)
            sheets = await fin_api.get_balance_sheet()
            
            if not sheets:
                logger.warning(f"No balance sheet data found for {ticker}")
                return []
                
            return sheets
            
        except Exception as e:
            logger.error(f"Error fetching balance sheets for {ticker}: {str(e)}")
            return []
    
    async def get_cash_flow_statement(self, ticker: str, period: str = "annual", limit: int = 1) -> List[Dict[str, Any]]:
        """
        Get cash flow statements for a ticker.
        
        Args:
            ticker: Stock ticker symbol
            period: Time period ("annual" or "quarterly")
            limit: Number of statements to retrieve
            
        Returns:
            List of cash flow statement dictionaries
        """
        try:
            fin_api = AsyncFinancialAPI(ticker=ticker.upper(), period=period, limit=limit)
            statements = await fin_api.get_cash_flow_statement()
            
            if not statements:
                logger.warning(f"No cash flow statement data found for {ticker}")
                return []
                
            return statements
            
        except Exception as e:
            logger.error(f"Error fetching cash flow statements for {ticker}: {str(e)}")
            return []