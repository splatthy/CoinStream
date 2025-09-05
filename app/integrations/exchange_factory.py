"""
Exchange client factory and registry for managing multiple exchange integrations.

This module provides a factory pattern for creating exchange clients and a registry
for managing multiple exchange instances with plugin support.
"""

import logging
from typing import Dict, Optional, List, Any
from dataclasses import dataclass
from abc import ABC, abstractmethod

from .base_exchange import BaseExchange, RateLimitConfig


@dataclass
class ExchangeInfo:
    """Information about a registered exchange."""

    name: str
    display_name: str
    description: str
    supported_features: List[str]
    default_rate_limits: RateLimitConfig
    requires_secret: bool = True


class ExchangePlugin(ABC):
    """Abstract base class for exchange plugins."""

    @property
    @abstractmethod
    def exchange_info(self) -> ExchangeInfo:
        """Get information about this exchange."""
        pass

    @abstractmethod
    def create_client(
        self, api_key: str, api_secret: Optional[str] = None, **kwargs
    ) -> BaseExchange:
        """Create an exchange client instance."""
        pass

    @abstractmethod
    def validate_credentials(
        self, api_key: str, api_secret: Optional[str] = None
    ) -> bool:
        """Validate exchange credentials format."""
        pass


class ExchangeRegistry:
    """Registry for managing exchange plugins and instances."""

    def __init__(self):
        self.logger = logging.getLogger("exchange.registry")
        self._plugins: Dict[str, ExchangePlugin] = {}
        self._instances: Dict[str, BaseExchange] = {}

    def register_plugin(self, plugin: ExchangePlugin) -> None:
        """
        Register an exchange plugin.

        Args:
            plugin: The exchange plugin to register

        Raises:
            ValueError: If plugin name is already registered
        """
        exchange_name = plugin.exchange_info.name.lower()

        if exchange_name in self._plugins:
            raise ValueError(f"Exchange '{exchange_name}' is already registered")

        self._plugins[exchange_name] = plugin
        self.logger.info(f"Registered exchange plugin: {exchange_name}")

    def unregister_plugin(self, exchange_name: str) -> None:
        """
        Unregister an exchange plugin.

        Args:
            exchange_name: Name of the exchange to unregister
        """
        exchange_name = exchange_name.lower()

        if exchange_name in self._plugins:
            # Close any active instances
            if exchange_name in self._instances:
                self._instances[exchange_name].close()
                del self._instances[exchange_name]

            del self._plugins[exchange_name]
            self.logger.info(f"Unregistered exchange plugin: {exchange_name}")

    def get_available_exchanges(self) -> List[ExchangeInfo]:
        """Get list of all available exchanges."""
        return [plugin.exchange_info for plugin in self._plugins.values()]

    def get_exchange_info(self, exchange_name: str) -> Optional[ExchangeInfo]:
        """
        Get information about a specific exchange.

        Args:
            exchange_name: Name of the exchange

        Returns:
            ExchangeInfo if found, None otherwise
        """
        exchange_name = exchange_name.lower()
        plugin = self._plugins.get(exchange_name)
        return plugin.exchange_info if plugin else None

    def is_exchange_supported(self, exchange_name: str) -> bool:
        """Check if an exchange is supported."""
        return exchange_name.lower() in self._plugins

    def validate_credentials(
        self, exchange_name: str, api_key: str, api_secret: Optional[str] = None
    ) -> bool:
        """
        Validate credentials for a specific exchange.

        Args:
            exchange_name: Name of the exchange
            api_key: API key to validate
            api_secret: API secret to validate (if required)

        Returns:
            True if credentials are valid format, False otherwise

        Raises:
            ValueError: If exchange is not supported
        """
        exchange_name = exchange_name.lower()

        if exchange_name not in self._plugins:
            raise ValueError(f"Exchange '{exchange_name}' is not supported")

        plugin = self._plugins[exchange_name]
        return plugin.validate_credentials(api_key, api_secret)

    def create_client(
        self,
        exchange_name: str,
        api_key: str,
        api_secret: Optional[str] = None,
        **kwargs,
    ) -> BaseExchange:
        """
        Create a new exchange client instance.

        Args:
            exchange_name: Name of the exchange
            api_key: API key for authentication
            api_secret: API secret for authentication (if required)
            **kwargs: Additional configuration options

        Returns:
            BaseExchange instance

        Raises:
            ValueError: If exchange is not supported or credentials are invalid
        """
        exchange_name = exchange_name.lower()

        if exchange_name not in self._plugins:
            raise ValueError(f"Exchange '{exchange_name}' is not supported")

        plugin = self._plugins[exchange_name]

        # Validate credentials format
        if not plugin.validate_credentials(api_key, api_secret):
            raise ValueError(f"Invalid credentials format for {exchange_name}")

        try:
            client = plugin.create_client(api_key, api_secret, **kwargs)
            self.logger.info(f"Created client for exchange: {exchange_name}")
            return client
        except Exception as e:
            self.logger.error(f"Failed to create client for {exchange_name}: {str(e)}")
            raise

    def get_or_create_client(
        self,
        exchange_name: str,
        api_key: str,
        api_secret: Optional[str] = None,
        **kwargs,
    ) -> BaseExchange:
        """
        Get existing client instance or create a new one.

        Args:
            exchange_name: Name of the exchange
            api_key: API key for authentication
            api_secret: API secret for authentication (if required)
            **kwargs: Additional configuration options

        Returns:
            BaseExchange instance
        """
        exchange_name = exchange_name.lower()

        # Check if we already have an instance
        if exchange_name in self._instances:
            existing_client = self._instances[exchange_name]
            # Verify the API key matches (simple check)
            if existing_client.api_key == api_key:
                return existing_client
            else:
                # Different credentials, close old instance and create new one
                existing_client.close()
                del self._instances[exchange_name]

        # Create new instance
        client = self.create_client(exchange_name, api_key, api_secret, **kwargs)
        self._instances[exchange_name] = client
        return client

    def close_client(self, exchange_name: str) -> None:
        """
        Close and remove a client instance.

        Args:
            exchange_name: Name of the exchange
        """
        exchange_name = exchange_name.lower()

        if exchange_name in self._instances:
            self._instances[exchange_name].close()
            del self._instances[exchange_name]
            self.logger.info(f"Closed client for exchange: {exchange_name}")

    def close_all_clients(self) -> None:
        """Close all active client instances."""
        for exchange_name in list(self._instances.keys()):
            self.close_client(exchange_name)

    def get_active_clients(self) -> Dict[str, BaseExchange]:
        """Get all active client instances."""
        return self._instances.copy()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close_all_clients()


