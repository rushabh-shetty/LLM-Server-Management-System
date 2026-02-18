# data.py

import pandas as pd
import os

def load_sections():
    excel_file = "sections_config.xlsx"
    
    if not os.path.isfile(excel_file):
        raise FileNotFoundError(f"'{excel_file}' not found in current directory: {os.getcwd()}")
    
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