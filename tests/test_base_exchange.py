"""
Unit tests for the BaseExchange abstract class and related utilities.
"""

import pytest
import time
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import requests

from app.integrations.base_exchange import (
    BaseExchange, RateLimiter, RateLimitConfig,
    ExchangeError, AuthenticationError, RateLimitError, NetworkError, APIError
)
from app.models.position import Position, PositionSide, PositionStatus


class TestExchange(BaseExchange):
    """Test implementation of BaseExchange for testing."""
    
    @property
    def base_url(self) -> str:
        return "https://api.test-exchange.com"
    
    @property
    def supported_endpoints(self) -> list:
        return ["/api/v1/ping", "/api/v1/position/history"]
    
    def _prepare_auth_headers(self) -> dict:
        return {"X-API-Key": self.api_key}
    
    def _parse_position_data(self, raw_data: dict) -> Position:
        from decimal import Decimal
        return Position(
            position_id=raw_data["id"],
            symbol=raw_data["symbol"],
            side=PositionSide(raw_data["side"]),
            size=Decimal(str(raw_data["size"])),
            entry_price=Decimal(str(raw_data["entry_price"])),
            mark_price=Decimal(str(raw_data["mark_price"])),
            unrealized_pnl=Decimal(str(raw_data["unrealized_pnl"])),
            realized_pnl=Decimal(str(raw_data["realized_pnl"])),
            status=PositionStatus(raw_data["status"]),
            open_time=datetime.fromtimestamp(raw_data["open_time"] / 1000),
            close_time=datetime.fromtimestamp(raw_data["close_time"] / 1000) if raw_data.get("close_time") else None,
            raw_data=raw_data
        )
    
    def _handle_api_error(self, response: requests.Response) -> None:
        if response.status_code == 401:
            raise AuthenticationError("Invalid API key", status_code=401)
        elif response.status_code == 403:
            raise AuthenticationError("Access forbidden", status_code=403)
        else:
            raise APIError(f"API error: {response.status_code}", status_code=response.status_code)


class TestRateLimiter:
    """Test cases for RateLimiter class."""
    
    def test_rate_limiter_initialization(self):
        """Test RateLimiter initialization."""
        config = RateLimitConfig(
            requests_per_second=2.0,
            requests_per_minute=60,
            requests_per_hour=1000
        )
        limiter = RateLimiter(config)
        
        assert limiter.config == config
        assert limiter.request_times == []
        assert limiter.last_request_time == 0.0
    
    def test_can_make_request_initially(self):
        """Test that requests can be made initially."""
        config = RateLimitConfig(
            requests_per_second=1.0,
            requests_per_minute=60,
            requests_per_hour=1000
        )
        limiter = RateLimiter(config)
        
        assert limiter.can_make_request() is True
    
    def test_rate_limiting_per_second(self):
        """Test rate limiting per second."""
        config = RateLimitConfig(
            requests_per_second=2.0,  # 2 requests per second
            requests_per_minute=60,
            requests_per_hour=1000
        )
        limiter = RateLimiter(config)
        
        # First request should be allowed
        assert limiter.can_make_request() is True
        limiter.record_request()
        
        # Immediate second request should be blocked
        assert limiter.can_make_request() is False
        
        # Wait for minimum interval and try again
        time.sleep(0.6)  # Wait more than 0.5 seconds (1/2.0)
        assert limiter.can_make_request() is True
    
    def test_wait_time_calculation(self):
        """Test wait time calculation."""
        config = RateLimitConfig(
            requests_per_second=1.0,
            requests_per_minute=60,
            requests_per_hour=1000
        )
        limiter = RateLimiter(config)
        
        # Record a request
        limiter.record_request()
        
        # Should need to wait approximately 1 second
        wait_time = limiter.wait_time_until_next_request()
        assert 0.9 <= wait_time <= 1.0
    
    def test_acquire_sync(self):
        """Test synchronous acquire method."""
        config = RateLimitConfig(
            requests_per_second=10.0,  # High rate for faster testing
            requests_per_minute=600,
            requests_per_hour=10000
        )
        limiter = RateLimiter(config)
        
        # Should acquire immediately
        start_time = time.time()
        limiter.acquire_sync()
        end_time = time.time()
        
        # Should be very fast
        assert end_time - start_time < 0.2


