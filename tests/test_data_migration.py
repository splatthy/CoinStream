"""
Unit tests for data migration utilities.
"""

import pytest
import json
import tempfile
import shutil
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import Mock, patch

from app.utils.data_migration import (
    DataMigrator, MigrationError, MigrationStep,
    migrate_data, get_current_schema_version, set_schema_version,
    validate_data_structure, backup_before_migration
)


class TestDataMigrator:
    """Test cases for DataMigrator class."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for testing."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def data_migrator(self, temp_dir):
        """Create DataMigrator instance."""
        return DataMigrator(data_dir=temp_dir)
    
    @pytest.fixture
    def sample_v1_data(self):
        """Sample version 1 data structure."""
        return {
            "schema_version": 1,
            "trades": [
                {
                    "id": "trade1",
                    "symbol": "BTCUSDT",
                    "side": "long",
                    "entry_price": "50000.00",
                    "quantity": "0.1",
                    "entry_time": "2024-01-01T10:00:00",
                    "status": "closed",
                    "pnl": "100.00"
                }
            ]
        }
    
    @pytest.fixture
    def sample_v2_data(self):
        """Sample version 2 data structure."""
        return {
            "schema_version": 2,
            "trades": [
                {
                    "id": "trade1",
                    "exchange": "bitunix",  # New field
                    "symbol": "BTCUSDT",
                    "side": "long",
                    "entry_price": "50000.00",
                    "quantity": "0.1",
                    "entry_time": "2024-01-01T10:00:00",
                    "status": "closed",
                    "pnl": "100.00",
                    "confluences": [],  # New field
                    "custom_fields": {}  # New field
                }
            ]
        }
    
    def test_init(self, temp_dir):
        """Test DataMigrator initialization."""
        migrator = DataMigrator(data_dir=temp_dir)
        
        assert migrator.data_dir == Path(temp_dir)
        assert migrator.current_version == 3  # Latest version
        assert len(migrator.migration_steps) > 0
    
    def test_get_current_schema_version_no_file(self, data_migrator):
        """Test getting schema version when no data file exists."""
        version = data_migrator.get_current_schema_version()
        assert version == 0  # No data file means version 0
    
    def test_get_current_schema_version_with_file(self, data_migrator, sample_v1_data, temp_dir):
        """Test getting schema version from existing file."""
        data_file = Path(temp_dir) / "trades.json"
        with open(data_file, 'w') as f:
            json.dump(sample_v1_data, f)
        
        version = data_migrator.get_current_schema_version()
        assert version == 1
    
    def test_get_current_schema_version_no_version_field(self, data_migrator, temp_dir):
        """Test getting schema version when file has no version field."""
        data_file = Path(temp_dir) / "trades.json"
        data_without_version = {"trades": []}
        
        with open(data_file, 'w') as f:
            json.dump(data_without_version, f)
        
        version = data_migrator.get_current_schema_version()
        assert version == 1  # Default to version 1 for legacy data
    
    def test_set_schema_version(self, data_migrator, sample_v1_data, temp_dir):
        """Test setting schema version."""
        data_file = Path(temp_dir) / "trades.json"
        with open(data_file, 'w') as f:
            json.dump(sample_v1_data, f)
        
        data_migrator.set_schema_version(2)
        
        with open(data_file, 'r') as f:
            updated_data = json.load(f)
        
        assert updated_data["schema_version"] == 2
    
    def test_needs_migration_true(self, data_migrator, sample_v1_data, temp_dir):
        """Test needs_migration returns True when migration is needed."""
        data_file = Path(temp_dir) / "trades.json"
        with open(data_file, 'w') as f:
            json.dump(sample_v1_data, f)
        
        assert data_migrator.needs_migration() is True
    
    def test_needs_migration_false(self, data_migrator, temp_dir):
        """Test needs_migration returns False when no migration is needed."""
        data_file = Path(temp_dir) / "trades.json"
        current_version_data = {"schema_version": 3, "trades": []}
        
        with open(data_file, 'w') as f:
            json.dump(current_version_data, f)
        
        assert data_migrator.needs_migration() is False
    
    def test_validate_data_structure_valid(self, data_migrator, sample_v2_data):
        """Test data structure validation with valid data."""
        result = data_migrator.validate_data_structure(sample_v2_data, version=2)
        assert result is True
    
    def test_validate_data_structure_invalid(self, data_migrator):
        """Test data structure validation with invalid data."""
        invalid_data = {"invalid": "structure"}
        
        result = data_migrator.validate_data_structure(invalid_data, version=2)
        assert result is False
    
    def test_migrate_v1_to_v2(self, data_migrator, sample_v1_data):
        """Test migration from version 1 to version 2."""
        migrated_data = data_migrator._migrate_v1_to_v2(sample_v1_data)
        
        assert migrated_data["schema_version"] == 2
        
        # Check that new fields were added
        trade = migrated_data["trades"][0]
        assert "exchange" in trade
        assert trade["exchange"] == "bitunix"  # Default exchange
        assert "confluences" in trade
        assert trade["confluences"] == []
        assert "custom_fields" in trade
        assert trade["custom_fields"] == {}
    
    def test_migrate_v2_to_v3(self, data_migrator, sample_v2_data):
        """Test migration from version 2 to version 3."""
        migrated_data = data_migrator._migrate_v2_to_v3(sample_v2_data)
        
        assert migrated_data["schema_version"] == 3
        
        # Check that new fields were added
        trade = migrated_data["trades"][0]
        assert "win_loss" in trade
        assert trade["win_loss"] is None  # Default value
        assert "exit_price" in trade
        assert "exit_time" in trade
        assert "created_at" in trade
        assert "updated_at" in trade
    
    def test_perform_migration_single_step(self, data_migrator, sample_v1_data, temp_dir):
        """Test performing single migration step."""
        data_file = Path(temp_dir) / "trades.json"
        with open(data_file, 'w') as f:
            json.dump(sample_v1_data, f)
        
        with patch.object(data_migrator, '_create_backup') as mock_backup:
            mock_backup.return_value = "/path/to/backup"
            
            result = data_migrator.perform_migration()
        
        assert result is True
        mock_backup.assert_called_once()
        
        # Verify data was migrated
        with open(data_file, 'r') as f:
            migrated_data = json.load(f)
        
        assert migrated_data["schema_version"] == 3
    
    def test_perform_migration_multiple_steps(self, data_migrator, temp_dir):
        """Test performing multiple migration steps."""
        # Create version 1 data
        v1_data = {
            "schema_version": 1,
            "trades": [
                {
                    "id": "trade1",
                    "symbol": "BTCUSDT",
                    "side": "long",
                    "entry_price": "50000.00",
                    "quantity": "0.1",
                    "entry_time": "2024-01-01T10:00:00",
                    "status": "closed",
                    "pnl": "100.00"
                }
            ]
        }
        
        data_file = Path(temp_dir) / "trades.json"
        with open(data_file, 'w') as f:
            json.dump(v1_data, f)
        
        with patch.object(data_migrator, '_create_backup') as mock_backup:
            mock_backup.return_value = "/path/to/backup"
            
            result = data_migrator.perform_migration()
        
        assert result is True
        
        # Verify data went through all migration steps
        with open(data_file, 'r') as f:
            migrated_data = json.load(f)
        
        assert migrated_data["schema_version"] == 3
        
        # Verify all new fields are present
        trade = migrated_data["trades"][0]
        assert "exchange" in trade
        assert "confluences" in trade
        assert "custom_fields" in trade
        assert "win_loss" in trade
        assert "created_at" in trade
        assert "updated_at" in trade
    
    def test_perform_migration_no_migration_needed(self, data_migrator, temp_dir):
        """Test performing migration when no migration is needed."""
        current_data = {"schema_version": 3, "trades": []}
        data_file = Path(temp_dir) / "trades.json"
        
        with open(data_file, 'w') as f:
            json.dump(current_data, f)
        
        result = data_migrator.perform_migration()
        assert result is True  # No migration needed, but still successful
    
    def test_perform_migration_backup_failure(self, data_migrator, sample_v1_data, temp_dir):
        """Test migration with backup failure."""
        data_file = Path(temp_dir) / "trades.json"
        with open(data_file, 'w') as f:
            json.dump(sample_v1_data, f)
        
        with patch.object(data_migrator, '_create_backup') as mock_backup:
            mock_backup.side_effect = Exception("Backup failed")
            
            with pytest.raises(MigrationError, match="Failed to create backup"):
                data_migrator.perform_migration()
    
    def test_perform_migration_validation_failure(self, data_migrator, temp_dir):
        """Test migration with validation failure."""
        invalid_data = {"invalid": "data"}
        data_file = Path(temp_dir) / "trades.json"
        
        with open(data_file, 'w') as f:
            json.dump(invalid_data, f)
        
        with pytest.raises(MigrationError, match="Data validation failed"):
            data_migrator.perform_migration()
    
    def test_rollback_migration(self, data_migrator, sample_v1_data, temp_dir):
        """Test rolling back migration."""
        data_file = Path(temp_dir) / "trades.json"
        with open(data_file, 'w') as f:
            json.dump(sample_v1_data, f)
        
        backup_path = "/path/to/backup.json"
        
        with patch('app.utils.data_migration.restore_backup') as mock_restore:
            data_migrator.rollback_migration(backup_path)
            mock_restore.assert_called_once_with(backup_path, str(data_file))
    
    def test_get_migration_history(self, data_migrator, temp_dir):
        """Test getting migration history."""
        # Create migration history file
        history_file = Path(temp_dir) / "migration_history.json"
        history_data = {
            "migrations": [
                {
                    "from_version": 1,
                    "to_version": 2,
                    "timestamp": "2024-01-01T10:00:00",
                    "backup_path": "/path/to/backup1.json"
                },
                {
                    "from_version": 2,
                    "to_version": 3,
                    "timestamp": "2024-01-01T10:05:00",
                    "backup_path": "/path/to/backup2.json"
                }
            ]
        }
        
        with open(history_file, 'w') as f:
            json.dump(history_data, f)
        
        history = data_migrator.get_migration_history()
        
        assert len(history) == 2
        assert history[0]["from_version"] == 1
        assert history[0]["to_version"] == 2
        assert history[1]["from_version"] == 2
        assert history[1]["to_version"] == 3
    
    def test_create_backup(self, data_migrator, sample_v1_data, temp_dir):
        """Test creating backup during migration."""
        data_file = Path(temp_dir) / "trades.json"
        with open(data_file, 'w') as f:
            json.dump(sample_v1_data, f)
        
        with patch('app.utils.data_migration.create_backup') as mock_create_backup:
            mock_create_backup.return_value = "/path/to/backup.json"
            
            backup_path = data_migrator._create_backup()
            
            assert backup_path == "/path/to/backup.json"
            mock_create_backup.assert_called_once()
    
    def test_record_migration(self, data_migrator, temp_dir):
        """Test recording migration in history."""
        backup_path = "/path/to/backup.json"
        
        with patch('app.utils.data_migration.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2024, 1, 1, 10, 0, 0)
            mock_datetime.isoformat = datetime.isoformat
            
            data_migrator._record_migration(1, 2, backup_path)
        
        # Verify history was recorded
        history_file = Path(temp_dir) / "migration_history.json"
        assert history_file.exists()
        
        with open(history_file, 'r') as f:
            history_data = json.load(f)
        
        assert len(history_data["migrations"]) == 1
        migration = history_data["migrations"][0]
        assert migration["from_version"] == 1
        assert migration["to_version"] == 2
        assert migration["backup_path"] == backup_path


class TestMigrationStep:
    """Test cases for MigrationStep dataclass."""
    
    def test_migration_step_creation(self):
        """Test MigrationStep creation."""
        def dummy_migration(data):
            return data
        
        step = MigrationStep(
            from_version=1,
            to_version=2,
            description="Migrate from v1 to v2",
            migration_function=dummy_migration
        )
        
        assert step.from_version == 1
        assert step.to_version == 2
        assert step.description == "Migrate from v1 to v2"
        assert step.migration_function == dummy_migration
    
    def test_migration_step_execution(self):
        """Test MigrationStep execution."""
        def add_field_migration(data):
            data["new_field"] = "new_value"
            return data
        
        step = MigrationStep(
            from_version=1,
            to_version=2,
            description="Add new field",
            migration_function=add_field_migration
        )
        
        input_data = {"existing_field": "value"}
        result = step.migration_function(input_data)
        
        assert result["existing_field"] == "value"
        assert result["new_field"] == "new_value"


class TestGlobalFunctions:
    """Test global migration functions."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for testing."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    @patch('app.utils.data_migration.DataMigrator')
    def test_migrate_data_function(self, mock_migrator_class, temp_dir):
        """Test global migrate_data function."""
        mock_migrator = Mock()
        mock_migrator.perform_migration.return_value = True
        mock_migrator_class.return_value = mock_migrator
        
        result = migrate_data(temp_dir)
        
        assert result is True
        mock_migrator_class.assert_called_once_with(temp_dir)
        mock_migrator.perform_migration.assert_called_once()
    
    @patch('app.utils.data_migration.DataMigrator')
    def test_get_current_schema_version_function(self, mock_migrator_class, temp_dir):
        """Test global get_current_schema_version function."""
        mock_migrator = Mock()
        mock_migrator.get_current_schema_version.return_value = 2
        mock_migrator_class.return_value = mock_migrator
        
        result = get_current_schema_version(temp_dir)
        
        assert result == 2
        mock_migrator_class.assert_called_once_with(temp_dir)
        mock_migrator.get_current_schema_version.assert_called_once()
    
    @patch('app.utils.data_migration.DataMigrator')
    def test_set_schema_version_function(self, mock_migrator_class, temp_dir):
        """Test global set_schema_version function."""
        mock_migrator = Mock()
        mock_migrator_class.return_value = mock_migrator
        
        set_schema_version(temp_dir, 3)
        
        mock_migrator_class.assert_called_once_with(temp_dir)
        mock_migrator.set_schema_version.assert_called_once_with(3)
    
    @patch('app.utils.data_migration.DataMigrator')
    def test_validate_data_structure_function(self, mock_migrator_class, temp_dir):
        """Test global validate_data_structure function."""
        mock_migrator = Mock()
        mock_migrator.validate_data_structure.return_value = True
        mock_migrator_class.return_value = mock_migrator
        
        data = {"test": "data"}
        result = validate_data_structure(data, version=2, data_dir=temp_dir)
        
        assert result is True
        mock_migrator_class.assert_called_once_with(temp_dir)
        mock_migrator.validate_data_structure.assert_called_once_with(data, version=2)
    
    @patch('app.utils.data_migration.create_backup')
    def test_backup_before_migration_function(self, mock_create_backup, temp_dir):
        """Test global backup_before_migration function."""
        mock_create_backup.return_value = "/path/to/backup.json"
        
        result = backup_before_migration(temp_dir)
        
        assert result == "/path/to/backup.json"
        mock_create_backup.assert_called_once()


class TestMigrationError:
    """Test MigrationError exception class."""
    
    def test_migration_error_creation(self):
        """Test MigrationError creation."""
        error = MigrationError("Migration failed")
        
        assert str(error) == "Migration failed"
        assert isinstance(error, Exception)
    
    def test_migration_error_with_cause(self):
        """Test MigrationError with underlying cause."""
        cause = ValueError("Original error")
        error = MigrationError("Migration failed", cause)
        
        assert str(error) == "Migration failed"
        assert error.__cause__ == cause


if __name__ == '__main__':
    pytest.main([__file__])