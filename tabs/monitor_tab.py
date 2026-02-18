# monitor_tab.py
import streamlit as st
import subprocess
import time
import csv
import os
import pandas as pd
from datetime import datetime, timedelta
from data import load_sections
from ai import get_ai_threshold

def render_monitor_tab():
    st.subheader("Live System Monitoring")
    st.markdown("""
    Tracks `dynamic_single` numeric metrics from your Excel config.  
    Select metrics to monitor/log/alert on (all enabled by default), and choose which to graph live.
    """)

    # Load and prepare data
    try:
        df = load_sections()
    except Exception as e:
        st.error(f"Failed to load sections_config.xlsx: {e}")
        return

    dynamic_df = df[df["Type"] == "dynamic_single"].copy()
    if dynamic_df.empty:
        st.info("No `dynamic_single` metrics defined in Excel yet.")
        return

    # Detect interface
    iface = subprocess.getoutput(
        "ip link | grep -oP '^[0-9]+: \\K[^:]+' | grep -v lo | head -n1"
    ).strip()
    if not iface:
        iface = "unknown"

    # Prepare thresholds/units
    dynamic_df["command"] = dynamic_df["Command"].str.replace("{iface}", iface)
    dynamic_df["min_thresh"] = pd.to_numeric(dynamic_df.get("Threshold_Min", pd.Series([None]*len(dynamic_df))), errors="coerce")
    dynamic_df["max_thresh"] = pd.to_numeric(dynamic_df.get("Threshold_Max", pd.Series([None]*len(dynamic_df))), errors="coerce")
    dynamic_df["unit"] = dynamic_df.get("Unit", "").fillna("")

    # Session state
    if "monitoring_running" not in st.session_state:
        st.session_state.monitoring_running = False
    if "monitor_history" not in st.session_state:
        st.session_state.monitor_history = {}
    if "active_alerts" not in st.session_state:
        st.session_state.active_alerts = {}
    if "monitored_metrics" not in st.session_state:
        st.session_state.monitored_metrics = list(dynamic_df["Subsection_Title"])
    if "displayed_metrics" not in st.session_state:
        st.session_state.displayed_metrics = list(dynamic_df["Subsection_Title"])

    # TODO: Metrics to Monitor

    with st.expander("**📊 Metrics to Monitor** (run, log, alert — all enabled by default)", expanded=True):
        col_sel1, col_sel2 = st.columns(2)
        with col_sel1:
            if st.button("Select All", key="select_all_monitor"):
                st.session_state.monitored_metrics = list(dynamic_df["Subsection_Title"])
                for subtitle in dynamic_df["Subsection_Title"]:
                    st.session_state[f"monitor_{subtitle}"] = True
        with col_sel2:
            if st.button("Deselect All", key="deselect_all_monitor"):
                st.session_state.monitored_metrics = []
                for subtitle in dynamic_df["Subsection_Title"]:
                    st.session_state[f"monitor_{subtitle}"] = False

        groups = dynamic_df.groupby("Section_Title")
        monitored = {}
        for section, group in groups:
            with st.expander(f"**{section}** ({len(group)} metrics)", expanded=True):
                for _, row in group.iterrows():
                    subtitle = row["Subsection_Title"]
                    unit = row["unit"]
                    min_t = row["min_thresh"]
                    max_t = row["max_thresh"]
                    min_str = f"{min_t}" if pd.notna(min_t) else "—"
                    max_str = f"{max_t}" if pd.notna(max_t) else "—"
                    thresh_display = f"Min: {min_str} | Max: {max_str}"
                    if unit:
                        thresh_display += f" ({unit})"

                    default = subtitle in st.session_state.monitored_metrics
                    monitored[subtitle] = st.checkbox(
                        f"**{subtitle}** — {thresh_display}",
                        value=default,
                        key=f"monitor_{subtitle}"
                    )

        st.session_state.monitored_metrics = [k for k, v in monitored.items() if v]

    ## TODO: AI Assistant
    with st.expander("🤖 AI Assistant for Threshold Recommendations", expanded=False):

        get_ai_threshold()

    # TODO: Monitoring Controls

    st.markdown("### ▶️ Monitoring Controls")

    ## TODO: Live Graph Display Selection

    if st.session_state.monitored_metrics:

        with st.expander("**📈 Live Graph Display** (choose which monitored metrics to visualize live)", expanded=True):
            col_disp1, col_disp2 = st.columns(2)
            with col_disp1:
                if st.button("Show All Monitored", key="show_all_graphs"):
                    st.session_state.displayed_metrics = st.session_state.monitored_metrics[:]
                    for subtitle in st.session_state.monitored_metrics:
                        st.session_state[f"display_{subtitle}"] = True
            with col_disp2:
                if st.button("Hide All Graphs", key="hide_all_graphs"):
                    st.session_state.displayed_metrics = []
                    for subtitle in st.session_state.monitored_metrics:
                        st.session_state[f"display_{subtitle}"] = False

            displayed = {}
            for subtitle in st.session_state.monitored_metrics:
                default = subtitle in st.session_state.displayed_metrics
                displayed[subtitle] = st.checkbox(
                    f"Graph **{subtitle}** live",
                    value=default,
                    key=f"display_{subtitle}"
                )

            st.session_state.displayed_metrics = [k for k, v in displayed.items() if v]

    ## TODO: FILTER

    interval = st.selectbox("Update interval", [10, 30, 60, 300], index=2, format_func=lambda x: f"{x} seconds")

    col_ctrl1, col_ctrl2 = st.columns([1, 1])

    with col_ctrl1:
        start_label = "Start Monitoring" if not st.session_state.monitoring_running else "Pause Monitoring"
        if st.button(start_label, type="primary", width="stretch"):
            st.session_state.monitoring_running = not st.session_state.monitoring_running
    with col_ctrl2:
        if st.button("Stop & Clear Live Graphs", type="secondary", width="stretch"):
            st.session_state.monitoring_running = False
            st.session_state.monitor_history = {}
            st.session_state.active_alerts = {}

    if not st.session_state.monitored_metrics:
        st.warning("⚠️ Select at least one metric in 'Metrics to Monitor' to start.")
        st.stop()

    ## TODO: Live Monitoring Fragment
    @st.fragment
    def live_monitoring():

        placeholder = st.empty()

        while st.session_state.monitoring_running:
            with placeholder.container():
                now = datetime.now()
                current_values = {}

                for subtitle in st.session_state.monitored_metrics:
                    row = dynamic_df[dynamic_df["Subsection_Title"] == subtitle].iloc[0]
                    cmd = row["command"]

                    try:
                        output = subprocess.check_output(cmd, shell=True, text=True, stderr=subprocess.STDOUT).strip()
                        value = float(output) if output else float("nan")
                    except Exception:
                        value = float("nan")

                    current_values[subtitle] = value

                    # Breach check (thresholds optional)
                    breached = False
                    if pd.notna(value):
                        if pd.notna(row["min_thresh"]) and value < row["min_thresh"]:
                            breached = True
                        if pd.notna(row["max_thresh"]) and value > row["max_thresh"]:
                            breached = True

                    if breached:
                        if subtitle not in st.session_state.active_alerts:
                            st.session_state.active_alerts[subtitle] = (value, now)
                    else:
                        st.session_state.active_alerts.pop(subtitle, None)

                    # Pruned in-memory history
                    if subtitle not in st.session_state.monitor_history:
                        st.session_state.monitor_history[subtitle] = []
                    st.session_state.monitor_history[subtitle].append((now, value))
                    if len(st.session_state.monitor_history[subtitle]) > 1000:
                        st.session_state.monitor_history[subtitle] = st.session_state.monitor_history[subtitle][-1000:]

                    # Persistent CSV append
                    csv_file = "monitoring_history.csv"
                    row_data = {
                        "timestamp": now.isoformat(),
                        "metric": subtitle,
                        "value": value if pd.notna(value) else "",
                        "unit": row["unit"]
                    }
                    file_exists = os.path.isfile(csv_file)
                    with open(csv_file, "a", newline="") as f:
                        writer = csv.DictWriter(f, fieldnames=["timestamp", "metric", "value", "unit"])
                        if not file_exists:
                            writer.writeheader()
                        writer.writerow(row_data)

                # Current values table
                st.markdown("#### 📋 Current Values")
                table_data = []
                for subtitle in st.session_state.monitored_metrics:
                    value = current_values.get(subtitle, float("nan"))
                    row = dynamic_df[dynamic_df["Subsection_Title"] == subtitle].iloc[0]
                    status = "❌" if subtitle in st.session_state.active_alerts else "✅"
                    table_data.append({
                        "Metric": subtitle,
                        "Value": f"{value:.4f}" if pd.notna(value) else "N/A",
                        "Unit": row["unit"],
                        "Min": row["min_thresh"] if pd.notna(row["min_thresh"]) else "—",
                        "Max": row["max_thresh"] if pd.notna(row["max_thresh"]) else "—",
                        "Status": status
                    })
                st.dataframe(table_data, width="stretch", hide_index=True)

                # Alerts
                st.markdown("#### ⚠️ Active Threshold Breaches")
                if st.session_state.active_alerts:
                    st.error("One or more metrics are outside thresholds")
                    for sub, (val, since) in st.session_state.active_alerts.items():
                        st.write(f"• **{sub}**: {val:.4f} (since {since.strftime('%H:%M:%S')})")
                else:
                    st.success("✅ All monitored metrics within thresholds")

                # Live graphs
                if st.session_state.displayed_metrics:
                    st.markdown("#### 📈 Live Trends (last ~1000 points)")
                    for subtitle in st.session_state.displayed_metrics:
                        if subtitle not in st.session_state.monitored_metrics:
                            continue
                        history = st.session_state.monitor_history.get(subtitle, [])
                        if history:
                            chart_df = pd.DataFrame(history, columns=["Time", "Value"])
                            st.subheader(subtitle)
                            st.line_chart(chart_df.set_index("Time")["Value"], width="stretch")

            time.sleep(interval)

        # Paused state
        if st.session_state.monitored_metrics:
            st.info("Monitoring paused — live graphs frozen, full history preserved in CSV.")

    live_monitoring()

    # TODO: History Download

    csv_file = "monitoring_history.csv"

    if os.path.isfile(csv_file):
        with open(csv_file, "rb") as f:
            st.download_button(
                "💾 Download Full History CSV",
                data=f,
                file_name="monitoring_history.csv",
                mime="text/csv",
                width="stretch"
            )