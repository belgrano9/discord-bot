# Configuration for stock alerts
ALERT_CHANNEL_ID = 1344038761868165211

# Stocks to monitor: symbol -> {threshold_low, threshold_high}
STOCKS = {
    "AAPL": {"low": 242.0, "high": 245.0},
    "NVDA": {"low": 130.0, "high": 135.0},
}

# Check interval in seconds
CHECK_INTERVAL = 180  # 1 hour

# Add to config.py
# Portfolio positions: symbol -> {shares, entry_price}
PORTFOLIO = {
    "AAPL": {"shares": 2, "entry_price": 244.765},
    "NVDA": {"shares": 4, "entry_price": 126.50},
    "RXRX": {"shares": 19, "entry_price": 8.205},
}

# Portfolio update interval in seconds
PORTFOLIO_UPDATE_INTERVAL = 180  # 1 hour

# Channel to post portfolio updates
PORTFOLIO_CHANNEL_ID = 1344038761868165211  # Using the same channel as alerts
