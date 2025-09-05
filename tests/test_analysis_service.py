import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List

from app.services.analysis_service import AnalysisService, PnLDataPoint, ConfluenceMetrics
from app.models.trade import Trade, TradeStatus, TradeSide, WinLoss


class TestAnalysisService:
    """Test cases for AnalysisService."""
    
    @pytest.fixture
    def analysis_service(self):
        """Create AnalysisService instance."""
        return AnalysisService()
    
    @pytest.fixture
    def sample_trades(self) -> List[Trade]:
        """Create sample trades for testing."""
        base_time = datetime(2024, 1, 1, 10, 0, 0)
        
        trades = [
            # Day 1 - 2 trades
            Trade(
                id="trade1",
                exchange="bitunix",
                symbol="BTCUSDT",
                side=TradeSide.LONG,
                entry_price=Decimal("50000"),
                quantity=Decimal("0.1"),
                entry_time=base_time,
                exit_price=Decimal("51000"),
                exit_time=base_time + timedelta(hours=2),
                pnl=Decimal("100"),
                status=TradeStatus.CLOSED,
                confluences=["support", "rsi_oversold"],
                win_loss=WinLoss.WIN
            ),
            Trade(
                id="trade2",
                exchange="bitunix",
                symbol="ETHUSDT",
                side=TradeSide.SHORT,
                entry_price=Decimal("3000"),
                quantity=Decimal("1"),
                entry_time=base_time + timedelta(hours=1),
                exit_price=Decimal("3050"),
                exit_time=base_time + timedelta(hours=3),
                pnl=Decimal("-50"),
                status=TradeStatus.CLOSED,
                confluences=["resistance"],
                win_loss=WinLoss.LOSS
            ),
            # Day 2 - 1 trade
            Trade(
                id="trade3",
                exchange="bitunix",
                symbol="BTCUSDT",
                side=TradeSide.LONG,
                entry_price=Decimal("51000"),
                quantity=Decimal("0.2"),
                entry_time=base_time + timedelta(days=1),
                exit_price=Decimal("52000"),
                exit_time=base_time + timedelta(days=1, hours=4),
                pnl=Decimal("200"),
                status=TradeStatus.CLOSED,
                confluences=["support", "volume_spike"],
                win_loss=WinLoss.WIN
            ),
            # Day 8 (next week) - 1 trade
            Trade(
                id="trade4",
                exchange="bitunix",
                symbol="ADAUSDT",
                side=TradeSide.LONG,
                entry_price=Decimal("1.0"),
                quantity=Decimal("100"),
                entry_time=base_time + timedelta(days=7),
                exit_price=Decimal("0.95"),
                exit_time=base_time + timedelta(days=7, hours=2),
                pnl=Decimal("-5"),
                status=TradeStatus.CLOSED,
                confluences=["support"],
                win_loss=WinLoss.LOSS
            ),
            # Open trade (should be excluded from analysis)
            Trade(
                id="trade5",
                exchange="bitunix",
                symbol="BTCUSDT",
                side=TradeSide.LONG,
                entry_price=Decimal("52000"),
                quantity=Decimal("0.1"),
                entry_time=base_time + timedelta(days=2),
                status=TradeStatus.OPEN,
                confluences=["support"]
            )
        ]
        
        return trades
    
    def test_calculate_pnl_trend_daily(self, analysis_service, sample_trades):
        """Test daily PnL trend calculation."""
        trend_data = analysis_service.calculate_pnl_trend(sample_trades, 'daily')
        
        assert len(trend_data) == 3  # 3 days with closed trades
        
        # Day 1: 100 - 50 = 50
        assert trend_data[0].daily_pnl == Decimal("50")
        assert trend_data[0].cumulative_pnl == Decimal("50")
        assert trend_data[0].trade_count == 2
        
        # Day 2: 200
        assert trend_data[1].daily_pnl == Decimal("200")
        assert trend_data[1].cumulative_pnl == Decimal("250")
        assert trend_data[1].trade_count == 1
        
        # Day 8: -5
        assert trend_data[2].daily_pnl == Decimal("-5")
        assert trend_data[2].cumulative_pnl == Decimal("245")
        assert trend_data[2].trade_count == 1
    
    def test_calculate_pnl_trend_weekly(self, analysis_service, sample_trades):
        """Test weekly PnL trend calculation."""
        trend_data = analysis_service.calculate_pnl_trend(sample_trades, 'weekly')
        
        assert len(trend_data) == 2  # 2 weeks with closed trades
        
        # Week 1: 50 + 200 = 250
        assert trend_data[0].daily_pnl == Decimal("250")
        assert trend_data[0].cumulative_pnl == Decimal("250")
        assert trend_data[0].trade_count == 3
        
        # Week 2: -5
        assert trend_data[1].daily_pnl == Decimal("-5")
        assert trend_data[1].cumulative_pnl == Decimal("245")
        assert trend_data[1].trade_count == 1
    
    def test_calculate_pnl_trend_monthly(self, analysis_service, sample_trades):
        """Test monthly PnL trend calculation."""
        trend_data = analysis_service.calculate_pnl_trend(sample_trades, 'monthly')
        
        assert len(trend_data) == 1  # All trades in same month
        
        # Month 1: 50 + 200 - 5 = 245
        assert trend_data[0].daily_pnl == Decimal("245")
        assert trend_data[0].cumulative_pnl == Decimal("245")
        assert trend_data[0].trade_count == 4
    
    def test_calculate_pnl_trend_invalid_timeframe(self, analysis_service, sample_trades):
        """Test invalid timeframe raises error."""
        with pytest.raises(ValueError, match="Unsupported timeframe"):
            analysis_service.calculate_pnl_trend(sample_trades, 'invalid')
    
    def test_calculate_pnl_trend_empty_trades(self, analysis_service):
        """Test PnL trend calculation with empty trades list."""
        trend_data = analysis_service.calculate_pnl_trend([], 'daily')
        assert trend_data == []
    
    def test_calculate_pnl_trend_no_closed_trades(self, analysis_service):
        """Test PnL trend calculation with no closed trades."""
        open_trade = Trade(
            id="open1",
            exchange="bitunix",
            symbol="BTCUSDT",
            side=TradeSide.LONG,
            entry_price=Decimal("50000"),
            quantity=Decimal("0.1"),
            entry_time=datetime.now(),
            status=TradeStatus.OPEN
        )
        
        trend_data = analysis_service.calculate_pnl_trend([open_trade], 'daily')
        assert trend_data == []
    
    def test_calculate_cumulative_pnl(self, analysis_service, sample_trades):
        """Test cumulative PnL calculation."""
        # All trades
        total_pnl = analysis_service.calculate_cumulative_pnl(sample_trades)
        assert total_pnl == Decimal("245")  # 100 - 50 + 200 - 5
        
        # Up to specific date
        cutoff_date = datetime(2024, 1, 2, 23, 59, 59)
        partial_pnl = analysis_service.calculate_cumulative_pnl(sample_trades, cutoff_date)
        assert partial_pnl == Decimal("250")  # 100 - 50 + 200
    
    def test_get_performance_summary(self, analysis_service, sample_trades):
        """Test performance summary calculation."""
        summary = analysis_service.get_performance_summary(sample_trades)
        
        assert summary['total_trades'] == 4
        assert summary['winning_trades'] == 2
        assert summary['losing_trades'] == 2
        assert summary['win_rate'] == 50.0
        assert summary['total_pnl'] == Decimal("245")
        assert summary['average_pnl'] == Decimal("61.25")
        assert summary['largest_win'] == Decimal("200")
        assert summary['largest_loss'] == Decimal("-50")
    
    def test_get_performance_summary_empty_trades(self, analysis_service):
        """Test performance summary with empty trades."""
        summary = analysis_service.get_performance_summary([])
        
        assert summary['total_trades'] == 0
        assert summary['winning_trades'] == 0
        assert summary['losing_trades'] == 0
        assert summary['win_rate'] == 0.0
        assert summary['total_pnl'] == Decimal("0")
        assert summary['average_pnl'] == Decimal("0")
        assert summary['largest_win'] == Decimal("0")
        assert summary['largest_loss'] == Decimal("0")
    
    def test_analyze_confluences(self, analysis_service, sample_trades):
        """Test confluence analysis."""
        confluence_metrics = analysis_service.analyze_confluences(sample_trades)
        
        # Should have 4 confluences: support, rsi_oversold, resistance, volume_spike
        assert len(confluence_metrics) == 4
        
        # Find support confluence (appears in 3 trades)
        support_metrics = next(m for m in confluence_metrics if m.confluence == "support")
        assert support_metrics.total_trades == 3
        assert support_metrics.winning_trades == 2
        assert support_metrics.losing_trades == 1
        assert support_metrics.win_rate == 66.67
        assert support_metrics.total_pnl == Decimal("295")  # 100 + 200 - 5
        
        # Find resistance confluence (appears in 1 trade)
        resistance_metrics = next(m for m in confluence_metrics if m.confluence == "resistance")
        assert resistance_metrics.total_trades == 1
        assert resistance_metrics.winning_trades == 0
        assert resistance_metrics.losing_trades == 1
        assert resistance_metrics.win_rate == 0.0
        assert resistance_metrics.total_pnl == Decimal("-50")
    
    def test_calculate_win_rate_all_trades(self, analysis_service, sample_trades):
        """Test win rate calculation for all trades."""
        win_rate = analysis_service.calculate_win_rate(sample_trades)
        assert win_rate == 50.0  # 2 wins out of 4 closed trades
    
    def test_calculate_win_rate_specific_confluence(self, analysis_service, sample_trades):
        """Test win rate calculation for specific confluence."""
        support_win_rate = analysis_service.calculate_win_rate(sample_trades, "support")
        assert round(support_win_rate, 2) == 66.67  # 2 wins out of 3 support trades
        
        resistance_win_rate = analysis_service.calculate_win_rate(sample_trades, "resistance")
        assert resistance_win_rate == 0.0  # 0 wins out of 1 resistance trade
        
        nonexistent_win_rate = analysis_service.calculate_win_rate(sample_trades, "nonexistent")
        assert nonexistent_win_rate == 0.0
    
    def test_calculate_win_rate_empty_trades(self, analysis_service):
        """Test win rate calculation with empty trades."""
        win_rate = analysis_service.calculate_win_rate([])
        assert win_rate == 0.0
    
    def test_get_pnl_by_timeframe(self, analysis_service, sample_trades):
        """Test PnL DataFrame generation."""
        df = analysis_service.get_pnl_by_timeframe(sample_trades, 'daily')
        
        assert len(df) == 3
        assert list(df.columns) == ['date', 'daily_pnl', 'cumulative_pnl', 'trade_count']
        
        # Check first row
        assert df.iloc[0]['daily_pnl'] == 50.0
        assert df.iloc[0]['cumulative_pnl'] == 50.0
        assert df.iloc[0]['trade_count'] == 2
    
    def test_get_pnl_by_timeframe_empty_trades(self, analysis_service):
        """Test PnL DataFrame with empty trades."""
        df = analysis_service.get_pnl_by_timeframe([], 'daily')
        
        assert len(df) == 0
        assert list(df.columns) == ['date', 'daily_pnl', 'cumulative_pnl', 'trade_count']
    
    def test_pnl_data_point_creation(self):
        """Test PnLDataPoint dataclass."""
        point = PnLDataPoint(
            date=datetime(2024, 1, 1),
            daily_pnl=Decimal("100"),
            cumulative_pnl=Decimal("500"),
            trade_count=3
        )
        
        assert point.date == datetime(2024, 1, 1)
        assert point.daily_pnl == Decimal("100")
        assert point.cumulative_pnl == Decimal("500")
        assert point.trade_count == 3
    
    def test_confluence_metrics_creation(self):
        """Test ConfluenceMetrics dataclass."""
        metrics = ConfluenceMetrics(
            confluence="support",
            total_trades=10,
            winning_trades=7,
            losing_trades=3,
            win_rate=70.0,
            total_pnl=Decimal("500"),
            average_pnl=Decimal("50"),
            pnl_percentage=25.5
        )
        
        assert metrics.confluence == "support"
        assert metrics.total_trades == 10
        assert metrics.winning_trades == 7
        assert metrics.losing_trades == 3
        assert metrics.win_rate == 70.0
        assert metrics.total_pnl == Decimal("500")
        assert metrics.average_pnl == Decimal("50")
        assert metrics.pnl_percentage == 25.5