class ExchangeFactory:
    """
    Factory class for creating exchange clients with a simplified interface.

    This class provides a high-level interface for creating exchange clients
    without needing to manage the registry directly.
    """

    def __init__(self, registry: Optional[ExchangeRegistry] = None):
        self.registry = registry or ExchangeRegistry()
        self.logger = logging.getLogger("exchange.factory")

    def register_exchange(self, plugin: ExchangePlugin) -> None:
        """Register an exchange plugin."""
        self.registry.register_plugin(plugin)

    def get_supported_exchanges(self) -> List[str]:
        """Get list of supported exchange names."""
        return [info.name for info in self.registry.get_available_exchanges()]

    def get_exchange_details(self, exchange_name: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about an exchange.

        Args:
            exchange_name: Name of the exchange

        Returns:
            Dictionary with exchange details or None if not found
        """
        info = self.registry.get_exchange_info(exchange_name)
        if not info:
            return None

        return {
            "name": info.name,
            "display_name": info.display_name,
            "description": info.description,
            "supported_features": info.supported_features,
            "requires_secret": info.requires_secret,
            "rate_limits": {
                "requests_per_second": info.default_rate_limits.requests_per_second,
                "requests_per_minute": info.default_rate_limits.requests_per_minute,
                "requests_per_hour": info.default_rate_limits.requests_per_hour,
                "burst_limit": info.default_rate_limits.burst_limit,
            },
        }

    def create_exchange_client(
        self,
        exchange_name: str,
        api_key: str,
        api_secret: Optional[str] = None,
        rate_limit_config: Optional[RateLimitConfig] = None,
        **kwargs,
    ) -> BaseExchange:
        """
        Create an exchange client with optional custom configuration.

        Args:
            exchange_name: Name of the exchange
            api_key: API key for authentication
            api_secret: API secret for authentication (if required)
            rate_limit_config: Custom rate limiting configuration
            **kwargs: Additional configuration options

        Returns:
            BaseExchange instance

        Raises:
            ValueError: If exchange is not supported or configuration is invalid
        """
        if not self.registry.is_exchange_supported(exchange_name):
            supported = self.get_supported_exchanges()
            raise ValueError(
                f"Exchange '{exchange_name}' is not supported. "
                f"Supported exchanges: {', '.join(supported)}"
            )

        # Add rate limit config to kwargs if provided
        if rate_limit_config:
            kwargs["rate_limit_config"] = rate_limit_config

        try:
            client = self.registry.create_client(
                exchange_name, api_key, api_secret, **kwargs
            )
            self.logger.info(f"Successfully created client for {exchange_name}")
            return client
        except Exception as e:
            self.logger.error(f"Failed to create client for {exchange_name}: {str(e)}")
            raise

    def test_exchange_connection(
        self, exchange_name: str, api_key: str, api_secret: Optional[str] = None
    ) -> bool:
        """
        Test connection to an exchange without creating a persistent client.

        Args:
            exchange_name: Name of the exchange
            api_key: API key for authentication
            api_secret: API secret for authentication (if required)

        Returns:
            True if connection successful, False otherwise
        """
        try:
            with self.create_exchange_client(
                exchange_name, api_key, api_secret
            ) as client:
                return client.test_connection()
        except Exception as e:
            self.logger.warning(f"Connection test failed for {exchange_name}: {str(e)}")
            return False

    def validate_exchange_credentials(
        self, exchange_name: str, api_key: str, api_secret: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Validate exchange credentials and return detailed results.

        Args:
            exchange_name: Name of the exchange
            api_key: API key to validate
            api_secret: API secret to validate (if required)

        Returns:
            Dictionary with validation results
        """
        result = {
            "exchange": exchange_name,
            "format_valid": False,
            "connection_test": False,
            "error": None,
        }

        try:
            # Check if exchange is supported
            if not self.registry.is_exchange_supported(exchange_name):
                result["error"] = f"Exchange '{exchange_name}' is not supported"
                return result

            # Validate credential format
            result["format_valid"] = self.registry.validate_credentials(
                exchange_name, api_key, api_secret
            )

            if not result["format_valid"]:
                result["error"] = "Invalid credential format"
                return result

            # Test connection
            result["connection_test"] = self.test_exchange_connection(
                exchange_name, api_key, api_secret
            )

            if not result["connection_test"]:
                result["error"] = "Connection test failed"

        except Exception as e:
            result["error"] = str(e)

        return result


# Global registry instance
_global_registry = ExchangeRegistry()

# Global factory instance
_global_factory = ExchangeFactory(_global_registry)


def get_exchange_registry() -> ExchangeRegistry:
    """Get the global exchange registry instance."""
    return _global_registry


def get_exchange_factory() -> ExchangeFactory:
    """Get the global exchange factory instance."""
    return _global_factory


def register_exchange_plugin(plugin: ExchangePlugin) -> None:
    """Register an exchange plugin with the global registry."""
    _global_registry.register_plugin(plugin)


def create_exchange_client(
    exchange_name: str, api_key: str, api_secret: Optional[str] = None, **kwargs
) -> BaseExchange:
    """Create an exchange client using the global factory."""
    return _global_factory.create_exchange_client(
        exchange_name, api_key, api_secret, **kwargs
    )


# Bitunix Plugin Implementation
class BitunixPlugin(ExchangePlugin):
    """Plugin for Bitunix exchange integration."""
    
    @property
    def exchange_info(self) -> ExchangeInfo:
        """Get information about Bitunix exchange."""
        return ExchangeInfo(
            name="bitunix",
            display_name="Bitunix",
            description="Bitunix cryptocurrency exchange integration",
            supported_features=[
                "position_history",
                "account_info",
                "real_time_data"
            ],
            default_rate_limits=RateLimitConfig(
                requests_per_second=2.0,
                requests_per_minute=100,
                requests_per_hour=2000
            ),
            requires_secret=False  # Bitunix uses API key only
        )
    
    def create_client(self, api_key: str, api_secret: Optional[str] = None, **kwargs) -> BaseExchange:
        """Create a Bitunix client instance."""
        try:
            from .bitunix_client import BitunixClient
            return BitunixClient(api_key=api_key, api_secret=api_secret)
        except ImportError as e:
            raise ValueError(f"Failed to import BitunixClient: {e}")
    
    def validate_credentials(self, api_key: str, api_secret: Optional[str] = None) -> bool:
        """Validate Bitunix credentials format."""
        # Basic validation - API key should be a non-empty string
        if not api_key or not isinstance(api_key, str):
            return False
        
        # API key should be at least 16 characters (typical for exchange API keys)
        if len(api_key.strip()) < 16:
            return False
        
        # API secret is optional for Bitunix
        if api_secret is not None:
            if not isinstance(api_secret, str) or len(api_secret.strip()) < 16:
                return False
        
        return True


# Initialize default plugins when module is imported
try:
    _bitunix_plugin = BitunixPlugin()
    register_exchange_plugin(_bitunix_plugin)
except Exception as e:
    import logging
    logger = logging.getLogger("exchange.factory")
    logger.warning(f"Failed to register Bitunix plugin: {e}")
