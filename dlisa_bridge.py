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
        
        self.adapter.apply_configuration(green_ns, green_ew)
        
        # 2. Run simulation step to let traffic react
        # We run 50 steps (seconds) to get a stable measurement
        for _ in range(50):
            self.adapter.run_step()
            
        # 3. Measure cost
        cost = self.adapter.get_reward_metric()
        
        # Return as list (because DLiSA supports multi-objective)
        return [cost]

    def get_current_context(self):
        """
        DLiSA calls this to see the 'Workload'
        """
        state = self.adapter.get_state()
        return np.array(state)