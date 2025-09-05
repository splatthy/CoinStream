"""
Bitunix exchange integration client.

This module provides the Bitunix-specific implementation of the BaseExchange interface,
handling authentication, API communication, and data parsing for Bitunix exchange.
"""

import hashlib
import hmac
import logging
import time
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

import requests

from ..models.position import Position, PositionSide, PositionStatus
from .base_exchange import (
    APIError,
    AuthenticationError,
    BaseExchange,
    NetworkError,
    RateLimitConfig,
    RateLimitError,
)


class BitunixClient(BaseExchange):
    """
    Bitunix exchange API client implementing the BaseExchange interface.

    This client handles authentication using API key headers, fetches position history,
    and parses Bitunix-specific API responses into standardized Position objects.
    """

    def __init__(self, api_key: str, api_secret: str = None):
        # Bitunix rate limits (conservative estimates)
        rate_limit_config = RateLimitConfig(
            requests_per_second=2.0, requests_per_minute=100, requests_per_hour=2000
        )

        super().__init__(
            name="bitunix",
            api_key=api_key,
            api_secret=api_secret,
            rate_limit_config=rate_limit_config,
        )

        self.logger = logging.getLogger("exchange.bitunix")

    @property
    def base_url(self) -> str:
        """Base URL for Bitunix Futures API."""
        return "https://fapi.bitunix.com"

    @property
    def supported_endpoints(self) -> List[str]:
        """List of supported Bitunix API endpoints."""
        return [
            "/api/v1/common/time",
            "/api/v1/future/position",
            "/api/v1/future/order/history",
        ]

    def _prepare_auth_headers(
        self, method: str = "GET", endpoint: str = "", params: str = "", body: str = ""
    ) -> Dict[str, str]:
        """
        Prepare authentication headers for Bitunix API requests.

        Bitunix uses API key + secret with HMAC-SHA256 signature authentication.

        Returns:
            Dict[str, str]: Authentication headers
        """
        timestamp = str(int(time.time() * 1000))

        headers = {
            "BX-APIKEY": self.api_key,
            "BX-TIMESTAMP": timestamp,
            "Content-Type": "application/json",
            "User-Agent": "CryptoTradingJournal/1.0",
        }

        # If API secret is provided, add signature-based authentication
        if self.api_secret:
            # Create signature according to Bitunix GitHub demo
            # Format: timestamp + method + endpoint + params + body
            query_string = params if params else ""
            message = timestamp + method.upper() + endpoint + query_string + body

            signature = hmac.new(
                self.api_secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256
            ).hexdigest()

            headers["BX-SIGNATURE"] = signature

        return headers

    def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        data: Optional[Dict] = None,
        require_auth: bool = True,
    ) -> requests.Response:
        """
        Make an authenticated API request with Bitunix-specific signature.
        """
        # Apply rate limiting
        self.rate_limiter.acquire_sync()

        # Prepare URL
        url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"

        # Prepare query string for signature
        query_string = ""
        if params:
            query_string = "&".join([f"{k}={v}" for k, v in sorted(params.items())])

        # Prepare body for signature
        body_string = ""
        if data:
            import json

            body_string = json.dumps(data, separators=(",", ":"))

        # Prepare headers with signature
        if require_auth:
            headers = self._prepare_auth_headers(
                method, endpoint, query_string, body_string
            )
        else:
            headers = {
                "Content-Type": "application/json",
                "User-Agent": "CryptoTradingJournal/1.0",
            }

        try:
            self.logger.debug(f"Making {method} request to {url}")
            if query_string:
                self.logger.debug(f"Query params: {query_string}")

            response = self.session.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                json=data,
                timeout=30,
            )

            # Handle rate limiting
            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", 60))
                raise RateLimitError(
                    f"Rate limit exceeded for {self.name}",
                    retry_after=retry_after,
                    status_code=429,
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

    def _handle_api_error(self, response: requests.Response) -> None:
        """
        Handle Bitunix API error responses and raise appropriate exceptions.

        Args:
            response: The HTTP response object

        Raises:
            AuthenticationError: For authentication-related errors
            APIError: For other API errors
        """
        self.logger.debug(f"Handling API error - Status: {response.status_code}")
        self.logger.debug(f"Response text: {response.text}")

        try:
            error_data = response.json()
            self.logger.debug(f"Parsed error data type: {type(error_data)}")
            self.logger.debug(f"Parsed error data: {error_data}")
        except ValueError as e:
            self.logger.debug(f"Failed to parse JSON error response: {e}")
            error_data = {"message": response.text or "Unknown error"}

        # Ensure error_data is a dictionary
        if not isinstance(error_data, dict):
            self.logger.error(
                f"Expected dict for error_data, got {type(error_data)}: {error_data}"
            )
            error_data = {"message": str(error_data)}

        error_message = error_data.get("message", response.text or "Unknown API error")
        error_code = error_data.get("code", str(response.status_code))

        self.logger.error(
            f"Bitunix API error: {error_code} - {error_message} "
            f"(HTTP {response.status_code})"
        )

        if response.status_code in [401, 403]:
            raise AuthenticationError(
                message=f"Authentication failed: {error_message}",
                error_code=error_code,
                status_code=response.status_code,
            )

        raise APIError(
            message=f"API error: {error_message}",
            error_code=error_code,
            status_code=response.status_code,
        )

    def _parse_position_data(self, raw_data: Dict) -> Position:
        """
        Parse raw position data from Bitunix API into a Position object.

        Args:
            raw_data: Raw position data from Bitunix API

        Returns:
            Position: Parsed position object

        Raises:
            ValueError: If required fields are missing or invalid
        """
        # Validate input type
        if not isinstance(raw_data, dict):
            raise ValueError(f"Expected dict, got {type(raw_data)}: {raw_data}")

        try:
            # Extract and validate required fields first
            position_id = raw_data.get("positionId") or raw_data.get("id")
            if not position_id:
                raise ValueError("Position ID is required")
            position_id = str(position_id)

            symbol = raw_data.get("symbol")
            if not symbol:
                raise ValueError("Symbol is required")

            # Parse position side
            side_str = raw_data.get("side", "").lower()
            if side_str == "long" or side_str == "buy":
                side = PositionSide.LONG
            elif side_str == "short" or side_str == "sell":
                side = PositionSide.SHORT
            else:
                raise ValueError(f"Invalid position side: {side_str}")

            # Parse numeric fields with validation
            size_value = raw_data.get("size", 0)
            if not size_value:
                raise ValueError("Size is required")
            size = Decimal(str(size_value))

            entry_price_value = raw_data.get("entryPrice", 0)
            if not entry_price_value:
                raise ValueError("Entry price is required")
            entry_price = Decimal(str(entry_price_value))

            mark_price = Decimal(
                str(
                    raw_data.get("markPrice", raw_data.get("currentPrice", entry_price))
                )
            )
            unrealized_pnl = Decimal(str(raw_data.get("unrealizedPnl", 0)))
            realized_pnl = Decimal(str(raw_data.get("realizedPnl", 0)))

            # Parse status
            status_str = raw_data.get("status", "").lower()
            if status_str in ["open", "active"]:
                status = PositionStatus.OPEN
            elif status_str in ["closed", "filled"]:
                status = PositionStatus.CLOSED
            elif status_str in ["partially_closed", "partial"]:
                status = PositionStatus.PARTIALLY_CLOSED
            else:
                # Default to open if status is unclear
                status = PositionStatus.OPEN
                self.logger.warning(
                    f"Unknown position status '{status_str}', defaulting to OPEN"
                )

            # Parse timestamps
            open_time_ms = raw_data.get("openTime") or raw_data.get("createTime")
            if open_time_ms:
                open_time = datetime.fromtimestamp(int(open_time_ms) / 1000)
            else:
                open_time = datetime.now()
                self.logger.warning("No open time provided, using current time")

            close_time = None
            close_time_ms = raw_data.get("closeTime")
            if close_time_ms and int(close_time_ms) > 0:
                close_time = datetime.fromtimestamp(int(close_time_ms) / 1000)

            # Create Position object
            position = Position(
                position_id=position_id,
                symbol=symbol,
                side=side,
                size=size,
                entry_price=entry_price,
                mark_price=mark_price,
                unrealized_pnl=unrealized_pnl,
                realized_pnl=realized_pnl,
                status=status,
                open_time=open_time,
                close_time=close_time,
                raw_data=raw_data,
            )

            return position

        except (KeyError, ValueError, TypeError) as e:
            self.logger.error(f"Failed to parse position data: {str(e)}")
            self.logger.debug(f"Raw data: {raw_data}")
            raise ValueError(f"Invalid position data format: {str(e)}")

    def test_connection(self) -> bool:
        """
        Test the connection to Bitunix API.

        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            # Test multiple possible API endpoints to find the correct one
            test_endpoints = [
                "/api/v1/ping",
                "/ping",
                "/api/ping",
                "/v1/ping",
                "/api/v1/time",
                "/api/v1/server/time",
            ]

            for endpoint in test_endpoints:
                try:
                    url = f"{self.base_url}{endpoint}"
                    headers = {"User-Agent": "CryptoTradingJournal/1.0"}

                    self.logger.debug(f"Testing endpoint: {url}")
                    response = self.session.get(url, headers=headers, timeout=10)

                    self.logger.debug(
                        f"Endpoint {endpoint} response: {response.status_code}"
                    )
                    self.logger.debug(f"Response text: {response.text[:200]}")

                    # If we get a 200, that's success
                    if response.status_code == 200:
                        self.logger.info(f"Found working endpoint: {endpoint}")
                        return True

                except Exception as e:
                    self.logger.debug(f"Endpoint {endpoint} failed: {e}")
                    continue

            # Try the correct Bitunix server time endpoint
            try:
                response = self._make_request(
                    "GET", "/api/v1/common/time", require_auth=False
                )
                self.logger.debug(
                    f"Server time endpoint response: {response.status_code}"
                )
                self.logger.debug(f"Response content: {response.text}")
                return response.status_code == 200

            except Exception as e:
                self.logger.error(f"Server time test failed: {e}")
                return False

        except Exception as e:
            self.logger.error(f"Connection test failed: {str(e)}")
            return False

    def get_account_info(self) -> Dict[str, Any]:
        """
        Get account information from Bitunix API.

        Returns:
            Dict[str, Any]: Account information

        Raises:
            AuthenticationError: If not authenticated
            APIError: If API request fails
        """
        if not self.is_authenticated():
            if not self.authenticate():
                raise AuthenticationError("Failed to authenticate")

        try:
            response = self._make_request("GET", "/api/v1/account/info")
            return response.json()
        except requests.RequestException as e:
            raise NetworkError(f"Network error while fetching account info: {str(e)}")
        except Exception as e:
            raise APIError(f"Failed to fetch account info: {str(e)}")

    def get_position_history(
        self, since: Optional[datetime] = None, limit: Optional[int] = None
    ) -> List[Position]:
        """
        Get position history from Bitunix API with enhanced error handling.

        Args:
            since: Get positions since this datetime
            limit: Maximum number of positions to return (default: 100)

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
            # Convert to milliseconds timestamp
            params["startTime"] = int(since.timestamp() * 1000)
        if limit:
            params["limit"] = min(limit, 1000)  # Cap at 1000 per API limits
        else:
            params["limit"] = 100  # Default limit

        try:
            # Use the correct Bitunix futures position endpoint
            response = self._make_request(
                "GET", "/api/v1/future/position", params=params
            )

            # Debug the raw response
            self.logger.debug(f"Raw response status: {response.status_code}")
            self.logger.debug(f"Raw response headers: {dict(response.headers)}")
            self.logger.debug(
                f"Raw response text: {response.text[:500]}..."
            )  # First 500 chars

            try:
                response_data = response.json()
            except Exception as json_error:
                self.logger.error(f"Failed to parse JSON response: {json_error}")
                self.logger.error(f"Response content: {response.text}")
                raise APIError(f"Invalid JSON response from Bitunix API: {json_error}")

            # Log the actual response for debugging
            self.logger.debug(f"Bitunix API response type: {type(response_data)}")
            self.logger.debug(f"Bitunix API response: {response_data}")

            # Handle different response formats with better error handling
            raw_positions = []

            if isinstance(response_data, dict):
                # Try different possible keys for position data
                raw_positions = (
                    response_data.get("data")
                    or response_data.get("positions")
                    or response_data.get("result")
                    or []
                )

                # If we still don't have a list, check if the dict itself contains position data
                if not isinstance(raw_positions, list):
                    if all(key in response_data for key in ["positionId", "symbol"]):
                        # Single position returned as dict
                        raw_positions = [response_data]
                    else:
                        raw_positions = []

            elif isinstance(response_data, list):
                raw_positions = response_data
            else:
                # Handle unexpected response types
                self.logger.error(
                    f"Unexpected response type from Bitunix API: {type(response_data)}"
                )
                self.logger.error(f"Response content: {response_data}")
                raise APIError(
                    f"Unexpected response format from Bitunix API: {type(response_data)}"
                )

            # Ensure raw_positions is a list
            if not isinstance(raw_positions, list):
                self.logger.error(
                    f"Expected list of positions, got: {type(raw_positions)}"
                )
                self.logger.error(f"Raw positions data: {raw_positions}")
                raise APIError(
                    f"Invalid position data format: expected list, got {type(raw_positions)}"
                )

            positions = []
            parse_errors = 0

            for i, raw_pos in enumerate(raw_positions):
                try:
                    # Ensure each position is a dictionary
                    if not isinstance(raw_pos, dict):
                        self.logger.warning(
                            f"Position {i} is not a dict: {type(raw_pos)} - {raw_pos}"
                        )
                        parse_errors += 1
                        continue

                    position = self._parse_position_data(raw_pos)
                    positions.append(position)
                except Exception as e:
                    parse_errors += 1
                    self.logger.warning(f"Failed to parse position {i}: {str(e)}")
                    self.logger.debug(f"Raw position data: {raw_pos}")
                    continue

            if parse_errors > 0:
                self.logger.warning(
                    f"Failed to parse {parse_errors} out of {len(raw_positions)} positions"
                )

            self.logger.info(
                f"Successfully retrieved {len(positions)} positions from Bitunix"
            )
            return positions

        except requests.RequestException as e:
            raise NetworkError(f"Network error while fetching positions: {str(e)}")
        except Exception as e:
            if isinstance(e, (AuthenticationError, APIError, NetworkError)):
                raise
            raise APIError(f"Failed to fetch position history: {str(e)}")

    def get_position_by_id(self, position_id: str) -> Optional[Position]:
        """
        Get a specific position by ID.

        Args:
            position_id: The position ID to fetch

        Returns:
            Optional[Position]: The position if found, None otherwise
        """
        try:
            # This would typically be a separate endpoint, but we'll use the history endpoint
            # with filtering as a fallback
            positions = self.get_position_history(limit=1000)

            for position in positions:
                if position.position_id == position_id:
                    return position

            return None

        except Exception as e:
            self.logger.error(f"Failed to fetch position {position_id}: {str(e)}")
            return None
