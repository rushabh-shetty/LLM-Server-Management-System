import streamlit as st
import os
from datetime import datetime
import pandas as pd

from data import get_available_hft_profiles, detect_build_system, build_system_profile, get_redfish_groups
from ai import perform_hft_analysis, perform_compiler_analysis, render_ai_chat, perform_application_code_analysis, perform_bios_analysis

@st.fragment
def render_performance_tab():

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
    
    st.header("Performance Optimizer")

    os_config, bios, compiler, application_code, agentic_optimizer = st.tabs(["OS Config", "BIOS", "Compiler", "Application Code", "Agentic Optimizer"])

    with os_config:

        render_os_config()

    with bios:

        render_bios()

    with compiler:

        render_compiler()

    with application_code:

        render_application_code()

# TODO: SUB TAB OS Analysis

@st.fragment
def render_os_config():

    st.subheader("OS Optimizer")

    st.markdown("Choose profile → Preview context → Run → Select recommendations → Generate script.")

    # TODO: Profile Selector

    profiles = get_available_hft_profiles()
    selected_profile = st.selectbox("Select HFT Profile", profiles, index=0)

    include_redfish = False
    selected_redfish_sections = []
    if "redfish_data" in st.session_state and st.session_state.redfish_data:
        include_redfish = st.checkbox(
            "Include Redfish BMC data in OS Analysis",
            value=False,
            key="os_include_redfish"
        )
        if include_redfish:
            available = list(st.session_state.redfish_data.keys())
            selected_redfish_sections = st.multiselect(
                "Redfish sections to include",
                options=available,
                default=[],
                key="os_redfish_sections"
            )

    # TODO: Call AI

    perform_hft_analysis(selected_profile, include_redfish, selected_redfish_sections)

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
            with st.expander(f"{rec.get('title', 'Recommendation')} — {rec.get('impact', '')}", expanded=True):
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

        # TODO: Generate Files

        if st.button("📥 Generate files", type="primary", width='stretch', key="generate_files_perf"):
            generate_tuning_files(last)
        
        # TODO: Chat box

        st.divider()
        st.markdown("### 💬 Discuss these OS recommendations")

        rec_summary = "\n".join([
            f"• {r.get('title')} — {r.get('impact', '')}  \n"
            f"  Commands: {r.get('commands', [])}  \n"
            f"  Risk: {r.get('risk', 'medium')}"
            for r in last.get("recommendations", [])
        ])

        qa_prompt = f"""
        You are an expert HFT low-latency Linux tuning advisor.

        ALL RECOMMENDED OS CHANGES (use these exact items):
        {rec_summary or "No recommendations yet."}

        Full analysis:
        {last.get("analysis_md", "")}

        Hardware:
        {build_system_profile(st.session_state.sections)}

        Answer any question about order of application, risks, kernel compatibility, testing, or alternatives."""

        cfg = st.session_state.ai_config
        render_ai_chat(
            system_prompt=qa_prompt,
            welcome_message="Ask me anything about these OS tweaks — order, risks, testing, alternatives, etc.",
            input_placeholder="Should I apply the hugepages fix before or after the sysctl changes?",
            model=cfg["model"],
            temperature=cfg["temperature"],
            top_p=cfg["top_p"],
            max_tokens=cfg["max_tokens"],
            api_key=cfg.get("api_key"),
            base_url=cfg.get("base_url"),
            messages_key="os_chat_messages",
            chat_input_key="os_chat_input",
            clear_key="os_chat_clear"
        )

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

# TODO: SUB TAB BIOS

