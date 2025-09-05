"""
Tests for exchange synchronization service.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from decimal import Decimal

from app.services.exchange_sync_service import (
    ExchangeSyncService,
    SyncStatus,
    SyncResult,
    PositionReconciliation
)
from app.services.config_service import ConfigService
from app.models.position import Position, PositionStatus, PositionSide
from app.models.exchange_config import ExchangeConfig, ConnectionStatus
from app.integrations.base_exchange import AuthenticationError, APIError, NetworkError


class TestExchangeSyncService:
    """Test cases for ExchangeSyncService."""
    
    @pytest.fixture
    def mock_config_service(self):
        """Create a mock configuration service."""
        config_service = Mock(spec=ConfigService)
        
        # Mock exchange config
        exchange_config = ExchangeConfig(
            name="bitunix",
            api_key_encrypted="encrypted_key",
            is_active=True,
            connection_status=ConnectionStatus.CONNECTED
        )
        config_service.get_exchange_config.return_value = exchange_config
        config_service.get_active_exchanges.return_value = [exchange_config]
        config_service.decrypt_api_key.return_value = "decrypted_api_key"
        
        return config_service
    
    @pytest.fixture
    def sync_service(self, mock_config_service):
        """Create an ExchangeSyncService instance for testing."""
        return ExchangeSyncService(mock_config_service)
    
    @pytest.fixture
    def sample_positions(self):
        """Create sample position data for testing."""
        return [
            Position(
                position_id="pos1",
                symbol="BTCUSDT",
                side=PositionSide.LONG,
                size=Decimal("1.0"),
                entry_price=Decimal("45000.00"),
                mark_price=Decimal("46000.00"),
                unrealized_pnl=Decimal("1000.00"),
                realized_pnl=Decimal("0.00"),
                status=PositionStatus.OPEN,
                open_time=datetime.now() - timedelta(hours=1),
                raw_data={"positionId": "pos1"}
            ),
            Position(
                position_id="pos2",
                symbol="ETHUSDT",
                side=PositionSide.SHORT,
                size=Decimal("5.0"),
                entry_price=Decimal("3000.00"),
                mark_price=Decimal("2950.00"),
                unrealized_pnl=Decimal("250.00"),
                realized_pnl=Decimal("100.00"),
                status=PositionStatus.PARTIALLY_CLOSED,
                open_time=datetime.now() - timedelta(hours=2),
                raw_data={"positionId": "pos2"}
            ),
            Position(
                position_id="pos3",
                symbol="ADAUSDT",
                side=PositionSide.LONG,
                size=Decimal("1000.0"),
                entry_price=Decimal("1.50"),
                mark_price=Decimal("1.55"),
                unrealized_pnl=Decimal("50.00"),
                realized_pnl=Decimal("25.00"),
                status=PositionStatus.CLOSED,
                open_time=datetime.now() - timedelta(hours=3),
                close_time=datetime.now() - timedelta(minutes=30),
                raw_data={"positionId": "pos3"}
            )
        ]
    
    def test_sync_exchange_success(self, sync_service, mock_config_service, sample_positions):
        """Test successful exchange synchronization."""
        # Mock exchange client
        mock_client = Mock()
        mock_client.get_position_history.return_value = sample_positions
        
        # Mock the exchange factory directly on the sync service
        sync_service.exchange_factory = Mock()
        sync_service.exchange_factory.create_exchange_client.return_value = mock_client
        
        # Perform sync
        result = sync_service.sync_exchange("bitunix")
        
        # Verify result
        assert result.exchange_name == "bitunix"
        assert result.status == SyncStatus.COMPLETED
        assert result.positions_fetched == 3
        assert result.positions_added == 3  # All new positions
        assert result.positions_updated == 0
        assert len(result.errors) == 0
        assert result.end_time is not None
        
        # Verify client was called correctly
        mock_client.get_position_history.assert_called_once()
        
        # Verify config was updated
        mock_config_service.save_exchange_config.assert_called_once()
    
    def test_sync_exchange_with_updates(self, sync_service, mock_config_service, sample_positions):
        """Test exchange synchronization with position updates."""
        # Mock exchange client
        mock_client = Mock()
        mock_client.get_position_history.return_value = sample_positions
        
        # Mock the exchange factory directly on the sync service
        sync_service.exchange_factory = Mock()
        sync_service.exchange_factory.create_exchange_client.return_value = mock_client
        
        # Pre-populate cache with existing position (different data)
        existing_position = Position(
            position_id="pos1",
            symbol="BTCUSDT",
            side=PositionSide.LONG,
            size=Decimal("1.0"),
            entry_price=Decimal("45000.00"),
            mark_price=Decimal("45500.00"),  # Different mark price
            unrealized_pnl=Decimal("500.00"),  # Different PnL
            realized_pnl=Decimal("0.00"),
            status=PositionStatus.OPEN,
            open_time=datetime.now() - timedelta(hours=1),
            raw_data={"positionId": "pos1"}
        )
        sync_service._position_cache = {"bitunix": {"pos1": existing_position}}
        
        # Perform sync
        result = sync_service.sync_exchange("bitunix")
        
        # Verify result
        assert result.status == SyncStatus.COMPLETED
        assert result.positions_fetched == 3
        assert result.positions_added == 2  # pos2 and pos3 are new
        assert result.positions_updated == 1  # pos1 was updated
    
    def test_sync_exchange_authentication_error(self, sync_service, mock_config_service):
        """Test exchange synchronization with authentication error."""
        # Mock exchange client to raise authentication error
        mock_client = Mock()
        mock_client.get_position_history.side_effect = AuthenticationError("Invalid API key")
        
        # Mock the exchange factory directly on the sync service
        sync_service.exchange_factory = Mock()
        sync_service.exchange_factory.create_exchange_client.return_value = mock_client
        
        # Perform sync
        result = sync_service.sync_exchange("bitunix")
        
        # Verify result
        assert result.status == SyncStatus.FAILED
        assert result.positions_fetched == 0
        assert len(result.errors) == 1
        assert "Exchange API error" in result.errors[0]
        
        # Verify config status was updated to error
        saved_config = mock_config_service.save_exchange_config.call_args[0][0]
        assert saved_config.connection_status == ConnectionStatus.ERROR
    
    def test_sync_exchange_network_error(self, sync_service, mock_config_service):
        """Test exchange synchronization with network error."""
        # Mock exchange client to raise network error
        mock_client = Mock()
        mock_client.get_position_history.side_effect = NetworkError("Connection timeout")
        
        # Mock the exchange factory directly on the sync service
        sync_service.exchange_factory = Mock()
        sync_service.exchange_factory.create_exchange_client.return_value = mock_client
        
        # Perform sync
        result = sync_service.sync_exchange("bitunix")
        
        # Verify result
        assert result.status == SyncStatus.FAILED
        assert "Exchange API error" in result.errors[0]
    
    def test_sync_exchange_no_config(self, sync_service, mock_config_service):
        """Test exchange synchronization with no configuration."""
        mock_config_service.get_exchange_config.return_value = None
        
        result = sync_service.sync_exchange("nonexistent")
        
        assert result.status == SyncStatus.FAILED
        assert "No configuration found" in result.errors[0]
    
    def test_sync_exchange_inactive(self, sync_service, mock_config_service):
        """Test exchange synchronization with inactive exchange."""
        inactive_config = ExchangeConfig(
            name="bitunix",
            api_key_encrypted="encrypted_key",
            is_active=False,
            connection_status=ConnectionStatus.CONNECTED
        )
        mock_config_service.get_exchange_config.return_value = inactive_config
        
        result = sync_service.sync_exchange("bitunix")
        
        assert result.status == SyncStatus.FAILED
        assert "is not active" in result.errors[0]
    
    def test_sync_all_exchanges(self, sync_service, mock_config_service, sample_positions):
        """Test synchronization of all active exchanges."""
        # Mock multiple exchange configs
        exchange_configs = [
            ExchangeConfig(name="bitunix", api_key_encrypted="key1", is_active=True),
            ExchangeConfig(name="binance", api_key_encrypted="key2", is_active=True)
        ]
        mock_config_service.get_active_exchanges.return_value = exchange_configs
        mock_config_service.get_exchange_config.side_effect = lambda name: next(
            (config for config in exchange_configs if config.name == name), None
        )
        
        # Mock exchange client
        mock_client = Mock()
        mock_client.get_position_history.return_value = sample_positions
        
        # Mock the exchange factory directly on the sync service
        sync_service.exchange_factory = Mock()
        sync_service.exchange_factory.create_exchange_client.return_value = mock_client
        
        # Perform sync
        results = sync_service.sync_all_exchanges()
        
        # Verify results
        assert len(results) == 2
        assert "bitunix" in results
        assert "binance" in results
        assert all(result.status == SyncStatus.COMPLETED for result in results.values())
    
    def test_sync_partial_positions(self, sync_service, mock_config_service, sample_positions):
        """Test synchronization of partially closed positions."""
        # Set up partial position tracking
        sync_service._partial_positions = {"bitunix": {"pos2"}}
        sync_service._position_cache = {
            "bitunix": {
                "pos2": sample_positions[1]  # The partially closed position
            }
        }
        
        # Mock exchange client
        mock_client = Mock()
        # Return updated position that is now fully closed
        updated_position = Position(
            position_id="pos2",
            symbol="ETHUSDT",
            side=PositionSide.SHORT,
            size=Decimal("5.0"),
            entry_price=Decimal("3000.00"),
            mark_price=Decimal("2950.00"),
            unrealized_pnl=Decimal("0.00"),  # No unrealized PnL
            realized_pnl=Decimal("250.00"),  # All PnL realized
            status=PositionStatus.CLOSED,  # Now fully closed
            open_time=datetime.now() - timedelta(hours=2),
            close_time=datetime.now() - timedelta(minutes=10),
            raw_data={"positionId": "pos2"}
        )
        mock_client.get_position_by_id.return_value = updated_position
        
        # Mock the exchange factory directly on the sync service
        sync_service.exchange_factory = Mock()
        sync_service.exchange_factory.create_exchange_client.return_value = mock_client
        
        # Perform partial sync
        result = sync_service.sync_partial_positions("bitunix")
        
        # Verify result
        assert result.status == SyncStatus.COMPLETED
        assert result.positions_fetched == 1
        assert result.positions_updated == 1
        
        # Verify position is no longer tracked as partial
        assert "pos2" not in sync_service._partial_positions.get("bitunix", set())
    
    def test_sync_partial_positions_no_partials(self, sync_service):
        """Test partial sync when no partial positions exist."""
        result = sync_service.sync_partial_positions("bitunix")
        
        assert result.status == SyncStatus.COMPLETED
        assert result.positions_fetched == 0
        assert result.positions_updated == 0
    
    def test_get_positions_all(self, sync_service, sample_positions):
        """Test getting all positions."""
        sync_service._position_cache = {
            "bitunix": {pos.position_id: pos for pos in sample_positions[:2]},
            "binance": {sample_positions[2].position_id: sample_positions[2]}
        }
        
        positions = sync_service.get_positions()
        
        assert len(positions) == 2
        assert "bitunix" in positions
        assert "binance" in positions
        assert len(positions["bitunix"]) == 2
        assert len(positions["binance"]) == 1
    
    def test_get_positions_specific_exchange(self, sync_service, sample_positions):
        """Test getting positions for a specific exchange."""
        sync_service._position_cache = {
            "bitunix": {pos.position_id: pos for pos in sample_positions}
        }
        
        positions = sync_service.get_positions("bitunix")
        
        assert len(positions) == 1
        assert "bitunix" in positions
        assert len(positions["bitunix"]) == 3
    
    def test_get_position_by_id(self, sync_service, sample_positions):
        """Test getting a specific position by ID."""
        sync_service._position_cache = {
            "bitunix": {sample_positions[0].position_id: sample_positions[0]}
        }
        
        position = sync_service.get_position_by_id("bitunix", "pos1")
        
        assert position is not None
        assert position.position_id == "pos1"
        assert position.symbol == "BTCUSDT"
    
    def test_get_position_by_id_not_found(self, sync_service):
        """Test getting a position that doesn't exist."""
        position = sync_service.get_position_by_id("bitunix", "nonexistent")
        
        assert position is None
    
    def test_get_partial_positions(self, sync_service, sample_positions):
        """Test getting partially closed positions."""
        sync_service._position_cache = {
            "bitunix": {pos.position_id: pos for pos in sample_positions}
        }
        sync_service._partial_positions = {"bitunix": {"pos2"}}
        
        partial_positions = sync_service.get_partial_positions("bitunix")
        
        assert len(partial_positions) == 1
        assert "bitunix" in partial_positions
        assert len(partial_positions["bitunix"]) == 1
        assert partial_positions["bitunix"][0].position_id == "pos2"
    
    def test_reconcile_positions_new_position(self, sync_service, sample_positions):
        """Test reconciliation with new positions."""
        local_positions = {}
        remote_positions = [sample_positions[0]]
        
        reconciliations = sync_service._reconcile_positions("bitunix", local_positions, remote_positions)
        
        assert len(reconciliations) == 1
        assert reconciliations[0].action == 'add'
        assert reconciliations[0].reason == 'New position from exchange'
        assert reconciliations[0].remote_position.position_id == "pos1"
    
    def test_reconcile_positions_update_needed(self, sync_service, sample_positions):
        """Test reconciliation when position update is needed."""
        # Create local position with different data
        local_position = Position(
            position_id="pos1",
            symbol="BTCUSDT",
            side=PositionSide.LONG,
            size=Decimal("1.0"),
            entry_price=Decimal("45000.00"),
            mark_price=Decimal("45500.00"),  # Different mark price
            unrealized_pnl=Decimal("500.00"),  # Different PnL
            realized_pnl=Decimal("0.00"),
            status=PositionStatus.OPEN,
            open_time=datetime.now() - timedelta(hours=1),
            raw_data={"positionId": "pos1"}
        )
        
        local_positions = {"pos1": local_position}
        remote_positions = [sample_positions[0]]  # Has different mark_price and PnL
        
        reconciliations = sync_service._reconcile_positions("bitunix", local_positions, remote_positions)
        
        assert len(reconciliations) == 1
        assert reconciliations[0].action == 'update'
        assert reconciliations[0].reason == 'Position data changed'
    
    def test_reconcile_positions_no_update_needed(self, sync_service, sample_positions):
        """Test reconciliation when no update is needed."""
        local_positions = {"pos1": sample_positions[0]}
        remote_positions = [sample_positions[0]]
        
        reconciliations = sync_service._reconcile_positions("bitunix", local_positions, remote_positions)
        
        assert len(reconciliations) == 1
        assert reconciliations[0].action == 'skip'
        assert reconciliations[0].reason == 'No changes detected'
    
    def test_reconcile_positions_partial_tracking(self, sync_service, sample_positions):
        """Test reconciliation marks partially closed positions for tracking."""
        local_positions = {}
        remote_positions = [sample_positions[1]]  # Partially closed position
        
        reconciliations = sync_service._reconcile_positions("bitunix", local_positions, remote_positions)
        
        assert len(reconciliations) == 1
        assert reconciliations[0].needs_tracking is True
    
    def test_position_needs_update_status_change(self, sync_service, sample_positions):
        """Test position update detection for status change."""
        local_position = sample_positions[0]  # OPEN status
        remote_position = Position(
            position_id="pos1",
            symbol="BTCUSDT",
            side=PositionSide.LONG,
            size=Decimal("1.0"),
            entry_price=Decimal("45000.00"),
            mark_price=Decimal("46000.00"),
            unrealized_pnl=Decimal("1000.00"),
            realized_pnl=Decimal("0.00"),
            status=PositionStatus.CLOSED,  # Different status
            open_time=datetime.now() - timedelta(hours=1),
            close_time=datetime.now(),
            raw_data={"positionId": "pos1"}
        )
        
        needs_update = sync_service._position_needs_update(local_position, remote_position)
        
        assert needs_update is True
    
    def test_position_needs_update_price_change(self, sync_service, sample_positions):
        """Test position update detection for price change."""
        local_position = sample_positions[0]
        remote_position = Position(
            position_id="pos1",
            symbol="BTCUSDT",
            side=PositionSide.LONG,
            size=Decimal("1.0"),
            entry_price=Decimal("45000.00"),
            mark_price=Decimal("47000.00"),  # Different mark price
            unrealized_pnl=Decimal("2000.00"),  # Different PnL
            realized_pnl=Decimal("0.00"),
            status=PositionStatus.OPEN,
            open_time=datetime.now() - timedelta(hours=1),
            raw_data={"positionId": "pos1"}
        )
        
        needs_update = sync_service._position_needs_update(local_position, remote_position)
        
        assert needs_update is True
    
    def test_position_needs_update_no_change(self, sync_service, sample_positions):
        """Test position update detection when no change is needed."""
        local_position = sample_positions[0]
        remote_position = sample_positions[0]  # Same position
        
        needs_update = sync_service._position_needs_update(local_position, remote_position)
        
        assert needs_update is False
    
    def test_track_partial_position(self, sync_service):
        """Test tracking a partially closed position."""
        sync_service._track_partial_position("bitunix", "pos1")
        
        assert "bitunix" in sync_service._partial_positions
        assert "pos1" in sync_service._partial_positions["bitunix"]
    
    def test_untrack_partial_position(self, sync_service):
        """Test untracking a partially closed position."""
        sync_service._partial_positions = {"bitunix": {"pos1", "pos2"}}
        
        sync_service._untrack_partial_position("bitunix", "pos1")
        
        assert "pos1" not in sync_service._partial_positions["bitunix"]
        assert "pos2" in sync_service._partial_positions["bitunix"]
    
    def test_get_sync_start_time_force_full(self, sync_service):
        """Test sync start time with force full sync."""
        start_time = sync_service._get_sync_start_time("bitunix", force_full_sync=True)
        
        assert start_time is None
    
    def test_get_sync_start_time_with_last_sync(self, sync_service):
        """Test sync start time with previous sync time."""
        last_sync = datetime.now() - timedelta(hours=2)
        sync_service._last_sync_times["bitunix"] = last_sync
        
        start_time = sync_service._get_sync_start_time("bitunix", force_full_sync=False)
        
        # Should be 1 hour before last sync
        expected_time = last_sync - timedelta(hours=1)
        assert abs((start_time - expected_time).total_seconds()) < 60  # Within 1 minute
    
    def test_get_sync_start_time_first_sync(self, sync_service):
        """Test sync start time for first sync."""
        start_time = sync_service._get_sync_start_time("bitunix", force_full_sync=False)
        
        # Should be 30 days ago
        expected_time = datetime.now() - timedelta(days=30)
        assert abs((start_time - expected_time).total_seconds()) < 3600  # Within 1 hour


