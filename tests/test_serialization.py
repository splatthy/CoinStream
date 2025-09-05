"""
Unit tests for data serialization and deserialization.
"""

import pytest
from datetime import datetime
from decimal import Decimal

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'app'))

# Use the same import paths as the serialization module
from app.models.trade import Trade, TradeSide, TradeStatus, WinLoss
from app.models.position import Position, PositionSide, PositionStatus
from app.models.exchange_config import ExchangeConfig, ConnectionStatus
from app.models.custom_fields import CustomFieldConfig, FieldType
from app.utils.serialization import DataSerializer


class TestTradeSerializationDeserialization:
    """Test cases for Trade serialization and deserialization."""
    
    def test_trade_serialization_round_trip(self):
        """Test trade serialization and deserialization round trip."""
        original_trade = Trade(
            id='test-123',
            exchange='bitunix',
            symbol='BTCUSDT',
            side=TradeSide.LONG,
            entry_price=Decimal('50000.00'),
            quantity=Decimal('0.1'),
            entry_time=datetime(2024, 1, 1, 12, 0, 0),
            status=TradeStatus.CLOSED,
            confluences=['Support/Resistance', 'Moving Average'],
            exit_price=Decimal('55000.00'),
            exit_time=datetime(2024, 1, 2, 12, 0, 0),
            pnl=Decimal('500.00'),
            win_loss=WinLoss.WIN,
            custom_fields={'notes': 'Good trade'},
            created_at=datetime(2024, 1, 1, 10, 0, 0),
            updated_at=datetime(2024, 1, 2, 12, 0, 0)
        )
        
        # Serialize
        serialized = DataSerializer.serialize_trade(original_trade)
        
        # Verify serialized data structure
        assert serialized['id'] == 'test-123'
        assert serialized['side'] == 'long'
        assert serialized['entry_price'] == '50000.00'
        assert serialized['win_loss'] == 'win'
        assert serialized['confluences'] == ['Support/Resistance', 'Moving Average']
        
        # Deserialize
        deserialized_trade = DataSerializer.deserialize_trade(serialized)
        
        # Verify round trip
        assert deserialized_trade.id == original_trade.id
        assert deserialized_trade.exchange == original_trade.exchange
        assert deserialized_trade.symbol == original_trade.symbol
        assert deserialized_trade.side == original_trade.side
        assert deserialized_trade.entry_price == original_trade.entry_price
        assert deserialized_trade.quantity == original_trade.quantity
        assert deserialized_trade.entry_time == original_trade.entry_time
        assert deserialized_trade.status == original_trade.status
        assert deserialized_trade.confluences == original_trade.confluences
        assert deserialized_trade.exit_price == original_trade.exit_price
        assert deserialized_trade.exit_time == original_trade.exit_time
        assert deserialized_trade.pnl == original_trade.pnl
        assert deserialized_trade.win_loss == original_trade.win_loss
        assert deserialized_trade.custom_fields == original_trade.custom_fields
    
    def test_trade_serialization_with_none_values(self):
        """Test trade serialization with None values."""
        trade = Trade(
            id='test-123',
            exchange='bitunix',
            symbol='BTCUSDT',
            side=TradeSide.LONG,
            entry_price=Decimal('50000.00'),
            quantity=Decimal('0.1'),
            entry_time=datetime.now(),
            status=TradeStatus.OPEN
        )
        
        serialized = DataSerializer.serialize_trade(trade)
        deserialized = DataSerializer.deserialize_trade(serialized)
        
        assert deserialized.exit_price is None
        assert deserialized.exit_time is None
        assert deserialized.pnl is None
        assert deserialized.win_loss is None


class TestPositionSerializationDeserialization:
    """Test cases for Position serialization and deserialization."""
    
    def test_position_serialization_round_trip(self):
        """Test position serialization and deserialization round trip."""
        original_position = Position(
            position_id='pos-456',
            symbol='ETHUSDT',
            side=PositionSide.SHORT,
            size=Decimal('1.5'),
            entry_price=Decimal('3000.00'),
            mark_price=Decimal('2950.00'),
            unrealized_pnl=Decimal('75.00'),
            realized_pnl=Decimal('25.00'),
            status=PositionStatus.PARTIALLY_CLOSED,
            open_time=datetime(2024, 1, 1, 12, 0, 0),
            close_time=datetime(2024, 1, 2, 12, 0, 0),
            raw_data={'exchange_id': 'eth_pos_123'},
            created_at=datetime(2024, 1, 1, 10, 0, 0),
            updated_at=datetime(2024, 1, 2, 12, 0, 0)
        )
        
        # Serialize
        serialized = DataSerializer.serialize_position(original_position)
        
        # Verify serialized data structure
        assert serialized['position_id'] == 'pos-456'
        assert serialized['side'] == 'short'
        assert serialized['size'] == '1.5'
        assert serialized['status'] == 'partially_closed'
        
        # Deserialize
        deserialized_position = DataSerializer.deserialize_position(serialized)
        
        # Verify round trip
        assert deserialized_position.position_id == original_position.position_id
        assert deserialized_position.symbol == original_position.symbol
        assert deserialized_position.side == original_position.side
        assert deserialized_position.size == original_position.size
        assert deserialized_position.entry_price == original_position.entry_price
        assert deserialized_position.mark_price == original_position.mark_price
        assert deserialized_position.unrealized_pnl == original_position.unrealized_pnl
        assert deserialized_position.realized_pnl == original_position.realized_pnl
        assert deserialized_position.status == original_position.status
        assert deserialized_position.open_time == original_position.open_time
        assert deserialized_position.close_time == original_position.close_time
        assert deserialized_position.raw_data == original_position.raw_data


