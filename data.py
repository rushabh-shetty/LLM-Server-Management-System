import pandas as pd
import os
import subprocess
import streamlit as st
import re
from pathlib import Path
import requests
from requests.auth import HTTPBasicAuth

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

@st.cache_data(ttl="10min", show_spinner=False)
def load_dynamic_df():

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
    for subtitle in monitored_metrics:
        row = dynamic_df[dynamic_df["Subsection_Title"] == subtitle]
        if not row.empty:
            # Use the pre-replaced command from load_dynamic_df 
            cmd = row.iloc[0].get("command")
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
    
def generate_selected_report(last):
    selected = [r for r in last.get("recommendations", []) if r.get("id") in st.session_state.get("selected_upgrade_recs", [])]
    if not selected:
        selected = last.get("recommendations", [])  # fallback: show everything if nothing selected

    total_cost = sum(r.get("estimated_cost", 0) for r in selected)
    budget_display = f"${last.get('budget', 0):,}" if last.get("budget") else "unlimited"

    md = f"# HFT Upgrade Report — {', '.join(last.get('focus_display', []))}\n\n"
    md += f"**Generated:** {last['timestamp']}\n"
    md += f"**Budget limit:** {budget_display}\n"
    md += f"**Selected total:** ${total_cost:,}\n\n"
    md += last.get("analysis_md", "") + "\n\n## Selected Upgrades\n\n"

    for r in selected:
        md += f"### {r.get('title')}\n"
        md += f"**Replace:** {r.get('current_part', '—')}\n"
        md += f"**With:** {r.get('recommended_model')} — {r.get('key_specs', '—')}\n"
        md += f"**Cost:** ${r.get('estimated_cost', 0):,}\n"
        md += f"**Impact:** {r.get('impact', '—')}\n"
        md += f"{r.get('description', '')}\n\n"

    st.download_button(
        "⬇️ Download upgrade_report.md",
        md,
        file_name="hft_upgrade_report.md",
        mime="text/markdown",
        use_container_width=True
    )
    st.success("✅ Report generated with your selected upgrades!")

def detect_build_system(project_path):
    
    # To extend for other languages later just add to the build_markers dict

    if not os.path.isdir(project_path):
        return {"error": f"Path not found or not a directory: {project_path}"}

    result = {
        "project_path": project_path,
        "build_type": "unknown",
        "build_files": [],
        "compiler": "unknown",
        "current_flags": "",
        "detected_make_vars": {},
        "hot_paths": []                     # For Application Code
    }

    # TODO: Build file markers 

    build_markers = {
        "Makefile": "make", 
        "CMakeLists.txt": "cmake", 
        "setup.py": "python",
        "Cargo.toml": "rust", 
        "build.ninja": "ninja", 
        "pyproject.toml": "python",
    }

    # TODO: Path finder

    for root, _, files in os.walk(project_path, topdown=True, followlinks=False):
        for f in files:
            if f in build_markers:
                full = os.path.join(root, f)
                result["build_files"].append(full)
                if result["build_type"] == "unknown":
                    result["build_type"] = build_markers[f]

    # TODO: Detect compiler version

    for cmd in ["gcc --version", "clang --version"]:
        try:
            out = subprocess.check_output(cmd, shell=True, text=True, timeout=3).strip()
            result["compiler"] = f"gcc ({out.splitlines()[0]})" if "gcc" in cmd else f"clang ({out.splitlines()[0]})"
            break
        except:
            continue

    # TODO: Flag extraction from Makefiles

    for bf in result["build_files"]:
        if "Makefile" in bf.lower():
            try:
                content = Path(bf).read_text(errors="ignore")
                for var in ["CFLAGS", "CXXFLAGS", "LDFLAGS"]:
                    m = re.search(rf"^{var}\s*[:?]?=\s*(.+?)(?:#|$)", content, re.MULTILINE)
                    if m:
                        result["current_flags"] = m.group(1).strip()
                        result["detected_make_vars"][var] = m.group(1).strip()
            except:
                pass

    # TODO: HOT-PATH detection for Application code 

    hft_keywords = ["order", "trade", "match", "book", "risk", "price", "position", "fill", "cancel", "latency"]
    for root, _, files in os.walk(project_path, topdown=True, followlinks=False):
        for f in files:
            if f.endswith((".cpp", ".h", ".cc", ".rs", ".py", ".pyx", ".c")):
                full = os.path.join(root, f)
                try:
                    content = Path(full).read_text(errors="ignore")
                    lines = content.splitlines()
                    for i, line in enumerate(lines):
                        if any(kw in line.lower() for kw in hft_keywords):
                            func = "unknown"
                            if f.endswith(".py") and "def " in line:
                                func = line.split("def ")[1].split("(")[0].strip()
                            elif "(" in line and any(x in line for x in ["int ", "void ", "fn "]):
                                func = line.split("(")[0].split()[-1].strip()
                            snippet = "\n".join(lines[max(0, i-3):i+4])[:400]
                            result["hot_paths"].append({
                                "file": os.path.relpath(full, project_path),
                                "line": i + 1,
                                "function": func,
                                "snippet": snippet,
                                "why": "contains latency-critical keywords"
                            })
                            break  # one hit per file
                except:
                    pass

    result["hot_paths"] = result["hot_paths"][:12]  # limit for UI

    return result

