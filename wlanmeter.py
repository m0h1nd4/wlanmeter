#!/usr/bin/env python3
"""
WLANMeter - Bandwidth & WLAN Quality Measurement Tool
Measures internet speed, WLAN signal quality, and logs results over time.

Author: [Your Name]
License: MIT
"""

import argparse
import csv
import json
import os
import platform
import re
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
import urllib.error
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from concurrent.futures import ThreadPoolExecutor
from collections import deque

__version__ = "1.0.0"

# --- Test File URLs for Speed Test ---
# Various sizes for adaptive testing
SPEED_TEST_URLS = {
    "small": [  # ~1 MB - quick test
        "http://speedtest.tele2.net/1MB.zip",
        "http://proof.ovh.net/files/1Mb.dat",
    ],
    "medium": [  # ~10 MB - standard test
        "http://speedtest.tele2.net/10MB.zip",
        "http://proof.ovh.net/files/10Mb.dat",
    ],
    "large": [  # ~100 MB - thorough test
        "http://speedtest.tele2.net/100MB.zip",
        "http://proof.ovh.net/files/100Mb.dat",
    ]
}

# Upload test endpoints (POST endpoints that accept data)
UPLOAD_TEST_URLS = [
    "http://speedtest.tele2.net/upload.php",
    "https://httpbin.org/post",
]


# --- Data Classes ---

@dataclass
class WLANInfo:
    """WLAN adapter information and signal quality."""
    timestamp: str
    interface: str
    ssid: str
    bssid: str
    channel: Optional[int]
    frequency_mhz: Optional[int]
    signal_strength_dbm: Optional[int]
    signal_quality_pct: Optional[int]
    link_speed_mbps: Optional[float]
    tx_rate_mbps: Optional[float]
    rx_rate_mbps: Optional[float]
    noise_dbm: Optional[int]
    snr_db: Optional[int]  # Signal-to-Noise Ratio
    band: Optional[str]  # 2.4GHz / 5GHz / 6GHz
    standard: Optional[str]  # 802.11ac, 802.11ax, etc.
    security: Optional[str]
    
    def get_quality_rating(self) -> Tuple[str, int]:
        """
        Rate WLAN quality based on signal strength.
        Returns (rating_text, score 0-100)
        """
        if self.signal_strength_dbm is None:
            return "Unknown", 0
        
        dbm = self.signal_strength_dbm
        
        if dbm >= -50:
            return "Excellent", 100
        elif dbm >= -60:
            return "Very Good", 80
        elif dbm >= -67:
            return "Good", 60
        elif dbm >= -70:
            return "Fair", 40
        elif dbm >= -80:
            return "Weak", 20
        else:
            return "Poor", 10
    
    def to_dict(self) -> dict:
        d = asdict(self)
        rating, score = self.get_quality_rating()
        d["quality_rating"] = rating
        d["quality_score"] = score
        return d


@dataclass
class SpeedTestResult:
    """Speed test measurement result."""
    timestamp: str
    download_mbps: Optional[float]
    upload_mbps: Optional[float]
    ping_ms: Optional[float]
    jitter_ms: Optional[float]
    test_server: Optional[str]
    test_duration_sec: float
    bytes_downloaded: int
    bytes_uploaded: int
    success: bool
    error: Optional[str] = None
    
    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CombinedResult:
    """Combined WLAN + Speed measurement."""
    timestamp: str
    wlan: Optional[WLANInfo]
    speed: Optional[SpeedTestResult]
    
    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "wlan": self.wlan.to_dict() if self.wlan else None,
            "speed": self.speed.to_dict() if self.speed else None
        }


# --- WLAN Quality Measurement ---

