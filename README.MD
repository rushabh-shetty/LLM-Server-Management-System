# LLM Server Management System: HFT Optimizer

![Python](https://img.shields.io/badge/Python-3.14%2B-blue)
![Streamlit](https://img.shields.io/badge/Streamlit-App-FF4B4B)
![Redfish](https://img.shields.io/badge/Redfish-BMC-green)

## Table of Content

- [Authors](#-authors)
- [Summary](#-summary) 
- [Key Features](#-key-features)
- [Repository Organization](#-repository-organization)
- [Installation](#-installation)
- [Usage](#-usage)
- [Prerequisites](#-prerequisites)
- [Setting up the Mockup Redfish Server](#-setting-up-the-redfish-mockup-server-testing-environment)
- [Typical Workflow for Optimizing a Redfish Server](#-typical-workflow-for-optimizing-a-redfish-server)
- [Final Report](#-final-report)

## 👥 Authors
**Alejandro Chavez Ramos** - ajc21@illinois.edu<br>
LikedIn: www.linkedin.com/in/ajc21 <br>
<img src="imgs/Alejandro.jpeg" alt="Alejandro" width="150"/> <br>


**Rushabh Shetty** - shetty6@illinois.edu<br>
LinkedIn: https://www.linkedin.com/in/rushabh-shetty/ <br>
<img src= "imgs/Headshot_Rushabh_Shetty.jpeg" alt="Rushabh Shetty" width="150"/><br>

## 📌 Summary

The **LLM Server Management System** is a Streamlit application built to optimize High-Frequency Trading (HFT) systems through integrated data collection, real-time monitoring, AI-driven performance analysis, and hardware upgrade advice. By leveraging configurable AI models (such as Grok, OpenAI, etc.) and Redfish BMC integrations, this tool helps engineers and traders pinpoint bottlenecks, configure dynamic thresholds for critical components, and continuously tune their infrastructure for ultra-low latency.

## ✨ Key Features

- **Tab-Based Workflow**: An intuitive UI separated into Data, Monitoring, Performance, and Settings tabs for a clear operational flow.
- **Redfish BMC Integration**: Direct connections to server baseboard management controllers to fetch vital parameters (BIOS configurations, Memory, PCIe slots, CPU, NIC).
- **AI-Driven Performance Analysis**: Automated insights identifying the impact, risk, and "why HFT" context for specific hardware components using LLMs.
- **Hardware Upgrade Advice**: Intelligent suggestions for optimizing critical components.
- **Real-Time Monitoring**: Dynamic metrics tracking numeric thresholds of essential HFT server metrics.

## 🪜 Repository Organization
<ul>
    <li>group_05_project
        <ul>
            <li>imgs
            <li>tabs
                <ul>
                    <li>agentic_optimizer.py
                    <li>ai_settings_tab.py
                    <li>collect_data_tab.py
                    <li>history_tab.py
                    <li>monitor_tab.py
                    <li>performance_tab.py
                    <li>upgrade_tab.py
                </ul>
            </li>
            <li>README.md
            <li>Server.xlsx
            <li>ai.py
            <li>ai_config.json
            <li>ai_config.py
            <li>data.py
            <li>main.py
            <li>monitoring_history.csv
            <li>requirements.txt
            <li>sections_config.xlsx
            <li>sections_config_mac.xlsx
        </ul>
    </li>
</ul>

## 📦 Installation
Clone this repository:

```bash
git clone [https://github.com/rushabh-shetty/LLM-Server-Management-System.git](https://github.com/rushabh-shetty/LLM-Server-Management-System.git)
cd LLM-Server-Management-System
```

Install the required Python packages:
```bash
pip install -r requirements.txt
```
(Optional) Configure your AI models in ai_config.json or the Settings tab with your preferred provider keys (OpenAI, Grok, etc.).

## 💻 Usage
To run the Streamlit application, set your entry point to main.py:

```bash
streamlit run main.py
```

## 🛠 Prerequisites

- **Python**: Recommended version 3.14 (See notes below for specific dependencies).
- **Redfish Server**: A physical server with Redfish enabled, or the Redfish Mockup Server for testing.

> **⚠️ Important Note for Python 3.14 Users**
> If you are using Python 3.14, you must downgrade `uvloop` to version `0.22.1` or lower to ensure compatibility:
> ```bash
> pip install uvloop==0.22.1
> ```

## 🚀 Setting Up the Redfish Mockup Server (Testing Environment)

If you do not have a live server and want to test the application's data collection capabilities, you can use the DMTF Redfish Mockup Server. **Please clone this repository outside of the main LLM-Server-Management-System directory.**


### Clone the Mockup Server repository
```bash
git clone [https://github.com/DMTF/Redfish-Mockup-Server.git](https://github.com/DMTF/Redfish-Mockup-Server.git)
```

### Navigate to the directory
```bash
cd Redfish-Mockup-Server
```

### Create and activate a virtual environment
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows use: venv\Scripts\activate
```

### Install requirements
```bash
pip install -r requirements.txt
```

### Run the mockup server
```bash
python3 redfishMockupServer.py
```

## 🌊 Typical Workflow for Optimizing a Redfish Server:
### Data Collection
<ul>
    <li>Navigate to the Data tab.
    <li>Click to collect system information.
    <li>Run the "Collect Redfish BIOS" command.
</ul>

### Performance Analysis
<ul>
    <li>Navigate to the Performance tab.
    <li>Go to the BIOS sub-tab.
    <li>Click on Run BIOS Analysis.
</ul>

#### The integrated LLM will assess the current configurations and output high-impact recommendations to improve HFT latency.

## 📖 Final Report
