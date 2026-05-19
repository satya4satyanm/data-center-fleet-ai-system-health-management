# System Health Monitor

Real-time hardware health monitoring for single hosts and **data center fleets** — Python backend + React dashboard.

Metrics are pushed every **10 seconds**; the dashboard refreshes on the same interval.

---

## Prerequisites

| Component | Requirement |
|-----------|-------------|
| **Server** | Python 3.10+ |
| **Server deps** | `pip install -r requirements.txt` (installs `psutil`) |
| **Dashboard** | Node.js 18+ and npm |

From the project root (`files/`):

```bash
pip install -r requirements.txt
cd frontend && npm install && cd ..
```

---

## How to run the server

`server.py` is the backend. It collects CPU, memory, disk, GPU, network, and other metrics from the host it runs on.

### Server modes

| Mode | Command | Port (default) | Use when |
|------|---------|----------------|----------|
| **standalone** | `python server.py --mode standalone` | 8888 | One machine: hub + push from this host (simplest for local dev) |
| **hub** | `python server.py --mode hub` | 8888 | Central collector; many agents report here |
| **agent** | `python server.py --mode agent --hub http://HUB:8888` | — (or 7777 if not `--push-only`) | Each machine in the data center sends metrics to the hub |
| **local** | `python server.py` | 7777 | Single host only; `GET /metrics` JSON (legacy HTML dashboard) |

### Recommended: one computer (hub + this machine)

**Terminal 1** — starts the hub and pushes this computer’s metrics every 10 seconds:

```bash
./scripts/start-local.sh
```

Equivalent manual command:

```bash
python server.py --mode standalone --host 127.0.0.1 --port 8888 --tag site=local --interval 10
```

You should see:

```
  Standalone: hub on :8888 + this machine reporting to http://127.0.0.1:8888
  Listening on  http://127.0.0.1:8888
  Fleet API     http://127.0.0.1:8888/api/fleet
```

Verify the hub:

```bash
curl http://127.0.0.1:8888/api/health
curl http://127.0.0.1:8888/api/fleet
```

### Hub and agent on separate processes

Use this when the hub is already running and you only need **this machine** to send data:

```bash
./scripts/send-metrics.sh
```

Or:

```bash
python server.py --mode agent \
  --hub http://127.0.0.1:8888 \
  --push-only \
  --tag site=local \
  --interval 10
```

Leave the terminal open. Every ~10 seconds you should see:

```
  [HH:MM:SS] reported → http://127.0.0.1:8888 as YOUR-HOSTNAME
```

**Hub only** (monitoring server, no local metrics collection on that box unless you also run an agent):

```bash
python server.py --mode hub --host 0.0.0.0 --port 8888
```

**Agent on each data center host** (replace `YOUR_HUB_IP` with the hub’s real address):

```bash
python server.py --mode agent \
  --hub http://YOUR_HUB_IP:8888 \
  --push-only \
  --interval 10 \
  --tag rack=rack-a1 \
  --tag role=compute
```

Optional stable ID if hostnames collide:

```bash
python server.py --mode agent --hub http://YOUR_HUB_IP:8888 --system-id rack-a1-node07 --push-only
```

### Local-only server (no fleet / React hub)

For the legacy `dashboard.html` or direct JSON access:

```bash
python server.py
# or: python server.py --host 127.0.0.1 --port 7777
```

Open `http://127.0.0.1:7777/metrics` in a browser or script.

### Useful server flags

| Flag | Default | Description |
|------|---------|-------------|
| `--host` | `127.0.0.1` | Bind address (`0.0.0.0` to listen on all interfaces) |
| `--port` | `7777` (local) / `8888` (hub/standalone) | HTTP port |
| `--hub` | `http://127.0.0.1:8888` | Hub URL (agent mode) |
| `--interval` | `10` | Seconds between agent pushes |
| `--push-only` | off | Agent: push to hub only; do not bind port 7777 |
| `--tag key=value` | — | Labels shown in the dashboard (repeatable) |
| `--system-id` | hostname | Override fleet system ID |

### Server troubleshooting

| Problem | Fix |
|---------|-----|
| `Address already in use` on 8888 | A hub is already running; use `./scripts/send-metrics.sh` instead of starting another hub, or stop the existing process |
| `Address already in use` on 7777 | Use `--push-only` for the agent, or stop the other `server.py` process |
| Dashboard empty / offline | Hub must run first; agent must use `http://127.0.0.1:8888` (not a placeholder URL) |
| Agent prints `hub push failed` | Check hub is up: `curl http://127.0.0.1:8888/api/health` |

---

## How to run the dashboard

The dashboard is a **React + Vite + Tailwind** SPA in `frontend/`. It reads from the hub API (`/api/fleet`, `/api/systems/{id}`).

### Development (recommended)

**Terminal 2** (while the server/hub is running on port 8888):

```bash
cd frontend
npm install    # first time only
npm run dev
```

Open the URL Vite prints, usually:

- http://localhost:5173

If that port is busy, Vite picks the next free port (e.g. **5174**) — use whatever appears in the terminal.

The dev server **proxies** `/api/*` to `http://127.0.0.1:8888`, so you do not need CORS or `VITE_API_URL` for local development.

### Production build

```bash
cd frontend
npm run build
```

Static files are written to `frontend/dist/`. Serve them with any static file server and **proxy `/api` to the hub**, for example:

