import os
import random

SCENARIO_MAP = {
    "NS_Heavy": (0.5, 0.05),
    "EW_Heavy": (0.05, 0.5),
    "Balanced": (0.2, 0.2),
}


def generate_timeline_route_file(timeline, output_path="traffic_env/routes.rou.xml"):
    """
    Writes multiple flows with begin/end windows so traffic changes dynamically over time.
    """

    os.makedirs("traffic_env", exist_ok=True)

    with open(output_path, "w") as routes:
        print("""<routes>
    <vType id="standard_car" accel="0.8" decel="4.5" sigma="0.5" length="5" minGap="2.5" maxSpeed="16.67" guiShape="passenger"/>
""", file=routes)

        # Routes
        print('    <route id="route_NS" edges="B1A1 A1B3"/>', file=routes)
        print('    <route id="route_SN" edges="B3A1 A1B1"/>', file=routes)
        print('    <route id="route_EW" edges="B4A1 A1B2"/>', file=routes)
        print('    <route id="route_WE" edges="B2A1 A1B4"/>', file=routes)

        # Timeline flows (each segment gets its own set of 4 flows)
        for i, seg in enumerate(timeline):
            name = seg["name"]
            if name not in SCENARIO_MAP:
                raise ValueError(f"Unknown segment name: {name}")
            begin = int(seg["begin"])
            end = int(seg["end"])

            prob_NS, prob_EW = SCENARIO_MAP[name]

            print(
                f'    <flow id="flow_NS_{i}" type="standard_car" route="route_NS" begin="{begin}" end="{end}" probability="{prob_NS}"/>',
                file=routes)
            print(
                f'    <flow id="flow_SN_{i}" type="standard_car" route="route_SN" begin="{begin}" end="{end}" probability="{prob_NS}"/>',
                file=routes)
            print(
                f'    <flow id="flow_EW_{i}" type="standard_car" route="route_EW" begin="{begin}" end="{end}" probability="{prob_EW}"/>',
                file=routes)
            print(
                f'    <flow id="flow_WE_{i}" type="standard_car" route="route_WE" begin="{begin}" end="{end}" probability="{prob_EW}"/>',
                file=routes)

        print("</routes>", file=routes)

    print(f"--> Generated TIMELINE routes file with {len(timeline)} segments: {output_path}")


def build_random_cycling_timeline(segment_len, n_cycles, seed, t0=0):
    """
    Random order of predefined scenarios each cycle, repeats for n_cycles.
    Total duration = len(scenarios) * segment_len * n_cycles.
    """

    rng = random.Random(seed)

    timeline = []
    t = int(t0)

    last_order = None
    for _ in range(n_cycles):
        order = list(SCENARIO_MAP.keys())
        rng.shuffle(order)

        # avoid repeating exact same order twice
        if last_order is not None and order == last_order and len(order) > 1:
            order.reverse()
        last_order = order

        for name in order:
            timeline.append({"name": name, "begin": t, "end": t + segment_len})
            t += segment_len

    return timeline