@st.fragment
def render_bios():
    st.subheader("BIOS Optimizer")
    st.markdown("Review and optimize firmware settings for ultra-low latency HFT.")

    # TODO: Local profile Selector

    profiles = get_available_hft_profiles()
    selected_profile = st.selectbox("Select HFT Profile", profiles, index=0, key="bios_profile")

    # TODO: Redfish profile Selector 

    redfish_data = None
    if "redfish_data" in st.session_state and "BIOS" in st.session_state.redfish_data:
        redfish_data = st.session_state.redfish_data["BIOS"]
        st.caption(f"✅ Redfish BIOS data ready ({redfish_data.get('total_settings', 0)} settings from {st.session_state.redfish_config.get('bmc_ip', '—')}:{st.session_state.redfish_config.get('port', '—')})")

    include_redfish = False
    if "redfish_data" in st.session_state and st.session_state.redfish_data and "BIOS" in st.session_state.redfish_data:
        include_redfish = st.checkbox(
            "Include Redfish BMC BIOS data in AI analysis",
            value=False,
            key="bios_include_redfish"
        )

    if include_redfish and redfish_data and "attributes" in redfish_data:
        groups_dict = get_redfish_groups(redfish_data["attributes"])
        available_groups = list(groups_dict.keys())

        selected_groups = st.multiselect(
            "Redfish Groups to Include",
            options=available_groups,
            default=available_groups,
            key="bios_redfish_groups"
        )
        st.session_state.bios_selected_redfish_groups = selected_groups
    else:
        st.session_state.pop("bios_selected_redfish_groups", None)

    # TODO: Call AI

    perform_bios_analysis(selected_profile)

    # TODO: Formatting Results

    if "last_bios_analysis" in st.session_state:
        last = st.session_state.last_bios_analysis
        st.success(f"**{last['profile']}** — {last['timestamp']}")

        with st.expander("📋 Full Analysis Report", expanded=True):
            st.markdown(last.get("analysis_md", "No output"))

        st.subheader("🔧 BIOS Recommendations")
        if "selected_bios_recs" not in st.session_state:
            st.session_state.selected_bios_recs = []

        for rec in last.get("recommendations", []):
            with st.expander(f"{rec.get('current_setting', 'Setting')} → {rec.get('recommended_value', '')}", expanded=True):
                st.markdown(f"**BIOS Menu Path:** {rec.get('bios_menu_path', '—')}")
                st.markdown(f"**Impact:** {rec.get('impact', '—')}")
                st.markdown(f"**Risk:** {rec.get('risk', 'medium').upper()} | **Reboot required:** {rec.get('reboot_required', 'YES')}")
                st.markdown(rec.get("description", ""))
                st.markdown(f"**Why HFT:** {rec.get('why_hft', '—')}")

                include = st.checkbox("Include in checklist", value=True, key=f"chk_bios_{rec.get('id')}")
                if include and rec.get("id") not in st.session_state.selected_bios_recs:
                    st.session_state.selected_bios_recs.append(rec.get("id"))
                elif not include and rec.get("id") in st.session_state.selected_bios_recs:
                    st.session_state.selected_bios_recs.remove(rec.get("id"))

        if st.button("📥 Generate bios_checklist.md", type="primary", width='stretch'):
            generate_bios_checklist(last)

        # TODO: Chat Box

        st.divider()
        st.markdown("### 💬 Discuss these BIOS changes")

        rec_summary = "\n".join([
            f"• {r.get('current_setting')} → {r.get('recommended_value')} ({r.get('impact', '')})"
            for r in last.get("recommendations", [])
        ])

        qa_prompt = f"""
        You are an expert HFT BIOS tuner.

        ALL RECOMMENDED CHANGES:
        {rec_summary or "No recommendations yet."}

        Full analysis:
        {last.get("analysis_md", "")}

        Hardware:
        {build_system_profile(st.session_state.sections)}

        Answer questions about order of changes, risks, testing after reboot, or alternatives."""

        cfg = st.session_state.ai_config
        render_ai_chat(
            system_prompt=qa_prompt,
            welcome_message="Ask me anything about these BIOS settings — order, risks, testing, etc.",
            input_placeholder="Should I disable C-States before or after ASPM?",
            model=cfg["model"],
            temperature=cfg["temperature"],
            top_p=cfg["top_p"],
            max_tokens=cfg["max_tokens"],
            api_key=cfg.get("api_key"),
            base_url=cfg.get("base_url"),
            messages_key="bios_chat_messages",
            chat_input_key="bios_chat_input",
            clear_key="bios_chat_clear"
        )

