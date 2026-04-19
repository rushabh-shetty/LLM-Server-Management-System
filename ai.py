import streamlit as st
import ollama
import pandas as pd
import json
import re
from datetime import datetime
from litellm import completion

from data import load_sections, load_dynamic_df, build_system_profile, take_ai_snapshot, build_full_raw_text, get_bios_context, get_redfish_groups, build_redfish_context, count_tokens

# TODO: Generic AI calls

def render_ai_chat(
    system_prompt,
    welcome_message="Hi! How can I help you today?",
    input_placeholder="Type your message...",
    model="ollama/llama3.1:8b",
    temperature=0.7,
    top_p=0.9,
    max_tokens=8000,
    clear_key="clear_ai_chat",
    messages_key="ai_messages",       
    chat_input_key="universal_chat_input", 
    api_key=None,
    base_url=None,
):
    "Universal chat works for multiple ai's, pending to test using grok"

    # Use the custom messages key for session state
    if messages_key not in st.session_state:
        st.session_state[messages_key] = []

    # Show chat history
    for msg in st.session_state[messages_key]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Welcome message (only once per chat)
    if not st.session_state[messages_key]:
        with st.chat_message("assistant"):
            st.markdown(welcome_message)
        st.session_state[messages_key].append({"role": "assistant", "content": welcome_message})

    # Input at the bottom + Clear button
    col_input, col_clear = st.columns([8, 1.2])

    with col_input:
        prompt = st.chat_input(
            placeholder=input_placeholder,
            key=chat_input_key,       
        )

    with col_clear:
        if st.button("🗑️ Clear", key=clear_key, use_container_width=True):
            st.session_state[messages_key] = []
            st.rerun()

    # Process new message
    if prompt:
        st.session_state[messages_key].append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        messages = [
            {"role": "system", "content": system_prompt},
            *st.session_state[messages_key]
        ]

        with st.chat_message("assistant"):
            try:
                response = completion(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    top_p=top_p,
                    max_tokens=max_tokens,
                    stream=True,
                    api_key=api_key,
                    api_base=base_url,
                )

                placeholder = st.empty()
                full_response = ""

                for chunk in response:
                    content = getattr(chunk.choices[0].delta, "content", None) or ""
                    if content:
                        full_response += content
                        placeholder.markdown(full_response + "▌")

                placeholder.markdown(full_response)

                st.session_state[messages_key].append(
                    {"role": "assistant", "content": full_response}
                )

            except Exception as e:
                error_msg = f"**Error with {model}**: {str(e)}\nMake sure it is running."
                st.error(error_msg)
                st.session_state[messages_key].append({"role": "assistant", "content": error_msg})

def render_structured_ai_task(
    context,
    system_prompt,
    result_key = "last_analysis",
    task_name = "Performance Analysis",
    model = "ollama/llama3.1:8b",  
    temperature = 0.1,
    top_p = 0.9,
    max_tokens = 8000,
    api_key = None,
    api_base = None,            
    force_json_user_message = "Generate the JSON analysis and recommendations NOW. Output ONLY the JSON object."
):

    with st.status(f"Running {task_name}...", expanded=True) as status:
        status.update(label=f"Asking {model}...", state="running")

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": force_json_user_message}
        ]

        try:
            response = completion(
                model=model,
                messages=messages,
                temperature=temperature,
                top_p=top_p,
                max_tokens=max_tokens,
                stream=True,
                api_key=api_key,
                api_base=api_base,
            )

            full_response = ""
            placeholder = st.empty()
            for chunk in response:
                content = getattr(chunk.choices[0].delta, "content", None) or ""
                if content:
                    full_response += content
                    placeholder.markdown(full_response + "▌")

            placeholder.empty()
            status.update(label="✅ Response received — parsing...", state="complete")

            # TODO: JSON Parsing

            full_response = full_response.strip()
            try:
                data = json.loads(full_response)
            except:
                data = None

            if not data:
                json_match = re.search(r'(\{[\s\S]*\})', full_response, re.DOTALL)
                if json_match:
                    try:
                        data = json.loads(json_match.group(1))
                    except:
                        data = None

            if data and isinstance(data, dict):
                analysis = data.get("analysis", full_response)
                recs = data.get("recommendations", [])
            else:
                analysis = full_response
                recs = []

            if not recs and '"recommendations"' in full_response:
                try:
                    rec_match = re.search(r'"recommendations":\s*(\[[\s\S]*?\])', full_response, re.DOTALL)
                    if rec_match:
                        recs = json.loads(rec_match.group(1))
                except:
                    pass

            # TODO: Store result 

            st.session_state[result_key] = {
                "profile": context.get("selected_profile", task_name), 
                "task_name": task_name,
                "analysis_md": analysis,
                "recommendations": recs,
                "context_for_ui": context,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "model_used": model
            }

            status.update(label="✅ Done!", state="complete")
            st.rerun()

        except Exception as e:
            error_msg = f"❌ Error with {model}: {str(e)}\nMake sure `ollama serve` is running."
            st.error(error_msg)
            st.session_state[result_key] = {"error": error_msg}  # safe fallback