class TestConfluenceAnalysis:
    """Test confluence-specific analysis methods."""
    
    @pytest.fixture
    def analysis_service(self):
        return AnalysisService()
    
    @pytest.fixture
    def confluence_trades(self) -> List[Trade]:
        """Create trades with various confluence combinations."""
        base_time = datetime(2024, 1, 1, 10, 0, 0)
        
        return [
            # Single confluence trades
            Trade(
                id="single1",
                exchange="bitunix",
                symbol="BTCUSDT",
                side=TradeSide.LONG,
                entry_price=Decimal("50000"),
                quantity=Decimal("0.1"),
                entry_time=base_time,
                exit_price=Decimal("51000"),
                exit_time=base_time + timedelta(hours=1),
                pnl=Decimal("100"),
                status=TradeStatus.CLOSED,
                confluences=["support"]
            ),
            # Multiple confluence trades
            Trade(
                id="multi1",
                exchange="bitunix",
                symbol="ETHUSDT",
                side=TradeSide.LONG,
                entry_price=Decimal("3000"),
                quantity=Decimal("1"),
                entry_time=base_time + timedelta(hours=2),
                exit_price=Decimal("3200"),
                exit_time=base_time + timedelta(hours=3),
                pnl=Decimal("200"),
                status=TradeStatus.CLOSED,
                confluences=["support", "rsi_oversold"]
            ),
            Trade(
                id="multi2",
                exchange="bitunix",
                symbol="ADAUSDT",
                side=TradeSide.SHORT,
                entry_price=Decimal("1.0"),
                quantity=Decimal("100"),
                entry_time=base_time + timedelta(hours=4),
                exit_price=Decimal("1.1"),
                exit_time=base_time + timedelta(hours=5),
                pnl=Decimal("-10"),
                status=TradeStatus.CLOSED,
                confluences=["resistance", "volume_spike"]
            ),
            # Three confluence trade
            Trade(
                id="multi3",
                exchange="bitunix",
                symbol="BTCUSDT",
                side=TradeSide.LONG,
                entry_price=Decimal("52000"),
                quantity=Decimal("0.05"),
                entry_time=base_time + timedelta(hours=6),
                exit_price=Decimal("53000"),
                exit_time=base_time + timedelta(hours=7),
                pnl=Decimal("50"),
                status=TradeStatus.CLOSED,
                confluences=["support", "rsi_oversold", "volume_spike"]
            )
        ]
    
    def test_get_confluence_win_rates(self, analysis_service, confluence_trades):
        """Test confluence win rate extraction."""
        win_rates = analysis_service.get_confluence_win_rates(confluence_trades)
        
        assert "support" in win_rates
        assert "rsi_oversold" in win_rates
        assert "resistance" in win_rates
        assert "volume_spike" in win_rates
        
        # Support appears in 3 trades, all winning
        assert win_rates["support"] == 100.0
        # Resistance appears in 1 trade, losing
        assert win_rates["resistance"] == 0.0
    
    def test_get_confluence_pnl_percentages(self, analysis_service, confluence_trades):
        """Test confluence PnL percentage extraction."""
        pnl_percentages = analysis_service.get_confluence_pnl_percentages(confluence_trades)
        
        assert "support" in pnl_percentages
        assert "resistance" in pnl_percentages
        
        # All percentages should sum to more than 100% due to overlapping confluences
        total_percentage = sum(pnl_percentages.values())
        assert total_percentage > 100.0
    
    def test_analyze_confluence_combinations(self, analysis_service, confluence_trades):
        """Test confluence combination analysis."""
        combinations = analysis_service.analyze_confluence_combinations(confluence_trades)
        
        # Should have 3 combinations: 2 different 2-confluence and 1 three-confluence
        assert len(combinations) == 3
        
        # Find the 2-confluence and 3-confluence combinations
        two_conf = [c for c in combinations if c['confluence_count'] == 2]
        three_conf = [c for c in combinations if c['confluence_count'] == 3]
        
        assert len(two_conf) == 2  # ['support', 'rsi_oversold'] and ['resistance', 'volume_spike']
        assert len(three_conf) == 1
        
        # Check 3-confluence combination
        assert three_conf[0]['total_trades'] == 1
        assert three_conf[0]['total_pnl'] == Decimal("50")
        
        # Check that combinations are sorted by PnL (descending)
        assert combinations[0]['total_pnl'] >= combinations[1]['total_pnl']
        assert combinations[1]['total_pnl'] >= combinations[2]['total_pnl']
    
    def test_get_confluence_performance_ranking(self, analysis_service, confluence_trades):
        """Test confluence performance ranking."""
        # Rank by total PnL
        pnl_ranking = analysis_service.get_confluence_performance_ranking(confluence_trades, 'total_pnl')
        assert pnl_ranking[0].confluence == "support"  # Highest total PnL
        
        # Rank by win rate
        win_rate_ranking = analysis_service.get_confluence_performance_ranking(confluence_trades, 'win_rate')
        # Support, rsi_oversold, and volume_spike should all have high win rates
        top_confluence = win_rate_ranking[0]
        assert top_confluence.win_rate >= 50.0
        
        # Test invalid sort parameter
        with pytest.raises(ValueError, match="Invalid sort_by parameter"):
            analysis_service.get_confluence_performance_ranking(confluence_trades, 'invalid')
    
    def test_compare_confluences(self, analysis_service, confluence_trades):
        """Test confluence comparison."""
        comparison = analysis_service.compare_confluences(confluence_trades, "support", "resistance")
        
        assert comparison['confluence1']['name'] == "support"
        assert comparison['confluence2']['name'] == "resistance"
        
        # Support should perform better than resistance
        assert comparison['comparison']['win_rate_difference'] > 0
        assert comparison['comparison']['pnl_difference'] > 0
        
        # Test non-existent confluence
        with pytest.raises(ValueError, match="Confluence 'nonexistent' not found"):
            analysis_service.compare_confluences(confluence_trades, "support", "nonexistent")
    
    def test_get_confluence_statistics(self, analysis_service, confluence_trades):
        """Test comprehensive confluence statistics."""
        stats = analysis_service.get_confluence_statistics(confluence_trades)
        
        assert stats['total_confluences'] == 4  # support, rsi_oversold, resistance, volume_spike
        assert stats['most_used_confluence'] == "support"  # Appears in 3 trades
        assert stats['most_used_count'] == 3
        assert stats['best_performing_confluence'] == "support"
        assert stats['trades_with_multiple_confluences'] == 3
        assert stats['multiple_confluence_percentage'] == 75.0  # 3 out of 4 trades
        assert stats['average_confluences_per_trade'] == 2.0  # 8 total confluences / 4 trades
    
    def test_get_confluence_statistics_empty_trades(self, analysis_service):
        """Test confluence statistics with empty trades."""
        stats = analysis_service.get_confluence_statistics([])
        
        assert stats['total_confluences'] == 0
        assert stats['most_used_confluence'] is None
        assert stats['best_performing_confluence'] is None
        assert stats['worst_performing_confluence'] is None
        assert stats['average_confluences_per_trade'] == 0.0
        assert stats['trades_with_multiple_confluences'] == 0


