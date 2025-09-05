"""
Unit tests for trade history page functionality.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from decimal import Decimal

from app.pages.trade_history import (
    render_trade_history_page,
    render_trade_filters,
    render_trade_table,
    render_trade_details,
    render_trade_editor,
    handle_trade_update,
    format_trade_display,
    get_filtered_trades,
    export_trades_to_csv
)
from app.models.trade import Trade, TradeStatus, TradeSide, WinLoss
from app.services.data_service import DataService


class TestTradeHistoryPage:
    """Test cases for trade history page functions."""
    
    @pytest.fixture
    def mock_data_service(self):
        """Create mock data service."""
        return Mock(spec=DataService)
    
    @pytest.fixture
    def sample_trades(self):
        """Create sample trades for testing."""
        return [
            Trade(
                id="trade1",
                exchange="bitunix",
                symbol="BTCUSDT",
                side=TradeSide.LONG,
                entry_price=Decimal("50000.00"),
                quantity=Decimal("0.1"),
                entry_time=datetime(2024, 1, 1, 10, 0, 0),
                status=TradeStatus.CLOSED,
                exit_price=Decimal("51000.00"),
                exit_time=datetime(2024, 1, 1, 12, 0, 0),
                pnl=Decimal("100.00"),
                win_loss=WinLoss.WIN,
                confluences=["support", "rsi_oversold"],
                custom_fields={"notes": "Good trade"}
            ),
            Trade(
                id="trade2",
                exchange="bitunix",
                symbol="ETHUSDT",
                side=TradeSide.SHORT,
                entry_price=Decimal("3000.00"),
                quantity=Decimal("1.0"),
                entry_time=datetime(2024, 1, 2, 14, 0, 0),
                status=TradeStatus.OPEN,
                confluences=["resistance"],
                custom_fields={}
            ),
            Trade(
                id="trade3",
                exchange="binance",
                symbol="ADAUSDT",
                side=TradeSide.LONG,
                entry_price=Decimal("1.50"),
                quantity=Decimal("100.0"),
                entry_time=datetime(2024, 1, 3, 9, 0, 0),
                status=TradeStatus.CLOSED,
                exit_price=Decimal("1.40"),
                exit_time=datetime(2024, 1, 3, 11, 0, 0),
                pnl=Decimal("-10.00"),
                win_loss=WinLoss.LOSS,
                confluences=["support", "volume_spike"],
                custom_fields={"risk_level": "high"}
            )
        ]
    
    @patch('streamlit.container')
    @patch('streamlit.columns')
    def test_render_trade_history_page(self, mock_columns, mock_container, mock_data_service, sample_trades):
        """Test rendering the main trade history page."""
        mock_data_service.load_trades.return_value = sample_trades
        
        # Mock streamlit components
        mock_container.return_value.__enter__ = Mock()
        mock_container.return_value.__exit__ = Mock()
        mock_columns.return_value = [Mock(), Mock()]
        
        with patch('app.pages.trade_history.render_trade_filters') as mock_filters, \
             patch('app.pages.trade_history.render_trade_table') as mock_table, \
             patch('app.pages.trade_history.get_filtered_trades') as mock_get_filtered:
            
            mock_get_filtered.return_value = sample_trades
            
            render_trade_history_page(mock_data_service)
            
            mock_filters.assert_called_once()
            mock_table.assert_called_once()
            mock_get_filtered.assert_called_once()
    
    @patch('streamlit.selectbox')
    @patch('streamlit.multiselect')
    @patch('streamlit.date_input')
    def test_render_trade_filters(self, mock_date_input, mock_multiselect, mock_selectbox, sample_trades):
        """Test rendering trade filters."""
        # Mock streamlit inputs
        mock_selectbox.side_effect = ["All", "All", "All"]
        mock_multiselect.side_effect = [[], []]
        mock_date_input.side_effect = [datetime(2024, 1, 1), datetime(2024, 1, 31)]
        
        filters = render_trade_filters(sample_trades)
        
        assert "status" in filters
        assert "exchange" in filters
        assert "symbol" in filters
        assert "confluences" in filters
        assert "win_loss" in filters
        assert "start_date" in filters
        assert "end_date" in filters
        
        # Verify streamlit components were called
        assert mock_selectbox.call_count == 3
        assert mock_multiselect.call_count == 2
        assert mock_date_input.call_count == 2
    
    @patch('streamlit.dataframe')
    @patch('streamlit.button')
    def test_render_trade_table(self, mock_button, mock_dataframe, sample_trades):
        """Test rendering trade table."""
        mock_button.return_value = False
        
        with patch('app.pages.trade_history.format_trade_display') as mock_format:
            mock_format.return_value = [
                {
                    "ID": "trade1",
                    "Exchange": "bitunix",
                    "Symbol": "BTCUSDT",
                    "Side": "LONG",
                    "Entry Price": "$50,000.00",
                    "Quantity": "0.1",
                    "Status": "CLOSED",
                    "PnL": "$100.00",
                    "Win/Loss": "WIN"
                }
            ]
            
            render_trade_table(sample_trades)
            
            mock_format.assert_called_once_with(sample_trades)
            mock_dataframe.assert_called_once()
    
    @patch('streamlit.expander')
    def test_render_trade_details(self, mock_expander, sample_trades):
        """Test rendering trade details."""
        mock_expander_obj = Mock()
        mock_expander_obj.__enter__ = Mock()
        mock_expander_obj.__exit__ = Mock()
        mock_expander.return_value = mock_expander_obj
        
        with patch('streamlit.write') as mock_write:
            render_trade_details(sample_trades[0])
            
            mock_expander.assert_called_once()
            assert mock_write.call_count > 0
    
    @patch('streamlit.form')
    @patch('streamlit.multiselect')
    @patch('streamlit.selectbox')
    @patch('streamlit.text_area')
    def test_render_trade_editor(self, mock_text_area, mock_selectbox, mock_multiselect, mock_form, sample_trades):
        """Test rendering trade editor."""
        mock_form_obj = Mock()
        mock_form_obj.__enter__ = Mock()
        mock_form_obj.__exit__ = Mock()
        mock_form.return_value = mock_form_obj
        
        mock_multiselect.return_value = ["support", "rsi_oversold"]
        mock_selectbox.return_value = "WIN"
        mock_text_area.return_value = "Updated notes"
        
        with patch('streamlit.form_submit_button') as mock_submit:
            mock_submit.return_value = False
            
            render_trade_editor(sample_trades[0], ["support", "resistance", "rsi_oversold"])
            
            mock_form.assert_called_once()
            mock_multiselect.assert_called_once()
            mock_selectbox.assert_called_once()
    
    def test_handle_trade_update(self, mock_data_service, sample_trades):
        """Test handling trade updates."""
        trade = sample_trades[0]
        updates = {
            "confluences": ["new_confluence"],
            "win_loss": WinLoss.LOSS,
            "custom_fields": {"notes": "Updated notes"}
        }
        
        mock_data_service.update_trade.return_value = trade
        
        with patch('app.pages.trade_history.get_notification_manager') as mock_notification:
            mock_notification_manager = Mock()
            mock_notification.return_value = mock_notification_manager
            
            result = handle_trade_update(mock_data_service, trade.id, updates)
            
            assert result is True
            mock_data_service.update_trade.assert_called_once_with(trade.id, updates)
            mock_notification_manager.success.assert_called_once()
    
    def test_handle_trade_update_error(self, mock_data_service):
        """Test handling trade update with error."""
        mock_data_service.update_trade.side_effect = Exception("Update failed")
        
        with patch('app.pages.trade_history.get_notification_manager') as mock_notification:
            mock_notification_manager = Mock()
            mock_notification.return_value = mock_notification_manager
            
            result = handle_trade_update(mock_data_service, "trade1", {})
            
            assert result is False
            mock_notification_manager.error.assert_called_once()
    
    def test_format_trade_display(self, sample_trades):
        """Test formatting trades for display."""
        formatted = format_trade_display(sample_trades)
        
        assert len(formatted) == 3
        
        # Check first trade formatting
        trade1 = formatted[0]
        assert trade1["ID"] == "trade1"
        assert trade1["Exchange"] == "bitunix"
        assert trade1["Symbol"] == "BTCUSDT"
        assert trade1["Side"] == "LONG"
        assert "$50,000.00" in trade1["Entry Price"]
        assert trade1["Quantity"] == "0.1"
        assert trade1["Status"] == "CLOSED"
        assert "$100.00" in trade1["PnL"]
        assert trade1["Win/Loss"] == "WIN"
        assert "support, rsi_oversold" in trade1["Confluences"]
    
    def test_format_trade_display_open_trade(self, sample_trades):
        """Test formatting open trade for display."""
        formatted = format_trade_display([sample_trades[1]])  # Open trade
        
        trade = formatted[0]
        assert trade["Status"] == "OPEN"
        assert trade["Exit Price"] == "-"
        assert trade["PnL"] == "-"
        assert trade["Win/Loss"] == "-"
    
    def test_get_filtered_trades_no_filters(self, sample_trades):
        """Test getting filtered trades with no filters."""
        filters = {
            "status": "All",
            "exchange": "All",
            "symbol": "All",
            "confluences": [],
            "win_loss": "All",
            "start_date": None,
            "end_date": None
        }
        
        filtered = get_filtered_trades(sample_trades, filters)
        assert len(filtered) == 3
    
    def test_get_filtered_trades_status_filter(self, sample_trades):
        """Test filtering trades by status."""
        filters = {
            "status": "CLOSED",
            "exchange": "All",
            "symbol": "All",
            "confluences": [],
            "win_loss": "All",
            "start_date": None,
            "end_date": None
        }
        
        filtered = get_filtered_trades(sample_trades, filters)
        assert len(filtered) == 2
        assert all(trade.status == TradeStatus.CLOSED for trade in filtered)
    
    def test_get_filtered_trades_exchange_filter(self, sample_trades):
        """Test filtering trades by exchange."""
        filters = {
            "status": "All",
            "exchange": "bitunix",
            "symbol": "All",
            "confluences": [],
            "win_loss": "All",
            "start_date": None,
            "end_date": None
        }
        
        filtered = get_filtered_trades(sample_trades, filters)
        assert len(filtered) == 2
        assert all(trade.exchange == "bitunix" for trade in filtered)
    
    def test_get_filtered_trades_symbol_filter(self, sample_trades):
        """Test filtering trades by symbol."""
        filters = {
            "status": "All",
            "exchange": "All",
            "symbol": "BTCUSDT",
            "confluences": [],
            "win_loss": "All",
            "start_date": None,
            "end_date": None
        }
        
        filtered = get_filtered_trades(sample_trades, filters)
        assert len(filtered) == 1
        assert filtered[0].symbol == "BTCUSDT"
    
    def test_get_filtered_trades_confluence_filter(self, sample_trades):
        """Test filtering trades by confluence."""
        filters = {
            "status": "All",
            "exchange": "All",
            "symbol": "All",
            "confluences": ["support"],
            "win_loss": "All",
            "start_date": None,
            "end_date": None
        }
        
        filtered = get_filtered_trades(sample_trades, filters)
        assert len(filtered) == 2
        assert all("support" in trade.confluences for trade in filtered)
    
    def test_get_filtered_trades_win_loss_filter(self, sample_trades):
        """Test filtering trades by win/loss."""
        filters = {
            "status": "All",
            "exchange": "All",
            "symbol": "All",
            "confluences": [],
            "win_loss": "WIN",
            "start_date": None,
            "end_date": None
        }
        
        filtered = get_filtered_trades(sample_trades, filters)
        assert len(filtered) == 1
        assert filtered[0].win_loss == WinLoss.WIN
    
    def test_get_filtered_trades_date_filter(self, sample_trades):
        """Test filtering trades by date range."""
        filters = {
            "status": "All",
            "exchange": "All",
            "symbol": "All",
            "confluences": [],
            "win_loss": "All",
            "start_date": datetime(2024, 1, 1),
            "end_date": datetime(2024, 1, 2)
        }
        
        filtered = get_filtered_trades(sample_trades, filters)
        assert len(filtered) == 2
        assert all(
            datetime(2024, 1, 1) <= trade.entry_time <= datetime(2024, 1, 2, 23, 59, 59)
            for trade in filtered
        )
    
    def test_get_filtered_trades_multiple_filters(self, sample_trades):
        """Test filtering trades with multiple filters."""
        filters = {
            "status": "CLOSED",
            "exchange": "bitunix",
            "symbol": "All",
            "confluences": ["support"],
            "win_loss": "WIN",
            "start_date": None,
            "end_date": None
        }
        
        filtered = get_filtered_trades(sample_trades, filters)
        assert len(filtered) == 1
        assert filtered[0].id == "trade1"
    
    @patch('pandas.DataFrame.to_csv')
    def test_export_trades_to_csv(self, mock_to_csv, sample_trades):
        """Test exporting trades to CSV."""
        mock_to_csv.return_value = "csv_content"
        
        with patch('app.pages.trade_history.format_trade_display') as mock_format:
            mock_format.return_value = [
                {
                    "ID": "trade1",
                    "Exchange": "bitunix",
                    "Symbol": "BTCUSDT",
                    "Side": "LONG",
                    "Entry Price": "$50,000.00",
                    "Quantity": "0.1",
                    "Status": "CLOSED",
                    "PnL": "$100.00",
                    "Win/Loss": "WIN"
                }
            ]
            
            result = export_trades_to_csv(sample_trades)
            
            assert result == "csv_content"
            mock_format.assert_called_once_with(sample_trades)
            mock_to_csv.assert_called_once_with(index=False)
    
    def test_export_trades_to_csv_empty(self):
        """Test exporting empty trades list to CSV."""
        result = export_trades_to_csv([])
        assert result == ""


class TestTradeHistoryPageIntegration:
    """Integration tests for trade history page."""
    
    @pytest.fixture
    def mock_streamlit_session_state(self):
        """Mock streamlit session state."""
        with patch('streamlit.session_state', {}) as mock_state:
            yield mock_state
    
    @patch('streamlit.title')
    @patch('streamlit.container')
    def test_full_page_render_workflow(self, mock_container, mock_title, mock_streamlit_session_state):
        """Test complete page rendering workflow."""
        mock_data_service = Mock(spec=DataService)
        sample_trades = [
            Trade(
                id="test_trade",
                exchange="bitunix",
                symbol="BTCUSDT",
                side=TradeSide.LONG,
                entry_price=Decimal("50000.00"),
                quantity=Decimal("0.1"),
                entry_time=datetime.now(),
                status=TradeStatus.CLOSED,
                exit_price=Decimal("51000.00"),
                exit_time=datetime.now(),
                pnl=Decimal("100.00"),
                win_loss=WinLoss.WIN,
                confluences=["support"],
                custom_fields={}
            )
        ]
        
        mock_data_service.load_trades.return_value = sample_trades
        
        # Mock container context manager
        mock_container_obj = Mock()
        mock_container_obj.__enter__ = Mock(return_value=mock_container_obj)
        mock_container_obj.__exit__ = Mock(return_value=None)
        mock_container.return_value = mock_container_obj
        
        with patch('app.pages.trade_history.render_trade_filters') as mock_filters, \
             patch('app.pages.trade_history.render_trade_table') as mock_table, \
             patch('app.pages.trade_history.get_filtered_trades') as mock_get_filtered:
            
            mock_filters.return_value = {
                "status": "All",
                "exchange": "All",
                "symbol": "All",
                "confluences": [],
                "win_loss": "All",
                "start_date": None,
                "end_date": None
            }
            mock_get_filtered.return_value = sample_trades
            
            render_trade_history_page(mock_data_service)
            
            # Verify the workflow
            mock_title.assert_called_once_with("📊 Trade History")
            mock_data_service.load_trades.assert_called_once()
            mock_filters.assert_called_once()
            mock_get_filtered.assert_called_once()
            mock_table.assert_called_once()


if __name__ == '__main__':
    pytest.main([__file__])