# TODO: AI Threshold

def get_ai_threshold():

    # TODO: Load dynamic_single metrics

    dynamic_df = load_dynamic_df()
    monitored_metrics = st.session_state.get("monitored_metrics", [])

    # TODO: Hardware profile

    if "sections" in st.session_state:
        system_profile = build_system_profile(st.session_state.sections)
    else:
        system_profile = "**⚠️ No hardware profile yet** — Go to the **Data** tab and click 'Collect System Information' first."
        st.warning(system_profile)

    # TODO: Refresh snapshot buttons

    col_refresh, col_clear, cl3 = st.columns([1,1,3])

    with col_refresh:
        if st.button("Get Snapshot for AI (better recommendations)", use_container_width=True, key="ai_refresh_snapshot", type="primary"):
            if monitored_metrics and not dynamic_df.empty:
                snapshot = take_ai_snapshot(dynamic_df, monitored_metrics)
                st.session_state.ai_snapshot = snapshot
                st.success(f"✅ Snapshot refreshed! ({len(snapshot)} metrics measured)")
                st.rerun()
            else:
                st.warning("Select at least one metric in Monitor tab first.")

    with col_clear:
        if st.button("Clear Snapshot", use_container_width=True, key="ai_clear_snapshot", type="primary"):
            st.session_state.pop("ai_snapshot", None)
            st.rerun()

    ai_snapshot = st.session_state.get("ai_snapshot", {})

    # TODO: Build monitored metrics context (inlined - simple & clean)

    context_lines = []

    for subtitle in monitored_metrics:
        row = dynamic_df[dynamic_df["Subsection_Title"] == subtitle]
        if not row.empty:
            r = row.iloc[0]
            cmd = r["Command"]
            unit = r["unit"] or "—"
            min_str = f"{r['min_thresh']:.2f}" if pd.notna(r['min_thresh']) else "not set"
            max_str = f"{r['max_thresh']:.2f}" if pd.notna(r['max_thresh']) else "not set"
            current_val = ai_snapshot.get(subtitle, "not measured yet")
            context_lines.append(
                f"- **{subtitle}**: command=`{cmd}`, unit={unit}, current={current_val}, "
                f"existing min={min_str}, max={max_str}"
            )
    metrics_context = (
        "Monitored metrics (with commands and thresholds):\n" + "\n".join(context_lines)
        if context_lines else "No metrics selected yet."
    )

    # TODO: Expander to Show context sent to AI
    
    with st.expander("Preview AI context", expanded=False):
        st.markdown("**Hardware Profile**")
        st.markdown(system_profile)
        st.markdown("**Monitored Metrics + Commands + Current Values**")
        st.code(metrics_context, language="markdown")
        if ai_snapshot:
            st.markdown("**Current Snapshot (just measured)**")
            st.json(ai_snapshot)
        st.caption("This is exactly what gets injected into the system prompt.")

    # TODO: Prompt (inlined)

    system_prompt = f"""
    
    You are an expert HFT/low-latency systems engineer specializing in safe thresholds.

    {system_profile}

    {metrics_context}

    RULES (follow strictly):
    - Always give **concrete numbers** for every metric the user mentions (or all monitored ones if they say "suggest for all").
    - Format: "For rx_queue_0_drops I recommend Min = 0, Max = 8. Reason: ..."
    - One short sentence justification only — focused on latency, packet loss, or HFT stability.
    - Be conservative and realistic based on the hardware profile and current values.
    - Never give ranges like "80-85" — always exact Min and Max.

    """

    # TODO: Threshold-specific welcome + placeholder

    welcome = ("Hi! Ask me for safe **min/max thresholds** on any monitored metric.")
    placeholder = "Ask about thresholds... (e.g. recommended max for NIC rx_queue_0_drops)"

    # TODO: Call chat

    cfg = st.session_state.ai_config
    
    render_ai_chat(
        system_prompt=system_prompt,
        welcome_message=welcome,
        input_placeholder=placeholder,
        model=cfg["model"],
        temperature=cfg["temperature"],
        top_p=cfg["top_p"],
        max_tokens=cfg["max_tokens"],
        api_key=cfg.get("api_key"),
        base_url=cfg.get("base_url"),
        messages_key="threshold_chat_messages",
        chat_input_key="threshold_chat_input",
        clear_key="threshold_clear_chat"
    )

