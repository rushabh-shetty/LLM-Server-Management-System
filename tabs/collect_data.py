# Main app file (updated render_collect_data — uses your separated load_sections)

import streamlit as st
import subprocess
import time
from collections import OrderedDict
import io
from data import load_sections

def render_collect_data():
    st.subheader("HFT System Information Collector")
    st.markdown("Click the button to collect and view system info.")

    if st.button("🚀 Collect System Information", type="primary"):
        with st.spinner("Collecting system info..."):
            output = io.StringIO()
            output.write(f"System metrics collection started at {time.ctime()}\n\n")

            # Detect interface early
            iface = subprocess.getoutput(
                "ip link | grep -oP '^[0-9]+: \\K[^:]+' | grep -v lo | head -n1"
            ).strip()
            if not iface:
                iface = "unknown"
                output.write("Warning: No network interface detected (excluding lo).\n\n")

            # Load and build sections
            try:
                df = load_sections()
                
                sections = []
                current_section = {"title": "", "commands": []}
                current_subtitle = ""
                
                for _, row in df.iterrows():
                    title = row["Section_Title"]
                    subtitle = row["Subsection_Title"]
                    cmd_template = row["Command"]
                    
                    # New section
                    if title != current_section["title"] and current_section["title"]:
                        sections.append(current_section)
                        current_section = {"title": title, "commands": []}
                        current_subtitle = ""
                    
                    current_section["title"] = title
                    
                    # Subtitle change → auto header
                    if subtitle and subtitle != current_subtitle:
                        current_section["commands"].append(f"echo '\n--- {subtitle} ---'\n")
                        current_subtitle = subtitle
                    
                    # Add real command with {iface} replace
                    cmd = cmd_template.replace('{iface}', iface)
                    current_section["commands"].append(cmd)
                
                # Append last section
                if current_section["title"]:
                    sections.append(current_section)
                
                st.success("✅ Configuration loaded from sections_config.xlsx")
                
            except Exception as e:
                st.error(f"❌ Failed to load sections_config.xlsx: {e}")
                st.stop()

            # Summary setup (only for subtitled commands)
            summary = OrderedDict()
            for sec in sections:
                summary[sec["title"]] = []
                for cmd in sec["commands"]:
                    if cmd.startswith("echo '\n--- "):
                        subtitle = cmd.split("---")[1].strip()
                        # Next real command after echo
                        real_cmds = [c for c in sec["commands"][sec["commands"].index(cmd)+1:] if not c.startswith("echo")]
                        real_cmd = real_cmds[0] if real_cmds else ""
                        summary[sec["title"]].append([subtitle, real_cmd, "Success", ""])

            # Execution
            for sec in sections:
                output.write(f"\n=== {sec['title']} ===\n")
                for cmd in sec["commands"]:
                    if cmd.startswith("echo"):
                        try:
                            out_txt = subprocess.check_output(cmd, shell=True, text=True, stderr=subprocess.STDOUT)
                            output.write(out_txt)
                        except:
                            pass
                    else:
                        try:
                            out_txt = subprocess.check_output(cmd, shell=True, text=True, stderr=subprocess.STDOUT)
                            if cmd == "sensors" and not out_txt.strip():
                                raise subprocess.CalledProcessError(1, cmd)
                            output.write(out_txt)
                        except subprocess.CalledProcessError:
                            # Mark matching subtitle as failed
                            for items in summary.values():
                                for item in items:
                                    if item[1] == cmd:
                                        item[2] = "Failed"
                                        item[3] = "Command failed or no output"
                            fallback = {
                                "sensors": "No sensors data available (install lm-sensors or check host if VM)\n"
                            }.get(cmd.split()[0], "Command failed or no output\n")
                            output.write(fallback)

            full_report = output.getvalue()

            # Summary display
            summary_text = "### Data Collection Summary\n\n"
            for title, items in summary.items():
                if items:
                    summary_text += f"**{title}**\n\n"
                    for subtitle, cmd, status, reason in items:
                        icon = "✅" if status == "Success" else "❌"
                        reason_part = f" ({reason})" if reason else ""
                        summary_text += f"{icon} **{subtitle}** → `{cmd}`{reason_part}\n\n"
                    summary_text += "---\n\n"

        st.success("✅ Collection complete!")
        if summary_text != "### Data Collection Summary\n\n":
            st.markdown(summary_text)

        with st.expander("📄 View Detailed Report (raw output)", expanded=False):
            st.code(full_report, language=None)

        st.download_button(
            label="💾 Download Report as system_info.txt",
            data=full_report,
            file_name="system_info.txt",
            mime="text/plain"
        )

    st.info("Place `sections_config.xlsx` in the same folder as this script. Edit it to add/remove/reorder commands — no code changes needed!")