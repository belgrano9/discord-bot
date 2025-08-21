import os
from dotenv import load_dotenv
from binance.client import Client
from datetime import datetime
import polars as pl
import argparse
from typing import Optional, List, Dict
from loguru import logger
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

# --- Configuration ---
load_dotenv()
api_key = os.getenv('BINANCE_API_KEY')
api_secret = os.getenv('BINANCE_API_SECRET')

# Configure loguru
logger.remove()
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="INFO"
)

logger.add(
    "binance_data_{time:YYYY-MM-DD}.log",
    rotation="1 day",
    retention="7 days",
    level="DEBUG",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}"
)

class BinanceDataFetcher:
    """Fetch OHLCV data from Binance using Polars for data processing"""
    
    INTERVAL_MAP = {
        '1m': Client.KLINE_INTERVAL_1MINUTE,
        '3m': Client.KLINE_INTERVAL_3MINUTE,
        '5m': Client.KLINE_INTERVAL_5MINUTE,
        '15m': Client.KLINE_INTERVAL_15MINUTE,
        '30m': Client.KLINE_INTERVAL_30MINUTE,
        '1h': Client.KLINE_INTERVAL_1HOUR,
        '2h': Client.KLINE_INTERVAL_2HOUR,
        '4h': Client.KLINE_INTERVAL_4HOUR,
        '6h': Client.KLINE_INTERVAL_6HOUR,
        '8h': Client.KLINE_INTERVAL_8HOUR,
        '12h': Client.KLINE_INTERVAL_12HOUR,
        '1d': Client.KLINE_INTERVAL_1DAY,
        '3d': Client.KLINE_INTERVAL_3DAY,
        '1w': Client.KLINE_INTERVAL_1WEEK,
        '1M': Client.KLINE_INTERVAL_1MONTH
    }
    
    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None):
        """Initialize with API credentials"""
        logger.info("Initializing BinanceDataFetcher")
        
        self.api_key = api_key or os.getenv('BINANCE_API_KEY')
        self.api_secret = api_secret or os.getenv('BINANCE_API_SECRET')
        
        if not self.api_key or not self.api_secret:
            logger.error("Binance API credentials not found in environment variables")
            raise ValueError("Binance API credentials not found")
        
        logger.debug(f"API Key found: {self.api_key[:8]}...")
        
        try:
            self.client = Client(self.api_key, self.api_secret)
            logger.success("Binance client initialized successfully")
        except Exception as e:
            logger.exception(f"Failed to initialize Binance client: {e}")
            raise
        
        self._test_connection()
    
    def _test_connection(self):
        """Test API connection"""
        logger.info("Testing Binance API connection...")
        try:
            server_time = self.client.get_server_time()
            server_datetime = datetime.fromtimestamp(server_time['serverTime']/1000)
            logger.success(f"Connected to Binance | Server time: {server_datetime}")
        except Exception as e:
            logger.error(f"Failed to connect to Binance API: {e}")
            raise ConnectionError(f"Failed to connect to Binance: {e}")
    
    @logger.catch
    def fetch_ohlcv(self, 
                    ticker: str,
                    start_date: str = '2025-01-01',
                    end_date: str = '2025-05-29',
                    interval: str = '1d',
                    rate_limit_delay: float = 0.1) -> pl.DataFrame:
        """
        Fetch OHLCV data for a single ticker
        """
        logger.info(f"Fetching data | Ticker: {ticker} | Period: {start_date} to {end_date} | Interval: {interval}")
        
        # Validate interval
        interval_constant = self.INTERVAL_MAP.get(interval.lower())
        if not interval_constant:
            logger.error(f"Invalid interval: {interval}")
            raise ValueError(f"Invalid interval: {interval}. Valid intervals: {list(self.INTERVAL_MAP.keys())}")
        
        # Add rate limit delay
        time.sleep(rate_limit_delay)
        
        try:
            klines = self.client.get_historical_klines(
                symbol=ticker,
                interval=interval_constant,
                start_str=start_date,
                end_str=end_date
            )
            
            if not klines:
                logger.warning(f"No data returned for {ticker}")
                return pl.DataFrame()  # Return empty DataFrame instead of raising
            
            logger.success(f"Retrieved {len(klines)} klines for {ticker}")
            
        except Exception as e:
            logger.error(f"Failed to fetch data for {ticker}: {e}")
            return pl.DataFrame()  # Return empty DataFrame on error
        
        # Process with Polars
        df = self._process_klines(klines, ticker, interval)
        return df
    
    def fetch_multiple_tickers(self,
                             tickers: List[str],
                             start_date: str = '2025-01-01',
                             end_date: str = '2025-05-29',
                             interval: str = '1d',
                             max_workers: int = 5,
                             rate_limit_delay: float = 0.1) -> Dict[str, pl.DataFrame]:
        """
        Fetch OHLCV data for multiple tickers concurrently
        
        Returns a dictionary with ticker symbols as keys and DataFrames as values
        """
        logger.info(f"Fetching data for {len(tickers)} tickers using {max_workers} workers")
        
        results = {}
        failed_tickers = []
        
        # Sequential approach for small number of tickers
        if len(tickers) <= 3:
            for ticker in tickers:
                df = self.fetch_ohlcv(ticker, start_date, end_date, interval, rate_limit_delay)
                if not df.is_empty():
                    results[ticker] = df
                else:
                    failed_tickers.append(ticker)
        else:
            # Concurrent approach for larger number of tickers
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_ticker = {
                    executor.submit(
                        self.fetch_ohlcv,
                        ticker,
                        start_date,
                        end_date,
                        interval,
                        rate_limit_delay
                    ): ticker
                    for ticker in tickers
                }
                
                for future in as_completed(future_to_ticker):
                    ticker = future_to_ticker[future]
                    try:
                        df = future.result()
                        if not df.is_empty():
                            results[ticker] = df
                        else:
                            failed_tickers.append(ticker)
                    except Exception as e:
                        logger.error(f"Error processing {ticker}: {e}")
                        failed_tickers.append(ticker)
        
        logger.info(f"Successfully fetched {len(results)} tickers")
        if failed_tickers:
            logger.warning(f"Failed to fetch {len(failed_tickers)} tickers: {failed_tickers}")
        
        return results
    
    def combine_tickers_data(self, data_dict: Dict[str, pl.DataFrame]) -> pl.DataFrame:
        """
        Combine multiple ticker DataFrames into a single DataFrame
        """
        if not data_dict:
            logger.warning("No data to combine")
            return pl.DataFrame()
        
        logger.info(f"Combining data from {len(data_dict)} tickers")
        
        # Concatenate all DataFrames
        combined_df = pl.concat(list(data_dict.values()), how="vertical")
        
        # Sort by ticker and date
        combined_df = combined_df.sort(['ticker', 'date'])
        
        logger.success(f"Combined DataFrame shape: {combined_df.shape}")
        return combined_df
    
    def _process_klines(self, klines: list, ticker: str, interval: str) -> pl.DataFrame:
        """Process raw klines data into clean Polars DataFrame"""
        
        schema = {
            'timestamp': pl.Int64,
            'open': pl.Utf8,
            'high': pl.Utf8,
            'low': pl.Utf8,
            'close': pl.Utf8,
            'volume': pl.Utf8,
            'close_time': pl.Int64,
            'quote_volume': pl.Utf8,
            'trades': pl.Int64,
            'taker_buy_base': pl.Utf8,
            'taker_buy_quote': pl.Utf8,
            'ignore': pl.Utf8
        }
        
        try:
            df = pl.DataFrame(klines, schema=schema)
            
            processed_df = (
                df.lazy()
                .select([
                    pl.col('timestamp').cast(pl.Datetime('ms')).alias('date'),
                    pl.col('open').cast(pl.Float64),
                    pl.col('high').cast(pl.Float64),
                    pl.col('low').cast(pl.Float64),
                    pl.col('close').cast(pl.Float64),
                    pl.col('volume').cast(pl.Float64),
                ])
                .with_columns([
                    pl.lit(ticker).alias('ticker'),
                    pl.lit(interval).alias('interval')
                ])
                .sort('date')
                .collect()
            )
            
            return processed_df
            
        except Exception as e:
            logger.exception(f"Failed to process klines data: {e}")
            raise
    
    @logger.catch
    def export_to_excel(self, 
                       df: pl.DataFrame, 
                       filename: str = 'crypto_data.xlsx',
                       separate_sheets: bool = False):
        """
        Export DataFrame to Excel
        
        If separate_sheets is True and df contains multiple tickers,
        each ticker will be on its own sheet
        """
        logger.info(f"Exporting data to Excel: {filename}")
        
        try:
            if separate_sheets and 'ticker' in df.columns:
                # Get unique tickers
                tickers = df['ticker'].unique().to_list()
                
                if len(tickers) > 1:
                    logger.info(f"Exporting {len(tickers)} tickers to separate sheets")
                    
                    # Create Excel writer
                    with pd.ExcelWriter(filename, engine='openpyxl') as writer:
                        for ticker in tickers:
                            ticker_df = df.filter(pl.col('ticker') == ticker)
                            # Convert to pandas for Excel export with sheets
                            ticker_pd = ticker_df.to_pandas()
                            ticker_pd.to_excel(writer, sheet_name=ticker, index=False)
                    
                    file_size = os.path.getsize(filename) / 1024
                    logger.success(f"Exported to {filename} with {len(tickers)} sheets | Size: {file_size:.2f} KB")
                    return
            
            # Default: export as single sheet
            df.write_excel(filename)
            file_size = os.path.getsize(filename) / 1024
            logger.success(f"Exported {len(df)} rows to {filename} | Size: {file_size:.2f} KB")
            
        except Exception as e:
            logger.error(f"Failed to export to Excel: {e}")
            raise
    
    def get_summary_stats_by_ticker(self, df: pl.DataFrame) -> pl.DataFrame:
        """Calculate summary statistics grouped by ticker"""
        logger.debug("Calculating summary statistics by ticker")
        
        if 'ticker' not in df.columns:
            return self.get_summary_stats(df)
        
        try:
            stats = (
                df.group_by('ticker')
                .agg([
                    pl.col('open').mean().alias('open_mean'),
                    pl.col('high').mean().alias('high_mean'),
                    pl.col('low').mean().alias('low_mean'),
                    pl.col('close').mean().alias('close_mean'),
                    pl.col('volume').mean().alias('volume_mean'),
                    pl.col('close').std().alias('close_std'),
                    pl.col('volume').std().alias('volume_std'),
                    pl.col('date').min().alias('start_date'),
                    pl.col('date').max().alias('end_date'),
                    pl.col('date').count().alias('data_points')
                ])
                .sort('ticker')
            )
            
            logger.debug("Summary statistics calculated successfully")
            return stats
            
        except Exception as e:
            logger.error(f"Failed to calculate statistics: {e}")
            raise
    
    def get_summary_stats(self, df: pl.DataFrame) -> pl.DataFrame:
        """Calculate summary statistics"""
        try:
            stats = df.select([
                pl.col('open', 'high', 'low', 'close', 'volume').mean().name.suffix('_mean'),
                pl.col('open', 'high', 'low', 'close', 'volume').std().name.suffix('_std'),
                pl.col('open', 'high', 'low', 'close', 'volume').min().name.suffix('_min'),
                pl.col('open', 'high', 'low', 'close', 'volume').max().name.suffix('_max'),
                pl.col('open', 'high', 'low', 'close', 'volume').median().name.suffix('_median')
            ])
            return stats
        except Exception as e:
            logger.error(f"Failed to calculate statistics: {e}")
            raise

