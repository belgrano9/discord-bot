from loguru import logger
import sys
import os

# Create logs directory if it doesn't exist
os.makedirs("logs", exist_ok=True)

# Configure loguru
logger.remove()  # Remove default handler

# Add console handler with INFO level
logger.add(sys.stderr, level="INFO")

# Add file handler with more verbosity for debugging
logger.add(
    "logs/app_{time:YYYY-MM-DD}.log",
    rotation="1 day",    # New file is created each day
    retention="1 week",  # Logs are kept for 1 week
    level="DEBUG",       # Log everything at DEBUG level or higher
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} - {message}",
    backtrace=True,      # Include traceback for errors
    diagnose=True        # Even more detailed error information
)

def get_logger(name):
    """Get a logger with the specified name"""
    return logger.bind(name=name)