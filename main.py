import os
import sys
import time

import numpy as np

from adapters.sumo_adapter import SumoAdapter
from dlisa_bridge import SumoBridge
from dlisa_source.Adaptation_Optimizer import AdaptationOptimizer
from dlisa_source.Genetic_Algorithm import GeneticAlgorithm
from tools.workload_generator import build_random_cycling_timeline, generate_timeline_route_file

###### Global definitions of configurable parameters
### Timeline creation
TIMELINE_SEGMENT_LENGTH = 200
TIMELINE_CYCLE_COUNT = 3
###
### Optimizer
OPTIMIZER_MAX_GENERATION = 5
OPTIMIZER_POPULATION_SIZE = 5
OPTIMIZER_MUTATION_RATE = 0.1
OPTIMIZER_CROSS_RATE = 0.8
###
### Live simulation
LIVE_START_CONFIG = [30, 30]
CHECK_EVERY = 25
MIN_STABLE_CLASSIFICATIONS = 6
MIN_HALTED_CARS = 6
###
######


def classify_workload(halting_state, density_state, queue_threshold=10, flow_ratio_threshold=2.0):
    """
    Classifies workload using both Queue Length (Halting) and Traffic Density (Total Vehicles).

    halting_state: [qN, qS, qE, qW] - Cars actually stopped.
    density_state: [tN, tS, tE, tW] - Total cars on the lane.
    """
    # Unpack
    q_ns1, q_ns2, q_ew1, q_ew2 = halting_state
    t_ns1, t_ns2, t_ew1, t_ew2 = density_state

    # 1. Calculate Queue Severity (The "Pain")
    ns_queue = q_ns1 + q_ns2
    ew_queue = q_ew1 + q_ew2

    # 2. Calculate Total Demand (The "Volume")
    ns_volume = t_ns1 + t_ns2
    ew_volume = t_ew1 + t_ew2

    # 3. Determine Load Status based on Queues (Priority to stopped cars)
    ns_is_critical = ns_queue > queue_threshold
    ew_is_critical = ew_queue > queue_threshold

    # --- CLASSIFICATION LOGIC ---

    # CASE A: Saturation (Gridlock)
    # Both sides are critical.
    # OR: One side is critical, and the other has high moving volume (approaching saturation).
    if (ns_is_critical and ew_is_critical) or \
            (ns_is_critical and ew_volume > queue_threshold) or \
            (ew_is_critical and ns_volume > queue_threshold):
        return "Saturated", 1.0, ns_queue, ew_queue

    # CASE B: Directional Heaviness (Critical Queues)
    if ns_is_critical:
        ratio = ns_queue / max(1, ew_queue)
        return "NS_Heavy", ratio, ns_queue, ew_queue

    if ew_is_critical:
        ratio = ew_queue / max(1, ns_queue)
        return "EW_Heavy", ratio, ns_queue, ew_queue

    # CASE C: High Flow, Low Queue (The "Green Wave" Scenario)
    # Cars are moving but not stopping. We shouldn't label this "Light".
    # We check Volume Ratios.
    if ns_volume > queue_threshold or ew_volume > queue_threshold:
        # If queues are low but volume is high, use Volume Ratio
        vol_ratio = ns_volume / max(1, ew_volume)
        if vol_ratio >= flow_ratio_threshold:
            return "NS_Flow", vol_ratio, ns_volume, ew_volume
        elif vol_ratio <= (1 / flow_ratio_threshold):
            return "EW_Flow", (1 / vol_ratio), ns_volume, ew_volume
        else:
            return "High_Volume_Balanced", 1.0, ns_volume, ew_volume

    # CASE D: Ghost Town (Low Queue, Low Volume)
    return "Light_Balanced", 1.0, ns_queue, ew_queue


def optimize_in_twin(live_optimizer, workload_label, initial_population, initial_ids, twin_bridge, cp_file):
    """
    Runs the Genetic Algorithm inside the Cyber-Twin
    """
    # Setup Twin Environment
    # TODO: Seed?
    twin_bridge.adapter.start(seed=42)  # Deterministic for fairness
    twin_bridge.adapter.load_checkpoint(cp_file)

    # Run Evolution
    ga = live_optimizer.ga_worker

    final_pop, final_perfs, final_ids, evaluated_map = ga.run(
        init_pop_config=initial_population,
        init_pop_config_ids=initial_ids,
        config_space=twin_bridge.bounds,
        perf_space=None,
        max_generation=live_optimizer.max_generation,
        bridge=twin_bridge
    )

    twin_bridge.adapter.close()

    # Return results for DLiSA memory
    return final_pop, final_perfs, evaluated_map


