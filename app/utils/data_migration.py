"""
Data migration utilities for handling schema updates and version compatibility.
"""

import json
import os
from datetime import datetime
from typing import Dict, Any, List, Optional, Callable
from pathlib import Path

from app.utils.serialization import DataSerializer


class MigrationError(Exception):
    """Exception raised during data migration."""
    pass


class DataMigration:
    """Utility class for handling data migrations and schema updates."""
    
    # Current schema version
    CURRENT_VERSION = "1.0.0"
    
    # Migration functions registry
    MIGRATIONS: Dict[str, Callable] = {}
    
    @classmethod
    def register_migration(cls, from_version: str, to_version: str):
        """Decorator to register migration functions."""
        def decorator(func: Callable):
            cls.MIGRATIONS[f"{from_version}->{to_version}"] = func
            return func
        return decorator
    
    @staticmethod
    def get_data_version(data: Dict[str, Any]) -> str:
        """Get version from data dictionary."""
        return data.get('version', '0.0.0')
    
    @staticmethod
    def set_data_version(data: Dict[str, Any], version: str) -> Dict[str, Any]:
        """Set version in data dictionary."""
        data['version'] = version
        data['migrated_at'] = datetime.now().isoformat()
        return data
    
    @staticmethod
    def needs_migration(data: Dict[str, Any]) -> bool:
        """Check if data needs migration to current version."""
        current_version = DataMigration.get_data_version(data)
        return current_version != DataMigration.CURRENT_VERSION
    
    @staticmethod
    def migrate_data(data: Dict[str, Any]) -> Dict[str, Any]:
        """Migrate data to current version."""
        current_version = DataMigration.get_data_version(data)
        
        if current_version == DataMigration.CURRENT_VERSION:
            return data
        
        # Apply migrations in sequence
        migrated_data = data.copy()
        
        # For now, we'll handle basic version upgrades
        # In the future, this can be expanded with specific migration functions
        if current_version == '0.0.0':
            migrated_data = DataMigration._migrate_from_initial(migrated_data)
        
        # Set final version
        migrated_data = DataMigration.set_data_version(migrated_data, DataMigration.CURRENT_VERSION)
        
        return migrated_data
    
    @staticmethod
    def _migrate_from_initial(data: Dict[str, Any]) -> Dict[str, Any]:
        """Migrate from initial version (no version field) to 1.0.0."""
        migrated = data.copy()
        
        # Ensure all required fields exist
        if 'trades' not in migrated:
            migrated['trades'] = []
        
        if 'positions' not in migrated:
            migrated['positions'] = []
        
        if 'exchange_configs' not in migrated:
            migrated['exchange_configs'] = []
        
        if 'custom_field_configs' not in migrated:
            migrated['custom_field_configs'] = []
        
        # Migrate individual trade records
        if migrated['trades']:
            migrated_trades = []
            for trade_data in migrated['trades']:
                migrated_trade = DataMigration._migrate_trade_from_initial(trade_data)
                migrated_trades.append(migrated_trade)
            migrated['trades'] = migrated_trades
        
        # Migrate individual position records
        if migrated['positions']:
            migrated_positions = []
            for position_data in migrated['positions']:
                migrated_position = DataMigration._migrate_position_from_initial(position_data)
                migrated_positions.append(migrated_position)
            migrated['positions'] = migrated_positions
        
        return migrated
    
    @staticmethod
    def _migrate_trade_from_initial(trade_data: Dict[str, Any]) -> Dict[str, Any]:
        """Migrate individual trade record from initial version."""
        migrated = trade_data.copy()
        
        # Ensure required fields exist with defaults
        if 'confluences' not in migrated:
            migrated['confluences'] = []
        
        if 'custom_fields' not in migrated:
            migrated['custom_fields'] = {}
        
        if 'created_at' not in migrated:
            migrated['created_at'] = datetime.now().isoformat()
        
        if 'updated_at' not in migrated:
            migrated['updated_at'] = datetime.now().isoformat()
        
        # Convert old field names if they exist
        if 'pnl_value' in migrated:
            migrated['pnl'] = migrated.pop('pnl_value')
        
        if 'trade_side' in migrated:
            migrated['side'] = migrated.pop('trade_side')
        
        return migrated
    
    @staticmethod
    def _migrate_position_from_initial(position_data: Dict[str, Any]) -> Dict[str, Any]:
        """Migrate individual position record from initial version."""
        migrated = position_data.copy()
        
        # Ensure required fields exist with defaults
        if 'raw_data' not in migrated:
            migrated['raw_data'] = {}
        
        if 'created_at' not in migrated:
            migrated['created_at'] = datetime.now().isoformat()
        
        if 'updated_at' not in migrated:
            migrated['updated_at'] = datetime.now().isoformat()
        
        return migrated
    
    @staticmethod
    def create_backup(file_path: str, backup_dir: str = None) -> str:
        """Create backup of data file before migration."""
        if not os.path.exists(file_path):
            raise MigrationError(f"File not found: {file_path}")
        
        if backup_dir is None:
            backup_dir = os.path.join(os.path.dirname(file_path), 'backups')
        
        # Create backup directory if it doesn't exist
        os.makedirs(backup_dir, exist_ok=True)
        
        # Generate backup filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = os.path.basename(file_path)
        name, ext = os.path.splitext(filename)
        backup_filename = f"{name}_backup_{timestamp}{ext}"
        backup_path = os.path.join(backup_dir, backup_filename)
        
        # Copy file to backup location
        import shutil
        shutil.copy2(file_path, backup_path)
        
        return backup_path
    
    @staticmethod
    def validate_migrated_data(data: Dict[str, Any]) -> bool:
        """Validate migrated data structure."""
        try:
            # Check version
            if DataMigration.get_data_version(data) != DataMigration.CURRENT_VERSION:
                return False
            
            # Check required top-level keys
            required_keys = ['trades', 'positions', 'exchange_configs', 'custom_field_configs']
            for key in required_keys:
                if key not in data:
                    return False
                if not isinstance(data[key], list):
                    return False
            
            # Validate trade records
            for trade_data in data['trades']:
                try:
                    DataSerializer.deserialize_trade(trade_data)
                except Exception:
                    return False
            
            # Validate position records
            for position_data in data['positions']:
                try:
                    DataSerializer.deserialize_position(position_data)
                except Exception:
                    return False
            
            # Validate exchange config records
            for config_data in data['exchange_configs']:
                try:
                    DataSerializer.deserialize_exchange_config(config_data)
                except Exception:
                    return False
            
            # Validate custom field config records
            for field_config_data in data['custom_field_configs']:
                try:
                    DataSerializer.deserialize_custom_field_config(field_config_data)
                except Exception:
                    return False
            
            return True
            
        except Exception:
            return False
    
    @staticmethod
    def migrate_file(file_path: str, create_backup: bool = True) -> bool:
        """Migrate a data file to current version."""
        try:
            if not os.path.exists(file_path):
                # File doesn't exist, nothing to migrate
                return True
            
            # Load current data
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Check if migration is needed
            if not DataMigration.needs_migration(data):
                return True
            
            # Create backup if requested
            if create_backup:
                backup_path = DataMigration.create_backup(file_path)
                print(f"Created backup: {backup_path}")
            
            # Perform migration
            migrated_data = DataMigration.migrate_data(data)
            
            # Validate migrated data
            if not DataMigration.validate_migrated_data(migrated_data):
                raise MigrationError("Migrated data failed validation")
            
            # Write migrated data back to file
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(migrated_data, f, indent=2, ensure_ascii=False)
            
            print(f"Successfully migrated {file_path} to version {DataMigration.CURRENT_VERSION}")
            return True
            
        except Exception as e:
            raise MigrationError(f"Failed to migrate {file_path}: {str(e)}")


# Register specific migration functions
@DataMigration.register_migration("0.0.0", "1.0.0")
def migrate_initial_to_v1(data: Dict[str, Any]) -> Dict[str, Any]:
    """Migration from initial version to 1.0.0."""
    return DataMigration._migrate_from_initial(data)