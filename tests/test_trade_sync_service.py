"""
Integration tests for TradeSyncService class.
"""

import pytest
import tempfile
import shutil
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch, MagicMock

from app.services.trade_sync_service import TradeSyncService, TradeSyncStatus, TradeSyncResult
from app.services.data_service import DataService
from app.services.config_service import ConfigService
from app.services.exchange_sync_service import ExchangeSyncService, SyncStatus, SyncResult
from app.models.trade import Trade, TradeStatus, TradeSide, WinLoss
from app.models.position import Position, PositionStatus, PositionSide
from app.models.exchange_config import ExchangeConfig, ConnectionStatus


class TestTradeSyncService:
    """Test cases for TradeSyncService."""
    
    @pytest.fixture
    def temp_data_dir(self):
        """Create temporary directory for test data."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def mock_config_service(self):
        """Create mock configuration service."""
        mock_service = Mock(spec=ConfigService)
        
        # Mock exchange config
        exchange_config = ExchangeConfig(
            name="bitunix",
            api_key_encrypted="encrypted_key",
            is_active=True,
            connection_status=ConnectionStatus.CONNECTED
        )
        
        mock_service.get_active_exchanges.return_value = [exchange_config]
        mock_service.get_exchange_config.return_value = exchange_config
        mock_service.decrypt_api_key.return_value = "decrypted_api_key"
        
        return mock_service
    
    @pytest.fixture
    def data_service(self, temp_data_dir):
        """Create DataService instance with temporary directory."""
        return DataService(temp_data_dir)
    
    @pytest.fixture
    def mock_exchange_sync_service(self):
        """Create mock exchange sync service."""
        mock_service = Mock(spec=ExchangeSyncService)
        return mock_service
    
    @pytest.fixture
    def trade_sync_service(self, mock_config_service, data_service, mock_exchange_sync_service):
        """Create TradeSyncService instance with mocked dependencies."""
        return TradeSyncService(mock_config_service, data_service, mock_exchange_sync_service)
    
    @pytest.fixture
    def sample_position(self):
        """Create a sample position for testing."""
        return Position(
            position_id="pos_123",
            symbol="BTCUSDT",
            side=PositionSide.LONG,
            size=Decimal("0.1"),
            entry_price=Decimal("50000.00"),
            mark_price=Decimal("51000.00"),
            unrealized_pnl=Decimal("100.00"),
            realized_pnl=Decimal("0.00"),
            status=PositionStatus.OPEN,
            open_time=datetime(2024, 1, 1, 12, 0, 0),
            close_time=None,
            raw_data={"exchange": "bitunix"}
        )
    
    @pytest.fixture
    def closed_position(self):
        """Create a closed position for testing."""
        return Position(
            position_id="pos_456",
            symbol="ETHUSDT",
            side=PositionSide.SHORT,
            size=Decimal("1.0"),
            entry_price=Decimal("3000.00"),
            mark_price=Decimal("2900.00"),
            unrealized_pnl=Decimal("0.00"),
            realized_pnl=Decimal("100.00"),
            status=PositionStatus.CLOSED,
            open_time=datetime(2024, 1, 2, 10, 0, 0),
            close_time=datetime(2024, 1, 2, 14, 0, 0),
            raw_data={"exchange": "bitunix", "close_price": "2900.00"}
        )
    
    def test_sync_exchange_trades_success(self, trade_sync_service, mock_exchange_sync_service, sample_position):
        """Test successful trade synchronization for an exchange."""
        # Mock successful position sync
        position_sync_result = SyncResult(
            exchange_name="bitunix",
            status=SyncStatus.COMPLETED,
            positions_fetched=1,
            positions_updated=0,
            positions_added=1,
            errors=[],
            start_time=datetime.now()
        )
        mock_exchange_sync_service.sync_exchange.return_value = position_sync_result
        mock_exchange_sync_service.get_positions.return_value = {"bitunix": [sample_position]}
        
        # Perform sync
        result = trade_sync_service.sync_exchange_trades("bitunix")
        
        # Verify result
        assert result.status == TradeSyncStatus.COMPLETED
        assert result.exchange_name == "bitunix"
        assert result.positions_processed == 1
        assert result.trades_created == 1
        assert result.trades_updated == 0
        assert result.trades_skipped == 0
        assert len(result.errors) == 0
        
        # Verify trade was created
        trades = trade_sync_service.data_service.load_trades()
        assert len(trades) == 1
        
        trade = trades[0]
        assert trade.exchange == "bitunix"
        assert trade.symbol == "BTCUSDT"
        assert trade.side == TradeSide.LONG
        assert trade.status == TradeStatus.OPEN
        assert trade.entry_price == Decimal("50000.00")
        assert trade.quantity == Decimal("0.1")
    
    def test_sync_exchange_trades_with_closed_position(self, trade_sync_service, mock_exchange_sync_service, closed_position):
        """Test synchronization with a closed position."""
        # Mock successful position sync
        position_sync_result = SyncResult(
            exchange_name="bitunix",
            status=SyncStatus.COMPLETED,
            positions_fetched=1,
            positions_updated=0,
            positions_added=1,
            errors=[],
            start_time=datetime.now()
        )
        mock_exchange_sync_service.sync_exchange.return_value = position_sync_result
        mock_exchange_sync_service.get_positions.return_value = {"bitunix": [closed_position]}
        
        # Perform sync
        result = trade_sync_service.sync_exchange_trades("bitunix")
        
        # Verify result
        assert result.status == TradeSyncStatus.COMPLETED
        assert result.trades_created == 1
        
        # Verify trade was created with correct data
        trades = trade_sync_service.data_service.load_trades()
        assert len(trades) == 1
        
        trade = trades[0]
        assert trade.status == TradeStatus.CLOSED
        assert trade.side == TradeSide.SHORT
        assert trade.pnl == Decimal("100.00")
        assert trade.win_loss == WinLoss.WIN
        assert trade.exit_time == closed_position.close_time
    
    def test_sync_exchange_trades_update_existing(self, trade_sync_service, mock_exchange_sync_service, sample_position):
        """Test updating existing trades during sync."""
        # Create existing trade
        existing_trade = Trade(
            id=trade_sync_service._generate_trade_id_from_position(sample_position),
            exchange="bitunix",
            symbol="BTCUSDT",
            side=TradeSide.LONG,
            entry_price=Decimal("50000.00"),
            quantity=Decimal("0.1"),
            entry_time=datetime(2024, 1, 1, 12, 0, 0),
            status=TradeStatus.OPEN,
            pnl=Decimal("50.00")  # Different PnL to trigger update
        )
        trade_sync_service.data_service.add_trade(existing_trade)
        
        # Mock position sync
        position_sync_result = SyncResult(
            exchange_name="bitunix",
            status=SyncStatus.COMPLETED,
            positions_fetched=1,
            positions_updated=0,
            positions_added=1,
            errors=[],
            start_time=datetime.now()
        )
        mock_exchange_sync_service.sync_exchange.return_value = position_sync_result
        mock_exchange_sync_service.get_positions.return_value = {"bitunix": [sample_position]}
        
        # Perform sync
        result = trade_sync_service.sync_exchange_trades("bitunix")
        
        # Verify result
        assert result.status == TradeSyncStatus.COMPLETED
        assert result.trades_created == 0
        assert result.trades_updated == 1
        assert result.trades_skipped == 0
        
        # Verify trade was updated
        trades = trade_sync_service.data_service.load_trades()
        assert len(trades) == 1
        
        trade = trades[0]
        assert trade.pnl == Decimal("100.00")  # Updated PnL
    
    def test_sync_exchange_trades_skip_unchanged(self, trade_sync_service, mock_exchange_sync_service, sample_position):
        """Test skipping unchanged trades during sync."""
        # Create existing trade with same data
        existing_trade = Trade(
            id=trade_sync_service._generate_trade_id_from_position(sample_position),
            exchange="bitunix",
            symbol="BTCUSDT",
            side=TradeSide.LONG,
            entry_price=Decimal("50000.00"),
            quantity=Decimal("0.1"),
            entry_time=datetime(2024, 1, 1, 12, 0, 0),
            status=TradeStatus.OPEN,
            pnl=Decimal("100.00")  # Same PnL as position
        )
        trade_sync_service.data_service.add_trade(existing_trade)
        
        # Mock position sync
        position_sync_result = SyncResult(
            exchange_name="bitunix",
            status=SyncStatus.COMPLETED,
            positions_fetched=1,
            positions_updated=0,
            positions_added=1,
            errors=[],
            start_time=datetime.now()
        )
        mock_exchange_sync_service.sync_exchange.return_value = position_sync_result
        mock_exchange_sync_service.get_positions.return_value = {"bitunix": [sample_position]}
        
        # Perform sync
        result = trade_sync_service.sync_exchange_trades("bitunix")
        
        # Verify result
        assert result.status == TradeSyncStatus.COMPLETED
        assert result.trades_created == 0
        assert result.trades_updated == 0
        assert result.trades_skipped == 1
    
    def test_sync_exchange_trades_position_sync_failure(self, trade_sync_service, mock_exchange_sync_service):
        """Test handling of position sync failure."""
        # Mock failed position sync
        position_sync_result = SyncResult(
            exchange_name="bitunix",
            status=SyncStatus.FAILED,
            positions_fetched=0,
            positions_updated=0,
            positions_added=0,
            errors=["API connection failed"],
            start_time=datetime.now()
        )
        mock_exchange_sync_service.sync_exchange.return_value = position_sync_result
        
        # Perform sync
        result = trade_sync_service.sync_exchange_trades("bitunix")
        
        # Verify result
        assert result.status == TradeSyncStatus.FAILED
        assert "API connection failed" in result.errors
        assert result.trades_created == 0
        assert result.trades_updated == 0
    
    def test_sync_all_exchanges(self, trade_sync_service, mock_exchange_sync_service, sample_position):
        """Test synchronizing all active exchanges."""
        # Mock position sync
        position_sync_result = SyncResult(
            exchange_name="bitunix",
            status=SyncStatus.COMPLETED,
            positions_fetched=1,
            positions_updated=0,
            positions_added=1,
            errors=[],
            start_time=datetime.now()
        )
        mock_exchange_sync_service.sync_exchange.return_value = position_sync_result
        mock_exchange_sync_service.get_positions.return_value = {"bitunix": [sample_position]}
        
        # Perform sync
        results = trade_sync_service.sync_all_exchanges()
        
        # Verify results
        assert "bitunix" in results
        assert results["bitunix"].status == TradeSyncStatus.COMPLETED
        assert results["bitunix"].trades_created == 1
    
    def test_sync_incremental(self, trade_sync_service, mock_exchange_sync_service):
        """Test incremental synchronization."""
        # Set last sync time
        trade_sync_service._last_sync_times["bitunix"] = datetime.now() - timedelta(hours=1)
        
        # Mock position sync
        position_sync_result = SyncResult(
            exchange_name="bitunix",
            status=SyncStatus.COMPLETED,
            positions_fetched=0,
            positions_updated=0,
            positions_added=0,
            errors=[],
            start_time=datetime.now()
        )
        mock_exchange_sync_service.sync_exchange.return_value = position_sync_result
        mock_exchange_sync_service.get_positions.return_value = {"bitunix": []}
        
        # Perform incremental sync
        result = trade_sync_service.sync_incremental("bitunix")
        
        # Verify result
        assert result.status == TradeSyncStatus.COMPLETED
        assert result.positions_processed == 0
    
    def test_get_sync_statistics(self, trade_sync_service, sample_position):
        """Test getting sync statistics."""
        # Add some test data
        trade = Trade(
            id="test_trade",
            exchange="bitunix",
            symbol="BTCUSDT",
            side=TradeSide.LONG,
            entry_price=Decimal("50000.00"),
            quantity=Decimal("0.1"),
            entry_time=datetime.now(),
            status=TradeStatus.OPEN
        )
        trade_sync_service.data_service.add_trade(trade)
        
        # Set last sync time
        sync_time = datetime.now() - timedelta(hours=2)
        trade_sync_service._last_sync_times["bitunix"] = sync_time
        
        # Get statistics
        stats = trade_sync_service.get_sync_statistics("bitunix")
        
        # Verify statistics
        assert "bitunix" in stats
        assert stats["bitunix"]["total_trades"] == 1
        assert stats["bitunix"]["last_sync_time"] == sync_time.isoformat()
        assert abs(stats["bitunix"]["sync_age_hours"] - 2.0) < 0.1
    
    def test_get_sync_health(self, trade_sync_service):
        """Test getting sync health information."""
        # Set some sync times
        trade_sync_service._last_sync_times["bitunix"] = datetime.now() - timedelta(hours=1)  # Healthy
        
        # Get health info
        health = trade_sync_service.get_sync_health()
        
        # Verify health info
        assert health["total_exchanges"] == 1
        assert health["synced_exchanges"] == 1
        assert health["stale_exchanges"] == 0
        assert health["never_synced"] == 0
        assert "bitunix" in health["exchanges"]
        assert health["exchanges"]["bitunix"]["status"] == "healthy"
    
    def test_force_resync(self, trade_sync_service, mock_exchange_sync_service, sample_position):
        """Test forcing a complete resync."""
        # Set last sync time
        trade_sync_service._last_sync_times["bitunix"] = datetime.now() - timedelta(hours=1)
        
        # Mock position sync
        position_sync_result = SyncResult(
            exchange_name="bitunix",
            status=SyncStatus.COMPLETED,
            positions_fetched=1,
            positions_updated=0,
            positions_added=1,
            errors=[],
            start_time=datetime.now()
        )
        mock_exchange_sync_service.sync_exchange.return_value = position_sync_result
        mock_exchange_sync_service.get_positions.return_value = {"bitunix": [sample_position]}
        
        # Force resync
        result = trade_sync_service.force_resync("bitunix")
        
        # Verify result
        assert result.status == TradeSyncStatus.COMPLETED
        assert result.trades_created == 1
        
        # Verify last sync time was cleared and reset
        assert "bitunix" in trade_sync_service._last_sync_times
    
    def test_generate_trade_id_from_position(self, trade_sync_service, sample_position):
        """Test trade ID generation from position."""
        trade_id = trade_sync_service._generate_trade_id_from_position(sample_position)
        
        expected_id = f"bitunix_BTCUSDT_{sample_position.open_time.isoformat()}_long"
        assert trade_id == expected_id
    
    def test_position_status_to_trade_status(self, trade_sync_service):
        """Test position status to trade status conversion."""
        assert trade_sync_service._position_status_to_trade_status(PositionStatus.OPEN) == TradeStatus.OPEN
        assert trade_sync_service._position_status_to_trade_status(PositionStatus.CLOSED) == TradeStatus.CLOSED
        assert trade_sync_service._position_status_to_trade_status(PositionStatus.PARTIALLY_CLOSED) == TradeStatus.PARTIALLY_CLOSED
    
    def test_determine_win_loss(self, trade_sync_service):
        """Test win/loss determination from PnL."""
        assert trade_sync_service._determine_win_loss(Decimal("100.00")) == WinLoss.WIN
        assert trade_sync_service._determine_win_loss(Decimal("-50.00")) == WinLoss.LOSS
        assert trade_sync_service._determine_win_loss(Decimal("0.00")) == WinLoss.LOSS
        assert trade_sync_service._determine_win_loss(None) is None
    
    def test_filter_positions_by_sync_time(self, trade_sync_service):
        """Test filtering positions by sync time."""
        now = datetime.now()
        
        # Create positions with different timestamps
        old_position = Position(
            position_id="old_pos",
            symbol="BTCUSDT",
            side=PositionSide.LONG,
            size=Decimal("0.1"),
            entry_price=Decimal("50000.00"),
            mark_price=Decimal("51000.00"),
            unrealized_pnl=Decimal("100.00"),
            realized_pnl=Decimal("0.00"),
            status=PositionStatus.CLOSED,
            open_time=now - timedelta(hours=2),
            close_time=now - timedelta(hours=2),
            raw_data={"exchange": "bitunix"}
        )
        
        new_position = Position(
            position_id="new_pos",
            symbol="ETHUSDT",
            side=PositionSide.LONG,
            size=Decimal("1.0"),
            entry_price=Decimal("3000.00"),
            mark_price=Decimal("3100.00"),
            unrealized_pnl=Decimal("100.00"),
            realized_pnl=Decimal("0.00"),
            status=PositionStatus.CLOSED,
            open_time=now - timedelta(minutes=10),
            close_time=now - timedelta(minutes=5),
            raw_data={"exchange": "bitunix"}
        )
        
        # Set last sync time
        trade_sync_service._last_sync_times["bitunix"] = now - timedelta(hours=1)
        
        # Filter positions
        filtered = trade_sync_service._filter_positions_by_sync_time("bitunix", [old_position, new_position])
        
        # Should only include the new position
        assert len(filtered) == 1
        assert filtered[0].position_id == "new_pos"
    
    def test_trade_needs_update_status_change(self, trade_sync_service):
        """Test trade update detection for status changes."""
        trade = Trade(
            id="test_trade",
            exchange="bitunix",
            symbol="BTCUSDT",
            side=TradeSide.LONG,
            entry_price=Decimal("50000.00"),
            quantity=Decimal("0.1"),
            entry_time=datetime.now(),
            status=TradeStatus.OPEN
        )
        
        position = Position(
            position_id="pos_123",
            symbol="BTCUSDT",
            side=PositionSide.LONG,
            size=Decimal("0.1"),
            entry_price=Decimal("50000.00"),
            mark_price=Decimal("51000.00"),
            unrealized_pnl=Decimal("100.00"),
            realized_pnl=Decimal("100.00"),
            status=PositionStatus.CLOSED,  # Status changed
            open_time=datetime.now(),
            close_time=datetime.now(),
            raw_data={"exchange": "bitunix"}
        )
        
        assert trade_sync_service._trade_needs_update(trade, position) is True
    
    def test_trade_needs_update_pnl_change(self, trade_sync_service):
        """Test trade update detection for PnL changes."""
        trade = Trade(
            id="test_trade",
            exchange="bitunix",
            symbol="BTCUSDT",
            side=TradeSide.LONG,
            entry_price=Decimal("50000.00"),
            quantity=Decimal("0.1"),
            entry_time=datetime.now(),
            status=TradeStatus.OPEN,
            pnl=Decimal("50.00")  # Different PnL
        )
        
        position = Position(
            position_id="pos_123",
            symbol="BTCUSDT",
            side=PositionSide.LONG,
            size=Decimal("0.1"),
            entry_price=Decimal("50000.00"),
            mark_price=Decimal("51000.00"),
            unrealized_pnl=Decimal("100.00"),  # Different PnL
            realized_pnl=Decimal("0.00"),
            status=PositionStatus.OPEN,
            open_time=datetime.now(),
            raw_data={"exchange": "bitunix"}
        )
        
        assert trade_sync_service._trade_needs_update(trade, position) is True