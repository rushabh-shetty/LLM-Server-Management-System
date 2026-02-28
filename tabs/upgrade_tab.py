import streamlit as st
from datetime import datetime
import pandas as pd
import os

from data import load_sections, get_available_hft_profiles, build_system_profile, build_full_raw_text, load_dynamic_df, take_ai_snapshot
from ai import perform_upgrade_analysis, render_ai_chat

def render_upgrade_tab():
    st.subheader("Upgrade")
    st.markdown("Hardware and configuration recommendations for your HFT system.")

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
    display_options = [p if p != "All Sections" else "General Overview" for p in profiles]

    focus_display = st.multiselect(
        "Upgrade Focus Area (select one or more)",
        display_options,
        default=[],
        placeholder="Select categories..."
    )

    budget = st.number_input(
        "Maximum Budget (USD) — leave 0 for no limit",
        min_value=0,
        value=0,
        step=100,
        format="%d"
    )

    if focus_display:
        with st.expander("📋 Preview what will be sent to AI", expanded=True):
            focus_keys = ["All Sections" if x == "General Overview" else x for x in focus_display]
            focused_sections = {}
            for key in focus_keys:
                if key == "All Sections":
                    focused_sections.update(st.session_state.sections)
                else:
                    df = load_sections()
                    profile_titles = df[df["HFT_Profile"] == key]["Section_Title"].unique().tolist()
                    for t in profile_titles:
                        if t in st.session_state.sections:
                            focused_sections[t] = st.session_state.sections[t]

            st.markdown("**Hardware Summary**")
            st.code(build_system_profile(st.session_state.sections), language=None)

            st.markdown("**Focused sections**")
            st.code(build_full_raw_text(focused_sections), language=None)

            dynamic_df = load_dynamic_df()
            monitored = [sub for subs in focused_sections.values() for sub in subs]
            snapshot = take_ai_snapshot(dynamic_df, monitored) if monitored else {}
            if snapshot:
                st.markdown("**Current dynamic values**")
                st.dataframe(pd.DataFrame(list(snapshot.items()), columns=["Metric", "Value"]), 
                             width='stretch', hide_index=True)

    run_disabled = len(focus_display) == 0 or "sections" not in st.session_state
    if st.button("Run Upgrade Analysis", type="primary", disabled=run_disabled, width='stretch'):
        focus_keys = ["All Sections" if x == "General Overview" else x for x in focus_display]
        with st.status("Running upgrade analysis...", expanded=True) as status:
            status.update(label="Asking Ollama...", state="running")
            
            # NEW CLEAN CALL — only 3 return values
            analysis, recommendations, full_raw = perform_upgrade_analysis(
                focus_keys, budget if budget > 0 else None
            )
            
            status.update(label="✅ Done!", state="complete")

        # UPDATED session_state — NO full_response anymore
        st.session_state.last_upgrade = {
            "focus_display": focus_display,
            "focus_key": focus_keys,
            "budget": budget if budget > 0 else None,
            "analysis": analysis,          # ← this is the ONLY place we store the AI output
            "recommendations": recommendations,
            "full_raw": full_raw,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M")
        }
        st.rerun()

    # ==================== DISPLAY SECTION ====================
    if "last_upgrade" in st.session_state:
        last = st.session_state.last_upgrade
        st.success(f"**{', '.join(last['focus_display'])}** — {last['timestamp']}")

        col_a, col_b = st.columns([3, 1])
        with col_a:
            st.markdown("### System Summary")
            st.code(build_system_profile(st.session_state.sections), language=None)
        with col_b:
            if last["budget"]:
                st.metric("Budget", f"${last['budget']:,}")

        # Analysis expander — uses last["analysis"]
        with st.expander("Analysis", expanded=True):
            st.markdown(last["analysis"])

        # Raw AI output — now also uses last["analysis"] (clean & consistent)
        st.subheader("Raw AI Recommendations")
        st.markdown(last["analysis"])

        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("Regenerate", width='stretch'):
                st.session_state.pop("last_upgrade", None)
                st.rerun()
        with col3:
            report_text = last["analysis"]   # ← changed here too
            st.download_button(
                "💾 Download upgrade_report.txt",
                report_text,
                file_name="upgrade_report.txt",
                mime="text/plain",
                width='stretch'
            )

        st.divider()
        st.markdown("### 💬 Ask about the recommendations")
        qa_prompt = f"""You are an expert HFT upgrade advisor.

Previous full response:
{last['analysis']}

Full hardware context:
{build_system_profile(st.session_state.sections)}

Answer conversationally and help the user decide on upgrades."""
        render_ai_chat(
            qa_prompt,
            welcome_message="Ask anything about the recommendations or alternatives!",
            input_placeholder="Is this CPU upgrade worth it?",
            clear_key="upgrade_clear_ai_chat"
        )

    else:
        st.info("Select one or more focus areas and budget, then click **Run Upgrade Analysis**.")