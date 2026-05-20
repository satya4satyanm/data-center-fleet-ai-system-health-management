#!/usr/bin/env python3
"""
System Health Monitor — Backend Server
Collects real hardware metrics and serves them as JSON over HTTP.
Supports Linux, macOS, and Windows.

Modes:
    local   — single-machine metrics at GET /metrics (default)
    hub     — data-center collector; agents POST reports here
    agent   — collect locally and push to a hub every N seconds

Usage:
    pip install psutil
    python server.py                          # local agent UI backend
    python server.py --mode hub --port 8888   # central data-center hub
    python server.py --mode agent --hub http://monitor.dc:8888
"""

import json
import platform
import subprocess
import shutil
import time
import re
import urllib.request
import urllib.error
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread, Lock
from urllib.parse import urlparse, unquote
import psutil

# Fleet registry (hub mode): system_id -> { metrics, tags, last_seen, ... }
_fleet_lock = Lock()
_fleet_systems = {}
STALE_AFTER_SEC = 30  # inactive if no report within 30s (~3 missed at 10s interval)

OS = platform.system()  # 'Linux', 'Darwin', 'Windows'

# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _run(cmd, timeout=4):
    """Run a shell command and return stdout, or '' on failure."""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=timeout
        )
        return result.stdout.strip()
    except Exception:
        return ""


def _safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


# ──────────────────────────────────────────────
# CPU
# ──────────────────────────────────────────────

def get_cpu():
    per_core = psutil.cpu_percent(interval=0.5, percpu=True)
    freq = psutil.cpu_freq()
    load_avg = _safe(lambda: list(psutil.getloadavg()), [0, 0, 0])

    cores = [{"id": i, "pct": round(p, 1)} for i, p in enumerate(per_core)]
    avg = round(sum(p["pct"] for p in cores) / max(len(cores), 1), 1)

    return {
        "cores": cores,
        "avg_pct": avg,
        "freq_mhz": round(freq.current) if freq else None,
        "freq_max_mhz": round(freq.max) if freq else None,
        "load_avg_1m": round(load_avg[0], 2),
        "load_avg_5m": round(load_avg[1], 2),
        "load_avg_15m": round(load_avg[2], 2),
        "count_physical": psutil.cpu_count(logical=False),
        "count_logical": psutil.cpu_count(logical=True),
        "status": "critical" if avg > 90 else "warning" if avg > 75 else "ok",
    }


# ──────────────────────────────────────────────
# Memory
# ──────────────────────────────────────────────

def get_memory():
    vm = psutil.virtual_memory()
    sw = psutil.swap_memory()
    pct = round(vm.percent, 1)

    # psutil.percent is (total - available) / total on all platforms, but
    # psutil.used is narrower on macOS (active + wired only, excludes cache
    # and compressed memory). Use total - available for "used" so the bar,
    # percentage, and GB figures all agree (matches Activity Monitor pressure).
    used_bytes = vm.total - vm.available
    total_mb = round(vm.total / 1024 / 1024)
    used_mb = round(used_bytes / 1024 / 1024)
    available_mb = round(vm.available / 1024 / 1024)

    result = {
        "total_mb": total_mb,
        "used_mb": used_mb,
        "available_mb": available_mb,
        "pct": pct,
        "swap_total_mb": round(sw.total / 1024 / 1024),
        "swap_used_mb": round(sw.used / 1024 / 1024),
        "swap_pct": round(sw.percent, 1),
        "status": "critical" if pct > 92 else "warning" if pct > 80 else "ok",
    }

    # Narrow "app" footprint (active + wired on macOS) for optional breakdown
    app_used_mb = round(vm.used / 1024 / 1024)
    if app_used_mb != used_mb:
        result["app_used_mb"] = app_used_mb

    result["top_apps"] = get_top_memory_apps()
    return result


# Suffixes stripped when grouping helper/renderer processes under one app name
_APP_SUFFIXES = (
    " Helper (Renderer)",
    " Helper (GPU)",
    " Helper (Plugin)",
    " Helper",
    " Renderer",
    " GPU Process",
    " Content Process",
    " Network Service",
    " Web Content",
)