def generate_bios_checklist(last):
    selected = [r for r in last.get("recommendations", []) if r.get("id") in st.session_state.get("selected_bios_recs", [])]
    if not selected:
        st.warning("Select at least one recommendation")
        return

    md = f"# HFT BIOS Optimization Checklist — {last.get('profile', 'Unknown')}\n\n"
    md += f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
    for i, rec in enumerate(selected, 1):
        md += f"### {i}. {rec.get('current_setting')} → {rec.get('recommended_value')}\n"
        md += f"**Menu Path:** {rec.get('bios_menu_path')}\n"
        md += f"**Impact:** {rec.get('impact')}\n"
        md += f"**Risk:** {rec.get('risk', 'medium').upper()} | Reboot required: {rec.get('reboot_required', 'YES')}\n"
        md += f"{rec.get('description', '')}\n\n"
        md += "☐ Done\n\n---\n\n"

    st.download_button(
        "⬇️ Download bios_checklist.md",
        md,
        "bios_checklist.md",
        "text/markdown",
        use_container_width=True
    )
    st.success("✅ BIOS checklist ready!")

# TODO: SUB TAB Compiler Analysis

@st.fragment
def render_compiler():
    st.subheader("Compiler Optimizer")
    st.markdown("Scan your HFT project → AI suggests optimal compiler flags for your exact CPU.")

    # TODO: Profile selector 

    profiles = get_available_hft_profiles()
    selected_profile = st.selectbox("Select HFT Profile", profiles, index=0, key="compiler_profile")

    # TODO: Project path + Scan

    col_path, col_scan = st.columns([4, 1], vertical_alignment="bottom")
    with col_path:
        project_path = st.text_input(
            "Project folder path",
            value=os.path.expanduser("~/my_hft_bot"),
            placeholder="/home/alejandro/my_hft_bot",
            help="Full absolute path to your source code folder"
        )
    with col_scan:
        if st.button("🔍 Scan Build System", type="primary", use_container_width=True, key = "compiler_scan_button"):
            if project_path:
                build_ctx = detect_build_system(project_path)
                st.session_state.compiler_build_context = build_ctx
                if "error" in build_ctx:
                    st.error(build_ctx["error"])
                else:
                    st.success(f"✅ Detected: {build_ctx.get('build_type', 'unknown')} • {len(build_ctx['build_files'])} build files")
            else:
                st.warning("Enter a path first")

    build_ctx = st.session_state.get("compiler_build_context", {})

    # TODO: Redfish

    include_redfish = False
    selected_redfish_sections = []
    if "redfish_data" in st.session_state and st.session_state.redfish_data:
        include_redfish = st.checkbox(
            "Enhance analysis with Redfish hardware inventory",
            value=True,   # default ON for Compiler
            key="compiler_include_redfish"
        )
        if include_redfish:
            available = list(st.session_state.redfish_data.keys())
            selected_redfish_sections = st.multiselect(
                "Redfish sections to include",
                options=available,
                default=[s for s in ["Processors", "Memory", "PCIeSlots"] if s in available],
                key="compiler_redfish_sections"
            )

    # TODO: Run AI

    if build_ctx and "error" not in build_ctx and build_ctx.get("build_files"):
        perform_compiler_analysis(selected_profile, build_ctx, include_redfish, selected_redfish_sections)
    else:
        st.info("Please scan a project folder first to unlock the analysis button.")

    # TODO: Result Display

    if "last_compiler_analysis" in st.session_state:
        last = st.session_state.last_compiler_analysis
        st.success(f"**{last['profile']}** — {last['timestamp']}")

        with st.expander("📋 Full Analysis Report", expanded=True):
            st.markdown(last.get("analysis_md", "No output"))

        st.subheader("🔧 Compiler Recommendations")
        if "selected_compiler_recs" not in st.session_state:
            st.session_state.selected_compiler_recs = []

        for rec in last.get("recommendations", []):
            with st.expander(f"{rec.get('title')} — {rec.get('impact', '')}", expanded=True):
                st.markdown(f"**Current flags:** `{rec.get('current_flags', '—')}`")
                st.code(rec.get("recommended_flags", ""), language="bash")
                st.markdown(f"**Rebuild command:** `{rec.get('rebuild_command', '')}`")
                if st.button("📋 Copy build command", key=f"copy_{rec.get('id')}"):
                    st.code(rec.get("rebuild_command", ""), language=None)
                    st.toast("✅ Command copied to clipboard!")

                st.markdown(rec.get("description", ""))
                st.markdown(f"**Impact:** {rec.get('impact', '')} | **Why HFT:** {rec.get('why_hft', '')}")

                include = st.checkbox("Include in script", value=True, key=f"chk_comp_{rec.get('id')}")
                if include and rec.get("id") not in st.session_state.selected_compiler_recs:
                    st.session_state.selected_compiler_recs.append(rec.get("id"))
                elif not include and rec.get("id") in st.session_state.selected_compiler_recs:
                    st.session_state.selected_compiler_recs.remove(rec.get("id"))

        # Generate script
        if st.button("📥 Generate compiler_tune.sh", type="primary", width='stretch'):
            generate_compiler_tuning_script(last)

        # TODO: Chat Box

        st.divider()
        st.markdown("### 💬 Discuss these recommendations")

        rec_summary = "\n".join([
            f"• {r.get('title')}  \n"
            f"  Current: `{r.get('current_flags', '—')}` → Recommended: `{r.get('recommended_flags', '—')}`  \n"
            f"  Rebuild: `{r.get('rebuild_command', '—')}`  \n"
            f"  Impact: {r.get('impact', '—')}"
            for r in last.get("recommendations", [])
        ])

        qa_prompt = f"""
        You are an expert HFT compiler optimization advisor.

        ALL RECOMMENDED FLAGS (use these exact items):
        {rec_summary or "No recommendations yet."}

        Full analysis:
        {last.get("analysis_md", "")}

        Hardware:
        {build_system_profile(st.session_state.sections)}

        Be specific: explain flags, compatibility, order of application, PGO steps, alternatives, or risks."""

        cfg = st.session_state.ai_config

        render_ai_chat(
            system_prompt=qa_prompt,
            welcome_message="Ask me anything about these flags — order, risks, PGO workflow, alternatives, etc.",
            input_placeholder="Should I run PGO before or after -flto?",
            model=cfg["model"],
            temperature=cfg["temperature"],
            top_p=cfg["top_p"],
            max_tokens=cfg["max_tokens"],
            api_key=cfg.get("api_key"),
            base_url=cfg.get("base_url"),
            messages_key="compiler_chat_messages",
            chat_input_key="compiler_chat_input",
            clear_key="compiler_chat_clear"
        )

