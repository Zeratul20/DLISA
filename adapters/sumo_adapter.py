import os
import traci


class SumoAdapter:
    def __init__(self, gui=False, label="default", port=None):
        self.sumo_binary = "sumo-gui" if gui else "sumo"
        self.config_path = "traffic_env/config.sumocfg"
        self.tls_id = "A1"
        self.label = label
        self.port = port
        self.conn = None

        #  last cumm time
        self._prev_wait = {}

    def start(self, seed=None):
        cmd = [self.sumo_binary, "-c", self.config_path, "--start", "--delay", "100"]

        if seed is not None:
            cmd += ["--seed", str(seed)]

        traci.start(cmd, label=self.label, port=self.port)
        self.conn = traci.getConnection(self.label)

    def close(self):
        if self.conn is not None:
            self.conn.close()
            self.conn = None

    def get_state(self):

        # NS Axis (B2, B4)
        h_NS1 = self.conn.lane.getLastStepHaltingNumber("B2A1_0")
        h_NS2 = self.conn.lane.getLastStepHaltingNumber("B4A1_0")
        t_NS1 = self.conn.lane.getLastStepVehicleNumber("B2A1_0")
        t_NS2 = self.conn.lane.getLastStepVehicleNumber("B4A1_0")

        # EW Axis (B1, B3)
        h_EW1 = self.conn.lane.getLastStepHaltingNumber("B1A1_0")
        h_EW2 = self.conn.lane.getLastStepHaltingNumber("B3A1_0")
        t_EW1 = self.conn.lane.getLastStepVehicleNumber("B1A1_0")
        t_EW2 = self.conn.lane.getLastStepVehicleNumber("B3A1_0")

        # Return as two distinct vectors
        # Vector 1: Queue/Halting
        halting_state = [h_NS1, h_NS2, h_EW1, h_EW2]
        # Vector 2: Density/Total
        density_state = [t_NS1, t_NS2, t_EW1, t_EW2]

        return halting_state, density_state

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
        logic = self.conn.trafficlight.getAllProgramLogics(self.tls_id)[0]

        # We create a new phases list copying the states but changing duration
        phases = []
        current_phases = logic.phases

        # Phase 0 (North-South Green)
        phases.append(self.conn.trafficlight.Phase(duration=green_NS, state=current_phases[0].state))

        # Phase 1 (Yellow) -> Keep Duration
        phases.append(self.conn.trafficlight.Phase(duration=current_phases[1].duration, state=current_phases[1].state))

        # Phase 2 (East-West Green) -> Update Duration
        phases.append(self.conn.trafficlight.Phase(duration=green_EW, state=current_phases[2].state))

        # Phase 3 (Yellow)
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
