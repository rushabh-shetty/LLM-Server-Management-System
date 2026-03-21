import streamlit as st
from ai_config import save_ai_config, test_ai_connection

def render_ai_settings_tab():
    
    st.header("AI Model & API Settings")
    st.caption("Changes here apply to **every** AI call in the app instantly")

    # TODO: Select AI

    config = st.session_state.ai_config

    col1, col2 = st.columns([3, 2])

    with col1:
        model = st.text_input(
            "Model name",
            value=config["model"],
            placeholder="ollama/llama3.1:8b",
            help="Examples:\n• xai/grok-4-1-fast-reasoning\n• ollama/llama3.1:8b\n• openai/gpt-4o\n• anthropic/claude-3-5-sonnet-20241022"
        )

    with col2:
        api_key = st.text_input(
            "API Key (leave blank for local Ollama)",
            value=config.get("api_key") or "",
            type="password",
            placeholder="sk-... or xai-..."
        )

    base_url = st.text_input(
        "Custom base URL (optional — only for local proxies)",
        value=config.get("base_url") or "",
        placeholder="http://localhost:11434/v1"
    )

    # TODO: Sliders

    temperature = st.slider("Temperature", 0.0, 1.0, config["temperature"], 0.05)
    top_p = st.slider("Top-p", 0.0, 1.0, config["top_p"], 0.05)
    max_tokens = st.slider("Max tokens", 1000, 32000, config["max_tokens"], 500)

    # TODO: Save + Test buttons

    col_save, col_test = st.columns(2)
    with col_save:
        if st.button("💾 Save & Apply to whole app", type="primary", use_container_width=True):
            new_config = {
                "model": model,
                "api_key": api_key if api_key.strip() else None,
                "base_url": base_url if base_url.strip() else None,
                "temperature": temperature,
                "top_p": top_p,
                "max_tokens": max_tokens
            }
            save_ai_config(new_config)
            st.session_state.ai_config = new_config
            st.success("✅ Settings saved! All AI tabs now use this model.")
            st.rerun()

    with col_test:
        if st.button("Test Connection Now", use_container_width=True):
            success, msg = test_ai_connection({
                "model": model,
                "api_key": api_key if api_key.strip() else None,
                "base_url": base_url if base_url.strip() else None
            })
            if success:
                st.success(msg)
            else:
                st.error(msg)

    st.info("🔒 Your API key stays only on your computer and is never sent anywhere except to the provider you chose.")