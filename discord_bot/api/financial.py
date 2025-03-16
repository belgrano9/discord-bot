"""
Asynchronous implementation of the Financial API client.
Refactored to use standardized async request handling and error processing.
"""

import os
from typing import Dict, Any, Optional, List, Union
import asyncio
from loguru import logger

from .base import AsyncBaseAPI, require_api_key, ApiKeyRequiredError


class AsyncFinancialAPI(AsyncBaseAPI):
    """
    Asynchronous client for financial data API endpoints.
    Handles requests for financial statements, metrics, and snapshots.
    """
    
    def __init__(
        self,
        ticker: str,
        period: Optional[str] = None,
        limit: Optional[int] = None,
        api_key: Optional[str] = None
    ):
        """
        Initialize the Financial API client.
        
        Args:
            ticker: Stock ticker symbol
            period: Time period for financial data
            limit: Limit the number of results
            api_key: API key (falls back to env var if not provided)
        """
        # Get API key from environment if not provided
        if not api_key:
            api_key = os.getenv("FINANCIAL_DATASETS_API_KEY")
        
        # Initialize base class
        super().__init__(
            base_url="https://api.financialdatasets.ai",
            api_key=api_key
        )
        
        # Set instance variables
        self.ticker = ticker
        self.period = period
        self.limit = limit
        
        logger.debug(f"Initialized AsyncFinancialAPI for {ticker}")
    
    async def _general_get(self, endpoint: str) -> Dict[str, Any]:
        """
        Make a general GET request to the API with the appropriate parameters.
        
        Args:
            endpoint: API endpoint
            
        Returns:
            API response data
        """
        # Prepare parameters based on endpoint
        if endpoint == "financial-metrics/snapshot":
            params = {"ticker": self.ticker}
        else:
            params = {
                "ticker": self.ticker,
                "period": self.period,
                "limit": self.limit
            }
            
            # Remove None values
            params = {k: v for k, v in params.items() if v is not None}
        
        # Make the request
        return await self.get(endpoint, params=params)
    
    @require_api_key
    async def get_income_statements(self) -> List[Dict[str, Any]]:
        """
        Get income statements for the specified ticker.
        
        Returns:
            List of income statement data
        """
        response = await self._general_get("financials/income-statements")
        success, data, error = await self.process_response(
            response, 
            success_path="income_statements",
            default_value=[]
        )
        
        if not success:
            logger.warning(f"Failed to get income statements for {self.ticker}: {error}")
            return []
            
        return data
    
    @require_api_key
    async def get_balance_sheet(self) -> List[Dict[str, Any]]:
        """
        Get balance sheets for the specified ticker.
        
        Returns:
            List of balance sheet data
        """
        response = await self._general_get("financials/balance-sheets")
        success, data, error = await self.process_response(
            response, 
            success_path="balance_sheets",
            default_value=[]
        )
        
        if not success:
            logger.warning(f"Failed to get balance sheets for {self.ticker}: {error}")
            return []
            
        return data
    
    @require_api_key
    async def get_cash_flow_statement(self) -> List[Dict[str, Any]]:
        """
        Get cash flow statements for the specified ticker.
        
        Returns:
            List of cash flow statement data
        """
        response = await self._general_get("financials/cash-flow-statements")
        success, data, error = await self.process_response(
            response, 
            success_path="cash_flow_statements",
            default_value=[]
        )
        
        if not success:
            logger.warning(f"Failed to get cash flow statements for {self.ticker}: {error}")
            return []
            
        return data
    
    @require_api_key
    async def get_all_financial_metrics(self) -> Dict[str, Any]:
        """
        Get all financial metrics for the specified ticker.
        
        Returns:
            Financial metrics data
        """
        return await self._general_get("financials")
    
    @require_api_key
    async def get_snapshots(self) -> Dict[str, Any]:
        """
        Get a real-time snapshot of key financial metrics and ratios for a ticker.
        
        Returns:
            Financial snapshot data
        """
        response = await self._general_get("financial-metrics/snapshot")
        success, data, error = await self.process_response(
            response, 
            success_path="snapshot",
            default_value={}
        )
        
        if not success:
            logger.warning(f"Failed to get snapshots for {self.ticker}: {error}")
            return {}
            
        return data
    
    @require_api_key
    async def get_historical(self) -> List[Dict[str, Any]]:
        """
        Get historical financial metrics for the specified ticker.
        
        Returns:
            List of historical financial metrics
        """
        response = await self._general_get("financial-metrics")
        success, data, error = await self.process_response(
            response, 
            success_path="financial_metrics",
            default_value=[]
        )
        
        if not success:
            logger.warning(f"Failed to get historical metrics for {self.ticker}: {error}")
            return []
            
        return data


# Backward compatibility wrapper for the original API
class FinancialAPI:
    """
    Backward compatibility wrapper for the AsyncFinancialAPI.
    Allows existing code to use the new async implementation without changes.
    """
    
    def __init__(
        self,
        ticker: str,
        period: Optional[str] = None,
        limit: Optional[int] = None
    ):
        """
        Initialize the backward compatibility wrapper.
        
        Args:
            ticker: Stock ticker symbol
            period: Time period for financial data
            limit: Limit the number of results
        """
        self.async_api = AsyncFinancialAPI(ticker, period, limit)
        self.ticker = ticker
        self.period = period
        self.limit = limit
    
    def _run_async(self, coroutine):
        """Helper to run async functions synchronously"""
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Create a new event loop if the current one is already running
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete(coroutine)
    
    def get_income_statements(self):
        """Get income statements (sync wrapper)"""
        return self._run_async(self.async_api.get_income_statements())
    
    def get_balance_sheet(self):
        """Get balance sheets (sync wrapper)"""
        return self._run_async(self.async_api.get_balance_sheet())
    
    def get_cash_flow_statement(self):
        """Get cash flow statements (sync wrapper)"""
        return self._run_async(self.async_api.get_cash_flow_statement())
    
    def get_all_financial_metrics(self):
        """Get all financial metrics (sync wrapper)"""
        return self._run_async(self.async_api.get_all_financial_metrics())
    
    def get_snapshots(self):
        """Get financial snapshots (sync wrapper)"""
        return self._run_async(self.async_api.get_snapshots())
    
    def get_historical(self):
        """Get historical metrics (sync wrapper)"""
        return self._run_async(self.async_api.get_historical())
