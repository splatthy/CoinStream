"""
Abstract base class for exchange integrations.

This module provides the base interface and common functionality for all exchange
integrations, including authentication, rate limiting, and error handling.
"""

import time
import asyncio
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from decimal import Decimal
import logging
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from ..models.position import Position


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""
    requests_per_second: float
    requests_per_minute: int
    requests_per_hour: int
    burst_limit: int = 5


@dataclass
class ExchangeError(Exception):
    """Base exception for exchange-related errors."""
    message: str
    error_code: Optional[str] = None
    status_code: Optional[int] = None
    retry_after: Optional[int] = None


class AuthenticationError(ExchangeError):
    """Raised when authentication fails."""
    pass


class RateLimitError(ExchangeError):
    """Raised when rate limit is exceeded."""
    pass


class NetworkError(ExchangeError):
    """Raised when network operations fail."""
    pass


class APIError(ExchangeError):
    """Raised when API returns an error response."""
    pass


class RateLimiter:
    """Rate limiter for API requests."""
    
    def __init__(self, config: RateLimitConfig):
        self.config = config
        self.request_times: List[float] = []
        self.last_request_time = 0.0
        self._lock = asyncio.Lock() if asyncio.iscoroutinefunction(self.__init__) else None
    
    def can_make_request(self) -> bool:
        """Check if a request can be made without violating rate limits."""
        now = time.time()
        
        # Clean old request times
        cutoff_time = now - 3600  # 1 hour ago
        self.request_times = [t for t in self.request_times if t > cutoff_time]
        
        # Check various rate limits
        recent_requests = [t for t in self.request_times if t > now - 60]  # Last minute
        if len(recent_requests) >= self.config.requests_per_minute:
            return False
        
        if len(self.request_times) >= self.config.requests_per_hour:
            return False
        
        # Check requests per second
        if now - self.last_request_time < (1.0 / self.config.requests_per_second):
            return False
        
        return True
    
    def wait_time_until_next_request(self) -> float:
        """Calculate how long to wait before the next request can be made."""
        now = time.time()
        
        # Check requests per second limit
        time_since_last = now - self.last_request_time
        min_interval = 1.0 / self.config.requests_per_second
        if time_since_last < min_interval:
            return min_interval - time_since_last
        
        return 0.0
    
    def record_request(self):
        """Record that a request was made."""
        now = time.time()
        self.request_times.append(now)
        self.last_request_time = now
    
    async def acquire(self):
        """Acquire permission to make a request (async version)."""
        while not self.can_make_request():
            wait_time = self.wait_time_until_next_request()
            if wait_time > 0:
                await asyncio.sleep(wait_time)
            else:
                await asyncio.sleep(0.1)  # Small delay to prevent busy waiting
        
        self.record_request()
    
    def acquire_sync(self):
        """Acquire permission to make a request (sync version)."""
        while not self.can_make_request():
            wait_time = self.wait_time_until_next_request()
            if wait_time > 0:
                time.sleep(wait_time)
            else:
                time.sleep(0.1)  # Small delay to prevent busy waiting
        
        self.record_request()


