import time
import os
import shutil
import numpy as np # Make sure to install numpy: pip install numpy
import json
from tools.workload_generator import generate_route_file
from adapters.sumo_adapter import SumoAdapter
from dlisa_bridge import SumoBridge, AdaptationOptimizer

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
        bridge.set_checkpoint(None)
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
            
            env = SumoAdapter(gui=True)
            env.start()
            bridge.adapter = env
            
            # --- START EVOLUTION (The "AI" Part) ---
            

            # checkpoint setup
            PRELOAD_STEPS = 200  # how long to run before capturing baseline
            for _ in range(PRELOAD_STEPS):
                bridge.adapter.run_step()

            ckpt_dir = "./traffic_env/checkpoints"
            os.makedirs(ckpt_dir, exist_ok=True)
            ckpt_path = os.path.abspath(os.path.join(ckpt_dir, f"{scenario}.xml"))

            bridge.adapter.save_checkpoint(ckpt_path)
            bridge.set_checkpoint(ckpt_path)

            print(f"   [CHECKPOINT] Baseline saved: {ckpt_path}")


            # Generation 0: Random Guesses
            population = planner.initialize_population(
                config_space=bridge.bounds, 
                required_size=5
            )
            
            # We need to track history so DLiSA can learn
            evaluated_history = [] 

            # Run for 3 Generations (0, 1, 2)
            for gen in range(9):
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
                if gen < 2: # Don't breed after the last generation
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

if __name__ == "__main__":
    run_dlisa_live()