class WLANScanner:
    """Platform-independent WLAN information scanner."""
    
    @staticmethod
    def get_wlan_info() -> Optional[WLANInfo]:
        """Get current WLAN connection info."""
        system = platform.system().lower()
        timestamp = datetime.now().isoformat()
        
        try:
            if system == "windows":
                return WLANScanner._get_windows_wlan(timestamp)
            elif system == "linux":
                return WLANScanner._get_linux_wlan(timestamp)
            elif system == "darwin":
                return WLANScanner._get_macos_wlan(timestamp)
            else:
                return None
        except Exception as e:
            print(f"Error getting WLAN info: {e}", file=sys.stderr)
            return None
    
    @staticmethod
    def _get_windows_wlan(timestamp: str) -> Optional[WLANInfo]:
        """Get WLAN info on Windows via netsh."""
        try:
            output = subprocess.check_output(
                ["netsh", "wlan", "show", "interfaces"],
                text=True, stderr=subprocess.DEVNULL,
                encoding='utf-8', errors='ignore'
            )
            
            # Parse output
            info = {}
            for line in output.split('\n'):
                if ':' in line:
                    key, _, value = line.partition(':')
                    info[key.strip().lower()] = value.strip()
            
            # Extract values (handle German/English)
            ssid = info.get('ssid') or info.get('ssid-name', '')
            bssid = info.get('bssid') or info.get('bssid-adresse', '')
            
            # Signal strength (German: "Signal", English: "Signal")
            signal_str = info.get('signal', '0%').replace('%', '')
            signal_pct = int(signal_str) if signal_str.isdigit() else None
            
            # Convert percentage to dBm (approximate)
            signal_dbm = None
            if signal_pct is not None:
                # Windows reports quality %, convert to approximate dBm
                # 100% ≈ -50 dBm, 0% ≈ -100 dBm
                signal_dbm = int(-100 + (signal_pct / 2))
            
            # Channel
            channel_str = info.get('channel') or info.get('kanal', '')
            channel = int(channel_str) if channel_str.isdigit() else None
            
            # Frequency (derive from channel if not available)
            frequency = None
            if channel:
                if channel <= 14:
                    frequency = 2412 + (channel - 1) * 5
                elif channel >= 36:
                    frequency = 5180 + (channel - 36) * 5
            
            # Link speed
            speed_str = info.get('receive rate (mbps)') or info.get('empfangsrate (mbit/s)', '')
            speed_str = speed_str.replace(',', '.')
            rx_rate = float(speed_str) if speed_str.replace('.', '').isdigit() else None
            
            tx_str = info.get('transmit rate (mbps)') or info.get('übertragungsrate (mbit/s)', '')
            tx_str = tx_str.replace(',', '.')
            tx_rate = float(tx_str) if tx_str.replace('.', '').isdigit() else None
            
            # Radio type / Standard
            radio = info.get('radio type') or info.get('funktyp', '')
            
            # Band detection
            band = None
            if frequency:
                if frequency < 3000:
                    band = "2.4GHz"
                elif frequency < 6000:
                    band = "5GHz"
                else:
                    band = "6GHz"
            
            # Interface name
            interface = info.get('name') or info.get('name', 'WLAN')
            
            return WLANInfo(
                timestamp=timestamp,
                interface=interface,
                ssid=ssid,
                bssid=bssid,
                channel=channel,
                frequency_mhz=frequency,
                signal_strength_dbm=signal_dbm,
                signal_quality_pct=signal_pct,
                link_speed_mbps=rx_rate,
                tx_rate_mbps=tx_rate,
                rx_rate_mbps=rx_rate,
                noise_dbm=None,  # Not available on Windows
                snr_db=None,
                band=band,
                standard=radio,
                security=info.get('authentication') or info.get('authentifizierung')
            )
            
        except (subprocess.CalledProcessError, FileNotFoundError):
            return None
    
    @staticmethod
    def _get_linux_wlan(timestamp: str) -> Optional[WLANInfo]:
        """Get WLAN info on Linux via iwconfig/iw."""
        interface = WLANScanner._find_linux_wlan_interface()
        if not interface:
            return None
        
        try:
            # Try iw first (more modern)
            output = subprocess.check_output(
                ["iw", "dev", interface, "link"],
                text=True, stderr=subprocess.DEVNULL
            )
            
            info = {}
            ssid = ""
            bssid = ""
            frequency = None
            signal_dbm = None
            tx_rate = None
            
            for line in output.split('\n'):
                line = line.strip()
                if line.startswith("SSID:"):
                    ssid = line.split(":", 1)[1].strip()
                elif line.startswith("Connected to"):
                    bssid = line.split()[2]
                elif "freq:" in line:
                    match = re.search(r'freq:\s*(\d+)', line)
                    if match:
                        frequency = int(match.group(1))
                elif "signal:" in line:
                    match = re.search(r'signal:\s*(-?\d+)', line)
                    if match:
                        signal_dbm = int(match.group(1))
                elif "tx bitrate:" in line:
                    match = re.search(r'tx bitrate:\s*([\d.]+)', line)
                    if match:
                        tx_rate = float(match.group(1))
            
            # Get additional info from iwconfig
            try:
                iw_output = subprocess.check_output(
                    ["iwconfig", interface],
                    text=True, stderr=subprocess.DEVNULL
                )
                
                # Extract link quality
                match = re.search(r'Link Quality[=:](\d+)/(\d+)', iw_output)
                quality_pct = None
                if match:
                    quality_pct = int((int(match.group(1)) / int(match.group(2))) * 100)
                
                # Noise level
                noise_match = re.search(r'Noise level[=:](-?\d+)', iw_output)
                noise_dbm = int(noise_match.group(1)) if noise_match else None
                
            except:
                quality_pct = None
                noise_dbm = None
            
            # Derive channel from frequency
            channel = None
            if frequency:
                if frequency >= 2412 and frequency <= 2484:
                    channel = (frequency - 2412) // 5 + 1
                elif frequency >= 5180:
                    channel = (frequency - 5180) // 5 + 36
            
            # Band
            band = None
            if frequency:
                if frequency < 3000:
                    band = "2.4GHz"
                elif frequency < 6000:
                    band = "5GHz"
                else:
                    band = "6GHz"
            
            # Convert signal to quality if not available
            if quality_pct is None and signal_dbm is not None:
                quality_pct = max(0, min(100, 2 * (signal_dbm + 100)))
            
            # SNR
            snr = None
            if signal_dbm is not None and noise_dbm is not None:
                snr = signal_dbm - noise_dbm
            
            return WLANInfo(
                timestamp=timestamp,
                interface=interface,
                ssid=ssid,
                bssid=bssid,
                channel=channel,
                frequency_mhz=frequency,
                signal_strength_dbm=signal_dbm,
                signal_quality_pct=quality_pct,
                link_speed_mbps=tx_rate,
                tx_rate_mbps=tx_rate,
                rx_rate_mbps=None,
                noise_dbm=noise_dbm,
                snr_db=snr,
                band=band,
                standard=None,
                security=None
            )
            
        except (subprocess.CalledProcessError, FileNotFoundError):
            return None
    
    @staticmethod
    def _get_macos_wlan(timestamp: str) -> Optional[WLANInfo]:
        """Get WLAN info on macOS via airport utility."""
        try:
            # airport utility path
            airport = "/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport"
            
            output = subprocess.check_output(
                [airport, "-I"],
                text=True, stderr=subprocess.DEVNULL
            )
            
            info = {}
            for line in output.split('\n'):
                if ':' in line:
                    key, _, value = line.partition(':')
                    info[key.strip().lower()] = value.strip()
            
            ssid = info.get('ssid', '')
            bssid = info.get('bssid', '')
            
            channel_str = info.get('channel', '')
            # Channel might be "36,1" for channel 36, width 1
            channel = int(channel_str.split(',')[0]) if channel_str else None
            
            signal_dbm = None
            if 'agrctlrssi' in info:
                signal_dbm = int(info['agrctlrssi'])
            
            noise_dbm = None
            if 'agrctlnoise' in info:
                noise_dbm = int(info['agrctlnoise'])
            
            # Link speed
            tx_rate = None
            if 'lastTxRate' in info.get('lasttxrate', ''):
                tx_rate = float(info['lasttxrate'])
            elif 'lasttxrate' in info:
                tx_rate = float(info['lasttxrate'])
            
            # SNR
            snr = None
            if signal_dbm is not None and noise_dbm is not None:
                snr = signal_dbm - noise_dbm
            
            # Quality percentage
            quality_pct = None
            if signal_dbm is not None:
                quality_pct = max(0, min(100, 2 * (signal_dbm + 100)))
            
            # Frequency (derive from channel)
            frequency = None
            if channel:
                if channel <= 14:
                    frequency = 2412 + (channel - 1) * 5
                elif channel >= 36:
                    frequency = 5180 + (channel - 36) * 5
            
            band = None
            if frequency:
                if frequency < 3000:
                    band = "2.4GHz"
                elif frequency < 6000:
                    band = "5GHz"
                else:
                    band = "6GHz"
            
            return WLANInfo(
                timestamp=timestamp,
                interface="en0",
                ssid=ssid,
                bssid=bssid,
                channel=channel,
                frequency_mhz=frequency,
                signal_strength_dbm=signal_dbm,
                signal_quality_pct=quality_pct,
                link_speed_mbps=tx_rate,
                tx_rate_mbps=tx_rate,
                rx_rate_mbps=None,
                noise_dbm=noise_dbm,
                snr_db=snr,
                band=band,
                standard=None,
                security=None
            )
            
        except (subprocess.CalledProcessError, FileNotFoundError):
            return None
    
    @staticmethod
    def _find_linux_wlan_interface() -> Optional[str]:
        """Find the active WLAN interface on Linux."""
        try:
            # Check /sys/class/net for wireless interfaces
            net_path = Path("/sys/class/net")
            for iface in net_path.iterdir():
                if (iface / "wireless").exists():
                    return iface.name
            
            # Fallback: try common names
            for name in ["wlan0", "wlp2s0", "wlp3s0", "wifi0"]:
                if (net_path / name).exists():
                    return name
                    
        except:
            pass
        
        return None


