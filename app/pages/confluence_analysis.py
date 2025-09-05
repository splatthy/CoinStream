"""
Confluence Analysis page for analyzing trading performance by confluence types.
"""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import logging
import json
import io
from decimal import Decimal
from scipy import stats
import warnings
warnings.filterwarnings('ignore')

from app.services.data_service import DataService
from app.services.analysis_service import AnalysisService, ConfluenceMetrics
from app.models.trade import Trade, TradeStatus
from app.utils.state_management import get_state_manager
from app.utils.notifications import get_notification_manager

logger = logging.getLogger(__name__)


def show_confluence_analysis_page() -> None:
    """Display the Confluence Analysis page with performance metrics and comparisons."""
    st.title("🎯 Confluence Analysis")
    
    # Get services from session state
    state_manager = get_state_manager()
    notification_manager = get_notification_manager()
    
    data_service = state_manager.get("data_service")
    analysis_service = state_manager.get("analysis_service")
    
    if not data_service or not analysis_service:
        st.error("Services not initialized. Please refresh the page.")
        return
    
    try:
        # Load trade data
        with st.spinner("Loading trade data..."):
            trades = data_service.load_trades()
        
        if not trades:
            st.info("No trade data available. Please configure exchanges and sync data first.")
            return
        
        # Filter for closed trades with confluence data
        closed_trades = [
            trade for trade in trades 
            if (trade.status == TradeStatus.CLOSED and 
                trade.pnl is not None and 
                trade.confluences)
        ]
        
        if not closed_trades:
            st.info("No closed trades with confluence data available for analysis.")
            return
        
        # Display confluence performance dashboard
        render_confluence_dashboard(analysis_service, closed_trades)
        
        st.divider()
        
        # Display confluence comparison features
        render_confluence_comparison(analysis_service, closed_trades)
        
    except Exception as e:
        logger.error(f"Error in confluence analysis page: {e}")
        notification_manager.error(f"Error loading confluence analysis: {e}")
        st.error(f"Error loading confluence analysis: {e}")


def render_confluence_dashboard(analysis_service: AnalysisService, trades: List[Trade]) -> None:
    """Render the main confluence performance dashboard."""
    try:
        st.subheader("📊 Confluence Performance Dashboard")
        
        # Get confluence metrics
        confluence_metrics = analysis_service.analyze_confluences(trades)
        
        if not confluence_metrics:
            st.warning("No confluence data available for analysis.")
            return
        
        # Display summary statistics
        render_confluence_summary(analysis_service, trades, confluence_metrics)
        
        # Performance ranking and sorting
        col1, col2 = st.columns([1, 3])
        
        with col1:
            # Sorting options
            sort_options = {
                "Total PnL": "total_pnl",
                "Win Rate": "win_rate", 
                "Average PnL": "average_pnl",
                "Total Trades": "total_trades"
            }
            
            sort_by = st.selectbox(
                "Sort by:",
                options=list(sort_options.keys()),
                key="confluence_sort"
            )
            
            # Get sorted metrics
            sorted_metrics = analysis_service.get_confluence_performance_ranking(
                trades, sort_options[sort_by]
            )
            
            # Display top performers
            st.subheader("🏆 Top Performers")
            for i, metrics in enumerate(sorted_metrics[:5], 1):
                with st.container():
                    st.markdown(f"**{i}. {metrics.confluence}**")
                    st.caption(f"Win Rate: {metrics.win_rate}% | PnL: ${float(metrics.total_pnl):,.2f}")
        
        with col2:
            # Main performance chart
            render_confluence_performance_chart(sorted_metrics, sort_by)
        
        # Detailed metrics table
        render_confluence_metrics_table(sorted_metrics)
        
    except Exception as e:
        logger.error(f"Error rendering confluence dashboard: {e}")
        st.error("Error loading confluence dashboard")


