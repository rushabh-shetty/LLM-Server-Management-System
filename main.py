import streamlit as st

from tabs.collect_data import render_collect_data

st.set_page_config(page_title="HFT System Info Collector", layout="wide")
st.title("LLM Management System")

# === Pestañas ===

tab_data, tab_2 = st.tabs(["Data", "Test"])

with tab_data:

    render_collect_data()

