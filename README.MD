# LLM Server Management System: HFT Optimizer

![Python](https://img.shields.io/badge/Python-3.14%2B-blue)
![Streamlit](https://img.shields.io/badge/Streamlit-App-FF4B4B)
![Redfish](https://img.shields.io/badge/Redfish-BMC-green)

## 📌 Executive Summary

The **LLM Server Management System** is a Streamlit application built to optimize High-Frequency Trading (HFT) systems through integrated data collection, real-time monitoring, AI-driven performance analysis, and hardware upgrade advice. By leveraging configurable AI models (such as Grok, OpenAI, etc.) and Redfish BMC integrations, this tool helps engineers and traders pinpoint bottlenecks, configure dynamic thresholds for critical components, and continuously tune their infrastructure for ultra-low latency.

## ✨ Key Features

- **Tab-Based Workflow**: An intuitive UI separated into Data, Monitoring, Performance, and Settings tabs for a clear operational flow.
- **Redfish BMC Integration**: Direct connections to server baseboard management controllers to fetch vital parameters (BIOS configurations, Memory, PCIe slots, CPU, NIC).
- **AI-Driven Performance Analysis**: Automated insights identifying the impact, risk, and "why HFT" context for specific hardware components using LLMs.
- **Hardware Upgrade Advice**: Intelligent suggestions for optimizing critical components.
- **Real-Time Monitoring**: Dynamic metrics tracking numeric thresholds of essential HFT server metrics.

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

```bash
# Clone the Mockup Server repository
git clone [https://github.com/DMTF/Redfish-Mockup-Server.git](https://github.com/DMTF/Redfish-Mockup-Server.git)

# Navigate to the directory
cd Redfish-Mockup-Server

# Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows use: venv\Scripts\activate

# Install requirements
pip install -r requirements.txt

# Run the mockup server
python3 redfishMockupServer.py
📦 Installation
Clone this repository:

Bash
git clone [https://github.com/rushabh-shetty/LLM-Server-Management-System.git](https://github.com/rushabh-shetty/LLM-Server-Management-System.git)
cd LLM-Server-Management-System
Install the required Python packages:

Bash
pip install -r requirements.txt
(Optional) Configure your AI models in ai_config.json or the Settings tab with your preferred provider keys (OpenAI, Grok, etc.).

💻 Usage
To run the Streamlit application, set your entry point to main.py:

Bash
streamlit run main.py
Typical Workflow for Optimizing a Redfish Server:
Data Collection

Navigate to the Data tab.

Click to collect system information.

Run the "Collect Redfish BIOS" command.

Performance Analysis

Navigate to the Performance tab.

Go to the BIOS sub-tab.

Click on Run BIOS Analysis. The integrated LLM will assess the current configurations and output high-impact recommendations to improve HFT latency.

👥 Authors
Alejandro Chavez Ramos - ajc21@illinois.edu

Rushabh Shetty - shetty6@illinois.edu



Note:

If you are using Python version 3.14 then please install lower of uvloop version <= 0.22.1

'''bash pip install uvloop==0.22.1

Redfish Server Emulator to test out the code: https://github.com/DMTF/Redfish-Mockup-Server.git

Clone this repository outside the LLM-SERVER-MANAGEMENT-SYSTEM

OR run the commands below:
git clone https://github.com/DMTF/Redfish-Mockup-Server.git
cd Redfish-Mockup-Server
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 redfishMockupServer.py


To optimize a Server which has Redfish 

Go to data tab

collect system information and Collect redfish bios

Go to performance tab and navigate to BIOS subtab 
 and click on run bios analysis 


