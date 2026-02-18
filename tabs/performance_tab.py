import streamlit as st
import os
from datetime import datetime
import pandas as pd

from data import get_available_hft_profiles, load_sections
from ai import perform_hft_analysis, build_system_profile, load_dynamic_df, take_ai_snapshot

def render_performance_tab():
    st.subheader("⚡ HFT Performance Optimizer")
    st.markdown("Choose profile → Preview context → Run → Select recommendations → Generate script.")

    # Status
    c1, c2 = st.columns(2)
    with c1:
        st.success("✅ sections_config.xlsx") if os.path.isfile("sections_config.xlsx") else st.error("❌ sections_config.xlsx missing")
    with c2:
        st.success("✅ System data ready") if "sections" in st.session_state else st.warning("Run Data tab first")

    profiles = get_available_hft_profiles()
    selected_profile = st.selectbox("Select HFT Profile", profiles, index=0)

    # === LIVE PREVIEW ===
    with st.expander("📋 Preview what will be sent to Ollama", expanded=True):
        if "sections" not in st.session_state:
            st.info("Run Data tab first")
        else:
            all_sections = st.session_state.sections
            if selected_profile == "All Sections":
                preview_sections = all_sections
            else:
                df = load_sections()
                profile_titles = df[df["HFT_Profile"] == selected_profile]["Section_Title"].unique()
                preview_sections = {k: v for k, v in all_sections.items() if k in profile_titles}

            st.markdown("**Hardware Summary**")
            st.code(build_system_profile(preview_sections) if preview_sections else "—")

            st.markdown("**Full sections for this profile**")
            preview_text = ""
            for title, subs in preview_sections.items():
                preview_text += f"\n=== {title} ===\n"
                for subtitle, data in subs.items():
                    cmd = data.get("command", "")
                    out = data.get("output", "").strip() or "(no output yet)"
                    preview_text += f"--- {subtitle} ---\n{cmd}\n{out}\n"
            st.code(preview_text.strip() or "No sections", language=None)

            dynamic_df = load_dynamic_df()
            monitored = [sub for subs in preview_sections.values() for sub in subs]
            snapshot = take_ai_snapshot(dynamic_df, monitored) if monitored else {}
            if snapshot:
                st.markdown("**Dynamic values**")
                st.dataframe(pd.DataFrame(list(snapshot.items()), columns=["Metric", "Value"]), 
                             use_container_width=True, hide_index=True)

    # Run button
    if st.button("🚀 Run Performance Analysis", type="primary", use_container_width=True):
        with st.status("Running analysis...", expanded=True) as status:
            status.update(label="Asking Ollama...", state="running")
            analysis_md, recommendations, context_for_ui = perform_hft_analysis(selected_profile)
            status.update(label="✅ Done!", state="complete")

        st.session_state.last_analysis = {
            "profile": selected_profile,
            "analysis_md": analysis_md,
            "recommendations": recommendations,
            "context_for_ui": context_for_ui,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M")
        }
        st.rerun()

    # Results
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
            if st.button("Select All", use_container_width=True, key="select_all_perf"):
                st.session_state.selected_recs = [r.get("id") for r in last["recommendations"] if r.get("id")]
                st.rerun()
        with col2:
            if st.button("Deselect All", use_container_width=True, key="deselect_all_perf"):
                st.session_state.selected_recs = []
                st.rerun()
        with col3:
            if st.button("📥 Generate files", type="primary", use_container_width=True, key="generate_files_perf"):
                generate_tuning_files(last)

        # Post-run context
        with st.expander("📋 What was sent to Ollama (last run)", expanded=False):
            ctx = last["context_for_ui"]
            st.markdown("**Hardware Summary**")
            st.code(ctx["short_summary"])
            st.markdown("**Full sections for this profile**")
            st.code(ctx["full_profile_data"], language=None)
            if ctx.get("dynamic_snapshot"):
                st.markdown("**Dynamic values**")
                st.dataframe(pd.DataFrame(list(ctx["dynamic_snapshot"].items()), columns=["Metric", "Value"]), 
                             use_container_width=True, hide_index=True)

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