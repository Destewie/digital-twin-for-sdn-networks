"""
dt_model.py - Digital Twin representation using networkx.

Stores:
- Switches and hosts as separate nodes.
- Links switch‑switch and host‑switch as edges.
- Port statistics and flow statistics as node attributes.
"""

import networkx as nx
import json
from typing import Dict, List, Any, Optional, Tuple
import copy

class DigitalTwin:
    def __init__(self):
        """Initialize an empty MultiGraph for the digital twin."""
        self.graph = nx.MultiGraph()
        # Keep track of previous state for diff logging
        self._prev_state = None

    # ----------------------------------------------------------------------
    # Core update methods (called by sync loop)
    # ----------------------------------------------------------------------
    def update_switches(self, switches_data: Optional[List[Dict]]):
        """
        switches_data: list from /v1.0/topology/switches
        Each element: {"dpid": "0000...", "ports": [{"port_no": "...", "name": "...", "hw_addr": "..."}, ...]}
        """
        if switches_data is None:
            return
        current_dpids = set()
        for sw in switches_data:
            dpid = sw["dpid"]
            current_dpids.add(dpid)
            # Add node if not exists
            if not self.graph.has_node(dpid):
                self.graph.add_node(dpid, type="switch", dpid=dpid, ports=sw["ports"], port_stats={}, flows=[])
            else:
                # Update ports list (could change)
                self.graph.nodes[dpid]["ports"] = sw["ports"]
        # Remove switches no longer present
        for node in list(self.graph.nodes):
            if self.graph.nodes[node].get("type") == "switch" and node not in current_dpids:
                self.graph.remove_node(node)

    def update_links(self, links_data: Optional[List[Dict]]):
        """
        links_data: list from /v1.0/topology/links
        Each element: {"src": "dpid_src", "dst": "dpid_dst",
                       "src_port": "...", "dst_port": "...", "state": 0/1}
        """
        if links_data is None:
            return
        # Keep track of existing links to remove stale ones
        current_links = set()
        for link in links_data:
            src = link["src"]
            dst = link["dst"]
            src_port = link["src_port"]
            dst_port = link["dst_port"]
            state = link["state"]  # 0=down, 1=up
            key = (src, dst, src_port, dst_port)
            current_links.add(key)
            # Add edge if not exists, else update state
            if not self.graph.has_edge(src, dst, key=key):
                self.graph.add_edge(src, dst, key=key, type="switch_switch",
                                    src_port=src_port, dst_port=dst_port, state=state)
            else:
                self.graph[src][dst][key]["state"] = state

        # Remove edges not in current links
        for u, v, k, data in list(self.graph.edges(keys=True, data=True)):
            if data.get("type") == "switch_switch":
                key = (u, v, data["src_port"], data["dst_port"])
                if key not in current_links:
                    self.graph.remove_edge(u, v, k)

    def update_switch_link_states(self, portdesc_dict: Dict[str, List[Dict]]):
        """
        Update switch-switch link states based on port operational status.
        A link is considered UP only if both end ports are up.
        """
        if not portdesc_dict:
            return

        # First build a quick lookup: (dpid, port_no) -> state ('up'/'down')
        port_state_lookup = {}
        for dpid, ports in portdesc_dict.items():
            for p in ports:
                port_no = str(p.get("port_no"))
                if port_no == "LOCAL":
                    continue
                config = p.get("config", 0)
                state = p.get("state", 0)
                is_down = ((config & 1) == 1) or ((state & 1) == 1)
                port_state_lookup[(dpid, port_no)] = "down" if is_down else "up"

        # Iterate over all switch-switch edges
        for u, v, key, attrs in list(self.graph.edges(keys=True, data=True)):
            if attrs.get("type") != "switch_switch":
                continue
            # Get source and destination DPIDs and ports
            src_dpid = u
            dst_dpid = v
            src_port = str(attrs.get("src_port"))
            dst_port = str(attrs.get("dst_port"))

            # Determine if both ends are up
            src_state = port_state_lookup.get((src_dpid, src_port), "unknown")
            dst_state = port_state_lookup.get((dst_dpid, dst_port), "unknown")

            # Link is up only if both ends are up
            if src_state == "up" and dst_state == "up":
                new_state = 1
            else:
                new_state = 0

            old_state = attrs.get("state", -1)
            if new_state != old_state:
                self.graph[u][v][key]["state"] = new_state
                status = "UP" if new_state == 1 else "DOWN"
                print(f"[STATE] Switch link {src_dpid}:{src_port} <-> {dst_dpid}:{dst_port} is now {status}")

    def update_hosts(self, hosts_data: Optional[List[Dict]]):
        """
        hosts_data: list from /v1.0/topology/hosts
        Each element: {"mac": "...", "ipv4": [...], "port": {"dpid": "...", "port_no": "...", ...}, ...}
        """
        if hosts_data is None:
            return
        current_host_macs = set()
        for host in hosts_data:
            mac = host["mac"]
            current_host_macs.add(mac)
            # Extract connection info
            port_info = host["port"]
            switch_dpid = port_info["dpid"]
            switch_port = port_info["port_no"]
            ipv4 = host.get("ipv4", [])
            ipv6 = host.get("ipv6", [])
            # Add host node if not exists
            if not self.graph.has_node(mac):
                self.graph.add_node(mac, type="host", mac=mac, ipv4=ipv4, ipv6=ipv6,
                                    connected_to=switch_dpid, connected_port=switch_port)
            else:
                # Update existing host attributes (IPs may change)
                self.graph.nodes[mac]["ipv4"] = ipv4
                self.graph.nodes[mac]["ipv6"] = ipv6
                self.graph.nodes[mac]["connected_to"] = switch_dpid
                self.graph.nodes[mac]["connected_port"] = switch_port
            # Add/update host‑switch edge
            edge_key = (mac, switch_dpid, "host_switch")
            if not self.graph.has_edge(mac, switch_dpid, key=edge_key):
                self.graph.add_edge(mac, switch_dpid, key=edge_key, type="host_switch",
                                    host_mac=mac, switch_port=switch_port, state="up")
            else:
                # Update state just in case
                self.graph[mac][switch_dpid][edge_key]["state"] = "up"
        # Remove hosts no longer present
        for node in list(self.graph.nodes):
            if self.graph.nodes[node].get("type") == "host" and node not in current_host_macs:
                self.graph.remove_node(node)

    def update_port_stats(self, port_stats_dict: Dict[str, List[Dict]]):
        """
        port_stats_dict: mapping dpid_hex -> list of port stats (from get_port_stats)
        Each port stat: {"port_no": X, "rx_packets": ..., "tx_packets": ..., ...}
        """
        for dpid, stats_list in port_stats_dict.items():
            if not self.graph.has_node(dpid):
                continue
            # Convert list to dict keyed by port_no for easier access
            stats_by_port = {}
            for pstat in stats_list:
                port_no = str(pstat.get("port_no"))
                stats_by_port[port_no] = pstat
            self.graph.nodes[dpid]["port_stats"] = stats_by_port

    def update_flow_stats(self, flow_stats_dict: Dict[str, List[Dict]]):
        """
        flow_stats_dict: mapping dpid_hex -> list of flow stats (from get_flow_stats)
        """
        for dpid, flows in flow_stats_dict.items():
            if not self.graph.has_node(dpid):
                continue
            self.graph.nodes[dpid]["flows"] = flows

    def update_host_link_states(self, portdesc_dict: Dict[str, List[Dict]]):
        """
        Update host-switch edge states based on port admin/operational status.
        portdesc_dict: mapping dpid_hex -> list of port descriptions from /stats/portdesc/<dpid>
        A port is considered DOWN if:
          - config has OFPPC_PORT_DOWN (bit 0) set, OR
          - state has OFPPS_LINK_DOWN (bit 0) set.
        """
        if not portdesc_dict:
            return
        for dpid, ports in portdesc_dict.items():
            if not self.graph.has_node(dpid):
                continue

            port_state_map = {}
            for p in ports:
                port_no = str(p.get("port_no"))
                # Ignore LOCAL port (not relevant for host links)
                if port_no == "LOCAL":
                    continue
                config = p.get("config", 0)
                state = p.get("state", 0)
                # Down if admin down (config bit 0) OR link down (state bit 0)
                is_down = ((config & 1) == 1) or ((state & 1) == 1)
                port_state_map[port_no] = "down" if is_down else "up"
                print(f"[DEBUG] Switch {dpid} port {port_no}: config={config}, state={state} -> {port_state_map[port_no]}")

            # Update each host-switch edge that uses this switch
            for u, v, key, attrs in list(self.graph.edges(keys=True, data=True)):
                if attrs.get("type") != "host_switch":
                    continue
                # Identify switch and port
                if self.graph.nodes[u].get("type") == "switch":
                    sw, host = u, v
                    sw_port = str(attrs.get("switch_port"))
                elif self.graph.nodes[v].get("type") == "switch":
                    sw, host = v, u
                    sw_port = str(attrs.get("switch_port"))
                else:
                    continue

                if sw != dpid:
                    continue

                if sw_port in port_state_map:
                    new_state = port_state_map[sw_port]
                    old_state = attrs.get("state", "unknown")
                    if new_state != old_state:
                        self.graph[u][v][key]["state"] = new_state
                        print(f"[STATE] Host {host} link to switch {sw} port {sw_port} is now {new_state}")

    # ----------------------------------------------------------------------
    # Diff & logging
    # ----------------------------------------------------------------------
    def compare_and_log(self, previous_state: Optional[Dict] = None):
        """
        Compare current graph state with previous state (if provided)
        and print differences.
        previous_state should be a dict from to_dict().
        """
        if previous_state is None:
            previous_state = self._prev_state
        if previous_state is None:
            print("[INFO] No previous state for comparison.")
            return
        current_state = self.to_dict()
        # Simple diff: keys and values
        # For brevity, we compare nodes and edges
        prev_nodes = {n["id"]: n for n in previous_state["nodes"]}
        curr_nodes = {n["id"]: n for n in current_state["nodes"]}
        prev_edges = {(e["u"], e["v"], e["key"]): e for e in previous_state["edges"]}
        curr_edges = {(e["u"], e["v"], e["key"]): e for e in current_state["edges"]}

        # Nodes added/removed
        added_nodes = set(curr_nodes.keys()) - set(prev_nodes.keys())
        removed_nodes = set(prev_nodes.keys()) - set(curr_nodes.keys())
        for nid in added_nodes:
            print(f"[CHANGE] Node added: {nid} ({curr_nodes[nid]['type']})")
        for nid in removed_nodes:
            print(f"[CHANGE] Node removed: {nid} ({prev_nodes[nid]['type']})")
        # Node attribute changes (simplified: check if whole dict changed)
        for nid in set(prev_nodes.keys()) & set(curr_nodes.keys()):
            if prev_nodes[nid] != curr_nodes[nid]:
                print(f"[CHANGE] Node {nid} attributes updated.")

        # Edges added/removed
        added_edges = set(curr_edges.keys()) - set(prev_edges.keys())
        removed_edges = set(prev_edges.keys()) - set(curr_edges.keys())
        for e in added_edges:
            print(f"[CHANGE] Edge added: {e[0]} - {e[1]} (key {e[2]})")
        for e in removed_edges:
            print(f"[CHANGE] Edge removed: {e[0]} - {e[1]} (key {e[2]})")
        # Edge attribute changes
        for e in set(prev_edges.keys()) & set(curr_edges.keys()):
            if prev_edges[e] != curr_edges[e]:
                print(f"[CHANGE] Edge {e[0]}-{e[1]} attributes updated.")

        # Store current state for next comparison
        self._prev_state = current_state

    # ----------------------------------------------------------------------
    # Serialization (to/from JSON)
    # ----------------------------------------------------------------------
    def to_dict(self) -> Dict:
        """Convert the entire graph to a serializable dictionary."""
        # Nodes
        nodes_list = []
        for node, attrs in self.graph.nodes(data=True):
            nodes_list.append({"id": node, **attrs})
        # Edges (including multi-edges)
        edges_list = []
        for u, v, key, attrs in self.graph.edges(keys=True, data=True):
            edges_list.append({"u": u, "v": v, "key": key, **attrs})
        return {"nodes": nodes_list, "edges": edges_list}

    def from_dict(self, data: Dict):
        """Reconstruct graph from dictionary."""
        self.graph = nx.MultiGraph()
        for node in data["nodes"]:
            nid = node.pop("id")
            self.graph.add_node(nid, **node)
        for edge in data["edges"]:
            u = edge.pop("u")
            v = edge.pop("v")
            key = edge.pop("key")
            # Convert key to tuple if it's a list (JSON serialization)
            if isinstance(key, list):
                key = tuple(key)
            self.graph.add_edge(u, v, key=key, **edge)

    def to_json(self, filename: str):
        """Save state to JSON file."""
        with open(filename, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    def from_json(self, filename: str):
        """Load state from JSON file."""
        with open(filename, "r") as f:
            data = json.load(f)
        self.from_dict(data)

    # ----------------------------------------------------------------------
    # Utility: print summary
    # ----------------------------------------------------------------------
    def summary(self) -> str:
        """Return a short summary of the twin."""
        switches = [n for n, d in self.graph.nodes(data=True) if d.get("type") == "switch"]
        hosts = [n for n, d in self.graph.nodes(data=True) if d.get("type") == "host"]
        links = [(u, v) for u, v, d in self.graph.edges(data=True) if d.get("type") == "switch_switch"]
        return (f"Digital Twin: {len(switches)} switches, {len(hosts)} hosts, "
                f"{len(links)} switch‑switch links.")


# ----------------------------------------------------------------------
# Quick test (to be run after rest_client works)
# ----------------------------------------------------------------------
if __name__ == "__main__":
    # This part will be used later when we have rest_client data.
    # For now, just create an empty twin.
    dt = DigitalTwin()
    print(dt.summary())