# --- Speed Test ---

class SpeedTester:
    """Internet speed measurement."""
    
    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self._stop_flag = False
    
    def stop(self):
        self._stop_flag = True
    
    def measure_download(self, size: str = "medium") -> Tuple[Optional[float], int, float]:
        """
        Measure download speed.
        Returns (speed_mbps, bytes_downloaded, duration_sec)
        """
        urls = SPEED_TEST_URLS.get(size, SPEED_TEST_URLS["medium"])
        
        for url in urls:
            if self._stop_flag:
                return None, 0, 0
            
            try:
                # Create request with headers
                req = urllib.request.Request(url)
                req.add_header('User-Agent', 'WLANMeter/1.0')
                
                start_time = time.perf_counter()
                bytes_downloaded = 0
                
                with urllib.request.urlopen(req, timeout=self.timeout) as response:
                    # Read in chunks
                    chunk_size = 1024 * 64  # 64KB chunks
                    while True:
                        if self._stop_flag:
                            break
                        chunk = response.read(chunk_size)
                        if not chunk:
                            break
                        bytes_downloaded += len(chunk)
                
                end_time = time.perf_counter()
                duration = end_time - start_time
                
                if duration > 0 and bytes_downloaded > 0:
                    speed_mbps = (bytes_downloaded * 8) / (duration * 1_000_000)
                    return speed_mbps, bytes_downloaded, duration
                    
            except Exception as e:
                continue
        
        return None, 0, 0
    
    def measure_upload(self, size_mb: float = 2.0) -> Tuple[Optional[float], int, float]:
        """
        Measure upload speed.
        Returns (speed_mbps, bytes_uploaded, duration_sec)
        """
        # Generate random data for upload
        data_size = int(size_mb * 1024 * 1024)
        data = os.urandom(data_size)
        
        for url in UPLOAD_TEST_URLS:
            if self._stop_flag:
                return None, 0, 0
            
            try:
                req = urllib.request.Request(url, data=data, method='POST')
                req.add_header('User-Agent', 'WLANMeter/1.0')
                req.add_header('Content-Type', 'application/octet-stream')
                req.add_header('Content-Length', str(len(data)))
                
                start_time = time.perf_counter()
                
                with urllib.request.urlopen(req, timeout=self.timeout) as response:
                    response.read()
                
                end_time = time.perf_counter()
                duration = end_time - start_time
                
                if duration > 0:
                    speed_mbps = (data_size * 8) / (duration * 1_000_000)
                    return speed_mbps, data_size, duration
                    
            except Exception as e:
                continue
        
        return None, 0, 0
    
    def measure_latency(self, host: str = "8.8.8.8", port: int = 53, samples: int = 5) -> Tuple[Optional[float], Optional[float]]:
        """
        Measure latency via TCP connect.
        Returns (avg_ping_ms, jitter_ms)
        """
        latencies = []
        
        for _ in range(samples):
            if self._stop_flag:
                break
            
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(2)
                
                start = time.perf_counter()
                sock.connect((host, port))
                end = time.perf_counter()
                sock.close()
                
                latencies.append((end - start) * 1000)
                
            except:
                continue
        
        if not latencies:
            return None, None
        
        avg_ping = sum(latencies) / len(latencies)
        
        # Calculate jitter (average deviation)
        if len(latencies) > 1:
            jitter = sum(abs(latencies[i] - latencies[i-1]) for i in range(1, len(latencies))) / (len(latencies) - 1)
        else:
            jitter = 0
        
        return round(avg_ping, 2), round(jitter, 2)
    
    def run_full_test(self, test_size: str = "medium", skip_upload: bool = False) -> SpeedTestResult:
        """Run complete speed test."""
        timestamp = datetime.now().isoformat()
        start_time = time.perf_counter()
        
        # Latency
        ping_ms, jitter_ms = self.measure_latency()
        
        # Download
        download_mbps, bytes_down, _ = self.measure_download(test_size)
        
        # Upload
        upload_mbps = None
        bytes_up = 0
        if not skip_upload and not self._stop_flag:
            upload_mbps, bytes_up, _ = self.measure_upload()
        
        duration = time.perf_counter() - start_time
        
        success = download_mbps is not None
        
        return SpeedTestResult(
            timestamp=timestamp,
            download_mbps=round(download_mbps, 2) if download_mbps else None,
            upload_mbps=round(upload_mbps, 2) if upload_mbps else None,
            ping_ms=ping_ms,
            jitter_ms=jitter_ms,
            test_server="speedtest.tele2.net",
            test_duration_sec=round(duration, 2),
            bytes_downloaded=bytes_down,
            bytes_uploaded=bytes_up,
            success=success,
            error=None if success else "Speed test failed"
        )


