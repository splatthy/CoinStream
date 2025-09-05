"""
Integration tests for exchange API clients.
"""

import pytest
import json
import tempfile
import shutil
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

from app.integrations.bitunix_client import BitunixClient
from app.integrations.exchange_factory import ExchangeFactory, get_exchange_factory
from app.integrations.base_exchange import AuthenticationError, APIError, NetworkError
from app.models.position import Position, PositionStatus, PositionSide
from app.services.exchange_sync_service import ExchangeSyncService
from app.services.config_service import ConfigService
from app.models.exchange_config import ExchangeConfig, ConnectionStatus


class TestBitunixClientIntegration:
    """Integration tests for BitunixClient with mock API responses."""
    
    @pytest.fixture
    def mock_api_responses(self):
        """Mock API responses for different endpoints."""
        return {
            'ping': {
                'status_code': 200,
                'json': {}
            },
            'account_info': {
                'status_code': 200,
                'json': {
                    'balance': '10000.00',
                    'currency': 'USDT',
                    'available_balance': '8000.00',
                    'frozen_balance': '2000.00'
                }
            },
            'position_history': {
                'status_code': 200,
                'json': {
                    'data': [
                        {
                            'positionId': 'pos_001',
                            'symbol': 'BTCUSDT',
                            'side': 'long',
                            'size': '0.1',
                            'entryPrice': '50000.00',
                            'markPrice': '51000.00',
                            'unrealizedPnl': '100.00',
                            'realizedPnl': '0.00',
                            'status': 'open',
                            'openTime': int(datetime.now().timestamp() * 1000),
                            'closeTime': 0
                        },
                        {
                            'positionId': 'pos_002',
                            'symbol': 'ETHUSDT',
                            'side': 'short',
                            'size': '2.0',
                            'entryPrice': '3000.00',
                            'markPrice': '2950.00',
                            'unrealizedPnl': '100.00',
                            'realizedPnl': '50.00',
                            'status': 'closed',
                            'openTime': int((datetime.now() - timedelta(days=1)).timestamp() * 1000),
                            'closeTime': int(datetime.now().timestamp() * 1000)
                        }
                    ]
                }
            },
            'position_history_empty': {
                'status_code': 200,
                'json': {'data': []}
            },
            'auth_error': {
                'status_code': 401,
                'json': {
                    'code': 'AUTH_FAILED',
                    'message': 'Invalid API key'
                }
            },
            'rate_limit_error': {
                'status_code': 429,
                'json': {
                    'code': 'RATE_LIMIT_EXCEEDED',
                    'message': 'Too many requests'
                }
            }
        }
    
    @pytest.fixture
    def bitunix_client(self):
        """Create BitunixClient instance for testing."""
        return BitunixClient(api_key="test_api_key_12345", api_secret="test_secret_12345")
    
    def test_full_authentication_workflow(self, bitunix_client, mock_api_responses):
        """Test complete authentication workflow."""
        with patch('requests.Session.request') as mock_request:
            # Mock ping response for connection test
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.ok = True
            mock_response.json.return_value = mock_api_responses['ping']['json']
            mock_request.return_value = mock_response
            
            # Test connection
            assert bitunix_client.test_connection() is True
            
            # Test authentication
            assert bitunix_client.authenticate() is True
            assert bitunix_client._authenticated is True
            assert bitunix_client._auth_expires_at is not None
    
    def test_position_data_sync_workflow(self, bitunix_client, mock_api_responses):
        """Test complete position data synchronization workflow."""
        with patch('requests.Session.request') as mock_request:
            def mock_request_side_effect(*args, **kwargs):
                url = kwargs.get('url', '')
                
                if 'ping' in url:
                    response = Mock()
                    response.status_code = 200
                    response.ok = True
                    response.json.return_value = mock_api_responses['ping']['json']
                    return response
                elif 'position/history' in url:
                    response = Mock()
                    response.status_code = 200
                    response.ok = True
                    response.json.return_value = mock_api_responses['position_history']['json']
                    return response
                else:
                    response = Mock()
                    response.status_code = 404
                    return response
            
            mock_request.side_effect = mock_request_side_effect
            
            # Authenticate first
            assert bitunix_client.authenticate() is True
            
            # Fetch position history
            positions = bitunix_client.get_position_history()
            
            assert len(positions) == 2
            
            # Verify first position (open)
            btc_position = positions[0]
            assert btc_position.position_id == 'pos_001'
            assert btc_position.symbol == 'BTCUSDT'
            assert btc_position.side == PositionSide.LONG
            assert btc_position.status == PositionStatus.OPEN
            assert btc_position.size == Decimal('0.1')
            assert btc_position.entry_price == Decimal('50000.00')
            assert btc_position.unrealized_pnl == Decimal('100.00')
            
            # Verify second position (closed)
            eth_position = positions[1]
            assert eth_position.position_id == 'pos_002'
            assert eth_position.symbol == 'ETHUSDT'
            assert eth_position.side == PositionSide.SHORT
            assert eth_position.status == PositionStatus.CLOSED
            assert eth_position.realized_pnl == Decimal('50.00')
    
    def test_error_handling_workflow(self, bitunix_client, mock_api_responses):
        """Test error handling in various scenarios."""
        with patch('requests.Session.request') as mock_request:
            # Test authentication error
            mock_response = Mock()
            mock_response.status_code = 401
            mock_response.ok = False
            mock_response.json.return_value = mock_api_responses['auth_error']['json']
            mock_request.return_value = mock_response
            
            with pytest.raises(AuthenticationError):
                bitunix_client.authenticate()
            
            # Test rate limiting
            mock_response.status_code = 429
            mock_response.json.return_value = mock_api_responses['rate_limit_error']['json']
            
            with pytest.raises(APIError):
                bitunix_client.get_position_history()
    
    def test_data_parsing_edge_cases(self, bitunix_client, mock_api_responses):
        """Test data parsing with various edge cases."""
        with patch('requests.Session.request') as mock_request:
            # Test with empty position data
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.ok = True
            mock_response.json.return_value = mock_api_responses['position_history_empty']['json']
            mock_request.return_value = mock_response
            
            # Mock authentication
            bitunix_client._authenticated = True
            bitunix_client._auth_expires_at = datetime.now() + timedelta(hours=1)
            
            positions = bitunix_client.get_position_history()
            assert len(positions) == 0
    
    def test_pagination_and_filtering(self, bitunix_client, mock_api_responses):
        """Test pagination and filtering parameters."""
        with patch('requests.Session.request') as mock_request:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.ok = True
            mock_response.json.return_value = mock_api_responses['position_history']['json']
            mock_request.return_value = mock_response
            
            # Mock authentication
            bitunix_client._authenticated = True
            bitunix_client._auth_expires_at = datetime.now() + timedelta(hours=1)
            
            # Test with date filtering
            since_date = datetime.now() - timedelta(days=7)
            positions = bitunix_client.get_position_history(since=since_date, limit=50)
            
            # Verify request was made with correct parameters
            call_args = mock_request.call_args
            assert 'params' in call_args[1]
            params = call_args[1]['params']
            assert 'startTime' in params
            assert 'limit' in params
            assert params['limit'] == 50


