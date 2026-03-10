import streamlit as st

from tabs.collect_data_tab import render_collect_data_tab
from tabs.monitor_tab import render_monitor_tab
from tabs.history_tab import render_history_tab
from tabs.performance_tab import render_performance_tab
from tabs.upgrade_tab import render_upgrade_tab
from tabs.ai_settings_tab import render_ai_settings_tab 
from ai_config import load_ai_config                  

# TODO: Read AI config

if "ai_config" not in st.session_state:
    st.session_state.ai_config = load_ai_config()

# TODO: Page Config

st.set_page_config(page_title="LLM Manager", layout="wide")

# TODO: Title

st.title("LLM Management System", text_alignment="center")

# TODO: Tabs

tab_data, tab_monitor, tab_history, tab_performance, tab_upgrade, tab_ai = st.tabs(["Data", "Monitor Data", "Trends", "Performance", "Upgrade", "AI Settings"])

with tab_data:

    render_collect_data_tab()

with tab_monitor:

    render_monitor_tab()

with tab_history:

    render_history_tab()

with tab_performance:

    render_performance_tab()

with tab_upgrade:

    render_upgrade_tab()

with tab_ai:        

    render_ai_settings_tab()
