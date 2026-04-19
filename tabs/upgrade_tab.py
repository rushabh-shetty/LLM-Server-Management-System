import streamlit as st
from datetime import datetime
import pandas as pd
import os

from data import get_available_hft_profiles, build_system_profile, generate_selected_report
from ai import perform_upgrade_analysis, render_ai_chat

@st.fragment
def render_upgrade_tab():

    st.header("Upgrade Advisor")

    st.markdown("Targeted hardware upgrade recommendations optimized for your HFT system and budget.")

    # TODO: Prerequisite

    if not os.path.isfile("sections_config.xlsx") or "sections" not in st.session_state:
        c1, c2 = st.columns(2)
        with c1:
            st.success("✅ sections_config.xlsx") if os.path.isfile("sections_config.xlsx") else st.error("⚠️ sections_config.xlsx missing")
        with c2:
            st.success("✅ System data ready") if "sections" in st.session_state else st.error("⚠️ Run **Data** tab first")
        st.info("Fix the issues above, then come back.")
        return

    # TODO: User inputs

    ## Profiles 

    profiles = get_available_hft_profiles()
    display_options = [p if p != "All Sections" else "General Overview" for p in profiles]
    focus_display = st.multiselect(
        "Upgrade Focus Area (one or more)",
        display_options,
        default=[],
        placeholder="Select categories to upgrade..."
    )

    ## Budget

    budget = st.number_input(
        "Maximum Budget (USD) — 0 = no limit",
        min_value=0,
        value=0,
        step=500,
        format="%d"
    )

    ## Redfish

    include_redfish = False
    selected_redfish_sections = []
    if "redfish_data" in st.session_state and st.session_state.redfish_data:
        include_redfish = st.checkbox(
            "Include Redfish BMC data in Upgrade Analysis",
            value=True,
            key="upgrade_include_redfish"
        )
        if include_redfish:
            available = list(st.session_state.redfish_data.keys())
            selected_redfish_sections = st.multiselect(
                "Redfish sections to include",
                options=available,
                default=[s for s in ["Processors", "Memory", "PCIeSlots", "BIOS"] if s in available],
                key="upgrade_redfish_sections"
            )

    # TODO: AI Call

    perform_upgrade_analysis(focus_display, budget if budget > 0 else None, include_redfish, selected_redfish_sections)

    # TODO: Parsing output

    if "last_upgrade" in st.session_state:
        last = st.session_state.last_upgrade
        st.success(f"**{', '.join(last.get('focus_display', []))}** — {last['timestamp']}")

        ## Full Analysis
        with st.expander("Full Upgrade Analysis", expanded=True):
            md = last.get("analysis_md", "No analysis was generated.")
            st.markdown(md if isinstance(md, str) else "**Parsing failed** — re-run the analysis.")

        ## RECOMMENDATIONS — checkbox inside each card
        st.subheader("🔧 Recommended Hardware Upgrades")
        recommendations = last.get("recommendations", [])

        if not recommendations:
            st.info("No recommendations generated.")
            return

        # Default: everything selected
        if "selected_upgrade_recs" not in st.session_state:
            recs = last.get("recommendations", [])
            if isinstance(recs, list):
                st.session_state.selected_upgrade_recs = {
                    rec.get("id") for rec in recs 
                    if isinstance(rec, dict) and rec.get("id")
                }
            else:
                st.session_state.selected_upgrade_recs = set()

        # Render cards with checkbox inside
        for rec in recommendations:
            if not isinstance(rec, dict):
                continue
            rec_id = rec.get("id")
            if not rec_id:
                continue

            with st.expander(
                f"{rec.get('title', 'Upgrade')} — ${rec.get('estimated_cost', 0):,} — {rec.get('impact', '')}",
                expanded=True
            ):
                # Checkbox inside the card
                include = st.checkbox(
                    "Include in my upgrade plan",
                    value=rec_id in st.session_state.selected_upgrade_recs,
                    key=f"upg_chk_{rec_id}"
                )

                cols = st.columns([3, 3])
                with cols[0]:
                    st.markdown("**Currently Installed**")
                    st.markdown(f"**{rec.get('current_part', '—')}**")
                with cols[1]:
                    st.markdown("**Recommended Replacement**")
                    st.markdown(f"**{rec.get('recommended_model', '—')}**")
                    st.markdown(rec.get("key_specs", "—"))

                st.markdown("---")
                st.markdown(f"**Estimated Street Price (2025):** ${rec.get('estimated_cost', 0):,}")
                st.markdown(f"**Expected HFT Impact:** {rec.get('impact', '—')}")
                st.markdown(f"**Why this exact model?** {rec.get('why_this_model', '—')}")
                st.markdown(rec.get("description", "No further details provided."))

                # Update selection
                if include:
                    st.session_state.selected_upgrade_recs.add(rec_id)
                else:
                    st.session_state.selected_upgrade_recs.discard(rec_id)

        # TODO: Total at the bottom
        selected_cost = sum(
            r.get("estimated_cost", 0)
            for r in recommendations
            if r.get("id") in st.session_state.selected_upgrade_recs
        )

        col_b, col_c = st.columns([1, 1])
        with col_b:
            if last.get("budget"):
                st.metric("Your Budget Limit", f"${last['budget']:,}")
        with col_c:
            st.metric(
                "Selected Total",
                f"${selected_cost:,}",
                delta=f"Over by ${selected_cost - last['budget']:,}" if last.get("budget") and selected_cost > last["budget"] else None,
                delta_color="inverse" if last.get("budget") and selected_cost > last["budget"] else "normal"
            )

        # TODO: Download
        st.divider()
        if st.button("📄 Download Report with Selected Upgrades", type="primary", use_container_width=True):
            generate_selected_report(last)

        # TODO: AI Chat

        st.divider()
        st.markdown("### 💬 Discuss these recommendations")

        ## Build clean, readable summary of ALL recommendations
        rec_summary = "\n".join([
            f"• {r.get('title')} — ${r.get('estimated_cost', 0):,}  \n"
            f"  Model: {r.get('recommended_model', '—')}  \n"
            f"  Impact: {r.get('impact', '—')}  \n"
            f"  Why: {r.get('why_this_model', '—')}"
            for r in last.get("recommendations", [])
        ])

        qa_prompt = f"""
        
        You are an expert HFT hardware upgrade advisor.

        CURRENT RECOMMENDED UPGRADES (use these exact items in every answer):
        {rec_summary or "No recommendations available yet."}

        Full analysis context:
        {last.get("analysis_md", "")}

        Current system hardware:
        {build_system_profile(st.session_state.sections)}

        Be specific, reference exact models and prices, help the user compare options, decide priorities, check compatibility, suggest alternatives, or adjust for budget."""

        ## Call AI 

        cfg = st.session_state.ai_config

        render_ai_chat(
            system_prompt=qa_prompt,
            welcome_message="Ask me anything about these upgrades — compatibility, alternatives, vendors, priorities, etc.",
            input_placeholder="Would the EPYC 9755 be better than the 9654 here?",
            model=cfg["model"],
            temperature=cfg["temperature"],
            top_p=cfg["top_p"],
            max_tokens=cfg["max_tokens"],
            api_key=cfg.get("api_key"),
            base_url=cfg.get("base_url"),
            messages_key="upgrade_chat_messages",
            chat_input_key="upgrade_chat_input",
            clear_key="upgrade_chat_clear"
        )