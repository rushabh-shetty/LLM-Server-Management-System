import streamlit as st
import ollama
import pandas as pd
import subprocess
from data import load_sections, get_sections_for_profile
import json
import re

# TODO: General AI CONFIG

def render_ai_chat(system_prompt, welcome_message="Hi! How can I help you today?", input_placeholder="Type your question..."):
    """Generic chat UI + streaming — fully reusable for any future AI mode"""
    if "ai_messages" not in st.session_state:
        st.session_state.ai_messages = []

    for msg in st.session_state.ai_messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if st.session_state.ai_messages and st.button("🗑️ Clear Chat", key="clear_ai_chat"):
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

# TODO: Helpers

def load_dynamic_df():
    """Load and prepare dynamic_single metrics"""
    try:
        df = load_sections()
        dynamic_df = df[df["Type"] == "dynamic_single"].copy()
        dynamic_df["min_thresh"] = pd.to_numeric(
            dynamic_df.get("Threshold_Min", pd.Series([None] * len(dynamic_df))), errors="coerce"
        )
        dynamic_df["max_thresh"] = pd.to_numeric(
            dynamic_df.get("Threshold_Max", pd.Series([None] * len(dynamic_df))), errors="coerce"
        )
        dynamic_df["unit"] = dynamic_df.get("Unit", "").fillna("")
        return dynamic_df
    except Exception as e:
        st.error(f"Failed to load config: {e}")
        return pd.DataFrame()


def build_system_profile(sections):
    """Clean, short hardware fingerprint"""
    profile = ["**Hardware Profile (from Collect Data):**"]
    key_sections = ["CPU Info", "NIC Model Info", "Environmental Parameters",
                    "Memory Info", "NUMA Topology", "NIC Firmware Info"]
    for title in key_sections:
        if title in sections:
            profile.append(f"\n**{title}**")
            for subtitle, data in list(sections[title].items())[:5]:
                out = data.get("output", "").strip()
                if out:
                    clean = out.replace("\n", " ")[:280] + ("..." if len(out) > 280 else "")
                    profile.append(f"- {subtitle}: {clean}")
    return "\n".join(profile)


def take_ai_snapshot(dynamic_df, monitored_metrics):
    """Run current values for monitored metrics"""
    snapshot = {}
    iface = subprocess.getoutput(
        "ip link | grep -oP '^[0-9]+: \\K[^:]+' | grep -v lo | head -n1"
    ).strip() or "unknown"

    for subtitle in monitored_metrics:
        row = dynamic_df[dynamic_df["Subsection_Title"] == subtitle]
        if not row.empty:
            cmd_template = row.iloc[0]["Command"]
            cmd = cmd_template.replace("{iface}", iface)
            try:
                output = subprocess.check_output(cmd, shell=True, text=True, stderr=subprocess.STDOUT).strip()
                try:
                    val = float(output) if output else 0.0
                except ValueError:
                    val = output[:100]
                snapshot[subtitle] = val
            except Exception:
                snapshot[subtitle] = "error"
    return snapshot

# TODO: Threshold

def get_ai_threshold():
    """Main AI assistant for HFT threshold recommendations"""
    st.markdown("""
    Chat with **Llama 3.1 8B** for personalized HFT threshold recommendations.  
    It knows your exact hardware and every monitored metric.
    """)

    st.write("Example prompts:")
    st.code(
        "- Recommended max for NIC rx_queue_0_drops on low-latency servers?\n"
        "- Suggest thresholds for all my monitored metrics"
    )

    # Load dynamic_single metrics
    dynamic_df = load_dynamic_df()
    monitored_metrics = st.session_state.get("monitored_metrics", [])

    # Hardware profile
    if "sections" in st.session_state:
        system_profile = build_system_profile(st.session_state.sections)
    else:
        system_profile = "**⚠️ No hardware profile yet** — Go to the **Data** tab and click 'Collect System Information' first."

    # Refresh snapshot buttons
    col_refresh, col_clear = st.columns(2)
    with col_refresh:
        if st.button("📊 Refresh Snapshot for AI (run current values)", key="ai_refresh_snapshot", type="secondary"):
            if monitored_metrics and not dynamic_df.empty:
                snapshot = take_ai_snapshot(dynamic_df, monitored_metrics)
                st.session_state.ai_snapshot = snapshot
                st.success(f"✅ Snapshot refreshed! ({len(snapshot)} metrics measured)")
                st.rerun()
            else:
                st.warning("Select at least one metric in Monitor tab first.")

    with col_clear:
        if st.button("Clear Snapshot", key="ai_clear_snapshot"):
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
    with st.expander("📋 View Full Context Being Sent to AI (for transparency/debugging)", expanded=False):
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
    welcome = (
        "Hi! Ask me for safe **min/max thresholds** on any monitored metric. "
        "Click 'Refresh Snapshot' above for even better answers."
    )
    placeholder = "Ask about thresholds... (e.g. suggest for all my metrics)"

    # Generic reusable chat
    render_ai_chat(system_prompt, welcome_message=welcome, input_placeholder=placeholder)

# TODO: Performance analyzer

def perform_hft_analysis(selected_profile: str):
    """Improved parsing - handles model returning JSON inside analysis field"""
    if "sections" not in st.session_state:
        st.error("Run the Data tab first.")
        return None, [], {}

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
    monitored = []
    for subs in profile_sections.values():
        monitored.extend(subs.keys())
    dynamic_snapshot = take_ai_snapshot(dynamic_df, monitored) if monitored else {}

    context_for_ui = {
        "short_summary": short_summary,
        "full_profile_data": full_profile_data,
        "dynamic_snapshot": dynamic_snapshot
    }

    system_prompt = f"""You are an expert HFT/low-latency Linux performance engineer.

Hardware summary:
{short_summary}

Detailed data for the selected profile ({selected_profile}):
{full_profile_data}

Current dynamic values:
{json.dumps(dynamic_snapshot, indent=2) if dynamic_snapshot else "None"}

Output ONLY a valid JSON object. Nothing else. No explanations before or after.
{{
  "analysis": "=== Performance Analysis ===\n\nYour full markdown report here...",
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

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "Generate the JSON now."}
    ]

    try:
        stream = ollama.chat(model="llama3.1:8b", messages=messages, stream=True)
        full_response = ""
        placeholder = st.empty()
        for chunk in stream:
            full_response += chunk["message"].get("content", "")
            placeholder.markdown(full_response + "▌")
        placeholder.empty()

        # === ROBUST JSON PARSING ===
        full_response = full_response.strip()

        # Try 1: whole response is JSON
        try:
            data = json.loads(full_response)
        except:
            data = None

        # Try 2: extract largest JSON block
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

        # Final safety
        if not recs and '"recommendations"' in full_response:
            # Last attempt: manual extraction
            try:
                rec_match = re.search(r'"recommendations":\s*(\[[\s\S]*?\])', full_response, re.DOTALL)
                if rec_match:
                    recs = json.loads(rec_match.group(1))
            except:
                pass

        return analysis, recs, context_for_ui

    except Exception as e:
        error_msg = f"Ollama error: {str(e)}"
        st.error(error_msg)
        return error_msg, [], context_for_ui