# TODO: OS Performance analyzer

def perform_hft_analysis(selected_profile, include_redfish=False, selected_redfish_sections=None):

    if "sections" not in st.session_state:
        st.info("Run Data tab first")
        return
    
    # TODO: Context

    all_sections = st.session_state.sections

    full_hardware_summary = build_system_profile(all_sections)

    ## Profile-specific sections

    if selected_profile == "All Sections":
        profile_sections = all_sections
    else:
        df = load_sections()
        profile_titles = df[df["HFT_Profile"] == selected_profile]["Section_Title"].unique().tolist()
        profile_sections = {k: v for k, v in all_sections.items() if k in profile_titles}

    full_profile_data = build_full_raw_text(profile_sections)

    ## Dynamic snapshot
    dynamic_df = load_dynamic_df()
    monitored = [subtitle for subs in profile_sections.values() for subtitle in subs.keys()]
    dynamic_snapshot = take_ai_snapshot(dynamic_df, monitored) if monitored else {}

    context = {
        "short_summary": full_hardware_summary,     
        "full_profile_data": full_profile_data,
        "dynamic_snapshot": dynamic_snapshot,
        "selected_profile": selected_profile,
        "full_hardware_summary": full_hardware_summary 
    }

    # TODO: Contex Preview

    with st.expander("Preview AI context", expanded = False):

        st.markdown("**Full Hardware Summary** (stable base context — always sent)")
        if full_hardware_summary and full_hardware_summary.strip():
            st.markdown(full_hardware_summary)
        else:
            st.markdown("—")

        st.markdown(f"**Selected Profile: {selected_profile}**")
        st.markdown("**Detailed sections for this profile**")
        st.code(full_profile_data.strip() or "No sections", language=None)

        if dynamic_snapshot:
            st.markdown("**Dynamic values (profile-specific)**")
            st.dataframe(
                pd.DataFrame(list(dynamic_snapshot.items()), columns=["Metric", "Value"]),
                width='stretch', hide_index=True
            )

        redfish_ctx = ""

        if include_redfish and selected_redfish_sections:
            redfish_ctx = build_redfish_context(selected_redfish_sections, st.session_state.redfish_data)
            st.markdown("**Redfish BMC Data (user-selected)**")
            st.code(redfish_ctx, language=None)
    
    # Build final context + Token Control

    preview_text = f"""FULL HARDWARE SUMMARY:
    {full_hardware_summary}

    DETAILED PROFILE DATA:
    {full_profile_data}

    DYNAMIC VALUES:
    {json.dumps(dynamic_snapshot, indent=2) if dynamic_snapshot else "None"}

    {redfish_ctx if redfish_ctx else "No Redfish data included."}"""

    manual_enabled = st.checkbox("Enable manual context editing", value=False, key="os_manual_enabled")

    if manual_enabled:
        if "os_manual_context" not in st.session_state:
            st.session_state.os_manual_context = preview_text
        edited_context = st.text_area(
            "Final context sent to AI (edit freely)",
            value=st.session_state.os_manual_context,
            height=500,
            key="os_manual_text"
        )
        final_context = edited_context
    else:
        final_context = preview_text
        st.session_state.pop("os_manual_context", None)

    # Live token count
    total_tokens = count_tokens(final_context)
    st.markdown(f"**Total tokens being sent to AI:** {total_tokens}")

    if manual_enabled:
        st.session_state.final_os_context = st.session_state.get("os_manual_text", preview_text)
    else:
        st.session_state.final_os_context = preview_text

    # TODO: Run Button + AI Call

    if st.button("🚀 Run OS Analysis", type="primary", width='stretch'):

        if st.session_state.get("os_manual_enabled", False):
            final_context_for_ai = st.session_state.get("os_manual_text", preview_text)
        else:
            final_context_for_ai = preview_text

        system_prompt = f"""
        You are an expert HFT/low-latency Linux performance engineer.

        FULL CONTEXT PROVIDED BY USER (respect any manual edits the user made):
        {final_context_for_ai}

        IMPORTANT:
        - LOCAL data comes from sections_config.xlsx running on the host
        - REDFISH BMC data comes directly from the BMC (more accurate hardware inventory)

        You MUST analyze this system and output **EXACTLY** a valid JSON object.
        Do not add any explanation, markdown, or extra text before or after the JSON.
        Use this exact structure:
        
        {{
        "analysis": "=== Performance Analysis ===\\n\\nYour full markdown report here with latency/throughput details...",
        "recommendations": [
            {{
                "id": "rec-001",
                "title": "Short title",
                "description": "1-2 sentence explanation",
                "impact": "15-30% lower latency",
                "commands": ["sudo command1", "sudo command2"],
                "risk": "low",
                "why_hft": "One sentence why this helps HFT"
            }}
        ]
        }}

        Reply with ONLY the JSON. Do not add any other text.
        
        """
        cfg = st.session_state.ai_config

        render_structured_ai_task(
            context=context,
            system_prompt=system_prompt,
            result_key="last_analysis",
            task_name=f"HFT Analysis — {selected_profile}",
            model=cfg["model"],
            temperature=0.0,    # foricng 0.0 for perfect JSON (upgrade is special)
            top_p=cfg["top_p"],
            max_tokens=cfg["max_tokens"],
            api_key=cfg.get("api_key"),
            api_base=cfg.get("base_url")
        )

