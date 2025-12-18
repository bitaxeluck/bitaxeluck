#!/usr/bin/env python3
"""
BitAxeLuck Agent
================
Collects metrics from your BitAxe miner(s) and sends them to BitAxeLuck.

Usage:
    # Single miner
    python3 bitaxeluck-agent.py --bitaxe-ip 192.168.1.50 --token YOUR_API_TOKEN

    # Multiple miners (uses BitAxe hostname automatically)
    python3 bitaxeluck-agent.py --bitaxe-ip 192.168.1.50,192.168.1.51 --token YOUR_API_TOKEN

    # Multiple miners with custom names (recommended)
    python3 bitaxeluck-agent.py --bitaxe-ip 192.168.1.50,192.168.1.51 --token YOUR_API_TOKEN --miner-names "Garage,Office"

    # Using token suffix for miner name (alternative method)
    # Token format: YOUR_TOKEN.MINER_NAME
    python3 bitaxeluck-agent.py --bitaxe-ip 192.168.1.50 --token YOUR_API_TOKEN.MyBitAxe

Requirements:
    pip install requests

"""

import argparse
import requests
import time
import sys
import signal
import os
import re
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# BitAxeLuck API endpoint
BITAXELUCK_URL = "https://influx.bitaxeluck.com/api/v2/write"
DEFAULT_INTERVAL = 10  # seconds

# Miner name validation (same as backend)
MINER_NAME_REGEX = re.compile(r'^[a-zA-Z0-9_-]+$')
MINER_NAME_MAX_LENGTH = 32


def sanitize_miner_name(name: str) -> str:
    """Sanitize miner name: only alphanumeric, dash, underscore. Max 32 chars."""
    if not name:
        return ""
    sanitized = re.sub(r'[^a-zA-Z0-9_-]', '', name)
    return sanitized[:MINER_NAME_MAX_LENGTH]

# Global flag for graceful shutdown
running = True


def signal_handler(sig, frame):
    global running
    print("\n[INFO] Shutting down gracefully...")
    running = False


def get_bitaxe_metrics(bitaxe_ip: str) -> tuple:
    """Fetch metrics from BitAxe API. Returns (ip, metrics) tuple."""
    url = f"http://{bitaxe_ip}/api/system/info"
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        return (bitaxe_ip, response.json())
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] [{bitaxe_ip}] Failed to fetch metrics: {e}")
        return (bitaxe_ip, None)


def convert_to_line_protocol(metrics: dict, host: str, custom_name: str = None) -> str:
    """Convert BitAxe metrics to InfluxDB line protocol.

    Args:
        metrics: BitAxe metrics dict
        host: IP address of BitAxe (fallback for hostname)
        custom_name: Optional custom name (overrides hostname)
    """
    # Extract and convert fields
    fields = []

    # Hashrate (convert GH/s to H/s)
    if "hashRate" in metrics:
        fields.append(f"hashrate={metrics['hashRate'] * 1e9}")
    if "hashRate_1m" in metrics:
        fields.append(f"hashrate_1m={metrics['hashRate_1m'] * 1e9}")
    if "hashRate_10m" in metrics:
        fields.append(f"hashrate_10m={metrics['hashRate_10m'] * 1e9}")
    if "hashRate_1h" in metrics:
        fields.append(f"hashrate_1h={metrics['hashRate_1h'] * 1e9}")

    # Temperature
    if "temp" in metrics:
        fields.append(f"temperature={metrics['temp']}")
    if "vrTemp" in metrics:
        fields.append(f"vr_temperature={metrics['vrTemp']}")

    # Power
    if "power" in metrics:
        fields.append(f"power={metrics['power']}")
    if "voltage" in metrics:
        fields.append(f"voltage={metrics['voltage']}")
    if "current" in metrics:
        fields.append(f"current={metrics['current']}")
    if "coreVoltage" in metrics:
        fields.append(f"core_voltage={metrics['coreVoltage']}")
    if "coreVoltageActual" in metrics:
        fields.append(f"core_voltage_actual={metrics['coreVoltageActual']}")

    # Fan
    if "fanrpm" in metrics:
        fields.append(f"fan_rpm={metrics['fanrpm']}")
    if "fanspeed" in metrics:
        fields.append(f"fan_speed={metrics['fanspeed']}")

    # Shares
    if "sharesAccepted" in metrics:
        fields.append(f"shares_accepted={metrics['sharesAccepted']}i")
    if "sharesRejected" in metrics:
        fields.append(f"shares_rejected={metrics['sharesRejected']}i")

    # Difficulty
    if "bestDiff" in metrics:
        fields.append(f'best_diff="{metrics["bestDiff"]}"')
    if "bestSessionDiff" in metrics:
        fields.append(f'best_session_diff="{metrics["bestSessionDiff"]}"')
    if "poolDifficulty" in metrics:
        fields.append(f"pool_difficulty={metrics['poolDifficulty']}")

    # Frequency
    if "frequency" in metrics:
        fields.append(f"frequency={metrics['frequency']}")

    # System
    if "uptimeSeconds" in metrics:
        fields.append(f"uptime={metrics['uptimeSeconds']}i")
    if "freeHeap" in metrics:
        fields.append(f"free_heap={metrics['freeHeap']}i")

    # ASIC info
    if "ASICModel" in metrics:
        fields.append(f'asic_model="{metrics["ASICModel"]}"')
    if "boardVersion" in metrics:
        fields.append(f'board_version="{metrics["boardVersion"]}"')
    if "version" in metrics:
        fields.append(f'firmware_version="{metrics["version"]}"')

    # Build line protocol: measurement,tags fields timestamp
    # Priority: custom_name > hostname from metrics > IP-based fallback
    if custom_name:
        hostname = sanitize_miner_name(custom_name)
    else:
        hostname = metrics.get("hostname", host.replace(".", "_"))

    line = f"bitaxe,host={hostname} {','.join(fields)}"

    return line


