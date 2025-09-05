"""
Tests for Bitunix exchange client implementation.
"""

import json
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, Mock, patch

import pytest
import requests

from app.integrations.base_exchange import (
    APIError,
    AuthenticationError,
    NetworkError,
    RateLimitError,
)
from app.integrations.bitunix_client import BitunixClient
from app.models.position import Position, PositionSide, PositionStatus


class TestBitunixClient:
    """Test cases for BitunixClient."""

    @pytest.fixture
    def client(self):
        """Create a BitunixClient instance for testing."""
        return BitunixClient(api_key="test_api_key", api_secret="test_api_secret")

    @pytest.fixture
    def mock_response(self):
        """Create a mock HTTP response."""
        response = Mock(spec=requests.Response)
        response.status_code = 200
        response.ok = True
        return response

    @pytest.fixture
    def sample_position_data(self):
        """Sample position data from Bitunix API."""
        return {
            "positionId": "12345",
            "symbol": "BTCUSDT",
            "side": "long",
            "size": "1.5",
            "entryPrice": "45000.00",
            "markPrice": "46000.00",
            "unrealizedPnl": "1500.00",
            "realizedPnl": "0.00",
            "status": "open",
            "openTime": 1640995200000,  # 2022-01-01 00:00:00 UTC
            "closeTime": 0,
        }

    def test_init(self):
        """Test BitunixClient initialization."""
        client = BitunixClient(api_key="test_key", api_secret="test_secret")

        assert client.name == "bitunix"
        assert client.api_key == "test_key"
        assert client.api_secret == "test_secret"
        assert client.base_url == "https://fapi.bitunix.com"
        assert "/api/v1/common/time" in client.supported_endpoints
        assert "/api/v1/future/position" in client.supported_endpoints

    def test_prepare_auth_headers(self, client):
        """Test authentication header preparation."""
        with patch("time.time", return_value=1640995200):
            headers = client._prepare_auth_headers("GET", "/api/v1/test", "", "")

            assert "BX-APIKEY" in headers
            assert headers["BX-APIKEY"] == "test_api_key"
            assert "User-Agent" in headers
            assert "BX-TIMESTAMP" in headers
            assert "BX-SIGNATURE" in headers

    def test_prepare_auth_headers_no_secret(self):
        """Test authentication headers without API secret."""
        client = BitunixClient(api_key="test_key")
        headers = client._prepare_auth_headers("GET", "/api/v1/test", "", "")

        assert "BX-APIKEY" in headers
        assert headers["BX-APIKEY"] == "test_key"
        assert "User-Agent" in headers
        assert "BX-TIMESTAMP" in headers
        assert "BX-SIGNATURE" not in headers

    def test_handle_api_error_authentication(self, client):
        """Test handling of authentication errors."""
        response = Mock(spec=requests.Response)
        response.status_code = 401
        response.json.return_value = {
            "code": "AUTH_FAILED",
            "message": "Invalid API key",
        }

        with pytest.raises(AuthenticationError) as exc_info:
            client._handle_api_error(response)

        assert "Authentication failed" in exc_info.value.message
        assert exc_info.value.error_code == "AUTH_FAILED"
        assert exc_info.value.status_code == 401

    def test_handle_api_error_general(self, client):
        """Test handling of general API errors."""
        response = Mock(spec=requests.Response)
        response.status_code = 400
        response.json.return_value = {
            "code": "BAD_REQUEST",
            "message": "Invalid parameters",
        }

        with pytest.raises(APIError) as exc_info:
            client._handle_api_error(response)

        assert "API error" in exc_info.value.message
        assert exc_info.value.error_code == "BAD_REQUEST"
        assert exc_info.value.status_code == 400

    def test_handle_api_error_no_json(self, client):
        """Test handling of API errors with no JSON response."""
        response = Mock(spec=requests.Response)
        response.status_code = 500
        response.json.side_effect = ValueError("No JSON")
        response.text = "Internal Server Error"

        with pytest.raises(APIError) as exc_info:
            client._handle_api_error(response)

        assert "Internal Server Error" in exc_info.value.message

    def test_parse_position_data_valid(self, client, sample_position_data):
        """Test parsing valid position data."""
        position = client._parse_position_data(sample_position_data)

        assert isinstance(position, Position)
        assert position.position_id == "12345"
        assert position.symbol == "BTCUSDT"
        assert position.side == PositionSide.LONG
        assert position.size == Decimal("1.5")
        assert position.entry_price == Decimal("45000.00")
        assert position.mark_price == Decimal("46000.00")
        assert position.unrealized_pnl == Decimal("1500.00")
        assert position.realized_pnl == Decimal("0.00")
        assert position.status == PositionStatus.OPEN
        assert position.open_time == datetime.fromtimestamp(1640995200)
        assert position.close_time is None
        assert position.raw_data == sample_position_data

    def test_parse_position_data_short_position(self, client):
        """Test parsing short position data."""
        data = {
            "positionId": "67890",
            "symbol": "ETHUSDT",
            "side": "short",
            "size": "10.0",
            "entryPrice": "3000.00",
            "markPrice": "2950.00",
            "unrealizedPnl": "500.00",
            "realizedPnl": "100.00",
            "status": "closed",
            "openTime": 1640995200000,
            "closeTime": 1641081600000,  # 2022-01-02 00:00:00 UTC
        }

        position = client._parse_position_data(data)

        assert position.side == PositionSide.SHORT
        assert position.status == PositionStatus.CLOSED
        assert position.close_time == datetime.fromtimestamp(1641081600)

    def test_parse_position_data_alternative_fields(self, client):
        """Test parsing position data with alternative field names."""
        data = {
            "id": "alt123",  # Alternative to positionId
            "symbol": "ADAUSDT",
            "side": "buy",  # Alternative to long
            "size": "1000.0",
            "entryPrice": "1.50",
            "currentPrice": "1.55",  # Alternative to markPrice
            "unrealizedPnl": "50.00",
            "realizedPnl": "0.00",
            "status": "active",  # Alternative to open
            "createTime": 1640995200000,  # Alternative to openTime
        }

        position = client._parse_position_data(data)

        assert position.position_id == "alt123"
        assert position.side == PositionSide.LONG
        assert position.mark_price == Decimal("1.55")
        assert position.status == PositionStatus.OPEN

    def test_parse_position_data_missing_required_field(self, client):
        """Test parsing position data with missing required fields."""
        data = {
            "symbol": "BTCUSDT",
            "side": "long",
            # Missing positionId/id
        }

        with pytest.raises(ValueError) as exc_info:
            client._parse_position_data(data)

        assert "Position ID is required" in str(exc_info.value)

    def test_parse_position_data_invalid_side(self, client):
        """Test parsing position data with invalid side."""
        data = {
            "positionId": "123",
            "symbol": "BTCUSDT",
            "side": "invalid_side",
            "size": "1.0",
            "entryPrice": "45000.00",
            "markPrice": "46000.00",
            "unrealizedPnl": "1000.00",
            "realizedPnl": "0.00",
            "status": "open",
            "openTime": 1640995200000,
        }

        with pytest.raises(ValueError) as exc_info:
            client._parse_position_data(data)

        assert "Invalid position side" in str(exc_info.value)

    @patch("app.integrations.bitunix_client.BitunixClient._make_request")
    def test_test_connection_success(self, mock_request, client, mock_response):
        """Test successful connection test."""
        mock_request.return_value = mock_response

        result = client.test_connection()

        assert result is True
        mock_request.assert_called_once_with(
            "GET", "/api/v1/common/time", require_auth=False
        )

    @patch("app.integrations.bitunix_client.BitunixClient._make_request")
    def test_test_connection_failure(self, mock_request, client):
        """Test failed connection test."""
        mock_request.side_effect = Exception("Connection failed")

        result = client.test_connection()

        assert result is False

    @patch("app.integrations.bitunix_client.BitunixClient._make_request")
    def test_get_account_info_success(self, mock_request, client, mock_response):
        """Test successful account info retrieval."""
        account_data = {"balance": "1000.00", "currency": "USDT"}
        mock_response.json.return_value = account_data
        mock_request.return_value = mock_response

        # Mock authentication
        client._authenticated = True
        client._auth_expires_at = datetime.now() + timedelta(hours=1)

        result = client.get_account_info()

        assert result == account_data
        mock_request.assert_called_once_with("GET", "/api/v1/account/info")

    @patch("app.integrations.bitunix_client.BitunixClient.authenticate")
    @patch("app.integrations.bitunix_client.BitunixClient._make_request")
    def test_get_account_info_authentication_required(
        self, mock_request, mock_auth, client
    ):
        """Test account info retrieval when authentication is required."""
        mock_auth.return_value = True
        mock_response = Mock()
        mock_response.json.return_value = {"balance": "1000.00"}
        mock_request.return_value = mock_response

        # Client is not authenticated
        client._authenticated = False

        result = client.get_account_info()

        mock_auth.assert_called_once()
        assert result == {"balance": "1000.00"}

    @patch("app.integrations.bitunix_client.BitunixClient.authenticate")
    def test_get_account_info_authentication_failed(self, mock_auth, client):
        """Test account info retrieval when authentication fails."""
        mock_auth.return_value = False
        client._authenticated = False

        with pytest.raises(AuthenticationError):
            client.get_account_info()

    @patch("app.integrations.bitunix_client.BitunixClient._make_request")
    def test_get_position_history_success(
        self, mock_request, client, sample_position_data
    ):
        """Test successful position history retrieval."""
        response_data = {"data": [sample_position_data]}
        mock_response = Mock()
        mock_response.json.return_value = response_data
        mock_request.return_value = mock_response

        # Mock authentication
        client._authenticated = True
        client._auth_expires_at = datetime.now() + timedelta(hours=1)

        positions = client.get_position_history()

        assert len(positions) == 1
        assert isinstance(positions[0], Position)
        assert positions[0].position_id == "12345"
        mock_request.assert_called_once()

    @patch("app.integrations.bitunix_client.BitunixClient._make_request")
    def test_get_position_history_with_params(
        self, mock_request, client, sample_position_data
    ):
        """Test position history retrieval with parameters."""
        response_data = {"data": [sample_position_data]}
        mock_response = Mock()
        mock_response.json.return_value = response_data
        mock_request.return_value = mock_response

        # Mock authentication
        client._authenticated = True
        client._auth_expires_at = datetime.now() + timedelta(hours=1)

        since = datetime(2022, 1, 1)
        limit = 50

        positions = client.get_position_history(since=since, limit=limit)

        # Verify the request was made with correct parameters
        call_args = mock_request.call_args
        assert call_args[0] == ("GET", "/api/v1/future/position")
        params = call_args[1]["params"]
        assert params["startTime"] == int(since.timestamp() * 1000)
        assert params["limit"] == 50

    @patch("app.integrations.bitunix_client.BitunixClient._make_request")
    def test_get_position_history_list_response(
        self, mock_request, client, sample_position_data
    ):
        """Test position history with direct list response."""
        mock_response = Mock()
        mock_response.json.return_value = [sample_position_data]  # Direct list
        mock_request.return_value = mock_response

        # Mock authentication
        client._authenticated = True
        client._auth_expires_at = datetime.now() + timedelta(hours=1)

        positions = client.get_position_history()

        assert len(positions) == 1
        assert positions[0].position_id == "12345"

    @patch("app.integrations.bitunix_client.BitunixClient._make_request")
    def test_get_position_history_parse_errors(
        self, mock_request, client, sample_position_data
    ):
        """Test position history with some parsing errors."""
        invalid_data = {
            "positionId": "invalid",
            "symbol": "",
        }  # Missing required fields
        response_data = {"data": [sample_position_data, invalid_data]}
        mock_response = Mock()
        mock_response.json.return_value = response_data
        mock_request.return_value = mock_response

        # Mock authentication
        client._authenticated = True
        client._auth_expires_at = datetime.now() + timedelta(hours=1)

        positions = client.get_position_history()

        # Should only return the valid position
        assert len(positions) == 1
        assert positions[0].position_id == "12345"

    @patch("app.integrations.bitunix_client.BitunixClient._make_request")
    def test_get_position_history_network_error(self, mock_request, client):
        """Test position history with network error."""
        mock_request.side_effect = requests.ConnectionError("Network error")

        # Mock authentication
        client._authenticated = True
        client._auth_expires_at = datetime.now() + timedelta(hours=1)

        with pytest.raises(NetworkError) as exc_info:
            client.get_position_history()

        assert "Network error while fetching positions" in str(exc_info.value)

    @patch("app.integrations.bitunix_client.BitunixClient.get_position_history")
    def test_get_position_by_id_found(
        self, mock_get_history, client, sample_position_data
    ):
        """Test getting position by ID when found."""
        position = Position(
            position_id="12345",
            symbol="BTCUSDT",
            side=PositionSide.LONG,
            size=Decimal("1.5"),
            entry_price=Decimal("45000.00"),
            mark_price=Decimal("46000.00"),
            unrealized_pnl=Decimal("1500.00"),
            realized_pnl=Decimal("0.00"),
            status=PositionStatus.OPEN,
            open_time=datetime.now(),
            raw_data=sample_position_data,
        )
        mock_get_history.return_value = [position]

        result = client.get_position_by_id("12345")

        assert result is not None
        assert result.position_id == "12345"

    @patch("app.integrations.bitunix_client.BitunixClient.get_position_history")
    def test_get_position_by_id_not_found(self, mock_get_history, client):
        """Test getting position by ID when not found."""
        mock_get_history.return_value = []

        result = client.get_position_by_id("nonexistent")

        assert result is None

    @patch("app.integrations.bitunix_client.BitunixClient.get_position_history")
    def test_get_position_by_id_error(self, mock_get_history, client):
        """Test getting position by ID with error."""
        mock_get_history.side_effect = Exception("API error")

        result = client.get_position_by_id("12345")

        assert result is None


