import os
from unittest.mock import patch
from discord_bot.api import FinancialAPI

def test_financial_api_initialization():
    """Test that FinancialAPI initializes correctly with a ticker"""
    # Use patch to temporarily override the actual API key
    with patch.dict(os.environ, {"FINANCIAL_DATASETS_API_KEY": "test_api_key"}):
        # Initialize the API with a ticker
        api = FinancialAPI(ticker="AAPL")
        
        # Check that ticker was set correctly
        assert api.ticker == "AAPL"
        assert api.period is None
        assert api.limit is None
        
        # Check that headers were created correctly
        assert "X-API-KEY" in api.headers
        assert api.headers["X-API-KEY"] == "test_api_key"