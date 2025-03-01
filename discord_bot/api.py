import requests

# from base_api import BaseAPI
import os
from abc import ABC, abstractmethod
import polars as pl


class BaseAPI(ABC):
    def __init__(self):
        self.headers = {"X-API-KEY": os.getenv("FINANCIAL_DATASETS_API_KEY")}

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

    def _base_request(self, url: str) -> requests.Response:
        """Make a base request to the API."""
        return requests.get(url, headers=self.headers)

    def _general_get(self, endpoint: str) -> requests.Response:
        """Make a general GET request to the API."""
        if endpoint == "financial-metrics/snapshots":
            return self._base_request(
                f"https://api.financialdatasets.ai/financial-metrics/snapshot"
                f"?ticker={self.ticker}"
            )
        else:
            return self._base_request(
                f"https://api.financialdatasets.ai/{endpoint}"
                f"?ticker={self.ticker}"
                f"&period={self.period}"
                f"&limit={self.limit}"
            )

    def get_income_statements(self) -> requests.Response:
        """## Make a GET request to the income statements endpoint."""
        return (
            self._general_get(endpoint="financials/income-statements")
            .json()
            .get("income_statements")
        )

    def get_balance_sheet(self) -> requests.Response:
        """Make a GET request to the balance sheet endpoint."""
        return (
            self._general_get(endpoint="financials/balance-sheets")
            .json()
            .get("balance_sheets")
        )

    def get_cash_flow_statement(self) -> requests.Response:
        """## Make a GET request to the cash flow statement endpoint."""
        return (
            self._general_get(endpoint="financials/cash-flow-statements")
            .json()
            .get("cash_flow_statements")
        )

    def get_all_financial_metrics(self) -> requests.Response:
        """## Make a GET request to the all financial metrics endpoint."""
        return self._general_get(endpoint="financials").json()

    def get_snapshots(self) -> requests.Response:
        """## Make a GET request to the snapshots endpoint.

        Get a real-time snapshot of key financial metrics and ratios for a ticker, including valuation, profitability, efficiency, liquidity, leverage, growth, and per share metrics.
        """
        return (
            self._general_get(endpoint="financial-metrics/snapshot")
            .json()
            .get("snapshot")
        )

    def get_historical(self) -> requests.Response:
        """
        ## Make a GET request to the historical endpoint.
        Get financial metrics for a ticker, including valuation, profitability, efficiency, liquidity, leverage, growth, and per share metrics.
        """
        return (
            self._general_get(endpoint="financial-metrics")
            .json()
            .get("financial_metrics")
        )


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

    def _base_request(self, url: str) -> requests.Response:
        """Make a base request to the API."""
        return requests.get(url, headers=self.headers)

    def _general_get(self, endpoint: str) -> requests.Response:
        """Make a general GET request to the API."""
        return self._base_request(
            f"https://api.financialdatasets.ai/{endpoint}/"
            f"?ticker={self.ticker}"
            f"&interval={self.interval}"
            f"&interval_multiplier={self.interval_multiplier}"
            f"&start_date={self.start_date}"
            f"&end_date={self.end_date}"
        )

    def get_prices(self) -> requests.Response:
        """Make a GET request to the API for prices."""
        return self._general_get("prices").json().get("prices")

    def get_live_price(self) -> requests.Response:
        """Make a GET request to get a live price snapshot."""
        return (
            self._base_request(
                f"https://api.financialdatasets.ai/prices/snapshot"
                f"?ticker={self.ticker}"
            )
            .json()
            .get("snapshot")
        )


if __name__ == "__main__":
    fin = FinancialAPI(ticker="AAPL")
    print(fin.get_snapshots())
