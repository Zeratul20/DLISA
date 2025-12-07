import os
import random

def generate_route_file(scenario_type="balanced"):
    """
    Generates a SUMO routes file based on the scenario.
    - NS_Heavy: Lots of cars on the B1 <-> B3 axis.
    - EW_Heavy: Lots of cars on the B2 <-> B4 axis.
    - Balanced: Equal traffic everywhere.
    """
    
    # 1. Define Traffic Probabilities (Cars per second)
    # 0.5 = A car every 2 seconds (Heavy)
    # 0.05 = A car every 20 seconds (Light)
    
    if scenario_type == "NS_Heavy":
        prob_NS = 0.5  # Heavy traffic North-South
        prob_EW = 0.05 # Light traffic East-West
    elif scenario_type == "EW_Heavy":
        prob_NS = 0.05
        prob_EW = 0.5
    else: # Balanced
        prob_NS = 0.2
        prob_EW = 0.2

    # 2. Write the XML file
    # Ensure directory exists
    os.makedirs("traffic_env", exist_ok=True)
    
    with open("traffic_env/routes.rou.xml", "w") as routes:
        # Header
        print("""<routes>
    <vType id="standard_car" accel="0.8" decel="4.5" sigma="0.5" length="5" minGap="2.5" maxSpeed="16.67" guiShape="passenger"/>
    """, file=routes)

        # --- THE KEY CHANGE IS HERE (Route Definitions) ---
        # We define the paths using the IDs you found with the script.
        
        # PAIR 1: B1 <-> B3
        print('    <route id="route_NS" edges="B1A1 A1B3"/>', file=routes)
        print('    <route id="route_SN" edges="B3A1 A1B1"/>', file=routes)
        
        # PAIR 2: B4 <-> B2
        print('    <route id="route_EW" edges="B4A1 A1B2"/>', file=routes)
        print('    <route id="route_WE" edges="B2A1 A1B4"/>', file=routes)
        
        # --------------------------------------------------

        # 3. Define Flows (The stream of cars using those routes)
        print(f'    <flow id="flow_NS" type="standard_car" route="route_NS" begin="0" end="2000" probability="{prob_NS}"/>', file=routes)
        print(f'    <flow id="flow_SN" type="standard_car" route="route_SN" begin="0" end="2000" probability="{prob_NS}"/>', file=routes)
        print(f'    <flow id="flow_EW" type="standard_car" route="route_EW" begin="0" end="2000" probability="{prob_EW}"/>', file=routes)
        print(f'    <flow id="flow_WE" type="standard_car" route="route_WE" begin="0" end="2000" probability="{prob_EW}"/>', file=routes)
        
        print("</routes>", file=routes)

    print(f"--> Generated Traffic Scenario: {scenario_type}")

if __name__ == "__main__":
    # Test run: Generates a Heavy North-South file immediately
    generate_route_file("NS_Heavy")