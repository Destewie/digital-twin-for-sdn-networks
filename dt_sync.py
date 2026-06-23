"""
dt_sync.py - Periodically fetch data from Ryu and update the Digital Twin.
"""

import time
import signal
import sys
from typing import Optional
from rest_client import RyuRestClient
from dt_model import DigitalTwin

class DigitalTwinSync:
    def __init__(self, ryu_url: str, dt: DigitalTwin, interval: float = 2.0):
        self.client = RyuRestClient(ryu_url)
        self.dt = dt
        self.interval = interval
        self.running = True
        self._prev_state = None  # store previous twin state for diff

    def fetch_and_update(self) -> bool:
        """Fetch all data and update the twin. Returns True if success."""
        try:
            # 1. Topology
            switches = self.client.get_switches()
            links = self.client.get_links()
            hosts = self.client.get_hosts()
            if switches is None:
                print("[WARN] Could not fetch switches, skipping cycle")
                return False

            self.dt.update_switches(switches)
            self.dt.update_links(links)
            self.dt.update_hosts(hosts)
            self.dt.update_switch_link_states(portdesc_dict) 

            # 2. Statistics per switch
            port_stats_dict = {}
            flow_stats_dict = {}
            portdesc_dict = {}  # new: for port state
            for sw in switches:
                dpid = sw["dpid"]
                port_stats = self.client.get_port_stats(dpid)
                flow_stats = self.client.get_flow_stats(dpid)
                port_desc = self.client.get_port_description(dpid)  # we already implemented this
                if port_stats:
                    port_stats_dict[dpid] = port_stats
                if flow_stats:
                    flow_stats_dict[dpid] = flow_stats
                if port_desc:
                    portdesc_dict[dpid] = port_desc
                    print(f"[DEBUG] Raw portdesc for {dpid}: {port_desc}")  # <-- add this

            self.dt.update_port_stats(port_stats_dict)
            self.dt.update_flow_stats(flow_stats_dict)
            self.dt.update_host_link_states(portdesc_dict)   # new call

            # 3. Compare with previous state
            current_state = self.dt.to_dict()
            if self._prev_state:
                self.dt.compare_and_log(self._prev_state)
            self._prev_state = current_state

            return True

        except Exception as e:
            print(f"[ERROR] Exception in sync cycle: {e}")
            return False

    def run(self):
        """Main loop: poll every `interval` seconds."""
        print(f"[INFO] Starting sync loop (interval = {self.interval}s)")
        while self.running:
            start = time.time()
            self.fetch_and_update()
            elapsed = time.time() - start
            sleep_time = max(0, self.interval - elapsed)
            if self.running:
                time.sleep(sleep_time)
        print("[INFO] Sync loop stopped")

    def stop(self):
        self.running = False

def signal_handler(sync_loop, signum, frame):
    print("\n[INFO] Received SIGINT, stopping sync loop...")
    sync_loop.stop()

def start_sync(ryu_url: str = "http://127.0.0.1:8080", interval: float = 2.0):
    dt = DigitalTwin()
    syncer = DigitalTwinSync(ryu_url, dt, interval)

    # Set up signal handler for graceful termination
    signal.signal(signal.SIGINT, lambda s, f: signal_handler(syncer, s, f))
    try:
        syncer.run()
    except KeyboardInterrupt:
        pass
    finally:
        # Optional: save final state
        dt.to_json("dt_final_state.json")
        print("[INFO] Final twin saved to dt_final_state.json")

if __name__ == "__main__":
    # If run directly, start sync with default parameters
    start_sync()
