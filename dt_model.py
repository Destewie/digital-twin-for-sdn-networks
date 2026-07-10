"""
dt_model.py - Digital Twin representation using networkx.

Stores:
- Switches and hosts as separate nodes.
- Links switch‑switch and host‑switch as edges.
- Port statistics and flow statistics as node attributes.
"""

import json
from typing import Dict, List, Optional

import networkx as nx


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
        The switches_data can be retrieved through the API: /v1.0/topology/switches
        Each element: {"dpid": "0000...", "ports": [{"port_no": "...", "name": "...", "hw_addr": "..."}, ...]}
        dpid = datapath ID
        """
        if switches_data is None:
            return
        current_dpids = set()
        for sw in switches_data:
            dpid = sw["dpid"]
            current_dpids.add(dpid)
            # Add node to the graph if it doesn't exist
            if not self.graph.has_node(dpid):
                self.graph.add_node(
                    dpid,
                    type="switch",
                    dpid=dpid,
                    ports=sw["ports"],
                    port_stats={},  # Will be updated by update_port_stats()
                    flows=[],  # Will be updated by update_flow_stats()
                )
            else:
                # If the switch already exists, update the switch ports list
                self.graph.nodes[dpid]["ports"] = sw["ports"]

        # Remove switches that are no longer present
        # -> they are in the digital twin graph, but not in the api response
        for node in list(self.graph.nodes):
            if (
                self.graph.nodes[node].get("type") == "switch"
                and node not in current_dpids
            ):
                self.graph.remove_node(node)

    def update_links(self, links_data: Optional[List[Dict]]):
        """
        Update switch-switch links using a canonical key independent of direction.
        Port numbers are taken from port_no and stored in the canonical key.
        """
        if links_data is None:
            return

        current_links = set()

        for link in links_data:
            src = link["src"]["dpid"]
            dst = link["dst"]["dpid"]
            src_port = int(link["src"]["port_no"], 16)
            dst_port = int(link["dst"]["port_no"], 16)

            # Canonical key: sorted tuple of (dpid, port)
            pair1 = (src, src_port)
            pair2 = (dst, dst_port)
            canonical_key = tuple(sorted([pair1, pair2]))

            if canonical_key in current_links:
                continue
            current_links.add(canonical_key)

            # Add edge with canonical key as edge key
            # No src_port/dst_port attributes needed — they are in the key
            if not self.graph.has_edge(src, dst, key=canonical_key):
                self.graph.add_edge(
                    src,
                    dst,
                    key=canonical_key,
                    type="switch_switch",
                    state=-1,
                )

        # Remove links that are no longer present
        for u, v, k, data in list(self.graph.edges(keys=True, data=True)):
            if data.get("type") == "switch_switch":
                if k not in current_links:
                    self.graph.remove_edge(u, v, k)

    def update_switch_link_states(self, portdesc_dict: Dict[str, List[Dict]]):
        """
        Update switch-switch link states using the canonical key stored as edge key.
        The key is a tuple: ((dpid1, port1), (dpid2, port2))
        """
        if not portdesc_dict:
            return

        # Build lookup: (dpid, port_no) -> 'up'/'down'
        port_state_lookup = {}
        for dpid, ports in portdesc_dict.items():
            for p in ports:
                port_no = p.get("port_no")
                if port_no == "LOCAL":
                    continue
                if isinstance(port_no, str) and port_no.isdigit():
                    port_no = int(port_no)
                config = p.get("config", 0)
                state = p.get("state", 0)
                is_down = ((config & 1) == 1) or ((state & 1) == 1)
                port_state_lookup[(dpid, port_no)] = "down" if is_down else "up"

        # Iterate over switch-switch edges
        for u, v, key, attrs in list(self.graph.edges(keys=True, data=True)):
            if attrs.get("type") != "switch_switch":
                continue

            # Key should be a tuple of two (dpid, port) pairs
            if not isinstance(key, tuple) or len(key) != 2:
                print(f"[WARN] Invalid edge key for {u}-{v}: {key}")
                continue

            # Extract ports from the canonical key
            (dpid1, port1) = key[0]
            (dpid2, port2) = key[1]

            # Look up both ends
            state1 = port_state_lookup.get((dpid1, port1), "unknown")
            state2 = port_state_lookup.get((dpid2, port2), "unknown")

            new_state = 1 if (state1 == "up" and state2 == "up") else 0
            old_state = attrs.get("state", -1)

            if new_state != old_state:
                self.graph[u][v][key]["state"] = new_state
                status = "UP" if new_state == 1 else "DOWN"
                print(
                    f"[STATE] Switch link {dpid1}:{port1} <-> {dpid2}:{port2} is now {status}"
                )

    def update_hosts(self, hosts_data: Optional[List[Dict]]):
        """
        The hosts_data can be retrieved through the API: /v1.0/topology/hosts
        Each element: {"mac": "...", "ipv4": [...], "port": {"dpid": "...", "port_no": "...", ...}, ...}
        This function also creates links (or edges) between hosts and switches
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
            switch_port = int(port_info["port_no"], 16)
            ipv4 = host.get("ipv4", [])
            ipv6 = host.get("ipv6", [])
            # Add host node if not exists
            if not self.graph.has_node(mac):
                self.graph.add_node(
                    mac,
                    type="host",
                    mac=mac,
                    ipv4=ipv4,
                    ipv6=ipv6,
                    connected_to=switch_dpid,
                    connected_port=switch_port,
                )
            else:
                # Update existing host attributes (IPs may change)
                self.graph.nodes[mac]["ipv4"] = ipv4
                self.graph.nodes[mac]["ipv6"] = ipv6
                self.graph.nodes[mac]["connected_to"] = switch_dpid
                self.graph.nodes[mac]["connected_port"] = switch_port

            # Before adding new edges, I want to remove old switch-host edges
            old_edges_to_remove = []
            for u, v, k, attrs in self.graph.edges(keys=True, data=True):
                if attrs.get("type") == "host_switch":
                    if (u == mac and self.graph.nodes[v].get("type") == "switch") or (
                        v == mac and self.graph.nodes[u].get("type") == "switch"
                    ):
                        old_edges_to_remove.append((u, v, k))
            for u, v, k in old_edges_to_remove:
                self.graph.remove_edge(u, v, k)

            # Add/update host‑switch edge
            edge_key = (mac, switch_dpid, "host_switch")
            if not self.graph.has_edge(mac, switch_dpid, key=edge_key):
                self.graph.add_edge(
                    mac,
                    switch_dpid,
                    key=edge_key,
                    type="host_switch",
                    host_mac=mac,
                    switch_port=switch_port,
                    state="unknown",
                )
            else:
                # Update state just in case
                # If it is not really up, don't worry! The state is going to be updated in the same sync cycle by update_host_link_states()
                self.graph[mac][switch_dpid][edge_key]["switch_port"] = switch_port
        # Remove hosts no longer present
        # list() fixes the list of nodes at the beginning of the cycle, while graph.nodes is dynamic
        # I use the list() method to avoid runtime changes in self.graph.nodes.
        for node in list(self.graph.nodes):
            if (
                self.graph.nodes[node].get("type") == "host"
                and node not in current_host_macs
            ):
                self.graph.remove_node(node)

    def update_port_stats(self, port_stats_dict: Dict[str, List[Dict]]):
        """
        port_stats_dict: mapping dpid_hex -> list of port stats (from get_port_stats)
        Each port stat: {"port_no": X, "rx_packets": ..., "tx_packets": ..., ...}
        """
        for dpid, stats_list in port_stats_dict.items():
            if not self.graph.has_node(dpid):
                continue  # If the switch is not in the graph, it will be added by the update_switches function
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
                continue  # If the switch is not in the graph, it will be added by the update_switches function
            self.graph.nodes[dpid]["flows"] = flows

    def update_host_link_states(self, portdesc_dict: Dict[str, List[Dict]]):
        if not portdesc_dict:
            return
        for dpid, ports in portdesc_dict.items():
            if not self.graph.has_node(dpid):
                continue
            port_state_map = {}  # Where new port states will be saved
            for p in ports:
                port_no = p.get("port_no")
                if port_no == "LOCAL":
                    continue
                if isinstance(port_no, str) and port_no.isdigit():
                    port_no = int(port_no)
                config = p.get("config", 0)
                state = p.get("state", 0)
                is_down = ((config & 1) == 1) or ((state & 1) == 1)
                port_state_map[port_no] = "down" if is_down else "up"

            # Here i go through every existing edge to update the link state based on the port_state_map (so the effective actual state of the ports)
            for u, v, key, attrs in list(self.graph.edges(keys=True, data=True)):
                if attrs.get("type") != "host_switch":
                    continue
                if self.graph.nodes[u].get("type") == "switch":
                    sw, host = u, v
                    sw_port = attrs.get("switch_port")
                elif self.graph.nodes[v].get("type") == "switch":
                    sw, host = v, u
                    sw_port = attrs.get("switch_port")
                else:
                    continue
                if sw != dpid:
                    continue
                if sw_port in port_state_map:
                    new_state = port_state_map[sw_port]
                    old_state = attrs.get("state", "unknown")
                    if new_state != old_state:
                        self.graph[u][v][key]["state"] = new_state
                        print(
                            f"[STATE] Host {host} link to switch {sw} port {sw_port} is now {new_state}"
                        )

    # ----------------------------------------------------------------------
    # Diff & logging
    # ----------------------------------------------------------------------
    def compare_and_log(self, previous_state: Optional[Dict] = None):
        """
        Compare current graph state with previous state (if present) and print differences.
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
        switches = [
            n for n, d in self.graph.nodes(data=True) if d.get("type") == "switch"
        ]
        hosts = [n for n, d in self.graph.nodes(data=True) if d.get("type") == "host"]
        links = [
            (u, v)
            for u, v, d in self.graph.edges(data=True)
            if d.get("type") == "switch_switch"
        ]
        return (
            f"Digital Twin: {len(switches)} switches, {len(hosts)} hosts, "
            f"{len(links)} switch‑switch links."
        )

    # ----------------------------------------------------------------------
    # What‑If Simulation
    # ----------------------------------------------------------------------
    def clone(self) -> "DigitalTwin":
        """Return a deep copy of the twin (detached from the real network)."""
        import copy

        new_twin = DigitalTwin()
        new_twin.graph = copy.deepcopy(self.graph)
        new_twin._prev_state = None
        return new_twin

    def add_hypothetical_flow(
        self, dpid: str, match: dict, actions: list, priority: int = 1
    ):
        """
        Add a hypothetical flow rule to a switch in the twin.
        This does NOT affect the real network.
        """
        if not self.graph.has_node(dpid):
            raise ValueError(f"Switch {dpid} not found")
        if "hypothetical_flows" not in self.graph.nodes[dpid]:
            self.graph.nodes[dpid]["hypothetical_flows"] = []
        self.graph.nodes[dpid]["hypothetical_flows"].append(
            {
                "match": match,
                "actions": actions,
                "priority": priority,
                "hypothetical": True,
            }
        )

    def simulate_impact(self) -> dict:
        """
        Analyze the impact of new hypotetical flows.
        A real flow is considered "affected" if the hypotetical match is a subset of the real match.
        """
        impact = {
            "affected_flows": [],
            "affected_hosts": set(),
            "affected_links": set(),
        }

        def is_subset(hypo_match, real_match):
            """Verifica se tutte le chiavi di hypo_match sono in real_match con lo stesso valore."""
            if not hypo_match:
                return True  # match vuoto cattura tutto
            for key, value in hypo_match.items():
                if key not in real_match or real_match[key] != value:
                    return False
            return True

        for sw, attrs in self.graph.nodes(data=True):
            if attrs.get("type") != "switch":
                continue
            real_flows = attrs.get("flows", [])
            hypo_flows = attrs.get("hypothetical_flows", [])
            for hf in hypo_flows:
                for rf in real_flows:
                    if is_subset(hf["match"], rf.get("match", {})):
                        impact["affected_flows"].append(
                            {"switch": sw, "real_flow": rf, "hypothetical": hf}
                        )
                        # Estrae MAC dai match
                        for field in ["dl_src", "dl_dst", "nw_src", "nw_dst"]:
                            if field in rf.get("match", {}):
                                impact["affected_hosts"].add(rf["match"][field])
        return impact


# ----------------------------------------------------------------------
# Quick test (to be run after rest_client works)
# ----------------------------------------------------------------------
if __name__ == "__main__":
    # This part will be used later when we have rest_client data.
    # For now, just create an empty twin.
    dt = DigitalTwin()
    print(dt.summary())
