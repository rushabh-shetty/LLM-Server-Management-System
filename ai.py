import streamlit as st
import ollama
import pandas as pd
import json
import re

from data import load_sections, get_sections_for_profile, load_dynamic_df, build_system_profile, take_ai_snapshot, build_full_raw_text, load_dynamic_df

# TODO: Generic chat UI

def render_ai_chat(system_prompt, welcome_message="Hi! How can I help you today?", input_placeholder="Type your question...", clear_key="clear_ai_chat"):

    if "ai_messages" not in st.session_state:
        st.session_state.ai_messages = []

    for msg in st.session_state.ai_messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if st.session_state.ai_messages and st.button("🗑️ Clear Chat", key=clear_key):
        st.session_state.ai_messages = []
        st.rerun()

    if not st.session_state.ai_messages:
        with st.chat_message("assistant"):
            st.markdown(welcome_message)
        st.session_state.ai_messages.append({"role": "assistant", "content": welcome_message})

    if prompt := st.chat_input(input_placeholder):
        st.session_state.ai_messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        messages = [{"role": "system", "content": system_prompt}] + st.session_state.ai_messages

        with st.chat_message("assistant"):
            try:
                stream = ollama.chat(model="llama3.1:8b", messages=messages, stream=True)
                placeholder = st.empty()
                full_response = ""
                for chunk in stream:
                    if content := chunk["message"].get("content", ""):
                        full_response += content
                        placeholder.markdown(full_response + "▌")
                placeholder.markdown(full_response)
            except Exception as e:
                error_msg = f"**Ollama error**: {str(e)}\nMake sure `ollama serve` is running."
                st.error(error_msg)
                full_response = error_msg

        st.session_state.ai_messages.append({"role": "assistant", "content": full_response})

# TODO: AI Threshold

def get_ai_threshold():

    # Load dynamic_single metrics
    dynamic_df = load_dynamic_df()
    monitored_metrics = st.session_state.get("monitored_metrics", [])

    # Hardware profile
    if "sections" in st.session_state:
        system_profile = build_system_profile(st.session_state.sections)
    else:
        system_profile = "**⚠️ No hardware profile yet** — Go to the **Data** tab and click 'Collect System Information' first."
        st.warning(system_profile)

    # Refresh snapshot buttons
    col_refresh, col_clear, cl3 = st.columns([1,1,3])
    with col_refresh:
        if st.button("Get Snapshot for AI (better recommendations)", use_container_width=True, key="ai_refresh_snapshot", type="secondary"):
            if monitored_metrics and not dynamic_df.empty:
                snapshot = take_ai_snapshot(dynamic_df, monitored_metrics)
                st.session_state.ai_snapshot = snapshot
                st.success(f"✅ Snapshot refreshed! ({len(snapshot)} metrics measured)")
                st.rerun()
            else:
                st.warning("Select at least one metric in Monitor tab first.")

    with col_clear:
        if st.button("Clear Snapshot", use_container_width=True, key="ai_clear_snapshot"):
            st.session_state.pop("ai_snapshot", None)
            st.rerun()

    ai_snapshot = st.session_state.get("ai_snapshot", {})

    # === Build monitored metrics context (inlined - simple & clean) ===
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

    # Transparency expander
    with st.expander("View Full Context Being Sent to AI", expanded=False):
        st.markdown("**Hardware Profile**")
        st.markdown(system_profile)
        st.markdown("**Monitored Metrics + Commands + Current Values**")
        st.code(metrics_context, language="markdown")
        if ai_snapshot:
            st.markdown("**Current Snapshot (just measured)**")
            st.json(ai_snapshot)
        st.caption("This is exactly what gets injected into the system prompt.")

    # Threshold-specific prompt (inlined)
    system_prompt = f"""You are an expert HFT/low-latency systems engineer specializing in safe thresholds.

{system_profile}

{metrics_context}

RULES (follow strictly):
- Always give **concrete numbers** for every metric the user mentions (or all monitored ones if they say "suggest for all").
- Format: "For rx_queue_0_drops I recommend Min = 0, Max = 8. Reason: ..."
- One short sentence justification only — focused on latency, packet loss, or HFT stability.
- Be conservative and realistic based on the hardware profile and current values.
- Never give ranges like "80-85" — always exact Min and Max.
"""

    # Threshold-specific welcome + placeholder
    welcome = ("Hi! Ask me for safe **min/max thresholds** on any monitored metric.")
    placeholder = "Ask about thresholds... (e.g. recommended max for NIC rx_queue_0_drops)"

    # Generic reusable chat
    render_ai_chat(system_prompt, welcome_message=welcome, input_placeholder=placeholder)

# TODO: Performance analyzer

def perform_hft_analysis(selected_profile: str):

    if "sections" not in st.session_state:
        return "❌ No system data collected yet. Run the Data tab first.", [], {}

    all_sections = st.session_state.sections

    if selected_profile == "All Sections":
        profile_sections = all_sections
    else:
        df = load_sections()
        profile_titles = df[df["HFT_Profile"] == selected_profile]["Section_Title"].unique().tolist()
        profile_sections = {k: v for k, v in all_sections.items() if k in profile_titles}

    short_summary = build_system_profile(profile_sections)
    full_profile_data = ""
    for title, subs in profile_sections.items():
        full_profile_data += f"\n=== {title} ===\n"
        for subtitle, data in subs.items():
            cmd = data.get("command", "")
            out = data.get("output", "").strip() or "(no output yet)"
            full_profile_data += f"--- {subtitle} ---\n{cmd}\n{out}\n"

    dynamic_df = load_dynamic_df()
    monitored = [sub for subs in profile_sections.values() for sub in subs]
    dynamic_snapshot = take_ai_snapshot(dynamic_df, monitored) if monitored else {}

    context_for_ui = {
        "short_summary": short_summary,
        "full_profile_data": full_profile_data,
        "dynamic_snapshot": dynamic_snapshot
    }

    # === STRONG SYSTEM PROMPT (forces JSON) ===
    system_prompt = f"""You are an expert HFT/low-latency Linux performance engineer.

Hardware summary:
{short_summary}

Detailed data for the selected profile ({selected_profile}):
{full_profile_data}

Current dynamic values:
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

    # === MESSAGES THAT GUARANTEE OLLAMA ANSWERS (same trick that fixed Upgrade tab) ===
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "Generate the JSON analysis and recommendations NOW. Output ONLY the JSON object."}
    ]

    try:
        with st.status("Asking Ollama for JSON analysis...", expanded=True) as status:
            stream = ollama.chat(
                model="llama3.1:8b",
                messages=messages,
                stream=True,
                options={
                    "temperature": 0.1,   # very low = strict JSON
                    "top_p": 0.9,
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
            status.update(label="✅ JSON received — parsing...", state="complete")

        # === ROBUST JSON PARSING (same as before but improved) ===
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

        # Safety fallback
        if not recs and '"recommendations"' in full_response:
            try:
                rec_match = re.search(r'"recommendations":\s*(\[[\s\S]*?\])', full_response, re.DOTALL)
                if rec_match:
                    recs = json.loads(rec_match.group(1))
            except:
                pass

        return analysis, recs, context_for_ui

    except Exception as e:
        error_msg = f"❌ Ollama error: {str(e)}\nMake sure `ollama serve` is running."
        st.error(error_msg)
        return error_msg, [], context_for_ui

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