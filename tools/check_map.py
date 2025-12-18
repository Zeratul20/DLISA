import sumolib
import os

# Path to your network file
net_file = "traffic_env/cross.net.xml"

if not os.path.exists(net_file):
    print(f"Error: Could not find {net_file}")
else:
    net = sumolib.net.readNet(net_file)
    print(f"\nScanning {net_file} for incoming lanes...\n")
    
    for edge in net.getEdges():
        # Get the angle of the edge (0=North, 90=East, 180=South, 270=West)
        # Note: In SUMO, an angle of 180 means the road goes South (so traffic comes FROM North)
        angle = net.getEdge(edge.getID()).getAngle() 
        lane_id = edge.getLanes()[0].getID() # Get the first lane of this edge
        
        direction = "Unknown"
        # Determine direction based on where traffic is GOING
        if -45 < angle <= 45:    direction = "Northbound (Traffic from South)"
        elif 45 < angle <= 135:  direction = "Eastbound  (Traffic from West)"
        elif 135 < angle <= 225: direction = "Southbound (Traffic from North)"
        elif 225 < angle <= 315: direction = "Westbound  (Traffic from East)"
            
        print(f"Direction: {direction:30} | Edge ID: {edge.getID():10} | Lane ID: {lane_id}")