class TestBaseExchange:
    """Test cases for BaseExchange abstract class."""
    
    def test_initialization(self):
        """Test BaseExchange initialization."""
        exchange = TestExchange("test", "api_key", "api_secret")
        
        assert exchange.name == "test"
        assert exchange.api_key == "api_key"
        assert exchange.api_secret == "api_secret"
        assert exchange.rate_limiter is not None
        assert exchange.session is not None
        assert exchange._authenticated is False
    
    def test_custom_rate_limit_config(self):
        """Test initialization with custom rate limit config."""
        config = RateLimitConfig(
            requests_per_second=5.0,
            requests_per_minute=300,
            requests_per_hour=5000
        )
        exchange = TestExchange("test", "api_key", rate_limit_config=config)
        
        assert exchange.rate_limit_config == config
        assert exchange.rate_limiter.config == config
    
    @patch('requests.Session.request')
    def test_make_request_success(self, mock_request):
        """Test successful API request."""
        mock_response = Mock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "success"}
        mock_request.return_value = mock_response
        
        exchange = TestExchange("test", "api_key")
        response = exchange._make_request("GET", "/api/v1/test", require_auth=False)
        
        assert response.status_code == 200
        mock_request.assert_called_once()
    
    @patch('requests.Session.request')
    def test_make_request_with_auth(self, mock_request):
        """Test API request with authentication."""
        mock_response = Mock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_request.return_value = mock_response
        
        exchange = TestExchange("test", "test_api_key")
        exchange._make_request("GET", "/api/v1/test", require_auth=True)
        
        # Check that auth headers were added
        call_args = mock_request.call_args
        headers = call_args[1]['headers']
        assert "X-API-Key" in headers
        assert headers["X-API-Key"] == "test_api_key"
    
    @patch('requests.Session.request')
    def test_make_request_rate_limit_error(self, mock_request):
        """Test handling of rate limit errors."""
        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.ok = False
        mock_response.headers = {"Retry-After": "60"}
        mock_request.return_value = mock_response
        
        exchange = TestExchange("test", "api_key")
        
        with pytest.raises(RateLimitError) as exc_info:
            exchange._make_request("GET", "/api/v1/test", require_auth=False)
        
        assert exc_info.value.retry_after == 60
        assert exc_info.value.status_code == 429
    
    @patch('requests.Session.request')
    def test_make_request_authentication_error(self, mock_request):
        """Test handling of authentication errors."""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.ok = False
        mock_request.return_value = mock_response
        
        exchange = TestExchange("test", "api_key")
        
        with pytest.raises(AuthenticationError):
            exchange._make_request("GET", "/api/v1/test")
    
    @patch('requests.Session.request')
    def test_make_request_network_error(self, mock_request):
        """Test handling of network errors."""
        mock_request.side_effect = requests.ConnectionError("Connection failed")
        
        exchange = TestExchange("test", "api_key")
        
        with pytest.raises(NetworkError):
            exchange._make_request("GET", "/api/v1/test", require_auth=False)
    
    @patch('requests.Session.request')
    def test_make_request_timeout(self, mock_request):
        """Test handling of request timeouts."""
        mock_request.side_effect = requests.Timeout("Request timeout")
        
        exchange = TestExchange("test", "api_key")
        
        with pytest.raises(NetworkError):
            exchange._make_request("GET", "/api/v1/test", require_auth=False)
    
    @patch.object(TestExchange, 'test_connection')
    def test_authenticate_success(self, mock_test_connection):
        """Test successful authentication."""
        mock_test_connection.return_value = True
        
        exchange = TestExchange("test", "api_key")
        result = exchange.authenticate()
        
        assert result is True
        assert exchange._authenticated is True
        assert exchange._auth_expires_at is not None
    
    @patch.object(TestExchange, 'test_connection')
    def test_authenticate_failure(self, mock_test_connection):
        """Test authentication failure."""
        mock_test_connection.return_value = False
        
        exchange = TestExchange("test", "api_key")
        result = exchange.authenticate()
        
        assert result is False
        assert exchange._authenticated is False
    
    @patch.object(TestExchange, 'test_connection')
    def test_authenticate_exception(self, mock_test_connection):
        """Test authentication with exception."""
        mock_test_connection.side_effect = Exception("Connection failed")
        
        exchange = TestExchange("test", "api_key")
        
        with pytest.raises(AuthenticationError):
            exchange.authenticate()
    
    def test_is_authenticated_false_initially(self):
        """Test that is_authenticated returns False initially."""
        exchange = TestExchange("test", "api_key")
        assert exchange.is_authenticated() is False
    
    def test_is_authenticated_true_after_auth(self):
        """Test that is_authenticated returns True after successful auth."""
        exchange = TestExchange("test", "api_key")
        exchange._authenticated = True
        exchange._auth_expires_at = datetime.now() + timedelta(hours=1)
        
        assert exchange.is_authenticated() is True
    
    def test_is_authenticated_false_after_expiry(self):
        """Test that is_authenticated returns False after auth expires."""
        exchange = TestExchange("test", "api_key")
        exchange._authenticated = True
        exchange._auth_expires_at = datetime.now() - timedelta(minutes=1)  # Expired
        
        assert exchange.is_authenticated() is False
        assert exchange._authenticated is False  # Should be reset
    
    @patch('requests.Session.request')
    def test_test_connection_success(self, mock_request):
        """Test successful connection test."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.ok = True
        mock_request.return_value = mock_response
        
        exchange = TestExchange("test", "api_key")
        result = exchange.test_connection()
        
        assert result is True
    
    @patch('requests.Session.request')
    def test_test_connection_failure(self, mock_request):
        """Test failed connection test."""
        mock_request.side_effect = Exception("Connection failed")
        
        exchange = TestExchange("test", "api_key")
        result = exchange.test_connection()
        
        assert result is False
    
    @patch.object(TestExchange, '_make_request')
    @patch.object(TestExchange, 'is_authenticated')
    def test_get_position_history_success(self, mock_is_authenticated, mock_make_request):
        """Test successful position history retrieval."""
        mock_is_authenticated.return_value = True
        
        mock_response = Mock()
        mock_response.json.return_value = {
            "data": [
                {
                    "id": "pos1",
                    "symbol": "BTCUSDT",
                    "side": "long",
                    "size": "1.0",
                    "entry_price": "50000.0",
                    "mark_price": "51000.0",
                    "unrealized_pnl": "1000.0",
                    "realized_pnl": "0.0",
                    "status": "open",
                    "open_time": 1640995200000,  # 2022-01-01 00:00:00
                    "close_time": None
                }
            ]
        }
        mock_make_request.return_value = mock_response
        
        exchange = TestExchange("test", "api_key")
        positions = exchange.get_position_history()
        
        assert len(positions) == 1
        assert positions[0].position_id == "pos1"
        assert positions[0].symbol == "BTCUSDT"
        assert positions[0].side == PositionSide.LONG
    
    @patch.object(TestExchange, 'is_authenticated')
    @patch.object(TestExchange, 'authenticate')
    def test_get_position_history_auto_authenticate(self, mock_authenticate, mock_is_authenticated):
        """Test automatic authentication when not authenticated."""
        mock_is_authenticated.return_value = False
        mock_authenticate.return_value = True
        
        with patch.object(TestExchange, '_make_request') as mock_make_request:
            mock_response = Mock()
            mock_response.json.return_value = {"data": []}
            mock_make_request.return_value = mock_response
            
            exchange = TestExchange("test", "api_key")
            exchange.get_position_history()
            
            mock_authenticate.assert_called_once()
    
    @patch.object(TestExchange, 'is_authenticated')
    @patch.object(TestExchange, 'authenticate')
    def test_get_position_history_auth_failure(self, mock_authenticate, mock_is_authenticated):
        """Test position history when authentication fails."""
        mock_is_authenticated.return_value = False
        mock_authenticate.return_value = False
        
        exchange = TestExchange("test", "api_key")
        
        with pytest.raises(AuthenticationError):
            exchange.get_position_history()
    
    def test_context_manager(self):
        """Test BaseExchange as context manager."""
        with TestExchange("test", "api_key") as exchange:
            assert exchange.session is not None
        
        # Session should be closed after exiting context
        # Note: We can't easily test this without mocking, but the structure is correct
    
    def test_close_method(self):
        """Test close method."""
        exchange = TestExchange("test", "api_key")
        session_mock = Mock()
        exchange.session = session_mock
        
        exchange.close()
        session_mock.close.assert_called_once()


class TestExceptionClasses:
    """Test custom exception classes."""
    
    def test_exchange_error(self):
        """Test ExchangeError exception."""
        error = ExchangeError("Test error", error_code="TEST001", status_code=400)
        
        assert str(error) == "Test error"
        assert error.message == "Test error"
        assert error.error_code == "TEST001"
        assert error.status_code == 400
    
    def test_authentication_error(self):
        """Test AuthenticationError exception."""
        error = AuthenticationError("Auth failed", status_code=401)
        
        assert str(error) == "Auth failed"
        assert error.status_code == 401
        assert isinstance(error, ExchangeError)
    
    def test_rate_limit_error(self):
        """Test RateLimitError exception."""
        error = RateLimitError("Rate limit exceeded", retry_after=60)
        
        assert str(error) == "Rate limit exceeded"
        assert error.retry_after == 60
        assert isinstance(error, ExchangeError)
    
    def test_network_error(self):
        """Test NetworkError exception."""
        error = NetworkError("Network failed")
        
        assert str(error) == "Network failed"
        assert isinstance(error, ExchangeError)
    
    def test_api_error(self):
        """Test APIError exception."""
        error = APIError("API error", status_code=500)
        
        assert str(error) == "API error"
        assert error.status_code == 500
        assert isinstance(error, ExchangeError)