# --- Main Application ---

class WLANMeter:
    """Main WLAN measurement application."""
    
    def __init__(
        self,
        interval: int = 60,
        output_file: Optional[Path] = None,
        output_format: str = "csv",
        test_size: str = "medium",
        skip_upload: bool = False,
        wlan_only: bool = False,
        speed_only: bool = False,
        quiet: bool = False
    ):
        self.interval = interval
        self.output_file = output_file
        self.output_format = output_format
        self.test_size = test_size
        self.skip_upload = skip_upload
        self.wlan_only = wlan_only
        self.speed_only = speed_only
        self.quiet = quiet
        
        self.running = False
        self.scanner = WLANScanner()
        self.speed_tester = SpeedTester()
        
        # Statistics
        self.measurements: List[CombinedResult] = []
    
    def _print_header(self):
        """Print startup header."""
        if self.quiet:
            return
        
        print(f"\n{'='*65}")
        print(f"  WLANMeter v{__version__} - Bandwidth & WLAN Quality Monitor")
        print(f"{'='*65}")
        print(f"  Interval:      {self.interval}s")
        print(f"  Test Size:     {self.test_size}")
        print(f"  Skip Upload:   {self.skip_upload}")
        print(f"  Output:        {self.output_file or 'stdout only'}")
        print(f"  Format:        {self.output_format}")
        print(f"{'='*65}")
        print("  Press Ctrl+C to stop\n")
    
    def _print_wlan_info(self, wlan: WLANInfo):
        """Print WLAN information."""
        rating, score = wlan.get_quality_rating()
        
        # Color based on quality
        if score >= 60:
            color = "\033[92m"  # Green
        elif score >= 40:
            color = "\033[93m"  # Yellow
        else:
            color = "\033[91m"  # Red
        reset = "\033[0m"
        
        print(f"  📶 WLAN Quality:")
        print(f"     SSID:      {wlan.ssid}")
        print(f"     Signal:    {color}{wlan.signal_strength_dbm} dBm ({wlan.signal_quality_pct}%) - {rating}{reset}")
        if wlan.link_speed_mbps:
            print(f"     Link:      {wlan.link_speed_mbps} Mbit/s")
        if wlan.band:
            print(f"     Band:      {wlan.band} (Ch. {wlan.channel})")
        if wlan.snr_db:
            print(f"     SNR:       {wlan.snr_db} dB")
    
    def _print_speed_info(self, speed: SpeedTestResult):
        """Print speed test results."""
        if not speed.success:
            print(f"  ⚠️  Speed test failed: {speed.error}")
            return
        
        # Color for download speed
        if speed.download_mbps:
            if speed.download_mbps >= 100:
                color = "\033[92m"
            elif speed.download_mbps >= 25:
                color = "\033[93m"
            else:
                color = "\033[91m"
        else:
            color = "\033[91m"
        reset = "\033[0m"
        
        print(f"  🚀 Speed Test:")
        print(f"     Download:  {color}{speed.download_mbps or 'N/A'} Mbit/s{reset}")
        print(f"     Upload:    {speed.upload_mbps or 'N/A'} Mbit/s")
        print(f"     Ping:      {speed.ping_ms or 'N/A'} ms (Jitter: {speed.jitter_ms or 'N/A'} ms)")
    
    def _write_result(self, result: CombinedResult, file, write_header: bool = False):
        """Write result to file."""
        if self.output_format == "jsonl":
            file.write(json.dumps(result.to_dict(), ensure_ascii=False) + '\n')
        elif self.output_format == "csv":
            if write_header:
                headers = ["timestamp"]
                if not self.speed_only:
                    headers.extend([
                        "ssid", "signal_dbm", "signal_pct", "quality_rating",
                        "link_speed_mbps", "channel", "band", "snr_db"
                    ])
                if not self.wlan_only:
                    headers.extend([
                        "download_mbps", "upload_mbps", "ping_ms", "jitter_ms"
                    ])
                file.write(";".join(headers) + '\n')
            
            row = [result.timestamp]
            
            if not self.speed_only and result.wlan:
                rating, _ = result.wlan.get_quality_rating()
                row.extend([
                    result.wlan.ssid,
                    str(result.wlan.signal_strength_dbm or ""),
                    str(result.wlan.signal_quality_pct or ""),
                    rating,
                    str(result.wlan.link_speed_mbps or ""),
                    str(result.wlan.channel or ""),
                    result.wlan.band or "",
                    str(result.wlan.snr_db or "")
                ])
            elif not self.speed_only:
                row.extend([""] * 8)
            
            if not self.wlan_only and result.speed:
                row.extend([
                    str(result.speed.download_mbps or ""),
                    str(result.speed.upload_mbps or ""),
                    str(result.speed.ping_ms or ""),
                    str(result.speed.jitter_ms or "")
                ])
            elif not self.wlan_only:
                row.extend([""] * 4)
            
            file.write(";".join(row) + '\n')
        
        file.flush()
    
    def run_single(self) -> CombinedResult:
        """Run a single measurement."""
        timestamp = datetime.now().isoformat()
        
        wlan = None
        speed = None
        
        if not self.speed_only:
            wlan = self.scanner.get_wlan_info()
        
        if not self.wlan_only:
            speed = self.speed_tester.run_full_test(
                test_size=self.test_size,
                skip_upload=self.skip_upload
            )
        
        return CombinedResult(
            timestamp=timestamp,
            wlan=wlan,
            speed=speed
        )
    
    def run(self, count: Optional[int] = None):
        """Run measurement loop."""
        self.running = True
        self._print_header()
        
        file = None
        write_header = True
        
        if self.output_file:
            self.output_file.parent.mkdir(parents=True, exist_ok=True)
            file = open(self.output_file, "a", encoding="utf-8")
            write_header = self.output_file.stat().st_size == 0 if self.output_file.exists() else True
        
        iteration = 0
        
        try:
            while self.running:
                iteration += 1
                
                if not self.quiet:
                    print(f"\n{'─'*50}")
                    print(f"  Measurement #{iteration} @ {datetime.now().strftime('%H:%M:%S')}")
                    print(f"{'─'*50}")
                
                result = self.run_single()
                self.measurements.append(result)
                
                if not self.quiet:
                    if result.wlan:
                        self._print_wlan_info(result.wlan)
                    if result.speed:
                        self._print_speed_info(result.speed)
                
                if file:
                    self._write_result(result, file, write_header)
                    write_header = False
                
                # Check count
                if count and iteration >= count:
                    break
                
                # Wait for next interval
                if self.running and (count is None or iteration < count):
                    if not self.quiet:
                        print(f"\n  Next measurement in {self.interval}s...")
                    time.sleep(self.interval)
                    
        except KeyboardInterrupt:
            pass
        finally:
            self.running = False
            self.speed_tester.stop()
            if file:
                file.close()
            
            self._print_summary()
    
    def _print_summary(self):
        """Print summary statistics."""
        if self.quiet or not self.measurements:
            return
        
        print(f"\n{'='*65}")
        print("  SUMMARY")
        print(f"{'='*65}")
        print(f"  Total measurements: {len(self.measurements)}")
        
        # WLAN stats
        wlan_results = [m.wlan for m in self.measurements if m.wlan]
        if wlan_results:
            signals = [w.signal_strength_dbm for w in wlan_results if w.signal_strength_dbm]
            if signals:
                print(f"\n  📶 WLAN Signal:")
                print(f"     Min:  {min(signals)} dBm")
                print(f"     Max:  {max(signals)} dBm")
                print(f"     Avg:  {sum(signals)/len(signals):.1f} dBm")
        
        # Speed stats
        speed_results = [m.speed for m in self.measurements if m.speed and m.speed.success]
        if speed_results:
            downloads = [s.download_mbps for s in speed_results if s.download_mbps]
            uploads = [s.upload_mbps for s in speed_results if s.upload_mbps]
            
            if downloads:
                print(f"\n  🚀 Download Speed:")
                print(f"     Min:  {min(downloads):.2f} Mbit/s")
                print(f"     Max:  {max(downloads):.2f} Mbit/s")
                print(f"     Avg:  {sum(downloads)/len(downloads):.2f} Mbit/s")
            
            if uploads:
                print(f"\n  📤 Upload Speed:")
                print(f"     Min:  {min(uploads):.2f} Mbit/s")
                print(f"     Max:  {max(uploads):.2f} Mbit/s")
                print(f"     Avg:  {sum(uploads)/len(uploads):.2f} Mbit/s")
        
        print()