# TODO: BIOS performance analysis

def perform_bios_analysis(selected_profile):
    
    if "sections" not in st.session_state:
        st.info("Run Data tab first")
        return

    all_sections = st.session_state.sections
    full_hardware_summary = build_system_profile(all_sections)

    # TODO: Profile Filtering

    if selected_profile == "All Sections":
        profile_sections = all_sections
    else:
        df = load_sections()
        profile_titles = df[df["HFT_Profile"] == selected_profile]["Section_Title"].unique().tolist()
        profile_sections = {k: v for k, v in all_sections.items() if k in profile_titles}

    full_profile_data = build_full_raw_text(profile_sections)
    bios_ctx = get_bios_context(all_sections)
    bios_text = json.dumps({
        k: {sub: v["output"] for sub, v in subs.items()}
        for k, subs in bios_ctx.items()
    }, indent=2)

    # TODO: Profile Redfish context

    redfish_ctx = "None — user did not enable Redfish data"

    if ("redfish_data" in st.session_state and 
        "BIOS" in st.session_state.redfish_data and
        st.session_state.get("bios_include_redfish") and 
        st.session_state.get("bios_selected_redfish_groups")):
        
        redfish_data = st.session_state.redfish_data["BIOS"]
        
        if "attributes" in redfish_data:
            selected_groups = st.session_state.bios_selected_redfish_groups
            grouped_attrs = get_redfish_groups(redfish_data["attributes"], return_attributes=True)
            
            lines = []
            for group in selected_groups:
                if group in grouped_attrs:
                    lines.append(f"{group}:")
                    for key, value in grouped_attrs[group].items():
                        lines.append(f"  - {key}: {value}")
            redfish_ctx = "\n".join(lines) if lines else "No matching settings"

    context = {
        "short_summary": full_hardware_summary,
        "selected_profile": selected_profile,
        "full_profile_data": full_profile_data,
        "bios_context": bios_ctx,
    }

    # TODO: Preview

    with st.expander("Preview AI context", expanded=False):
        st.markdown("**Hardware Summary**")
        st.markdown(full_hardware_summary or "—")
        st.markdown(f"**Selected Profile:** {selected_profile}")
        st.markdown("**Detailed sections for this profile**")
        st.code(full_profile_data.strip() or "No sections", language=None)
        
        st.markdown("**Local BIOS & Firmware Data**")
        if bios_ctx:
            preview_df = []
            for title, subs in bios_ctx.items():
                for subtitle, data in list(subs.items())[:8]:
                    out = data.get("output", "")[:120].replace("\n", " ")
                    preview_df.append({"Section": title, "Setting": subtitle, "Current Value": out})
            st.dataframe(pd.DataFrame(preview_df), use_container_width=True, hide_index=True)
        else:
            st.code(bios_text, language="json")

        st.markdown("**Redfish BMC Data**")
        st.code(f"BIOS: {redfish_ctx}", language=None)

    # TODO: Run Button + AI Call

    if st.button("🚀 Run BIOS Analysis", type="primary", use_container_width=True):
        system_prompt = f"""

        You are an expert HFT BIOS/UEFI tuning engineer (2025 era).

        FULL HARDWARE SUMMARY:
        {full_hardware_summary}

        DETAILED PROFILE SECTIONS:
        {full_profile_data}

        CURRENT BIOS/FIRMWARE SETTINGS (LOCAL — from dmidecode/cpupower/lspci running on the OS):

        {bios_text or "None"}

        REDFISH BMC DATA:
        BIOS: {redfish_ctx}

        IMPORTANT:
        - Local data comes directly from the operating system.
        - Redfish data comes from the BMC (usually more accurate/up-to-date for firmware settings).
        - If the same setting appears in both sources and they differ, note the discrepancy and clearly state which value you recommend trusting (usually prefer Redfish).

        YOU MUST output **EXACTLY** this JSON and nothing else:

        {{
        "analysis": "=== BIOS Analysis ===\\n\\nYour full markdown report here...",
        "recommendations": [
            {{
                "id": "bios-001",
                "current_setting": "C-States: Enabled",
                "recommended_value": "C-States: Disabled",
                "bios_menu_path": "Enter BIOS → Advanced → CPU Configuration → C-States → Disabled",
                "impact": "8-25 μs lower latency per packet",
                "risk": "low",
                "reboot_required": "YES",
                "why_hft": "Eliminates CPU power-state exit latency in the critical path",
                "description": "Short explanation"
            }}
        ]
        }}

        Reply with ONLY the JSON.
        """

        cfg = st.session_state.ai_config

        render_structured_ai_task(
            context=context,
            system_prompt=system_prompt,
            result_key="last_bios_analysis",
            task_name=f"BIOS — {selected_profile}",
            model=cfg["model"],
            temperature=0.0,
            top_p=cfg["top_p"],
            max_tokens=10000,
            api_key=cfg.get("api_key"),
            api_base=cfg.get("base_url")
        )