def render_confluence_summary(analysis_service: AnalysisService, trades: List[Trade], 
                             confluence_metrics: List[ConfluenceMetrics]) -> None:
    """Render confluence summary statistics."""
    try:
        confluence_stats = analysis_service.get_confluence_statistics(trades)
        
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            st.metric(
                "Total Confluences",
                confluence_stats['total_confluences']
            )
        
        with col2:
            st.metric(
                "Most Used",
                confluence_stats['most_used_confluence'] or "N/A",
                f"{confluence_stats['most_used_count']} trades"
            )
        
        with col3:
            best_confluence = confluence_stats['best_performing_confluence']
            best_pnl = float(confluence_stats['best_performing_pnl'])
            st.metric(
                "Best Performer",
                best_confluence or "N/A",
                f"${best_pnl:,.2f}" if best_confluence else None
            )
        
        with col4:
            avg_confluences = confluence_stats['average_confluences_per_trade']
            st.metric(
                "Avg per Trade",
                f"{avg_confluences:.1f}"
            )
        
        with col5:
            multiple_pct = confluence_stats['multiple_confluence_percentage']
            st.metric(
                "Multiple Confluences",
                f"{multiple_pct:.1f}%"
            )
        
    except Exception as e:
        logger.error(f"Error rendering confluence summary: {e}")


def render_confluence_performance_chart(metrics: List[ConfluenceMetrics], sort_by: str) -> None:
    """Render the main confluence performance chart."""
    try:
        if not metrics:
            st.warning("No confluence metrics available for chart.")
            return
        
        # Prepare data for chart
        confluences = [m.confluence for m in metrics]
        
        if sort_by == "Total PnL":
            values = [float(m.total_pnl) for m in metrics]
            title = "Total PnL by Confluence"
            y_label = "Total PnL ($)"
            colors = ['green' if v >= 0 else 'red' for v in values]
        elif sort_by == "Win Rate":
            values = [m.win_rate for m in metrics]
            title = "Win Rate by Confluence"
            y_label = "Win Rate (%)"
            colors = ['darkgreen' if v >= 50 else 'darkred' for v in values]
        elif sort_by == "Average PnL":
            values = [float(m.average_pnl) for m in metrics]
            title = "Average PnL per Trade by Confluence"
            y_label = "Average PnL ($)"
            colors = ['green' if v >= 0 else 'red' for v in values]
        else:  # Total Trades
            values = [m.total_trades for m in metrics]
            title = "Total Trades by Confluence"
            y_label = "Number of Trades"
            colors = ['steelblue'] * len(values)
        
        # Create bar chart
        fig = go.Figure(data=[
            go.Bar(
                x=confluences,
                y=values,
                marker_color=colors,
                hovertemplate=(
                    '<b>%{x}</b><br>'
                    f'{y_label}: %{{y}}<br>'
                    '<extra></extra>'
                )
            )
        ])
        
        fig.update_layout(
            title=title,
            xaxis_title="Confluence",
            yaxis_title=y_label,
            height=400,
            showlegend=False
        )
        
        # Rotate x-axis labels if many confluences
        if len(confluences) > 5:
            fig.update_xaxes(tickangle=45)
        
        st.plotly_chart(fig, use_container_width=True)
        
    except Exception as e:
        logger.error(f"Error rendering confluence performance chart: {e}")