class TestSyncResult:
    """Test cases for SyncResult dataclass."""
    
    def test_sync_result_duration(self):
        """Test sync result duration calculation."""
        start_time = datetime.now()
        end_time = start_time + timedelta(minutes=5)
        
        result = SyncResult(
            exchange_name="bitunix",
            status=SyncStatus.COMPLETED,
            positions_fetched=10,
            positions_updated=5,
            positions_added=5,
            errors=[],
            start_time=start_time,
            end_time=end_time
        )
        
        duration = result.get_duration()
        assert duration == timedelta(minutes=5)
    
    def test_sync_result_duration_no_end_time(self):
        """Test sync result duration when no end time is set."""
        result = SyncResult(
            exchange_name="bitunix",
            status=SyncStatus.IN_PROGRESS,
            positions_fetched=0,
            positions_updated=0,
            positions_added=0,
            errors=[],
            start_time=datetime.now()
        )
        
        duration = result.get_duration()
        assert duration is None
    
    def test_sync_result_is_successful_completed(self):
        """Test sync result success check for completed status."""
        result = SyncResult(
            exchange_name="bitunix",
            status=SyncStatus.COMPLETED,
            positions_fetched=10,
            positions_updated=5,
            positions_added=5,
            errors=[],
            start_time=datetime.now()
        )
        
        assert result.is_successful() is True
    
    def test_sync_result_is_successful_partial(self):
        """Test sync result success check for partial status."""
        result = SyncResult(
            exchange_name="bitunix",
            status=SyncStatus.PARTIAL,
            positions_fetched=10,
            positions_updated=5,
            positions_added=3,
            errors=["Some positions failed to parse"],
            start_time=datetime.now()
        )
        
        assert result.is_successful() is True
    
    def test_sync_result_is_successful_failed(self):
        """Test sync result success check for failed status."""
        result = SyncResult(
            exchange_name="bitunix",
            status=SyncStatus.FAILED,
            positions_fetched=0,
            positions_updated=0,
            positions_added=0,
            errors=["Authentication failed"],
            start_time=datetime.now()
        )
        
        assert result.is_successful() is False


class TestPositionReconciliation:
    """Test cases for PositionReconciliation dataclass."""
    
    def test_position_reconciliation_creation(self):
        """Test creation of position reconciliation object."""
        local_position = Position(
            position_id="pos1",
            symbol="BTCUSDT",
            side=PositionSide.LONG,
            size=Decimal("1.0"),
            entry_price=Decimal("45000.00"),
            mark_price=Decimal("46000.00"),
            unrealized_pnl=Decimal("1000.00"),
            realized_pnl=Decimal("0.00"),
            status=PositionStatus.OPEN,
            open_time=datetime.now(),
            raw_data={}
        )
        
        reconciliation = PositionReconciliation(
            local_position=local_position,
            remote_position=None,
            action='update',
            reason='Position data changed',
            needs_tracking=True
        )
        
        assert reconciliation.local_position == local_position
        assert reconciliation.remote_position is None
        assert reconciliation.action == 'update'
        assert reconciliation.reason == 'Position data changed'
        assert reconciliation.needs_tracking is True