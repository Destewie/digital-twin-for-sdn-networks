#!/usr/bin/env python3
"""
dt_cli.py - Interactive CLI for the Digital Twin.
"""

import cmd
import json

from dt_model import DigitalTwin


class DTCli(cmd.Cmd):
    intro = (
        "Digital Twin CLI. Type 'help' or '?' to list commands.\n"
        "The twin is updated in the background; query it anytime."
    )
    prompt = "(dt) "

    def __init__(self, dt: DigitalTwin, syncer=None):
        super().__init__()
        self.dt = dt
        self.syncer = syncer  # not used directly, but kept for future

    # ----------------------------------------
    # Basic queries
    # ----------------------------------------
    def do_summary(self, arg):
        """Print a summary of the twin (switches, hosts, links)."""
        print(self.dt.summary())

    def do_hosts(self, arg):
        """List all hosts with MAC, IP, connection, and link state."""
        for node, attrs in self.dt.graph.nodes(data=True):
            if attrs.get("type") == "host":
                mac = attrs.get("mac")
                ip = attrs.get("ipv4")
                sw = attrs.get("connected_to")
                port = attrs.get("connected_port")
                # find edge state
                state = "unknown"
                for u, v, key, edata in self.dt.graph.edges(keys=True, data=True):
                    if edata.get("type") == "host_switch":
                        if (u == node and v == sw) or (v == node and u == sw):
                            state = edata.get("state", "unknown")
                            break
                print(
                    f"Host {mac} IP {ip} connected to switch {sw} port {port} [state: {state}]"
                )

    def do_switches(self, arg):
        """List all switches with DPID, port count, real flows, and hypothetical flows."""
        for node, attrs in self.dt.graph.nodes(data=True):
            if attrs.get("type") == "switch":
                ports = len(attrs.get("ports", []))
                flows = len(attrs.get("flows", []))
                hypo = len(attrs.get("hypothetical_flows", []))
                print(
                    f"Switch {node}: {ports} ports, {flows} real flows, {hypo} hypothetical flows"
                )

    def do_links(self, arg):
        """List all switch‑switch links and their current state."""
        for u, v, key, attrs in self.dt.graph.edges(keys=True, data=True):
            if attrs.get("type") == "switch_switch":
                state = "UP" if attrs.get("state") == 1 else "DOWN"
                print(f"{u}:{attrs['src_port']} <-> {v}:{attrs['dst_port']} [{state}]")

    def do_flows(self, arg):
        """Show real and hypothetical flows on a specific switch. Usage: flows <dpid>"""
        if not arg:
            print("Usage: flows <dpid>")
            return
        dpid = arg.strip()
        if not self.dt.graph.has_node(dpid):
            print(f"Switch {dpid} not found")
            return
        attrs = self.dt.graph.nodes[dpid]
        real = attrs.get("flows", [])
        hypo = attrs.get("hypothetical_flows", [])
        print(f"Real flows on {dpid}:")
        for i, f in enumerate(real, 1):
            print(
                f"  {i}: match={f.get('match')}, actions={f.get('actions')}, packets={f.get('packet_count')}"
            )
        print(f"Hypothetical flows on {dpid}:")
        for i, f in enumerate(hypo, 1):
            print(
                f"  {i}: match={f.get('match')}, actions={f.get('actions')}, priority={f.get('priority')}"
            )

    # ----------------------------------------
    # What‑If simulation
    # ----------------------------------------
    def do_whatif(self, arg):
        """
        Run a what‑if simulation: add a hypothetical flow to a switch and see its impact.
        Usage: whatif <dpid> <match_json> <actions_json> <priority>
        Example: whatif 0000000000000001 '{"in_port":1}' '["OUTPUT:2"]' 10
        """
        parts = arg.split(maxsplit=3)
        if len(parts) < 4:
            print("Usage: whatif <dpid> <match_json> <actions_json> <priority>")
            return
        dpid, match_str, actions_str, priority_str = parts
        # Rimuovi eventuali virgolette esterne (singole o doppie) e spazi
        match_str = match_str.strip().strip("'\"").strip()
        actions_str = actions_str.strip().strip("'\"").strip()
        try:
            match = json.loads(match_str)
            actions = json.loads(actions_str)
            priority = int(priority_str)
        except Exception as e:
            print(f"Error parsing arguments: {e}")
            return

        # Clone the twin to avoid polluting the live state
        clone = self.dt.clone()
        try:
            clone.add_hypothetical_flow(dpid, match, actions, priority)
            impact = clone.simulate_impact()
            print("=== Impact of hypothetical flow ===")
            print(f"Affected real flows: {len(impact['affected_flows'])}")
            for af in impact["affected_flows"]:
                rf = af["real_flow"]
                print(
                    f"  Switch {af['switch']}: match={rf.get('match')} "
                    f"(packets={rf.get('packet_count')}, bytes={rf.get('byte_count')})"
                )
            print(
                f"Affected hosts (MACs): {impact['affected_hosts'] if impact['affected_hosts'] else 'none'}"
            )
        except Exception as e:
            print(f"Simulation error: {e}")

    # ----------------------------------------
    # Utility commands
    # ----------------------------------------
    def do_save(self, arg):
        """
        Save current twin state to a JSON file.
        Usage: save [filename]
        """
        filename = arg.strip() if arg else "dt_snapshot.json"
        self.dt.to_json(filename)
        print(f"Saved to {filename}")

    def do_quit(self, arg):
        """Exit the CLI."""
        print("Exiting.")
        return True

    def do_EOF(self, arg):
        return True
