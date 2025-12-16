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


def generate_timeline_route_file(timeline, output_path="traffic_env/routes.rou.xml"):
    """
    timeline: list of dicts, e.g.
    [
      {"name":"NS_Heavy", "begin":0, "end":600},
      {"name":"Balanced", "begin":600, "end":1200},
      {"name":"EW_Heavy", "begin":1200, "end":1800},
    ]
    Writes multiple flows with begin/end windows so traffic changes dynamically over time.
    """

    scenario_map = {
        "NS_Heavy": (0.5, 0.05),
        "EW_Heavy": (0.05, 0.5),
        "Balanced": (0.2, 0.2),
    }

    os.makedirs("traffic_env", exist_ok=True)

    with open(output_path, "w") as routes:
        print("""<routes>
    <vType id="standard_car" accel="0.8" decel="4.5" sigma="0.5" length="5" minGap="2.5" maxSpeed="16.67" guiShape="passenger"/>
""", file=routes)

        # Routes (same as your current generator)
        print('    <route id="route_NS" edges="B1A1 A1B3"/>', file=routes)
        print('    <route id="route_SN" edges="B3A1 A1B1"/>', file=routes)
        print('    <route id="route_EW" edges="B4A1 A1B2"/>', file=routes)
        print('    <route id="route_WE" edges="B2A1 A1B4"/>', file=routes)

        # Timeline flows (each segment gets its own set of 4 flows)
        for i, seg in enumerate(timeline):
            name = seg["name"]
            begin = int(seg["begin"])
            end = int(seg["end"])

            if name not in scenario_map:
                raise ValueError(f"Unknown segment name: {name}")

            prob_NS, prob_EW = scenario_map[name]

            print(f'    <flow id="flow_NS_{i}" type="standard_car" route="route_NS" begin="{begin}" end="{end}" probability="{prob_NS}"/>', file=routes)
            print(f'    <flow id="flow_SN_{i}" type="standard_car" route="route_SN" begin="{begin}" end="{end}" probability="{prob_NS}"/>', file=routes)
            print(f'    <flow id="flow_EW_{i}" type="standard_car" route="route_EW" begin="{begin}" end="{end}" probability="{prob_EW}"/>', file=routes)
            print(f'    <flow id="flow_WE_{i}" type="standard_car" route="route_WE" begin="{begin}" end="{end}" probability="{prob_EW}"/>', file=routes)

        print("</routes>", file=routes)

    print(f"--> Generated TIMELINE routes file with {len(timeline)} segments: {output_path}")




def build_random_cycling_timeline(scenarios=("NS_Heavy", "Balanced", "EW_Heavy"), segment_len=200, n_cycles=3, seed=123, t0=0):
    """
    Returns a timeline like:
    [
      {"name":"EW_Heavy", "begin":0, "end":200},
      {"name":"NS_Heavy", "begin":200, "end":400},
      ...
    ]
    Random order each cycle, repeats for n_cycles.
    Total duration = len(scenarios) * segment_len * n_cycles.
    """
    rng = random.Random(seed)

    timeline = []
    t = int(t0)

    last_order = None
    for _ in range(n_cycles):
        order = list(scenarios)
        rng.shuffle(order)

        # optional: avoid repeating exact same order twice
        if last_order is not None and order == last_order and len(order) > 1:
            order.reverse()
        last_order = order

        for name in order:
            timeline.append({"name": name, "begin": t, "end": t + segment_len})
            t += segment_len

    return timeline


def generate_timeline_route_file(timeline, output_path="traffic_env/routes.rou.xml"):
    """
    Write one routes file whose flows change over time by using begin/end windows.

    timeline: list of {"name": scenario, "begin": int, "end": int}
    """
    scenario_map = {
        "NS_Heavy": (0.5, 0.05),
        "EW_Heavy": (0.05, 0.5),
        "Balanced": (0.2, 0.2),
    }

    os.makedirs("traffic_env", exist_ok=True)

    with open(output_path, "w") as routes:
        print("""<routes>
    <vType id="standard_car" accel="0.8" decel="4.5" sigma="0.5" length="5" minGap="2.5" maxSpeed="16.67" guiShape="passenger"/>
""", file=routes)

        # same routes as your current generator :contentReference[oaicite:1]{index=1}
        print('    <route id="route_NS" edges="B1A1 A1B3"/>', file=routes)
        print('    <route id="route_SN" edges="B3A1 A1B1"/>', file=routes)
        print('    <route id="route_EW" edges="B4A1 A1B2"/>', file=routes)
        print('    <route id="route_WE" edges="B2A1 A1B4"/>', file=routes)

        # timeline segments: each segment gets 4 flows with begin/end
        for i, seg in enumerate(timeline):
            name = seg["name"]
            begin = int(seg["begin"])
            end = int(seg["end"])

            if name not in scenario_map:
                raise ValueError(f"Unknown segment name: {name}")

            prob_NS, prob_EW = scenario_map[name]

            print(f'    <flow id="flow_NS_{i}" type="standard_car" route="route_NS" begin="{begin}" end="{end}" probability="{prob_NS}"/>', file=routes)
            print(f'    <flow id="flow_SN_{i}" type="standard_car" route="route_SN" begin="{begin}" end="{end}" probability="{prob_NS}"/>', file=routes)
            print(f'    <flow id="flow_EW_{i}" type="standard_car" route="route_EW" begin="{begin}" end="{end}" probability="{prob_EW}"/>', file=routes)
            print(f'    <flow id="flow_WE_{i}" type="standard_car" route="route_WE" begin="{begin}" end="{end}" probability="{prob_EW}"/>', file=routes)

        print("</routes>", file=routes)

    total_end = max(seg["end"] for seg in timeline) if timeline else 0
    print(f"--> Generated TIMELINE routes file: {output_path} (end={total_end})")


if __name__ == "__main__":
    # Test run: Generates a Heavy North-South file immediately
    generate_route_file("NS_Heavy")