def render_confluence_metrics_table(metrics: List[ConfluenceMetrics]) -> None:
    """Render detailed confluence metrics table."""
    try:
        st.subheader("📋 Detailed Confluence Metrics")
        
        if not metrics:
            st.warning("No confluence metrics available.")
            return
        
        # Convert to DataFrame for display
        df = pd.DataFrame([
            {
                'Confluence': m.confluence,
                'Total Trades': m.total_trades,
                'Winning Trades': m.winning_trades,
                'Losing Trades': m.losing_trades,
                'Win Rate (%)': f"{m.win_rate:.1f}%",
                'Total PnL': f"${float(m.total_pnl):,.2f}",
                'Average PnL': f"${float(m.average_pnl):,.2f}",
                'PnL %': f"{m.pnl_percentage:.1f}%"
            }
            for m in metrics
        ])
        
        # Display with enhanced styling
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Confluence": st.column_config.TextColumn("Confluence", width="medium"),
                "Total Trades": st.column_config.NumberColumn("Total Trades", width="small"),
                "Winning Trades": st.column_config.NumberColumn("Wins", width="small"),
                "Losing Trades": st.column_config.NumberColumn("Losses", width="small"),
                "Win Rate (%)": st.column_config.TextColumn("Win Rate", width="small"),
                "Total PnL": st.column_config.TextColumn("Total PnL", width="medium"),
                "Average PnL": st.column_config.TextColumn("Avg PnL", width="medium"),
                "PnL %": st.column_config.TextColumn("PnL %", width="small")
            }
        )
        
        # Export functionality
        render_confluence_export_options(df, metrics)
        
    except Exception as e:
        logger.error(f"Error rendering confluence metrics table: {e}")


def render_confluence_comparison(analysis_service: AnalysisService, trades: List[Trade]) -> None:
    """Render confluence comparison features."""
    try:
        st.subheader("🔍 Confluence Comparison")
        
        # Get available confluences
        all_confluences = set()
        for trade in trades:
            all_confluences.update(trade.confluences)
        
        confluence_list = sorted(list(all_confluences))
        
        if len(confluence_list) < 2:
            st.info("Need at least 2 confluences for comparison analysis.")
            return
        
        # Comparison selection
        col1, col2 = st.columns(2)
        
        with col1:
            confluence1 = st.selectbox(
                "Select first confluence:",
                options=confluence_list,
                key="confluence1_select"
            )
        
        with col2:
            confluence2 = st.selectbox(
                "Select second confluence:",
                options=[c for c in confluence_list if c != confluence1],
                key="confluence2_select"
            )
        
        if confluence1 and confluence2:
            # Perform comparison
            comparison = analysis_service.compare_confluences(trades, confluence1, confluence2)
            
            # Display comparison results
            render_comparison_results(comparison)
            
            # Side-by-side comparison charts
            render_side_by_side_comparison(analysis_service, trades, confluence1, confluence2)
        
        # Date range and trade type filtering
        render_comparison_filters(analysis_service, trades, confluence_list)
        
    except Exception as e:
        logger.error(f"Error rendering confluence comparison: {e}")


def render_comparison_results(comparison: Dict[str, Any]) -> None:
    """Render comparison results between two confluences."""
    try:
        st.subheader("📊 Comparison Results")
        
        conf1 = comparison['confluence1']
        conf2 = comparison['confluence2']
        comp = comparison['comparison']
        
        # Display metrics side by side
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown(f"**{conf1['name']}**")
            st.metric("Total Trades", conf1['total_trades'])
            st.metric("Win Rate", f"{conf1['win_rate']:.1f}%")
            st.metric("Total PnL", f"${float(conf1['total_pnl']):,.2f}")
            st.metric("Avg PnL", f"${float(conf1['average_pnl']):,.2f}")
        
        with col2:
            st.markdown(f"**{conf2['name']}**")
            st.metric("Total Trades", conf2['total_trades'])
            st.metric("Win Rate", f"{conf2['win_rate']:.1f}%")
            st.metric("Total PnL", f"${float(conf2['total_pnl']):,.2f}")
            st.metric("Avg PnL", f"${float(conf2['average_pnl']):,.2f}")
        
        with col3:
            st.markdown("**Differences**")
            
            trade_diff = comp['trade_count_difference']
            st.metric("Trade Count Diff", f"{trade_diff:+d}")
            
            win_rate_diff = comp['win_rate_difference']
            st.metric("Win Rate Diff", f"{win_rate_diff:+.1f}%")
            
            pnl_diff = float(comp['pnl_difference'])
            st.metric("PnL Difference", f"${pnl_diff:+,.2f}")
            
            avg_pnl_diff = float(comp['average_pnl_difference'])
            st.metric("Avg PnL Diff", f"${avg_pnl_diff:+,.2f}")
        
    except Exception as e:
        logger.error(f"Error rendering comparison results: {e}")