class TestAnalysisServiceEdgeCases:
    """Test edge cases for AnalysisService."""
    
    @pytest.fixture
    def analysis_service(self):
        return AnalysisService()
    
    def test_trades_with_zero_pnl(self, analysis_service):
        """Test handling of trades with zero PnL."""
        trade = Trade(
            id="zero_pnl",
            exchange="bitunix",
            symbol="BTCUSDT",
            side=TradeSide.LONG,
            entry_price=Decimal("50000"),
            quantity=Decimal("0.1"),
            entry_time=datetime(2024, 1, 1),
            exit_price=Decimal("50000"),
            exit_time=datetime(2024, 1, 1, 2),
            pnl=Decimal("0"),
            status=TradeStatus.CLOSED
        )
        
        summary = analysis_service.get_performance_summary([trade])
        assert summary['total_trades'] == 1
        assert summary['winning_trades'] == 0
        assert summary['losing_trades'] == 0
        assert summary['total_pnl'] == Decimal("0")
    
    def test_trades_without_confluences(self, analysis_service):
        """Test analysis of trades without confluences."""
        trade = Trade(
            id="no_confluence",
            exchange="bitunix",
            symbol="BTCUSDT",
            side=TradeSide.LONG,
            entry_price=Decimal("50000"),
            quantity=Decimal("0.1"),
            entry_time=datetime(2024, 1, 1),
            exit_price=Decimal("51000"),
            exit_time=datetime(2024, 1, 1, 2),
            pnl=Decimal("100"),
            status=TradeStatus.CLOSED,
            confluences=[]
        )
        
        confluence_metrics = analysis_service.analyze_confluences([trade])
        assert len(confluence_metrics) == 0
    
    def test_same_day_multiple_aggregations(self, analysis_service):
        """Test multiple trades on same day with different hours."""
        base_time = datetime(2024, 1, 1)
        trades = []
        
        for hour in range(0, 24, 4):  # 6 trades throughout the day
            trade = Trade(
                id=f"trade_{hour}",
                exchange="bitunix",
                symbol="BTCUSDT",
                side=TradeSide.LONG,
                entry_price=Decimal("50000"),
                quantity=Decimal("0.1"),
                entry_time=base_time + timedelta(hours=hour),
                exit_price=Decimal("50010"),
                exit_time=base_time + timedelta(hours=hour, minutes=30),
                pnl=Decimal("1"),
                status=TradeStatus.CLOSED
            )
            trades.append(trade)
        
        trend_data = analysis_service.calculate_pnl_trend(trades, 'daily')
        assert len(trend_data) == 1
        assert trend_data[0].daily_pnl == Decimal("6")
        assert trend_data[0].trade_count == 6