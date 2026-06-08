# ROSscope 🔭
 
> Open source observability platform for ROS 2 robot fleets.
 
ROSscope gives robotics engineers real-time visibility into their ROS 2 systems topic health, service availability, node lifecycle states, inter-node relationships, anomaly detection, and alert management. Think Datadog, built for robots.
 
[![Docker Pulls](https://img.shields.io/docker/pulls/jawadglitch/rosscope)](https://hub.docker.com/r/jawadglitch/rosscope)
[![GitHub release](https://img.shields.io/github/v/release/jawad-glitch/ROSscope)](https://github.com/jawad-glitch/ROSscope/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
 
---
 
## The Problem
 
When something goes wrong on a robot fleet, you find out when the robot stops moving. There's no unified tool that:
- Watches your entire ROS 2 graph in real time
- Detects degraded communication before it causes failures
- Maps which nodes are connected to which
- Manages alerts from detection to resolution
- Deploys in one command
ROSscope fixes that.
 
---
 
## Features
 
- **Topic monitoring** - publish rate (Hz), message count, publisher count per topic
- **Service monitoring** - discovery and server availability across the fleet
- **Lifecycle monitoring** - managed node state tracking (unconfigured/inactive/active/finalized)
- **Anomaly detection** - z-score statistical baseline per topic, no threshold tuning required
- **Alert management** - firing → acknowledged → resolved states with notes
- **Computation graph** - live directed graph of publisher/subscriber relationships
- **Graph visualization** - interactive D3.js force-directed graph
- **Web UI** - overview, topics, alerts, and graph pages at `http://localhost:8001`
- **Prometheus exporter** - 15 custom ROS 2 metrics over HTTP
- **Grafana dashboard** - pre-built, auto-provisioned, zero manual setup
- **Slack + email notifications** - alerts delivered to your team automatically
- **Configurable** - `rosscope.yaml` controls all behavior
- **One command install** - `curl -sSL .../install.sh | bash`
---
 
## Quickstart
 
### One-line install (recommended)
 
```bash
curl -sSL https://raw.githubusercontent.com/jawad-glitch/ROSscope/main/install.sh | bash
```
 
This downloads everything and starts Prometheus + Grafana automatically.
 
Then start the collector:
```bash
cd rosscope
python3 main.py
```
 
### Clone and run (developers)
 
**Requirements:**
- Docker + Docker Compose
- ROS 2 Humble (Ubuntu 22.04)
- Python 3.10+
```bash
git clone https://github.com/jawad-glitch/ROSscope.git
cd ROSscope
./start.sh
```
 
### Docker image
 
```bash
docker pull jawadglitch/rosscope:latest
```
 
---
 
## Access
 
| Service | URL | Credentials |
|---------|-----|-------------|
| ROSscope Web UI | http://localhost:8001 | — |
| Grafana dashboard | http://localhost:3000 | admin / rosscope |
| Prometheus metrics | http://localhost:8000/metrics | — |
| Graph API | http://localhost:8001/api/graph | — |
| Alerts API | http://localhost:8001/api/alerts | — |
 
---
 
## Architecture
 
```
Your ROS 2 Robot Fleet
        │
        ▼
┌──────────────────────────────────────┐
│         ROSscope Collectors           │
│  TopicCollector    — Hz, anomaly      │
│  ServiceCollector  — availability     │
│  LifecycleCollector— node states      │
│  GraphCollector    — relationships    │
│  AnomalyDetector   — z-score          │
│  AlertManager      — lifecycle        │
│  NotificationManager — Slack/email   │
└──────────┬───────────────────────────┘
           │
     ┌─────┴──────┐
     ▼            ▼
:8000/metrics  :8001
Prometheus     Web UI + Graph API + Alerts API
Exporter
     │
     ▼
Prometheus :9090
     │
     ▼
Grafana :3000
```
 
---
 
## Configuration
 
Edit `rosscope.yaml` to customize behavior — no code changes needed:
 
```yaml
rosscope:
  # Collection
  collection_interval: 5        # seconds between metric scans
 
  # Anomaly detection
  anomaly_threshold: 3.0        # z-score threshold (3.0 = 0.3% false positive rate)
  anomaly_window: 60            # readings in baseline window (~5 minutes)
  anomaly_min_samples: 10       # minimum readings before detection activates
 
  # Topics to ignore
  exclude_topics:
    - /rosout
    - /parameter_events
  exclude_topic_prefixes:
    - /rosscope
 
  # Ports
  metrics_port: 8000
  graph_port: 8001
  ui_port: 8080
 
  # ROS 2
  ros_domain_id: 0
 
  # Notifications
  alerts:
    slack:
      enabled: false
      webhook_url: ""
    email:
      enabled: false
      smtp_host: ""
      smtp_port: 587
      sender: ""
      recipients: []
 
  # Grafana
  grafana_password: rosscope
```
 
---
 
## Anomaly Detection
 
ROSscope uses a **z-score rolling window** to detect topic rate anomalies automatically — no manual threshold configuration needed.
 
```
z = |current_rate - rolling_mean| / rolling_std
anomaly flagged if z > 3.0
```
 
- Window: 60 readings (~5 minutes at 5s intervals)
- Minimum baseline: 10 readings before detection activates
- False positive rate: ~0.3% statistically
- Learns what normal looks like per topic automatically
---
 
## Alert Management
 
Every anomaly creates an alert with a full lifecycle:
 
```
firing → acknowledged → resolved
```
 
Manage alerts via the web UI at `http://localhost:8001` or directly via API:
 
```bash
# List active alerts
curl http://localhost:8001/api/alerts
 
# Acknowledge an alert
curl -X POST http://localhost:8001/api/alerts/{id}/acknowledge
 
# Resolve with a note
curl -X POST "http://localhost:8001/api/alerts/{id}/resolve?note=Sensor+restarted"
```
 
---
 
## Computation Graph
 
ROSscope maps live publisher/subscriber relationships across your entire ROS 2 system:
 
```bash
curl http://localhost:8001/api/graph
```
 
```json
{
  "nodes": [
    {"id": "/camera_node", "type": "node"},
    {"id": "/image_raw", "type": "topic"}
  ],
  "edges": [
    {"source": "/camera_node", "target": "/image_raw", "type": "publishes"},
    {"source": "/image_raw", "target": "/object_detector", "type": "subscribes"}
  ]
}
```
 
The graph visualization at `http://localhost:8001` renders this as an interactive force-directed graph with drag, zoom, search, and connection highlighting.
 
---
 
## Metrics Reference
 
| Metric | Labels | Description |
|--------|--------|-------------|
| `rosscope_topic_rate_hz` | topic, msg_type | Publish rate in Hz |
| `rosscope_topic_msg_count` | topic, msg_type | Messages in last window |
| `rosscope_topic_publisher_count` | topic, msg_type | Active publishers |
| `rosscope_active_topics_total` | — | Total topics with active publishers |
| `rosscope_topic_anomaly` | topic, msg_type | 1 if anomalous, 0 if normal |
| `rosscope_topic_z_score` | topic, msg_type | Z-score vs rolling baseline |
| `rosscope_service_response_time_ms` | service, service_type | Latency in ms |
| `rosscope_service_healthy` | service, service_type | 1 if responsive |
| `rosscope_service_server_count` | service, service_type | Active servers |
| `rosscope_active_services_total` | — | Total discovered services |
| `rosscope_node_state_id` | node | Lifecycle state (0=unconfigured, 1=inactive, 2=active, 3=finalized) |
| `rosscope_node_is_active` | node | 1 if active, 0 otherwise |
| `rosscope_managed_nodes_total` | — | Total lifecycle managed nodes |
 
---
 
## Project Structure
 
```
ROSscope/
├── collector/
│   ├── topic_collector.py       # DDS topic scanning + Hz measurement
│   ├── service_collector.py     # Service discovery + availability
│   ├── lifecycle_collector.py   # Managed node state monitoring
│   ├── graph_collector.py       # Computation graph + FastAPI + Web UI
│   └── anomaly_detector.py      # Z-score statistical detector
├── exporter/
│   └── prometheus_exporter.py   # Prometheus HTTP exporter
├── dashboard/
│   ├── rosscope.json            # Pre-built Grafana dashboard
│   ├── ui.html                  # ROSscope web UI
│   ├── graph.html               # D3.js graph visualization
│   └── provisioning/            # Auto-provisioning configs
├── docker/
│   ├── Dockerfile.collector
│   └── prometheus/
│       └── prometheus.yml
├── .github/
│   └── workflows/
│       └── publish.yml          # GitHub Actions — auto-publish to Docker Hub
├── alerts.py                    # Alert manager
├── notifier.py                  # Slack + email notifications
├── config.py                    # Config loader
├── main.py                      # Entry point
├── rosscope.yaml                # User configuration
├── requirements.txt
├── docker-compose.yml           # Development stack
├── docker-compose.prod.yml      # Production stack (pulls from Docker Hub)
├── start.sh                     # One-command startup
├── stop.sh                      # One-command shutdown
└── install.sh                   # One-line install for new users
```
 
---
 
## Roadmap
 
### v0.2.0
- [ ] Root cause correlation - trace failure cascades upstream to origin node
- [ ] Port consolidation - single port for all ROSscope endpoints
- [ ] Persistent alert history - survives restarts
- [ ] Services page in web UI
### v0.3.0
- [ ] TimescaleDB - persistent metric history
- [ ] Multi-machine fleet aggregation
- [ ] TF tree freshness monitoring
- [ ] ROS 2 bag replay for post-mortem analysis
### v1.0.0 (production ready)
- [ ] Predictive maintenance - ML-based failure forecasting
- [ ] Auto-remediation - node restart, traffic reroute, failover
- [ ] Helm chart for Kubernetes fleet deployment
- [ ] Full authentication and multi-user support
- [ ] Grafana deprecation - web UI covers all functionality
- [ ] FastRTPS compatibility - no DDS configuration required
---
 
## Built With
 
- [ROS 2 Humble](https://docs.ros.org/en/humble/)
- [Prometheus](https://prometheus.io/)
- [Grafana](https://grafana.com/)
- [FastAPI](https://fastapi.tiangolo.com/)
- [D3.js](https://d3js.org/)
- [Docker](https://docker.com/)
- [Python 3.10](https://python.org/)
---
 
## Contributing
 
Contributions welcome. Open an issue first to discuss what you'd like to change.
 
```bash
git clone https://github.com/jawad-glitch/ROSscope.git
cd ROSscope
./start.sh
```
 
---
 
## Author
 
Muhammad Jawad — DevOps & AIOps Engineer
[github.com/jawad-glitch](https://github.com/jawad-glitch)
muhammadjawadok@gmail.com
 
---
 
## License
 
MIT License — use it, fork it, build on it.
