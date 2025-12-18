# BitAxeLuck Agent

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/docker-ready-brightgreen.svg)](https://hub.docker.com/)

Send metrics from your BitAxe miner(s) to [BitAxeLuck.com](https://bitaxeluck.com) for real-time monitoring, AI health analysis, and luck calculations.

## Features

- **Multi-miner support** - Monitor unlimited BitAxe miners with a single agent
- **Parallel collection** - Metrics collected simultaneously from all miners
- **Lightweight** - Single Python script, no database required
- **Cloud dashboard** - Access your metrics from anywhere
- **AI health analysis** - Get insights about your miner's performance
- **Luck calculations** - See your probability of finding a block

## Why do I need this?

BitAxe firmware (ESP-Miner) doesn't have native InfluxDB support yet ([ESP-Miner #614](https://github.com/bitaxeorg/ESP-Miner/issues/614)). This agent bridges the gap by:

1. Reading metrics from your BitAxe's local API
2. Sending them to BitAxeLuck's InfluxDB endpoint

```
┌──────────┐         ┌─────────────────┐         ┌──────────────────┐
│  BitAxe  │  HTTP   │ BitAxeLuck Agent│  HTTPS  │  bitaxeluck.com  │
│  Miners  │────────>│ (this script)   │────────>│  /api/v2/write   │
│          │ :80/api │                 │         │                  │
└──────────┘         └─────────────────┘         └──────────────────┘
 192.168.x.x          Your PC/RPi/NAS             Cloud
```

## Quick Start

### Prerequisites

1. **BitAxeLuck account** - Register free at [bitaxeluck.com/setup](https://bitaxeluck.com/setup)
2. **Your API token** - Provided after registration
3. **BitAxe IP address(es)** - Find it in your router or BitAxe display

---

## Installation Options

### Option 1: Python Script (Simplest)

Best for: Quick testing, any number of miners

```bash
# Download the script
curl -O https://raw.githubusercontent.com/bitaxeluck/bitaxeluck/main/bitaxeluck-agent.py

# Install dependency
pip3 install requests

# Single miner
python3 bitaxeluck-agent.py --bitaxe-ip 192.168.1.50 --token YOUR_API_TOKEN

# Multiple miners (comma-separated)
python3 bitaxeluck-agent.py --bitaxe-ip 192.168.1.50,192.168.1.51,192.168.1.52 --token YOUR_API_TOKEN
```

**Run in background:**
```bash
nohup python3 bitaxeluck-agent.py --bitaxe-ip 192.168.1.50,192.168.1.51 --token YOUR_API_TOKEN > agent.log 2>&1 &
```

**Command line options:**
| Option | Description | Default |
|--------|-------------|---------|
| `--bitaxe-ip` | BitAxe IP address(es), comma-separated | Required |
| `--token` | Your BitAxeLuck API token | Required |
| `--interval` | Seconds between readings | 10 |
| `--verbose` | Enable debug logging | False |

---

### Option 2: Docker (Recommended)

Best for: Always-on monitoring, easy updates

```bash
# Download docker-compose.yml
curl -O https://raw.githubusercontent.com/bitaxeluck/bitaxeluck/main/docker-compose.yml

# Edit the file and set your values:
# - BITAXE_IP=192.168.1.50 (or comma-separated for multiple)
# - BITAXELUCK_TOKEN=your_token_here

# Start the container
docker compose up -d

# Check logs
docker compose logs -f
```

**Or run directly:**
```bash
# Single miner
docker run -d \
  --name bitaxeluck-agent \
  --restart unless-stopped \
  --network host \
  -e BITAXE_IP=192.168.1.50 \
  -e BITAXELUCK_TOKEN=your_token_here \
  -e INTERVAL=10 \
  ghcr.io/bitaxeluck/agent:latest

# Multiple miners
docker run -d \
  --name bitaxeluck-agent \
  --restart unless-stopped \
  --network host \
  -e BITAXE_IP=192.168.1.50,192.168.1.51,192.168.1.52 \
  -e BITAXELUCK_TOKEN=your_token_here \
  ghcr.io/bitaxeluck/agent:latest
```

**Build locally:**
```bash
git clone https://github.com/bitaxeluck/bitaxeluck.git
cd bitaxeluck
docker build -t bitaxeluck-agent .
docker run -d --network host -e BITAXE_IP=192.168.1.50 -e BITAXELUCK_TOKEN=your_token bitaxeluck-agent
```

---

### Option 3: Telegraf (Advanced)

Best for: Users already running Telegraf

```bash
# Download configuration
curl -O https://raw.githubusercontent.com/bitaxeluck/bitaxeluck/main/telegraf.conf

# Edit telegraf.conf:
# 1. Set your BitAxe IP(s) in [inputs.http] urls
# 2. Set your token in [outputs.influxdb_v2] token

# Run with Telegraf
telegraf --config telegraf.conf
```

**Multiple miners with Telegraf:** Duplicate the `[[inputs.http]]` section for each BitAxe or use a single section with multiple URLs.

---

## Configuration

### Environment Variables (Docker)

| Variable | Description | Required |
|----------|-------------|----------|
| `BITAXE_IP` | IP address(es) of your BitAxe (comma-separated) | Yes |
| `BITAXELUCK_TOKEN` | Your API token from bitaxeluck.com | Yes |
| `INTERVAL` | Polling interval in seconds | No (default: 10) |
| `VERBOSE` | Enable debug output ("1" to enable) | No |

### BitAxe API

The agent reads from your BitAxe's local API:
```
GET http://<bitaxe-ip>/api/system/info
```

This returns metrics like:
- `hashRate` - Current hashrate (GH/s)
- `temp` - ASIC temperature
- `power` - Power consumption
- `sharesAccepted` / `sharesRejected` - Share counts
- `bestDiff` - Best difficulty found
- And more...

---

## Multi-Miner Setup

The agent supports monitoring multiple BitAxe miners with a single instance:

```bash
# Python - comma-separated IPs
python3 bitaxeluck-agent.py \
  --bitaxe-ip 192.168.1.50,192.168.1.51,192.168.1.52,192.168.1.53 \
  --token YOUR_TOKEN

# Docker - same approach
docker run -d --network host \
  -e BITAXE_IP=192.168.1.50,192.168.1.51,192.168.1.52 \
  -e BITAXELUCK_TOKEN=your_token \
  bitaxeluck-agent
```

**Output example:**
```
╔══════════════════════════════════════════════════════════════╗
║                    BitAxeLuck Agent                          ║
╠══════════════════════════════════════════════════════════════╣
║  Monitoring: 3 miners                                        ║
║    1. 192.168.1.50                                           ║
║    2. 192.168.1.51                                           ║
║    3. 192.168.1.52                                           ║
║  Interval:  10 seconds                                       ║
║  Target:    influx.bitaxeluck.com                           ║
╚══════════════════════════════════════════════════════════════╝

[INFO] Starting metrics collection... (Ctrl+C to stop)
[14:32:15] bitaxe-office: 523.4 GH/s | 54.2°C
[14:32:15] bitaxe-garage: 498.1 GH/s | 51.8°C
[14:32:15] bitaxe-bedroom: 510.7 GH/s | 53.0°C
[14:32:15] Summary: 3/3 miners reporting
```

---

## Supported Miners

| Miner | Native InfluxDB | Agent Needed |
|-------|-----------------|--------------|
| BitAxe (ESP-Miner) | No | **Yes** |
| NerdAxe | No | **Yes** |
| NerdQAxe+ (shufps fork) | Yes | No |
| Antminer S9/S19 | No | Future support |

---

## Troubleshooting

### Agent can't connect to BitAxe

```bash
# Test BitAxe API directly
curl http://192.168.1.50/api/system/info
```

If this fails:
- Check BitAxe IP address
- Ensure agent is on same network as BitAxe
- Check firewall rules

### No data appearing on dashboard

1. Wait 2-3 minutes after starting
2. Check agent logs for errors
3. Verify your API token is correct
4. Visit [bitaxeluck.com/dashboard](https://bitaxeluck.com/dashboard)

### Rate limiting errors

The agent has built-in rate limiting protection. If you see 429 errors:
- The agent will automatically retry with backoff
- Don't run multiple agents for the same miner

### Some miners not reporting

If using multi-miner mode and some miners fail:
- Check if those specific IPs are reachable
- Agent will warn after 5 consecutive failures per miner
- Other miners continue reporting normally

---

## Running on Raspberry Pi

```bash
# Install Python and pip
sudo apt update
sudo apt install python3 python3-pip -y

# Download and run
curl -O https://raw.githubusercontent.com/bitaxeluck/bitaxeluck/main/bitaxeluck-agent.py
pip3 install requests
python3 bitaxeluck-agent.py --bitaxe-ip 192.168.1.50,192.168.1.51 --token YOUR_TOKEN
```

**Auto-start on boot (systemd):**

```bash
sudo tee /etc/systemd/system/bitaxeluck-agent.service << EOF
[Unit]
Description=BitAxeLuck Agent
After=network.target

[Service]
Type=simple
User=pi
ExecStart=/usr/bin/python3 /home/pi/bitaxeluck-agent.py --bitaxe-ip 192.168.1.50,192.168.1.51 --token YOUR_TOKEN
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl enable bitaxeluck-agent
sudo systemctl start bitaxeluck-agent
```

---

## Links

- **Website**: [bitaxeluck.com](https://bitaxeluck.com)
- **Dashboard**: [bitaxeluck.com/dashboard](https://bitaxeluck.com/dashboard)
- **Setup Guide**: [bitaxeluck.com/setup](https://bitaxeluck.com/setup)
- **Calculator**: [bitaxeluck.com/calculator](https://bitaxeluck.com/calculator)
- **Twitter/X**: [@bitaxeluck](https://x.com/bitaxeluck)

---

## Contributing

Pull requests welcome! Please open an issue first to discuss changes.

---

## License

MIT License - see [LICENSE](LICENSE) for details.

---

## Acknowledgments

- [BitAxe](https://bitaxe.org) - Open source Bitcoin miner
- [ESP-Miner](https://github.com/bitaxeorg/ESP-Miner) - BitAxe firmware
- [CKPool](https://solo.ckpool.org) - Solo mining pool

---

**Happy mining!** May the hashes be with you.
