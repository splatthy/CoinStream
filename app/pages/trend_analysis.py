"""
Trend Analysis page for displaying PnL trends and performance over time.
"""

import io
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from app.models.trade import Trade
from app.services.analysis_service import AnalysisService, PnLDataPoint
from app.services.data_service import DataService
from app.utils.notifications import get_notification_manager
from app.utils.state_management import get_state_manager

logger = logging.getLogger(__name__)


def show_trend_analysis_page() -> None:
    """Display the Trend Analysis page with PnL trends and interactive charts."""
    st.title("📈 Trend Analysis")

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
            st.info(
                "No trade data available. Please configure exchanges and sync data first."
            )
            return

        # Filter for closed trades with PnL data
        closed_trades = [
            trade
            for trade in trades
            if trade.status.value == "closed"
            and trade.pnl is not None
            and trade.exit_time is not None
        ]

        if not closed_trades:
            st.info("No closed trades with PnL data available for analysis.")
            return

        # Display summary metrics
        render_summary_metrics(analysis_service, closed_trades)

        # Time frame selector
        st.subheader("PnL Trend Analysis")

        col1, col2 = st.columns([1, 3])

        with col1:
            timeframe = st.selectbox(
                "Select Time Frame:",
                options=["daily", "weekly", "monthly"],
                index=0,
                key="timeframe_selector",
            )

            # Date range filter
            st.subheader("Date Range Filter")

            # Get date range from trades
            min_date = min(trade.exit_time.date() for trade in closed_trades)
            max_date = max(trade.exit_time.date() for trade in closed_trades)

            start_date = st.date_input(
                "Start Date:",
                value=min_date,
                min_value=min_date,
                max_value=max_date,
                key="start_date",
            )

            end_date = st.date_input(
                "End Date:",
                value=max_date,
                min_value=min_date,
                max_value=max_date,
                key="end_date",
            )

            # Filter trades by date range
            filtered_trades = [
                trade
                for trade in closed_trades
                if start_date <= trade.exit_time.date() <= end_date
            ]

            if not filtered_trades:
                st.warning("No trades found in the selected date range.")
                return

        with col2:
            # Generate and display PnL trend chart
            render_pnl_trend_chart(analysis_service, filtered_trades, timeframe)

        # Additional analysis sections
        st.divider()

        # Performance breakdown
        render_performance_breakdown(analysis_service, filtered_trades, timeframe)

        # Monthly/Weekly performance table
        render_performance_table(analysis_service, filtered_trades, timeframe)

    except Exception as e:
        logger.error(f"Error in trend analysis page: {e}")
        notification_manager.error(f"Error loading trend analysis: {e}")
        st.error(f"Error loading trend analysis: {e}")


def render_summary_metrics(
    analysis_service: AnalysisService, trades: List[Trade]
) -> None:
    """Render summary performance metrics."""
    try:
        summary = analysis_service.get_performance_summary(trades)

        col1, col2, col3, col4, col5 = st.columns(5)

        with col1:
            st.metric("Total Trades", summary["total_trades"])

        with col2:
            st.metric("Win Rate", f"{summary['win_rate']:.1f}%")

        with col3:
            total_pnl = float(summary["total_pnl"])
            st.metric(
                "Total PnL",
                f"${total_pnl:,.2f}",
                delta=f"${total_pnl:,.2f}" if total_pnl != 0 else None,
            )

        with col4:
            avg_pnl = float(summary["average_pnl"])
            st.metric("Avg PnL/Trade", f"${avg_pnl:,.2f}")

        with col5:
            largest_win = float(summary["largest_win"])
            st.metric("Largest Win", f"${largest_win:,.2f}")

    except Exception as e:
        logger.error(f"Error rendering summary metrics: {e}")
        st.error("Error loading summary metrics")


