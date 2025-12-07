import traci
import sumolib
import sys
import os

# Ensure SUMO_HOME is set
if 'SUMO_HOME' in os.environ:
    tools = os.path.join(os.environ['SUMO_HOME'], 'tools')
    sys.path.append(tools)
else:
    sys.exit("please declare environment variable 'SUMO_HOME'")

class SumoAdapter:
    def __init__(self, gui=False):
        self.sumo_binary = "sumo-gui" if gui else "sumo"
        self.config_path = "traffic_env/config.sumocfg"
        
        # FIX 1: Updated ID from your find_lanes.py output
        self.tls_id = "A1" 

    def start(self):
        traci.start([self.sumo_binary, "-c", self.config_path, "--start", "--delay", "100"])

    def close(self):
        traci.close()

    def get_state(self):
        # Axis 1: B1 and B3 (e.g., North-South)
        q_N = traci.lane.getLastStepHaltingNumber("B1A1_0") 
        q_S = traci.lane.getLastStepHaltingNumber("B3A1_0") 
        
        # Axis 2: B4 and B2 (e.g., East-West)
        q_E = traci.lane.getLastStepHaltingNumber("B4A1_0") 
        q_W = traci.lane.getLastStepHaltingNumber("B2A1_0") 
        
        return [q_N, q_S, q_E, q_W]

    def apply_configuration(self, green_NS, green_EW):
        # FIX 2: Use getAllProgramLogics instead of getLogic
        logic = traci.trafficlight.getAllProgramLogics(self.tls_id)[0]
        
        # We need to preserve the original phase structure (Yellow lights)
        # Standard SUMO generated lights usually have 4 phases:
        # 0: Green NS
        # 1: Yellow NS
        # 2: Green EW
        # 3: Yellow EW
        
        # We create a new phases list copying the states but changing duration
        phases = []
        
        # Note: The state string "GrGr..." depends on how many lanes you have.
        # We grab the 'state' string from the existing logic so we don't break it.
        # usually logic.phases is a tuple of Phase objects.
        
        current_phases = logic.phases
        
        # Phase 0 (North-South Green) -> Update Duration
        phases.append(traci.trafficlight.Phase(duration=green_NS, state=current_phases[0].state))
        
        # Phase 1 (Yellow) -> Keep Duration (usually 3s or 4s)
        phases.append(traci.trafficlight.Phase(duration=current_phases[1].duration, state=current_phases[1].state))
        
        # Phase 2 (East-West Green) -> Update Duration
        phases.append(traci.trafficlight.Phase(duration=green_EW, state=current_phases[2].state))
        
        # Phase 3 (Yellow) -> Keep Duration
        phases.append(traci.trafficlight.Phase(duration=current_phases[3].duration, state=current_phases[3].state))
        
        logic.phases = phases
        traci.trafficlight.setCompleteRedYellowGreenDefinition(self.tls_id, logic)

    def run_step(self):
        traci.simulationStep()

    def get_reward_metric(self):
        total_wait = 0
        for veh_id in traci.vehicle.getIDList():
            total_wait += traci.vehicle.getAccumulatedWaitingTime(veh_id)
        return total_wait