```nginx
location /api/ {
    proxy_pass http://127.0.0.1:8888/api/;
}
location / {
    root /path/to/frontend/dist;
    try_files $uri /index.html;
}
```

If the API is on another host or port, set at build time:

```bash
VITE_API_URL=http://your-hub.example.com:8888 npm run build
```

### Preview production build locally

```bash
cd frontend
npm run build
npm run preview
```

Ensure the hub is still running on port 8888, or set `VITE_API_URL` when building.

### Dashboard troubleshooting

| Problem | Fix |
|---------|-----|
| “Hub unreachable” | Start the server: `./scripts/start-local.sh` or `python server.py --mode hub` |
| Stale data | Confirm agent is running: `./scripts/send-metrics.sh` |
| Wrong port after `npm run dev` | Use the URL shown in the terminal, not an old bookmark |
| API works but UI does not update | Hard-refresh the browser; restart `npm run dev` after pulling changes |

Refresh interval is **10 seconds** (see `frontend/src/config.ts`). It should match the agent `--interval`.

---

## Full local workflow (copy-paste)

```bash
# From project root: files/

# 1. Dependencies (once)
pip install -r requirements.txt
cd frontend && npm install && cd ..

# 2. Terminal 1 — server (hub + this machine)
./scripts/start-local.sh

# 3. Terminal 2 — dashboard
cd frontend && npm run dev

# 4. Browser → http://localhost:5173 (or port shown by Vite)
```

---

## Architecture

```
┌─────────────┐     POST /api/report      ┌──────────────────┐     GET /api/fleet
│  server.py  │ ────────────────────────► │  server.py       │ ◄──────────────────  React SPA
│  --mode     │      every 10s            │  --mode hub      │      (poll 10s)
│  agent      │                           │  port 8888       │
└─────────────┘                           └──────────────────┘
   rack-A1-host01                              central monitor
   rack-A1-host02
```

---

## Hub API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/report` | POST | Agents submit metrics |
| `/api/fleet` | GET | Fleet summary for the dashboard |
| `/api/systems/{id}` | GET | Full metrics for one system |
| `/api/health` | GET | Hub status |
| `/metrics` | GET | Raw metrics from the host running the request (local/standalone) |

**Report body:**

```json
{
  "system_id": "rack-a1-node07",
  "tags": { "rack": "a1", "role": "compute" },
  "metrics": { "...": "same shape as GET /metrics" }
}
```

Systems are marked **offline** if no report is received for **35 seconds**.

---

## What's monitored

| Component | Metrics | Early failure signals |
|---|---|---|
| **CPU** | per-core %, load avg, frequency | Sustained >90% load |
| **Memory** | RAM %, swap %, available, top apps by RAM | RAM >90%, swap in use |
| **Disks** | Usage %, S.M.A.R.T. attributes | Reallocated/pending sectors > 0 |
| **GPU** | Temp, load %, VRAM, fan, power | Temp >80°C (NVIDIA/AMD) |
| **Thermals** | All sensor readings | Any sensor >80°C |
| **Network** | RX/TX rate, drops, errors | Packet drops, interface errors |
| **Battery** | Charge %, health %, cycle count | Health <80%, cycles >800 |
| **Logs** | journalctl warnings (Linux) | Kernel errors, hardware faults |

---

## Optional: Enhanced hardware access

### S.M.A.R.T. disk health (Linux)

```bash
sudo apt install smartmontools
sudo python server.py --mode agent --hub http://hub:8888 --push-only
```

### Temperature sensors (Linux)

```bash
sudo apt install lm-sensors
sudo sensors-detect
```

### NVIDIA / AMD GPU

Install `nvidia-smi` or ROCm `rocm-smi` on GPU nodes.

---

## Run as systemd services (Linux)

**Hub** — `/etc/systemd/system/syshealth-hub.service`:

```ini
[Unit]
Description=System Health Hub
After=network.target

[Service]
ExecStart=/usr/bin/python3 /path/to/server.py --mode hub --host 0.0.0.0 --port 8888
Restart=always

[Install]
WantedBy=multi-user.target
```

**Agent** — `/etc/systemd/system/syshealth-agent.service`:

```ini
[Unit]
Description=System Health Agent
After=network.target

[Service]
ExecStart=/usr/bin/python3 /path/to/server.py --mode agent --hub http://monitor.dc.local:8888 --push-only --interval 10 --tag rack=a1
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now syshealth-hub   # on monitor server
sudo systemctl enable --now syshealth-agent # on each host
```

---

## Project layout

```
server.py              # Metrics collector + hub + agent
requirements.txt
scripts/
  start-local.sh       # Hub + this machine (one command)
  send-metrics.sh      # Push only (hub already running)
dashboard.html         # Legacy single-host HTML dashboard
frontend/              # React + Vite + Tailwind SPA
  src/config.ts        # Dashboard refresh interval (10s)
  src/pages/           # Fleet overview, system detail
```

---

## Legacy HTML dashboard

With local mode (`python server.py` on port 7777), open `dashboard.html` in a browser. It polls `http://127.0.0.1:7777/metrics` every 5 seconds. For fleet monitoring, use the React dashboard instead.

---

## AI analysis example

```python
import requests, anthropic

fleet = requests.get("http://localhost:8888/api/fleet").json()
client = anthropic.Anthropic()
msg = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=1024,
    messages=[{
        "role": "user",
        "content": f"Analyze this data center fleet health and flag risks:\n{fleet}"
    }]
)
print(msg.content[0].text)
```