# --- CLI ---

def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="wlanmeter",
        description="WLANMeter - Bandwidth & WLAN Quality Measurement Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  wlanmeter                           # Single measurement
  wlanmeter -c 10 -i 60               # 10 measurements, 60s interval
  wlanmeter --wlan-only               # Only WLAN quality (no speed test)
  wlanmeter --speed-only              # Only speed test
  wlanmeter -o log.csv -i 300         # Log every 5 minutes
  wlanmeter --size large              # Use 100MB test file
  wlanmeter --skip-upload             # Skip upload test (faster)

Quality Ratings:
  Excellent  : >= -50 dBm (100%%)
  Very Good  : >= -60 dBm (80%%)
  Good       : >= -67 dBm (60%%)
  Fair       : >= -70 dBm (40%%)
  Weak       : >= -80 dBm (20%%)
  Poor       : <  -80 dBm
        """
    )
    
    parser.add_argument("-V", "--version", action="version", version=f"%(prog)s {__version__}")
    
    # Measurement options
    measure_group = parser.add_argument_group("Measurement")
    measure_group.add_argument(
        "-c", "--count",
        type=int,
        help="Number of measurements (default: infinite)"
    )
    measure_group.add_argument(
        "-i", "--interval",
        type=int,
        default=60,
        help="Interval between measurements in seconds (default: 60)"
    )
    measure_group.add_argument(
        "--size",
        choices=["small", "medium", "large"],
        default="medium",
        help="Speed test file size: small=1MB, medium=10MB, large=100MB (default: medium)"
    )
    measure_group.add_argument(
        "--skip-upload",
        action="store_true",
        help="Skip upload test (faster)"
    )
    
    # Mode selection
    mode_group = parser.add_argument_group("Mode")
    mode_group.add_argument(
        "--wlan-only",
        action="store_true",
        help="Only measure WLAN quality (no speed test)"
    )
    mode_group.add_argument(
        "--speed-only",
        action="store_true",
        help="Only run speed test (no WLAN info)"
    )
    
    # Output
    output_group = parser.add_argument_group("Output")
    output_group.add_argument(
        "-o", "--output",
        type=Path,
        help="Output file path"
    )
    output_group.add_argument(
        "-f", "--format",
        choices=["csv", "jsonl"],
        default="csv",
        help="Output format (default: csv)"
    )
    output_group.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Suppress console output"
    )
    
    return parser


def main():
    parser = create_parser()
    args = parser.parse_args()
    
    meter = WLANMeter(
        interval=args.interval,
        output_file=args.output,
        output_format=args.format,
        test_size=args.size,
        skip_upload=args.skip_upload,
        wlan_only=args.wlan_only,
        speed_only=args.speed_only,
        quiet=args.quiet
    )
    
    # Signal handlers
    def signal_handler(sig, frame):
        meter.running = False
        meter.speed_tester.stop()
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Run
    meter.run(count=args.count)


if __name__ == "__main__":
    main()
