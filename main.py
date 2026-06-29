#!/usr/bin/env python3
"""
main.py - Entry point for the Digital Twin service with interactive CLI.
"""

import argparse
import threading
import time
from dt_sync import DigitalTwinSync
from dt_model import DigitalTwin
from dt_cli import DTCli

def main():
    parser = argparse.ArgumentParser(description="Digital Twin for SDN networks")
    parser.add_argument("--ryu-url", default="http://127.0.0.1:8080",
                        help="Ryu REST API base URL")
    parser.add_argument("--interval", type=float, default=2.0,
                        help="Polling interval in seconds")
    args = parser.parse_args()

    dt = DigitalTwin()
    syncer = DigitalTwinSync(args.ryu_url, dt, args.interval)

    # Run the sync loop in a background daemon thread
    def sync_worker():
        while True:
            syncer.fetch_and_update()
            time.sleep(args.interval)

    thread = threading.Thread(target=sync_worker, daemon=True)
    thread.start()
    print(f"[INFO] Sync loop started (interval {args.interval}s)")

    # Start the interactive CLI
    cli = DTCli(dt, syncer)
    cli.cmdloop()

if __name__ == "__main__":
    main()