# TODO: Compiler performace analysis 

def perform_compiler_analysis(selected_profile, build_ctx, include_redfish=False, selected_redfish_sections=None):

    if "sections" not in st.session_state:
        st.info("Run Data tab first")
        return

    all_sections = st.session_state.sections
    full_hardware_summary = build_system_profile(all_sections)

    # TODO: Profile Filtering

    if selected_profile == "All Sections":
        profile_sections = all_sections
    else:
        df = load_sections()
        profile_titles = df[df["HFT_Profile"] == selected_profile]["Section_Title"].unique().tolist()
        profile_sections = {k: v for k, v in all_sections.items() if k in profile_titles}

    full_profile_data = build_full_raw_text(profile_sections)

    build_text = json.dumps(build_ctx, indent=2) if build_ctx else "No build system scanned yet."

    context = {
        "short_summary": full_hardware_summary,
        "selected_profile": selected_profile,
        "full_profile_data": full_profile_data,
        "build_context": build_ctx,
    }

    # TODO: Preview

    with st.expander("Preview AI context", expanded=False):
        st.markdown("**Hardware Summary**")
        st.markdown(full_hardware_summary or "—")
        st.markdown(f"**Selected Profile:** {selected_profile}")
        st.markdown("**Detailed sections for this profile**")
        st.code(full_profile_data.strip() or "No sections", language=None)
        st.markdown("**Detected Build System**")
        st.code(build_text, language="json")

        # Redfish

        redfish_ctx = ""
        if include_redfish and selected_redfish_sections:
            redfish_ctx = build_redfish_context(selected_redfish_sections, st.session_state.redfish_data)
            st.markdown("**Redfish BMC Data (user-selected)**")
            st.code(redfish_ctx, language=None)

    # Build final context + Token Control

    preview_text = f"""FULL HARDWARE SUMMARY:
    {full_hardware_summary}

    DETAILED PROFILE SECTIONS:
    {full_profile_data}

    BUILD SYSTEM:
    {build_text}

    {redfish_ctx if redfish_ctx else "No Redfish data included."}"""

    manual_enabled = st.checkbox("Enable manual context editing", value=False, key="compiler_manual_enabled")

    if manual_enabled:
        if "compiler_manual_context" not in st.session_state:
            st.session_state.compiler_manual_context = preview_text
        edited_context = st.text_area(
            "Final context sent to AI (edit freely)",
            value=st.session_state.compiler_manual_context,
            height=500,
            key="compiler_manual_text"
        )
        final_context = edited_context
    else:
        final_context = preview_text
        st.session_state.pop("compiler_manual_context", None)

    # Live token count
    total_tokens = count_tokens(final_context)
    st.markdown(f"**Total tokens being sent to AI:** {total_tokens}")

    if manual_enabled:
        st.session_state.final_compiler_context = st.session_state.get("compiler_manual_text", preview_text)
    else:
        st.session_state.final_compiler_context = preview_text

    # TODO: Run Button + AI Call

    if st.button("🚀 Run Compiler Analysis", type="primary", use_container_width=True):

        # Read latest manual value inside button

        if st.session_state.get("compiler_manual_enabled", False):
            final_context_for_ai = st.session_state.get("compiler_manual_text", preview_text)
        else:
            final_context_for_ai = preview_text

        system_prompt = f"""
        You are an expert HFT compiler engineer (2025 era).

        FULL CONTEXT PROVIDED BY USER (respect any manual edits the user made):
        {final_context_for_ai}

        IMPORTANT:
        - LOCAL data comes from sections_config.xlsx running on the host
        - REDFISH BMC data comes directly from the BMC (more accurate hardware inventory)

        YOU MUST output **EXACTLY** this JSON and nothing else:

        {{
        "analysis": "=== Compiler Analysis ===\\n\\nYour full markdown report here...",
        "recommendations": [
            {{
            "id": "comp-001",
            "title": "Enable native CPU tuning",
            "current_flags": "existing flags or —",
            "recommended_flags": "-march=native -mtune=native -O3 -flto -fprofile-use",
            "rebuild_command": "make clean && make -j$(nproc) CFLAGS=\"...\"",
            "impact": "15-35% lower end-to-end latency",
            "why_hft": "Removes micro-architecture penalties and enables LTO + PGO",
            "description": "1-2 sentence explanation"
            }}
        ]
        }}

        Reply with ONLY the JSON. Do not add any other text.
        """

        cfg = st.session_state.ai_config
        render_structured_ai_task(
            context=context,
            system_prompt=system_prompt,
            result_key="last_compiler_analysis",
            task_name=f"Compiler — {selected_profile}",
            model=cfg["model"],
            temperature=0.0,
            top_p=cfg["top_p"],
            max_tokens=10000,
            api_key=cfg.get("api_key"),
            api_base=cfg.get("base_url")
        )

