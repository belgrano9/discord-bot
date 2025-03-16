"""
Base classes for asynchronous API clients.
Provides standardized request handling, error processing, and response formatting.
"""

import asyncio
from abc import ABC
from typing import Dict, Any, Optional, Union, List, Tuple
from loguru import logger

from .request_utilities import (
    async_request,
    APIError,
    build_url_with_params,
    process_response,
)


class AsyncBaseAPI(ABC):
    """
    Base class for asynchronous API clients with common functionality.
    
    Provides:
    - Async HTTP request methods
    - Standardized error handling
    - Environment variable management
    - Consistent response formatting
    """
    
    def __init__(self, base_url: str, api_key: Optional[str] = None):
        """
        Initialize the async API client.
        
        Args:
            base_url: Base URL for API requests
            api_key: Optional API key for authentication
        """
        self.base_url = base_url
        self.api_key = api_key
        self.default_headers = {}
        
        if api_key:
            self.default_headers["X-API-KEY"] = api_key
    
    async def request(
        self,
        method: str,
        endpoint: str,
        params: Dict[str, Any] = None,
        data: Dict[str, Any] = None,
        headers: Dict[str, Any] = None,
        timeout: int = 10,
        retries: int = 3
    ) -> Dict[str, Any]:
        """
        Make an asynchronous request to the API.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint
            params: Query parameters
            data: JSON data for POST/PUT requests
            headers: Additional headers
            timeout: Request timeout in seconds
            retries: Number of retries on failure
            
        Returns:
            Response data as a dictionary
            
        Raises:
            APIError: On request failure
        """
        # Merge headers with defaults
        request_headers = self.default_headers.copy()
        if headers:
            request_headers.update(headers)
            
        # Build the URL
        url = build_url_with_params(self.base_url, endpoint, params)
        
        # Log the request (not including sensitive headers)
        logger.debug(f"API Request: {method} {endpoint}")
        
        try:
            # Make the async request
            start_time = asyncio.get_event_loop().time()
            response = await async_request(
                method=method,
                url=url,
                headers=request_headers,
                json_data=data,
                timeout=timeout,
                retries=retries
            )
            elapsed = asyncio.get_event_loop().time() - start_time
            
            # Log the response time
            logger.debug(f"API Response received in {elapsed:.2f}s")
            
            return response
            
        except APIError as e:
            # Log the error
            logger.error(f"API Error: {e.message} (Status: {e.status_code})")
            
            # Re-raise with additional context
            raise APIError(
                message=f"Error in {method} request to {endpoint}: {e.message}",
                status_code=e.status_code,
                response=e.response
            )
    
    async def get(
        self,
        endpoint: str,
        params: Dict[str, Any] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Make a GET request to the API.
        
        Args:
            endpoint: API endpoint
            params: Query parameters
            **kwargs: Additional arguments for request method
            
        Returns:
            Response data
        """
        return await self.request("GET", endpoint, params=params, **kwargs)
    
    async def post(
        self,
        endpoint: str,
        data: Dict[str, Any] = None,
        params: Dict[str, Any] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Make a POST request to the API.
        
        Args:
            endpoint: API endpoint
            data: JSON data
            params: Query parameters
            **kwargs: Additional arguments for request method
            
        Returns:
            Response data
        """
        return await self.request("POST", endpoint, params=params, data=data, **kwargs)
    
    async def process_response(
        self,
        response: Dict[str, Any],
        success_path: str = None,
        error_path: str = None,
        default_value: Any = None
    ) -> Tuple[bool, Any, Optional[str]]:
        """
        Process API response to extract data and errors consistently.
        
        Args:
            response: API response dictionary
            success_path: Dot-separated path to success data
            error_path: Dot-separated path to error message
            default_value: Default value if success_path is not found
            
        Returns:
            Tuple of (success, data, error_message)
        """
        return process_response(
            response=response,
            success_path=success_path,
            error_path=error_path,
            default_value=default_value
        )


class ApiKeyRequiredError(Exception):
    """Exception raised when an API key is required but not provided."""
    pass


def require_api_key(func):
    """
    Decorator to ensure API key is set before calling a method.
    
    Args:
        func: The API method to wrap
        
    Returns:
        Wrapped function that checks for API key
        
    Raises:
        ApiKeyRequiredError: If API key is not set
    """
    async def wrapper(self, *args, **kwargs):
        if not hasattr(self, 'api_key') or not self.api_key:
            raise ApiKeyRequiredError(f"API key is required for {func.__name__}")
        return await func(self, *args, **kwargs)
    return wrapper