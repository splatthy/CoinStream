"""
Configuration service for managing application settings, exchange configurations,
and custom field definitions.
"""

import json
import os
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..models.custom_fields import CustomFieldConfig, FieldType
from ..models.exchange_config import ConnectionStatus, ExchangeConfig
from ..utils.encryption import CredentialEncryption
from ..utils.serialization import DataSerializer


class ConfigService:
    """
    Service for managing application configuration including exchange settings
    and custom field definitions.
    """

    def __init__(self, data_path: str = "/app/data"):
        """
        Initialize configuration service.

        Args:
            data_path: Path to persistent data directory
        """
        self.data_path = Path(data_path)
        self.config_file = self.data_path / "config.json"
        self.exchanges_file = self.data_path / "exchanges.json"
        self.custom_fields_file = self.data_path / "custom_fields.json"

        # Ensure data directory exists
        self.data_path.mkdir(parents=True, exist_ok=True)

        # Initialize encryption manager with a consistent key for testing
        # In production, this should use a proper key management system
        self.encryption_manager = CredentialEncryption(
            "test_master_key_for_config_service"
        )

        # Cache for loaded configurations
        self._app_config: Optional[Dict[str, Any]] = None
        self._exchange_configs: Optional[Dict[str, ExchangeConfig]] = None
        self._custom_field_configs: Optional[Dict[str, CustomFieldConfig]] = None

    def get_app_config(self) -> Dict[str, Any]:
        """
        Get application configuration settings.

        Returns:
            Dictionary containing application configuration
        """
        if self._app_config is None:
            self._load_app_config()
        return self._app_config.copy()

    def update_app_config(self, config_updates: Dict[str, Any]) -> None:
        """
        Update application configuration settings.

        Args:
            config_updates: Dictionary of configuration updates
        """
        if self._app_config is None:
            self._load_app_config()

        self._app_config.update(config_updates)
        self._save_app_config()

    def get_exchange_config(self, exchange_name: str) -> Optional[ExchangeConfig]:
        """
        Get configuration for a specific exchange.

        Args:
            exchange_name: Name of the exchange

        Returns:
            ExchangeConfig object or None if not found
        """
        if self._exchange_configs is None:
            self._load_exchange_configs()

        return self._exchange_configs.get(exchange_name)

    def get_all_exchange_configs(self) -> Dict[str, ExchangeConfig]:
        """
        Get all exchange configurations.

        Returns:
            Dictionary mapping exchange names to ExchangeConfig objects
        """
        if self._exchange_configs is None:
            self._load_exchange_configs()

        return self._exchange_configs.copy()

    def save_exchange_config(self, config: ExchangeConfig) -> None:
        """
        Save or update exchange configuration.

        Args:
            config: ExchangeConfig object to save
        """
        if self._exchange_configs is None:
            self._load_exchange_configs()

        # Update timestamp
        config.updated_at = datetime.now()

        # Store in cache
        self._exchange_configs[config.name] = config

        # Persist to file
        self._save_exchange_configs()

    def delete_exchange_config(self, exchange_name: str) -> bool:
        """
        Delete exchange configuration.

        Args:
            exchange_name: Name of the exchange to delete

        Returns:
            True if deleted, False if not found
        """
        if self._exchange_configs is None:
            self._load_exchange_configs()

        if exchange_name in self._exchange_configs:
            del self._exchange_configs[exchange_name]
            self._save_exchange_configs()
            return True

        return False

    def get_active_exchanges(self) -> List[ExchangeConfig]:
        """
        Get list of active exchange configurations.

        Returns:
            List of active ExchangeConfig objects
        """
        if self._exchange_configs is None:
            self._load_exchange_configs()

        return [
            config for config in self._exchange_configs.values() if config.is_active
        ]

    def get_custom_field_config(self, field_name: str) -> Optional[CustomFieldConfig]:
        """
        Get configuration for a specific custom field.

        Args:
            field_name: Name of the custom field

        Returns:
            CustomFieldConfig object or None if not found
        """
        if self._custom_field_configs is None:
            self._load_custom_field_configs()

        return self._custom_field_configs.get(field_name)

    def get_all_custom_field_configs(self) -> Dict[str, CustomFieldConfig]:
        """
        Get all custom field configurations.

        Returns:
            Dictionary mapping field names to CustomFieldConfig objects
        """
        if self._custom_field_configs is None:
            self._load_custom_field_configs()

        return self._custom_field_configs.copy()

    def save_custom_field_config(self, config: CustomFieldConfig) -> None:
        """
        Save or update custom field configuration.

        Args:
            config: CustomFieldConfig object to save
        """
        if self._custom_field_configs is None:
            self._load_custom_field_configs()

        # Update timestamp
        config.updated_at = datetime.now()

        # Store in cache
        self._custom_field_configs[config.field_name] = config

        # Persist to file
        self._save_custom_field_configs()

    def delete_custom_field_config(self, field_name: str) -> bool:
        """
        Delete custom field configuration.

        Args:
            field_name: Name of the field to delete

        Returns:
            True if deleted, False if not found
        """
        if self._custom_field_configs is None:
            self._load_custom_field_configs()

        if field_name in self._custom_field_configs:
            del self._custom_field_configs[field_name]
            self._save_custom_field_configs()
            return True

        return False

    def get_confluence_options(self) -> List[str]:
        """
        Get available confluence options from custom field configurations.

        Returns:
            List of confluence option strings
        """
        confluence_config = self.get_custom_field_config("confluences")
        if confluence_config and confluence_config.field_type in [
            FieldType.SELECT,
            FieldType.MULTISELECT,
        ]:
            return confluence_config.options.copy()

        return []

    def update_confluence_options(self, options: List[str]) -> None:
        """
        Update confluence options in custom field configuration.

        Args:
            options: List of confluence option strings
        """
        confluence_config = self.get_custom_field_config("confluences")

        if confluence_config is None:
            # Create default confluence configuration
            confluence_config = CustomFieldConfig(
                field_name="confluences",
                field_type=FieldType.MULTISELECT,
                options=options,
                is_required=False,
                description="Trading confluences for analysis",
            )
        else:
            confluence_config.update_options(options)

        self.save_custom_field_config(confluence_config)

    def validate_api_key(self, exchange_name: str, api_key: str) -> bool:
        """
        Validate API key format and basic requirements.

        Args:
            exchange_name: Name of the exchange
            api_key: API key to validate

        Returns:
            True if API key format is valid, False otherwise
        """
        if not api_key or not isinstance(api_key, str):
            return False

        # Remove whitespace
        api_key = api_key.strip()

        if not api_key:
            return False

        # Basic validation based on exchange
        if exchange_name.lower() == "bitunix":
            # Bitunix API keys are typically 16-128 characters alphanumeric with some special chars
            if len(api_key) < 8 or len(api_key) > 128:
                return False

            # Should contain only alphanumeric characters and some special chars
            import re

            if not re.match(r"^[a-zA-Z0-9\-_]+$", api_key):
                return False

        return True

    def encrypt_and_store_api_key(self, exchange_name: str, api_key: str) -> str:
        """
        Encrypt API key and return encrypted string for storage.

        Args:
            exchange_name: Name of the exchange
            api_key: Plain text API key

        Returns:
            Encrypted API key string

        Raises:
            ValueError: If encryption fails
        """
        try:
            return self.encryption_manager.encrypt_credential(api_key)
        except Exception as e:
            raise ValueError(f"Failed to encrypt API key for {exchange_name}: {e}")

    def decrypt_api_key(self, exchange_name: str, encrypted_api_key: str) -> str:
        """
        Decrypt stored API key.

        Args:
            exchange_name: Name of the exchange
            encrypted_api_key: Encrypted API key string

        Returns:
            Decrypted API key

        Raises:
            ValueError: If decryption fails
        """
        try:
            return self.encryption_manager.decrypt_credential(encrypted_api_key)
        except Exception as e:
            raise ValueError(f"Failed to decrypt API key for {exchange_name}: {e}")

    def test_exchange_connection(
        self, exchange_name: str, api_key: str = None, api_secret: str = None
    ) -> bool:
        """
        Test connection to exchange using API key.

        Args:
            exchange_name: Name of the exchange
            api_key: API key to test (if None, uses stored key)

        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Get API credentials if not provided
            if api_key is None:
                config = self.get_exchange_config(exchange_name)
                if not config:
                    return False
                api_key = self.decrypt_api_key(exchange_name, config.api_key_encrypted)

                # Get API secret if available
                if config.api_secret_encrypted:
                    api_secret = self.decrypt_api_key(
                        f"{exchange_name}_secret", config.api_secret_encrypted
                    )

            # Import exchange client dynamically based on exchange name
            if exchange_name.lower() == "bitunix":
                # Import and test with actual Bitunix client
                from ..integrations.bitunix_client import BitunixClient

                client = BitunixClient(api_key=api_key, api_secret=api_secret)
                return client.test_connection()

            return False

        except Exception as e:
            self.logger.error(f"Failed to test connection for {exchange_name}: {e}")
            return False

    def update_exchange_connection_status(
        self, exchange_name: str, status: ConnectionStatus
    ) -> None:
        """
        Update connection status for an exchange.

        Args:
            exchange_name: Name of the exchange
            status: New connection status
        """
        config = self.get_exchange_config(exchange_name)
        if config:
            config.update_connection_status(status)
            self.save_exchange_config(config)

    def monitor_exchange_connections(self) -> Dict[str, ConnectionStatus]:
        """
        Monitor all active exchange connections and update their status.

        Returns:
            Dictionary mapping exchange names to their connection status
        """
        status_map = {}
        active_exchanges = self.get_active_exchanges()

        for exchange_config in active_exchanges:
            try:
                # Update status to testing
                self.update_exchange_connection_status(
                    exchange_config.name, ConnectionStatus.TESTING
                )

                # Test connection
                is_connected = self.test_exchange_connection(exchange_config.name)

                # Update status based on test result
                new_status = (
                    ConnectionStatus.CONNECTED
                    if is_connected
                    else ConnectionStatus.ERROR
                )
                self.update_exchange_connection_status(exchange_config.name, new_status)

                status_map[exchange_config.name] = new_status

            except Exception:
                # Update status to error
                self.update_exchange_connection_status(
                    exchange_config.name, ConnectionStatus.ERROR
                )
                status_map[exchange_config.name] = ConnectionStatus.ERROR

        return status_map

    def create_exchange_config_with_validation(
        self,
        exchange_name: str,
        api_key: str,
        api_secret: str = None,
        test_connection: bool = True,
    ) -> ExchangeConfig:
        """
        Create and validate a new exchange configuration.

        Args:
            exchange_name: Name of the exchange
            api_key: API key for the exchange
            test_connection: Whether to test the connection before saving

        Returns:
            Created ExchangeConfig object

        Raises:
            ValueError: If validation fails
        """
        # Validate API key format
        if not self.validate_api_key(exchange_name, api_key):
            raise ValueError(f"Invalid API key format for {exchange_name}")

        # Encrypt API key
        encrypted_key = self.encrypt_and_store_api_key(exchange_name, api_key)

        # Encrypt API secret if provided
        encrypted_secret = None
        if api_secret:
            encrypted_secret = self.encrypt_and_store_api_key(
                f"{exchange_name}_secret", api_secret
            )

        # Create configuration
        config = ExchangeConfig(
            name=exchange_name,
            api_key_encrypted=encrypted_key,
            api_secret_encrypted=encrypted_secret,
            is_active=True,
            connection_status=ConnectionStatus.UNKNOWN,
        )

        # Test connection if requested
        if test_connection:
            is_connected = self.test_exchange_connection(
                exchange_name, api_key, api_secret
            )
            config.connection_status = (
                ConnectionStatus.CONNECTED if is_connected else ConnectionStatus.ERROR
            )

        # Save configuration
        self.save_exchange_config(config)

        return config

    def update_exchange_api_key(
        self, exchange_name: str, new_api_key: str, test_connection: bool = True
    ) -> bool:
        """
        Update API key for an existing exchange configuration.

        Args:
            exchange_name: Name of the exchange
            new_api_key: New API key
            test_connection: Whether to test the connection before saving

        Returns:
            True if update successful, False otherwise
        """
        try:
            # Get existing configuration
            config = self.get_exchange_config(exchange_name)
            if not config:
                return False

            # Validate new API key format
            if not self.validate_api_key(exchange_name, new_api_key):
                return False

            # Encrypt new API key
            encrypted_key = self.encrypt_and_store_api_key(exchange_name, new_api_key)

            # Update configuration
            config.api_key_encrypted = encrypted_key
            config.connection_status = ConnectionStatus.UNKNOWN

            # Test connection if requested
            if test_connection:
                is_connected = self.test_exchange_connection(exchange_name, new_api_key)
                config.connection_status = (
                    ConnectionStatus.CONNECTED
                    if is_connected
                    else ConnectionStatus.ERROR
                )

            # Save updated configuration
            self.save_exchange_config(config)

            return True

        except Exception:
            return False

    def update_exchange_credentials(
        self,
        exchange_name: str,
        new_api_key: str,
        new_api_secret: str = None,
        test_connection: bool = True,
    ) -> bool:
        """
        Update API key and secret for an existing exchange configuration.

        Args:
            exchange_name: Name of the exchange
            new_api_key: New API key
            new_api_secret: New API secret (optional)
            test_connection: Whether to test the connection before saving

        Returns:
            True if update successful, False otherwise
        """
        try:
            # Get existing configuration
            config = self.get_exchange_config(exchange_name)
            if not config:
                return False

            # Validate new API key format
            if not self.validate_api_key(exchange_name, new_api_key):
                return False

            # Encrypt new API key
            encrypted_key = self.encrypt_and_store_api_key(exchange_name, new_api_key)

            # Encrypt new API secret if provided
            encrypted_secret = None
            if new_api_secret:
                encrypted_secret = self.encrypt_and_store_api_key(
                    f"{exchange_name}_secret", new_api_secret
                )

            # Update configuration
            config.api_key_encrypted = encrypted_key
            config.api_secret_encrypted = encrypted_secret
            config.connection_status = ConnectionStatus.UNKNOWN

            # Test connection if requested
            if test_connection:
                is_connected = self.test_exchange_connection(
                    exchange_name, new_api_key, new_api_secret
                )
                config.connection_status = (
                    ConnectionStatus.CONNECTED
                    if is_connected
                    else ConnectionStatus.ERROR
                )

            # Save updated configuration
            self.save_exchange_config(config)

            return True

        except Exception:
            return False

    def get_exchange_connection_summary(self) -> Dict[str, Dict[str, Any]]:
        """
        Get summary of all exchange connections and their status.

        Returns:
            Dictionary with exchange connection summaries
        """
        summary = {}
        all_configs = self.get_all_exchange_configs()

        for name, config in all_configs.items():
            summary[name] = {
                "is_active": config.is_active,
                "connection_status": config.connection_status.value,
                "last_sync": config.last_sync.isoformat() if config.last_sync else None,
                "needs_sync": config.needs_sync(),
                "display_name": config.get_display_name(),
                "created_at": config.created_at.isoformat(),
                "updated_at": config.updated_at.isoformat(),
            }

        return summary

    def initialize_default_config(self) -> None:
        """
        Initialize default configuration if none exists.
        """
        # Initialize default app config
        if not self.config_file.exists():
            default_config = {
                "app_name": "Crypto Trading Journal",
                "version": "1.0.0",
                "data_retention_days": 365,
                "auto_sync_enabled": True,
                "sync_interval_hours": 24,
                "theme": "light",
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
            }
            self._app_config = default_config
            self._save_app_config()

        # Initialize default custom fields
        if not self.custom_fields_file.exists():
            default_fields = {
                "confluences": CustomFieldConfig(
                    field_name="confluences",
                    field_type=FieldType.MULTISELECT,
                    options=[
                        "Support/Resistance",
                        "Moving Average",
                        "RSI",
                        "Volume",
                        "News",
                    ],
                    is_required=False,
                    description="Trading confluences for analysis",
                ),
                "win_loss": CustomFieldConfig(
                    field_name="win_loss",
                    field_type=FieldType.SELECT,
                    options=["win", "loss"],
                    is_required=False,
                    description="Trade outcome classification",
                ),
            }
            self._custom_field_configs = default_fields
            self._save_custom_field_configs()

    def _load_app_config(self) -> None:
        """Load application configuration from file."""
        if self.config_file.exists():
            try:
                with open(self.config_file, "r") as f:
                    self._app_config = json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                raise ValueError(f"Failed to load app configuration: {e}")
        else:
            self._app_config = {}

    def _save_app_config(self) -> None:
        """Save application configuration to file."""
        try:
            with open(self.config_file, "w") as f:
                json.dump(self._app_config, f, indent=2, default=str)
        except IOError as e:
            raise ValueError(f"Failed to save app configuration: {e}")

    def _load_exchange_configs(self) -> None:
        """Load exchange configurations from file."""
        if self.exchanges_file.exists():
            try:
                with open(self.exchanges_file, "r") as f:
                    data = json.load(f)

                self._exchange_configs = {}
                for name, config_data in data.items():
                    self._exchange_configs[name] = (
                        DataSerializer.deserialize_exchange_config(config_data)
                    )

            except (json.JSONDecodeError, IOError, ValueError) as e:
                raise ValueError(f"Failed to load exchange configurations: {e}")
        else:
            self._exchange_configs = {}

    def _save_exchange_configs(self) -> None:
        """Save exchange configurations to file."""
        try:
            data = {}
            for name, config in self._exchange_configs.items():
                data[name] = DataSerializer.serialize_exchange_config(config)

            with open(self.exchanges_file, "w") as f:
                json.dump(data, f, indent=2, default=str)
        except IOError as e:
            raise ValueError(f"Failed to save exchange configurations: {e}")

    def _load_custom_field_configs(self) -> None:
        """Load custom field configurations from file."""
        if self.custom_fields_file.exists():
            try:
                with open(self.custom_fields_file, "r") as f:
                    data = json.load(f)

                self._custom_field_configs = {}
                for name, config_data in data.items():
                    self._custom_field_configs[name] = (
                        DataSerializer.deserialize_custom_field_config(config_data)
                    )

            except (json.JSONDecodeError, IOError, ValueError) as e:
                raise ValueError(f"Failed to load custom field configurations: {e}")
        else:
            self._custom_field_configs = {}

    def _save_custom_field_configs(self) -> None:
        """Save custom field configurations to file."""
        try:
            data = {}
            for name, config in self._custom_field_configs.items():
                data[name] = DataSerializer.serialize_custom_field_config(config)

            with open(self.custom_fields_file, "w") as f:
                json.dump(data, f, indent=2, default=str)
        except IOError as e:
            raise ValueError(f"Failed to save custom field configurations: {e}")