class BaseExchange(ABC):
    """
    Abstract base class for exchange integrations.
    
    This class defines the interface that all exchange integrations must implement
    and provides common functionality for authentication, rate limiting, and error handling.
    """
    
    def __init__(self, name: str, api_key: str, api_secret: str = None, 
                 rate_limit_config: Optional[RateLimitConfig] = None):
        self.name = name
        self.api_key = api_key
        self.api_secret = api_secret
        self.logger = logging.getLogger(f"exchange.{name}")
        
        # Set up rate limiting
        self.rate_limit_config = rate_limit_config or RateLimitConfig(
            requests_per_second=1.0,
            requests_per_minute=60,
            requests_per_hour=1000
        )
        self.rate_limiter = RateLimiter(self.rate_limit_config)
        
        # Set up HTTP session with retry strategy
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # Authentication state
        self._authenticated = False
        self._auth_expires_at: Optional[datetime] = None
    
    @property
    @abstractmethod
    def base_url(self) -> str:
        """Base URL for the exchange API."""
        pass
    
    @property
    @abstractmethod
    def supported_endpoints(self) -> List[str]:
        """List of supported API endpoints."""
        pass
    
    @abstractmethod
    def _prepare_auth_headers(self) -> Dict[str, str]:
        """Prepare authentication headers for API requests."""
        pass
    
    @abstractmethod
    def _parse_position_data(self, raw_data: Dict) -> Position:
        """Parse raw position data from the exchange into a Position object."""
        pass
    
    @abstractmethod
    def _handle_api_error(self, response: requests.Response) -> None:
        """Handle API error responses and raise appropriate exceptions."""
        pass
    
    def authenticate(self) -> bool:
        """
        Authenticate with the exchange API.
        
        Returns:
            bool: True if authentication successful, False otherwise
            
        Raises:
            AuthenticationError: If authentication fails
        """
        try:
            # Test authentication with a simple API call
            success = self.test_connection()
            self._authenticated = success
            if success:
                self._auth_expires_at = datetime.now() + timedelta(hours=1)
                self.logger.info(f"Successfully authenticated with {self.name}")
            return success
        except Exception as e:
            self.logger.error(f"Authentication failed for {self.name}: {str(e)}")
            raise AuthenticationError(f"Authentication failed: {str(e)}")
    
    def is_authenticated(self) -> bool:
        """Check if currently authenticated and authentication hasn't expired."""
        if not self._authenticated:
            return False
        
        if self._auth_expires_at and datetime.now() > self._auth_expires_at:
            self._authenticated = False
            return False
        
        return True
    
    def test_connection(self) -> bool:
        """
        Test the API connection and authentication.
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            # This should be implemented by subclasses to make a simple API call
            # that verifies the connection and authentication
            response = self._make_request("GET", "/api/v1/ping", require_auth=False)
            return response.status_code == 200
        except Exception as e:
            self.logger.error(f"Connection test failed for {self.name}: {str(e)}")
            return False
    
    def get_position_history(self, since: Optional[datetime] = None, 
                           limit: Optional[int] = None) -> List[Position]:
        """
        Get position history from the exchange.
        
        Args:
            since: Get positions since this datetime
            limit: Maximum number of positions to return
            
        Returns:
            List[Position]: List of position objects
            
        Raises:
            AuthenticationError: If not authenticated
            APIError: If API request fails
        """
        if not self.is_authenticated():
            if not self.authenticate():
                raise AuthenticationError("Failed to authenticate")
        
        params = {}
        if since:
            params['since'] = int(since.timestamp() * 1000)  # Convert to milliseconds
        if limit:
            params['limit'] = limit
        
        try:
            response = self._make_request("GET", "/api/v1/position/history", params=params)
            raw_positions = response.json()
            
            positions = []
            for raw_pos in raw_positions.get('data', []):
                try:
                    position = self._parse_position_data(raw_pos)
                    positions.append(position)
                except Exception as e:
                    self.logger.warning(f"Failed to parse position data: {str(e)}")
                    continue
            
            self.logger.info(f"Retrieved {len(positions)} positions from {self.name}")
            return positions
            
        except requests.RequestException as e:
            raise NetworkError(f"Network error while fetching positions: {str(e)}")
        except Exception as e:
            raise APIError(f"Failed to fetch position history: {str(e)}")
    
    def _make_request(self, method: str, endpoint: str, params: Optional[Dict] = None,
                     data: Optional[Dict] = None, require_auth: bool = True) -> requests.Response:
        """
        Make an authenticated API request with rate limiting.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            params: Query parameters
            data: Request body data
            require_auth: Whether authentication is required
            
        Returns:
            requests.Response: The API response
            
        Raises:
            RateLimitError: If rate limit is exceeded
            NetworkError: If network request fails
            APIError: If API returns an error
        """
        # Apply rate limiting
        self.rate_limiter.acquire_sync()
        
        # Prepare URL
        url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        
        # Prepare headers
        headers = {"Content-Type": "application/json"}
        if require_auth:
            auth_headers = self._prepare_auth_headers()
            headers.update(auth_headers)
        
        try:
            self.logger.debug(f"Making {method} request to {url}")
            
            response = self.session.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                json=data,
                timeout=30
            )
            
            # Handle rate limiting
            if response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', 60))
                raise RateLimitError(
                    f"Rate limit exceeded for {self.name}",
                    retry_after=retry_after,
                    status_code=429
                )
            
            # Handle other API errors
            if not response.ok:
                self._handle_api_error(response)
            
            return response
            
        except requests.Timeout:
            raise NetworkError("Request timeout")
        except requests.ConnectionError as e:
            raise NetworkError(f"Connection error: {str(e)}")
        except requests.RequestException as e:
            raise NetworkError(f"Request failed: {str(e)}")
    
    def close(self):
        """Clean up resources."""
        if self.session:
            self.session.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()