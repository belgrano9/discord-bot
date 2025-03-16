import discord
from discord.ext import commands
import polars as pl
from datetime import datetime, timedelta
from loguru import logger

# Import the async API clients
from api.financial import AsyncFinancialAPI
from api.prices import AsyncPricesAPI

# Import the utility functions for embeds
from utils.embed_utilities import (
    create_price_embed,
    create_alert_embed,
    format_large_number,
    format_field_name
)


class StockCommands(commands.Cog):
    """Discord commands for interacting with financial data"""

    def __init__(self, bot):
        self.bot = bot
        logger.info("Stock commands initialized")

    @commands.command(name="stock")
    async def stock_snapshot(self, ctx, ticker: str):
        """Get a snapshot of key financial metrics for a stock"""
        await ctx.send(f"Fetching data for {ticker}...")

        try:
            # Get financial snapshot using async API
            fin_api = AsyncFinancialAPI(ticker=ticker.upper())
            snapshot = await fin_api.get_snapshots()

            if not snapshot:
                await ctx.send(f"No data found for {ticker}.")
                return

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

            await ctx.send(embed=embed)
            logger.info(f"Successfully sent financial snapshot for {ticker}")

        except Exception as e:
            logger.error(f"Error fetching data for {ticker}: {str(e)}")
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
            end_date = datetime.now().strftime("%Y-%m-%d")
            start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

            # Get price data using async API
            price_api = AsyncPricesAPI(
                ticker=ticker.upper(),
                interval="day",
                interval_multiplier=1,
                start_date=start_date,
                end_date=end_date,
                limit=days,
            )

            prices = await price_api.get_prices()

            if not prices:
                await ctx.send(f"No price data found for {ticker}.")
                return

            # If only requesting latest price (days=1)
            if days == 1:
                # Get just the latest price
                if isinstance(prices, list) and len(prices) > 0:
                    latest = prices[0]  # Assuming most recent is first
                    
                    # Find the date field in the data
                    date_field = next(
                        (k for k in latest.keys() if "date" in k.lower() or "time" in k.lower()),
                        None
                    )
                    
                    # Create footer text with date if available
                    footer_text = f"Date: {latest[date_field]}" if date_field else None
                    
                    # Use the utility function to create price embed
                    embed = create_price_embed(
                        symbol=ticker.upper(),
                        price_data=latest,
                        title_prefix="Latest",
                        footer_text=footer_text
                    )

                    await ctx.send(embed=embed)
                    logger.info(f"Successfully sent price data for {ticker}")
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
                
                # Prepare data for the price embed
                price_data = {
                    "price": latest_price,
                    "change": price_change,
                    "change_percent": price_change_pct,
                }
                
                # Add volume if available
                if "volume" in latest.columns:
                    price_data["volume"] = latest["volume"][0]
                
                # Create embed with the utility function
                embed = create_price_embed(
                    symbol=ticker.upper(),
                    price_data=price_data,
                    title_prefix=f"{days}-Day",
                    footer_text=f"Date: {latest[date_column][0]}" if date_column else None,
                    color_based_on_change=True
                )

                await ctx.send(embed=embed)
                logger.info(f"Successfully sent {days}-day price data for {ticker}")

            except Exception as e:
                logger.error(f"Error processing price data for {ticker}: {str(e)}")
                await ctx.send(f"Error processing price data: {str(e)}")

        except Exception as e:
            logger.error(f"Error fetching price data for {ticker}: {str(e)}")
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
            today = datetime.now().strftime("%Y-%m-%d")

            # Use AsyncPricesAPI for live price
            price_api = AsyncPricesAPI(
                ticker=ticker.upper(),
                interval="day",
                interval_multiplier=1,
                start_date=today,
                end_date=today,
                limit=1,
            )

            snapshot = await price_api.get_live_price()

            if not snapshot:
                await ctx.send(f"No live price data found for {ticker}.")
                return

            # Use utility function to create the embed
            embed = create_price_embed(
                symbol=ticker.upper(),
                price_data=snapshot,
                title_prefix="Live",
                footer_text=f"Last updated: {snapshot.get('timestamp', 'N/A')}",
                show_additional_fields=True
            )

            await ctx.send(embed=embed)
            logger.info(f"Successfully sent live price for {ticker}")

        except Exception as e:
            logger.error(f"Error fetching live price for {ticker}: {str(e)}")
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
            # Initialize async API client
            fin_api = AsyncFinancialAPI(ticker=ticker.upper(), period="annual", limit=1)

            # Get appropriate statement type
            if statement_type == "income":
                data = await fin_api.get_income_statements()
                title = "Income Statement"
            elif statement_type == "balance":
                data = await fin_api.get_balance_sheet()
                title = "Balance Sheet"
            else:  # cash
                data = await fin_api.get_cash_flow_statement()
                title = "Cash Flow Statement"

            if not data:
                await ctx.send(
                    f"No {statement_type} statement data found for {ticker}."
                )
                return

            # Take most recent statement
            statement = data[0] if isinstance(data, list) and len(data) > 0 else data

            # Create fields for the financials statement
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

            await ctx.send(embed=embed)
            logger.info(f"Successfully sent {statement_type} statement for {ticker}")

        except Exception as e:
            logger.error(f"Error fetching financial data for {ticker}: {str(e)}")
            await ctx.send(f"Error fetching financial data: {str(e)}")


# In stock_commands.py, change the setup function to:
async def setup(bot):
    """Add the StockCommands cog to the bot"""
    await bot.add_cog(StockCommands(bot))