class TestExchangeConfigSerializationDeserialization:
    """Test cases for ExchangeConfig serialization and deserialization."""
    
    def test_exchange_config_serialization_round_trip(self):
        """Test exchange config serialization and deserialization round trip."""
        original_config = ExchangeConfig(
            name='bitunix',
            api_key_encrypted='encrypted_key_123',
            is_active=True,
            last_sync=datetime(2024, 1, 1, 12, 0, 0),
            connection_status=ConnectionStatus.CONNECTED,
            created_at=datetime(2024, 1, 1, 10, 0, 0),
            updated_at=datetime(2024, 1, 1, 12, 0, 0)
        )
        
        # Serialize
        serialized = DataSerializer.serialize_exchange_config(original_config)
        
        # Verify serialized data structure
        assert serialized['name'] == 'bitunix'
        assert serialized['is_active'] == True
        assert serialized['connection_status'] == 'connected'
        
        # Deserialize
        deserialized_config = DataSerializer.deserialize_exchange_config(serialized)
        
        # Verify round trip
        assert deserialized_config.name == original_config.name
        assert deserialized_config.api_key_encrypted == original_config.api_key_encrypted
        assert deserialized_config.is_active == original_config.is_active
        assert deserialized_config.last_sync == original_config.last_sync
        assert deserialized_config.connection_status == original_config.connection_status


class TestCustomFieldConfigSerializationDeserialization:
    """Test cases for CustomFieldConfig serialization and deserialization."""
    
    def test_custom_field_config_serialization_round_trip(self):
        """Test custom field config serialization and deserialization round trip."""
        original_config = CustomFieldConfig(
            field_name='confluences',
            field_type=FieldType.MULTISELECT,
            options=['Support/Resistance', 'Moving Average', 'RSI'],
            is_required=False,
            default_value=['Support/Resistance'],
            description='Trading confluences',
            validation_rules={'min_selections': 1},
            created_at=datetime(2024, 1, 1, 10, 0, 0),
            updated_at=datetime(2024, 1, 1, 12, 0, 0)
        )
        
        # Serialize
        serialized = DataSerializer.serialize_custom_field_config(original_config)
        
        # Verify serialized data structure
        assert serialized['field_name'] == 'confluences'
        assert serialized['field_type'] == 'multiselect'
        assert serialized['options'] == ['Support/Resistance', 'Moving Average', 'RSI']
        assert serialized['is_required'] == False
        
        # Deserialize
        deserialized_config = DataSerializer.deserialize_custom_field_config(serialized)
        
        # Verify round trip
        assert deserialized_config.field_name == original_config.field_name
        assert deserialized_config.field_type == original_config.field_type
        assert deserialized_config.options == original_config.options
        assert deserialized_config.is_required == original_config.is_required
        assert deserialized_config.default_value == original_config.default_value
        assert deserialized_config.description == original_config.description
        assert deserialized_config.validation_rules == original_config.validation_rules


class TestListSerializationDeserialization:
    """Test cases for list serialization and deserialization."""
    
    def test_trades_list_serialization(self):
        """Test serialization of trades list."""
        trades = [
            Trade(
                id='trade-1',
                exchange='bitunix',
                symbol='BTCUSDT',
                side=TradeSide.LONG,
                entry_price=Decimal('50000.00'),
                quantity=Decimal('0.1'),
                entry_time=datetime.now(),
                status=TradeStatus.OPEN
            ),
            Trade(
                id='trade-2',
                exchange='bitunix',
                symbol='ETHUSDT',
                side=TradeSide.SHORT,
                entry_price=Decimal('3000.00'),
                quantity=Decimal('1.0'),
                entry_time=datetime.now(),
                status=TradeStatus.CLOSED,
                exit_price=Decimal('2900.00'),
                exit_time=datetime.now(),
                pnl=Decimal('100.00')
            )
        ]
        
        # Serialize list
        serialized_list = DataSerializer.serialize_trades_list(trades)
        assert len(serialized_list) == 2
        assert serialized_list[0]['id'] == 'trade-1'
        assert serialized_list[1]['id'] == 'trade-2'
        
        # Deserialize list
        deserialized_list = DataSerializer.deserialize_trades_list(serialized_list)
        assert len(deserialized_list) == 2
        assert deserialized_list[0].id == 'trade-1'
        assert deserialized_list[1].id == 'trade-2'
        assert deserialized_list[1].exit_price == Decimal('2900.00')


class TestJSONUtilities:
    """Test cases for JSON utilities."""
    
    def test_json_encoding_decoding(self):
        """Test JSON encoding and decoding with custom encoder."""
        data = {
            'decimal_value': Decimal('123.45'),
            'datetime_value': datetime(2024, 1, 1, 12, 0, 0),
            'enum_value': TradeSide.LONG,
            'string_value': 'test'
        }
        
        # Encode to JSON
        json_str = DataSerializer.to_json(data)
        assert '"decimal_value": "123.45"' in json_str
        assert '"enum_value": "long"' in json_str
        assert '"datetime_value": "2024-01-01T12:00:00"' in json_str
        
        # Decode from JSON
        decoded = DataSerializer.from_json(json_str)
        assert decoded['decimal_value'] == '123.45'  # Note: comes back as string
        assert decoded['enum_value'] == 'long'
        assert decoded['string_value'] == 'test'


if __name__ == '__main__':
    pytest.main([__file__])