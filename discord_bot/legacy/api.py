import requests
import os
from abc import ABC, abstractmethod
from logging_setup import get_logger

# Create module logger
logger = get_logger("api")

class BaseAPI(ABC):
    def __init__(self):
        self.headers = {"X-API-KEY": os.getenv("FINANCIAL_DATASETS_API_KEY")}
        logger.debug("Initialized BaseAPI with API key")

    @abstractmethod
    def _base_request(self) -> requests.Response:
        pass

    @abstractmethod
    def _general_get(self) -> requests.Response:
        pass


class FinancialAPI(BaseAPI):
    def __init__(
        self, ticker: str, period: str | None = None, limit: int | None = None
    ):
        super().__init__()
        self.ticker = ticker
        self.period = period
        self.limit = limit
        logger.debug(f"Initialized FinancialAPI for ticker {ticker}, period {period}, limit {limit}")

    def _base_request(self, url: str) -> requests.Response:
        """Make a base request to the API."""
        logger.debug(f"Making base request to {url}")
        try:
            response = requests.get(url, headers=self.headers)
            logger.debug(f"Received response with status code {response.status_code}")
            return response
        except Exception as e:
            logger.error(f"Error making request to {url}: {str(e)}")
            raise

    def _general_get(self, endpoint: str) -> requests.Response:
        """Make a general GET request to the API."""
        logger.debug(f"Making general GET request to endpoint {endpoint}")
        if endpoint == "financial-metrics/snapshots":
            url = f"https://api.financialdatasets.ai/financial-metrics/snapshot?ticker={self.ticker}"
            logger.debug(f"Using snapshot URL: {url}")
            return self._base_request(url)
        else:
            url = (
                f"https://api.financialdatasets.ai/{endpoint}"
                f"?ticker={self.ticker}"
                f"&period={self.period}"
                f"&limit={self.limit}"
            )
            logger.debug(f"Using standard URL: {url}")
            return self._base_request(url)

    def get_income_statements(self) -> requests.Response:
        """## Make a GET request to the income statements endpoint."""
        logger.info(f"Getting income statements for {self.ticker}")
        try:
            result = (
                self._general_get(endpoint="financials/income-statements")
                .json()
                .get("income_statements")
            )
            logger.debug(f"Received income statements data: {len(result) if result else 0} records")
            return result
        except Exception as e:
            logger.error(f"Failed to get income statements for {self.ticker}: {str(e)}")
            raise

    def get_balance_sheet(self) -> requests.Response:
        """Make a GET request to the balance sheet endpoint."""
        logger.info(f"Getting balance sheet for {self.ticker}")
        try:
            result = (
                self._general_get(endpoint="financials/balance-sheets")
                .json()
                .get("balance_sheets")
            )
            logger.debug(f"Received balance sheet data: {len(result) if result else 0} records")
            return result
        except Exception as e:
            logger.error(f"Failed to get balance sheet for {self.ticker}: {str(e)}")
            raise

    def get_cash_flow_statement(self) -> requests.Response:
        """## Make a GET request to the cash flow statement endpoint."""
        logger.info(f"Getting cash flow statement for {self.ticker}")
        try:
            result = (
                self._general_get(endpoint="financials/cash-flow-statements")
                .json()
                .get("cash_flow_statements")
            )
            logger.debug(f"Received cash flow statement data: {len(result) if result else 0} records")
            return result
        except Exception as e:
            logger.error(f"Failed to get cash flow statement for {self.ticker}: {str(e)}")
            raise

    def get_all_financial_metrics(self) -> requests.Response:
        """## Make a GET request to the all financial metrics endpoint."""
        logger.info(f"Getting all financial metrics for {self.ticker}")
        try:
            result = self._general_get(endpoint="financials").json()
            logger.debug(f"Received financial metrics data")
            return result
        except Exception as e:
            logger.error(f"Failed to get all financial metrics for {self.ticker}: {str(e)}")
            raise

    def get_snapshots(self) -> requests.Response:
        """## Make a GET request to the snapshots endpoint.

        Get a real-time snapshot of key financial metrics and ratios for a ticker, including valuation, profitability, efficiency, liquidity, leverage, growth, and per share metrics.
        """
        logger.info(f"Getting financial snapshots for {self.ticker}")
        try:
            result = (
                self._general_get(endpoint="financial-metrics/snapshot")
                .json()
                .get("snapshot")
            )
            logger.debug(f"Received snapshot data")
            return result
        except Exception as e:
            logger.error(f"Failed to get financial snapshots for {self.ticker}: {str(e)}")
            raise

    def get_historical(self) -> requests.Response:
        """
        ## Make a GET request to the historical endpoint.
        Get financial metrics for a ticker, including valuation, profitability, efficiency, liquidity, leverage, growth, and per share metrics.
        """
        logger.info(f"Getting historical financial metrics for {self.ticker}")
        try:
            result = (
                self._general_get(endpoint="financial-metrics")
                .json()
                .get("financial_metrics")
            )
            logger.debug(f"Received historical data: {len(result) if result else 0} records")
            return result
        except Exception as e:
            logger.error(f"Failed to get historical financial metrics for {self.ticker}: {str(e)}")
            raise


