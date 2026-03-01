import streamlit as st
import ollama
import pandas as pd
import json
import re
from datetime import datetime
from litellm import completion

from data import load_sections, get_sections_for_profile, load_dynamic_df, build_system_profile, take_ai_snapshot, build_full_raw_text

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
    context: dict,
    system_prompt: str,
    result_key: str = "last_analysis",
    task_name: str = "Performance Analysis",
    model: str = "ollama/llama3.1:8b",      # ← FIXED: now matches your chat + litellm requirement
    temperature: float = 0.1,
    top_p: float = 0.9,
    max_tokens: int = 8000,
    api_key: str = None,
    api_base: str = None,                    # e.g. "http://localhost:11434" if needed
    force_json_user_message: str = "Generate the JSON analysis and recommendations NOW. Output ONLY the JSON object."
):
    """Reusable one-shot structured AI task using litellm (same style as render_ai_chat)"""
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

            # === Robust JSON parsing (exactly your original logic) ===
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

            # Store result — backward compatible with your existing display code
            st.session_state[result_key] = {
                "profile": context.get("selected_profile", task_name),   # ← FIXED for KeyError
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
    
    with st.expander("View Full Context Being Sent to AI", expanded=False):
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

    render_ai_chat(
        system_prompt = system_prompt,     
        welcome_message = welcome,
        input_placeholder = placeholder,
        messages_key="threshold_chat_messages", 
        chat_input_key="threshold_chat_input",    
        clear_key="threshold_clear_chat"
    )

# TODO: Performance analyzer

def perform_hft_analysis(selected_profile):

    if "sections" not in st.session_state:
        st.info("Run Data tab first")
        return

    # === 1. BUILD CONTEXT ONCE ===
    all_sections = st.session_state.sections

    # Stable full hardware summary (never changes when switching profiles)
    full_hardware_summary = build_system_profile(all_sections)

    # Profile-specific sections (real collected data, not the empty template)
    if selected_profile == "All Sections":
        profile_sections = all_sections
    else:
        df = load_sections()
        profile_titles = df[df["HFT_Profile"] == selected_profile]["Section_Title"].unique().tolist()
        profile_sections = {k: v for k, v in all_sections.items() if k in profile_titles}

    # Re-use existing helper (much cleaner than the old loop)
    full_profile_data = build_full_raw_text(profile_sections)

    # Dynamic snapshot (profile-specific)
    dynamic_df = load_dynamic_df()
    monitored = [subtitle for subs in profile_sections.values() for subtitle in subs.keys()]
    dynamic_snapshot = take_ai_snapshot(dynamic_df, monitored) if monitored else {}

    context = {
        "short_summary": full_hardware_summary,      # kept old key for your existing display code
        "full_profile_data": full_profile_data,
        "dynamic_snapshot": dynamic_snapshot,
        "selected_profile": selected_profile,
        "full_hardware_summary": full_hardware_summary   # extra name for future tabs
    }

    # === 2. PREVIEW ===
    with st.expander("Preview what will be sent to AI", expanded = False):
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

    # === 3. RUN BUTTON + AI CALL ===
    if st.button("🚀 Run Performance Analysis", type="primary", width='stretch'):
        system_prompt = f"""You are an expert HFT/low-latency Linux performance engineer.

FULL HARDWARE SUMMARY (always included — use this as base context):
{full_hardware_summary}

DETAILED DATA FOR THE SELECTED PROFILE ({selected_profile}):
{full_profile_data}

CURRENT DYNAMIC VALUES (profile-specific):
{json.dumps(dynamic_snapshot, indent=2) if dynamic_snapshot else "None"}

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
}}"""

        render_structured_ai_task(
            context=context,
            system_prompt=system_prompt,
            result_key="last_analysis",
            task_name=f"HFT Analysis — {selected_profile}",
        )

#TODO: Upgrade AI

def perform_upgrade_analysis(focus_keys: list[str], budget: float | None = None):

    if "sections" not in st.session_state:
        return "❌ No system data collected yet. Run the Data tab first.", [], ""

    all_sections = st.session_state.sections

    # Build focused sections (supports multiple categories)
    focused_sections = {}
    focus_names = []
    for key in focus_keys:
        if key in ("General Overview", "All Sections"):
            focused_sections.update(all_sections)
            focus_names.append("General Overview")
        else:
            df = load_sections()
            profile_titles = df[df["HFT_Profile"] == key]["Section_Title"].unique().tolist()
            for t in profile_titles:
                if t in all_sections:
                    focused_sections[t] = all_sections[t]
            focus_names.append(key)

    focus_name_str = " + ".join(focus_names)

    short_summary = build_system_profile(all_sections)
    full_raw = build_full_raw_text(focused_sections)

    dynamic_df = load_dynamic_df()
    monitored = [sub for subs in focused_sections.values() for sub in subs]
    snapshot = take_ai_snapshot(dynamic_df, monitored) if monitored else {}

    budget_text = f"maximum budget of ${budget:,.0f}" if budget and budget > 0 else "no budget limit"

    # === STRONG SYSTEM PROMPT ===
    system_prompt = f"""You are an expert HFT/low-latency systems engineer with 15+ years optimizing trading infrastructure.

Full hardware profile:
{short_summary}

Focused data for: {focus_name_str}
{full_raw}

Current dynamic values:
{str(snapshot) if snapshot else "None"}

Analyze this system for high-frequency trading optimization.
Provide a detailed analysis and **at least 3 practical hardware/software upgrade recommendations**.
Consider {budget_text}.

Respond in clear, professional markdown with these exact sections:

### Analysis
(detailed paragraph form, mention latency/throughput gains, bottlenecks, etc.)

### Recommendations
- **Title 1**  
  Description...  
  Estimated cost: $X  
  Expected HFT impact: ...

- **Title 2**  
  ...

Be specific, realistic, and conservative. Never say "it depends" — give concrete advice."""

    # === MESSAGES THAT GUARANTEE OLLAMA ANSWERS ===
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "Generate the full upgrade analysis and recommendations NOW."}
    ]

    try:
        with st.status("Asking Ollama (Llama 3.1 8B)...", expanded=True) as status:
            stream = ollama.chat(
                model="llama3.1:8b",
                messages=messages,
                stream=True,
                # These options make responses much more reliable for demos/role-play
                options={
                    "temperature": 0.7,
                    "top_p": 0.92,
                    "num_ctx": 8192,
                }
            )

            full_response = ""
            placeholder = st.empty()

            for chunk in stream:
                content = chunk["message"].get("content", "")
                full_response += content
                placeholder.markdown(full_response + "▌")

            placeholder.empty()
            status.update(label="✅ Analysis complete!", state="complete")

        return full_response, [], full_raw   # analysis, recommendations (empty), full_raw

    except Exception as e:
        error_msg = f"❌ Ollama error: {str(e)}\nMake sure `ollama serve` is running and the model is pulled."
        st.error(error_msg)
        return error_msg, [], full_raw