# WLANMeter

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey.svg)]()

**Bandwidth & WLAN Quality Measurement Tool**

Measures internet speed (download/upload), WLAN signal quality, and logs results over time for network analysis and troubleshooting.

## Features

- **WLAN Signal Quality** – Signal strength (dBm), quality percentage, SNR, link speed
- **Internet Speed Test** – Download/Upload bandwidth, latency, jitter
- **Quality Rating** – Automatic assessment (Excellent → Poor)
- **Cross-platform** – Windows, Linux, macOS
- **Zero Dependencies** – Pure Python stdlib
- **Flexible Output** – CSV, JSON Lines (JSONL)
- **Configurable** – Test intervals, file sizes, modes

## Installation

```bash
git clone https://github.com/m0h1nd4/wlanmeter.git
cd wlanmeter

# Make executable (Linux/macOS)
chmod +x wlanmeter.py
```

### Requirements

- Python 3.8+
- No external dependencies
- Admin/root NOT required for basic operation

## Quick Start

```bash
# Single measurement (WLAN + Speed)
python wlanmeter.py

# 10 measurements, every 60 seconds
python wlanmeter.py -c 10 -i 60

# Only WLAN quality (fast, no speed test)
python wlanmeter.py --wlan-only -c 5

# Only speed test
python wlanmeter.py --speed-only

# Log to file every 5 minutes
python wlanmeter.py -o wlan_log.csv -i 300

# Quick test (small file, no upload)
python wlanmeter.py --size small --skip-upload
```

## Usage

```
usage: wlanmeter [-h] [-V] [-c COUNT] [-i INTERVAL] [--size {small,medium,large}]
                 [--skip-upload] [--wlan-only] [--speed-only] [-o OUTPUT]
                 [-f {csv,jsonl}] [-q]

Measurement:
  -c, --count COUNT       Number of measurements (default: infinite)
  -i, --interval SEC      Interval between measurements (default: 60)
  --size {small,medium,large}
                          Speed test file size (default: medium)
                          small=1MB, medium=10MB, large=100MB
  --skip-upload           Skip upload test (faster)

Mode:
  --wlan-only             Only measure WLAN quality
  --speed-only            Only run speed test

Output:
  -o, --output FILE       Output file path
  -f, --format {csv,jsonl}  Output format (default: csv)
  -q, --quiet             Suppress console output
```

## WLAN Quality Ratings

| Rating | Signal (dBm) | Quality | Description |
|--------|--------------|---------|-------------|
| **Excellent** | ≥ -50 | 100% | Perfect signal, max performance |
| **Very Good** | ≥ -60 | 80% | Strong signal, excellent performance |
| **Good** | ≥ -67 | 60% | Reliable for all applications |
| **Fair** | ≥ -70 | 40% | Usable, may have occasional issues |
| **Weak** | ≥ -80 | 20% | Connectivity problems likely |
| **Poor** | < -80 | 10% | Unreliable, frequent disconnects |

### What the Numbers Mean

| Metric | Good | Concerning | Action Needed |
|--------|------|------------|---------------|
| Signal Strength | > -65 dBm | -65 to -75 dBm | < -75 dBm |
| SNR (Signal-to-Noise) | > 25 dB | 15-25 dB | < 15 dB |
| Link Speed | > 100 Mbps | 50-100 Mbps | < 50 Mbps |

## Output Formats

### CSV (Default)

Semicolon-delimited, Excel-compatible:

```csv
timestamp;ssid;signal_dbm;signal_pct;quality_rating;link_speed_mbps;channel;band;snr_db;download_mbps;upload_mbps;ping_ms;jitter_ms
2024-01-15T14:30:00;MyNetwork;-52;96;Excellent;866.0;36;5GHz;45;245.32;48.76;12.5;2.3
2024-01-15T14:31:00;MyNetwork;-58;84;Very Good;866.0;36;5GHz;38;198.45;45.23;14.2;3.1
```

### JSON Lines (JSONL)

```json
{"timestamp":"2024-01-15T14:30:00","wlan":{"ssid":"MyNetwork","signal_strength_dbm":-52,"signal_quality_pct":96,"quality_rating":"Excellent","link_speed_mbps":866.0,"channel":36,"band":"5GHz"},"speed":{"download_mbps":245.32,"upload_mbps":48.76,"ping_ms":12.5,"jitter_ms":2.3}}
```

## Example Output

