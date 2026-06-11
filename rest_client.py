"""
rest_client.py - Wrapper per le API REST Northbound di Ryu.
"""

import requests
import json
from typing import List, Dict, Any, Optional

class RyuRestClient:
    def __init__(self, base_url: str = "http://127.0.0.1:8080"):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.timeout = 3.0

    def _get(self, endpoint: str) -> Optional[Dict[str, Any]]:
        url = f"{self.base_url}{endpoint}"
        try:
            resp = self.session.get(url, timeout=self.timeout)
            resp.raise_for_status()
            return resp.json()
        except (requests.exceptions.RequestException, json.JSONDecodeError) as e:
            print(f"[ERROR] GET {url} fallita: {e}")
            return None

    # ----------------------------------------------------------------------
    # Topology endpoints (rest_topology) – these keep /v1.0 prefix
    # ----------------------------------------------------------------------
    def get_switches(self) -> Optional[List[Dict]]:
        data = self._get("/v1.0/topology/switches")
        if data is None:
            return None
        if isinstance(data, list):
            return data
        elif isinstance(data, dict) and "switches" in data:
            return data["switches"]
        else:
            print(f"[WARN] Formato inaspettato per /switches: {data}")
            return None

    def get_links(self) -> Optional[List[Dict]]:
        data = self._get("/v1.0/topology/links")
        if data is None:
            return None
        if isinstance(data, list):
            return data
        elif isinstance(data, dict) and "links" in data:
            return data["links"]
        else:
            print(f"[WARN] Formato inaspettato per /links: {data}")
            return None

    def get_hosts(self) -> Optional[List[Dict]]:
        data = self._get("/v1.0/topology/hosts")
        if data is None:
            return None
        if isinstance(data, list):
            return data
        elif isinstance(data, dict) and "hosts" in data:
            return data["hosts"]
        else:
            print(f"[WARN] Formato inaspettato per /hosts: {data}")
            return None

    # ----------------------------------------------------------------------
    # Statistics endpoints (ofctl_rest) – NO /v1.0, DPID as integer
    # ----------------------------------------------------------------------
    @staticmethod
    def _dpid_to_int(dpid_hex: str) -> int:
        """Convert a 16‑character hex DPID (e.g. '0000000000000001') to int (e.g. 1)."""
        return int(dpid_hex, 16)

    def get_port_stats(self, dpid_hex: str) -> Optional[List[Dict]]:
        """Get port statistics for a switch. Endpoint: /stats/port/<dpid>"""
        dpid_int = self._dpid_to_int(dpid_hex)
        endpoint = f"/stats/port/{dpid_int}"
        data = self._get(endpoint)
        if data is None:
            return None
        # Response is a dict with the integer DPID as key
        if isinstance(data, dict) and str(dpid_int) in data:
            return data[str(dpid_int)]
        else:
            print(f"[WARN] Formato inaspettato per /stats/port/{dpid_int}: {data}")
            return None

    def get_flow_stats(self, dpid_hex: str) -> Optional[List[Dict]]:
        """Get flow statistics for a switch. Endpoint: /stats/flow/<dpid>"""
        dpid_int = self._dpid_to_int(dpid_hex)
        endpoint = f"/stats/flow/{dpid_int}"
        data = self._get(endpoint)
        if data is None:
            return None
        if isinstance(data, dict) and str(dpid_int) in data:
            return data[str(dpid_int)]
        else:
            print(f"[WARN] Formato inaspettato per /stats/flow/{dpid_int}: {data}")
            return None

    def get_port_description(self, dpid_hex: str) -> Optional[List[Dict]]:
        """Get port description (including state) for a switch. Endpoint: /stats/portdesc/<dpid>"""
        dpid_int = self._dpid_to_int(dpid_hex)
        endpoint = f"/stats/portdesc/{dpid_int}"
        data = self._get(endpoint)
        if data is None:
            return None
        if isinstance(data, dict) and str(dpid_int) in data:
            return data[str(dpid_int)]
        else:
            print(f"[WARN] Formato inaspettato per /stats/portdesc/{dpid_int}: {data}")
            return None


if __name__ == "__main__":
    client = RyuRestClient("http://127.0.0.1:8080")
    print("=== Test REST client ===")
    
    switches = client.get_switches()
    print(f"Switches: {switches}")
    
    links = client.get_links()
    print(f"Links: {links}")
    
    hosts = client.get_hosts()
    print(f"Hosts: {hosts}")
    
    if switches and len(switches) > 0:
        dpid_hex = switches[0]["dpid"]
        print(f"\nTest statistiche per switch {dpid_hex}:")
        
        ports = client.get_port_stats(dpid_hex)
        print(f"Port stats: {ports}")
        
        flows = client.get_flow_stats(dpid_hex)
        print(f"Flow stats: {flows}")
        
        portdesc = client.get_port_description(dpid_hex)
        print(f"Port description: {portdesc}")
