import numpy as np

###### Global definitions of configurable parameters
### Bounds
LIGHTS_TIME_BOUNDS = [[15, 60], [15, 60]]
###
### Evaluation parameters
WARMUP_STEPS = 30
MEASURE_STEPS = 100
###
######


class SumoBridge:
    """
    The interface between SUMO Simulation and the DLiSA Brain.
    """

    def __init__(self, sumo_adapter):
        self.adapter = sumo_adapter

        # DLiSA needs to know the limits of the genes (knobs)
        # We have 2 Genes: [Green_NS, Green_EW]
        self.n_dim = 2
        # [NS bounds, EW bounds]
        self.bounds = LIGHTS_TIME_BOUNDS
        self.checkpoint = None

    def evaluate(self, configuration, log=True):
        """
        DLiSA calls this to test a specific configuration.
        """
        # Apply the configuration
        green_ns = int(configuration[0])
        green_ew = int(configuration[1])

        # Safety check: Ensure values are within bounds
        green_ns = max(self.bounds[0][0], min(self.bounds[0][1], green_ns))
        green_ew = max(self.bounds[1][0], min(self.bounds[1][1], green_ew))

        replicate_costs = []

        # Load checkpoint for fresh evaluation
        if self.checkpoint:
            self.adapter.load_checkpoint(self.checkpoint)

            # Apply candidate
            self.adapter.apply_configuration(green_ns, green_ew, log)

            # Warm-up
            for _ in range(WARMUP_STEPS):
                self.adapter.run_step()

            # Measure delta waiting
            self.adapter.reset_waiting_meter()
            cost = 0.0
            for _ in range(MEASURE_STEPS):
                self.adapter.run_step()
                cost += self.adapter.get_delta_waiting_time_step()

                replicate_costs.append(cost)

        # Mean across replications
        mean_cost = float(np.mean(replicate_costs))
        return [mean_cost]