class TestBitunixClientIntegration:
    """Integration tests for BitunixClient with mock API responses."""

    @pytest.fixture
    def client(self):
        """Create a BitunixClient instance for integration testing."""
        return BitunixClient(api_key="integration_test_key")

    @patch("requests.Session.request")
    def test_full_position_sync_workflow(self, mock_request, client):
        """Test complete position synchronization workflow."""
        # Mock ping response
        ping_response = Mock()
        ping_response.status_code = 200
        ping_response.ok = True

        # Mock position history response
        position_response = Mock()
        position_response.status_code = 200
        position_response.ok = True
        position_response.json.return_value = {
            "data": [
                {
                    "positionId": "pos1",
                    "symbol": "BTCUSDT",
                    "side": "long",
                    "size": "1.0",
                    "entryPrice": "45000.00",
                    "markPrice": "46000.00",
                    "unrealizedPnl": "1000.00",
                    "realizedPnl": "0.00",
                    "status": "open",
                    "openTime": 1640995200000,
                },
                {
                    "positionId": "pos2",
                    "symbol": "ETHUSDT",
                    "side": "short",
                    "size": "5.0",
                    "entryPrice": "3000.00",
                    "markPrice": "2950.00",
                    "unrealizedPnl": "250.00",
                    "realizedPnl": "100.00",
                    "status": "closed",
                    "openTime": 1640995200000,
                    "closeTime": 1641081600000,
                },
            ]
        }

        # Configure mock to return different responses based on URL
        def mock_request_side_effect(*args, **kwargs):
            url = kwargs.get("url", "")
            if "common/time" in url:
                return ping_response
            elif "future/position" in url:
                return position_response
            return Mock(status_code=404)

        mock_request.side_effect = mock_request_side_effect

        # Test connection
        assert client.test_connection() is True

        # Test authentication
        assert client.authenticate() is True

        # Test position history retrieval
        positions = client.get_position_history()

        assert len(positions) == 2

        # Verify first position (BTCUSDT long)
        btc_position = positions[0]
        assert btc_position.position_id == "pos1"
        assert btc_position.symbol == "BTCUSDT"
        assert btc_position.side == PositionSide.LONG
        assert btc_position.status == PositionStatus.OPEN
        assert btc_position.close_time is None

        # Verify second position (ETHUSDT short)
        eth_position = positions[1]
        assert eth_position.position_id == "pos2"
        assert eth_position.symbol == "ETHUSDT"
        assert eth_position.side == PositionSide.SHORT
        assert eth_position.status == PositionStatus.CLOSED
        assert eth_position.close_time is not None