def _app_group_name(name):
    """Collapse Chrome/Safari helpers into a single application label."""
    n = (name or "unknown").strip()
    if n.lower().endswith(".exe"):
        n = n[:-4]
    for suffix in _APP_SUFFIXES:
        if n.endswith(suffix):
            return n[: -len(suffix)].strip()
    if " Helper" in n:
        return n.split(" Helper", 1)[0].strip()
    return n


def get_top_memory_apps(limit=12):
    """Return processes grouped by app name, sorted by total RSS descending."""
    groups = {}
    total = psutil.virtual_memory().total

    for proc in psutil.process_iter(["name", "memory_info", "status"]):
        try:
            info = proc.info
            if info["status"] == psutil.STATUS_ZOMBIE:
                continue
            mem = info.get("memory_info")
            if not mem:
                continue
            rss = mem.rss
            if rss < 5 * 1024 * 1024:  # ignore processes under 5 MB
                continue
            display = _app_group_name(info["name"])
            key = display.lower()
            bucket = groups.setdefault(key, {"name": display, "mem_bytes": 0, "processes": 0})
            if len(display) > len(bucket["name"]):
                bucket["name"] = display
            bucket["mem_bytes"] += rss
            bucket["processes"] += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    ranked = sorted(groups.items(), key=lambda item: item[1]["mem_bytes"], reverse=True)
    apps = []
    for _key, g in ranked[:limit]:
        mem_mb = round(g["mem_bytes"] / 1024 / 1024, 1)
        apps.append({
            "name": g["name"],
            "mem_mb": mem_mb,
            "mem_pct": round(g["mem_bytes"] / total * 100, 1),
            "processes": g["processes"],
        })
    return apps


# ──────────────────────────────────────────────
# Disk — usage + S.M.A.R.T.
# ──────────────────────────────────────────────

def _smart_linux(device):
    """Parse smartctl output for key health attributes."""
    out = _run(f"smartctl -A {device} 2>/dev/null")
    attrs = {}
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 10:
            name = parts[1]
            raw = parts[9]
            try:
                attrs[name] = int(raw)
            except ValueError:
                attrs[name] = raw
    return {
        "reallocated_sectors": attrs.get("Reallocated_Sector_Ct", 0),
        "pending_sectors": attrs.get("Current_Pending_Sector", 0),
        "uncorrectable": attrs.get("Offline_Uncorrectable", 0),
        "power_on_hours": attrs.get("Power_On_Hours", None),
        "temperature_c": attrs.get("Temperature_Celsius", None),
    }


def _smart_nvme_linux(device):
    out = _run(f"smartctl -A {device} 2>/dev/null")
    result = {"reallocated_sectors": 0, "pending_sectors": 0, "uncorrectable": 0}
    for line in out.splitlines():
        l = line.lower()
        if "media_and_data_integrity_errors" in l or "media and data integrity" in l:
            try:
                result["uncorrectable"] = int(line.split()[-1])
            except Exception:
                pass
        if "percentage_used" in l or "percentage used" in l:
            try:
                result["wear_pct"] = int(line.split()[-1].replace("%", ""))
            except Exception:
                pass
        if "temperature" in l and "sensor" not in l:
            m = re.search(r"(\d+)\s*(celsius|°c)?", l)
            if m:
                result["temperature_c"] = int(m.group(1))
    return result


def get_disks():
    disks = []
    for part in psutil.disk_partitions(all=False):
        # Skip unreadable / virtual partitions
        if part.fstype in ("", "squashfs", "tmpfs", "devtmpfs", "overlay"):
            continue
        try:
            usage = psutil.disk_usage(part.mountpoint)
        except PermissionError:
            continue

        pct = round(usage.percent, 1)
        smart = {}

        if OS == "Linux" and shutil.which("smartctl"):
            dev = part.device
            if "nvme" in dev:
                smart = _smart_nvme_linux(dev)
            else:
                smart = _smart_linux(dev)

        reallocated = smart.get("reallocated_sectors", 0)
        pending = smart.get("pending_sectors", 0)
        uncorrectable = smart.get("uncorrectable", 0)

        status = "ok"
        if uncorrectable > 0 or pending > 5 or reallocated > 5:
            status = "critical"
        elif pending > 0 or reallocated > 0 or pct > 90:
            status = "warning"

        disks.append({
            "device": part.device,
            "mountpoint": part.mountpoint,
            "fstype": part.fstype,
            "total_gb": round(usage.total / 1e9, 1),
            "used_gb": round(usage.used / 1e9, 1),
            "free_gb": round(usage.free / 1e9, 1),
            "pct": pct,
            "smart": smart,
            "status": status,
        })

    return disks