# TODO: Aplication code performance analysis 

def perform_application_code_analysis(selected_profile, code_context, include_redfish=False, selected_redfish_sections=None):

    if "sections" not in st.session_state:
        st.info("Run Data tab first")
        return

    all_sections = st.session_state.sections
    full_hardware_summary = build_system_profile(all_sections)

    # TODO: Profile Filtering

    if selected_profile == "All Sections":
        profile_sections = all_sections
    else:
        df = load_sections()
        profile_titles = df[df["HFT_Profile"] == selected_profile]["Section_Title"].unique().tolist()
        profile_sections = {k: v for k, v in all_sections.items() if k in profile_titles}

    full_profile_data = build_full_raw_text(profile_sections)

    code_text = json.dumps(code_context, indent=2) if code_context else "No code scanned yet."

    context = {
        "short_summary": full_hardware_summary,
        "selected_profile": selected_profile,
        "full_profile_data": full_profile_data,
        "code_context": code_context,
    }

    # TODO: Preview

    with st.expander("Preview AI context", expanded=False):
        st.markdown("**Hardware Summary**")
        st.markdown(full_hardware_summary or "—")
        st.markdown(f"**Selected Profile:** {selected_profile}")
        st.markdown("**Detailed sections for this profile**")
        st.code(full_profile_data.strip() or "No sections", language=None)
        st.markdown("**Detected Hot Paths**")
        if code_context.get("hot_paths"):
            st.dataframe(pd.DataFrame(code_context["hot_paths"]), use_container_width=True, hide_index=True)
        else:
            st.code(code_text, language="json")

        # Redfish
        redfish_ctx = ""
        if include_redfish and selected_redfish_sections:
            redfish_ctx = build_redfish_context(selected_redfish_sections, st.session_state.redfish_data)
            st.markdown("**Redfish BMC Data (user-selected)**")
            st.code(redfish_ctx, language=None)

    # Build final context + Token Control
    preview_text = f"""FULL HARDWARE SUMMARY:
    {full_hardware_summary}

    DETAILED PROFILE SECTIONS:
    {full_profile_data}

    HOT-PATH CODE:
    {code_text}

    {redfish_ctx if redfish_ctx else "No Redfish data included."}"""

    manual_enabled = st.checkbox("Enable manual context editing", value=False, key="appcode_manual_enabled")

    if manual_enabled:
        if "appcode_manual_context" not in st.session_state:
            st.session_state.appcode_manual_context = preview_text
        edited_context = st.text_area(
            "Final context sent to AI (edit freely)",
            value=st.session_state.appcode_manual_context,
            height=500,
            key="appcode_manual_text"
        )
        final_context = edited_context
    else:
        final_context = preview_text
        st.session_state.pop("appcode_manual_context", None)

    # Live token count
    total_tokens = count_tokens(final_context)
    st.markdown(f"**Total tokens being sent to AI:** {total_tokens}")

    if manual_enabled:
        st.session_state.final_appcode_context = st.session_state.get("appcode_manual_text", preview_text)
    else:
        st.session_state.final_appcode_context = preview_text

    # TODO: Run Button + AI Call

    if st.button("🚀 Run Code Analysis", type="primary", use_container_width=True):

        if st.session_state.get("appcode_manual_enabled", False):
            final_context_for_ai = st.session_state.get("appcode_manual_text", preview_text)
        else:
            final_context_for_ai = preview_text

        system_prompt = f"""
        You are an expert HFT low-latency code reviewer (2025 era).

        FULL CONTEXT PROVIDED BY USER (respect any manual edits the user made):
        {final_context_for_ai}

        IMPORTANT:
        - LOCAL data comes from sections_config.xlsx running on the host
        - REDFISH BMC data comes directly from the BMC (more accurate hardware inventory)

        YOU MUST output **EXACTLY** this JSON and nothing else:

        {{
        "analysis": "=== Application Code Analysis ===\\n\\nYour full markdown report...",
        "recommendations": [
            {{
            "id": "code-001",
            "file": "src/order_book.cpp",
            "line": 142,
            "current_smell": "Naive loop without branch prediction",
            "suggested_patch": "```diff\\n- for(auto& o : orders) ...\\n+ if (__builtin_expect(o.valid, 1)) ...\\n```",
            "impact": "18-42 μs lower per order match",
            "why_hft": "Removes branch misprediction in the hottest loop",
            "description": "Short explanation"
            }}
        ]
        }}

        Reply with ONLY the JSON. Do not add any other text.
        """

        cfg = st.session_state.ai_config
        render_structured_ai_task(
            context=context,
            system_prompt=system_prompt,
            result_key="last_application_analysis",
            task_name=f"App Code — {selected_profile}",
            model=cfg["model"],
            temperature=0.0,
            top_p=cfg["top_p"],
            max_tokens=12000,
            api_key=cfg.get("api_key"),
            api_base=cfg.get("base_url")
        )

