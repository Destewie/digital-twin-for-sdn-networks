#!/usr/bin/env python3
"""
test_dt_basic.py - Temporary test script to verify that rest_client and dt_model work together.

Usage:
    python3 test_dt_basic.py
"""

import sys
import json
from rest_client import RyuRestClient
from dt_model import DigitalTwin

def main():
    print("=== Test: Building Digital Twin from Ryu REST API ===\n")
    
    # 1. Connect to Ryu
    client = RyuRestClient("http://127.0.0.1:8080")
    
    # 2. Fetch all data
    print("Fetching data from Ryu...")
    switches = client.get_switches()
    links = client.get_links()
    hosts = client.get_hosts()
    
    if switches is None:
        print("[ERROR] Could not fetch switches. Is Ryu running?")
        sys.exit(1)
    
    print(f" - Switches: {len(switches)}")
    print(f" - Links: {len(links) if links else 0}")
    print(f" - Hosts: {len(hosts) if hosts else 0}")
    
    # 3. Create Digital Twin and populate topology
    dt = DigitalTwin()
    dt.update_switches(switches)
    dt.update_links(links)
    dt.update_hosts(hosts)
    
    # 4. Fetch and update statistics for each switch
    if switches:
        port_stats_dict = {}
        flow_stats_dict = {}
        for sw in switches:
            dpid = sw["dpid"]
            print(f"\nFetching stats for switch {dpid}...")
            port_stats = client.get_port_stats(dpid)
            flow_stats = client.get_flow_stats(dpid)
            if port_stats:
                port_stats_dict[dpid] = port_stats
                print(f"  - Port stats: {len(port_stats)} ports")
            else:
                print(f"  - Port stats: None (no traffic yet?)")
            if flow_stats:
                flow_stats_dict[dpid] = flow_stats
                print(f"  - Flow stats: {len(flow_stats)} flows")
            else:
                print(f"  - Flow stats: None")
        dt.update_port_stats(port_stats_dict)
        dt.update_flow_stats(flow_stats_dict)
    
    # 5. Show summary
    print("\n" + "="*50)
    print(dt.summary())
    
    # 6. Print some details (first few nodes/edges)
    print("\n--- Nodes ---")
    for node, attrs in list(dt.graph.nodes(data=True))[:10]:  # limit output
        node_type = attrs.get("type", "unknown")
        if node_type == "switch":
            print(f"Switch {node}: ports={len(attrs.get('ports', []))}, flows={len(attrs.get('flows', []))}")
        elif node_type == "host":
            print(f"Host {node}: MAC={attrs.get('mac')}, IP={attrs.get('ipv4')}, connected to switch {attrs.get('connected_to')}")
    
    print("\n--- Edges (switch‑switch) ---")
    for u, v, key, attrs in dt.graph.edges(keys=True, data=True):
        if attrs.get("type") == "switch_switch":
            state = "UP" if attrs.get("state") == 1 else "DOWN"
            print(f"{u} -- {v} (ports {attrs['src_port']}->{attrs['dst_port']}) [{state}]")
    
    print("\n--- Host‑Switch connections ---")
    for u, v, key, attrs in dt.graph.edges(keys=True, data=True):
        if attrs.get("type") == "host_switch":
            print(f"Host {u} connected to switch {v} on port {attrs['switch_port']}")
    
    # 7. Save to JSON file for later inspection
    json_file = "dt_snapshot.json"
    dt.to_json(json_file)
    print(f"\n[INFO] Digital Twin saved to {json_file}")
    
    # 8. Optional: compare with itself (should show no changes)
    print("\n--- Testing compare_and_log (should show no changes) ---")
    dt.compare_and_log(dt.to_dict())  # pass same state
    
    # 9. Try to load back and verify
    dt2 = DigitalTwin()
    dt2.from_json(json_file)
    print(f"\n[INFO] Reloaded from JSON: {dt2.summary()}")
    
    print("\n=== Test completed successfully ===")

if __name__ == "__main__":
    main()
