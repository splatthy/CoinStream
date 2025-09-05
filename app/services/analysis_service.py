from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from app.models.trade import Trade, TradeStatus, WinLoss


@dataclass
class PnLDataPoint:
    """Data point for PnL trend analysis."""

    date: datetime
    daily_pnl: Decimal
    cumulative_pnl: Decimal
    trade_count: int


@dataclass
class ConfluenceMetrics:
    """Performance metrics for a confluence."""

    confluence: str
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_pnl: Decimal
    average_pnl: Decimal
    pnl_percentage: float


class AnalysisService:
    """Service for analyzing trading performance and calculating metrics."""

    def __init__(self, data_service=None):
        """
        Initialize the AnalysisService.

        Args:
            data_service: Optional DataService instance for data access
        """
        self.data_service = data_service
        self.timeframe_aggregators = {
            "daily": self._aggregate_daily,
            "weekly": self._aggregate_weekly,
            "monthly": self._aggregate_monthly,
        }

    def calculate_pnl_trend(
        self, trades: List[Trade], timeframe: str = "daily"
    ) -> List[PnLDataPoint]:
        """
        Calculate PnL trend with specified timeframe aggregation.

        Args:
            trades: List of trades to analyze
            timeframe: 'daily', 'weekly', or 'monthly'

        Returns:
            List of PnLDataPoint objects with trend data
        """
        if timeframe not in self.timeframe_aggregators:
            raise ValueError(
                f"Unsupported timeframe: {timeframe}. Use 'daily', 'weekly', or 'monthly'"
            )

        # Filter closed trades with PnL data
        closed_trades = [
            trade
            for trade in trades
            if trade.status == TradeStatus.CLOSED
            and trade.pnl is not None
            and trade.exit_time is not None
        ]

        if not closed_trades:
            return []

        # Sort trades by exit time
        closed_trades.sort(key=lambda t: t.exit_time)

        # Aggregate by timeframe
        aggregator = self.timeframe_aggregators[timeframe]
        return aggregator(closed_trades)

    def _aggregate_daily(self, trades: List[Trade]) -> List[PnLDataPoint]:
        """Aggregate trades by day."""
        daily_data = defaultdict(lambda: {"pnl": Decimal("0"), "count": 0})

        for trade in trades:
            date_key = trade.exit_time.date()
            daily_data[date_key]["pnl"] += trade.pnl
            daily_data[date_key]["count"] += 1

        # Convert to sorted list with cumulative PnL
        cumulative_pnl = Decimal("0")
        result = []

        for date in sorted(daily_data.keys()):
            daily_pnl = daily_data[date]["pnl"]
            cumulative_pnl += daily_pnl

            result.append(
                PnLDataPoint(
                    date=datetime.combine(date, datetime.min.time()),
                    daily_pnl=daily_pnl,
                    cumulative_pnl=cumulative_pnl,
                    trade_count=daily_data[date]["count"],
                )
            )

        return result

    def _aggregate_weekly(self, trades: List[Trade]) -> List[PnLDataPoint]:
        """Aggregate trades by week (Monday to Sunday)."""
        weekly_data = defaultdict(lambda: {"pnl": Decimal("0"), "count": 0})

        for trade in trades:
            # Get Monday of the week
            days_since_monday = trade.exit_time.weekday()
            week_start = trade.exit_time.date() - timedelta(days=days_since_monday)

            weekly_data[week_start]["pnl"] += trade.pnl
            weekly_data[week_start]["count"] += 1

        # Convert to sorted list with cumulative PnL
        cumulative_pnl = Decimal("0")
        result = []

        for week_start in sorted(weekly_data.keys()):
            weekly_pnl = weekly_data[week_start]["pnl"]
            cumulative_pnl += weekly_pnl

            result.append(
                PnLDataPoint(
                    date=datetime.combine(week_start, datetime.min.time()),
                    daily_pnl=weekly_pnl,
                    cumulative_pnl=cumulative_pnl,
                    trade_count=weekly_data[week_start]["count"],
                )
            )

        return result

    def _aggregate_monthly(self, trades: List[Trade]) -> List[PnLDataPoint]:
        """Aggregate trades by month."""
        monthly_data = defaultdict(lambda: {"pnl": Decimal("0"), "count": 0})

        for trade in trades:
            # Get first day of the month
            month_start = trade.exit_time.date().replace(day=1)

            monthly_data[month_start]["pnl"] += trade.pnl
            monthly_data[month_start]["count"] += 1

        # Convert to sorted list with cumulative PnL
        cumulative_pnl = Decimal("0")
        result = []

        for month_start in sorted(monthly_data.keys()):
            monthly_pnl = monthly_data[month_start]["pnl"]
            cumulative_pnl += monthly_pnl

            result.append(
                PnLDataPoint(
                    date=datetime.combine(month_start, datetime.min.time()),
                    daily_pnl=monthly_pnl,
                    cumulative_pnl=cumulative_pnl,
                    trade_count=monthly_data[month_start]["count"],
                )
            )

        return result

    def calculate_cumulative_pnl(
        self, trades: List[Trade], end_date: Optional[datetime] = None
    ) -> Decimal:
        """
        Calculate cumulative PnL up to a specific date.

        Args:
            trades: List of trades to analyze
            end_date: Calculate PnL up to this date (inclusive). If None, uses all trades.

        Returns:
            Cumulative PnL as Decimal
        """
        cumulative = Decimal("0")

        for trade in trades:
            if (
                trade.status == TradeStatus.CLOSED
                and trade.pnl is not None
                and trade.exit_time is not None
            ):
                if end_date is None or trade.exit_time <= end_date:
                    cumulative += trade.pnl

        return cumulative

    def get_performance_summary(self, trades: List[Trade]) -> Dict[str, Any]:
        """
        Generate overall performance summary.

        Args:
            trades: List of trades to analyze

        Returns:
            Dictionary with performance metrics
        """
        closed_trades = [
            trade
            for trade in trades
            if trade.status == TradeStatus.CLOSED and trade.pnl is not None
        ]

        if not closed_trades:
            return {
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "win_rate": 0.0,
                "total_pnl": Decimal("0"),
                "average_pnl": Decimal("0"),
                "largest_win": Decimal("0"),
                "largest_loss": Decimal("0"),
            }

        winning_trades = [t for t in closed_trades if t.pnl > 0]
        losing_trades = [t for t in closed_trades if t.pnl < 0]

        total_pnl = sum(trade.pnl for trade in closed_trades)
        win_rate = len(winning_trades) / len(closed_trades) * 100

        largest_win = max((t.pnl for t in winning_trades), default=Decimal("0"))
        largest_loss = min((t.pnl for t in losing_trades), default=Decimal("0"))

        return {
            "total_trades": len(closed_trades),
            "winning_trades": len(winning_trades),
            "losing_trades": len(losing_trades),
            "win_rate": round(win_rate, 2),
            "total_pnl": total_pnl,
            "average_pnl": total_pnl / len(closed_trades),
            "largest_win": largest_win,
            "largest_loss": largest_loss,
        }

    def analyze_confluences(self, trades: List[Trade]) -> List[ConfluenceMetrics]:
        """
        Analyze performance by confluence type.

        Args:
            trades: List of trades to analyze

        Returns:
            List of ConfluenceMetrics for each confluence
        """
        # Get all unique confluences
        all_confluences = set()
        for trade in trades:
            all_confluences.update(trade.confluences)

        confluence_metrics = []

        for confluence in sorted(all_confluences):
            # Get trades that include this confluence
            confluence_trades = [
                trade
                for trade in trades
                if (
                    confluence in trade.confluences
                    and trade.status == TradeStatus.CLOSED
                    and trade.pnl is not None
                )
            ]

            if not confluence_trades:
                continue

            winning_trades = [t for t in confluence_trades if t.pnl > 0]
            losing_trades = [t for t in confluence_trades if t.pnl < 0]

            total_pnl = sum(trade.pnl for trade in confluence_trades)
            win_rate = len(winning_trades) / len(confluence_trades) * 100
            average_pnl = total_pnl / len(confluence_trades)

            # Calculate PnL percentage (relative to total portfolio PnL)
            total_portfolio_pnl = sum(
                trade.pnl
                for trade in trades
                if trade.status == TradeStatus.CLOSED and trade.pnl is not None
            )
            pnl_percentage = (
                float(total_pnl / total_portfolio_pnl * 100)
                if total_portfolio_pnl != 0
                else 0.0
            )

            confluence_metrics.append(
                ConfluenceMetrics(
                    confluence=confluence,
                    total_trades=len(confluence_trades),
                    winning_trades=len(winning_trades),
                    losing_trades=len(losing_trades),
                    win_rate=round(win_rate, 2),
                    total_pnl=total_pnl,
                    average_pnl=average_pnl,
                    pnl_percentage=round(pnl_percentage, 2),
                )
            )

        # Sort by total PnL descending
        confluence_metrics.sort(key=lambda x: x.total_pnl, reverse=True)

        return confluence_metrics

    def calculate_win_rate(
        self, trades: List[Trade], confluence: Optional[str] = None
    ) -> float:
        """
        Calculate win rate for all trades or specific confluence.

        Args:
            trades: List of trades to analyze
            confluence: Optional confluence to filter by

        Returns:
            Win rate as percentage (0-100)
        """
        if confluence:
            filtered_trades = [
                trade
                for trade in trades
                if (
                    confluence in trade.confluences
                    and trade.status == TradeStatus.CLOSED
                    and trade.pnl is not None
                )
            ]
        else:
            filtered_trades = [
                trade
                for trade in trades
                if trade.status == TradeStatus.CLOSED and trade.pnl is not None
            ]

        if not filtered_trades:
            return 0.0

        winning_trades = [t for t in filtered_trades if t.pnl > 0]
        return len(winning_trades) / len(filtered_trades) * 100

    def get_pnl_by_timeframe(self, trades: List[Trade], timeframe: str) -> pd.DataFrame:
        """
        Get PnL data as pandas DataFrame for easier visualization.

        Args:
            trades: List of trades to analyze
            timeframe: 'daily', 'weekly', or 'monthly'

        Returns:
            DataFrame with date, daily_pnl, cumulative_pnl, trade_count columns
        """
        pnl_data = self.calculate_pnl_trend(trades, timeframe)

        if not pnl_data:
            return pd.DataFrame(
                columns=["date", "daily_pnl", "cumulative_pnl", "trade_count"]
            )

        return pd.DataFrame(
            [
                {
                    "date": point.date,
                    "daily_pnl": float(point.daily_pnl),
                    "cumulative_pnl": float(point.cumulative_pnl),
                    "trade_count": point.trade_count,
                }
                for point in pnl_data
            ]
        )

    def get_confluence_win_rates(self, trades: List[Trade]) -> Dict[str, float]:
        """
        Get win rates for all confluences.

        Args:
            trades: List of trades to analyze

        Returns:
            Dictionary mapping confluence names to win rates
        """
        confluence_metrics = self.analyze_confluences(trades)
        return {metrics.confluence: metrics.win_rate for metrics in confluence_metrics}

    def get_confluence_pnl_percentages(self, trades: List[Trade]) -> Dict[str, float]:
        """
        Get PnL percentages for all confluences.

        Args:
            trades: List of trades to analyze

        Returns:
            Dictionary mapping confluence names to PnL percentages
        """
        confluence_metrics = self.analyze_confluences(trades)
        return {
            metrics.confluence: metrics.pnl_percentage for metrics in confluence_metrics
        }

    def analyze_confluence_combinations(
        self, trades: List[Trade]
    ) -> List[Dict[str, Any]]:
        """
        Analyze performance of confluence combinations (trades with multiple confluences).

        Args:
            trades: List of trades to analyze

        Returns:
            List of dictionaries with combination analysis
        """
        closed_trades = [
            trade
            for trade in trades
            if trade.status == TradeStatus.CLOSED and trade.pnl is not None
        ]

        # Group trades by confluence combinations
        combination_data = defaultdict(lambda: {"trades": [], "pnl": Decimal("0")})

        for trade in closed_trades:
            if len(trade.confluences) > 1:
                # Sort confluences for consistent combination keys
                combination_key = tuple(sorted(trade.confluences))
                combination_data[combination_key]["trades"].append(trade)
                combination_data[combination_key]["pnl"] += trade.pnl

        # Calculate metrics for each combination
        results = []
        for combination, data in combination_data.items():
            trades_list = data["trades"]
            winning_trades = [t for t in trades_list if t.pnl > 0]

            win_rate = (
                len(winning_trades) / len(trades_list) * 100 if trades_list else 0
            )

            results.append(
                {
                    "confluences": list(combination),
                    "confluence_count": len(combination),
                    "total_trades": len(trades_list),
                    "winning_trades": len(winning_trades),
                    "losing_trades": len(trades_list) - len(winning_trades),
                    "win_rate": round(win_rate, 2),
                    "total_pnl": data["pnl"],
                    "average_pnl": data["pnl"] / len(trades_list)
                    if trades_list
                    else Decimal("0"),
                }
            )

        # Sort by total PnL descending
        results.sort(key=lambda x: x["total_pnl"], reverse=True)

        return results

    def get_confluence_performance_ranking(
        self, trades: List[Trade], sort_by: str = "total_pnl"
    ) -> List[ConfluenceMetrics]:
        """
        Get confluences ranked by performance metric.

        Args:
            trades: List of trades to analyze
            sort_by: Metric to sort by ('total_pnl', 'win_rate', 'average_pnl', 'total_trades')

        Returns:
            List of ConfluenceMetrics sorted by specified metric
        """
        confluence_metrics = self.analyze_confluences(trades)

        if sort_by == "total_pnl":
            confluence_metrics.sort(key=lambda x: x.total_pnl, reverse=True)
        elif sort_by == "win_rate":
            confluence_metrics.sort(key=lambda x: x.win_rate, reverse=True)
        elif sort_by == "average_pnl":
            confluence_metrics.sort(key=lambda x: x.average_pnl, reverse=True)
        elif sort_by == "total_trades":
            confluence_metrics.sort(key=lambda x: x.total_trades, reverse=True)
        else:
            raise ValueError(f"Invalid sort_by parameter: {sort_by}")

        return confluence_metrics

    def compare_confluences(
        self, trades: List[Trade], confluence1: str, confluence2: str
    ) -> Dict[str, Any]:
        """
        Compare performance between two specific confluences.

        Args:
            trades: List of trades to analyze
            confluence1: First confluence to compare
            confluence2: Second confluence to compare

        Returns:
            Dictionary with comparison metrics
        """
        confluence_metrics = self.analyze_confluences(trades)

        # Find metrics for both confluences
        metrics1 = next(
            (m for m in confluence_metrics if m.confluence == confluence1), None
        )
        metrics2 = next(
            (m for m in confluence_metrics if m.confluence == confluence2), None
        )

        if not metrics1:
            raise ValueError(f"Confluence '{confluence1}' not found in trades")
        if not metrics2:
            raise ValueError(f"Confluence '{confluence2}' not found in trades")

        return {
            "confluence1": {
                "name": confluence1,
                "total_trades": metrics1.total_trades,
                "win_rate": metrics1.win_rate,
                "total_pnl": metrics1.total_pnl,
                "average_pnl": metrics1.average_pnl,
            },
            "confluence2": {
                "name": confluence2,
                "total_trades": metrics2.total_trades,
                "win_rate": metrics2.win_rate,
                "total_pnl": metrics2.total_pnl,
                "average_pnl": metrics2.average_pnl,
            },
            "comparison": {
                "win_rate_difference": metrics1.win_rate - metrics2.win_rate,
                "pnl_difference": metrics1.total_pnl - metrics2.total_pnl,
                "average_pnl_difference": metrics1.average_pnl - metrics2.average_pnl,
                "trade_count_difference": metrics1.total_trades - metrics2.total_trades,
            },
        }

    def get_confluence_statistics(self, trades: List[Trade]) -> Dict[str, Any]:
        """
        Get comprehensive confluence statistics.

        Args:
            trades: List of trades to analyze

        Returns:
            Dictionary with confluence statistics
        """
        closed_trades = [
            trade
            for trade in trades
            if trade.status == TradeStatus.CLOSED and trade.pnl is not None
        ]

        if not closed_trades:
            return {
                "total_confluences": 0,
                "most_used_confluence": None,
                "best_performing_confluence": None,
                "worst_performing_confluence": None,
                "average_confluences_per_trade": 0.0,
                "trades_with_multiple_confluences": 0,
            }

        # Get all confluences and their usage
        confluence_usage = defaultdict(int)
        total_confluence_count = 0
        trades_with_multiple = 0

        for trade in closed_trades:
            if len(trade.confluences) > 1:
                trades_with_multiple += 1

            for confluence in trade.confluences:
                confluence_usage[confluence] += 1
                total_confluence_count += 1

        confluence_metrics = self.analyze_confluences(trades)

        # Find best and worst performing confluences
        best_confluence = (
            max(confluence_metrics, key=lambda x: x.total_pnl)
            if confluence_metrics
            else None
        )
        worst_confluence = (
            min(confluence_metrics, key=lambda x: x.total_pnl)
            if confluence_metrics
            else None
        )
        most_used = (
            max(confluence_usage.items(), key=lambda x: x[1])
            if confluence_usage
            else (None, 0)
        )

        return {
            "total_confluences": len(confluence_usage),
            "most_used_confluence": most_used[0],
            "most_used_count": most_used[1],
            "best_performing_confluence": best_confluence.confluence
            if best_confluence
            else None,
            "best_performing_pnl": best_confluence.total_pnl
            if best_confluence
            else Decimal("0"),
            "worst_performing_confluence": worst_confluence.confluence
            if worst_confluence
            else None,
            "worst_performing_pnl": worst_confluence.total_pnl
            if worst_confluence
            else Decimal("0"),
            "average_confluences_per_trade": total_confluence_count / len(closed_trades)
            if closed_trades
            else 0.0,
            "trades_with_multiple_confluences": trades_with_multiple,
            "multiple_confluence_percentage": (
                trades_with_multiple / len(closed_trades) * 100
            )
            if closed_trades
            else 0.0,
        }