#TODO: Upgrade AI

def perform_upgrade_analysis(focus_display: list, budget: float | None = None, include_redfish=False, selected_redfish_sections=None):

    # TODO: Sections to include

    if not focus_display or "sections" not in st.session_state:
        return

    focus_keys = ["All Sections" if x == "General Overview" else x for x in focus_display]

    all_sections = st.session_state.sections
    focused_sections = {}
    focus_names = []

    for key in focus_keys:
        if key in ("All Sections", "General Overview"):
            focused_sections.update(all_sections)
            focus_names.append("General Overview")
        else:
            df = load_sections()
            profile_titles = df[df["HFT_Profile"] == key]["Section_Title"].unique().tolist()
            for t in profile_titles:
                if t in all_sections:
                    focused_sections[t] = all_sections[t]
            focus_names.append(key)

    focus_name_str = " + ".join(set(focus_names))

    # TODO: System Context

    short_summary = build_system_profile(all_sections)
    full_profile_data = build_full_raw_text(focused_sections)
    dynamic_df = load_dynamic_df()
    monitored = [sub for subs in focused_sections.values() for sub in subs]
    dynamic_snapshot = take_ai_snapshot(dynamic_df, monitored) if monitored else {}

    context = {
        "short_summary": short_summary,
        "full_profile_data": full_profile_data,
        "dynamic_snapshot": dynamic_snapshot,
        "selected_profile": focus_name_str,
        "focus_display": focus_display,
        "budget": budget
    }

    # TODO: Preview Contex 

    with st.expander("Preview AI context", expanded=False):
        st.markdown("**Hardware Summary**")
        st.code(short_summary or "—", language=None)
        st.markdown(f"**Focus:** {focus_name_str}")
        st.markdown("**Detailed sections**")
        st.code(full_profile_data.strip() or "No data", language=None)
        if dynamic_snapshot:
            st.markdown("**Live metrics snapshot**")
            st.dataframe(pd.DataFrame(list(dynamic_snapshot.items()), columns=["Metric", "Value"]),
                         use_container_width=True, hide_index=True)
            
        # Redfish 
        redfish_ctx = ""
        if include_redfish and selected_redfish_sections:
            redfish_ctx = build_redfish_context(selected_redfish_sections, st.session_state.redfish_data)
            st.markdown("**Redfish BMC Inventory (user-selected)**")
            st.code(redfish_ctx, language=None)

        # Build final context + Token Control (outside the Preview expander)
    preview_text = f"""FULL HARDWARE SUMMARY:
    {short_summary}

    FOCUSED AREAS:
    {full_profile_data}

    LIVE VALUES:
    {json.dumps(dynamic_snapshot, indent=2) if dynamic_snapshot else "None"}

    {redfish_ctx if redfish_ctx else "No Redfish data included."}"""

    manual_enabled = st.checkbox("Enable manual context editing", value=False, key="upgrade_manual_enabled")

    if manual_enabled:
        if "upgrade_manual_context" not in st.session_state:
            st.session_state.upgrade_manual_context = preview_text
        edited_context = st.text_area(
            "Final context sent to AI (edit freely)",
            value=st.session_state.upgrade_manual_context,
            height=500,
            key="upgrade_manual_text"
        )
        final_context = edited_context
    else:
        final_context = preview_text
        st.session_state.pop("upgrade_manual_context", None)

    # Live token count
    total_tokens = count_tokens(final_context)
    st.markdown(f"**Total tokens being sent to AI:** {total_tokens}")

    if manual_enabled:
        st.session_state.final_upgrade_context = st.session_state.get("upgrade_manual_text", preview_text)
    else:
        st.session_state.final_upgrade_context = preview_text
            
    # TODO: Execute AI call

    if st.button("🚀 Run Upgrade Analysis", type="primary", use_container_width=True):
        budget_text = f"${budget:,.0f} maximum" if budget else "no budget constraint"
        budget_level = "high" if budget and budget >= 5000 else "medium" if budget else "unlimited"

        # Read latest manual value inside button

        if st.session_state.get("upgrade_manual_enabled", False):
            final_context_for_ai = st.session_state.get("upgrade_manual_text", preview_text)
        else:
            final_context_for_ai = preview_text

        system_prompt = f"""
        You are a senior HFT hardware engineer (2025 era).

        FULL CONTEXT PROVIDED BY USER (respect any manual edits the user made):
        {final_context_for_ai}

        IMPORTANT:
        - LOCAL data comes from sections_config.xlsx running on the host
        - REDFISH BMC data comes directly from the BMC (more accurate hardware inventory)

        Budget: {budget_text} ({budget_level}-level budget)

        YOU MUST SCALE RECOMMENDATIONS TO THE BUDGET:
        - If budget is $5,000+, always recommend premium/high-end 2025 parts that deliver maximum HFT performance (enterprise SSDs, high-capacity low-latency RAM, latest-gen CPUs, BlueField-3 DPUs, PCIe Gen5 cards, etc.).
        - Never default to cheap consumer parts when the user has a large budget — use the money to buy the best realistic upgrade possible.

        COMPATIBILITY RULE (MANDATORY):
        Every single recommendation MUST be 100% compatible with the current motherboard chipset, CPU socket, PCIe version/slots, RAM type/speed, and form factors shown in the full hardware summary. If something would require a motherboard swap, say so explicitly and justify it.

        YOU MUST REPLY WITH **NOTHING BUT** A VALID JSON OBJECT. No explanations, no markdown, no extra text.

        Output exactly this structure:

        {{
        "analysis": "Full markdown analysis...",
        "recommendations": [
            {{
            "id": "rec-001",
            "title": "...",
            "current_part": "...",
            "recommended_model": "Exact model + part number",
            "key_specs": "Key specs that matter for HFT",
            "estimated_cost": 2290,
            "impact": "25-40% lower latency...",
            "why_this_model": "Why this exact model is perfect for the current system + budget",
            "description": "1-2 sentence explanation"
            }}
        ]
        }}

        Reply with ONLY the JSON. Do not add any other text."""

        cfg = st.session_state.ai_config

        render_structured_ai_task(
            context=context,
            system_prompt=system_prompt,
            result_key="last_upgrade",
            task_name=f"Upgrade — {focus_name_str}",
            model=cfg["model"],
            temperature=0.0,                     # foricng 0.0 for perfect JSON (upgrade is special)
            top_p=cfg["top_p"],
            max_tokens=10000,
            api_key=cfg.get("api_key"),
            api_base=cfg.get("base_url")
        )