# --- Utility functions ---
def parse_tickers(ticker_input: str) -> List[str]:
    """
    Parse ticker input which can be:
    - Single ticker: "BTCUSDT"
    - Comma-separated: "BTCUSDT,ETHUSDT,BNBUSDT"
    - File path: "@tickers.txt" (each ticker on new line)
    """
    if ticker_input.startswith('@'):
        # Read from file
        file_path = ticker_input[1:]
        logger.info(f"Reading tickers from file: {file_path}")
        
        try:
            with open(file_path, 'r') as f:
                tickers = [line.strip() for line in f if line.strip()]
            logger.success(f"Loaded {len(tickers)} tickers from file")
            return tickers
        except Exception as e:
            logger.error(f"Failed to read ticker file: {e}")
            raise
    
    elif ',' in ticker_input:
        # Comma-separated list
        tickers = [t.strip() for t in ticker_input.split(',') if t.strip()]
        logger.info(f"Parsed {len(tickers)} tickers from comma-separated list")
        return tickers
    
    else:
        # Single ticker
        return [ticker_input.strip()]

# --- Main execution ---
def main():
    parser = argparse.ArgumentParser(
        description='Fetch crypto data from Binance using Polars',
        epilog="""
Examples:
  # Single ticker
  python script.py --ticker BTCUSDT
  
  # Multiple tickers
  python script.py --ticker "BTCUSDT,ETHUSDT,BNBUSDT"
  
  # From file
  python script.py --ticker @tickers.txt
  
  # Export each ticker to separate sheet
  python script.py --ticker "BTCUSDT,ETHUSDT" --separate-sheets
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('--ticker', default='BTCUSDT', 
                       help='Single ticker, comma-separated list, or @filename')
    parser.add_argument('--start', default='2025-01-01', 
                       help='Start date YYYY-MM-DD (default: 2025-01-01)')
    parser.add_argument('--end', default='2025-05-29', 
                       help='End date YYYY-MM-DD (default: 2025-05-29)')
    parser.add_argument('--interval', default='1d', 
                       help='Interval: 1m, 5m, 1h, 1d, etc. (default: 1d)')
    parser.add_argument('--output', default='crypto_data.xlsx', 
                       help='Output filename (default: crypto_data.xlsx)')
    parser.add_argument('--separate-sheets', action='store_true',
                       help='Export each ticker to a separate Excel sheet')
    parser.add_argument('--combine', action='store_true',
                       help='Combine all tickers into single DataFrame (default: True for multiple tickers)')
    parser.add_argument('--max-workers', type=int, default=5,
                       help='Maximum concurrent workers for fetching (default: 5)')
    parser.add_argument('--rate-limit', type=float, default=0.1,
                       help='Delay between API calls in seconds (default: 0.1)')
    parser.add_argument('--debug', action='store_true', 
                       help='Enable debug logging')
    
    args = parser.parse_args()
    
    # Adjust logging level if debug flag is set
    if args.debug:
        logger.remove()
        logger.add(sys.stdout, level="DEBUG")
        logger.debug("Debug logging enabled")
    
    # Parse tickers
    try:
        tickers = parse_tickers(args.ticker)
    except Exception as e:
        logger.error(f"Failed to parse tickers: {e}")
        return 1
    
    logger.info("Starting Binance data fetcher")
    logger.info(f"Tickers: {tickers}")
    logger.info(f"Parameters: start={args.start}, end={args.end}, interval={args.interval}")
    
    try:
        # Initialize fetcher
        fetcher = BinanceDataFetcher()
        
        if len(tickers) == 1:
            # Single ticker - simple fetch
            df = fetcher.fetch_ohlcv(
                ticker=tickers[0],
                start_date=args.start,
                end_date=args.end,
                interval=args.interval
            )
            
            if df.is_empty():
                logger.error(f"No data retrieved for {tickers[0]}")
                return 1
            
            # Export to Excel
            fetcher.export_to_excel(df, args.output)
            
            # Show summary
            print(f"\n📊 Data Summary for {tickers[0]}")
            print(f"Shape: {df.shape}")
            print(f"Date range: {df['date'].min()} to {df['date'].max()}")
            print("\nStatistics:")
            print(fetcher.get_summary_stats(df))
            
        else:
            # Multiple tickers
            data_dict = fetcher.fetch_multiple_tickers(
                tickers=tickers,
                start_date=args.start,
                end_date=args.end,
                interval=args.interval,
                max_workers=args.max_workers,
                rate_limit_delay=args.rate_limit
            )
            
            if not data_dict:
                logger.error("No data retrieved for any ticker")
                return 1
            
            # Combine or keep separate based on user preference
            if args.combine or not args.separate_sheets:
                # Combine all data
                df = fetcher.combine_tickers_data(data_dict)
                
                # Export
                fetcher.export_to_excel(df, args.output, args.separate_sheets)
                
                # Show summary
                print(f"\n📊 Combined Data Summary")
                print(f"Tickers: {sorted(data_dict.keys())}")
                print(f"Total shape: {df.shape}")
                print(f"Date range: {df['date'].min()} to {df['date'].max()}")
                print("\nStatistics by ticker:")
                print(fetcher.get_summary_stats_by_ticker(df))
                
            else:
                # Export each ticker to separate file
                for ticker, df in data_dict.items():
                    output_file = args.output.replace('.xlsx', f'_{ticker}.xlsx')
                    fetcher.export_to_excel(df, output_file)
                
                print(f"\n📊 Exported {len(data_dict)} separate files")
        
        # Save as parquet for faster loading
        if args.output.endswith('.xlsx'):
            parquet_file = args.output.replace('.xlsx', '.parquet')
            try:
                if 'df' in locals():
                    df.write_parquet(parquet_file)
                    logger.success(f"Also saved as {parquet_file}")
            except Exception as e:
                logger.warning(f"Failed to save parquet: {e}")
        
        logger.success("Data fetching completed successfully! ✨")
        
    except KeyboardInterrupt:
        logger.warning("Process interrupted by user")
        return 1
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    # For pandas Excel writer
    import pandas as pd
    exit(main())