# ──────────────────────────────────────────────
# GPU (NVIDIA via nvidia-smi, AMD via rocm-smi)
# ──────────────────────────────────────────────

def get_gpu():
    gpus = []

    # NVIDIA
    if shutil.which("nvidia-smi"):
        out = _run(
            "nvidia-smi --query-gpu=name,temperature.gpu,utilization.gpu,"
            "memory.used,memory.total,fan.speed,power.draw,power.limit "
            "--format=csv,noheader,nounits"
        )
        for i, line in enumerate(out.splitlines()):
            parts = [p.strip() for p in line.split(",")]
            if len(parts) < 8:
                continue
            try:
                temp = int(parts[1])
                load = int(parts[2])
                mem_used = int(parts[3])
                mem_total = int(parts[4])
                fan = parts[5] if parts[5] != "[N/A]" else None
                power_draw = float(parts[6]) if parts[6] not in ("[N/A]", "N/A") else None
                power_limit = float(parts[7]) if parts[7] not in ("[N/A]", "N/A") else None
                gpus.append({
                    "id": i,
                    "name": parts[0],
                    "vendor": "nvidia",
                    "temp_c": temp,
                    "load_pct": load,
                    "mem_used_mb": mem_used,
                    "mem_total_mb": mem_total,
                    "mem_pct": round(mem_used / max(mem_total, 1) * 100, 1),
                    "fan_pct": int(fan) if fan else None,
                    "power_draw_w": power_draw,
                    "power_limit_w": power_limit,
                    "status": "critical" if temp >= 90 else "warning" if temp >= 80 else "ok",
                })
            except (ValueError, IndexError):
                pass

    # AMD
    elif shutil.which("rocm-smi"):
        out = _run("rocm-smi --showtemp --showuse --showmemuse --csv 2>/dev/null")
        for i, line in enumerate(out.splitlines()[1:], start=0):
            parts = line.split(",")
            if len(parts) < 4:
                continue
            try:
                temp = float(parts[1])
                load = float(parts[2])
                mem_pct = float(parts[3])
                gpus.append({
                    "id": i,
                    "name": f"AMD GPU {i}",
                    "vendor": "amd",
                    "temp_c": round(temp),
                    "load_pct": round(load),
                    "mem_pct": round(mem_pct),
                    "status": "critical" if temp >= 90 else "warning" if temp >= 80 else "ok",
                })
            except (ValueError, IndexError):
                pass

    return gpus


# ──────────────────────────────────────────────
# Temperatures (lm-sensors / macOS)
# ──────────────────────────────────────────────

def get_thermals():
    sensors = []

    if OS == "Linux" and shutil.which("sensors"):
        out = _run("sensors -j 2>/dev/null")
        try:
            data = json.loads(out)
            for chip, readings in data.items():
                for feature, values in readings.items():
                    if not isinstance(values, dict):
                        continue
                    for key, val in values.items():
                        if "input" in key and isinstance(val, (int, float)):
                            temp = round(val, 1)
                            sensors.append({
                                "chip": chip,
                                "name": feature,
                                "temp_c": temp,
                                "status": "critical" if temp >= 90 else "warning" if temp >= 75 else "ok",
                            })
        except (json.JSONDecodeError, KeyError):
            # Fallback: plain text parse
            for line in _run("sensors 2>/dev/null").splitlines():
                m = re.search(r"^([^:]+):\s+\+?([\d.]+)°C", line)
                if m:
                    temp = float(m.group(2))
                    sensors.append({
                        "chip": "unknown",
                        "name": m.group(1).strip(),
                        "temp_c": temp,
                        "status": "critical" if temp >= 90 else "warning" if temp >= 75 else "ok",
                    })

    elif OS == "Darwin":
        # macOS: use osx-cpu-temp or powermetrics (needs sudo); graceful fallback
        out = _run("osx-cpu-temp 2>/dev/null")
        if out:
            m = re.search(r"([\d.]+)", out)
            if m:
                temp = float(m.group(1))
                sensors.append({"chip": "cpu", "name": "CPU temp", "temp_c": temp,
                                 "status": "critical" if temp >= 90 else "warning" if temp >= 75 else "ok"})

    # psutil can provide temps on some platforms
    if hasattr(psutil, "sensors_temperatures"):
        raw = _safe(psutil.sensors_temperatures, {})
        for chip, entries in raw.items():
            for e in entries:
                if e.current and e.current > 0:
                    sensors.append({
                        "chip": chip,
                        "name": e.label or chip,
                        "temp_c": round(e.current, 1),
                        "high": e.high,
                        "critical": e.critical,
                        "status": (
                            "critical" if (e.critical and e.current >= e.critical) or e.current >= 95
                            else "warning" if (e.high and e.current >= e.high) or e.current >= 80
                            else "ok"
                        ),
                    })

    # Deduplicate by name
    seen = set()
    unique = []
    for s in sensors:
        key = s["name"].lower()
        if key not in seen:
            seen.add(key)
            unique.append(s)
    return unique[:16]  # cap at 16 sensors


