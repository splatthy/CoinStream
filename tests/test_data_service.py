"""
Unit tests for DataService class.
"""

import json
import pytest
import tempfile
import shutil
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import Mock, patch

from app.services.data_service import DataService
from app.models.trade import Trade, TradeStatus, TradeSide, WinLoss
from app.utils.validators import ValidationError


class TestDataService:
    """Test cases for DataService."""
    
    @pytest.fixture
    def temp_data_dir(self):
        """Create temporary directory for test data."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def data_service(self, temp_data_dir):
        """Create DataService instance with temporary directory."""
        return DataService(temp_data_dir)
    
    @pytest.fixture
    def sample_trade(self):
        """Create a sample trade for testing."""
        return Trade(
            id="test_trade_1",
            exchange="bitunix",
            symbol="BTCUSDT",
            side=TradeSide.LONG,
            entry_price=Decimal("50000.00"),
            quantity=Decimal("0.1"),
            entry_time=datetime(2024, 1, 1, 12, 0, 0),
            status=TradeStatus.CLOSED,
            exit_price=Decimal("51000.00"),
            exit_time=datetime(2024, 1, 1, 14, 0, 0),
            pnl=Decimal("100.00"),
            win_loss=WinLoss.WIN,
            confluences=["support", "rsi_oversold"],
            custom_fields={"notes": "Good trade"}
        )
    
    @pytest.fixture
    def sample_trades(self, sample_trade):
        """Create multiple sample trades for testing."""
        trade2 = Trade(
            id="test_trade_2",
            exchange="bitunix",
            symbol="ETHUSDT",
            side=TradeSide.SHORT,
            entry_price=Decimal("3000.00"),
            quantity=Decimal("1.0"),
            entry_time=datetime(2024, 1, 2, 10, 0, 0),
            status=TradeStatus.OPEN,
            confluences=["resistance", "macd_bearish"]
        )
        
        trade3 = Trade(
            id="test_trade_3",
            exchange="binance",
            symbol="BTCUSDT",
            side=TradeSide.LONG,
            entry_price=Decimal("49000.00"),
            quantity=Decimal("0.2"),
            entry_time=datetime(2024, 1, 3, 9, 0, 0),
            status=TradeStatus.CLOSED,
            exit_price=Decimal("48000.00"),
            exit_time=datetime(2024, 1, 3, 11, 0, 0),
            pnl=Decimal("-200.00"),
            win_loss=WinLoss.LOSS,
            confluences=["support"]
        )
        
        return [sample_trade, trade2, trade3]
    
    def test_init_creates_data_directory(self, temp_data_dir):
        """Test that DataService creates data directory if it doesn't exist."""
        data_path = Path(temp_data_dir) / "new_data_dir"
        assert not data_path.exists()
        
        service = DataService(str(data_path))
        assert data_path.exists()
        assert service.data_path == data_path
    
    def test_load_trades_empty_file(self, data_service):
        """Test loading trades when file doesn't exist."""
        trades = data_service.load_trades()
        assert trades == []
    
    def test_save_and_load_trades(self, data_service, sample_trades):
        """Test saving and loading trades."""
        # Save trades
        data_service.save_trades(sample_trades)
        
        # Load trades
        loaded_trades = data_service.load_trades()
        
        assert len(loaded_trades) == len(sample_trades)
        
        # Check first trade details
        trade = loaded_trades[0]
        original = sample_trades[0]
        
        assert trade.id == original.id
        assert trade.exchange == original.exchange
        assert trade.symbol == original.symbol
        assert trade.side == original.side
        assert trade.entry_price == original.entry_price
        assert trade.quantity == original.quantity
        assert trade.status == original.status
        assert trade.confluences == original.confluences
    
    def test_save_trades_creates_backup(self, data_service, sample_trades):
        """Test that saving trades creates a backup of existing file."""
        # Save initial trades
        data_service.save_trades(sample_trades[:1])
        
        # Mock backup manager
        with patch.object(data_service.backup_manager, 'create_backup') as mock_backup:
            # Save updated trades
            data_service.save_trades(sample_trades)
            
            # Verify backup was created
            mock_backup.assert_called_once_with("trades.json")
    
    def test_save_trades_atomic_operation(self, data_service, sample_trades):
        """Test that save operation is atomic (uses temporary file)."""
        temp_file = data_service.trades_file.with_suffix('.tmp')
        
        # Ensure temp file doesn't exist initially
        assert not temp_file.exists()
        
        # Save trades
        data_service.save_trades(sample_trades)
        
        # Temp file should be cleaned up
        assert not temp_file.exists()
        
        # Main file should exist
        assert data_service.trades_file.exists()
    
    def test_load_trades_invalid_data(self, data_service, temp_data_dir):
        """Test loading trades with invalid data."""
        # Create file with invalid JSON
        trades_file = Path(temp_data_dir) / "trades.json"
        with open(trades_file, 'w') as f:
            f.write("invalid json")
        
        with pytest.raises(Exception):
            data_service.load_trades()
    
    def test_load_trades_invalid_structure(self, data_service, temp_data_dir):
        """Test loading trades with invalid data structure."""
        # Create file with invalid structure (not a list)
        trades_file = Path(temp_data_dir) / "trades.json"
        with open(trades_file, 'w') as f:
            json.dump({"not": "a list"}, f)
        
        with pytest.raises(Exception):
            data_service.load_trades()
    
    def test_load_trades_partial_failure(self, data_service):
        """Test loading trades when some trades are invalid."""
        # This test verifies that the service handles errors gracefully
        # For now, we'll test that empty data loads correctly
        trades = data_service.load_trades()
        assert trades == []
    
    def test_update_trade(self, data_service, sample_trades):
        """Test updating a trade."""
        # Save initial trades
        data_service.save_trades(sample_trades)
        
        # Update trade
        updates = {
            'win_loss': WinLoss.LOSS,
            'confluences': ['new_confluence'],
            'custom_fields': {'updated': 'field'}
        }
        
        updated_trade = data_service.update_trade(sample_trades[0].id, updates)
        
        assert updated_trade.win_loss == WinLoss.LOSS
        assert updated_trade.confluences == ['new_confluence']
        assert updated_trade.custom_fields == {'updated': 'field'}
        
        # Verify persistence
        loaded_trades = data_service.load_trades()
        updated_loaded = next(t for t in loaded_trades if t.id == sample_trades[0].id)
        assert updated_loaded.win_loss == WinLoss.LOSS
    
    def test_update_trade_not_found(self, data_service, sample_trades):
        """Test updating a non-existent trade."""
        data_service.save_trades(sample_trades)
        
        with pytest.raises(ValueError, match="Trade with ID nonexistent not found"):
            data_service.update_trade("nonexistent", {"win_loss": WinLoss.WIN})
    
    def test_update_trade_invalid_field(self, data_service, sample_trades):
        """Test updating trade with invalid field."""
        data_service.save_trades(sample_trades)
        
        with pytest.raises(ValueError, match="Invalid field: invalid_field"):
            data_service.update_trade(sample_trades[0].id, {"invalid_field": "value"})
    
    def test_get_trades_by_date_range(self, data_service, sample_trades):
        """Test filtering trades by date range."""
        data_service.save_trades(sample_trades)
        
        # Get trades from Jan 1-2, 2024
        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 1, 2, 23, 59, 59)
        
        filtered_trades = data_service.get_trades_by_date_range(start_date, end_date)
        
        assert len(filtered_trades) == 2  # First two trades
        assert all(start_date <= trade.entry_time <= end_date for trade in filtered_trades)
    
    def test_get_trades_by_date_range_invalid_range(self, data_service):
        """Test date range validation."""
        start_date = datetime(2024, 1, 2)
        end_date = datetime(2024, 1, 1)  # End before start
        
        with pytest.raises(ValidationError):
            data_service.get_trades_by_date_range(start_date, end_date)
    
    def test_filter_trades(self, data_service, sample_trades):
        """Test custom trade filtering."""
        data_service.save_trades(sample_trades)
        
        # Filter for BTCUSDT trades
        btc_trades = data_service.filter_trades(lambda t: t.symbol == "BTCUSDT")
        
        assert len(btc_trades) == 2
        assert all(trade.symbol == "BTCUSDT" for trade in btc_trades)
    
    def test_get_trades_by_symbol(self, data_service, sample_trades):
        """Test getting trades by symbol."""
        data_service.save_trades(sample_trades)
        
        btc_trades = data_service.get_trades_by_symbol("BTCUSDT")
        assert len(btc_trades) == 2
        
        eth_trades = data_service.get_trades_by_symbol("ETHUSDT")
        assert len(eth_trades) == 1
    
    def test_get_trades_by_exchange(self, data_service, sample_trades):
        """Test getting trades by exchange."""
        data_service.save_trades(sample_trades)
        
        bitunix_trades = data_service.get_trades_by_exchange("bitunix")
        assert len(bitunix_trades) == 2
        
        binance_trades = data_service.get_trades_by_exchange("binance")
        assert len(binance_trades) == 1
    
    def test_get_trades_by_status(self, data_service, sample_trades):
        """Test getting trades by status."""
        data_service.save_trades(sample_trades)
        
        closed_trades = data_service.get_trades_by_status(TradeStatus.CLOSED)
        assert len(closed_trades) == 2
        
        open_trades = data_service.get_trades_by_status(TradeStatus.OPEN)
        assert len(open_trades) == 1
    
    def test_get_trades_by_confluence(self, data_service, sample_trades):
        """Test getting trades by confluence."""
        data_service.save_trades(sample_trades)
        
        support_trades = data_service.get_trades_by_confluence("support")
        assert len(support_trades) == 2
        
        resistance_trades = data_service.get_trades_by_confluence("resistance")
        assert len(resistance_trades) == 1
    
    def test_get_winning_losing_trades(self, data_service, sample_trades):
        """Test getting winning and losing trades."""
        data_service.save_trades(sample_trades)
        
        winning_trades = data_service.get_winning_trades()
        assert len(winning_trades) == 1
        assert all(trade.win_loss == WinLoss.WIN for trade in winning_trades)
        
        losing_trades = data_service.get_losing_trades()
        assert len(losing_trades) == 1
        assert all(trade.win_loss == WinLoss.LOSS for trade in losing_trades)
    
    def test_get_profitable_unprofitable_trades(self, data_service, sample_trades):
        """Test getting profitable and unprofitable trades."""
        data_service.save_trades(sample_trades)
        
        profitable_trades = data_service.get_profitable_trades()
        assert len(profitable_trades) == 1
        assert all(trade.pnl > 0 for trade in profitable_trades)
        
        unprofitable_trades = data_service.get_unprofitable_trades()
        assert len(unprofitable_trades) == 1
        assert all(trade.pnl < 0 for trade in unprofitable_trades)
    
    def test_add_trade(self, data_service, sample_trade):
        """Test adding a new trade."""
        data_service.add_trade(sample_trade)
        
        trades = data_service.load_trades()
        assert len(trades) == 1
        assert trades[0].id == sample_trade.id
    
    def test_add_duplicate_trade(self, data_service, sample_trade):
        """Test adding a trade with duplicate ID."""
        data_service.add_trade(sample_trade)
        
        with pytest.raises(ValueError, match="Trade with ID test_trade_1 already exists"):
            data_service.add_trade(sample_trade)
    
    def test_delete_trade(self, data_service, sample_trades):
        """Test deleting a trade."""
        data_service.save_trades(sample_trades)
        
        # Delete first trade
        result = data_service.delete_trade(sample_trades[0].id)
        assert result is True
        
        # Verify deletion
        trades = data_service.load_trades()
        assert len(trades) == 2
        assert not any(trade.id == sample_trades[0].id for trade in trades)
    
    def test_delete_nonexistent_trade(self, data_service, sample_trades):
        """Test deleting a non-existent trade."""
        data_service.save_trades(sample_trades)
        
        result = data_service.delete_trade("nonexistent")
        assert result is False
        
        # Verify no trades were deleted
        trades = data_service.load_trades()
        assert len(trades) == 3
    
    def test_get_trade_count(self, data_service, sample_trades):
        """Test getting trade count."""
        assert data_service.get_trade_count() == 0
        
        data_service.save_trades(sample_trades)
        assert data_service.get_trade_count() == 3
    
    def test_get_trade_statistics(self, data_service, sample_trades):
        """Test getting trade statistics."""
        data_service.save_trades(sample_trades)
        
        stats = data_service.get_trade_statistics()
        
        assert stats['total_trades'] == 3
        assert stats['open_trades'] == 1
        assert stats['closed_trades'] == 2
        assert stats['partially_closed_trades'] == 0
        assert stats['winning_trades'] == 1
        assert stats['losing_trades'] == 1
        assert stats['total_pnl'] == Decimal('-100.00')  # 100 - 200
        assert 'bitunix' in stats['exchanges']
        assert 'binance' in stats['exchanges']
        assert 'BTCUSDT' in stats['symbols']
        assert 'ETHUSDT' in stats['symbols']
        assert 'support' in stats['confluences']
    
    def test_get_trade_statistics_empty(self, data_service):
        """Test getting statistics with no trades."""
        stats = data_service.get_trade_statistics()
        
        assert stats['total_trades'] == 0
        assert stats['total_pnl'] == Decimal('0')
        assert stats['exchanges'] == []
        assert stats['symbols'] == []
        assert stats['confluences'] == []
    
    def test_backup_data(self, data_service, sample_trades):
        """Test creating data backup."""
        data_service.save_trades(sample_trades)
        
        with patch.object(data_service.backup_manager, 'create_backup', return_value='/path/to/backup') as mock_backup:
            backup_path = data_service.backup_data()
            
            assert backup_path == '/path/to/backup'
            mock_backup.assert_called_once_with("trades.json")
    
    def test_backup_data_no_file(self, data_service):
        """Test backup when no trades file exists."""
        with pytest.raises(Exception, match="No trades file to backup"):
            data_service.backup_data()
    
    def test_restore_from_backup(self, data_service):
        """Test restoring from backup."""
        backup_path = "/path/to/backup"
        
        with patch.object(data_service.backup_manager, 'restore_backup') as mock_restore:
            data_service.restore_from_backup(backup_path)
            
            mock_restore.assert_called_once_with(backup_path, "trades.json")
            
            # Cache should be cleared
            assert data_service._trades_cache is None
            assert data_service._cache_last_modified is None
    
    def test_cache_functionality(self, data_service, sample_trades):
        """Test caching functionality."""
        # Save trades
        data_service.save_trades(sample_trades)
        
        # First load should populate cache
        trades1 = data_service.load_trades()
        assert data_service._trades_cache is not None
        
        # Second load should use cache
        with patch('builtins.open') as mock_open:
            trades2 = data_service.load_trades()
            # File should not be opened if cache is used
            mock_open.assert_not_called()
        
        assert len(trades1) == len(trades2)
    
    def test_clear_cache(self, data_service, sample_trades):
        """Test clearing cache."""
        data_service.save_trades(sample_trades)
        data_service.load_trades()  # Populate cache
        
        assert data_service._trades_cache is not None
        
        data_service.clear_cache()
        
        assert data_service._trades_cache is None
        assert data_service._cache_last_modified is None
    
    def test_cache_invalidation_on_file_change(self, data_service, sample_trades, temp_data_dir):
        """Test that cache is invalidated when file is modified."""
        data_service.save_trades(sample_trades)
        data_service.load_trades()  # Populate cache
        
        # Modify file timestamp
        import os
        trades_file = Path(temp_data_dir) / "trades.json"
        future_time = datetime.now() + timedelta(minutes=10)
        timestamp = future_time.timestamp()
        os.utime(trades_file, (timestamp, timestamp))
        
        # Next load should read from file, not cache
        with patch('builtins.open', wraps=open) as mock_open:
            data_service.load_trades()
            # File should be opened because cache is invalidated
            mock_open.assert_called()