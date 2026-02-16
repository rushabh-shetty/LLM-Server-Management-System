import streamlit as st
import ollama
import pandas as pd
from data import load_sections


def get_ai_threshold():
    """Renders a full streaming chat interface with Llama 3.1 8B (local Ollama) inside an expander."""
    st.markdown("""
    Chat with **Llama 3.1 8B** for personalized threshold recommendations, metric explanations,
    and low-latency/HFT monitoring advice — automatically aware of your current config and monitored metrics.
    """)

    st.info("""
    **Requirements**  
    - Ollama running: `ollama serve` (in a terminal)  
    - Model pulled once: `ollama pull llama3.1:8b`
    """)

    # Load config (same as monitor_tab for consistency)
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
    except Exception as e:
        st.error(f"Failed to load config: {e}")
        dynamic_df = pd.DataFrame()
        context = "Config could not be loaded — recommendations will be generic."

    # Current monitored metrics (shared via session_state)
    monitored_metrics = st.session_state.get("monitored_metrics", [])

    # Build rich context for the system prompt
    if monitored_metrics and not dynamic_df.empty:
        context_lines = []
        for subtitle in monitored_metrics:
            row = dynamic_df[dynamic_df["Subsection_Title"] == subtitle]
            if not row.empty:
                r = row.iloc[0]
                unit = r["unit"] or "—"
                min_t = r["min_thresh"]
                max_t = r["max_thresh"]
                min_str = f"{min_t:.4f}" if pd.notna(min_t) else "not set"
                max_str = f"{max_t:.4f}" if pd.notna(max_t) else "not set"
                context_lines.append(
                    f"- **{subtitle}**: unit = {unit}, current min = {min_str}, current max = {max_str}"
                )
        context = "Current monitored metrics (with existing thresholds):\n" + "\n".join(context_lines)
        context += "\n\nFocus on safe, practical values for high-performance/low-latency (HFT) servers."
    else:
        context = "No metrics currently selected for monitoring — suggestions will be general."

    system_prompt = f"""You are an expert in system performance monitoring for high-performance,
low-latency servers (especially HFT workloads).

{context}

Provide clear, safe threshold recommendations with brief justifications.
Use markdown (tables, bullets) for readability. Be concise but thorough."""

    # Chat history (isolated to this component)
    if "ai_messages" not in st.session_state:
        st.session_state.ai_messages = []

    # Display previous messages
    for msg in st.session_state.ai_messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Clear chat button
    if st.session_state.ai_messages:
        if st.button("🗑️ Clear Chat", key="clear_ai_chat"):
            st.session_state.ai_messages = []
            st.rerun()

    # Welcome message on first load
    if not st.session_state.ai_messages:
        welcome = (
            "Hi! I can suggest safe thresholds, explain metrics, or give optimization tips. "
            f"{'I see your current monitored metrics and thresholds.' if monitored_metrics else 'Select metrics in the Monitor section for tailored advice.'}"
        )
        with st.chat_message("assistant"):
            st.markdown(welcome)
        # Pre-store welcome so it persists
        st.session_state.ai_messages.append({"role": "assistant", "content": welcome})

    # User input
    if prompt := st.chat_input("Ask about thresholds, metrics, or tuning..."):
        # Add user message
        st.session_state.ai_messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Build messages for Ollama
        messages = [{"role": "system", "content": system_prompt}] + st.session_state.ai_messages

        # Streaming response
        with st.chat_message("assistant"):
            try:
                stream = ollama.chat(
                    model="llama3.1:8b",
                    messages=messages,
                    stream=True,
                )
                placeholder = st.empty()
                full_response = ""
                for chunk in stream:
                    if content := chunk["message"].get("content", ""):
                        full_response += content
                        placeholder.markdown(full_response + "▌")
                placeholder.markdown(full_response)
            except Exception as e:
                error_msg = f"**Ollama connection error**: {str(e)}\n\nEnsure `ollama serve` is running and the model is pulled."
                st.error(error_msg)
                full_response = error_msg

        # Store assistant response
        st.session_state.ai_messages.append({"role": "assistant", "content": full_response})