import os
import discord
from discord.ext import commands
from discord import Embed
import polars as pl
from typing import List, Dict, Any

# Import your API classes
from api import FinancialAPI, PricesAPI


class StockCommands(commands.Cog):
    """Discord commands for interacting with financial data"""

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="stock")
    async def stock_snapshot(self, ctx, ticker: str):
        """Get a snapshot of key financial metrics for a stock"""
        await ctx.send(f"Fetching data for {ticker}...")

        try:
            # Get financial snapshot
            fin_api = FinancialAPI(ticker=ticker.upper())
            snapshot = fin_api.get_snapshots()

            if not snapshot:
                await ctx.send(f"No data found for {ticker}.")
                return

            # Create embed with financial data
            embed = Embed(
                title=f"{ticker.upper()} Financial Snapshot", color=discord.Color.blue()
            )

            # Add key metrics to the embed
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
                                value = f"{prefix}{self._format_large_number(value)}"
                            elif key in [
                                "dividend_yield",
                                "return_on_equity",
                                "return_on_assets",
                            ]:
                                value = f"{prefix}{value:.2f}"
                            else:
                                value = f"{prefix}{value:.2f}"
                        embed.add_field(name=label, value=value, inline=True)

            await ctx.send(embed=embed)

        except Exception as e:
            await ctx.send(f"Error fetching data: {str(e)}")

    @commands.command(name="price")
    async def stock_price(self, ctx, ticker: str = None, days: int = 1):
        """Get recent price data for a stock

        Usage:
        !price AAPL - Get latest price for Apple
        !price MSFT 7 - Get Microsoft price data for past 7 days
        """
        if ticker is None:
            await ctx.send("Please provide a ticker symbol. Example: !price AAPL")
            return

        await ctx.send(f"Fetching price data for {ticker}...")

        try:
            # Calculate dates based on requested days
            from datetime import datetime, timedelta

            end_date = datetime.now().strftime("%Y-%m-%d")
            start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

            # Get price data
            price_api = PricesAPI(
                ticker=ticker.upper(),
                interval="day",
                interval_multiplier=1,
                start_date=start_date,
                end_date=end_date,
                limit=days,
            )

            prices = price_api.get_prices()

            if not prices:
                await ctx.send(f"No price data found for {ticker}.")
                return

            # If only requesting latest price (days=1)
            if days == 1:
                # Get just the latest price
                if isinstance(prices, list) and len(prices) > 0:
                    latest = prices[0]  # Assuming most recent is first

                    # Create simple embed with latest price
                    embed = Embed(
                        title=f"{ticker.upper()} Latest Price",
                        color=discord.Color.blue(),
                    )

                    # Add basic price info
                    if "close" in latest:
                        embed.add_field(
                            name="Price", value=f"${latest['close']:.2f}", inline=True
                        )

                    # Add additional fields if available
                    fields = [
                        ("open", "Open"),
                        ("high", "High"),
                        ("low", "Low"),
                        ("volume", "Volume"),
                    ]

                    for key, label in fields:
                        if key in latest:
                            value = latest[key]
                            if key == "volume":
                                value = self._format_large_number(value)
                            else:
                                value = f"${value:.2f}"
                            embed.add_field(name=label, value=value, inline=True)

                    # Add date
                    date_field = next(
                        (
                            k
                            for k in latest.keys()
                            if "date" in k.lower() or "time" in k.lower()
                        ),
                        None,
                    )
                    if date_field:
                        embed.set_footer(text=f"Date: {latest[date_field]}")

                    await ctx.send(embed=embed)
                    return

            # For historical data (days > 1)
            try:
                df = pl.DataFrame(prices)

                # Get the date column name
                date_column = next(
                    (
                        col
                        for col in df.columns
                        if "date" in col.lower() or "time" in col.lower()
                    ),
                    None,
                )

                if not date_column:
                    await ctx.send(
                        f"Could not identify date column. Available columns: {df.columns}"
                    )
                    return

                # Get latest price and change
                latest = df.sort(date_column, descending=True).head(1)
                latest_price = latest["close"][0]

                # Calculate price change
                if len(df) > 1:
                    prev_close = df.sort(date_column, descending=True).slice(1, 2)[
                        "close"
                    ][0]
                    price_change = latest_price - prev_close
                    price_change_pct = (price_change / prev_close) * 100
                else:
                    price_change = 0
                    price_change_pct = 0

                # Create embed with price data
                embed = Embed(
                    title=f"{ticker.upper()} Price Data",
                    description=f"Last {days} days",
                    color=(
                        discord.Color.green()
                        if price_change >= 0
                        else discord.Color.red()
                    ),
                )

                # Add price info
                embed.add_field(
                    name="Latest Close", value=f"${latest_price:.2f}", inline=True
                )
                embed.add_field(
                    name="Change",
                    value=f"${price_change:.2f} ({price_change_pct:.2f}%)",
                    inline=True,
                )

                # Add volume
                if "volume" in latest.columns:
                    embed.add_field(
                        name="Volume",
                        value=self._format_large_number(latest["volume"][0]),
                        inline=True,
                    )

                # Add date
                embed.set_footer(text=f"Date: {latest[date_column][0]}")

                await ctx.send(embed=embed)

            except Exception as e:
                await ctx.send(f"Error processing price data: {str(e)}")

        except Exception as e:
            await ctx.send(f"Error fetching price data: {str(e)}")

    @commands.command(name="live")
    async def live_price(self, ctx, ticker: str = None):
        """Get the latest live price for a stock"""
        if ticker is None:
            await ctx.send("Please provide a ticker symbol. Example: !live AAPL")
            return

        await ctx.send(f"Fetching live price for {ticker}...")

        try:
            # Calculate current date for API parameters
            from datetime import datetime

            today = datetime.now().strftime("%Y-%m-%d")

            # Use PricesAPI for live price
            price_api = PricesAPI(
                ticker=ticker.upper(),
                interval="day",
                interval_multiplier=1,
                start_date=today,
                end_date=today,
                limit=1,
            )

            snapshot = price_api.get_live_price()

            if not snapshot:
                await ctx.send(f"No live price data found for {ticker}.")
                return

            # Create embed with price data
            embed = Embed(
                title=f"{ticker.upper()} Live Price",
                color=(
                    discord.Color.green()
                    if snapshot.get("change_percent", 0) >= 0
                    else discord.Color.red()
                ),
            )

            # Add price fields
            fields = [
                ("Price", "price", "$"),
                ("Change", "change", "$"),
                ("Change %", "change_percent", "%"),
                ("Volume", "volume", ""),
                ("Open", "open", "$"),
                ("High", "high", "$"),
                ("Low", "low", "$"),
                ("Previous Close", "prev_close", "$"),
            ]

            for label, key, prefix in fields:
                if key in snapshot and snapshot[key] is not None:
                    value = snapshot[key]
                    if key == "volume":
                        formatted_value = self._format_large_number(value)
                    elif isinstance(value, (int, float)):
                        formatted_value = f"{prefix}{value:.2f}"
                    else:
                        formatted_value = f"{prefix}{value}"

                    embed.add_field(name=label, value=formatted_value, inline=True)

            # Add timestamp if available
            if "timestamp" in snapshot:
                embed.set_footer(text=f"Last updated: {snapshot['timestamp']}")

            await ctx.send(embed=embed)

        except Exception as e:
            await ctx.send(f"Error fetching live price: {str(e)}")

    @commands.command(name="financials")
    async def financials(self, ctx, ticker: str, statement_type: str = "income"):
        """Get financial statements for a company

        statement_type options: income, balance, cash
        """
        await ctx.send(f"Fetching {statement_type} statement for {ticker}...")

        valid_types = ["income", "balance", "cash"]
        if statement_type not in valid_types:
            await ctx.send(
                f"Invalid statement type. Choose from: {', '.join(valid_types)}"
            )
            return

        try:
            fin_api = FinancialAPI(ticker=ticker.upper(), period="annual", limit=1)

            if statement_type == "income":
                data = fin_api.get_income_statements()
                title = "Income Statement"
            elif statement_type == "balance":
                data = fin_api.get_balance_sheet()
                title = "Balance Sheet"
            else:  # cash
                data = fin_api.get_cash_flow_statement()
                title = "Cash Flow Statement"

            if not data:
                await ctx.send(
                    f"No {statement_type} statement data found for {ticker}."
                )
                return

            # Take most recent statement
            statement = data[0] if isinstance(data, list) and len(data) > 0 else data

            # Create embed with financial data
            embed = Embed(
                title=f"{ticker.upper()} {title}",
                description=f"Period: {statement.get('period', 'Annual')}",
                color=discord.Color.blue(),
            )

            # Add key items from the statement (limit to 25 fields due to Discord limits)
            counter = 0
            for key, value in statement.items():
                if key in ["ticker", "period", "fiscal_year", "fiscal_period"]:
                    continue

                if counter >= 25:
                    break

                if isinstance(value, (int, float)) and value is not None:
                    formatted_value = self._format_large_number(value)
                    embed.add_field(
                        name=self._format_field_name(key),
                        value=f"${formatted_value}",
                        inline=True,
                    )
                    counter += 1

            # Add date/period info
            if "fiscal_year" in statement:
                embed.set_footer(text=f"Fiscal Year: {statement['fiscal_year']}")

            await ctx.send(embed=embed)

        except Exception as e:
            await ctx.send(f"Error fetching financial data: {str(e)}")

    def _format_large_number(self, num: float) -> str:
        """Format large numbers with K, M, B suffixes"""
        if num is None:
            return "N/A"

        abs_num = abs(num)
        sign = "-" if num < 0 else ""

        if abs_num >= 1_000_000_000:
            return f"{sign}{abs_num/1_000_000_000:.2f}B"
        elif abs_num >= 1_000_000:
            return f"{sign}{abs_num/1_000_000:.2f}M"
        elif abs_num >= 1_000:
            return f"{sign}{abs_num/1_000:.2f}K"
        else:
            return f"{sign}{abs_num:.2f}"

    def _format_field_name(self, name: str) -> str:
        """Convert snake_case to Title Case with spaces"""
        return " ".join(word.capitalize() for word in name.split("_"))


# In stock_commands.py, change the setup function to:
async def setup(bot):
    """Add the StockCommands cog to the bot"""
    await bot.add_cog(StockCommands(bot))