def render_side_by_side_comparison(analysis_service: AnalysisService, trades: List[Trade], 
                                 confluence1: str, confluence2: str) -> None:
    """Render side-by-side comparison charts."""
    try:
        st.subheader("📈 Side-by-Side Performance")
        
        # Get trades for each confluence
        conf1_trades = [t for t in trades if confluence1 in t.confluences]
        conf2_trades = [t for t in trades if confluence2 in t.confluences]
        
        col1, col2 = st.columns(2)
        
        with col1:
            render_confluence_performance_pie(conf1_trades, confluence1)
        
        with col2:
            render_confluence_performance_pie(conf2_trades, confluence2)
        
        # Statistical significance testing
        render_statistical_significance_testing(conf1_trades, conf2_trades, confluence1, confluence2)
        
        # PnL distribution comparison
        render_pnl_distribution_comparison(conf1_trades, conf2_trades, confluence1, confluence2)
        
        # Performance over time comparison
        render_performance_over_time_comparison(conf1_trades, conf2_trades, confluence1, confluence2)
        
    except Exception as e:
        logger.error(f"Error rendering side-by-side comparison: {e}")


def render_confluence_performance_pie(trades: List[Trade], confluence_name: str) -> None:
    """Render pie chart for confluence win/loss distribution."""
    try:
        winning_trades = [t for t in trades if t.pnl > 0]
        losing_trades = [t for t in trades if t.pnl < 0]
        breakeven_trades = [t for t in trades if t.pnl == 0]
        
        labels = []
        values = []
        colors = []
        
        if winning_trades:
            labels.append('Wins')
            values.append(len(winning_trades))
            colors.append('green')
        
        if losing_trades:
            labels.append('Losses')
            values.append(len(losing_trades))
            colors.append('red')
        
        if breakeven_trades:
            labels.append('Breakeven')
            values.append(len(breakeven_trades))
            colors.append('gray')
        
        if not values:
            st.warning(f"No data for {confluence_name}")
            return
        
        fig = go.Figure(data=[
            go.Pie(
                labels=labels,
                values=values,
                marker_colors=colors,
                hovertemplate='<b>%{label}</b><br>Count: %{value}<br>Percentage: %{percent}<extra></extra>'
            )
        ])
        
        fig.update_layout(
            title=f"{confluence_name} Win/Loss Distribution",
            height=300,
            showlegend=True
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
    except Exception as e:
        logger.error(f"Error rendering confluence performance pie: {e}")


def render_pnl_distribution_comparison(trades1: List[Trade], trades2: List[Trade], 
                                     conf1: str, conf2: str) -> None:
    """Render PnL distribution comparison histogram."""
    try:
        st.subheader("💰 PnL Distribution Comparison")
        
        pnl1 = [float(t.pnl) for t in trades1 if t.pnl is not None]
        pnl2 = [float(t.pnl) for t in trades2 if t.pnl is not None]
        
        if not pnl1 and not pnl2:
            st.warning("No PnL data available for comparison.")
            return
        
        fig = go.Figure()
        
        if pnl1:
            fig.add_trace(go.Histogram(
                x=pnl1,
                name=conf1,
                opacity=0.7,
                nbinsx=20,
                marker_color='blue'
            ))
        
        if pnl2:
            fig.add_trace(go.Histogram(
                x=pnl2,
                name=conf2,
                opacity=0.7,
                nbinsx=20,
                marker_color='orange'
            ))
        
        fig.update_layout(
            title="PnL Distribution Comparison",
            xaxis_title="PnL ($)",
            yaxis_title="Frequency",
            barmode='overlay',
            height=400
        )
        
        # Add statistical lines
        if pnl1:
            fig.add_vline(
                x=np.mean(pnl1),
                line_dash="dash",
                line_color="blue",
                annotation_text=f"{conf1} Mean: ${np.mean(pnl1):.2f}"
            )
        
        if pnl2:
            fig.add_vline(
                x=np.mean(pnl2),
                line_dash="dash", 
                line_color="orange",
                annotation_text=f"{conf2} Mean: ${np.mean(pnl2):.2f}"
            )
        
        st.plotly_chart(fig, use_container_width=True)
        
    except Exception as e:
        logger.error(f"Error rendering PnL distribution comparison: {e}")


def render_comparison_filters(analysis_service: AnalysisService, trades: List[Trade], 
                            confluence_list: List[str]) -> None:
    """Render filtering options for confluence analysis."""
    try:
        st.subheader("🔧 Analysis Filters")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            # Date range filter
            st.markdown("**Date Range**")
            
            # Get date range from trades
            min_date = min(t.exit_time.date() for t in trades if t.exit_time)
            max_date = max(t.exit_time.date() for t in trades if t.exit_time)
            
            start_date = st.date_input(
                "Start Date:",
                value=min_date,
                min_value=min_date,
                max_value=max_date,
                key="filter_start_date"
            )
            
            end_date = st.date_input(
                "End Date:",
                value=max_date,
                min_value=min_date,
                max_value=max_date,
                key="filter_end_date"
            )
        
        with col2:
            # Trade type filter
            st.markdown("**Trade Type**")
            
            trade_types = ["All", "Long Only", "Short Only"]
            selected_type = st.selectbox(
                "Trade Type:",
                options=trade_types,
                key="filter_trade_type"
            )
        
        with col3:
            # Confluence filter
            st.markdown("**Confluence Filter**")
            
            selected_confluences = st.multiselect(
                "Include Confluences:",
                options=confluence_list,
                default=confluence_list,
                key="filter_confluences"
            )
        
        # Apply filters and show filtered analysis
        if st.button("Apply Filters", key="apply_filters"):
            filtered_trades = apply_analysis_filters(
                trades, start_date, end_date, selected_type, selected_confluences
            )
            
            if filtered_trades:
                st.success(f"Filtered to {len(filtered_trades)} trades")
                render_filtered_analysis(analysis_service, filtered_trades)
            else:
                st.warning("No trades match the selected filters.")
        
    except Exception as e:
        logger.error(f"Error rendering comparison filters: {e}")


def apply_analysis_filters(trades: List[Trade], start_date, end_date, 
                         trade_type: str, selected_confluences: List[str]) -> List[Trade]:
    """Apply filters to trade list."""
    filtered_trades = []
    
    for trade in trades:
        # Date filter
        if trade.exit_time and not (start_date <= trade.exit_time.date() <= end_date):
            continue
        
        # Trade type filter
        if trade_type == "Long Only" and trade.side.value != "long":
            continue
        elif trade_type == "Short Only" and trade.side.value != "short":
            continue
        
        # Confluence filter
        if not any(conf in selected_confluences for conf in trade.confluences):
            continue
        
        filtered_trades.append(trade)
    
    return filtered_trades


def render_filtered_analysis(analysis_service: AnalysisService, trades: List[Trade]) -> None:
    """Render analysis results for filtered trades."""
    try:
        st.subheader("🎯 Filtered Analysis Results")
        
        confluence_metrics = analysis_service.analyze_confluences(trades)
        
        if not confluence_metrics:
            st.warning("No confluence data in filtered results.")
            return
        
        # Quick metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Filtered Trades", len(trades))
        
        with col2:
            total_pnl = sum(float(t.pnl) for t in trades if t.pnl)
            st.metric("Total PnL", f"${total_pnl:,.2f}")
        
        with col3:
            win_rate = analysis_service.calculate_win_rate(trades)
            st.metric("Win Rate", f"{win_rate:.1f}%")
        
        with col4:
            st.metric("Confluences", len(confluence_metrics))
        
        # Top performers in filtered data
        st.markdown("**Top Performers (Filtered)**")
        top_metrics = sorted(confluence_metrics, key=lambda x: x.total_pnl, reverse=True)[:3]
        
        for i, metrics in enumerate(top_metrics, 1):
            st.markdown(f"{i}. **{metrics.confluence}** - Win Rate: {metrics.win_rate}%, PnL: ${float(metrics.total_pnl):,.2f}")
        
    except Exception as e:
        logger.error(f"Error rendering filtered analysis: {e}")


def render_confluence_export_options(df: pd.DataFrame, metrics: List[ConfluenceMetrics]) -> None:
    """Render export options for confluence analysis."""
    try:
        st.subheader("📥 Export Analysis")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            # Export as CSV
            if st.button("Export as CSV", key="export_confluence_csv"):
                csv_buffer = io.StringIO()
                df.to_csv(csv_buffer, index=False)
                st.download_button(
                    label="Download CSV",
                    data=csv_buffer.getvalue(),
                    file_name=f"confluence_analysis_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )
        
        with col2:
            # Export as JSON
            if st.button("Export as JSON", key="export_confluence_json"):
                export_data = {
                    'export_date': datetime.now().isoformat(),
                    'analysis_type': 'confluence_performance',
                    'metrics': [
                        {
                            'confluence': m.confluence,
                            'total_trades': m.total_trades,
                            'winning_trades': m.winning_trades,
                            'losing_trades': m.losing_trades,
                            'win_rate': m.win_rate,
                            'total_pnl': float(m.total_pnl),
                            'average_pnl': float(m.average_pnl),
                            'pnl_percentage': m.pnl_percentage
                        }
                        for m in metrics
                    ]
                }
                json_str = json.dumps(export_data, indent=2)
                st.download_button(
                    label="Download JSON",
                    data=json_str,
                    file_name=f"confluence_analysis_{datetime.now().strftime('%Y%m%d')}.json",
                    mime="application/json"
                )
        
        with col3:
            # Export summary report
            if st.button("Export Summary", key="export_confluence_summary"):
                summary_text = generate_confluence_summary_report(metrics)
                st.download_button(
                    label="Download Report",
                    data=summary_text,
                    file_name=f"confluence_summary_{datetime.now().strftime('%Y%m%d')}.txt",
                    mime="text/plain"
                )
        
    except Exception as e:
        logger.error(f"Error rendering confluence export options: {e}")


def render_statistical_significance_testing(trades1: List[Trade], trades2: List[Trade], 
                                          conf1: str, conf2: str) -> None:
    """Render statistical significance testing results."""
    try:
        st.subheader("📊 Statistical Significance Testing")
        
        # Get PnL data
        pnl1 = [float(t.pnl) for t in trades1 if t.pnl is not None]
        pnl2 = [float(t.pnl) for t in trades2 if t.pnl is not None]
        
        if len(pnl1) < 3 or len(pnl2) < 3:
            st.warning("Need at least 3 trades per confluence for statistical testing.")
            return
        
        # Perform statistical tests
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**T-Test Results (PnL Comparison)**")
            
            # Two-sample t-test
            t_stat, t_p_value = stats.ttest_ind(pnl1, pnl2)
            
            st.metric("T-Statistic", f"{t_stat:.4f}")
            st.metric("P-Value", f"{t_p_value:.4f}")
            
            # Interpretation
            alpha = 0.05
            if t_p_value < alpha:
                st.success(f"✅ Statistically significant difference (p < {alpha})")
            else:
                st.info(f"❌ No significant difference (p ≥ {alpha})")
        
        with col2:
            st.markdown("**Mann-Whitney U Test (Non-parametric)**")
            
            # Mann-Whitney U test (non-parametric alternative)
            u_stat, u_p_value = stats.mannwhitneyu(pnl1, pnl2, alternative='two-sided')
            
            st.metric("U-Statistic", f"{u_stat:.0f}")
            st.metric("P-Value", f"{u_p_value:.4f}")
            
            # Interpretation
            if u_p_value < alpha:
                st.success(f"✅ Statistically significant difference (p < {alpha})")
            else:
                st.info(f"❌ No significant difference (p ≥ {alpha})")
        
        # Effect size calculation
        st.markdown("**Effect Size Analysis**")
        
        col3, col4, col5 = st.columns(3)
        
        with col3:
            # Cohen's d
            pooled_std = np.sqrt(((len(pnl1) - 1) * np.var(pnl1, ddof=1) + 
                                 (len(pnl2) - 1) * np.var(pnl2, ddof=1)) / 
                                (len(pnl1) + len(pnl2) - 2))
            cohens_d = (np.mean(pnl1) - np.mean(pnl2)) / pooled_std if pooled_std > 0 else 0
            
            st.metric("Cohen's d", f"{cohens_d:.3f}")
            
            # Interpretation
            if abs(cohens_d) < 0.2:
                effect_size = "Small"
            elif abs(cohens_d) < 0.5:
                effect_size = "Medium"
            else:
                effect_size = "Large"
            
            st.caption(f"Effect size: {effect_size}")
        
        with col4:
            # Confidence interval for difference in means
            diff_mean = np.mean(pnl1) - np.mean(pnl2)
            se_diff = np.sqrt(np.var(pnl1, ddof=1)/len(pnl1) + np.var(pnl2, ddof=1)/len(pnl2))
            
            # 95% confidence interval
            ci_lower = diff_mean - 1.96 * se_diff
            ci_upper = diff_mean + 1.96 * se_diff
            
            st.metric("Mean Difference", f"${diff_mean:.2f}")
            st.caption(f"95% CI: [${ci_lower:.2f}, ${ci_upper:.2f}]")
        
        with col5:
            # Sample sizes and power
            st.metric(f"{conf1} Sample", len(pnl1))
            st.metric(f"{conf2} Sample", len(pnl2))
            
            # Basic power calculation note
            if len(pnl1) < 30 or len(pnl2) < 30:
                st.caption("⚠️ Small sample size")
            else:
                st.caption("✅ Adequate sample size")
        
    except Exception as e:
        logger.error(f"Error rendering statistical significance testing: {e}")
        st.error("Error performing statistical tests")


def render_performance_over_time_comparison(trades1: List[Trade], trades2: List[Trade], 
                                          conf1: str, conf2: str) -> None:
    """Render performance over time comparison."""
    try:
        st.subheader("📈 Performance Over Time")
        
        # Prepare time series data
        def prepare_time_series(trades, name):
            if not trades:
                return pd.DataFrame()
            
            df = pd.DataFrame([
                {
                    'date': t.exit_time.date() if t.exit_time else t.entry_time.date(),
                    'pnl': float(t.pnl) if t.pnl else 0,
                    'confluence': name
                }
                for t in trades if t.exit_time or t.entry_time
            ])
            
            if df.empty:
                return df
            
            # Sort by date and calculate cumulative PnL
            df = df.sort_values('date')
            df['cumulative_pnl'] = df['pnl'].cumsum()
            
            return df
        
        df1 = prepare_time_series(trades1, conf1)
        df2 = prepare_time_series(trades2, conf2)
        
        if df1.empty and df2.empty:
            st.warning("No time series data available for comparison.")
            return
        
        # Create time series comparison chart
        fig = go.Figure()
        
        if not df1.empty:
            fig.add_trace(go.Scatter(
                x=df1['date'],
                y=df1['cumulative_pnl'],
                mode='lines+markers',
                name=f"{conf1} Cumulative PnL",
                line=dict(color='blue', width=2),
                hovertemplate='<b>%{fullData.name}</b><br>Date: %{x}<br>Cumulative PnL: $%{y:,.2f}<extra></extra>'
            ))
        
        if not df2.empty:
            fig.add_trace(go.Scatter(
                x=df2['date'],
                y=df2['cumulative_pnl'],
                mode='lines+markers',
                name=f"{conf2} Cumulative PnL",
                line=dict(color='orange', width=2),
                hovertemplate='<b>%{fullData.name}</b><br>Date: %{x}<br>Cumulative PnL: $%{y:,.2f}<extra></extra>'
            ))
        
        fig.update_layout(
            title="Cumulative PnL Over Time Comparison",
            xaxis_title="Date",
            yaxis_title="Cumulative PnL ($)",
            height=400,
            hovermode='x unified'
        )
        
        # Add zero line
        fig.add_hline(y=0, line_dash="dash", line_color="gray", annotation_text="Break-even")
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Performance metrics over time
        col1, col2 = st.columns(2)
        
        with col1:
            if not df1.empty:
                st.markdown(f"**{conf1} Time Series Stats**")
                st.metric("First Trade", df1['date'].min().strftime('%Y-%m-%d'))
                st.metric("Last Trade", df1['date'].max().strftime('%Y-%m-%d'))
                st.metric("Final Cumulative", f"${df1['cumulative_pnl'].iloc[-1]:,.2f}")
        
        with col2:
            if not df2.empty:
                st.markdown(f"**{conf2} Time Series Stats**")
                st.metric("First Trade", df2['date'].min().strftime('%Y-%m-%d'))
                st.metric("Last Trade", df2['date'].max().strftime('%Y-%m-%d'))
                st.metric("Final Cumulative", f"${df2['cumulative_pnl'].iloc[-1]:,.2f}")
        
    except Exception as e:
        logger.error(f"Error rendering performance over time comparison: {e}")


def generate_confluence_summary_report(metrics: List[ConfluenceMetrics]) -> str:
    """Generate a text summary report of confluence analysis."""
    try:
        report_lines = [
            "CONFLUENCE ANALYSIS SUMMARY REPORT",
            "=" * 40,
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"Total Confluences Analyzed: {len(metrics)}",
            "",
            "TOP PERFORMERS BY TOTAL PnL:",
            "-" * 30
        ]
        
        # Sort by total PnL and show top 10
        top_performers = sorted(metrics, key=lambda x: x.total_pnl, reverse=True)[:10]
        
        for i, m in enumerate(top_performers, 1):
            report_lines.append(
                f"{i:2d}. {m.confluence:<20} | "
                f"Trades: {m.total_trades:3d} | "
                f"Win Rate: {m.win_rate:5.1f}% | "
                f"PnL: ${float(m.total_pnl):8,.2f}"
            )
        
        report_lines.extend([
            "",
            "HIGHEST WIN RATES:",
            "-" * 20
        ])
        
        # Sort by win rate
        best_win_rates = sorted(metrics, key=lambda x: x.win_rate, reverse=True)[:5]
        
        for i, m in enumerate(best_win_rates, 1):
            report_lines.append(
                f"{i}. {m.confluence:<20} | "
                f"Win Rate: {m.win_rate:5.1f}% | "
                f"Trades: {m.total_trades:3d}"
            )
        
        report_lines.extend([
            "",
            "SUMMARY STATISTICS:",
            "-" * 20,
            f"Total Trades Across All Confluences: {sum(m.total_trades for m in metrics)}",
            f"Total PnL Across All Confluences: ${sum(float(m.total_pnl) for m in metrics):,.2f}",
            f"Average Win Rate: {sum(m.win_rate for m in metrics) / len(metrics):.1f}%",
            "",
            "Note: Trades with multiple confluences are counted in each confluence's statistics."
        ])
        
        return "\n".join(report_lines)
        
    except Exception as e:
        logger.error(f"Error generating confluence summary report: {e}")
        return f"Error generating report: {e}"

# E
xecute the main page function directly (Streamlit multipage approach)
show_confluence_analysis_page()