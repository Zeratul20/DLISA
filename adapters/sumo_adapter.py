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
    def __init__(self, gui=False, label="default", port=None):
        self.sumo_binary = "sumo-gui" if gui else "sumo"
        self.config_path = "traffic_env/config.sumocfg"
        
        # FIX 1: Updated ID from your find_lanes.py output
        self.tls_id = "A1" 

        # second conn
        self.label = label
        self.port = port
        self.conn = None

        #  last cumm time
        self._prev_wait = {}

    def start(self,seed = None):
        cmd = [self.sumo_binary, "-c", self.config_path, "--start", "--delay", "100"]

        # NEW: deterministic/stochastic replication control
        if seed is not None:
            cmd += ["--seed", str(seed)]

        traci.start(cmd, label=self.label, port=self.port)
        self.conn = traci.getConnection(self.label)

    def close(self):
        if self.conn is not None:
            self.conn.close()
            self.conn = None

    def min_expected(self) -> int:
        return int(self.conn.simulation.getMinExpectedNumber())

    def get_state(self):
        # Axis 1: B1 and B3 (e.g., North-South)
        q_N = self.conn.lane.getLastStepHaltingNumber("B1A1_0")
        q_S = self.conn.lane.getLastStepHaltingNumber("B3A1_0")
        
        # Axis 2: B4 and B2 (e.g., East-West)
        q_E = self.conn.lane.getLastStepHaltingNumber("B4A1_0")
        q_W = self.conn.lane.getLastStepHaltingNumber("B2A1_0")
        
        return [q_N, q_S, q_E, q_W]

    def reset_waiting_meter(self):
        """Reset delta-wait tracking (call at the start of each evaluation window)."""
        self._prev_wait = {}

    def get_delta_waiting_time_step(self) -> float:
        """
        Return waiting time ADDED during the current step only (delta),
        computed from accumulated waiting time differences per vehicle.
        """
        total_delta = 0.0
        veh_ids = self.conn.vehicle.getIDList()

        for vid in veh_ids:
            cur = self.conn.vehicle.getAccumulatedWaitingTime(vid)
            prev = self._prev_wait.get(vid, cur)  # first time seen -> delta 0
            d = cur - prev
            if d > 0:
                total_delta += d
            self._prev_wait[vid] = cur

        # cleanup vehicles that left the simulation
        for vid in list(self._prev_wait.keys()):
            if vid not in veh_ids:
                del self._prev_wait[vid]

        return total_delta

    def apply_configuration(self, green_NS, green_EW):
        print("APPLY green_NS:", green_NS, "green_EW:", green_EW)
        # FIX 2: Use getAllProgramLogics instead of getLogic
        logic = self.conn.trafficlight.getAllProgramLogics(self.tls_id)[0]
        
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
        phases.append(self.conn.trafficlight.Phase(duration=green_NS, state=current_phases[0].state))
        
        # Phase 1 (Yellow) -> Keep Duration (usually 3s or 4s)
        phases.append(self.conn.trafficlight.Phase(duration=current_phases[1].duration, state=current_phases[1].state))
        
        # Phase 2 (East-West Green) -> Update Duration
        phases.append(self.conn.trafficlight.Phase(duration=green_EW, state=current_phases[2].state))
        
        # Phase 3 (Yellow) -> Keep Duration
        phases.append(self.conn.trafficlight.Phase(duration=current_phases[3].duration, state=current_phases[3].state))
        
        logic.phases = phases
        self.conn.trafficlight.setCompleteRedYellowGreenDefinition(self.tls_id, logic)

    def save_checkpoint(self, path: str):
        """Save SUMO state to an XML checkpoint."""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.conn.simulation.saveState(path)

    def load_checkpoint(self, path: str):
        """Load SUMO state from an XML checkpoint."""
        self.conn.simulation.loadState(path)

    def run_step(self):
        self.conn.simulationStep()

    def get_reward_metric(self):
        total_wait = 0
        for veh_id in self.conn.vehicle.getIDList():
            total_wait += self.conn.vehicle.getAccumulatedWaitingTime(veh_id)
        return total_wait
