import time
import os
import shutil
import numpy as np # Make sure to install numpy: pip install numpy
import json
from tools.workload_generator import generate_route_file, generate_timeline_route_file, build_random_cycling_timeline
from adapters.sumo_adapter import SumoAdapter
from dlisa_bridge import SumoBridge, AdaptationOptimizer
import argparse

# ==========================================
# MONKEY PATCH 1: FIX INITIALIZATION CRASH
# ==========================================
def patched_initialize_population(self, config_space, required_size, existing_configs=None, existing_ids=None):
    """
    A simple replacement for the crashing initialize_population method.
    Generates random configurations as NumPy arrays.
    """
    print("   [Patch] Generating initial population using fixed logic...")
    population = []
    
    # Ensure config_space is a numpy array
    bounds = np.array(config_space)
    
    for _ in range(required_size):
        # Generate a random configuration
        # Gene 0: Green NS, Gene 1: Green EW
        config = []
        for i in range(len(bounds)):
            low = bounds[i][0]
            high = bounds[i][1]
            val = np.random.randint(low, high + 1)
            config.append(val)
        
        # CRITICAL FIX: Convert to NumPy array
        population.append(np.array(config))
        
    return population

# Apply Patch 1
AdaptationOptimizer.initialize_population = patched_initialize_population