# ──────────────────────────────────────────────
# Network
# ──────────────────────────────────────────────

_prev_net = {}
_prev_net_time = 0

def get_network():
    global _prev_net, _prev_net_time

    counters = psutil.net_io_counters(pernic=True)
    now = time.time()
    dt = max(now - _prev_net_time, 1)
    interfaces = []

    for iface, stats in counters.items():
        if iface == "lo":
            continue
        prev = _prev_net.get(iface)
        rx_rate = tx_rate = 0
        if prev:
            rx_rate = max(0, (stats.bytes_recv - prev.bytes_recv) / dt)
            tx_rate = max(0, (stats.bytes_sent - prev.bytes_sent) / dt)

        interfaces.append({
            "name": iface,
            "rx_bytes_total": stats.bytes_recv,
            "tx_bytes_total": stats.bytes_sent,
            "rx_rate_kbps": round(rx_rate / 1024, 1),
            "tx_rate_kbps": round(tx_rate / 1024, 1),
            "packets_recv": stats.packets_recv,
            "packets_sent": stats.packets_sent,
            "errors_in": stats.errin,
            "errors_out": stats.errout,
            "drops_in": stats.dropin,
            "drops_out": stats.dropout,
            "status": (
                "warning" if stats.errin + stats.errout > 10 or stats.dropin + stats.dropout > 50
                else "ok"
            ),
        })

    _prev_net = counters
    _prev_net_time = now
    return interfaces


# ──────────────────────────────────────────────
# Battery
# ──────────────────────────────────────────────

def get_battery():
    bat = _safe(psutil.sensors_battery)
    if not bat:
        return {"present": False}

    result = {
        "present": True,
        "pct": round(bat.percent, 1),
        "plugged_in": bat.power_plugged,
        "status": "Charging" if bat.power_plugged else "Discharging",
    }

    if bat.secsleft not in (psutil.POWER_TIME_UNLIMITED, psutil.POWER_TIME_UNKNOWN, -1, -2):
        remaining = str(timedelta(seconds=int(bat.secsleft)))
        result["time_remaining"] = remaining

    # Linux: read extra battery info from sysfs
    if OS == "Linux":
        def _sysfs(path):
            try:
                with open(path) as f:
                    return f.read().strip()
            except Exception:
                return None

        import glob
        for bat_path in glob.glob("/sys/class/power_supply/BAT*"):
            energy_full = _sysfs(f"{bat_path}/energy_full")
            energy_full_design = _sysfs(f"{bat_path}/energy_full_design")
            cycle_count = _sysfs(f"{bat_path}/cycle_count")
            manufacturer = _sysfs(f"{bat_path}/manufacturer")
            model = _sysfs(f"{bat_path}/model_name")

            if energy_full and energy_full_design:
                try:
                    health = round(int(energy_full) / int(energy_full_design) * 100, 1)
                    result["health_pct"] = min(health, 100)
                except Exception:
                    pass
            if cycle_count:
                try:
                    result["cycle_count"] = int(cycle_count)
                except Exception:
                    pass
            if manufacturer:
                result["manufacturer"] = manufacturer
            if model:
                result["model"] = model
            break

    status = "ok"
    if result.get("health_pct", 100) < 80 or result.get("cycle_count", 0) > 800:
        status = "warning"
    if result["pct"] < 10 and not result["plugged_in"]:
        status = "critical"
    result["status"] = status

    return result


