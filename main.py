import streamlit as st

from tabs.collect_data_tab import render_collect_data_tab
from tabs.monitor_tab import render_monitor_tab
from tabs.history_tab import render_history_tab

st.set_page_config(page_title="HFT System Info Collector", layout="wide")
st.title("LLM Management System")

# === Pestañas ===

tab_data, tab_monitor, tab_history = st.tabs(["Data", "Monitor Data", "Trends"])

with tab_data:

    render_collect_data_tab()

with tab_monitor:

    render_monitor_tab()

with tab_history:

    render_history_tab()

