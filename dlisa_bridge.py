import sys
import os
import numpy as np

# 1. Allow Python to see the dlisa_source folder
sys.path.append(os.path.join(os.getcwd(), 'dlisa_source'))

# 2. Import the logic (Corrected based on your grep command)
try:
    # File: Adaptation_Optimizer.py | Class: AdaptationOptimizer
    from dlisa_source.Adaptation_Optimizer import AdaptationOptimizer
except ImportError as e:
    print(f"CRITICAL ERROR: Could not import DLiSA. Details: {e}")
    sys.exit(1)

class SumoBridge:
    """
    The interface between your Traffic City and the DLiSA Brain.
    """
    def __init__(self, sumo_adapter):
        self.adapter = sumo_adapter
        
        # DLiSA needs to know the limits of the genes (knobs)
        # We have 2 Genes: [Green_NS, Green_EW]
        # Range: 10 seconds to 90 seconds
        self.n_dim = 2
        self.bounds = [[10, 90], [10, 90]] 
        
        # We have 1 Objective: Minimize Waiting Time
        self.n_obj = 1
        # checkpoint for the start of every evaluation
        self.checkpoint_paths = []

    def set_checkpoints(self, paths):
        self.checkpoint_paths = paths or []

    def evaluate(self, configuration):
        """
        DLiSA calls this to test a specific setting.
        """
        # 1. Apply the settings (Convert float to int because SUMO needs integers)
        green_ns = int(configuration[0])
        green_ew = int(configuration[1])
        
        # Safety check: Ensure values are within bounds
        green_ns = max(10, min(90, green_ns))
        green_ew = max(10, min(90, green_ew))
        
        WARMUP_STEPS = 30
        MEASURE_STEPS = 200

        # If no checkpoints configured, evaluate once on current sim state
        ckpts = self.checkpoint_paths if self.checkpoint_paths else [None]

        replicate_costs = []

        for ckpt in ckpts:
            # 1) reset to baseline for this replication
            if ckpt is not None:
                self.adapter.load_checkpoint(ckpt)

            # 2) apply candidate
            self.adapter.apply_configuration(green_ns, green_ew)

            # 3) warm-up
            for _ in range(WARMUP_STEPS):
                self.adapter.run_step()

            # 4) measure delta waiting
            self.adapter.reset_waiting_meter()
            cost = 0.0
            for _ in range(MEASURE_STEPS):
                self.adapter.run_step()
                cost += self.adapter.get_delta_waiting_time_step()

            replicate_costs.append(cost)

        # Mean across replications
        mean_cost = float(np.mean(replicate_costs))
        return [mean_cost]

    def get_current_context(self):
        """
        DLiSA calls this to see the 'Workload'
        """
        state = self.adapter.get_state()
        return np.array(state)
