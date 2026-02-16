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
    
    # Clean column names
    df.columns = df.columns.str.strip()
    
    required_cols = ["Section_Title", "Subsection_Title", "Command"]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(f"Missing required columns: {', '.join(missing_cols)}. Found: {list(df.columns)}")
    
    # Clean data
    df["Section_Title"] = df["Section_Title"].astype(str).str.strip()
    df["Subsection_Title"] = df["Subsection_Title"].fillna("").astype(str).str.strip()
    df["Command"] = df["Command"].fillna("").astype(str)
    df["Type"] = df.get("Type", "static").astype(str).str.lower()
    
    return df  # Preserves natural row order