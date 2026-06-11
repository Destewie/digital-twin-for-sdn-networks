#!/usr/bin/env python3
"""
main.py - Entry point for the Digital Twin sync service.
"""

import argparse
import os
from dt_sync import start_sync

def main():
    parser = argparse.ArgumentParser(description="Digital Twin for SDN networks")
    parser.add_argument("--ryu-url", default=os.getenv("RYU_URL", "http://127.0.0.1:8080"),
                        help="Ryu REST API base URL")
    parser.add_argument("--interval", type=float, default=float(os.getenv("POLL_INTERVAL", "2.0")),
                        help="Polling interval in seconds")
    args = parser.parse_args()

    print(f"=== Digital Twin ===\nRyu URL: {args.ryu_url}\nPoll interval: {args.interval}s\n")
    start_sync(ryu_url=args.ryu_url, interval=args.interval)

if __name__ == "__main__":
    main()