def send_to_bitaxeluck(line_protocol: str, token: str) -> bool:
    """Send metrics to BitAxeLuck."""
    headers = {
        "Authorization": f"Token {token}",
        "Content-Type": "text/plain"
    }
    params = {
        "bucket": "miners",
        "org": "hashluck",
        "precision": "s"
    }

    try:
        response = requests.post(
            BITAXELUCK_URL,
            headers=headers,
            params=params,
            data=line_protocol,
            timeout=10
        )

        if response.status_code == 200:
            return True
        elif response.status_code == 429:
            print(f"[WARN] Rate limited, waiting...")
            return False
        else:
            print(f"[ERROR] Failed to send: {response.status_code} - {response.text}")
            return False

    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Failed to send metrics: {e}")
        return False


def parse_bitaxe_ips(ip_string: str) -> list:
    """Parse comma-separated IP addresses."""
    ips = [ip.strip() for ip in ip_string.split(',') if ip.strip()]
    return ips


def collect_from_miners(miners: list, verbose: bool = False) -> list:
    """Collect metrics from multiple miners in parallel."""
    results = []

    # Use ThreadPoolExecutor for parallel collection
    with ThreadPoolExecutor(max_workers=min(len(miners), 10)) as executor:
        futures = {executor.submit(get_bitaxe_metrics, ip): ip for ip in miners}

        for future in as_completed(futures):
            ip, metrics = future.result()
            if metrics:
                results.append((ip, metrics))

    return results


