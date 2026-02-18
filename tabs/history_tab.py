# history_tab.py
import streamlit as st
import pandas as pd
import os
from datetime import timedelta

def render_history_tab():
    st.subheader("Historical Data Analysis")
    st.markdown("""
    View and analyze the full monitoring history collected from the Live Monitoring tab.
    """)

    csv_file = "monitoring_history.csv"

    if not os.path.isfile(csv_file):
        st.info("No monitoring history found yet. Start collecting data in the Live Monitoring tab to populate this section.")
        return

    # Load data
    try:
        hist_df = pd.read_csv(csv_file)
        hist_df["timestamp"] = pd.to_datetime(hist_df["timestamp"])
    except Exception as e:
        st.error(f"Error loading history: {e}")
        return

    if hist_df.empty:
        st.info("History file is empty — start monitoring to collect data.")
        return

    available_metrics = sorted(hist_df["metric"].unique().tolist())

    if not available_metrics:
        st.info("No metrics in history yet.")
        return

    # Metric selector
    selected = st.selectbox("Select metric for detailed historical view", available_metrics)

    metric_df = hist_df[hist_df["metric"] == selected].copy()
    if metric_df.empty:
        st.info(f"No data for metric '{selected}'.")
        return

    # Time range handling
    timestamps = metric_df["timestamp"]
    min_t = timestamps.min().to_pydatetime()
    max_t = timestamps.max().to_pydatetime()

    st.markdown(f"**{selected}** — Data points: {len(metric_df)} | Range: {min_t.strftime('%Y-%m-%d %H:%M')} to {max_t.strftime('%Y-%m-%d %H:%M')}")

    if len(metric_df) <= 1 or min_t == max_t:
        st.info("Not enough data points for time range selection — showing all available data.")
        st.line_chart(metric_df.set_index("timestamp")["value"], use_container_width=True)
    else:
        # Default to last 24 hours if history is long, otherwise full range
        default_end = max_t
        default_start = max_t - timedelta(hours=24)
        if default_start < min_t:
            default_start = min_t

        time_range = st.slider(
            "Zoom to time range",
            min_value=min_t,
            max_value=max_t,
            value=(default_start, default_end),
            format="MM/DD HH:mm",
            key=f"history_slider_{selected}"
        )

        view_df = metric_df[
            (metric_df["timestamp"] >= pd.Timestamp(time_range[0])) &
            (metric_df["timestamp"] <= pd.Timestamp(time_range[1]))
        ]

        if view_df.empty:
            st.info("No data in selected time range.")
        else:
            st.line_chart(view_df.set_index("timestamp")["value"], use_container_width=True)

            # Basic stats for the visible range
            values = view_df["value"].dropna()
            if not values.empty:
                col_stat1, col_stat2, col_stat3, col_stat4 = st.columns(4)
                with col_stat1:
                    st.metric("Min", f"{values.min():.4f}")
                with col_stat2:
                    st.metric("Max", f"{values.max():.4f}")
                with col_stat3:
                    st.metric("Average", f"{values.mean():.4f}")
                with col_stat4:
                    st.metric("Std Dev", f"{values.std():.4f}")
