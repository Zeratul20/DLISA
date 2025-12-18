import sumolib

# Load the map
net = sumolib.net.readNet("traffic_env/cross.net.xml")

# 1. Find the Central Intersection (The Node with the most edges)
nodes = net.getNodes()
center_node = max(nodes, key=lambda n: len(n.getIncoming()) + len(n.getOutgoing()))
print(f"Detected Center Intersection ID: {center_node.getID()}")

# 2. Identify Incoming and Outgoing Edges
incoming_edges = center_node.getIncoming()
outgoing_edges = center_node.getOutgoing()

print("\n=== COPIABLE IDs FOR YOUR CODE ===")

directions = ["North", "East", "South", "West"]

# Helper to sort edges by angle so we know which is North/South/etc
# We sort by the angle of the edge starting point relative to the center
def get_edge_angle(edge):
    shape = edge.getShape()
    # Vector from start to end
    import math
    dx = shape[-1][0] - shape[0][0]
    dy = shape[-1][1] - shape[0][1]
    return math.atan2(dx, dy)

# Sort incoming edges: North (comes from top), East (from right), South (from bottom), West (from left)
# Note: This sorting might vary slightly, but usually:
# Incoming from North has a Southbound angle.
sorted_incoming = sorted(incoming_edges, key=get_edge_angle)
sorted_outgoing = sorted(outgoing_edges, key=get_edge_angle)

print("\n--- FOR ADAPTERS/SUMO_ADAPTER.PY (SENSORS) ---")
# We need edges COMING INTO the center.
# Usually sorted order is roughly: Southbound (from N), Westbound (from E), Northbound (from S), Eastbound (from W)
# Let's just print them with their specific IDs so you can plug them in.

for i, edge in enumerate(sorted_incoming):
    print(f"Incoming Edge {i+1} (ID: {edge.getID()}) -> Lane ID: {edge.getLanes()[0].getID()}")

print("\n--- FOR TOOLS/WORKLOAD_GENERATOR.PY (ROUTES) ---")
# We need pairs: Incoming -> Outgoing (Straight line)
# We assume the edge entering from North connects to the edge leaving to South.

for inc in sorted_incoming:
    # Find the outgoing edge that is "roughly straight" (angle difference ~ 180 degrees)
    best_out = None
    min_diff = 999
    
    inc_angle = get_edge_angle(inc)
    
    for out in sorted_outgoing:
        out_angle = get_edge_angle(out)
        diff = abs(inc_angle - out_angle)
        # We look for continuity, so the angle should be similar (straight line)
        if diff < min_diff:
            min_diff = diff
            best_out = out
            
    print(f"Route Pair: edges=\"{inc.getID()} {best_out.getID()}\"")