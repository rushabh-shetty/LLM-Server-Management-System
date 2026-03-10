import streamlit as st
import os

@st.fragment
def render_agentic_optimizer_tab():

    # TODO: Prerequisite

    if not os.path.isfile("sections_config.xlsx") or "sections" not in st.session_state:

        c1, c2 = st.columns(2)
    
        with c1:
            if os.path.isfile("sections_config.xlsx"):
                st.success("✅ sections_config.xlsx")
            else:
                st.error("⚠️ sections_config.xlsx missing")
    
        with c2:
            if "sections" in st.session_state:
                st.success("✅ System data ready")
            else:
                st.error("⚠️ Run **Data** tab first")
        
        st.info("Fix the issues above, then come back.")
    
        return

    return