def get_actual_workload_label(timeline, current_time_step):
    """
    Finds the ground truth workload label for a specific time step
    based on the generated timeline.
    """
    for segment in timeline:
        # Check if the current time falls within this segment's window
        if segment["begin"] <= current_time_step < segment["end"]:
            return segment["name"]

    return "Unknown"  # Should not happen


def run_cyber_twin_demo():
    # Set up a random timeline of scenarios
    # TODO: Seed?
    timeline = build_random_cycling_timeline(segment_len=TIMELINE_SEGMENT_LENGTH, n_cycles=TIMELINE_CYCLE_COUNT, seed=42)
    generate_timeline_route_file(timeline)
    end_time = timeline[-1]["end"]

    live_optimizer = AdaptationOptimizer(
        max_generation=OPTIMIZER_MAX_GENERATION,
        pop_size=OPTIMIZER_POPULATION_SIZE,
        mutation_rate=OPTIMIZER_MUTATION_RATE,
        crossover_rate=OPTIMIZER_CROSS_RATE,
        compared_algorithms=["DLiSA"],
        system="TrafficLights",  # Not really used, we pass bridge manually
        optimization_goal="minimum"
    )

    # Attach a GA worker to the live_optimizer for convenience
    live_optimizer.ga_worker = GeneticAlgorithm(5, 0.1, 0.8, "minimum")

    # Live Simulation Setup
    live_sumo_simulation = SumoAdapter(gui=True, label="live", port=8813)
    # TODO: Seed?
    live_sumo_simulation.start()
    live_bridge = SumoBridge(live_sumo_simulation)

    crt_config = LIVE_START_CONFIG
    live_bridge.adapter.apply_configuration(crt_config[0], crt_config[1])

    # Detection Loop parameter initializations
    crt_workload = None
    candidate_workload = None
    stable = 0

    try:
        for t in range(end_time + 1):
            live_sumo_simulation.run_step()

            # Get current state - number of stopped vehicles and number of total vehicles
            halting_state, density_state = live_sumo_simulation.get_state()
            # Classify current state (detect if workload changed)
            detected_workload, ratio, ns_stopped, ew_stopped = classify_workload(halting_state, density_state)

            # Stability logic
            # - do not change configuration if not sure that workload changed
            # - do not change configuration if too few cars are waiting
            if (ns_stopped + ew_stopped) < MIN_HALTED_CARS and crt_workload is not None:
                detected_workload = crt_workload

            if detected_workload != candidate_workload:
                candidate_workload = detected_workload
                stable = 1
            else:
                stable += 1

            real_workload = get_actual_workload_label(timeline, t)
            print(f"[MON] t={t} Real Workload={real_workload} Detected Workload={detected_workload} Config={crt_config} Halting state={halting_state} Density state={density_state}")

            # New workload detected - optimize configuration
            if t % CHECK_EVERY == 0 and stable >= MIN_STABLE_CLASSIFICATIONS and candidate_workload != crt_workload:
                print(f"\n[DLiSA] New Workload Detected: {candidate_workload}")

                # Ask DLiSA for Initial Population (Seeding vs Random)
                # We pass the bounds as 'config_space'
                init_pop, init_ids = live_optimizer.generate_next_population(
                    config_space=np.array(live_bridge.bounds),
                    selected_algorithm='DLiSA',
                    environment_name=candidate_workload
                )

                # Run Optimization in Cyber-Twin
                cp_file = os.path.join(os.getcwd(), 'traffic_env/crt_live_cp.xml')
                live_bridge.adapter.save_checkpoint(cp_file)

                print("   [DLiSA] Running Cyber-Twin Simulation...")
                best_pop, best_perfs, eval_map = optimize_in_twin(
                    live_optimizer, candidate_workload, init_pop, init_ids,
                    SumoBridge(SumoAdapter(gui=False, label="twin", port=9999)), cp_file
                )

                # Register Results (Learning)
                live_optimizer.register_workload_result(
                    environment_name=candidate_workload,
                    population_configs=best_pop,
                    population_perfs=best_perfs,
                    evaluated_configs_map=eval_map
                )

                # Apply Winner to Live System
                best_idx = np.argmin(best_perfs)
                winner = best_pop[best_idx]
                print(f"   [DLiSA] Optimization Done. Applying: {winner}")
                live_bridge.adapter.apply_configuration(winner[0], winner[1])

                crt_config = winner
                crt_workload = candidate_workload

            time.sleep(0.01)
    finally:
        live_sumo_simulation.close()


if __name__ == "__main__":
    # Ensure SUMO_HOME is set
    if 'SUMO_HOME' in os.environ:
        tools = os.path.join(os.environ['SUMO_HOME'], 'tools')
        sys.path.append(tools)
    else:
        sys.exit("please declare environment variable 'SUMO_HOME'")
    run_cyber_twin_demo()
