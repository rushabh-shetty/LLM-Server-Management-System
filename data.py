# data.py

import pandas as pd
import os
import subprocess
import streamlit as st

@st.cache_data(ttl="10min", show_spinner=False)
def load_sections():
    excel_file = "sections_config_mac.xlsx"
    #excel_file = "sections_config.xlsx"
    
    if not os.path.isfile(excel_file):    
        return None
    
    df = pd.read_excel(excel_file, sheet_name="Sections")
    
    if df.empty:
        raise ValueError("The 'Sections' sheet is empty.")
    
    df.columns = df.columns.str.strip()
    
    required_cols = ["Section_Title", "Subsection_Title", "Command"]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(f"Missing required columns: {', '.join(missing_cols)}")
    
    df["Section_Title"] = df["Section_Title"].astype(str).str.strip()
    df["Subsection_Title"] = df["Subsection_Title"].fillna("").astype(str).str.strip()
    df["Command"] = df["Command"].fillna("").astype(str)
    df["Type"] = df.get("Type", "static").astype(str).str.lower()
    df["HFT_Profile"] = df.get("HFT_Profile", "").astype(str).str.strip()
    
    return df

# TODO: Helpers

def get_available_hft_profiles():
    """Returns sorted unique profiles + 'All Sections'"""
    df = load_sections()
    profiles = sorted([p for p in df["HFT_Profile"].dropna().unique() if p])
    return ["All Sections"] + profiles

def get_sections_for_profile(profile: str):
    """Returns sections for the chosen profile (plain dict, order preserved)"""
    df = load_sections()
    
    if profile == "All Sections":
        relevant = df
    else:
        relevant = df[df["HFT_Profile"] == profile]
    
    sections = {}                    
    
    for _, row in relevant.iterrows():
        title = row["Section_Title"]
        subtitle = row["Subsection_Title"] or "Untitled"
        
        if title not in sections:
            sections[title] = {}    
        
        sections[title][subtitle] = {
            "command": row["Command"],
            "type": row["Type"],
            "output": ""
        }
    
    return sections

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

@st.cache_data(ttl="10min", show_spinner=False)
def load_dynamic_df_2():

    iface = get_default_interface()
    df = load_sections()

    dyn = df[df["Type"] == "dynamic_single"].copy()

    dyn["command"]   = dyn["Command"].str.replace("{iface}", iface)
    dyn["min_thresh"] = pd.to_numeric(
        dyn.get("Threshold_Min", pd.Series([None] * len(dyn))),
        errors="coerce"
    )
    dyn["max_thresh"] = pd.to_numeric(
        dyn.get("Threshold_Max", pd.Series([None] * len(dyn))),
        errors="coerce"
    )
    dyn["unit"] = dyn.get("Unit", "").fillna("")

    return dyn

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

def build_full_raw_text(sections):
    """Reconstruct exact format like original parse_system_info()"""
    text = ""
    for title, subs in sections.items():
        text += f"=== {title} ===\n"
        for subtitle, data in subs.items():
            cmd = data.get("command", "").strip()
            out = data.get("output", "").strip() or "(no output yet)"
            text += f"--- {subtitle} ---\n{cmd}\n{out}\n\n"
    return text.strip()

def get_default_interface():
    """Get the first non-loopback network interface."""
    try:
        output = subprocess.getoutput(
            "ip link | grep -oP '^[0-9]+: \K[^:]+' | grep -v lo | head -n1"
        ).strip()
        return output if output else "unknown"
    except Exception:
        return "unknown"