def get_bios_context(sections):

    #keyword matching to filter BIOS info

    bios_data = {}
    bios_keywords = ["bios", "firmware", "dmidecode", "cpupower", "c-state", "aspm", 
                     "pcie", "idle", "power management", "smc", "boot rom", "chipset", 
                     "motherboard", "frequency-info", "lspci"]
    
    for title, subs in sections.items():
        title_lower = title.lower()
        if any(k in title_lower for k in bios_keywords):
            bios_data[title] = subs
        else:
            # Also catch subsections
            for subtitle, data in subs.items():
                if any(k in str(data.get("output", "")).lower() for k in bios_keywords):
                    bios_data[title] = subs
                    break
    return bios_data

def get_redfish_bios(bmc_ip, port=8000, use_https=False, username="ADMIN", password="ADMIN"):
    
    # Just call the general endpoint with the BIOS path

    data = fetch_redfish_endpoint(
        bmc_ip=bmc_ip,
        port=port,
        use_https=use_https,
        username=username,
        password=password,
        endpoint="/redfish/v1/Systems/1/Bios" 
    )

    if not data:
        return None

    attributes = data.get("Attributes", {})
    if not attributes:
        st.error("BIOS Attributes section is empty in the response.")
        return None

    return {
        "raw": data,
        "attributes": attributes,
        "total_settings": len(attributes),
        "bmc_ip": bmc_ip,
        "port": port,
        "system_id": data.get("@odata.id", "").split("/")[-2] if "/Bios" in data.get("@odata.id", "") else "unknown",
        "endpoint": "/redfish/v1/Systems/*/Bios"
    }


def get_redfish_groups(attributes, return_attributes=False):

    if return_attributes:
        groups = {}
    else:
        groups = {}

    for key, value in attributes.items():
        key_lower = key.lower()

        if any(x in key_lower for x in ["cstate", "turbo", "hyper", "proc", "cpu"]):
            group = "Advanced → CPU Configuration"
        elif any(x in key_lower for x in ["pcie", "aspm", "sr-iov", "sriov", "link"]):
            group = "Advanced → PCI Subsystem"
        elif any(x in key_lower for x in ["power", "energy", "performance", "bias"]):
            group = "Power & Performance"
        elif any(x in key_lower for x in ["memory", "numa", "dimm"]):
            group = "Chipset → Memory / NUMA"
        elif any(x in key_lower for x in ["boot"]):
            group = "Boot Options"
        elif any(x in key_lower for x in ["security", "password", "tpm"]):
            group = "Security"
        else:
            group = "Other Settings"

        if return_attributes:
            if group not in groups:
                groups[group] = {}
            groups[group][key] = value
        else:
            groups[group] = groups.get(group, 0) + 1

    if return_attributes:
        return groups  # {group: {key: value, ...}}
    else:
        return dict(sorted(groups.items(), key=lambda x: -x[1]))  # counts, sorted

