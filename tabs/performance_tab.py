import streamlit as st
import os
from datetime import datetime
import pandas as pd

from data import get_available_hft_profiles, load_sections, build_system_profile, load_dynamic_df, take_ai_snapshot
from ai import perform_hft_analysis

def render_performance_tab():

    st.subheader("Performance Optimizer")

    st.markdown("Choose profile → Preview context → Run → Select recommendations → Generate script.")

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


    profiles = get_available_hft_profiles()
    selected_profile = st.selectbox("Select HFT Profile", profiles, index=0)

    # TODO: Call AI

    perform_hft_analysis(selected_profile)

    # TODO: Formatting Results

    if "last_analysis" in st.session_state:
        last = st.session_state.last_analysis
        st.success(f"**{last['profile']}** — {last['timestamp']}")

        if last.get("analysis_md"):
            with st.expander("📋 Full Analysis Report", expanded=True):
                st.markdown(last["analysis_md"])
        else:
            st.warning("Analysis incomplete — showing raw below")
            st.markdown(last.get("analysis_md", "No output from Ollama."))

        st.subheader("🔧 Recommendations")
        if "selected_recs" not in st.session_state:
            st.session_state.selected_recs = []

        for rec in last["recommendations"]:
            with st.expander(f"{rec.get('title', 'Recommendation')} — {rec.get('impact', '')}", expanded=False):
                risk_map = {"low": "🟢 Low", "medium": "🟡 Medium", "high": "🔴 High"}
                st.markdown(f"**Risk:** {risk_map.get(rec.get('risk'), '🟡 Medium')}")
                st.markdown(f"**Why it matters for HFT:** {rec.get('why_hft', '—')}")
                st.markdown(rec.get("description", "No description."))
                if rec.get("risk") == "high":
                    st.error("⚠️ HIGH RISK")
                st.code("\n".join(rec.get("commands", [])), language="bash")
                include = st.checkbox("Include in script", value=rec.get("risk") != "high", key=f"chk_{rec.get('id', 'unknown')}")
                if include and rec.get("id") not in st.session_state.selected_recs:
                    st.session_state.selected_recs.append(rec.get("id"))
                elif not include and rec.get("id") in st.session_state.selected_recs:
                    st.session_state.selected_recs.remove(rec.get("id"))

        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("Select All", width='stretch', key="select_all_perf"):
                st.session_state.selected_recs = [r.get("id") for r in last["recommendations"] if r.get("id")]
                st.rerun()
        with col2:
            if st.button("Deselect All", width='stretch', key="deselect_all_perf"):
                st.session_state.selected_recs = []
                st.rerun()
        with col3:
            if st.button("📥 Generate files", type="primary", width='stretch', key="generate_files_perf"):
                generate_tuning_files(last)

# TODO: Tunning file

def generate_tuning_files(last):
    selected = [r for r in last["recommendations"] if r.get("id") in st.session_state.get("selected_recs", [])]
    if not selected:
        st.warning("Select at least one recommendation")
        return

    script_lines = [
        "#!/bin/bash",
        f"# HFT Tuning Script — {last['profile']} — Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        'echo -e "\\033[1;36m=== HFT Performance Tuning ===\\033[0m"'
    ]
    for rec in selected:
        script_lines.append(f'echo -e "\\033[1;33m=== {rec.get("title", "")} ===\\033[0m"')
        script_lines.append(f'echo "{rec.get("description", "")}"')
        script_lines.append('read -p "Apply this recommendation? (y/N): " ans')
        script_lines.append('if [[ $ans =~ ^[Yy]$ ]]; then')
        for cmd in rec.get("commands", []):
            script_lines.append(f"    {cmd}")
        script_lines.append('    echo -e "\\033[32m✅ Applied\\033[0m"')
        script_lines.append('else')
        script_lines.append('    echo -e "\\033[33m⏭️ Skipped\\033[0m"')
        script_lines.append('fi')

    script_content = "\n".join(script_lines)
    report_md = f"# Performance Report — {last['profile']}\n\n{last.get('analysis_md', 'No analysis generated')}"

    col_d1, col_d2 = st.columns(2)
    with col_d1:
        st.download_button("⬇️ Download tune_system.sh", script_content, "tune_system.sh", "text/x-shellscript", key="download_sh")
    with col_d2:
        st.download_button("⬇️ Download performance_report.md", report_md, "performance_report.md", "text/markdown", key="download_md")
    st.success("✅ Files generated!")