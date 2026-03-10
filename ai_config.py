import json
import os
from litellm import completion

CONFIG_FILE = "ai_config.json"

DEFAULT_CONFIG = {
    "model": "ollama/llama3.1:8b",
    "api_key": None,
    "base_url": None,
    "temperature": 0.7,
    "top_p": 0.9,
    "max_tokens": 8000
}

def load_ai_config():
    """Load config from json or create default."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                config = json.load(f)
            # merge any missing keys (backward compatibility)
            for k, v in DEFAULT_CONFIG.items():
                if k not in config:
                    config[k] = v
            return config
        except:
            pass
    # first run or corrupted → create default
    save_ai_config(DEFAULT_CONFIG)
    return DEFAULT_CONFIG.copy()

def save_ai_config(config: dict):
    """Save to json (never sends keys anywhere else)."""
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)

def test_ai_connection(config: dict):
    """One-click test — returns (success, message)."""
    try:
        response = completion(
            model=config["model"],
            messages=[{"role": "user", "content": "Say only: Connection OK"}],
            temperature=0.0,
            max_tokens=10,
            api_key=config.get("api_key"),
            api_base=config.get("base_url"),
            stream=False
        )
        reply = response.choices[0].message.content.strip()
        return True, f"✅ Connected! Model replied: {reply}"
    except Exception as e:
        return False, f"❌ {str(e)}"