```
══════════════════════════════════════════════════════════════════
  WLANMeter v1.0.0 - Bandwidth & WLAN Quality Monitor
══════════════════════════════════════════════════════════════════
  Interval:      60s
  Test Size:     medium
  Skip Upload:   False
  Output:        wlan_log.csv
  Format:        csv
══════════════════════════════════════════════════════════════════
  Press Ctrl+C to stop

──────────────────────────────────────────────────────
  Measurement #1 @ 14:30:00
──────────────────────────────────────────────────────
  📶 WLAN Quality:
     SSID:      MyNetwork
     Signal:    -52 dBm (96%) - Excellent
     Link:      866.0 Mbit/s
     Band:      5GHz (Ch. 36)
     SNR:       45 dB
  🚀 Speed Test:
     Download:  245.32 Mbit/s
     Upload:    48.76 Mbit/s
     Ping:      12.5 ms (Jitter: 2.3 ms)

  Next measurement in 60s...
```

## Advanced Usage

### Long-term Monitoring

```bash
# Monitor for 24 hours, log every 5 minutes (288 samples)
python wlanmeter.py -c 288 -i 300 -o daily_log.csv

# Continuous monitoring with small tests (less bandwidth usage)
python wlanmeter.py --size small --skip-upload -i 120 -o monitor.csv
```

### WLAN Survey (Signal Mapping)

```bash
# Quick signal check at different locations
python wlanmeter.py --wlan-only -c 1

# Walk around and run at each location to map signal strength
```

### Speed Test Only

```bash
# Thorough speed test with large file
python wlanmeter.py --speed-only --size large -c 3
```

### Automation / Cron

```bash
# Add to crontab for hourly logging
# crontab -e
0 * * * * /usr/bin/python3 /path/to/wlanmeter.py -c 1 -q -o /var/log/wlan_hourly.csv
```

### Systemd Service

```ini
# /etc/systemd/system/wlanmeter.service
[Unit]
Description=WLAN Quality Monitor
After=network-online.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /opt/wlanmeter/wlanmeter.py -i 300 -o /var/log/wlanmeter.csv -q
Restart=always

[Install]
WantedBy=multi-user.target
```

---

## Data Analysis

### Analysis Prompt for LLM/AI

Use this prompt with Claude, GPT-4, or similar for WLAN quality analysis:

```
You are a wireless network engineer analyzing WLAN quality data to diagnose connectivity issues and optimize network performance.

## Input Data Format

The data is from WLANMeter, a WLAN quality and bandwidth monitoring tool. Fields:

**WLAN Metrics:**
- `ssid`: Network name
- `signal_dbm`: Signal strength in dBm (higher = better, typical range -30 to -90)
- `signal_pct`: Signal quality percentage
- `quality_rating`: Categorical rating (Excellent/Very Good/Good/Fair/Weak/Poor)
- `link_speed_mbps`: Negotiated link speed with AP
- `channel`: WiFi channel number
- `band`: Frequency band (2.4GHz/5GHz/6GHz)
- `snr_db`: Signal-to-Noise Ratio (higher = better, >25dB is good)

**Speed Metrics:**
- `download_mbps`: Download speed in Megabits per second
- `upload_mbps`: Upload speed in Megabits per second
- `ping_ms`: Latency to test server
- `jitter_ms`: Latency variation

## Analysis Requirements

### 1. Signal Quality Assessment
- Average signal strength and variance
- Percentage of time in each quality tier
- Correlation between signal strength and actual throughput
- Identify signal degradation patterns

### 2. Performance Analysis
- Download/Upload speed consistency
- Speed vs signal strength correlation
- Identify bottleneck (WLAN vs ISP)
- Calculate utilization ratio (actual speed / link speed)

### 3. Temporal Patterns
- Time-of-day variations
- Congestion patterns (busy hours)
- Signal stability over time

### 4. Recommendations
Based on the data, provide actionable recommendations:

**If signal is weak (<-70 dBm):**
- Relocate router or device
- Consider range extender/mesh
- Check for interference sources

**If signal strong but speed low:**
- Channel congestion (recommend channel change)
- ISP throttling
- Router/AP limitations

**If high jitter/variable speeds:**
- Interference from other networks
- Microwave/Bluetooth interference
- Too many connected devices

### 5. Optimization Suggestions
- Optimal channel recommendation
- Band steering advice (2.4 vs 5GHz)
- QoS configuration suggestions
- Hardware upgrade recommendations if needed

## Data

```
[PASTE DATA HERE]
```
```

### Quick Analysis with Python