# ──────────────────────────────────────────────
# System info + uptime
# ──────────────────────────────────────────────

def get_system_info():
    boot_time = _safe(psutil.boot_time)
    uptime_sec = int(time.time() - boot_time) if boot_time else None
    uptime_str = str(timedelta(seconds=uptime_sec)) if uptime_sec is not None else "unknown"

    info = {
        "hostname": platform.node(),
        "os": platform.system(),
        "os_version": platform.version(),
        "os_release": platform.release(),
        "machine": platform.machine(),
        "python": platform.python_version(),
        "uptime_str": uptime_str,
    }
    if boot_time:
        info["boot_time"] = datetime.fromtimestamp(boot_time).isoformat()
        info["uptime_seconds"] = uptime_sec
    return info


# ──────────────────────────────────────────────
# Recent system log warnings (Linux/macOS)
# ──────────────────────────────────────────────

def get_logs():
    entries = []

    if OS == "Linux" and shutil.which("journalctl"):
        out = _run('journalctl -p warning --since "2 hours ago" --no-pager -n 30 --output=short-iso 2>/dev/null')
        for line in out.splitlines():
            parts = line.split(None, 4)
            if len(parts) >= 5:
                entries.append({"time": parts[0], "host": parts[1], "unit": parts[2], "msg": parts[4][:200]})

    elif OS == "Darwin":
        out = _run('log show --style syslog --predicate \'messageType == error\' --last 2h 2>/dev/null | tail -30')
        for line in out.splitlines():
            if line.strip():
                entries.append({"time": "", "host": "", "unit": "", "msg": line[:200]})

    return entries[-20:]


# ──────────────────────────────────────────────
# Master metrics collector
# ──────────────────────────────────────────────

def collect_all():
    return {
        "timestamp": datetime.now().isoformat(),
        "system": get_system_info(),
        "cpu": get_cpu(),
        "memory": get_memory(),
        "disks": get_disks(),
        "gpu": get_gpu(),
        "thermals": get_thermals(),
        "network": get_network(),
        "battery": get_battery(),
        "logs": get_logs(),
    }


# ──────────────────────────────────────────────
# Fleet / hub helpers
# ──────────────────────────────────────────────

def _worst_status(*statuses):
    if any(s == "critical" for s in statuses):
        return "critical"
    if any(s == "warning" for s in statuses):
        return "warning"
    return "ok"


def compute_fleet_status(metrics):
    """Derive overall health from a full metrics payload."""
    parts = [
        metrics.get("cpu", {}).get("status", "ok"),
        metrics.get("memory", {}).get("status", "ok"),
    ]
    for dk in metrics.get("disks") or []:
        parts.append(dk.get("status", "ok"))
    for g in metrics.get("gpu") or []:
        parts.append(g.get("status", "ok"))
    for t in metrics.get("thermals") or []:
        parts.append(t.get("status", "ok"))
    for n in metrics.get("network") or []:
        parts.append(n.get("status", "ok"))
    bat = metrics.get("battery") or {}
    if bat.get("present"):
        parts.append(bat.get("status", "ok"))
    return _worst_status(*parts)


def _fleet_summary(system_id, entry, now=None):
    now = now or time.time()
    metrics = entry.get("metrics") or {}
    system = metrics.get("system") or {}
    last_seen = entry.get("last_seen", 0)
    age = now - last_seen
    online = age <= STALE_AFTER_SEC
    status = "offline" if not online else entry.get("status", "ok")
    return {
        "id": system_id,
        "hostname": system.get("hostname", system_id),
        "os": system.get("os"),
        "os_release": system.get("os_release"),
        "machine": system.get("machine"),
        "uptime_str": system.get("uptime_str"),
        "tags": entry.get("tags") or {},
        "status": status,
        "online": online,
        "last_seen": datetime.fromtimestamp(last_seen).isoformat() if last_seen else None,
        "last_seen_ago_sec": round(age, 1),
        "timestamp": metrics.get("timestamp"),
        "cpu_pct": metrics.get("cpu", {}).get("avg_pct"),
        "memory_pct": metrics.get("memory", {}).get("pct"),
        "load_avg_1m": metrics.get("cpu", {}).get("load_avg_1m"),
        "alert_count": entry.get("alert_count", 0),
    }


