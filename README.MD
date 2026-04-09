Note:

If you are using Python version 3.14 then please install lower of uvloop version <= 0.22.1

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
 