def fetch_redfish_endpoint(bmc_ip, port=8000, use_https=False, username="ADMIN", password="ADMIN", endpoint="/redfish/v1/Systems/1/Bios"):

    protocol = "https" if use_https else "http"
    base_url = f"{protocol}://{bmc_ip}:{port}"
    auth = HTTPBasicAuth(username, password) if username and password else None

    try:
        # Discover real System ID

        if "/Systems/" in endpoint or endpoint.startswith("/redfish/v1/Systems"):
            systems_url = f"{base_url}/redfish/v1/Systems"
            systems_resp = requests.get(systems_url, auth=auth, verify=False, timeout=8)
            systems_resp.raise_for_status()
            members = systems_resp.json().get("Members", [])
            if members:
                system_id_url = members[0]["@odata.id"]   # e.g. /redfish/v1/Systems/437XR1138R2
                # Replace any "/Systems/1/" with the real ID
                endpoint = endpoint.replace("/Systems/1/", f"{system_id_url}/")

        # Discover real Chassis ID

        if "/Chassis/" in endpoint:
            chassis_url = f"{base_url}/redfish/v1/Chassis"
            chassis_resp = requests.get(chassis_url, auth=auth, verify=False, timeout=8)
            chassis_resp.raise_for_status()
            members = chassis_resp.json().get("Members", [])
            if members:
                chassis_id_url = members[0]["@odata.id"]
                endpoint = endpoint.replace("/Chassis/1/", f"{chassis_id_url}/")

        full_url = f"{base_url}{endpoint}"
        resp = requests.get(full_url, auth=auth, verify=False, timeout=8)
        resp.raise_for_status()
        return resp.json()

    except Exception as e:
        st.error(f"Redfish endpoint {endpoint} failed: {str(e)}")
        return None


def collect_redfish_sections(bmc_ip, port, use_https, username, password, selected_sections, custom_endpoints = None):
    
    # Main function called from the Data tab. Returns a dict with all collected data

     #TODO: Pre-defined endpoints

    result = {}
    custom_endpoints = custom_endpoints or []

    for section in selected_sections:
        if section == "BIOS":

            # Reusing get_redfish_bios

            bios_data = get_redfish_bios(bmc_ip, port, use_https, username, password)
            if bios_data:
                result["BIOS"] = bios_data
                result["BIOS"]["endpoint"] = "/redfish/v1/Systems/*/Bios"

        elif section == "Processors":
            data = fetch_redfish_endpoint(bmc_ip, port, use_https, username, password, "/redfish/v1/Systems/1/Processors")
            if data:
                result["Processors"] = {"raw": data, "item_count": len(data.get("Members", [])), "endpoint": "/redfish/v1/Systems/1/Processors"}

        elif section == "Memory":
            data = fetch_redfish_endpoint(bmc_ip, port, use_https, username, password, "/redfish/v1/Systems/1/Memory")
            if data:
                result["Memory"] = {"raw": data, "item_count": len(data.get("Members", [])), "endpoint": "/redfish/v1/Systems/1/Memory"}

        elif section == "PCIeSlots":
            data = fetch_redfish_endpoint(bmc_ip, port, use_https, username, password, "/redfish/v1/Chassis/1/PCIeSlots")
            if data:
                result["PCIeSlots"] = {"raw": data, "item_count": len(data.get("Members", [])), "endpoint": "/redfish/v1/Chassis/1/PCIeSlots"}

        elif section == "Thermal":
            data = fetch_redfish_endpoint(bmc_ip, port, use_https, username, password, "/redfish/v1/Chassis/1/ThermalSubsystem")
            if data:
                result["Thermal"] = {"raw": data, "item_count": len(data.get("Temperatures", [])), "endpoint": "/redfish/v1/Chassis/1/ThermalSubsystem"}

        elif section == "Power":
            data = fetch_redfish_endpoint(bmc_ip, port, use_https, username, password, "/redfish/v1/Chassis/1/Power")
            if data:
                result["Power"] = {"raw": data, "item_count": len(data.get("PowerSupplies", [])), "endpoint": "/redfish/v1/Chassis/1/Power"}

        elif section == "FirmwareInventory":
            data = fetch_redfish_endpoint(bmc_ip, port, use_https, username, password, "/redfish/v1/UpdateService/FirmwareInventory")
            if data:
                result["FirmwareInventory"] = {"raw": data, "item_count": len(data.get("Members", [])), "endpoint": "/redfish/v1/UpdateService/FirmwareInventory"}

        elif section == "ChassisSensors":
            data = fetch_redfish_endpoint(bmc_ip, port, use_https, username, password, "/redfish/v1/Chassis/1")
            if data:
                result["ChassisSensors"] = {"raw": data, "item_count": 0, "endpoint": "/redfish/v1/Chassis/1"}

    # TODO: Add any custom endpoints the user typed

    for ep in custom_endpoints:
        if ep.strip():
            data = fetch_redfish_endpoint(bmc_ip, port, use_https, username, password, ep.strip())
            if data:
                key = ep.strip().strip("/").replace("/", "_").replace(":", "")
                count = 0
                if isinstance(data, dict):
                    if "Members" in data and isinstance(data["Members"], list):
                        count = len(data["Members"])
                    elif "Members@odata.count" in data:
                        count = data["Members@odata.count"]
                result[key] = {"raw": data, "item_count": count, "endpoint": ep.strip()}

    return result if result else None