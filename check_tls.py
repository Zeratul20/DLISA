import traci
import sumolib
import os
import sys

# Ensure SUMO_HOME is set
if 'SUMO_HOME' in os.environ:
    tools = os.path.join(os.environ['SUMO_HOME'], 'tools')
    sys.path.append(tools)

# Start SUMO without GUI to be fast
traci.start(["sumo", "-c", "traffic_env/config.sumocfg"])

print("\n" + "="*40)
print("  VALID TRAFFIC LIGHT IDs:")
print("="*40)

# Get list of all traffic lights in the simulation
tls_list = traci.trafficlight.getIDList()

for tls in tls_list:
    print(f"  -> '{tls}'")

if not tls_list:
    print("  ERROR: No traffic lights found! Did netgenerate use --tls.guess?")

print("="*40 + "\n")

traci.close()