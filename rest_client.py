"""
rest_client.py - Wrapper per le API REST Northbound di Ryu.

Endpoint utilizzati (basati su ryu.app.rest_topology e ryu.app.ofctl_rest):
- GET /v1.0/topology/switches
- GET /v1.0/topology/links
- GET /v1.0/topology/hosts
- GET /v1.0/stats/ports/<dpid>
- GET /v1.0/stats/flows/<dpid>
- GET /v1.0/stats/portdesc/<dpid>   (opzionale, per stato porte)
"""

import requests
import json
from typing import List, Dict, Any, Optional

class RyuRestClient:
    """Client semplice per le REST API di Ryu."""

    def __init__(self, base_url: str = "http://127.0.0.1:8080"):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        # Timeout per evitare blocchi
        self.timeout = 3.0

    def _get(self, endpoint: str) -> Optional[Dict[str, Any]]:
        """Effettua una GET e restituisce il JSON oppure None in caso di errore."""
        url = f"{self.base_url}{endpoint}"
        try:
            resp = self.session.get(url, timeout=self.timeout)
            resp.raise_for_status()
            return resp.json()
        except (requests.exceptions.RequestException, json.JSONDecodeError) as e:
            print(f"[ERROR] GET {url} fallita: {e}")
            return None

    # ----------------------------------------------------------------------
    # Topology endpoints (rest_topology)
    # ----------------------------------------------------------------------
    def get_switches(self) -> Optional[List[Dict]]:
        """Restituisce la lista degli switch con i loro DPID.
        Esempio di risposta:
        [{"dpid": "0000000000000001", "ports": [...]}, ...]
        """
        data = self._get("/v1.0/topology/switches")
        if data is None:
            return None
        # A volte la risposta è una lista direttamente, altre volte un dict con chiave "switches"
        if isinstance(data, list):
            return data
        elif isinstance(data, dict) and "switches" in data:
            return data["switches"]
        else:
            print(f"[WARN] Formato inaspettato per /switches: {data}")
            return None

    def get_links(self) -> Optional[List[Dict]]:
        """Restituisce la lista dei link tra switch.
        Ogni link ha: src, dst, src_port, dst_port, state (0=down, 1=up)
        """
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
        """Restituisce la lista degli host connessi.
        Ogni host ha: mac, ipv4 (lista), port, dpid (switch connesso)
        """
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
    # OFPT stats (ofctl_rest)
    # ----------------------------------------------------------------------
    def get_port_stats(self, dpid: str) -> Optional[List[Dict]]:
        """Statistiche delle porte per uno switch (DPID in formato esadecimale a 16 char).
        Restituisce lista di dict: {"port_no": X, "rx_packets": ..., "tx_packets": ..., ...}
        """
        endpoint = f"/v1.0/stats/ports/{dpid}"
        data = self._get(endpoint)
        if data is None:
            return None
        # La risposta di ofctl_rest è un dict con chiave dpid, valore lista di porte
        if isinstance(data, dict) and dpid in data:
            return data[dpid]
        else:
            print(f"[WARN] Formato inaspettato per /stats/ports/{dpid}: {data}")
            return None

    def get_flow_stats(self, dpid: str) -> Optional[List[Dict]]:
        """Statistiche dei flussi per uno switch.
        Restituisce lista di flow: {"match": {...}, "actions": [...], "packet_count": ..., "byte_count": ...}
        """
        endpoint = f"/v1.0/stats/flows/{dpid}"
        data = self._get(endpoint)
        if data is None:
            return None
        if isinstance(data, dict) and dpid in data:
            return data[dpid]
        else:
            print(f"[WARN] Formato inaspettato per /stats/flows/{dpid}: {data}")
            return None

    def get_port_description(self, dpid: str) -> Optional[List[Dict]]:
        """Descrizione delle porte (stato, velocità, nome).
        Utile per rilevare lo stato UP/DOWN reale della porta.
        """
        endpoint = f"/v1.0/stats/portdesc/{dpid}"
        data = self._get(endpoint)
        if data is None:
            return None
        if isinstance(data, dict) and dpid in data:
            return data[dpid]
        else:
            print(f"[WARN] Formato inaspettato per /stats/portdesc/{dpid}: {data}")
            return None


# ----------------------------------------------------------------------
# Test veloce (da eseguire solo se script lanciato direttamente)
# ----------------------------------------------------------------------
if __name__ == "__main__":
    import time
    client = RyuRestClient("http://127.0.0.1:8080")
    print("=== Test REST client ===")
    
    switches = client.get_switches()
    print(f"Switches: {switches}")
    
    links = client.get_links()
    print(f"Links: {links}")
    
    hosts = client.get_hosts()
    print(f"Hosts: {hosts}")
    
    if switches and len(switches) > 0:
        dpid = switches[0]["dpid"]
        print(f"\nTest statistiche per switch {dpid}:")
        ports = client.get_port_stats(dpid)
        print(f"Port stats: {ports}")
        flows = client.get_flow_stats(dpid)
        print(f"Flow stats: {flows}")
        portdesc = client.get_port_description(dpid)
        print(f"Port description: {portdesc}")