# ==========================================
# MONKEY PATCH 2: ENABLE EVOLUTION (AI)
# ==========================================
def patched_generate_offspring(self, evaluated_population, pop_size):
    """
    Implements a Standard Genetic Algorithm (Selection -> Crossover -> Mutation).
    This fixes the 'AttributeError' and allows the system to learn.
    """
    print("     [Patch] Running Evolutionary Logic (Selection -> Crossover -> Mutation)...")
    
    # 1. SELECTION: Sort all past results by cost (Lowest is better)
    # structure: [ [config_array, [cost]], ... ]
    sorted_pop = sorted(evaluated_population, key=lambda x: x[1][0])
    
    # Keep the top 50% best parents
    n_parents = max(1, len(sorted_pop) // 2)
    parents = [item[0] for item in sorted_pop[:n_parents]]
    
    offspring = []
    
    # 2. CROSSOVER & MUTATION: Create new children
    while len(offspring) < pop_size:
        # Pick two random parents
        p1 = parents[np.random.randint(len(parents))]
        p2 = parents[np.random.randint(len(parents))]
        
        # Crossover: Mix genes (Child gets half from P1, half from P2)
        child = [p1[0], p2[1]]
        
        # Mutation: 30% chance to tweak the timing
        if np.random.rand() < 0.3:
            gene_idx = np.random.randint(2) # Pick gene 0 or 1
            change = np.random.randint(-10, 11) # Change by -10 to +10 seconds
            child[gene_idx] += change
            
            # Clamp: Ensure valid traffic light bounds (10s to 90s)
            child[gene_idx] = max(10, min(90, child[gene_idx]))
        
        # Convert to numpy for consistency
        offspring.append(np.array(child))
        
    return offspring

# Apply Patch 2 dynamically
AdaptationOptimizer.generate_offspring = patched_generate_offspring
# ==========================================

def classify_workload(state):
    qN, qS, qE, qW = state
    ns = qN + qS
    ew = qE + qW
    ratio = ns / (ew + 1e-9)

    if ratio >= 2.0:
        return "NS_Heavy", ratio, ns, ew
    if ratio <= 0.5:
        return "EW_Heavy", ratio, ns, ew
    return "Balanced", ratio, ns, ew


def run_workload_detector_demo():
    # timeline
    segment_len = 200
    n_cycles = 3
    seed = 123

    timeline = build_random_cycling_timeline(segment_len=segment_len, n_cycles=n_cycles, seed=seed)
    generate_timeline_route_file(timeline)
    total_end = timeline[-1]["end"] if timeline else 0

    # detector settings (your request: keep state for 100–300 steps)
    HOLD_STEPS = 200      # set to 100..300
    CHECK_EVERY = 25

    env = SumoAdapter(gui=True)
    env.start(seed=seed)
    bridge = SumoBridge(env)

    bridge.adapter.apply_configuration(30, 30)

    held_label = None
    hold_until = -1

    try:
        for t in range(total_end + 1):
            bridge.adapter.run_step()

            # stop once flows ended and no vehicles remain
            if t >= total_end and traci.simulation.getMinExpectedNumber() == 0:
                print(f"\n[INFO] No more vehicles expected at t={t}. Closing.\n")
                break

            if t % CHECK_EVERY != 0:
                continue

            state = bridge.adapter.get_state()
            raw_label, ratio, ns, ew = classify_workload(state)

            # initialize held label once
            if held_label is None:
                held_label = raw_label
                hold_until = t + HOLD_STEPS
                print(f"\n[DETECT] INITIAL @ t={t}: {held_label} (hold at least{HOLD_STEPS})\n")

            # change only if hold expired
            if t >= hold_until and raw_label != held_label:
                prev = held_label
                held_label = raw_label
                hold_until = t + HOLD_STEPS
                print(f"\n[DETECT] CHANGE @ t={t}: {prev} -> {held_label} (hold {HOLD_STEPS})\n")

            print(f"[MON] t={t:4d} raw={raw_label:9s} held={held_label:9s} q={state} NS={ns:3d} EW={ew:3d} NS/EW={ratio:5.2f}")

            time.sleep(0.02)

    except KeyboardInterrupt:
        print("\nStopping detector...")

    finally:
        env.close()
def run_dynamic_timeline_demo():
    """
    Demo only: dynamic traffic workload changes in ONE SUMO run.
    Random order per cycle, cycles back multiple times.
    Prints segment changes + queue feedback so you can verify it works.
    """
    # Keep total duration <= 2000 to match your previous default horizon :contentReference[oaicite:2]{index=2}
    segment_len = 200
    n_cycles = 3
    seed = 123

    timeline = build_random_cycling_timeline(
        segment_len=segment_len,
        n_cycles=n_cycles,
        seed=seed
    )

    # Generate dynamic routes file
    generate_timeline_route_file(timeline)

    # Print the schedule so you know what's coming
    print("\n=== TIMELINE SCHEDULE ===")
    for seg in timeline:
        print(f"  {seg['begin']:>4}..{seg['end']:<4}  {seg['name']}")
    total_end = timeline[-1]["end"] if timeline else 0
    print("=========================\n")

    # Start SUMO
    env = SumoAdapter(gui=True)
    env.start(seed=seed)
    bridge = SumoBridge(env)

    # fixed light config so you can observe demand changes (not adaptation yet)
    fixed = (30, 30)
    bridge.adapter.apply_configuration(*fixed)

    seg_idx = 0
    next_switch = timeline[0]["end"] if timeline else None

    # Run until end of timeline
    for t in range(total_end):
        bridge.adapter.run_step()

        # detect segment boundary (purely for logging; flows switch automatically)
        if next_switch is not None and t + 1 == next_switch:
            seg_idx += 1
            if seg_idx < len(timeline):
                print(f"\n=== SWITCH @ t={t+1}: now entering {timeline[seg_idx]['name']} ({timeline[seg_idx]['begin']}..{timeline[seg_idx]['end']}) ===")
                next_switch = timeline[seg_idx]["end"]
            else:
                next_switch = None

        # periodic feedback
        if t % 50 == 0:
            qN, qS, qE, qW = bridge.adapter.get_state()
            ns = qN + qS
            ew = qE + qW
            ratio = (ns / ew) if ew > 0 else float("inf")
            cur_seg = timeline[seg_idx]["name"] if seg_idx < len(timeline) else "DONE"
            print(f"t={t:4d} seg={cur_seg:9s} q=[{qN},{qS},{qE},{qW}] NS={ns:3d} EW={ew:3d} NS/EW={ratio:5.2f}")

        time.sleep(0.02)  # make it watchable

    env.close()
    print("\nDemo finished.")



def run_dlisa_live():
    # 1. SETUP
    scenarios = ["NS_Heavy", "Balanced", "EW_Heavy"]
    kb_path = "./dlisa_knowledge/knowledge.json"
    
    # Create folder if missing
    if not os.path.exists("./dlisa_knowledge"): 
        os.makedirs("./dlisa_knowledge")

    # Load existing memory if file exists
    knowledge_base = {}
    if os.path.exists(kb_path):
        with open(kb_path, 'r') as f:
            try:
                knowledge_base = json.load(f)
            except json.JSONDecodeError:
                knowledge_base = {}
        print(f"-> Loaded Knowledge Base: {len(knowledge_base)} scenarios known.")

    print("=== DLiSA TRAFFIC OPTIMIZATION (LIVE MODE) STARTED ===")

    # 2. INITIALIZE ENVIRONMENT & BRIDGE
    # Just to init the bridge object, we run a quick dummy start
    generate_route_file("Balanced")
    init_env = SumoAdapter(gui=False) # No GUI for init
    init_env.start()
    bridge = SumoBridge(init_env)
    
    # 3. INITIALIZE THE OPTIMIZER
    print("-> Initializing Adaptation Optimizer...")
    planner = AdaptationOptimizer(
        max_generation=10, 
        pop_size=5,
        mutation_rate=0.1, 
        crossover_rate=0.8, 
        compared_algorithms=["DLiSA"], 
        system=bridge,
        optimization_goal="Minimize_Time"
    )
    init_env.close()

    # 4. MAIN LOOP
    for scenario in scenarios:
        print(f"\n\n>>> SCENARIO: {scenario} <<<")
        generate_route_file(scenario)
        
        # === START INTELLIGENCE CHECK ===
        best_config = None
        best_cost = float('inf')

        # CHECK 1: Do we remember this scenario?
        if scenario in knowledge_base:
            print(f"   [MEMORY] I recognize '{scenario}'! Retrieving solution...")
            best_config = np.array(knowledge_base[scenario]['config'])
            best_cost = knowledge_base[scenario]['cost']
            print(f"   [MEMORY] Instant Winner: {best_config} (Saved Cost: {best_cost})")
            
            # Start SUMO just to show the winner
            env = SumoAdapter(gui=True)
            env.start()
            bridge.adapter = env
            
        else:
            # CHECK 2: No memory? We must learn (Run the EVOLUTIONARY LOOP)
            print(f"   [UNKNOWN] Never seen '{scenario}' before. Starting AI Optimization...")
            
            
            # --- START EVOLUTION (The "AI" Part) ---
            import argparse

            # checkpoint setup
            PRELOAD_STEPS = 200  # how long to run before capturing baseline
            ckpt_dir = "./traffic_env/checkpoints"
            os.makedirs(ckpt_dir, exist_ok=True)

            checkpoint_paths = []
            for seed in [1,2,3]:

                tmp = SumoAdapter(gui=False)
                tmp.start(seed=seed)

                bridge.adapter = tmp  # so run_step uses the active sim

                for _ in range(PRELOAD_STEPS):
                    tmp.run_step()

                ckpt_path = os.path.abspath(os.path.join(ckpt_dir,f"{scenario}_seed{seed}.xml"))
                tmp.save_checkpoint(ckpt_path)
                checkpoint_paths.append(ckpt_path)

                tmp.close()

            bridge.set_checkpoints(checkpoint_paths)

            print(f"   [CHECKPOINTS] Using {len(checkpoint_paths)} replications.")

            env = SumoAdapter(gui=True)
            env.start()
            bridge.adapter = env

            # Generation 0: Random Guesses
            population = planner.initialize_population(
                config_space=bridge.bounds, 
                required_size=5
            )
            
            # We need to track history so DLiSA can learn
            evaluated_history = [] 

            # Run for 3 Generations (0, 1, 2)
            generations = 4
            for gen in range(generations):
                print(f"\n     --- GENERATION {gen} ---")
                current_gen_results = []
                
                # Evaluate this generation
                for i, config in enumerate(population):
                    print(f"     [Gen {gen} | Cand {i}] Testing Config: {config}")
                    costs = bridge.evaluate(config)
                    cost = costs[0]
                    print(f"        -> Cost: {cost}")
                    
                    # Store result: [config, [cost]]
                    current_gen_results.append([config, [cost]])

                    # Check if this is the all-time best
                    if cost < best_cost:
                        best_cost = cost
                        best_config = config
                        print(f"        (New Best Found!)")

                # Add to history
                evaluated_history.extend(current_gen_results)

                # CREATE NEXT GENERATION (Evolution)
                if gen < generations-1: # Don't breed after the last generation
                    print("     [AI] Evolving new population based on results...")
                    population = planner.generate_offspring(
                        evaluated_history, 
                        pop_size=5
                    )
            
            # --- END EVOLUTION ---

            # Step C: SAVE TO MEMORY
            print(f"   [LEARNING] Optimization complete. Best: {best_config}")
            print("   [LEARNING] Storing solution to Knowledge Base...")
            
            knowledge_base[scenario] = {
                'config': [int(best_config[0]), int(best_config[1])],
                'cost': best_cost
            }
            with open(kb_path, 'w') as f:
                json.dump(knowledge_base, f, indent=4)

        # === APPLY WINNER ===
        print(f"   >>> APPLYING WINNER: {best_config}")
        print("   >>> Holding for 15 seconds to demonstrate flow...")
        
        bridge.adapter.apply_configuration(int(best_config[0]), int(best_config[1]))
        
        # Run simulation for a while so you can see the result
        for _ in range(150): 
            bridge.adapter.run_step()
            time.sleep(0.05) # Small sleep to make it watchable
            
        env.close()

def _parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "mode",
        nargs="?",
        default="testing",
        choices=["testing", "demo", "detect"],
        help="Run mode: testing (default), demo, detect",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()

    if args.mode == "demo":
        run_dynamic_timeline_demo()
    elif args.mode == "detect":
        run_workload_detector_demo()
    else:
        run_dlisa_live()