def render_pnl_trend_chart(
    analysis_service: AnalysisService, trades: List[Trade], timeframe: str
) -> None:
    """Render the main PnL trend chart with cumulative PnL and interactive features."""
    try:
        # Get PnL trend data
        pnl_data = analysis_service.calculate_pnl_trend(trades, timeframe)

        if not pnl_data:
            st.warning("No PnL data available for the selected timeframe.")
            return

        # Convert to DataFrame for easier plotting
        df = pd.DataFrame(
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

        # Performance optimization: limit data points for large datasets
        if len(df) > 1000:
            st.info(
                f"Large dataset detected ({len(df)} points). Showing every {len(df) // 500}th point for better performance."
            )
            step = max(1, len(df) // 500)
            df = df.iloc[::step].copy()

        # Create subplot with secondary y-axis
        fig = make_subplots(
            rows=2,
            cols=1,
            subplot_titles=(f"{timeframe.title()} PnL", "Cumulative PnL"),
            vertical_spacing=0.1,
            row_heights=[0.4, 0.6],
        )

        # Daily/Weekly/Monthly PnL bars with enhanced hover information
        colors = ["green" if pnl >= 0 else "red" for pnl in df["daily_pnl"]]

        fig.add_trace(
            go.Bar(
                x=df["date"],
                y=df["daily_pnl"],
                name=f"{timeframe.title()} PnL",
                marker_color=colors,
                hovertemplate=(
                    f"<b>%{{x|%Y-%m-%d}}</b><br>"
                    f"{timeframe.title()} PnL: <b>${{y:,.2f}}</b><br>"
                    f"Trades: <b>%{{customdata}}</b><br>"
                    f"Avg per Trade: <b>${{customdata2:,.2f}}</b><br>"
                    "<extra></extra>"
                ),
                customdata=df["trade_count"],
                customdata2=[
                    pnl / count if count > 0 else 0
                    for pnl, count in zip(df["daily_pnl"], df["trade_count"])
                ],
            ),
            row=1,
            col=1,
        )

        # Cumulative PnL line with enhanced hover information
        fig.add_trace(
            go.Scatter(
                x=df["date"],
                y=df["cumulative_pnl"],
                mode="lines+markers",
                name="Cumulative PnL",
                line=dict(color="blue", width=3),
                marker=dict(size=6),
                hovertemplate=(
                    "<b>%{x|%Y-%m-%d}</b><br>"
                    "Cumulative PnL: <b>${y:,.2f}</b><br>"
                    "Change from Previous: <b>$%{customdata:,.2f}</b><br>"
                    "<extra></extra>"
                ),
                customdata=[0]
                + [
                    curr - prev
                    for curr, prev in zip(
                        df["cumulative_pnl"][1:], df["cumulative_pnl"][:-1]
                    )
                ],
            ),
            row=2,
            col=1,
        )

        # Add zero line for cumulative PnL
        fig.add_hline(
            y=0,
            line_dash="dash",
            line_color="gray",
            row=2,
            col=1,
            annotation_text="Break-even",
            annotation_position="bottom right",
        )

        # Add trend line for cumulative PnL if enough data points
        if len(df) >= 3:
            # Simple linear trend line
            x_numeric = pd.to_numeric(df["date"])
            z = np.polyfit(x_numeric, df["cumulative_pnl"], 1)
            p = np.poly1d(z)

            fig.add_trace(
                go.Scatter(
                    x=df["date"],
                    y=p(x_numeric),
                    mode="lines",
                    name="Trend Line",
                    line=dict(color="orange", width=2, dash="dot"),
                    hovertemplate="Trend: $%{y:,.2f}<extra></extra>",
                ),
                row=2,
                col=1,
            )

        # Enhanced layout with interactive features
        fig.update_layout(
            title={
                "text": f"PnL Trend Analysis - {timeframe.title()} View",
                "x": 0.5,
                "xanchor": "center",
            },
            height=700,
            showlegend=True,
            hovermode="x unified",
            # Enable zoom and pan
            dragmode="zoom",
            # Add range selector buttons
            xaxis=dict(
                rangeselector=dict(
                    buttons=list(
                        [
                            dict(count=7, label="7D", step="day", stepmode="backward"),
                            dict(
                                count=30, label="30D", step="day", stepmode="backward"
                            ),
                            dict(count=90, label="3M", step="day", stepmode="backward"),
                            dict(
                                count=180, label="6M", step="day", stepmode="backward"
                            ),
                            dict(step="all", label="All"),
                        ]
                    )
                ),
                rangeslider=dict(visible=False),
                type="date",
            ),
            # Add modebar with custom buttons
            modebar=dict(
                add=[
                    "drawline",
                    "drawopenpath",
                    "drawclosedpath",
                    "drawcircle",
                    "drawrect",
                    "eraseshape",
                ]
            ),
        )

        # Update x-axes with better formatting
        fig.update_xaxes(title_text="Date", row=2, col=1, tickformat="%Y-%m-%d")
        fig.update_xaxes(row=1, col=1, tickformat="%Y-%m-%d")

        # Update y-axes with better formatting
        fig.update_yaxes(title_text="PnL ($)", row=1, col=1, tickformat="$,.0f")
        fig.update_yaxes(
            title_text="Cumulative PnL ($)", row=2, col=1, tickformat="$,.0f"
        )

        # Display the chart with enhanced configuration
        config = {
            "displayModeBar": True,
            "displaylogo": False,
            "modeBarButtonsToAdd": [
                "drawline",
                "drawopenpath",
                "drawclosedpath",
                "drawcircle",
                "drawrect",
                "eraseshape",
            ],
            "toImageButtonOptions": {
                "format": "png",
                "filename": f"pnl_trend_{timeframe}_{datetime.now().strftime('%Y%m%d')}",
                "height": 700,
                "width": 1200,
                "scale": 2,
            },
        }

        try:
            st.plotly_chart(fig, width="stretch", config=config)
        except TypeError:
            st.plotly_chart(fig, use_container_width=True, config=config)

        # Chart export options
        render_chart_export_options(fig, df, timeframe)

        # Display key statistics
        render_trend_statistics(df, timeframe)

    except Exception as e:
        logger.error(f"Error rendering PnL trend chart: {e}")
        st.error("Error generating PnL trend chart")


def render_trend_statistics(df: pd.DataFrame, timeframe: str) -> None:
    """Render key trend statistics below the chart."""
    try:
        if df.empty:
            return

        # Calculate statistics
        total_periods = len(df)
        profitable_periods = len(df[df["daily_pnl"] > 0])
        losing_periods = len(df[df["daily_pnl"] < 0])
        breakeven_periods = len(df[df["daily_pnl"] == 0])

        profitable_percentage = (
            (profitable_periods / total_periods * 100) if total_periods > 0 else 0
        )

        best_period = df.loc[df["daily_pnl"].idxmax()]
        worst_period = df.loc[df["daily_pnl"].idxmin()]

        final_cumulative = df["cumulative_pnl"].iloc[-1]
        max_cumulative = df["cumulative_pnl"].max()
        min_cumulative = df["cumulative_pnl"].min()

        # Display statistics in columns
        st.subheader("Trend Statistics")

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric(
                f"Profitable {timeframe.title()}s",
                f"{profitable_periods}/{total_periods}",
                f"{profitable_percentage:.1f}%",
            )

        with col2:
            st.metric(
                f"Best {timeframe.title()}",
                f"${best_period['daily_pnl']:,.2f}",
                best_period["date"].strftime("%Y-%m-%d"),
            )

        with col3:
            st.metric(
                f"Worst {timeframe.title()}",
                f"${worst_period['daily_pnl']:,.2f}",
                worst_period["date"].strftime("%Y-%m-%d"),
            )

        with col4:
            st.metric(
                "Max Drawdown",
                f"${min_cumulative:,.2f}",
                f"${min_cumulative - max_cumulative:,.2f}",
            )

    except Exception as e:
        logger.error(f"Error rendering trend statistics: {e}")


def render_performance_breakdown(
    analysis_service: AnalysisService, trades: List[Trade], timeframe: str
) -> None:
    """Render performance breakdown by different metrics with interactive features."""
    try:
        st.subheader("Performance Breakdown")

        # Get PnL data for analysis
        pnl_data = analysis_service.calculate_pnl_trend(trades, timeframe)

        if not pnl_data:
            return

        # Convert to DataFrame
        df = pd.DataFrame(
            [
                {
                    "date": point.date,
                    "pnl": float(point.daily_pnl),
                    "cumulative_pnl": float(point.cumulative_pnl),
                    "trade_count": point.trade_count,
                }
                for point in pnl_data
            ]
        )

        # Performance optimization for large datasets
        display_df = df
        if len(df) > 500:
            st.info(f"Optimizing display for {len(df)} data points...")
            step = max(1, len(df) // 250)
            display_df = df.iloc[::step].copy()

        col1, col2 = st.columns(2)

        with col1:
            # Enhanced PnL distribution histogram with statistics
            fig_hist = px.histogram(
                df,
                x="pnl",
                nbins=min(30, len(df) // 5) if len(df) > 10 else 10,
                title=f"{timeframe.title()} PnL Distribution",
                labels={"pnl": "PnL ($)", "count": "Frequency"},
                color_discrete_sequence=["lightblue"],
                marginal="box",  # Add box plot on top
            )

            # Add statistical lines
            mean_pnl = df["pnl"].mean()
            median_pnl = df["pnl"].median()

            fig_hist.add_vline(
                x=0,
                line_dash="dash",
                line_color="red",
                annotation_text="Break-even",
                annotation_position="top",
            )

            fig_hist.add_vline(
                x=mean_pnl,
                line_dash="dot",
                line_color="green",
                annotation_text=f"Mean: ${mean_pnl:.2f}",
                annotation_position="top",
            )

            fig_hist.add_vline(
                x=median_pnl,
                line_dash="dot",
                line_color="blue",
                annotation_text=f"Median: ${median_pnl:.2f}",
                annotation_position="bottom",
            )

            # Enhanced hover information
            fig_hist.update_traces(
                hovertemplate="<b>PnL Range: $%{x:.2f}</b><br>Frequency: %{y}<br><extra></extra>"
            )

            fig_hist.update_layout(height=450, showlegend=False, dragmode="zoom")

            st.plotly_chart(
                fig_hist, width="stretch", config={"displayModeBar": True}
            )

        with col2:
            # Enhanced trade count over time with moving average
            fig_trades = go.Figure()

            # Add trade count bars
            fig_trades.add_trace(
                go.Bar(
                    x=display_df["date"],
                    y=display_df["trade_count"],
                    name="Trade Count",
                    marker_color="orange",
                    hovertemplate="<b>%{x|%Y-%m-%d}</b><br>Trades: %{y}<br><extra></extra>",
                )
            )

            # Add moving average if enough data points
            if len(display_df) >= 7:
                window = min(7, len(display_df) // 3)
                moving_avg = (
                    display_df["trade_count"].rolling(window=window, center=True).mean()
                )

                fig_trades.add_trace(
                    go.Scatter(
                        x=display_df["date"],
                        y=moving_avg,
                        mode="lines",
                        name=f"{window}-Period MA",
                        line=dict(color="red", width=2),
                        hovertemplate="<b>%{x|%Y-%m-%d}</b><br>Moving Avg: %{y:.1f}<br><extra></extra>",
                    )
                )

            fig_trades.update_layout(
                title=f"Trade Count per {timeframe.title()}",
                xaxis_title="Date",
                yaxis_title="Number of Trades",
                height=450,
                hovermode="x unified",
                dragmode="zoom",
            )

            st.plotly_chart(
                fig_trades, width="stretch", config={"displayModeBar": True}
            )

        # Additional interactive analysis
        st.subheader("Interactive Analysis")

        col3, col4 = st.columns(2)

        with col3:
            # PnL vs Trade Count scatter plot
            fig_scatter = px.scatter(
                df,
                x="trade_count",
                y="pnl",
                title="PnL vs Trade Count Relationship",
                labels={"trade_count": "Number of Trades", "pnl": "PnL ($)"},
                hover_data={"date": "|%Y-%m-%d"},
                color="pnl",
                color_continuous_scale="RdYlGn",
                size="trade_count",
                size_max=15,
            )

            # Add trend line
            if len(df) > 3:
                z = np.polyfit(df["trade_count"], df["pnl"], 1)
                p = np.poly1d(z)
                x_trend = np.linspace(
                    df["trade_count"].min(), df["trade_count"].max(), 100
                )

                fig_scatter.add_trace(
                    go.Scatter(
                        x=x_trend,
                        y=p(x_trend),
                        mode="lines",
                        name="Trend Line",
                        line=dict(color="black", width=2, dash="dash"),
                        hovertemplate="Trend: $%{y:.2f}<extra></extra>",
                    )
                )

            fig_scatter.update_layout(height=400, dragmode="zoom")
            try:
                st.plotly_chart(fig_scatter, width="stretch")
            except TypeError:
                st.plotly_chart(fig_scatter, use_container_width=True)

        with col4:
            # Cumulative PnL growth rate
            if len(df) > 1:
                df_growth = df.copy()
                df_growth["pnl_growth_rate"] = (
                    df_growth["cumulative_pnl"].pct_change() * 100
                )
                df_growth = df_growth.dropna()

                if not df_growth.empty:
                    fig_growth = px.line(
                        df_growth,
                        x="date",
                        y="pnl_growth_rate",
                        title="PnL Growth Rate (%)",
                        labels={"date": "Date", "pnl_growth_rate": "Growth Rate (%)"},
                        line_shape="spline",
                    )

                    fig_growth.add_hline(
                        y=0,
                        line_dash="dash",
                        line_color="gray",
                        annotation_text="No Growth",
                    )

                    fig_growth.update_layout(height=400, dragmode="zoom")
                    try:
                        st.plotly_chart(fig_growth, width="stretch")
                    except TypeError:
                        st.plotly_chart(fig_growth, use_container_width=True)

    except Exception as e:
        logger.error(f"Error rendering performance breakdown: {e}")


def render_chart_export_options(
    fig: go.Figure, df: pd.DataFrame, timeframe: str
) -> None:
    """Render chart export options and functionality."""
    try:
        st.subheader("📥 Export Options")

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            # Export chart as HTML
            if st.button("Export Chart as HTML", key="export_html"):
                html_str = fig.to_html(include_plotlyjs="cdn")
                st.download_button(
                    label="Download HTML",
                    data=html_str,
                    file_name=f"pnl_chart_{timeframe}_{datetime.now().strftime('%Y%m%d')}.html",
                    mime="text/html",
                )

        with col2:
            # Export chart data as JSON
            if st.button("Export Chart Data", key="export_json"):
                chart_data = {
                    "timeframe": timeframe,
                    "export_date": datetime.now().isoformat(),
                    "data": df.to_dict("records"),
                }
                json_str = json.dumps(chart_data, indent=2, default=str)
                st.download_button(
                    label="Download JSON",
                    data=json_str,
                    file_name=f"pnl_data_{timeframe}_{datetime.now().strftime('%Y%m%d')}.json",
                    mime="application/json",
                )

        with col3:
            # Export as CSV
            if st.button("Export as CSV", key="export_csv"):
                csv_buffer = io.StringIO()
                df.to_csv(csv_buffer, index=False)
                st.download_button(
                    label="Download CSV",
                    data=csv_buffer.getvalue(),
                    file_name=f"pnl_data_{timeframe}_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv",
                )

        with col4:
            # Export chart configuration
            if st.button("Export Chart Config", key="export_config"):
                config_data = {
                    "chart_type": "pnl_trend",
                    "timeframe": timeframe,
                    "data_points": len(df),
                    "date_range": {
                        "start": df["date"].min().isoformat() if not df.empty else None,
                        "end": df["date"].max().isoformat() if not df.empty else None,
                    },
                    "layout": fig.layout.to_dict(),
                    "export_timestamp": datetime.now().isoformat(),
                }
                config_json = json.dumps(config_data, indent=2, default=str)
                st.download_button(
                    label="Download Config",
                    data=config_json,
                    file_name=f"chart_config_{timeframe}_{datetime.now().strftime('%Y%m%d')}.json",
                    mime="application/json",
                )

        # Performance information
        if len(df) > 100:
            st.info(
                f"💡 **Performance Tip**: Chart contains {len(df)} data points. "
                f"For better performance with large datasets, consider using a longer timeframe "
                f"or filtering to a smaller date range."
            )

    except Exception as e:
        logger.error(f"Error rendering chart export options: {e}")


def optimize_data_for_display(df: pd.DataFrame, max_points: int = 1000) -> pd.DataFrame:
    """Optimize DataFrame for display by reducing data points if necessary."""
    if len(df) <= max_points:
        return df

    # Calculate step size to reduce data points
    step = max(1, len(df) // max_points)
    return df.iloc[::step].copy()


def render_performance_table(
    analysis_service: AnalysisService, trades: List[Trade], timeframe: str
) -> None:
    """Render a detailed performance table with interactive features."""
    try:
        st.subheader(f"{timeframe.title()} Performance Table")

        # Get PnL data
        pnl_data = analysis_service.calculate_pnl_trend(trades, timeframe)

        if not pnl_data:
            return

        # Convert to DataFrame with raw numeric values for sorting/filtering
        raw_df = pd.DataFrame(
            [
                {
                    "Date": point.date,
                    "PnL": float(point.daily_pnl),
                    "Cumulative PnL": float(point.cumulative_pnl),
                    "Trades": point.trade_count,
                    "Avg PnL/Trade": float(point.daily_pnl / point.trade_count)
                    if point.trade_count > 0
                    else 0.0,
                }
                for point in pnl_data
            ]
        )

        # Add filtering options
        col1, col2, col3 = st.columns(3)

        with col1:
            # PnL filter
            pnl_filter = st.selectbox(
                "Filter by PnL:",
                options=["All", "Profitable Only", "Losing Only", "Break-even"],
                key="pnl_filter",
            )

        with col2:
            # Sort options
            sort_by = st.selectbox(
                "Sort by:",
                options=[
                    "Date (Recent First)",
                    "Date (Oldest First)",
                    "PnL (High to Low)",
                    "PnL (Low to High)",
                    "Cumulative PnL",
                    "Trade Count",
                ],
                key="sort_by",
            )

        with col3:
            # Page size
            page_size = st.selectbox(
                "Rows per page:", options=[10, 20, 50, 100], index=1, key="page_size"
            )

        # Apply filters
        filtered_df = raw_df.copy()

        if pnl_filter == "Profitable Only":
            filtered_df = filtered_df[filtered_df["PnL"] > 0]
        elif pnl_filter == "Losing Only":
            filtered_df = filtered_df[filtered_df["PnL"] < 0]
        elif pnl_filter == "Break-even":
            filtered_df = filtered_df[filtered_df["PnL"] == 0]

        # Apply sorting
        if sort_by == "Date (Recent First)":
            filtered_df = filtered_df.sort_values("Date", ascending=False)
        elif sort_by == "Date (Oldest First)":
            filtered_df = filtered_df.sort_values("Date", ascending=True)
        elif sort_by == "PnL (High to Low)":
            filtered_df = filtered_df.sort_values("PnL", ascending=False)
        elif sort_by == "PnL (Low to High)":
            filtered_df = filtered_df.sort_values("PnL", ascending=True)
        elif sort_by == "Cumulative PnL":
            filtered_df = filtered_df.sort_values("Cumulative PnL", ascending=False)
        elif sort_by == "Trade Count":
            filtered_df = filtered_df.sort_values("Trades", ascending=False)

        # Format for display
        display_df = filtered_df.copy()
        display_df["Date"] = display_df["Date"].dt.strftime("%Y-%m-%d")
        display_df["PnL"] = display_df["PnL"].apply(lambda x: f"${x:,.2f}")
        display_df["Cumulative PnL"] = display_df["Cumulative PnL"].apply(
            lambda x: f"${x:,.2f}"
        )
        display_df["Avg PnL/Trade"] = display_df["Avg PnL/Trade"].apply(
            lambda x: f"${x:,.2f}"
        )

        # Pagination
        total_rows = len(display_df)

        if total_rows == 0:
            st.warning("No data matches the selected filters.")
            return

        if total_rows > page_size:
            total_pages = (total_rows - 1) // page_size + 1
            page = st.selectbox(
                f"Page (1-{total_pages}):",
                options=list(range(1, total_pages + 1)),
                key="performance_table_page",
            )

            start_idx = (page - 1) * page_size
            end_idx = min(start_idx + page_size, total_rows)

            st.caption(
                f"Showing rows {start_idx + 1}-{end_idx} of {total_rows} filtered results"
            )
            paginated_df = display_df.iloc[start_idx:end_idx]
        else:
            paginated_df = display_df
            st.caption(f"Showing all {total_rows} results")

        # Display the table with enhanced styling
        st.dataframe(
            paginated_df,
            width="stretch",
            hide_index=True,
            column_config={
                "Date": st.column_config.DateColumn("Date"),
                "PnL": st.column_config.TextColumn("PnL"),
                "Cumulative PnL": st.column_config.TextColumn("Cumulative PnL"),
                "Trades": st.column_config.NumberColumn("Trades", format="%d"),
                "Avg PnL/Trade": st.column_config.TextColumn("Avg PnL/Trade"),
            },
        )

        # Summary statistics for filtered data
        if not filtered_df.empty:
            st.subheader("Filtered Data Summary")

            col1, col2, col3, col4 = st.columns(4)

            with col1:
                profitable_periods = len(filtered_df[filtered_df["PnL"] > 0])
                st.metric(
                    "Profitable Periods", f"{profitable_periods}/{len(filtered_df)}"
                )

            with col2:
                total_filtered_pnl = filtered_df["PnL"].sum()
                st.metric("Total PnL", f"${total_filtered_pnl:,.2f}")

            with col3:
                avg_filtered_pnl = filtered_df["PnL"].mean()
                st.metric("Average PnL", f"${avg_filtered_pnl:,.2f}")

            with col4:
                total_trades = filtered_df["Trades"].sum()
                st.metric("Total Trades", total_trades)

        # Enhanced export functionality
        st.subheader("Export Options")

        col1, col2, col3 = st.columns(3)

        with col1:
            if st.button("📥 Export Filtered Data", key="export_filtered"):
                # Use raw numeric data for export
                export_df = filtered_df.copy()
                export_df["Date"] = export_df["Date"].dt.strftime("%Y-%m-%d")

                csv = export_df.to_csv(index=False)
                st.download_button(
                    label="Download Filtered CSV",
                    data=csv,
                    file_name=f"filtered_performance_{timeframe}_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv",
                )

        with col2:
            if st.button("📥 Export All Data", key="export_all"):
                # Export all data regardless of filters
                export_df = raw_df.copy()
                export_df["Date"] = export_df["Date"].dt.strftime("%Y-%m-%d")

                csv = export_df.to_csv(index=False)
                st.download_button(
                    label="Download Complete CSV",
                    data=csv,
                    file_name=f"complete_performance_{timeframe}_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv",
                )

        with col3:
            if st.button("📊 Export Summary Stats", key="export_summary"):
                if not filtered_df.empty:
                    summary_stats = {
                        "timeframe": timeframe,
                        "filter_applied": pnl_filter,
                        "sort_order": sort_by,
                        "total_periods": len(filtered_df),
                        "profitable_periods": len(filtered_df[filtered_df["PnL"] > 0]),
                        "losing_periods": len(filtered_df[filtered_df["PnL"] < 0]),
                        "total_pnl": float(filtered_df["PnL"].sum()),
                        "average_pnl": float(filtered_df["PnL"].mean()),
                        "median_pnl": float(filtered_df["PnL"].median()),
                        "std_pnl": float(filtered_df["PnL"].std()),
                        "min_pnl": float(filtered_df["PnL"].min()),
                        "max_pnl": float(filtered_df["PnL"].max()),
                        "total_trades": int(filtered_df["Trades"].sum()),
                        "export_timestamp": datetime.now().isoformat(),
                    }

                    json_str = json.dumps(summary_stats, indent=2)
                    st.download_button(
                        label="Download Summary JSON",
                        data=json_str,
                        file_name=f"summary_stats_{timeframe}_{datetime.now().strftime('%Y%m%d')}.json",
                        mime="application/json",
                    )

    except Exception as e:
        logger.error(f"Error rendering performance table: {e}")
        st.error("Error rendering performance table")


# Execute the main page function directly (Streamlit multipage approach)
show_trend_analysis_page()
