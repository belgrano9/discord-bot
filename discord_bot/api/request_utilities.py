"""
Common utilities for API request handling and response processing.
Provides reusable functions for HTTP requests, authentication, and error handling.
"""

import requests
import asyncio
import time
import os
from typing import Dict, Any, Optional, Tuple
import urllib.parse
from functools import wraps

# Import your preferred logging module
from loguru import logger


class APIError(Exception):
    """Exception raised for API errors."""
    
    def __init__(self, message: str, status_code: Optional[int] = None, response: Any = None):
        self.message = message
        self.status_code = status_code
        self.response = response
        super().__init__(self.message)


def get_env_var(key: str, default: str = "", required: bool = False) -> str:
    """
    Get environment variable with validation.
    
    Args:
        key: Environment variable name
        default: Default value if not set
        required: Whether the variable is required
        
    Returns:
        Environment variable value or default
        
    Raises:
        ValueError: If the variable is required but not set
    """
    value = os.getenv(key, default)
    if required and not value:
        logger.error(f"Required environment variable {key} is not set!")
        raise ValueError(f"Required environment variable {key} is not set!")
    return value


def log_api_request(func):
    """
    Decorator to log API requests and responses.
    
    Args:
        func: The API request function to wrap
        
    Returns:
        Wrapped function with logging
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Extract method and endpoint from args or kwargs
        method = kwargs.get('method', args[1] if len(args) > 1 else 'GET')
        endpoint = kwargs.get('endpoint', args[2] if len(args) > 2 else 'unknown')
        
        # Log the request
        logger.debug(f"API Request: {method} {endpoint}")
        
        # Call the original function
        start_time = time.time()
        try:
            response = func(*args, **kwargs)
            
            # Log the response
            elapsed = time.time() - start_time
            if isinstance(response, dict) and 'code' in response:
                status = response.get('code')
                logger.debug(f"API Response: {status} ({elapsed:.2f}s)")
            else:
                logger.debug(f"API Response: Success ({elapsed:.2f}s)")
                
            return response
        except Exception as e:
            # Log the error
            elapsed = time.time() - start_time
            logger.error(f"API Error: {str(e)} ({elapsed:.2f}s)")
            raise
            
    return wrapper


def rate_limited(max_calls: int, time_frame: int = 60):
    """
    Decorator to rate limit API calls.
    
    Args:
        max_calls: Maximum number of calls in the time frame
        time_frame: Time frame in seconds
        
    Returns:
        Decorator function
    """
    calls = []
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            now = time.time()
            
            # Remove calls outside the time frame
            calls[:] = [call for call in calls if call > now - time_frame]
            
            # Check if we've exceeded the rate limit
            if len(calls) >= max_calls:
                sleep_time = calls[0] - (now - time_frame)
                if sleep_time > 0:
                    logger.warning(f"Rate limit reached. Sleeping for {sleep_time:.2f}s")
                    time.sleep(sleep_time)
            
            # Add this call
            calls.append(now)
            
            # Call the original function
            return func(*args, **kwargs)
        return wrapper
    return decorator


async def async_request(
    method: str,
    url: str,
    headers: Dict[str, str] = None,
    params: Dict[str, Any] = None,
    json_data: Dict[str, Any] = None,
    timeout: int = 10,
    retries: int = 3,
    backoff_factor: float = 0.5
) -> Dict[str, Any]:
    """
    Make an asynchronous HTTP request to an API.
    
    Args:
        method: HTTP method (GET, POST, etc.)
        url: URL to request
        headers: Optional headers
        params: Optional query parameters
        json_data: Optional JSON data for POST requests
        timeout: Request timeout in seconds
        retries: Number of retries on failure
        backoff_factor: Backoff factor for retries
        
    Returns:
        Parsed JSON response
        
    Raises:
        APIError: On request failure after retries
    """
    loop = asyncio.get_event_loop()
    
    # Define the synchronous request function to run in executor
    def make_request():
        for attempt in range(retries):
            try:
                response = requests.request(
                    method=method,
                    url=url,
                    headers=headers,
                    params=params,
                    json=json_data,
                    timeout=timeout
                )
                
                # Check for HTTP errors
                response.raise_for_status()
                
                # Parse and return JSON
                return response.json()
                
            except requests.exceptions.RequestException as e:
                # Log the error
                logger.warning(f"Request failed (attempt {attempt+1}/{retries}): {str(e)}")
                
                # If this was the last attempt, raise the error
                if attempt == retries - 1:
                    # Try to extract response data if available
                    error_response = None
                    status_code = None
                    
                    if hasattr(e, 'response') and e.response is not None:
                        status_code = e.response.status_code
                        try:
                            error_response = e.response.json()
                        except:
                            error_response = e.response.text
                    
                    # Don't retry, re-raise as APIError
                    raise APIError(
                        message=f"Request failed after {retries} attempts: {str(e)}",
                        status_code=status_code,
                        response=error_response
                    )
                
                # Exponential backoff
                sleep_time = backoff_factor * (2 ** attempt)
                time.sleep(sleep_time)
    
    # Run the request in a thread pool
    try:
        return await loop.run_in_executor(None, make_request)
    except Exception as e:
        # Re-raise with consistent error type
        if isinstance(e, APIError):
            raise e
        raise APIError(f"Unexpected error during request: {str(e)}")


def build_url_with_params(base_url: str, endpoint: str, params: Dict[str, Any] = None) -> str:
    """
    Build a URL with properly encoded query parameters.
    
    Args:
        base_url: Base URL
        endpoint: API endpoint
        params: Query parameters
        
    Returns:
        Full URL with encoded parameters
    """
    # Ensure there's no double slash between base_url and endpoint
    if base_url.endswith('/') and endpoint.startswith('/'):
        endpoint = endpoint[1:]
    elif not base_url.endswith('/') and not endpoint.startswith('/'):
        endpoint = '/' + endpoint
    
    url = base_url + endpoint
    
    # Add query parameters if provided
    if params:
        # Filter out None values
        filtered_params = {k: v for k, v in params.items() if v is not None}
        if filtered_params:
            query_string = urllib.parse.urlencode(filtered_params)
            url = f"{url}?{query_string}"
    
    return url


def process_response(
    response: Dict[str, Any],
    success_path: str = None,
    error_path: str = None,
    default_value: Any = None
) -> Tuple[bool, Any, Optional[str]]:
    """
    Process API response to extract data and errors consistently.
    
    Args:
        response: API response dictionary
        success_path: Dot-separated path to success data (e.g., "data.items")
        error_path: Dot-separated path to error message
        default_value: Default value if success_path is not found
        
    Returns:
        Tuple of (success, data, error_message)
    """
    # Check if response is None
    if response is None:
        return False, default_value, "No response received"
    
    # Extract error message if present
    error_message = None
    if error_path:
        parts = error_path.split('.')
        error_data = response
        for part in parts:
            if isinstance(error_data, dict) and part in error_data:
                error_data = error_data[part]
            else:
                error_data = None
                break
        error_message = str(error_data) if error_data else None
    
    # Check for common error indicators
    is_success = True
    if 'error' in response:
        is_success = False
        error_message = error_message or response.get('error')
    elif 'code' in response and str(response['code']) not in ['0', '200', '200000']:
        is_success = False
        error_message = error_message or response.get('msg', f"Error code: {response['code']}")
    
    # Extract success data if present
    data = default_value
    if success_path and is_success:
        parts = success_path.split('.')
        success_data = response
        for part in parts:
            if isinstance(success_data, dict) and part in success_data:
                success_data = success_data[part]
            else:
                success_data = default_value
                break
        data = success_data
    
    return is_success, data, error_message