class PricesAPI(BaseAPI):
    def __init__(
        self,
        ticker: str,
        interval: str,
        interval_multiplier: int,
        start_date: str,
        end_date: str,
        limit: int | None = None,
    ):
        super().__init__()
        self.ticker = ticker
        self.interval = interval
        self.interval_multiplier = interval_multiplier
        self.start_date = start_date
        self.end_date = end_date
        self.limit = limit
        logger.debug(
            f"Initialized PricesAPI for ticker {ticker}, interval {interval}, "
            f"interval_multiplier {interval_multiplier}, date range {start_date} to {end_date}, limit {limit}"
        )

    def _base_request(self, url: str) -> requests.Response:
        """Make a base request to the API."""
        logger.debug(f"Making base request to {url}")
        try:
            response = requests.get(url, headers=self.headers)
            logger.debug(f"Received response with status code {response.status_code}")
            return response
        except Exception as e:
            logger.error(f"Error making request to {url}: {str(e)}")
            raise

    def _general_get(self, endpoint: str) -> requests.Response:
        """Make a general GET request to the API."""
        logger.debug(f"Making general GET request to endpoint {endpoint}")
        url = (
            f"https://api.financialdatasets.ai/{endpoint}/"
            f"?ticker={self.ticker}"
            f"&interval={self.interval}"
            f"&interval_multiplier={self.interval_multiplier}"
            f"&start_date={self.start_date}"
            f"&end_date={self.end_date}"
        )
        logger.debug(f"Using URL: {url}")
        return self._base_request(url)

    def get_prices(self) -> requests.Response:
        """Make a GET request to the API for prices."""
        logger.info(f"Getting prices for {self.ticker}")
        try:
            result = self._general_get("prices").json().get("prices")
            logger.debug(f"Received prices data: {len(result) if result else 0} records")
            return result
        except Exception as e:
            logger.error(f"Failed to get prices for {self.ticker}: {str(e)}")
            raise

    def get_live_price(self) -> requests.Response:
        """Make a GET request to get a live price snapshot."""
        logger.info(f"Getting live price for {self.ticker}")
        try:
            url = f"https://api.financialdatasets.ai/prices/snapshot?ticker={self.ticker}"
            logger.debug(f"Using URL for live price: {url}")
            result = self._base_request(url).json().get("snapshot")
            logger.debug(f"Received live price data")
            return result
        except Exception as e:
            logger.error(f"Failed to get live price for {self.ticker}: {str(e)}")
            raise


if __name__ == "__main__":
    logger.info("Testing FinancialAPI")
    fin = FinancialAPI(ticker="AAPL")
    print(fin.get_snapshots())