def main():
    parser = argparse.ArgumentParser(
        description="BitAxeLuck Agent - Send BitAxe metrics to BitAxeLuck",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Single miner
  python3 bitaxeluck-agent.py --bitaxe-ip 192.168.1.50 --token abc123

  # Multiple miners (comma-separated)
  python3 bitaxeluck-agent.py --bitaxe-ip 192.168.1.50,192.168.1.51 --token abc123

  # Using environment variables
  export BITAXE_IP=192.168.1.50,192.168.1.51,192.168.1.52
  export BITAXELUCK_TOKEN=abc123
  python3 bitaxeluck-agent.py
        """
    )
    parser.add_argument(
        "-b", "--bitaxe-ip",
        default=os.environ.get("BITAXE_IP", ""),
        help="IP address(es) of your BitAxe (comma-separated for multiple)"
    )
    parser.add_argument(
        "-t", "--token",
        default=os.environ.get("BITAXELUCK_TOKEN", ""),
        help="Your BitAxeLuck API token"
    )
    parser.add_argument(
        "-i", "--interval",
        type=int,
        default=int(os.environ.get("INTERVAL", DEFAULT_INTERVAL)),
        help=f"Polling interval in seconds (default: {DEFAULT_INTERVAL})"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        default=bool(os.environ.get("VERBOSE", "")),
        help="Enable verbose output"
    )
    parser.add_argument(
        "-n", "--miner-names",
        default=os.environ.get("MINER_NAMES", ""),
        help="Custom names for miners (comma-separated, same order as IPs). Example: --miner-names 'Garage,Office'"
    )

    args = parser.parse_args()

    # Validate required arguments
    if not args.bitaxe_ip:
        parser.error("--bitaxe-ip is required (or set BITAXE_IP environment variable)")
    if not args.token:
        parser.error("--token is required (or set BITAXELUCK_TOKEN environment variable)")

    # Parse multiple IPs
    miners = parse_bitaxe_ips(args.bitaxe_ip)

    if not miners:
        parser.error("No valid BitAxe IP addresses provided")

    # Parse custom miner names (optional)
    miner_names_list = [n.strip() for n in args.miner_names.split(',') if n.strip()] if args.miner_names else []

    # Create IP -> name mapping
    miner_name_map = {}
    for i, ip in enumerate(miners):
        if i < len(miner_names_list):
            miner_name_map[ip] = sanitize_miner_name(miner_names_list[i])
        else:
            miner_name_map[ip] = None  # Will use hostname from BitAxe

    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Display banner
    miner_count = len(miners)
    miner_label = "miner" if miner_count == 1 else "miners"

    print(f"""
╔══════════════════════════════════════════════════════════════╗
║                    BitAxeLuck Agent                          ║
╠══════════════════════════════════════════════════════════════╣
║  Monitoring: {miner_count} {miner_label:<44} ║""")

    for i, ip in enumerate(miners[:5]):  # Show first 5
        name = miner_name_map.get(ip)
        if name:
            display = f"{ip} ({name})"
        else:
            display = ip
        print(f"║    {i+1}. {display:<52} ║")

    if len(miners) > 5:
        print(f"║    ... and {len(miners) - 5} more{' ' * 41}║")

    print(f"""║  Interval:  {args.interval} seconds{' ' * 39}║
║  Target:    influx.bitaxeluck.com                           ║
╚══════════════════════════════════════════════════════════════╝
    """)

    print("[INFO] Starting metrics collection... (Ctrl+C to stop)")

    # Track consecutive errors per miner
    error_counts = {ip: 0 for ip in miners}
    max_errors = 5

    while running:
        timestamp = datetime.now().strftime("%H:%M:%S")

        # Collect from all miners in parallel
        results = collect_from_miners(miners, args.verbose)

        # Process results
        sent_count = 0
        for ip, metrics in results:
            error_counts[ip] = 0  # Reset error count on success

            # Get custom name for this miner (if configured)
            custom_name = miner_name_map.get(ip)

            # Convert to line protocol
            line = convert_to_line_protocol(metrics, ip, custom_name)

            if args.verbose:
                print(f"[DEBUG] [{ip}] {line[:80]}...")

            # Send to BitAxeLuck
            if send_to_bitaxeluck(line, args.token):
                sent_count += 1
                hashrate = metrics.get("hashRate", 0)
                temp = metrics.get("temp", 0)
                # Display name priority: custom_name > hostname > IP
                display_name = custom_name or metrics.get("hostname", ip)
                print(f"[{timestamp}] {display_name}: {hashrate:.1f} GH/s | {temp:.1f}°C")

        # Check for miners that failed
        successful_ips = {ip for ip, _ in results}
        for ip in miners:
            if ip not in successful_ips:
                error_counts[ip] += 1
                if error_counts[ip] >= max_errors:
                    print(f"[WARN] [{ip}] {max_errors} consecutive failures")
                    error_counts[ip] = 0

        # Summary for multi-miner
        if miner_count > 1:
            print(f"[{timestamp}] Summary: {sent_count}/{miner_count} miners reporting")

        # Wait for next interval
        for _ in range(args.interval):
            if not running:
                break
            time.sleep(1)

    print("[INFO] Agent stopped")


if __name__ == "__main__":
    main()
