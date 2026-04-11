import streamlit as st
import subprocess
import time
from collections import OrderedDict
import io
from data import load_sections, get_default_interface, collect_redfish_sections, get_redfish_groups
import os
import json

def render_collect_data_tab():

    st.header("HFT System Information Collector")

    st.divider()
    st.subheader("Local System Information Collection")

    st.markdown("Click the button to collect and view system info.")

    # TODO: Prerequisite

    st.info("Place `sections_config.xlsx` in the same folder as this script. Edit it to add/remove/reorder commands")

    if not os.path.isfile("sections_config.xlsx"):

        if os.path.isfile("sections_config.xlsx"):
            st.success("✅ sections_config.xlsx")
        else:
            st.error("⚠️ sections_config.xlsx missing")
    
        return

    # TODO: Variables to save in session state

    if 'full_report' not in st.session_state:
        st.session_state.full_report = None
    if 'summary_text' not in st.session_state:
        st.session_state.summary_text = None
    if 'has_content' not in st.session_state:
        st.session_state.has_content = False

    # TODO: Collect Information

    if st.button("Collect System Information", type="primary"):

        with st.spinner("Collecting system info..."):

            #TODO: Start creating the report

            output = io.StringIO()
            output.write(f"System metrics collection started at {time.ctime()}\n\n")

            # Detect users interface , later used in each command

            iface = get_default_interface()
            if not iface:
                iface = "unknown"
            output.write("Warning: No network interface detected (excluding lo).\n\n")

            # TODO: Load and build sections

            try:
                df = load_sections()
                sections = {} # Preserves insertion order (section order from Excel)

                for _, row in df.iterrows():
                    title = str(row["Section_Title"]).strip()
                    subtitle = str(row["Subsection_Title"]).strip()
                    cmd_template = str(row.get("Command", "")).strip()
                    cmd_type = str(row.get("Type", "static")).strip()

                    # Clean up possible 'nan' from empty cells
                    if subtitle.lower() == "nan":
                        subtitle = "Untitled"
                    if cmd_template.lower() == "nan":
                        cmd_template = ""
                    if cmd_type.lower() == "nan":
                        cmd_type = "static"
                    # Skip completely empty rows
                    
                    if not title:
                        continue

                    # Replace {iface}
                    cmd = cmd_template.replace("{iface}", iface)

                    # Initialize section and subsection
                    if title not in sections:
                        sections[title] = OrderedDict()

                    sections[title][subtitle] = {
                        "command": cmd,
                        "type": cmd_type,
                        "output": "",
                        "status": "Pending",
                        "reason": ""
                                            }
                
                st.session_state.sections = sections

            except Exception as e:
                st.error(f"❌ Failed to load sections_config.xlsx: {e}")
                st.stop()

            # TODO: Report

            for title in sections:
                output.write(f"\n=== {title} ===\n")
                for subtitle, data in sections[title].items():
                    cmd = data["command"]
                    if not cmd.strip():
                        continue # Skip empty commands (e.g., placeholder rows)
                    output.write(f"\n--- {subtitle} ---\n")
                    try:
                        out_txt = subprocess.check_output(
                            cmd, shell=True, text=True, stderr=subprocess.STDOUT
                                            )
                        data["output"] = out_txt
                        data["status"] = "Success"
                        data["reason"] = ""
                        # Special case: empty sensors output
                        if cmd.strip() == "sensors" and not out_txt.strip():
                            raise subprocess.CalledProcessError(1, cmd)
                    except subprocess.CalledProcessError:
                        data["status"] = "Failed"
                        data["reason"] = "Command failed or no output"
                        first_word = cmd.split()[0] if cmd.split() else ""
                        fallback = {
                            "sensors": "No sensors data available (install lm-sensors or check host if VM)\n"
                                            }.get(first_word, "Command failed or no output\n")
                        data["output"] = fallback
                    output.write(data["output"])
            full_report = output.getvalue()

            # TODO: Summary display

            summary_text = "### Data Collection Summary\n\n"
            has_content = False
            for title in sections:
                section_has_items = any(
                    data["command"].strip() for data in sections[title].values()
                                    )
                if section_has_items:
                    has_content = True
                    summary_text += f"**{title}**\n\n"
                    for subtitle, data in sections[title].items():
                        if not data["command"].strip():
                            continue
                        icon = "✅" if data["status"] == "Success" else "❌"
                        reason_part = f" ({data['reason']})" if data["reason"] else ""
                        summary_text += f"{icon} **{subtitle}** → `{data['command']}`{reason_part}\n\n"
                    summary_text += "---\n\n"

            # Store results in session state
            st.session_state.full_report = full_report
            st.session_state.summary_text = summary_text
            st.session_state.has_content = has_content

    # TODO: Display results 

    if st.session_state.full_report:
        
        if st.session_state.has_content:
            st.markdown(st.session_state.summary_text)
        
        with st.expander("📄 View Detailed Report (raw output)", expanded=False):
            st.code(st.session_state.full_report, language=None)
        
        st.download_button(
            label="💾 Download Report as system_info.txt",
            data=st.session_state.full_report,
            file_name="system_info.txt",
            mime="text/plain"
        )

    # TODO: Redfish Section

    st.divider()
    st.subheader("Redfish BMC Collection (Supermicro / compatible)")

    if "redfish_enabled" not in st.session_state:
        st.session_state.redfish_enabled = False

    st.session_state.redfish_enabled = st.checkbox(
        "Enable Redfish BMC query",
        value=st.session_state.redfish_enabled,
        help="Fetch hardware data directly from the BMC"
    )

    if st.session_state.redfish_enabled:

        col1, col2 = st.columns([3, 1])

        with col1:

            bmc_ip = st.text_input("BMC IP / Hostname", value=st.session_state.get("redfish_config", {}).get("bmc_ip", "127.0.0.1"), key="redfish_ip")
            port = st.number_input("Port", value=st.session_state.get("redfish_config", {}).get("port", 8000), min_value=1, max_value=65535, key="redfish_port")
            use_https = st.checkbox("Use HTTPS", value=st.session_state.get("redfish_config", {}).get("use_https", False), key="redfish_https")

        with col2:

            username = st.text_input("Username", value=st.session_state.get("redfish_config", {}).get("username", "ADMIN"), key="redfish_user")
            password = st.text_input("Password", value=st.session_state.get("redfish_config", {}).get("password", "ADMIN"), type="password", key="redfish_pass")

        # TODO: Checkbox - Select Endpoints 

        st.markdown("### Redfish Sections to Collect")
        st.caption("BIOS is recommended. Others are optional.")

        sections_options = {
            "BIOS": True,
            "Processors": True,
            "Memory": True,
            "PCIeSlots": True,
            "Thermal": False,
            "Power": False,
            "FirmwareInventory": False,
            "ChassisSensors": False,
        }

        selected = {}
        for name, default in sections_options.items():
            selected[name] = st.checkbox(name, value=default, key=f"redfish_{name}")

        ## Custom endpoints

        custom_endpoints = st.text_area(
            "Advanced — Custom endpoints (one full path per line)",
            value="",
            placeholder="/redfish/v1/Systems/1/Processors\n/redfish/v1/Chassis/1/ThermalSubsystem",
            help="Example: /redfish/v1/Systems/1/Processors",
            key="redfish_custom"
        ).strip().splitlines()

        if st.button("Collect Redfish Data", type="primary"):
            with st.spinner("Connecting to BMC..."):

                # Save config for future use

                st.session_state.redfish_config = {
                    "bmc_ip": bmc_ip,
                    "port": port,
                    "use_https": use_https,
                    "username": username,
                    "password": password
                }

                selected_list = [k for k, v in selected.items() if v]
                data = collect_redfish_sections(
                    bmc_ip, port, use_https, username, password,
                    selected_list, custom_endpoints
                )

                if data:
                    st.session_state.redfish_data = data
                    st.success(f"✅ Collected {len(data)} Redfish sections!")
                    st.rerun()
                else:
                    st.error("Failed to fetch any data — check IP/credentials.")

        # TODO: Show results from redfish

        if "redfish_data" in st.session_state:
            st.caption(f"IP: {st.session_state.redfish_config.get('bmc_ip')}:{st.session_state.redfish_config.get('port')}")

            for section_name, section_data in st.session_state.redfish_data.items():
                if section_name == "BIOS":
                    count = section_data.get("total_settings", "—")
                    title = f"**{section_name}** — {count} settings"
                else:
                    count = section_data.get("item_count", "—")
                    title = f"**{section_name}** — {count} items"

                with st.expander(title, expanded=section_name == "BIOS"):
                    if section_name == "BIOS" and "attributes" in section_data:
                        groups = get_redfish_groups(section_data["attributes"])
                        for title, count in groups.items():
                            st.write(f"- **{title}** — **{count}** settings")
                    else:
                        st.write(f"Endpoint: `{section_data.get('endpoint', '—')}`")
                        st.write(f"Items: `{section_data.get('item_count', 0)}`")

                    with st.expander("📄 Raw JSON (click to expand)", expanded=False):
                        st.json(section_data.get("raw", section_data), expanded=True)

            # Download + Clear
            col_dl, col_clear = st.columns(2)
            with col_dl:
                st.download_button(
                    "⬇️ Download full_redfish_data.json",
                    data=json.dumps(st.session_state.redfish_data, indent=2),
                    file_name="full_redfish_data.json",
                    mime="application/json",
                    use_container_width=True
                )
            with col_clear:
                if st.button("🗑️ Clear All Redfish Data", use_container_width=True):
                    st.session_state.pop("redfish_data", None)
                    st.session_state.pop("redfish_config", None)
                    st.rerun()

    