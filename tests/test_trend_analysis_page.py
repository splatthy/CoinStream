"""
Unit tests for trend analysis page functionality.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from decimal import Decimal
import pandas as pd

from app.pages.trend_analysis import (
    render_trend_analysis_page,
    render_timeframe_selector,
    render_pnl_chart,
    render_performance_metrics,
    render_chart_controls,
    create_pnl_chart,
    calculate_chart_statistics,
    export_chart_data,
    format_currency,
    format_percentage
)
from app.models.trade import Trade, TradeStatus, TradeSide, WinLoss
from app.services.analysis_service import AnalysisService, PnLDataPoint


class TestTrendAnalysisPage:
    """Test cases for trend analysis page functions."""
    
    @pytest.fixture
    def mock_analysis_service(self):
        """Create mock analysis service."""
        return Mock(spec=AnalysisService)
    
    @pytest.fixture
    def sample_trades(self):
        """Create sample trades for testing."""
        base_time = datetime(2024, 1, 1, 10, 0, 0)
        return [
            Trade(
                id="trade1",
                exchange="bitunix",
                symbol="BTCUSDT",
                side=TradeSide.LONG,
                entry_price=Decimal("50000.00"),
                quantity=Decimal("0.1"),
                entry_time=base_time,
                status=TradeStatus.CLOSED,
                exit_price=Decimal("51000.00"),
                exit_time=base_time + timedelta(hours=2),
                pnl=Decimal("100.00"),
                win_loss=WinLoss.WIN
            ),
            Trade(
                id="trade2",
                exchange="bitunix",
                symbol="ETHUSDT",
                side=TradeSide.SHORT,
                entry_price=Decimal("3000.00"),
                quantity=Decimal("1.0"),
                entry_time=base_time + timedelta(days=1),
                status=TradeStatus.CLOSED,
                exit_price=Decimal("3050.00"),
                exit_time=base_time + timedelta(days=1, hours=3),
                pnl=Decimal("-50.00"),
                win_loss=WinLoss.LOSS
            ),
            Trade(
                id="trade3",
                exchange="bitunix",
                symbol="BTCUSDT",
                side=TradeSide.LONG,
                entry_price=Decimal("51000.00"),
                quantity=Decimal("0.2"),
                entry_time=base_time + timedelta(days=2),
                status=TradeStatus.CLOSED,
                exit_price=Decimal("52000.00"),
                exit_time=base_time + timedelta(days=2, hours=4),
                pnl=Decimal("200.00"),
                win_loss=WinLoss.WIN
            )
        ]
    
    @pytest.fixture
    def sample_pnl_data(self):
        """Create sample PnL data points."""
        base_date = datetime(2024, 1, 1)
        return [
            PnLDataPoint(
                date=base_date,
                daily_pnl=Decimal("100.00"),
                cumulative_pnl=Decimal("100.00"),
                trade_count=1
            ),
            PnLDataPoint(
                date=base_date + timedelta(days=1),
                daily_pnl=Decimal("-50.00"),
                cumulative_pnl=Decimal("50.00"),
                trade_count=1
            ),
            PnLDataPoint(
                date=base_date + timedelta(days=2),
                daily_pnl=Decimal("200.00"),
                cumulative_pnl=Decimal("250.00"),
                trade_count=1
            )
        ]
    
    @patch('streamlit.container')
    @patch('streamlit.columns')
    def test_render_trend_analysis_page(self, mock_columns, mock_container, mock_analysis_service, sample_trades):
        """Test rendering the main trend analysis page."""
        mock_analysis_service.calculate_pnl_trend.return_value = []
        
        # Mock streamlit components
        mock_container.return_value.__enter__ = Mock()
        mock_container.return_value.__exit__ = Mock()
        mock_columns.return_value = [Mock(), Mock()]
        
        with patch('app.pages.trend_analysis.render_timeframe_selector') as mock_selector, \
             patch('app.pages.trend_analysis.render_pnl_chart') as mock_chart, \
             patch('app.pages.trend_analysis.render_performance_metrics') as mock_metrics:
            
            mock_selector.return_value = "daily"
            
            render_trend_analysis_page(sample_trades, mock_analysis_service)
            
            mock_selector.assert_called_once()
            mock_chart.assert_called_once()
            mock_metrics.assert_called_once()
    
    @patch('streamlit.selectbox')
    def test_render_timeframe_selector(self, mock_selectbox):
        """Test rendering timeframe selector."""
        mock_selectbox.return_value = "Daily"
        
        result = render_timeframe_selector()
        
        assert result == "daily"
        mock_selectbox.assert_called_once_with(
            "Select Timeframe",
            ["Daily", "Weekly", "Monthly"],
            index=0
        )
    
    @patch('streamlit.selectbox')
    def test_render_timeframe_selector_weekly(self, mock_selectbox):
        """Test rendering timeframe selector with weekly selection."""
        mock_selectbox.return_value = "Weekly"
        
        result = render_timeframe_selector()
        
        assert result == "weekly"
    
    @patch('streamlit.selectbox')
    def test_render_timeframe_selector_monthly(self, mock_selectbox):
        """Test rendering timeframe selector with monthly selection."""
        mock_selectbox.return_value = "Monthly"
        
        result = render_timeframe_selector()
        
        assert result == "monthly"
    
    @patch('streamlit.plotly_chart')
    def test_render_pnl_chart(self, mock_plotly_chart, sample_pnl_data):
        """Test rendering PnL chart."""
        with patch('app.pages.trend_analysis.create_pnl_chart') as mock_create_chart:
            mock_fig = Mock()
            mock_create_chart.return_value = mock_fig
            
            render_pnl_chart(sample_pnl_data, "daily")
            
            mock_create_chart.assert_called_once_with(sample_pnl_data, "daily")
            mock_plotly_chart.assert_called_once_with(mock_fig, use_container_width=True)
    
    @patch('streamlit.plotly_chart')
    @patch('streamlit.info')
    def test_render_pnl_chart_empty_data(self, mock_info, mock_plotly_chart):
        """Test rendering PnL chart with empty data."""
        render_pnl_chart([], "daily")
        
        mock_info.assert_called_once_with("No trade data available for chart.")
        mock_plotly_chart.assert_not_called()
    
    @patch('streamlit.metric')
    @patch('streamlit.columns')
    def test_render_performance_metrics(self, mock_columns, mock_metric, sample_pnl_data):
        """Test rendering performance metrics."""
        mock_columns.return_value = [Mock(), Mock(), Mock(), Mock()]
        
        with patch('app.pages.trend_analysis.calculate_chart_statistics') as mock_calc_stats:
            mock_calc_stats.return_value = {
                'total_pnl': Decimal('250.00'),
                'total_trades': 3,
                'win_rate': 66.67,
                'avg_daily_pnl': Decimal('83.33'),
                'best_day': Decimal('200.00'),
                'worst_day': Decimal('-50.00'),
                'profitable_days': 2,
                'total_days': 3
            }
            
            render_performance_metrics(sample_pnl_data)
            
            mock_calc_stats.assert_called_once_with(sample_pnl_data)
            assert mock_metric.call_count == 4  # 4 metrics displayed
    
    @patch('streamlit.metric')
    @patch('streamlit.columns')
    @patch('streamlit.info')
    def test_render_performance_metrics_empty_data(self, mock_info, mock_columns, mock_metric):
        """Test rendering performance metrics with empty data."""
        render_performance_metrics([])
        
        mock_info.assert_called_once_with("No data available for performance metrics.")
        mock_metric.assert_not_called()
    
    @patch('streamlit.checkbox')
    @patch('streamlit.slider')
    def test_render_chart_controls(self, mock_slider, mock_checkbox):
        """Test rendering chart controls."""
        mock_checkbox.side_effect = [True, False, True]
        mock_slider.return_value = 30
        
        controls = render_chart_controls()
        
        assert controls['show_cumulative'] is True
        assert controls['show_daily'] is False
        assert controls['show_trade_count'] is True
        assert controls['moving_average_days'] == 30
        
        assert mock_checkbox.call_count == 3
        mock_slider.assert_called_once()
    
    def test_create_pnl_chart(self, sample_pnl_data):
        """Test creating PnL chart."""
        with patch('plotly.graph_objects.Figure') as mock_figure, \
             patch('plotly.graph_objects.Scatter') as mock_scatter:
            
            mock_fig = Mock()
            mock_figure.return_value = mock_fig
            
            result = create_pnl_chart(sample_pnl_data, "daily")
            
            assert result == mock_fig
            mock_figure.assert_called_once()
            mock_fig.add_trace.assert_called()
            mock_fig.update_layout.assert_called()
    
    def test_create_pnl_chart_empty_data(self):
        """Test creating PnL chart with empty data."""
        result = create_pnl_chart([], "daily")
        assert result is None
    
    def test_create_pnl_chart_weekly_title(self, sample_pnl_data):
        """Test creating PnL chart with weekly timeframe."""
        with patch('plotly.graph_objects.Figure') as mock_figure:
            mock_fig = Mock()
            mock_figure.return_value = mock_fig
            
            create_pnl_chart(sample_pnl_data, "weekly")
            
            # Verify the title includes "Weekly"
            call_args = mock_fig.update_layout.call_args[1]
            assert "Weekly" in call_args['title']
    
    def test_create_pnl_chart_monthly_title(self, sample_pnl_data):
        """Test creating PnL chart with monthly timeframe."""
        with patch('plotly.graph_objects.Figure') as mock_figure:
            mock_fig = Mock()
            mock_figure.return_value = mock_fig
            
            create_pnl_chart(sample_pnl_data, "monthly")
            
            # Verify the title includes "Monthly"
            call_args = mock_fig.update_layout.call_args[1]
            assert "Monthly" in call_args['title']
    
    def test_calculate_chart_statistics(self, sample_pnl_data):
        """Test calculating chart statistics."""
        stats = calculate_chart_statistics(sample_pnl_data)
        
        assert stats['total_pnl'] == Decimal('250.00')
        assert stats['total_trades'] == 3
        assert stats['avg_daily_pnl'] == Decimal('83.33')
        assert stats['best_day'] == Decimal('200.00')
        assert stats['worst_day'] == Decimal('-50.00')
        assert stats['profitable_days'] == 2
        assert stats['total_days'] == 3
        assert stats['win_rate'] == 66.67
    
    def test_calculate_chart_statistics_empty_data(self):
        """Test calculating chart statistics with empty data."""
        stats = calculate_chart_statistics([])
        
        assert stats['total_pnl'] == Decimal('0')
        assert stats['total_trades'] == 0
        assert stats['avg_daily_pnl'] == Decimal('0')
        assert stats['best_day'] == Decimal('0')
        assert stats['worst_day'] == Decimal('0')
        assert stats['profitable_days'] == 0
        assert stats['total_days'] == 0
        assert stats['win_rate'] == 0.0
    
    def test_calculate_chart_statistics_all_profitable(self):
        """Test calculating statistics with all profitable days."""
        profitable_data = [
            PnLDataPoint(
                date=datetime(2024, 1, 1),
                daily_pnl=Decimal("100.00"),
                cumulative_pnl=Decimal("100.00"),
                trade_count=1
            ),
            PnLDataPoint(
                date=datetime(2024, 1, 2),
                daily_pnl=Decimal("50.00"),
                cumulative_pnl=Decimal("150.00"),
                trade_count=1
            )
        ]
        
        stats = calculate_chart_statistics(profitable_data)
        
        assert stats['win_rate'] == 100.0
        assert stats['profitable_days'] == 2
        assert stats['worst_day'] == Decimal('50.00')  # Still positive
    
    def test_export_chart_data(self, sample_pnl_data):
        """Test exporting chart data."""
        with patch('pandas.DataFrame.to_csv') as mock_to_csv:
            mock_to_csv.return_value = "csv_content"
            
            result = export_chart_data(sample_pnl_data)
            
            assert result == "csv_content"
            mock_to_csv.assert_called_once_with(index=False)
    
    def test_export_chart_data_empty(self):
        """Test exporting empty chart data."""
        result = export_chart_data([])
        assert result == ""
    
    def test_format_currency_positive(self):
        """Test formatting positive currency values."""
        assert format_currency(Decimal("1234.56")) == "$1,234.56"
        assert format_currency(Decimal("0.01")) == "$0.01"
        assert format_currency(Decimal("1000000.00")) == "$1,000,000.00"
    
    def test_format_currency_negative(self):
        """Test formatting negative currency values."""
        assert format_currency(Decimal("-1234.56")) == "-$1,234.56"
        assert format_currency(Decimal("-0.01")) == "-$0.01"
    
    def test_format_currency_zero(self):
        """Test formatting zero currency value."""
        assert format_currency(Decimal("0.00")) == "$0.00"
        assert format_currency(Decimal("0")) == "$0.00"
    
    def test_format_percentage_positive(self):
        """Test formatting positive percentage values."""
        assert format_percentage(66.67) == "66.67%"
        assert format_percentage(100.0) == "100.00%"
        assert format_percentage(0.5) == "0.50%"
    
    def test_format_percentage_negative(self):
        """Test formatting negative percentage values."""
        assert format_percentage(-25.5) == "-25.50%"
        assert format_percentage(-0.1) == "-0.10%"
    
    def test_format_percentage_zero(self):
        """Test formatting zero percentage value."""
        assert format_percentage(0.0) == "0.00%"
        assert format_percentage(0) == "0.00%"


class TestTrendAnalysisPageIntegration:
    """Integration tests for trend analysis page."""
    
    @pytest.fixture
    def mock_streamlit_session_state(self):
        """Mock streamlit session state."""
        with patch('streamlit.session_state', {}) as mock_state:
            yield mock_state
    
    @patch('streamlit.title')
    @patch('streamlit.container')
    def test_full_page_render_workflow(self, mock_container, mock_title, mock_streamlit_session_state):
        """Test complete page rendering workflow."""
        mock_analysis_service = Mock(spec=AnalysisService)
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
                win_loss=WinLoss.WIN
            )
        ]
        
        sample_pnl_data = [
            PnLDataPoint(
                date=datetime.now(),
                daily_pnl=Decimal("100.00"),
                cumulative_pnl=Decimal("100.00"),
                trade_count=1
            )
        ]
        
        mock_analysis_service.calculate_pnl_trend.return_value = sample_pnl_data
        
        # Mock container context manager
        mock_container_obj = Mock()
        mock_container_obj.__enter__ = Mock(return_value=mock_container_obj)
        mock_container_obj.__exit__ = Mock(return_value=None)
        mock_container.return_value = mock_container_obj
        
        with patch('app.pages.trend_analysis.render_timeframe_selector') as mock_selector, \
             patch('app.pages.trend_analysis.render_pnl_chart') as mock_chart, \
             patch('app.pages.trend_analysis.render_performance_metrics') as mock_metrics:
            
            mock_selector.return_value = "daily"
            
            render_trend_analysis_page(sample_trades, mock_analysis_service)
            
            # Verify the workflow
            mock_title.assert_called_once_with("📈 Trend Analysis")
            mock_analysis_service.calculate_pnl_trend.assert_called_once_with(sample_trades, "daily")
            mock_selector.assert_called_once()
            mock_chart.assert_called_once_with(sample_pnl_data, "daily")
            mock_metrics.assert_called_once_with(sample_pnl_data)
    
    @patch('streamlit.error')
    def test_page_render_with_analysis_error(self, mock_error, mock_streamlit_session_state):
        """Test page rendering when analysis service raises error."""
        mock_analysis_service = Mock(spec=AnalysisService)
        mock_analysis_service.calculate_pnl_trend.side_effect = Exception("Analysis failed")
        
        sample_trades = [Mock()]
        
        with patch('app.pages.trend_analysis.render_timeframe_selector') as mock_selector:
            mock_selector.return_value = "daily"
            
            render_trend_analysis_page(sample_trades, mock_analysis_service)
            
            mock_error.assert_called_once()
    
    def test_chart_data_conversion(self, sample_pnl_data):
        """Test conversion of PnL data to chart format."""
        with patch('plotly.graph_objects.Figure') as mock_figure:
            mock_fig = Mock()
            mock_figure.return_value = mock_fig
            
            create_pnl_chart(sample_pnl_data, "daily")
            
            # Verify that data was properly converted for plotting
            mock_fig.add_trace.assert_called()
            
            # Check that the trace was called with proper data
            call_args = mock_fig.add_trace.call_args_list
            assert len(call_args) >= 1  # At least one trace added
    
    @patch('streamlit.download_button')
    def test_chart_export_functionality(self, mock_download_button, sample_pnl_data):
        """Test chart export functionality."""
        with patch('app.pages.trend_analysis.export_chart_data') as mock_export:
            mock_export.return_value = "csv_data"
            
            # Simulate export button being rendered
            with patch('streamlit.button') as mock_button:
                mock_button.return_value = True
                
                # This would be called in the actual page
                csv_data = export_chart_data(sample_pnl_data)
                
                assert csv_data == "csv_data"
                mock_export.assert_called_once_with(sample_pnl_data)


if __name__ == '__main__':
    pytest.main([__file__])