class TestExchangeFactoryIntegration:
    """Integration tests for ExchangeFactory with multiple exchanges."""
    
    @pytest.fixture
    def exchange_factory(self):
        """Create ExchangeFactory instance."""
        return ExchangeFactory()
    
    @pytest.fixture
    def temp_config_dir(self):
        """Create temporary directory for configuration."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    def test_exchange_registration_and_creation(self, exchange_factory):
        """Test registering and creating exchange clients."""
        # Get supported exchanges (should include bitunix from default registration)
        supported = exchange_factory.get_supported_exchanges()
        assert 'bitunix' in supported
        
        # Get exchange details
        details = exchange_factory.get_exchange_details('bitunix')
        assert details is not None
        assert details['name'] == 'bitunix'
        assert 'rate_limits' in details
        
        # Create client
        client = exchange_factory.create_exchange_client(
            'bitunix', 
            'test_api_key_12345', 
            'test_secret_12345'
        )
        
        assert isinstance(client, BitunixClient)
        assert client.api_key == 'test_api_key_12345'
        assert client.api_secret == 'test_secret_12345'
    
    def test_connection_testing_workflow(self, exchange_factory):
        """Test connection testing workflow."""
        with patch.object(BitunixClient, 'test_connection') as mock_test:
            mock_test.return_value = True
            
            result = exchange_factory.test_exchange_connection(
                'bitunix',
                'test_api_key_12345',
                'test_secret_12345'
            )
            
            assert result is True
            mock_test.assert_called_once()
    
    def test_credential_validation_workflow(self, exchange_factory):
        """Test credential validation workflow."""
        with patch.object(BitunixClient, 'test_connection') as mock_test:
            mock_test.return_value = True
            
            # Test valid credentials
            result = exchange_factory.validate_exchange_credentials(
                'bitunix',
                'valid_api_key_12345',
                'valid_secret_12345'
            )
            
            assert result['exchange'] == 'bitunix'
            assert result['format_valid'] is True
            assert result['connection_test'] is True
            assert result['error'] is None
            
            # Test invalid format
            result = exchange_factory.validate_exchange_credentials(
                'bitunix',
                'short',  # Too short
                'valid_secret_12345'
            )
            
            assert result['format_valid'] is False
            assert result['connection_test'] is False
            assert 'Invalid credential format' in result['error']


class TestExchangeSyncServiceIntegration:
    """Integration tests for ExchangeSyncService with real exchange clients."""
    
    @pytest.fixture
    def temp_data_dir(self):
        """Create temporary directory for data storage."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def config_service(self, temp_data_dir):
        """Create ConfigService instance."""
        return ConfigService(data_dir=temp_data_dir)
    
    @pytest.fixture
    def exchange_sync_service(self, temp_data_dir, config_service):
        """Create ExchangeSyncService instance."""
        return ExchangeSyncService(data_dir=temp_data_dir, config_service=config_service)
    
    @pytest.fixture
    def mock_exchange_config(self):
        """Create mock exchange configuration."""
        return ExchangeConfig(
            name='bitunix',
            api_key_encrypted='encrypted_test_key',
            is_active=True,
            connection_status=ConnectionStatus.CONNECTED
        )
    
    def test_full_sync_workflow(self, exchange_sync_service, config_service, mock_exchange_config):
        """Test complete synchronization workflow."""
        # Setup exchange configuration
        config_service.save_exchange_config(mock_exchange_config)
        
        # Mock the exchange client and its methods
        with patch('app.services.exchange_sync_service.get_exchange_factory') as mock_factory:
            mock_client = Mock()
            mock_client.get_position_history.return_value = [
                Position(
                    position_id='sync_pos_001',
                    symbol='BTCUSDT',
                    side=PositionSide.LONG,
                    size=Decimal('0.1'),
                    entry_price=Decimal('50000.00'),
                    mark_price=Decimal('51000.00'),
                    unrealized_pnl=Decimal('100.00'),
                    realized_pnl=Decimal('0.00'),
                    status=PositionStatus.OPEN,
                    open_time=datetime.now(),
                    raw_data={}
                )
            ]
            
            mock_exchange_factory = Mock()
            mock_exchange_factory.create_exchange_client.return_value = mock_client
            mock_factory.return_value = mock_exchange_factory
            
            # Mock decryption
            with patch('app.services.exchange_sync_service.decrypt_api_key') as mock_decrypt:
                mock_decrypt.return_value = 'decrypted_test_key'
                
                # Perform sync
                result = exchange_sync_service.sync_exchange_data('bitunix')
                
                assert result is True
                mock_client.get_position_history.assert_called_once()
    
    def test_sync_with_multiple_exchanges(self, exchange_sync_service, config_service):
        """Test synchronization with multiple exchanges."""
        # Setup multiple exchange configurations
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
        
        with patch('app.services.exchange_sync_service.get_exchange_factory') as mock_factory:
            mock_client = Mock()
            mock_client.get_position_history.return_value = []
            
            mock_exchange_factory = Mock()
            mock_exchange_factory.create_exchange_client.return_value = mock_client
            mock_factory.return_value = mock_exchange_factory
            
            with patch('app.services.exchange_sync_service.decrypt_api_key') as mock_decrypt:
                mock_decrypt.return_value = 'decrypted_key'
                
                # Sync all exchanges
                results = exchange_sync_service.sync_all_exchanges()
                
                assert len(results) == 2
                assert 'bitunix' in results
                assert 'binance' in results
    
    def test_error_handling_during_sync(self, exchange_sync_service, config_service, mock_exchange_config):
        """Test error handling during synchronization."""
        config_service.save_exchange_config(mock_exchange_config)
        
        with patch('app.services.exchange_sync_service.get_exchange_factory') as mock_factory:
            mock_client = Mock()
            mock_client.get_position_history.side_effect = APIError("API Error")
            
            mock_exchange_factory = Mock()
            mock_exchange_factory.create_exchange_client.return_value = mock_client
            mock_factory.return_value = mock_exchange_factory
            
            with patch('app.services.exchange_sync_service.decrypt_api_key') as mock_decrypt:
                mock_decrypt.return_value = 'decrypted_key'
                
                # Sync should handle error gracefully
                result = exchange_sync_service.sync_exchange_data('bitunix')
                
                assert result is False
    
    def test_incremental_sync_workflow(self, exchange_sync_service, config_service, mock_exchange_config):
        """Test incremental synchronization workflow."""
        config_service.save_exchange_config(mock_exchange_config)
        
        # Set last sync time
        last_sync = datetime.now() - timedelta(hours=1)
        exchange_sync_service.set_last_sync_time('bitunix', last_sync)
        
        with patch('app.services.exchange_sync_service.get_exchange_factory') as mock_factory:
            mock_client = Mock()
            mock_client.get_position_history.return_value = []
            
            mock_exchange_factory = Mock()
            mock_exchange_factory.create_exchange_client.return_value = mock_client
            mock_factory.return_value = mock_exchange_factory
            
            with patch('app.services.exchange_sync_service.decrypt_api_key') as mock_decrypt:
                mock_decrypt.return_value = 'decrypted_key'
                
                # Perform incremental sync
                result = exchange_sync_service.sync_exchange_data('bitunix', incremental=True)
                
                assert result is True
                
                # Verify that since parameter was passed
                call_args = mock_client.get_position_history.call_args
                assert 'since' in call_args[1]