```python
import pandas as pd

# Load data
df = pd.read_csv('wlan_log.csv', sep=';', parse_dates=['timestamp'])

# Basic stats
print(f"Total samples: {len(df)}")
print(f"\nSignal Strength (dBm):")
print(f"  Min: {df['signal_dbm'].min()}")
print(f"  Max: {df['signal_dbm'].max()}")
print(f"  Avg: {df['signal_dbm'].mean():.1f}")

print(f"\nQuality Distribution:")
print(df['quality_rating'].value_counts())

print(f"\nDownload Speed (Mbit/s):")
print(f"  Min: {df['download_mbps'].min():.2f}")
print(f"  Max: {df['download_mbps'].max():.2f}")
print(f"  Avg: {df['download_mbps'].mean():.2f}")

# Correlation
corr = df['signal_dbm'].corr(df['download_mbps'])
print(f"\nSignal-Speed Correlation: {corr:.3f}")
```

### Visualization with Matplotlib

```python
import matplotlib.pyplot as plt
import pandas as pd

df = pd.read_csv('wlan_log.csv', sep=';', parse_dates=['timestamp'])

fig, axes = plt.subplots(2, 2, figsize=(14, 10))

# Signal over time
axes[0,0].plot(df['timestamp'], df['signal_dbm'], 'b-', alpha=0.7)
axes[0,0].axhline(y=-67, color='g', linestyle='--', label='Good threshold')
axes[0,0].axhline(y=-80, color='r', linestyle='--', label='Weak threshold')
axes[0,0].set_ylabel('Signal (dBm)')
axes[0,0].set_title('Signal Strength Over Time')
axes[0,0].legend()

# Download speed over time
axes[0,1].plot(df['timestamp'], df['download_mbps'], 'g-', alpha=0.7)
axes[0,1].set_ylabel('Download (Mbit/s)')
axes[0,1].set_title('Download Speed Over Time')

# Signal vs Speed scatter
axes[1,0].scatter(df['signal_dbm'], df['download_mbps'], alpha=0.5)
axes[1,0].set_xlabel('Signal (dBm)')
axes[1,0].set_ylabel('Download (Mbit/s)')
axes[1,0].set_title('Signal vs Download Speed')

# Quality distribution
df['quality_rating'].value_counts().plot(kind='bar', ax=axes[1,1], color='steelblue')
axes[1,1].set_title('Quality Rating Distribution')
axes[1,1].set_ylabel('Count')

plt.tight_layout()
plt.savefig('wlan_analysis.png', dpi=150)
plt.show()
```

---

## Platform Notes

### Windows
- Uses `netsh wlan show interfaces`
- Signal reported as percentage, converted to dBm approximation
- Works without admin rights

### Linux
- Uses `iw` and `iwconfig`
- Requires wireless interface (check with `ip link`)
- May need to be in `netdev` group for some systems

### macOS
- Uses `/System/Library/PrivateFrameworks/Apple80211.framework/.../airport`
- Full signal metrics including noise floor

---

## Troubleshooting

### "No WLAN info available"

- **Windows**: Ensure WiFi is connected, not Ethernet
- **Linux**: Check interface exists: `ip link | grep wl`
- **macOS**: Check airport utility exists

### Speed test fails

- Check internet connectivity
- Firewall may block test servers
- Try `--size small` for slower connections

### Inaccurate signal readings

- Windows only provides quality %, dBm is approximated
- For precise measurements on Windows, use dedicated WiFi analyzers

---

## Comparison with NetDiag

| Feature | WLANMeter | NetDiag |
|---------|-----------|---------|
| **Purpose** | Bandwidth & signal quality | Latency & connectivity |
| **Speed Test** | ✅ Download/Upload | ❌ |
| **WLAN Signal** | ✅ dBm, SNR, Link Speed | ❌ |
| **Latency** | ✅ Ping, Jitter | ✅ Multi-target |
| **Packet Loss** | ❌ | ✅ |
| **Gateway Test** | ❌ | ✅ |
| **ISP Detection** | Via speed | Via ping pattern |
| **Mobile Version** | ❌ | ✅ |

**Use together for complete diagnostics:**
```bash
# Terminal 1: Latency monitoring
python netdiag.py -o latency.csv

# Terminal 2: Bandwidth monitoring (every 5 min)
python wlanmeter.py -i 300 -o bandwidth.csv
```

---

## Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

## License

MIT License – see [LICENSE](LICENSE) for details.

## Acknowledgments

- Speed test servers provided by Tele2 and OVH
- Signal quality thresholds based on industry standards