def _count_alerts(metrics):
    n = 0
    if metrics.get("cpu", {}).get("status") in ("warning", "critical"):
        n += 1
    if metrics.get("memory", {}).get("status") in ("warning", "critical"):
        n += 1
    for dk in metrics.get("disks") or []:
        if dk.get("status") in ("warning", "critical"):
            n += 1
    for g in metrics.get("gpu") or []:
        if g.get("status") in ("warning", "critical"):
            n += 1
    for t in metrics.get("thermals") or []:
        if t.get("status") in ("warning", "critical"):
            n += 1
    return n


def register_report(system_id, metrics, tags=None):
    with _fleet_lock:
        status = compute_fleet_status(metrics)
        _fleet_systems[system_id] = {
            "metrics": metrics,
            "tags": tags or {},
            "status": status,
            "alert_count": _count_alerts(metrics),
            "last_seen": time.time(),
        }


def get_fleet_snapshot():
    now = time.time()
    with _fleet_lock:
        systems = [
            _fleet_summary(sid, entry, now)
            for sid, entry in sorted(_fleet_systems.items())
        ]
    counts = {"ok": 0, "warning": 0, "critical": 0, "offline": 0}
    for s in systems:
        key = s["status"] if s["status"] in counts else "offline"
        counts[key] += 1
    return {
        "timestamp": datetime.now().isoformat(),
        "total": len(systems),
        "counts": counts,
        "systems": systems,
    }


def get_system_metrics(system_id):
    with _fleet_lock:
        entry = _fleet_systems.get(system_id)
        if not entry:
            return None
        return {
            "id": system_id,
            "status": entry.get("status", "ok"),
            "tags": entry.get("tags") or {},
            "last_seen": datetime.fromtimestamp(entry["last_seen"]).isoformat(),
            "metrics": entry["metrics"],
        }


