import streamlit as st
import subprocess
import time
from collections import OrderedDict
import io
from data import load_sections

def render_collect_data_tab():

    st.subheader("HFT System Information Collector")

    st.markdown("Click the button to collect and view system info.")

    # Initialize session state to persist results across reruns
    if 'full_report' not in st.session_state:
        st.session_state.full_report = None
    if 'summary_text' not in st.session_state:
        st.session_state.summary_text = None
    if 'has_content' not in st.session_state:
        st.session_state.has_content = False

    if st.button("Collect System Information", type="primary"):

        with st.spinner("Collecting system info..."):

            #TODO: Start creating the report

            output = io.StringIO()
            output.write(f"System metrics collection started at {time.ctime()}\n\n")

            # Detect users interface , later used in each command

            iface = subprocess.getoutput(
                "ip link | grep -oP '^[0-9]+: \\K[^:]+' | grep -v lo | head -n1"
                            ).strip()
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
                st.success("✅ Configuration loaded from sections_config.xlsx")
                
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

    # Display results 

    if st.session_state.full_report:

        st.success("✅ Collection complete!")
        
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

    st.info("Place `sections_config.xlsx` in the same folder as this script. Edit it to add/remove/reorder commands")