def generate_compiler_tuning_script(last):
    
    selected = [r for r in last.get("recommendations", []) if r.get("id") in st.session_state.get("selected_compiler_recs", [])]
    if not selected:
        st.warning("Select at least one recommendation")
        return

    script_lines = [
        "#!/bin/bash",
        f"# HFT Compiler Tuning Script — {last.get('profile', 'Unknown')} — Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        'echo -e "\\033[1;36m=== HFT Compiler Optimization ===\\033[0m"'
    ]
    for rec in selected:
        script_lines.append(f'echo -e "\\033[1;33m=== {rec.get("title", "")} ===\\033[0m"')
        script_lines.append(f'echo "Current → Recommended: {rec.get("current_flags", "—")} → {rec.get("recommended_flags", "—")}"')
        script_lines.append('read -p "Apply this rebuild? (y/N): " ans')
        script_lines.append('if [[ $ans =~ ^[Yy]$ ]]; then')
        script_lines.append(f'    {rec.get("rebuild_command", "echo no command")}')
        script_lines.append('    echo -e "\\033[32m✅ Applied\\033[0m"')
        script_lines.append('else')
        script_lines.append('    echo -e "\\033[33m⏭️ Skipped\\033[0m"')
        script_lines.append('fi')

    script_content = "\n".join(script_lines)

    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            "⬇️ Download compiler_tune.sh",
            script_content,
            "compiler_tune.sh",
            "text/x-shellscript",
            use_container_width=True
        )
    with col2:
        st.download_button(
            "⬇️ Download compiler_report.md",
            f"# Compiler Report — {last.get('profile')}\n\n{last.get('analysis_md', '')}",
            "compiler_report.md",
            "text/markdown",
            use_container_width=True
        )
    st.success("✅ Compiler tuning script ready!")

# TODO: SUB TAB Application code

@st.fragment
def render_application_code():
    st.subheader("Application Code Optimizer")
    st.markdown("Scan your trading source code → AI suggests line-by-line HFT latency fixes.")

    # TODO: Profile selector 

    profiles = get_available_hft_profiles()
    selected_profile = st.selectbox("Select HFT Profile", profiles, index=0, key="appcode_profile")

    # TODO: Project path + Scan

    col_path, col_scan = st.columns([4, 1], vertical_alignment="bottom")
    with col_path:
        project_path = st.text_input(
            "Project folder path",
            value=os.path.expanduser("~/test_hft_bot"),
            placeholder="/home/alejandro/my_hft_bot",
            help="Full path to your source code"
        )
    with col_scan:
        if st.button("🔍 Scan Build System", type="primary", use_container_width=True, key = "application_scan_button"):
            if project_path:
                ctx = detect_build_system(project_path)
                st.session_state.appcode_context = ctx
                if "error" in ctx:
                    st.error(ctx["error"])
                else:
                    st.success(f"✅ Scanned {len(ctx.get('hot_paths', []))} hot paths")
            else:
                st.warning("Enter a path first")

    ctx = st.session_state.get("appcode_context", {})

    # Redfish

    include_redfish = False
    selected_redfish_sections = []
    if "redfish_data" in st.session_state and st.session_state.redfish_data:
        include_redfish = st.checkbox(
            "Enhance analysis with Redfish hardware inventory",
            value=True,   # default ON
            key="appcode_include_redfish"
        )
        if include_redfish:
            available = list(st.session_state.redfish_data.keys())
            selected_redfish_sections = st.multiselect(
                "Redfish sections to include",
                options=available,
                default=[s for s in ["Processors", "Memory", "PCIeSlots"] if s in available],
                key="appcode_redfish_sections"
            )

    # TODO: Run AI

    if ctx and "error" not in ctx and ctx.get("hot_paths"):
        perform_application_code_analysis(selected_profile, ctx, include_redfish, selected_redfish_sections)
    else:
        st.info("Please scan a project folder first to unlock the analysis button.")

    # TODO: Result Display

    if "last_application_analysis" in st.session_state:
        last = st.session_state.last_application_analysis
        st.success(f"**{last['profile']}** — {last['timestamp']}")

        with st.expander("📋 Full Analysis Report", expanded=True):
            st.markdown(last.get("analysis_md", "No output"))

        st.subheader("🔧 Code Recommendations")
        if "selected_app_recs" not in st.session_state:
            st.session_state.selected_app_recs = []

        for rec in last.get("recommendations", []):
            with st.expander(f"{rec.get('file')}:{rec.get('line')} — {rec.get('impact', '')}", expanded=True):
                st.markdown(f"**Smell:** {rec.get('current_smell', '—')}")
                st.code(rec.get("suggested_patch", ""), language="diff")
                st.markdown(rec.get("description", ""))
                st.markdown(f"**Impact:** {rec.get('impact', '')} | **Why HFT:** {rec.get('why_hft', '')}")

                if st.button("📋 Copy patch", key=f"copy_patch_{rec.get('id')}"):
                    st.code(rec.get("suggested_patch", ""), language=None)
                    st.toast("✅ Patch copied!")

                include = st.checkbox("Include in script", value=True, key=f"chk_app_{rec.get('id')}")
                if include and rec.get("id") not in st.session_state.selected_app_recs:
                    st.session_state.selected_app_recs.append(rec.get("id"))
                elif not include and rec.get("id") in st.session_state.selected_app_recs:
                    st.session_state.selected_app_recs.remove(rec.get("id"))

        if st.button("📥 Generate apply_patches.sh", type="primary", width='stretch'):
            generate_apply_patches_script(last)

        # TODO: Chat Box

        st.divider()
        st.markdown("### 💬 Discuss these code changes")

        rec_summary = "\n".join([
            f"• {r.get('file')}:{r.get('line')} — {r.get('current_smell', '')} → {r.get('impact', '')}"
            for r in last.get("recommendations", [])
        ])

        qa_prompt = f"""
        You are an expert HFT source-code optimizer.

        ALL RECOMMENDED PATCHES:
        {rec_summary or "No recommendations yet."}

        Full analysis:
        {last.get("analysis_md", "")}

        Hardware:
        {build_system_profile(st.session_state.sections)}

        Answer any question about the patches, alternatives, order of application, testing strategy, or risks."""

        cfg = st.session_state.ai_config
        render_ai_chat(
            system_prompt=qa_prompt,
            welcome_message="Ask me anything about these patches — testing, risks, alternatives, etc.",
            input_placeholder="Should I apply the branch prediction fix first?",
            model=cfg["model"],
            temperature=cfg["temperature"],
            top_p=cfg["top_p"],
            max_tokens=cfg["max_tokens"],
            api_key=cfg.get("api_key"),
            base_url=cfg.get("base_url"),
            messages_key="appcode_chat_messages",
            chat_input_key="appcode_chat_input",
            clear_key="appcode_chat_clear"
        )

def generate_apply_patches_script(last):
    selected = [r for r in last.get("recommendations", []) if r.get("id") in st.session_state.get("selected_app_recs", [])]
    if not selected:
        st.warning("Select at least one patch")
        return

    script_lines = [
        "#!/bin/bash",
        f"# HFT Patch Application Script — Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        'PATCH_DIR="$HOME/hft_patches"',
        'mkdir -p "$PATCH_DIR"',
        'echo -e "\\033[1;36m=== Applying HFT Patches ===\\033[0m"'
    ]
    for i, rec in enumerate(selected, 1):
        patch_file = f"patch_{i:03d}_{rec.get('id')}.patch"
        script_lines.append(f'cat > "$PATCH_DIR/{patch_file}" << \'EOF\'')
        script_lines.append(rec.get("suggested_patch", "").replace("```diff", "").replace("```", "").strip())
        script_lines.append('EOF')
        script_lines.append(f'echo -e "\\033[1;33mPatch {i}: {rec.get("file")}:{rec.get("line")} ===\\033[0m"')
        script_lines.append('read -p "Apply this patch? (y/N): " ans')
        script_lines.append('if [[ $ans =~ ^[Yy]$ ]]; then')
        script_lines.append(f'    patch -p0 < "$PATCH_DIR/{patch_file}" && echo -e "\\033[32m✅ Applied\\033[0m"')
        script_lines.append('else')
        script_lines.append('    echo -e "\\033[33m⏭️ Skipped\\033[0m"')
        script_lines.append('fi')

    script_content = "\n".join(script_lines)

    col1, col2 = st.columns(2)
    with col1:
        st.download_button("⬇️ Download apply_patches.sh", script_content, "apply_patches.sh", "text/x-shellscript", use_container_width=True)
    with col2:
        st.download_button("⬇️ Download code_report.md", f"# Application Code Report\\n\\n{last.get('analysis_md', '')}", "code_report.md", "text/markdown", use_container_width=True)
    st.success("✅ Patch script ready! (Patches saved safely in ~/hft_patches/)")