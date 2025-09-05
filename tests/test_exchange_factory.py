"""
Unit tests for the exchange factory and registry system.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from typing import Optional, List

from app.integrations.exchange_factory import (
    ExchangeRegistry, ExchangeFactory, ExchangePlugin, ExchangeInfo,
    get_exchange_registry, get_exchange_factory, register_exchange_plugin,
    create_exchange_client
)
from app.integrations.base_exchange import BaseExchange, RateLimitConfig


class MockExchange(BaseExchange):
    """Mock exchange implementation for testing."""
    
    @property
    def base_url(self) -> str:
        return "https://api.mock-exchange.com"
    
    @property
    def supported_endpoints(self) -> List[str]:
        return ["/api/v1/ping", "/api/v1/positions"]
    
    def _prepare_auth_headers(self) -> dict:
        return {"X-API-Key": self.api_key}
    
    def _parse_position_data(self, raw_data: dict):
        return raw_data  # Simplified for testing
    
    def _handle_api_error(self, response):
        pass  # Simplified for testing


class MockExchangePlugin(ExchangePlugin):
    """Mock exchange plugin for testing."""
    
    def __init__(self, name: str = "mock", requires_secret: bool = True):
        self._name = name
        self._requires_secret = requires_secret
    
    @property
    def exchange_info(self) -> ExchangeInfo:
        return ExchangeInfo(
            name=self._name,
            display_name=f"Mock {self._name.title()}",
            description=f"Mock exchange for testing: {self._name}",
            supported_features=["positions", "trading"],
            default_rate_limits=RateLimitConfig(
                requests_per_second=2.0,
                requests_per_minute=120,
                requests_per_hour=2000
            ),
            requires_secret=self._requires_secret
        )
    
    def create_client(self, api_key: str, api_secret: Optional[str] = None, 
                     **kwargs) -> BaseExchange:
        return MockExchange(self._name, api_key, api_secret, **kwargs)
    
    def validate_credentials(self, api_key: str, api_secret: Optional[str] = None) -> bool:
        # Simple validation: API key should be at least 10 characters
        if not api_key or len(api_key) < 10:
            return False
        
        # If secret is required, check it too
        if self._requires_secret and (not api_secret or len(api_secret) < 10):
            return False
        
        return True


class TestExchangeRegistry:
    """Test cases for ExchangeRegistry class."""
    
    def test_initialization(self):
        """Test registry initialization."""
        registry = ExchangeRegistry()
        
        assert len(registry._plugins) == 0
        assert len(registry._instances) == 0
        assert registry.get_available_exchanges() == []
    
    def test_register_plugin(self):
        """Test plugin registration."""
        registry = ExchangeRegistry()
        plugin = MockExchangePlugin("test")
        
        registry.register_plugin(plugin)
        
        assert "test" in registry._plugins
        assert registry.is_exchange_supported("test")
        assert registry.is_exchange_supported("TEST")  # Case insensitive
    
    def test_register_duplicate_plugin(self):
        """Test registering duplicate plugin raises error."""
        registry = ExchangeRegistry()
        plugin1 = MockExchangePlugin("test")
        plugin2 = MockExchangePlugin("test")
        
        registry.register_plugin(plugin1)
        
        with pytest.raises(ValueError, match="already registered"):
            registry.register_plugin(plugin2)
    
    def test_unregister_plugin(self):
        """Test plugin unregistration."""
        registry = ExchangeRegistry()
        plugin = MockExchangePlugin("test")
        
        registry.register_plugin(plugin)
        assert registry.is_exchange_supported("test")
        
        registry.unregister_plugin("test")
        assert not registry.is_exchange_supported("test")
    
    def test_unregister_plugin_with_active_instance(self):
        """Test unregistering plugin closes active instances."""
        registry = ExchangeRegistry()
        plugin = MockExchangePlugin("test")
        
        registry.register_plugin(plugin)
        client = registry.create_client("test", "test_api_key_123", "test_secret_123")
        registry._instances["test"] = client
        
        # Mock the close method
        client.close = Mock()
        
        registry.unregister_plugin("test")
        
        client.close.assert_called_once()
        assert "test" not in registry._instances
    
    def test_get_available_exchanges(self):
        """Test getting available exchanges."""
        registry = ExchangeRegistry()
        plugin1 = MockExchangePlugin("exchange1")
        plugin2 = MockExchangePlugin("exchange2")
        
        registry.register_plugin(plugin1)
        registry.register_plugin(plugin2)
        
        exchanges = registry.get_available_exchanges()
        assert len(exchanges) == 2
        
        exchange_names = [ex.name for ex in exchanges]
        assert "exchange1" in exchange_names
        assert "exchange2" in exchange_names
    
    def test_get_exchange_info(self):
        """Test getting exchange information."""
        registry = ExchangeRegistry()
        plugin = MockExchangePlugin("test")
        
        registry.register_plugin(plugin)
        
        info = registry.get_exchange_info("test")
        assert info is not None
        assert info.name == "test"
        assert info.display_name == "Mock Test"
        
        # Test case insensitive
        info = registry.get_exchange_info("TEST")
        assert info is not None
        
        # Test non-existent exchange
        info = registry.get_exchange_info("nonexistent")
        assert info is None
    
    def test_validate_credentials(self):
        """Test credential validation."""
        registry = ExchangeRegistry()
        plugin = MockExchangePlugin("test")
        
        registry.register_plugin(plugin)
        
        # Valid credentials
        assert registry.validate_credentials("test", "valid_key_123", "valid_secret_123")
        
        # Invalid API key (too short)
        assert not registry.validate_credentials("test", "short", "valid_secret_123")
        
        # Invalid secret (too short)
        assert not registry.validate_credentials("test", "valid_key_123", "short")
        
        # Test unsupported exchange
        with pytest.raises(ValueError, match="not supported"):
            registry.validate_credentials("unsupported", "key", "secret")
    
    def test_create_client(self):
        """Test client creation."""
        registry = ExchangeRegistry()
        plugin = MockExchangePlugin("test")
        
        registry.register_plugin(plugin)
        
        client = registry.create_client("test", "valid_key_123", "valid_secret_123")
        
        assert isinstance(client, MockExchange)
        assert client.name == "test"
        assert client.api_key == "valid_key_123"
        assert client.api_secret == "valid_secret_123"
    
    def test_create_client_unsupported_exchange(self):
        """Test creating client for unsupported exchange."""
        registry = ExchangeRegistry()
        
        with pytest.raises(ValueError, match="not supported"):
            registry.create_client("unsupported", "key", "secret")
    
    def test_create_client_invalid_credentials(self):
        """Test creating client with invalid credentials."""
        registry = ExchangeRegistry()
        plugin = MockExchangePlugin("test")
        
        registry.register_plugin(plugin)
        
        with pytest.raises(ValueError, match="Invalid credentials"):
            registry.create_client("test", "short", "secret")
    
    def test_get_or_create_client(self):
        """Test getting or creating client."""
        registry = ExchangeRegistry()
        plugin = MockExchangePlugin("test")
        
        registry.register_plugin(plugin)
        
        # First call should create new client
        client1 = registry.get_or_create_client("test", "valid_key_123", "valid_secret_123")
        assert isinstance(client1, MockExchange)
        
        # Second call with same credentials should return same instance
        client2 = registry.get_or_create_client("test", "valid_key_123", "valid_secret_123")
        assert client1 is client2
        
        # Call with different credentials should create new instance
        client1.close = Mock()
        client3 = registry.get_or_create_client("test", "different_key_123", "different_secret_123")
        assert client3 is not client1
        client1.close.assert_called_once()
    
    def test_close_client(self):
        """Test closing client."""
        registry = ExchangeRegistry()
        plugin = MockExchangePlugin("test")
        
        registry.register_plugin(plugin)
        client = registry.create_client("test", "valid_key_123", "valid_secret_123")
        registry._instances["test"] = client
        
        client.close = Mock()
        
        registry.close_client("test")
        
        client.close.assert_called_once()
        assert "test" not in registry._instances
    
    def test_close_all_clients(self):
        """Test closing all clients."""
        registry = ExchangeRegistry()
        plugin1 = MockExchangePlugin("test1")
        plugin2 = MockExchangePlugin("test2")
        
        registry.register_plugin(plugin1)
        registry.register_plugin(plugin2)
        
        client1 = registry.create_client("test1", "valid_key_123", "valid_secret_123")
        client2 = registry.create_client("test2", "valid_key_123", "valid_secret_123")
        
        registry._instances["test1"] = client1
        registry._instances["test2"] = client2
        
        client1.close = Mock()
        client2.close = Mock()
        
        registry.close_all_clients()
        
        client1.close.assert_called_once()
        client2.close.assert_called_once()
        assert len(registry._instances) == 0
    
    def test_get_active_clients(self):
        """Test getting active clients."""
        registry = ExchangeRegistry()
        plugin = MockExchangePlugin("test")
        
        registry.register_plugin(plugin)
        client = registry.create_client("test", "valid_key_123", "valid_secret_123")
        registry._instances["test"] = client
        
        active_clients = registry.get_active_clients()
        
        assert len(active_clients) == 1
        assert "test" in active_clients
        assert active_clients["test"] is client
        
        # Should return a copy, not the original dict
        assert active_clients is not registry._instances
    
    def test_context_manager(self):
        """Test registry as context manager."""
        registry = ExchangeRegistry()
        plugin = MockExchangePlugin("test")
        
        registry.register_plugin(plugin)
        
        with registry as reg:
            client = reg.create_client("test", "valid_key_123", "valid_secret_123")
            reg._instances["test"] = client
            client.close = Mock()
        
        # Should close all clients when exiting context
        client.close.assert_called_once()


class TestExchangeFactory:
    """Test cases for ExchangeFactory class."""
    
    def test_initialization(self):
        """Test factory initialization."""
        factory = ExchangeFactory()
        
        assert factory.registry is not None
        assert isinstance(factory.registry, ExchangeRegistry)
    
    def test_initialization_with_custom_registry(self):
        """Test factory initialization with custom registry."""
        custom_registry = ExchangeRegistry()
        factory = ExchangeFactory(custom_registry)
        
        assert factory.registry is custom_registry
    
    def test_register_exchange(self):
        """Test registering exchange through factory."""
        factory = ExchangeFactory()
        plugin = MockExchangePlugin("test")
        
        factory.register_exchange(plugin)
        
        assert factory.registry.is_exchange_supported("test")
    
    def test_get_supported_exchanges(self):
        """Test getting supported exchanges."""
        factory = ExchangeFactory()
        plugin1 = MockExchangePlugin("exchange1")
        plugin2 = MockExchangePlugin("exchange2")
        
        factory.register_exchange(plugin1)
        factory.register_exchange(plugin2)
        
        supported = factory.get_supported_exchanges()
        
        assert len(supported) == 2
        assert "exchange1" in supported
        assert "exchange2" in supported
    
    def test_get_exchange_details(self):
        """Test getting exchange details."""
        factory = ExchangeFactory()
        plugin = MockExchangePlugin("test")
        
        factory.register_exchange(plugin)
        
        details = factory.get_exchange_details("test")
        
        assert details is not None
        assert details["name"] == "test"
        assert details["display_name"] == "Mock Test"
        assert details["requires_secret"] is True
        assert "rate_limits" in details
        assert details["rate_limits"]["requests_per_second"] == 2.0
        
        # Test non-existent exchange
        details = factory.get_exchange_details("nonexistent")
        assert details is None
    
    def test_create_exchange_client(self):
        """Test creating exchange client."""
        factory = ExchangeFactory()
        plugin = MockExchangePlugin("test")
        
        factory.register_exchange(plugin)
        
        client = factory.create_exchange_client("test", "valid_key_123", "valid_secret_123")
        
        assert isinstance(client, MockExchange)
        assert client.name == "test"
    
    def test_create_exchange_client_unsupported(self):
        """Test creating client for unsupported exchange."""
        factory = ExchangeFactory()
        
        with pytest.raises(ValueError, match="not supported"):
            factory.create_exchange_client("unsupported", "key", "secret")
    
    def test_create_exchange_client_with_rate_limits(self):
        """Test creating client with custom rate limits."""
        factory = ExchangeFactory()
        plugin = MockExchangePlugin("test")
        
        factory.register_exchange(plugin)
        
        custom_rate_limits = RateLimitConfig(
            requests_per_second=5.0,
            requests_per_minute=300,
            requests_per_hour=5000
        )
        
        client = factory.create_exchange_client(
            "test", "valid_key_123", "valid_secret_123",
            rate_limit_config=custom_rate_limits
        )
        
        assert client.rate_limit_config == custom_rate_limits
    
    @patch.object(MockExchange, 'test_connection')
    def test_test_exchange_connection_success(self, mock_test_connection):
        """Test successful connection test."""
        mock_test_connection.return_value = True
        
        factory = ExchangeFactory()
        plugin = MockExchangePlugin("test")
        
        factory.register_exchange(plugin)
        
        result = factory.test_exchange_connection("test", "valid_key_123", "valid_secret_123")
        
        assert result is True
        mock_test_connection.assert_called_once()
    
    @patch.object(MockExchange, 'test_connection')
    def test_test_exchange_connection_failure(self, mock_test_connection):
        """Test failed connection test."""
        mock_test_connection.return_value = False
        
        factory = ExchangeFactory()
        plugin = MockExchangePlugin("test")
        
        factory.register_exchange(plugin)
        
        result = factory.test_exchange_connection("test", "valid_key_123", "valid_secret_123")
        
        assert result is False
    
    def test_test_exchange_connection_exception(self):
        """Test connection test with exception."""
        factory = ExchangeFactory()
        plugin = MockExchangePlugin("test")
        
        factory.register_exchange(plugin)
        
        # Test with invalid credentials to trigger exception
        result = factory.test_exchange_connection("test", "short", "secret")
        
        assert result is False
    
    def test_validate_exchange_credentials_success(self):
        """Test successful credential validation."""
        factory = ExchangeFactory()
        plugin = MockExchangePlugin("test")
        
        factory.register_exchange(plugin)
        
        with patch.object(factory, 'test_exchange_connection', return_value=True):
            result = factory.validate_exchange_credentials("test", "valid_key_123", "valid_secret_123")
        
        assert result["exchange"] == "test"
        assert result["format_valid"] is True
        assert result["connection_test"] is True
        assert result["error"] is None
    
    def test_validate_exchange_credentials_format_invalid(self):
        """Test credential validation with invalid format."""
        factory = ExchangeFactory()
        plugin = MockExchangePlugin("test")
        
        factory.register_exchange(plugin)
        
        result = factory.validate_exchange_credentials("test", "short", "secret")
        
        assert result["exchange"] == "test"
        assert result["format_valid"] is False
        assert result["connection_test"] is False
        assert result["error"] == "Invalid credential format"
    
    def test_validate_exchange_credentials_connection_failed(self):
        """Test credential validation with connection failure."""
        factory = ExchangeFactory()
        plugin = MockExchangePlugin("test")
        
        factory.register_exchange(plugin)
        
        with patch.object(factory, 'test_exchange_connection', return_value=False):
            result = factory.validate_exchange_credentials("test", "valid_key_123", "valid_secret_123")
        
        assert result["exchange"] == "test"
        assert result["format_valid"] is True
        assert result["connection_test"] is False
        assert result["error"] == "Connection test failed"
    
    def test_validate_exchange_credentials_unsupported(self):
        """Test credential validation for unsupported exchange."""
        factory = ExchangeFactory()
        
        result = factory.validate_exchange_credentials("unsupported", "key", "secret")
        
        assert result["exchange"] == "unsupported"
        assert result["format_valid"] is False
        assert result["connection_test"] is False
        assert "not supported" in result["error"]


class TestGlobalFunctions:
    """Test global convenience functions."""
    
    def test_get_exchange_registry(self):
        """Test getting global registry."""
        registry = get_exchange_registry()
        
        assert isinstance(registry, ExchangeRegistry)
        
        # Should return same instance on multiple calls
        registry2 = get_exchange_registry()
        assert registry is registry2
    
    def test_get_exchange_factory(self):
        """Test getting global factory."""
        factory = get_exchange_factory()
        
        assert isinstance(factory, ExchangeFactory)
        
        # Should return same instance on multiple calls
        factory2 = get_exchange_factory()
        assert factory is factory2
    
    def test_register_exchange_plugin(self):
        """Test registering plugin globally."""
        plugin = MockExchangePlugin("global_test")
        
        register_exchange_plugin(plugin)
        
        registry = get_exchange_registry()
        assert registry.is_exchange_supported("global_test")
        
        # Clean up
        registry.unregister_plugin("global_test")
    
    def test_create_exchange_client_global(self):
        """Test creating client globally."""
        plugin = MockExchangePlugin("global_client_test")
        
        register_exchange_plugin(plugin)
        
        client = create_exchange_client("global_client_test", "valid_key_123", "valid_secret_123")
        
        assert isinstance(client, MockExchange)
        assert client.name == "global_client_test"
        
        # Clean up
        client.close()
        registry = get_exchange_registry()
        registry.unregister_plugin("global_client_test")


class TestExchangePlugin:
    """Test ExchangePlugin abstract class."""
    
    def test_plugin_interface(self):
        """Test plugin implements required interface."""
        plugin = MockExchangePlugin("test")
        
        # Test exchange_info property
        info = plugin.exchange_info
        assert isinstance(info, ExchangeInfo)
        assert info.name == "test"
        
        # Test create_client method
        client = plugin.create_client("valid_key_123", "valid_secret_123")
        assert isinstance(client, BaseExchange)
        
        # Test validate_credentials method
        assert plugin.validate_credentials("valid_key_123", "valid_secret_123") is True
        assert plugin.validate_credentials("short", "secret") is False
    
    def test_plugin_without_secret_requirement(self):
        """Test plugin that doesn't require API secret."""
        plugin = MockExchangePlugin("test", requires_secret=False)
        
        info = plugin.exchange_info
        assert info.requires_secret is False
        
        # Should validate with just API key
        assert plugin.validate_credentials("valid_key_123") is True
        assert plugin.validate_credentials("valid_key_123", None) is True


class TestExchangeInfo:
    """Test ExchangeInfo dataclass."""
    
    def test_exchange_info_creation(self):
        """Test creating ExchangeInfo."""
        rate_limits = RateLimitConfig(
            requests_per_second=1.0,
            requests_per_minute=60,
            requests_per_hour=1000
        )
        
        info = ExchangeInfo(
            name="test",
            display_name="Test Exchange",
            description="A test exchange",
            supported_features=["trading", "positions"],
            default_rate_limits=rate_limits,
            requires_secret=True
        )
        
        assert info.name == "test"
        assert info.display_name == "Test Exchange"
        assert info.description == "A test exchange"
        assert info.supported_features == ["trading", "positions"]
        assert info.default_rate_limits == rate_limits
        assert info.requires_secret is True
    
    def test_exchange_info_defaults(self):
        """Test ExchangeInfo with default values."""
        rate_limits = RateLimitConfig(
            requests_per_second=1.0,
            requests_per_minute=60,
            requests_per_hour=1000
        )
        
        info = ExchangeInfo(
            name="test",
            display_name="Test Exchange",
            description="A test exchange",
            supported_features=["trading"],
            default_rate_limits=rate_limits
        )
        
        # requires_secret should default to True
        assert info.requires_secret is True