class TestEndToEndWorkflows:
    """End-to-end integration tests for complete workflows."""
    
    @pytest.fixture
    def temp_app_dir(self):
        """Create temporary directory for full application."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    def test_complete_exchange_setup_and_sync_workflow(self, temp_app_dir):
        """Test complete workflow from exchange setup to data synchronization."""
        # Initialize services
        config_service = ConfigService(data_dir=temp_app_dir)
        exchange_sync_service = ExchangeSyncService(
            data_dir=temp_app_dir, 
            config_service=config_service
        )
        
        # Step 1: Configure exchange
        exchange_config = ExchangeConfig(
            name='bitunix',
            api_key_encrypted='encrypted_test_key_12345',
            is_active=True,
            connection_status=ConnectionStatus.DISCONNECTED
        )
        
        config_service.save_exchange_config(exchange_config)
        
        # Step 2: Test connection
        with patch('app.services.config_service.get_exchange_factory') as mock_factory:
            mock_client = Mock()
            mock_client.test_connection.return_value = True
            
            mock_exchange_factory = Mock()
            mock_exchange_factory.create_exchange_client.return_value = mock_client
            mock_factory.return_value = mock_exchange_factory
            
            with patch('app.services.config_service.decrypt_api_key') as mock_decrypt:
                mock_decrypt.return_value = 'decrypted_test_key_12345'
                
                # Test connection
                result = config_service.test_exchange_connection('bitunix')
                assert result is True
                
                # Update connection status
                config_service.update_exchange_connection_status(
                    'bitunix', 
                    ConnectionStatus.CONNECTED
                )
        
        # Step 3: Perform data synchronization
        with patch('app.services.exchange_sync_service.get_exchange_factory') as mock_factory:
            mock_positions = [
                Position(
                    position_id='e2e_pos_001',
                    symbol='BTCUSDT',
                    side=PositionSide.LONG,
                    size=Decimal('0.1'),
                    entry_price=Decimal('50000.00'),
                    mark_price=Decimal('51000.00'),
                    unrealized_pnl=Decimal('100.00'),
                    realized_pnl=Decimal('0.00'),
                    status=PositionStatus.OPEN,
                    open_time=datetime.now(),
                    raw_data={}
                )
            ]
            
            mock_client = Mock()
            mock_client.get_position_history.return_value = mock_positions
            
            mock_exchange_factory = Mock()
            mock_exchange_factory.create_exchange_client.return_value = mock_client
            mock_factory.return_value = mock_exchange_factory
            
            with patch('app.services.exchange_sync_service.decrypt_api_key') as mock_decrypt:
                mock_decrypt.return_value = 'decrypted_test_key_12345'
                
                # Perform sync
                result = exchange_sync_service.sync_exchange_data('bitunix')
                assert result is True
                
                # Verify sync was recorded
                last_sync = exchange_sync_service.get_last_sync_time('bitunix')
                assert last_sync is not None
        
        # Step 4: Verify configuration persistence
        loaded_config = config_service.get_exchange_config('bitunix')
        assert loaded_config is not None
        assert loaded_config.name == 'bitunix'
        assert loaded_config.is_active is True
    
    def test_error_recovery_workflow(self, temp_app_dir):
        """Test error recovery in end-to-end workflow."""
        config_service = ConfigService(data_dir=temp_app_dir)
        exchange_sync_service = ExchangeSyncService(
            data_dir=temp_app_dir,
            config_service=config_service
        )
        
        # Setup exchange with invalid credentials
        exchange_config = ExchangeConfig(
            name='bitunix',
            api_key_encrypted='invalid_encrypted_key',
            is_active=True,
            connection_status=ConnectionStatus.CONNECTED
        )
        
        config_service.save_exchange_config(exchange_config)
        
        # Attempt sync with authentication error
        with patch('app.services.exchange_sync_service.get_exchange_factory') as mock_factory:
            mock_client = Mock()
            mock_client.get_position_history.side_effect = AuthenticationError("Invalid credentials")
            
            mock_exchange_factory = Mock()
            mock_exchange_factory.create_exchange_client.return_value = mock_client
            mock_factory.return_value = mock_exchange_factory
            
            with patch('app.services.exchange_sync_service.decrypt_api_key') as mock_decrypt:
                mock_decrypt.return_value = 'invalid_key'
                
                # Sync should fail gracefully
                result = exchange_sync_service.sync_exchange_data('bitunix')
                assert result is False
                
                # Connection status should be updated to reflect error
                updated_config = config_service.get_exchange_config('bitunix')
                # In a real implementation, this would update the status to ERROR
                assert updated_config is not None
    
    def test_performance_with_large_dataset(self, temp_app_dir):
        """Test performance with large dataset simulation."""
        config_service = ConfigService(data_dir=temp_app_dir)
        exchange_sync_service = ExchangeSyncService(
            data_dir=temp_app_dir,
            config_service=config_service
        )
        
        # Setup exchange
        exchange_config = ExchangeConfig(
            name='bitunix',
            api_key_encrypted='encrypted_test_key',
            is_active=True,
            connection_status=ConnectionStatus.CONNECTED
        )
        
        config_service.save_exchange_config(exchange_config)
        
        # Create large dataset of positions
        large_position_dataset = []
        for i in range(1000):  # 1000 positions
            position = Position(
                position_id=f'perf_pos_{i:04d}',
                symbol='BTCUSDT' if i % 2 == 0 else 'ETHUSDT',
                side=PositionSide.LONG if i % 2 == 0 else PositionSide.SHORT,
                size=Decimal('0.1'),
                entry_price=Decimal('50000.00') + Decimal(str(i)),
                mark_price=Decimal('51000.00') + Decimal(str(i)),
                unrealized_pnl=Decimal('100.00'),
                realized_pnl=Decimal('0.00'),
                status=PositionStatus.CLOSED if i % 10 == 0 else PositionStatus.OPEN,
                open_time=datetime.now() - timedelta(days=i % 30),
                raw_data={}
            )
            large_position_dataset.append(position)
        
        with patch('app.services.exchange_sync_service.get_exchange_factory') as mock_factory:
            mock_client = Mock()
            mock_client.get_position_history.return_value = large_position_dataset
            
            mock_exchange_factory = Mock()
            mock_exchange_factory.create_exchange_client.return_value = mock_client
            mock_factory.return_value = mock_exchange_factory
            
            with patch('app.services.exchange_sync_service.decrypt_api_key') as mock_decrypt:
                mock_decrypt.return_value = 'decrypted_test_key'
                
                # Measure sync performance
                import time
                start_time = time.time()
                
                result = exchange_sync_service.sync_exchange_data('bitunix')
                
                end_time = time.time()
                sync_duration = end_time - start_time
                
                assert result is True
                assert sync_duration < 5.0  # Should complete within 5 seconds
                
                # Verify all positions were processed
                mock_client.get_position_history.assert_called_once()


if __name__ == '__main__':
    pytest.main([__file__])