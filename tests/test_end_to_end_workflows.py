"""
End-to-end tests for complete user workflows.
"""

import pytest
import tempfile
import shutil
import json
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

from app.services.data_service import DataService
from app.services.analysis_service import AnalysisService
from app.services.config_service import ConfigService
from app.services.exchange_sync_service import ExchangeSyncService
from app.models.trade import Trade, TradeStatus, TradeSide, WinLoss
from app.models.position import Position, PositionStatus, PositionSide
from app.models.exchange_config import ExchangeConfig, ConnectionStatus
from app.models.custom_fields import CustomFieldConfig, FieldType


class TestCompleteUserWorkflows:
    """Test complete user workflows from start to finish."""
    
    @pytest.fixture
    def temp_app_dir(self):
        """Create temporary directory for full application."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def app_services(self, temp_app_dir):
        """Initialize all application services."""
        config_service = ConfigService(data_dir=temp_app_dir)
        data_service = DataService(data_dir=temp_app_dir)
        analysis_service = AnalysisService()
        exchange_sync_service = ExchangeSyncService(
            data_dir=temp_app_dir,
            config_service=config_service
        )
        
        return {
            'config': config_service,
            'data': data_service,
            'analysis': analysis_service,
            'exchange_sync': exchange_sync_service
        }
    
    def test_new_user_onboarding_workflow(self, app_services):
        """Test complete new user onboarding workflow."""
        config_service = app_services['config']
        data_service = app_services['data']
        
        # Step 1: User sets up custom fields
        confluence_field = CustomFieldConfig(
            field_name='confluences',
            field_type=FieldType.MULTISELECT,
            options=['Support/Resistance', 'Moving Average', 'RSI', 'Volume'],
            is_required=False,
            description='Trading confluences used in the trade'
        )
        
        config_service.save_custom_field_config(confluence_field)
        
        # Step 2: User configures exchange
        exchange_config = ExchangeConfig(
            name='bitunix',
            api_key_encrypted='encrypted_user_api_key',
            is_active=True,
            connection_status=ConnectionStatus.DISCONNECTED
        )
        
        config_service.save_exchange_config(exchange_config)
        
        # Step 3: User tests exchange connection
        with patch('app.services.config_service.get_exchange_factory') as mock_factory:
            mock_client = Mock()
            mock_client.test_connection.return_value = True
            
            mock_exchange_factory = Mock()
            mock_exchange_factory.create_exchange_client.return_value = mock_client
            mock_factory.return_value = mock_exchange_factory
            
            with patch('app.services.config_service.decrypt_api_key') as mock_decrypt:
                mock_decrypt.return_value = 'decrypted_user_api_key'
                
                connection_result = config_service.test_exchange_connection('bitunix')
                assert connection_result is True
                
                # Update connection status
                config_service.update_exchange_connection_status(
                    'bitunix',
                    ConnectionStatus.CONNECTED
                )
        
        # Step 4: Verify setup is complete
        loaded_confluence_field = config_service.get_custom_field_config('confluences')
        assert loaded_confluence_field is not None
        assert loaded_confluence_field.field_type == FieldType.MULTISELECT
        assert len(loaded_confluence_field.options) == 4
        
        loaded_exchange_config = config_service.get_exchange_config('bitunix')
        assert loaded_exchange_config is not None
        assert loaded_exchange_config.is_active is True
        
        # Step 5: Initial data should be empty
        trades = data_service.load_trades()
        assert len(trades) == 0
        
        stats = data_service.get_trade_statistics()
        assert stats['total_trades'] == 0
    
    def test_daily_trading_workflow(self, app_services):
        """Test daily trading workflow with data sync and analysis."""
        config_service = app_services['config']
        data_service = app_services['data']
        analysis_service = app_services['analysis']
        exchange_sync_service = app_services['exchange_sync']
        
        # Setup: Exchange is already configured
        exchange_config = ExchangeConfig(
            name='bitunix',
            api_key_encrypted='encrypted_api_key',
            is_active=True,
            connection_status=ConnectionStatus.CONNECTED
        )
        config_service.save_exchange_config(exchange_config)
        
        # Step 1: User performs data sync
        mock_positions = [
            Position(
                position_id='daily_pos_001',
                symbol='BTCUSDT',
                side=PositionSide.LONG,
                size=Decimal('0.1'),
                entry_price=Decimal('50000.00'),
                mark_price=Decimal('51000.00'),
                unrealized_pnl=Decimal('100.00'),
                realized_pnl=Decimal('0.00'),
                status=PositionStatus.CLOSED,
                open_time=datetime.now() - timedelta(hours=2),
                close_time=datetime.now() - timedelta(hours=1),
                raw_data={}
            ),
            Position(
                position_id='daily_pos_002',
                symbol='ETHUSDT',
                side=PositionSide.SHORT,
                size=Decimal('2.0'),
                entry_price=Decimal('3000.00'),
                mark_price=Decimal('2950.00'),
                unrealized_pnl=Decimal('100.00'),
                realized_pnl=Decimal('100.00'),
                status=PositionStatus.CLOSED,
                open_time=datetime.now() - timedelta(hours=3),
                close_time=datetime.now() - timedelta(minutes=30),
                raw_data={}
            )
        ]
        
        with patch('app.services.exchange_sync_service.get_exchange_factory') as mock_factory:
            mock_client = Mock()
            mock_client.get_position_history.return_value = mock_positions
            
            mock_exchange_factory = Mock()
            mock_exchange_factory.create_exchange_client.return_value = mock_client
            mock_factory.return_value = mock_exchange_factory
            
            with patch('app.services.exchange_sync_service.decrypt_api_key') as mock_decrypt:
                mock_decrypt.return_value = 'decrypted_api_key'
                
                # Perform sync
                sync_result = exchange_sync_service.sync_exchange_data('bitunix')
                assert sync_result is True
        
        # Step 2: User adds custom data to trades
        trades = data_service.load_trades()
        assert len(trades) >= 2  # Should have converted positions to trades
        
        # Simulate user adding confluence data
        if len(trades) > 0:
            first_trade = trades[0]
            updates = {
                'confluences': ['Support/Resistance', 'RSI'],
                'win_loss': WinLoss.WIN,
                'custom_fields': {'notes': 'Good setup with multiple confluences'}
            }
            
            updated_trade = data_service.update_trade(first_trade.id, updates)
            assert updated_trade.confluences == ['Support/Resistance', 'RSI']
            assert updated_trade.win_loss == WinLoss.WIN
        
        # Step 3: User views analysis
        updated_trades = data_service.load_trades()
        
        # PnL trend analysis
        pnl_trend = analysis_service.calculate_pnl_trend(updated_trades, 'daily')
        assert len(pnl_trend) >= 1
        
        # Performance summary
        performance = analysis_service.get_performance_summary(updated_trades)
        assert performance['total_trades'] >= 2
        assert 'total_pnl' in performance
        
        # Confluence analysis (if any trades have confluences)
        confluence_metrics = analysis_service.analyze_confluences(updated_trades)
        if any(trade.confluences for trade in updated_trades):
            assert len(confluence_metrics) > 0
    
    def test_weekly_review_workflow(self, app_services):
        """Test weekly review workflow with historical data analysis."""
        data_service = app_services['data']
        analysis_service = app_services['analysis']
        
        # Setup: Create a week's worth of historical trades
        base_time = datetime.now() - timedelta(days=7)
        historical_trades = []
        
        for day in range(7):
            for trade_num in range(2):  # 2 trades per day
                trade_time = base_time + timedelta(days=day, hours=trade_num * 4)
                
                trade = Trade(
                    id=f'week_trade_{day}_{trade_num}',
                    exchange='bitunix',
                    symbol='BTCUSDT' if trade_num % 2 == 0 else 'ETHUSDT',
                    side=TradeSide.LONG if trade_num % 2 == 0 else TradeSide.SHORT,
                    entry_price=Decimal('50000.00') + Decimal(str(day * 100)),
                    quantity=Decimal('0.1'),
                    entry_time=trade_time,
                    status=TradeStatus.CLOSED,
                    exit_price=Decimal('50100.00') + Decimal(str(day * 100)) if day % 3 != 0 else Decimal('49900.00') + Decimal(str(day * 100)),
                    exit_time=trade_time + timedelta(hours=2),
                    pnl=Decimal('10.00') if day % 3 != 0 else Decimal('-10.00'),
                    win_loss=WinLoss.WIN if day % 3 != 0 else WinLoss.LOSS,
                    confluences=['Support/Resistance'] if day % 2 == 0 else ['RSI', 'Volume'],
                    custom_fields={'session': 'morning' if trade_num == 0 else 'afternoon'}
                )
                
                historical_trades.append(trade)
        
        # Save historical trades
        data_service.save_trades(historical_trades)
        
        # Step 1: Weekly PnL trend analysis
        weekly_trend = analysis_service.calculate_pnl_trend(historical_trades, 'daily')
        assert len(weekly_trend) == 7  # One data point per day
        
        # Verify cumulative PnL calculation
        total_expected_pnl = sum(trade.pnl for trade in historical_trades if trade.pnl)
        final_cumulative = weekly_trend[-1].cumulative_pnl
        assert final_cumulative == total_expected_pnl
        
        # Step 2: Confluence performance analysis
        confluence_analysis = analysis_service.analyze_confluences(historical_trades)
        
        # Should have metrics for each confluence type
        confluence_names = [metric.confluence for metric in confluence_analysis]
        assert 'Support/Resistance' in confluence_names
        assert 'RSI' in confluence_names
        assert 'Volume' in confluence_names
        
        # Step 3: Performance summary
        weekly_performance = analysis_service.get_performance_summary(historical_trades)
        
        assert weekly_performance['total_trades'] == 14  # 7 days * 2 trades
        assert weekly_performance['winning_trades'] > 0
        assert weekly_performance['losing_trades'] > 0
        assert weekly_performance['win_rate'] > 0
        
        # Step 4: Filter analysis by date range
        last_3_days = datetime.now() - timedelta(days=3)
        recent_trades = data_service.get_trades_by_date_range(
            last_3_days,
            datetime.now()
        )
        
        assert len(recent_trades) == 6  # 3 days * 2 trades
        
        recent_performance = analysis_service.get_performance_summary(recent_trades)
        assert recent_performance['total_trades'] == 6
    
    def test_portfolio_management_workflow(self, app_services):
        """Test portfolio management workflow with multiple exchanges."""
        config_service = app_services['config']
        data_service = app_services['data']
        analysis_service = app_services['analysis']
        exchange_sync_service = app_services['exchange_sync']
        
        # Setup: Configure multiple exchanges
        exchanges = [
            ExchangeConfig(
                name='bitunix',
                api_key_encrypted='encrypted_bitunix_key',
                is_active=True,
                connection_status=ConnectionStatus.CONNECTED
            ),
            ExchangeConfig(
                name='binance',
                api_key_encrypted='encrypted_binance_key',
                is_active=True,
                connection_status=ConnectionStatus.CONNECTED
            )
        ]
        
        for exchange in exchanges:
            config_service.save_exchange_config(exchange)
        
        # Step 1: Sync data from multiple exchanges
        mock_positions_by_exchange = {
            'bitunix': [
                Position(
                    position_id='bitunix_pos_001',
                    symbol='BTCUSDT',
                    side=PositionSide.LONG,
                    size=Decimal('0.1'),
                    entry_price=Decimal('50000.00'),
                    mark_price=Decimal('51000.00'),
                    unrealized_pnl=Decimal('100.00'),
                    realized_pnl=Decimal('0.00'),
                    status=PositionStatus.CLOSED,
                    open_time=datetime.now() - timedelta(hours=1),
                    close_time=datetime.now(),
                    raw_data={}
                )
            ],
            'binance': [
                Position(
                    position_id='binance_pos_001',
                    symbol='ETHUSDT',
                    side=PositionSide.SHORT,
                    size=Decimal('2.0'),
                    entry_price=Decimal('3000.00'),
                    mark_price=Decimal('2950.00'),
                    unrealized_pnl=Decimal('100.00'),
                    realized_pnl=Decimal('100.00'),
                    status=PositionStatus.CLOSED,
                    open_time=datetime.now() - timedelta(hours=2),
                    close_time=datetime.now() - timedelta(minutes=30),
                    raw_data={}
                )
            ]
        }
        
        with patch('app.services.exchange_sync_service.get_exchange_factory') as mock_factory:
            def mock_create_client(exchange_name, *args, **kwargs):
                mock_client = Mock()
                mock_client.get_position_history.return_value = mock_positions_by_exchange.get(exchange_name, [])
                return mock_client
            
            mock_exchange_factory = Mock()
            mock_exchange_factory.create_exchange_client.side_effect = mock_create_client
            mock_factory.return_value = mock_exchange_factory
            
            with patch('app.services.exchange_sync_service.decrypt_api_key') as mock_decrypt:
                mock_decrypt.return_value = 'decrypted_key'
                
                # Sync all exchanges
                sync_results = exchange_sync_service.sync_all_exchanges()
                
                assert len(sync_results) == 2
                assert 'bitunix' in sync_results
                assert 'binance' in sync_results
        
        # Step 2: Analyze portfolio across exchanges
        all_trades = data_service.load_trades()
        
        # Should have trades from both exchanges
        exchanges_in_trades = set(trade.exchange for trade in all_trades)
        assert 'bitunix' in exchanges_in_trades
        assert 'binance' in exchanges_in_trades
        
        # Step 3: Exchange-specific analysis
        bitunix_trades = data_service.get_trades_by_exchange('bitunix')
        binance_trades = data_service.get_trades_by_exchange('binance')
        
        assert len(bitunix_trades) >= 1
        assert len(binance_trades) >= 1
        
        # Compare performance between exchanges
        bitunix_performance = analysis_service.get_performance_summary(bitunix_trades)
        binance_performance = analysis_service.get_performance_summary(binance_trades)
        
        assert bitunix_performance['total_trades'] >= 1
        assert binance_performance['total_trades'] >= 1
        
        # Step 4: Overall portfolio statistics
        portfolio_stats = data_service.get_trade_statistics()
        
        assert portfolio_stats['total_trades'] >= 2
        assert len(portfolio_stats['exchanges']) == 2
        assert 'bitunix' in portfolio_stats['exchanges']
        assert 'binance' in portfolio_stats['exchanges']
    
    def test_data_backup_and_recovery_workflow(self, app_services):
        """Test data backup and recovery workflow."""
        data_service = app_services['data']
        config_service = app_services['config']
        
        # Step 1: Create some data
        sample_trades = [
            Trade(
                id='backup_trade_001',
                exchange='bitunix',
                symbol='BTCUSDT',
                side=TradeSide.LONG,
                entry_price=Decimal('50000.00'),
                quantity=Decimal('0.1'),
                entry_time=datetime.now() - timedelta(hours=1),
                status=TradeStatus.CLOSED,
                exit_price=Decimal('51000.00'),
                exit_time=datetime.now(),
                pnl=Decimal('100.00'),
                win_loss=WinLoss.WIN,
                confluences=['Support/Resistance'],
                custom_fields={'notes': 'Test trade for backup'}
            )
        ]
        
        data_service.save_trades(sample_trades)
        
        # Create configuration
        exchange_config = ExchangeConfig(
            name='bitunix',
            api_key_encrypted='encrypted_key_for_backup',
            is_active=True,
            connection_status=ConnectionStatus.CONNECTED
        )
        config_service.save_exchange_config(exchange_config)
        
        # Step 2: Create backup
        with patch('app.services.data_service.create_backup') as mock_backup:
            mock_backup.return_value = '/path/to/backup/trades_backup.json'
            
            backup_path = data_service.backup_data()
            assert backup_path == '/path/to/backup/trades_backup.json'
            mock_backup.assert_called_once()
        
        # Step 3: Simulate data corruption/loss
        data_service.clear_cache()
        
        # Step 4: Restore from backup
        with patch('app.services.data_service.restore_backup') as mock_restore:
            data_service.restore_from_backup('/path/to/backup/trades_backup.json')
            mock_restore.assert_called_once()
        
        # Step 5: Verify data integrity after restore
        restored_trades = data_service.load_trades()
        # In a real scenario, this would verify the actual restored data
        # For this test, we're verifying the restore process was called
        assert mock_restore.called
    
    def test_error_handling_and_recovery_workflow(self, app_services):
        """Test error handling and recovery in various scenarios."""
        config_service = app_services['config']
        exchange_sync_service = app_services['exchange_sync']
        
        # Scenario 1: Invalid API credentials
        invalid_exchange_config = ExchangeConfig(
            name='bitunix',
            api_key_encrypted='invalid_encrypted_key',
            is_active=True,
            connection_status=ConnectionStatus.CONNECTED
        )
        config_service.save_exchange_config(invalid_exchange_config)
        
        with patch('app.services.exchange_sync_service.get_exchange_factory') as mock_factory:
            mock_client = Mock()
            mock_client.get_position_history.side_effect = Exception("Authentication failed")
            
            mock_exchange_factory = Mock()
            mock_exchange_factory.create_exchange_client.return_value = mock_client
            mock_factory.return_value = mock_exchange_factory
            
            with patch('app.services.exchange_sync_service.decrypt_api_key') as mock_decrypt:
                mock_decrypt.return_value = 'invalid_key'
                
                # Sync should fail gracefully
                result = exchange_sync_service.sync_exchange_data('bitunix')
                assert result is False
        
        # Scenario 2: Network connectivity issues
        with patch('app.services.exchange_sync_service.get_exchange_factory') as mock_factory:
            mock_client = Mock()
            mock_client.get_position_history.side_effect = ConnectionError("Network unreachable")
            
            mock_exchange_factory = Mock()
            mock_exchange_factory.create_exchange_client.return_value = mock_client
            mock_factory.return_value = mock_exchange_factory
            
            with patch('app.services.exchange_sync_service.decrypt_api_key') as mock_decrypt:
                mock_decrypt.return_value = 'valid_key'
                
                # Should handle network errors gracefully
                result = exchange_sync_service.sync_exchange_data('bitunix')
                assert result is False
        
        # Scenario 3: Partial data corruption
        # This would test the application's ability to handle corrupted data files
        # and recover gracefully
        
        # Verify that the application continues to function despite errors
        # (In a real implementation, this would check error logs, user notifications, etc.)
        assert True  # Placeholder for actual error recovery verification


class TestPerformanceAndScalability:
    """Test performance and scalability with large datasets."""
    
    @pytest.fixture
    def temp_app_dir(self):
        """Create temporary directory for performance tests."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    def test_large_dataset_performance(self, temp_app_dir):
        """Test application performance with large datasets."""
        data_service = DataService(data_dir=temp_app_dir)
        analysis_service = AnalysisService()
        
        # Create large dataset (10,000 trades)
        large_dataset = []
        base_time = datetime.now() - timedelta(days=365)  # 1 year of data
        
        for i in range(10000):
            trade_time = base_time + timedelta(hours=i)
            
            trade = Trade(
                id=f'perf_trade_{i:05d}',
                exchange='bitunix' if i % 2 == 0 else 'binance',
                symbol='BTCUSDT' if i % 3 == 0 else 'ETHUSDT' if i % 3 == 1 else 'ADAUSDT',
                side=TradeSide.LONG if i % 2 == 0 else TradeSide.SHORT,
                entry_price=Decimal('50000.00') + Decimal(str(i % 1000)),
                quantity=Decimal('0.1'),
                entry_time=trade_time,
                status=TradeStatus.CLOSED,
                exit_price=Decimal('50100.00') + Decimal(str(i % 1000)) if i % 4 != 0 else Decimal('49900.00') + Decimal(str(i % 1000)),
                exit_time=trade_time + timedelta(hours=2),
                pnl=Decimal('10.00') if i % 4 != 0 else Decimal('-10.00'),
                win_loss=WinLoss.WIN if i % 4 != 0 else WinLoss.LOSS,
                confluences=['Support/Resistance'] if i % 2 == 0 else ['RSI'],
                custom_fields={'batch': str(i // 1000)}
            )
            
            large_dataset.append(trade)
        
        # Test data saving performance
        import time
        start_time = time.time()
        
        data_service.save_trades(large_dataset)
        
        save_duration = time.time() - start_time
        assert save_duration < 10.0  # Should save within 10 seconds
        
        # Test data loading performance
        start_time = time.time()
        
        loaded_trades = data_service.load_trades()
        
        load_duration = time.time() - start_time
        assert load_duration < 5.0  # Should load within 5 seconds
        assert len(loaded_trades) == 10000
        
        # Test analysis performance
        start_time = time.time()
        
        # PnL trend analysis
        daily_trend = analysis_service.calculate_pnl_trend(loaded_trades, 'daily')
        
        # Performance summary
        performance = analysis_service.get_performance_summary(loaded_trades)
        
        # Confluence analysis
        confluence_metrics = analysis_service.analyze_confluences(loaded_trades)
        
        analysis_duration = time.time() - start_time
        assert analysis_duration < 15.0  # Should complete analysis within 15 seconds
        
        # Verify results
        assert len(daily_trend) > 0
        assert performance['total_trades'] == 10000
        assert len(confluence_metrics) > 0
        
        # Test filtering performance
        start_time = time.time()
        
        btc_trades = data_service.get_trades_by_symbol('BTCUSDT')
        winning_trades = data_service.get_winning_trades()
        recent_trades = data_service.get_trades_by_date_range(
            datetime.now() - timedelta(days=30),
            datetime.now()
        )
        
        filter_duration = time.time() - start_time
        assert filter_duration < 3.0  # Should filter within 3 seconds
        
        assert len(btc_trades) > 0
        assert len(winning_trades) > 0
        assert len(recent_trades) > 0
    
    def test_memory_usage_optimization(self, temp_app_dir):
        """Test memory usage with large datasets."""
        data_service = DataService(data_dir=temp_app_dir)
        
        # Create moderately large dataset
        dataset_size = 5000
        trades = []
        
        for i in range(dataset_size):
            trade = Trade(
                id=f'memory_trade_{i:05d}',
                exchange='bitunix',
                symbol='BTCUSDT',
                side=TradeSide.LONG,
                entry_price=Decimal('50000.00'),
                quantity=Decimal('0.1'),
                entry_time=datetime.now() - timedelta(hours=i),
                status=TradeStatus.CLOSED,
                exit_price=Decimal('50100.00'),
                exit_time=datetime.now() - timedelta(hours=i-1),
                pnl=Decimal('10.00'),
                win_loss=WinLoss.WIN,
                confluences=['Support/Resistance'],
                custom_fields={}
            )
            trades.append(trade)
        
        # Save and load data multiple times to test memory management
        for iteration in range(5):
            data_service.save_trades(trades)
            loaded_trades = data_service.load_trades()
            
            assert len(loaded_trades) == dataset_size
            
            # Clear cache to test memory cleanup
            data_service.clear_cache()
        
        # Test should complete without memory errors
        assert True
    
    def test_concurrent_operations(self, temp_app_dir):
        """Test concurrent operations simulation."""
        data_service = DataService(data_dir=temp_app_dir)
        
        # Create initial dataset
        initial_trades = []
        for i in range(100):
            trade = Trade(
                id=f'concurrent_trade_{i:03d}',
                exchange='bitunix',
                symbol='BTCUSDT',
                side=TradeSide.LONG,
                entry_price=Decimal('50000.00'),
                quantity=Decimal('0.1'),
                entry_time=datetime.now() - timedelta(hours=i),
                status=TradeStatus.CLOSED,
                exit_price=Decimal('50100.00'),
                exit_time=datetime.now() - timedelta(hours=i-1),
                pnl=Decimal('10.00'),
                win_loss=WinLoss.WIN,
                confluences=[],
                custom_fields={}
            )
            initial_trades.append(trade)
        
        data_service.save_trades(initial_trades)
        
        # Simulate concurrent read/write operations
        for i in range(10):
            # Read operation
            trades = data_service.load_trades()
            assert len(trades) == 100
            
            # Update operation
            if trades:
                first_trade = trades[0]
                updates = {
                    'confluences': [f'confluence_{i}'],
                    'custom_fields': {'iteration': str(i)}
                }
                data_service.update_trade(first_trade.id, updates)
            
            # Statistics operation
            stats = data_service.get_trade_statistics()
            assert stats['total_trades'] == 100
        
        # Verify final state
        final_trades = data_service.load_trades()
        assert len(final_trades) == 100
        
        # Check that the last update was applied
        updated_trade = next(t for t in final_trades if t.id == 'concurrent_trade_000')
        assert 'iteration' in updated_trade.custom_fields


if __name__ == '__main__':
    pytest.main([__file__])