def push_to_hub(hub_url, system_id=None, tags=None, interval=10):
    base = hub_url.rstrip("/")
    report_url = f"{base}/api/report"
    sid = system_id or platform.node()

    def _push_once():
        metrics = collect_all()
        payload = json.dumps({
            "system_id": sid,
            "tags": tags or {},
            "metrics": metrics,
        }).encode()
        req = urllib.request.Request(
            report_url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            if resp.status == 200:
                print(f"  [{datetime.now().strftime('%H:%M:%S')}] reported → {base} as {sid}")

    def _loop():
        while True:
            try:
                _push_once()
            except Exception as e:
                print(f"  [{datetime.now().strftime('%H:%M:%S')}] hub push failed: {e}")
            time.sleep(interval)

    t = Thread(target=_loop, daemon=True)
    t.start()
    return t


def hub_url_for_bind(host, port):
    """URL agents use to reach a hub bound on host:port (handles 0.0.0.0)."""
    if host in ("0.0.0.0", "", "::"):
        return f"http://127.0.0.1:{port}"
    if host == "::1":
        return f"http://[::1]:{port}"
    return f"http://{host}:{port}"


# ──────────────────────────────────────────────
# HTTP Server
# ──────────────────────────────────────────────

def _cors_headers(handler):
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type")


def _json_response(handler, code, obj):
    body = json.dumps(obj, indent=2).encode()
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    _cors_headers(handler)
    handler.end_headers()
    handler.wfile.write(body)


class MetricsHandler(BaseHTTPRequestHandler):
    mode = "local"

    def do_OPTIONS(self):
        self.send_response(204)
        _cors_headers(self)
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path.rstrip("/") or "/"

        if path in ("/metrics", "/metrics/"):
            data = collect_all()
            _json_response(self, 200, data)
            return

        if self.mode == "hub":
            if path in ("/api/fleet", "/api/fleet/"):
                _json_response(self, 200, get_fleet_snapshot())
                return
            if path.startswith("/api/systems/"):
                system_id = unquote(path.split("/api/systems/", 1)[1])
                data = get_system_metrics(system_id)
                if data is None:
                    _json_response(self, 404, {"error": "system not found", "id": system_id})
                else:
                    _json_response(self, 200, data)
                return

        if path in ("/", "/health", "/api/health"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            _cors_headers(self)
            self.end_headers()
            payload = {
                "status": "ok",
                "mode": self.mode,
                "systems": len(_fleet_systems) if self.mode == "hub" else 1,
            }
            self.wfile.write(json.dumps(payload).encode())
            return

        self.send_response(404)
        _cors_headers(self)
        self.end_headers()

    def do_POST(self):
        if self.mode != "hub":
            self.send_response(404)
            self.end_headers()
            return

        path = urlparse(self.path).path.rstrip("/")
        if path not in ("/api/report", "/api/report/"):
            self.send_response(404)
            self.end_headers()
            return

        length = int(self.headers.get("Content-Length", 0))
        try:
            raw = self.rfile.read(length).decode() if length else "{}"
            body = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError):
            _json_response(self, 400, {"error": "invalid JSON body"})
            return

        metrics = body.get("metrics")
        if not metrics:
            _json_response(self, 400, {"error": "missing metrics object"})
            return

        system_id = body.get("system_id") or metrics.get("system", {}).get("hostname")
        if not system_id:
            _json_response(self, 400, {"error": "missing system_id"})
            return

        register_report(system_id, metrics, tags=body.get("tags"))
        _json_response(self, 200, {
            "ok": True,
            "system_id": system_id,
            "status": compute_fleet_status(metrics),
        })

    def log_message(self, fmt, *args):
        print(f"  [{datetime.now().strftime('%H:%M:%S')}] {args[0]} {args[1]}")


def run_server(host="127.0.0.1", port=7777, mode="local"):
    MetricsHandler.mode = mode
    server = HTTPServer((host, port), MetricsHandler)
    print(f"\n  System Health Monitor ({mode})")
    print(f"  ─────────────────────────────────")
    print(f"  Listening on  http://{host}:{port}")
    if mode == "local":
        print(f"  Metrics at    http://{host}:{port}/metrics")
    if mode == "hub":
        print(f"  Fleet API     http://{host}:{port}/api/fleet")
        print(f"  Report POST   http://{host}:{port}/api/report")
    print(f"  Press Ctrl+C to stop\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Server stopped.")


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="System Health Monitor backend")
    p.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    p.add_argument("--port", type=int, default=7777, help="Port (default: 7777)")
    p.add_argument(
        "--mode",
        choices=("local", "hub", "agent", "standalone"),
        default="local",
        help="local | hub | agent | standalone (hub + this machine on one host)",
    )
    p.add_argument("--hub", default="http://127.0.0.1:8888", help="Hub URL (agent mode)")
    p.add_argument("--system-id", default=None, help="Override system id for agent reports")
    p.add_argument("--tag", action="append", default=[], help="Tags as key=value (agent mode)")
    p.add_argument("--interval", type=int, default=10, help="Agent push interval seconds (default: 10)")
    p.add_argument(
        "--push-only",
        action="store_true",
        help="Agent: push to hub only (do not bind local :7777)",
    )
    args = p.parse_args()

    tags = {}
    for item in args.tag:
        if "=" in item:
            k, v = item.split("=", 1)
            tags[k.strip()] = v.strip()

    if args.mode == "agent":
        push_to_hub(args.hub, system_id=args.system_id, tags=tags or None, interval=args.interval)
        print(f"  Agent pushing to {args.hub} every {args.interval}s")
        if args.push_only:
            print("  Press Ctrl+C to stop\n")
            try:
                while True:
                    time.sleep(3600)
            except KeyboardInterrupt:
                print("\n  Agent stopped.")
        else:
            hub_port = args.port if args.port != 7777 else 7777
            run_server(args.host, hub_port, mode="local")
    elif args.mode == "standalone":
        port = 8888 if args.port == 7777 else args.port
        hub = hub_url_for_bind(args.host, port)
        push_to_hub(hub, system_id=args.system_id, tags=tags or None, interval=args.interval)
        print(f"  Standalone: hub on :{port} + this machine reporting to {hub}")
        run_server(args.host, port, mode="hub")
    elif args.mode == "hub":
        if args.port == 7777:
            args.port = 8888
        run_server(args.host, args.port, mode="hub")
    else:
        run_server(args.host, args.port, mode="local")
