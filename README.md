# ROSscope 🔭
 
> Production-grade observability for ROS 2 robot fleets.
 
ROSscope is an open source monitoring platform that gives robotics engineers real-time visibility into their ROS 2 systems topic health, service availability, node lifecycle states, inter-node relationships, and AI-powered anomaly detection. Think Datadog, built for robots.
 
---
 
## The Problem
 
When something goes wrong on a robot fleet, you find out when the robot stops working. There's no unified tool that:
- Watches your entire ROS 2 graph in real time
- Detects degraded communication before it causes failures
- Maps which nodes are connected to which
- Tells you the root cause, not just the symptom
- Deploys in one command
ROSscope fixes that.
 
---
 
## Features
 
- **Topic monitoring** - publish rate (Hz), message count, publisher count per topic
- **Service monitoring** - discovery and server availability across the fleet
- **Lifecycle monitoring** - managed node state tracking (unconfigured/inactive/active/finalized)
- **Anomaly detection** - z-score statistical baseline per topic, no threshold tuning required
- **Computation graph** - live directed graph of publisher/subscriber relationships
- **Graph visualization** - interactive D3.js force-directed graph at `http://localhost:8001`
- **Prometheus exporter** - 15 custom metrics over HTTP, scrape-ready
- **Grafana dashboard** - pre-built, auto-provisioned, zero manual setup
- **One command deploy** - `./start.sh`
---
 
## Architecture
 
```
Your ROS 2 Robot Fleet
        │
        ▼
┌──────────────────────────────────────┐
│         ROSscope Collectors           │
│  TopicCollector    - Hz, anomaly      │
│  ServiceCollector  - availability     │
│  LifecycleCollector- node states      │
│  GraphCollector    - relationships    │
│  AnomalyDetector   - z-score ML       │
└──────────┬───────────────────────────┘
           │
     ┌─────┴──────┐
     ▼            ▼
:8000/metrics  :8001/api/graph
Prometheus     Graph UI + API
Exporter
     │
     ▼
Prometheus :9090
     │
     ▼
Grafana :3000
```
 
---
 
## Quickstart
 
**Requirements:**
- Docker + Docker Compose
- ROS 2 Humble (Ubuntu 22.04)
- Python 3.10+
```bash
git clone https://github.com/jawad-glitch/rosscope.git
cd rosscope
./start.sh
```
 
That's it. ROSscope starts collecting immediately.
 
| Service | URL | Credentials |
|---------|-----|-------------|
| Grafana dashboard | http://localhost:3000 | admin / rosscope |
| Graph visualization | http://localhost:8001 | — |
| Prometheus metrics | http://localhost:8000/metrics | — |
| Graph API | http://localhost:8001/api/graph | — |
 
To stop:
```bash
./stop.sh
```
 
---
 
## How It Works
 
ROSscope runs as a native Python process alongside your ROS 2 nodes — no DDS bridging, no special configuration required. It uses the same ROS 2 middleware you already have.
 
Prometheus and Grafana run in Docker purely for convenience. The collector itself lives on your host and talks directly to the ROS 2 graph.
 
---
 
## Anomaly Detection
 
ROSscope uses a **z-score rolling window** to detect topic rate anomalies automatically, no manual threshold configuration needed.
 
```
z = |current_rate - rolling_mean| / rolling_std
anomaly flagged if z > 3.0
```
 
- Window: 60 readings (~5 minutes at 5s intervals)
- Minimum baseline: 10 readings before detection activates
- False positive rate: ~0.3% statistically
- ROSscope learns what normal looks like per topic automatically
When a topic rate deviates significantly from its baseline, `rosscope_topic_anomaly` flips to `1` and the z-score is exported for alerting.
 
---
 
## Computation Graph
 
ROSscope maps live publisher/subscriber relationships across your entire ROS 2 system:
 
```json
GET http://localhost:8001/api/graph
 
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
| `rosscope_topic_msg_count` | topic, msg_type | Messages in last 5s window |
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
rosscope/
├── collector/
│   ├── topic_collector.py       # DDS topic scanning + Hz measurement
│   ├── service_collector.py     # Service discovery + availability
│   ├── lifecycle_collector.py   # Managed node state monitoring
│   ├── graph_collector.py       # Computation graph + FastAPI
│   └── anomaly_detector.py      # Z-score statistical detector
├── exporter/
│   └── prometheus_exporter.py   # Prometheus HTTP exporter
├── dashboard/
│   ├── rosscope.json            # Pre-built Grafana dashboard
│   ├── graph.html               # D3.js graph visualization
│   └── provisioning/            # Auto-provisioning configs
├── docker/
│   ├── Dockerfile.collector
│   └── prometheus/
│       └── prometheus.yml
├── docker-compose.yml
├── main.py
├── requirements.txt
├── start.sh
└── stop.sh
```
 
---
 
## Roadmap
 
### v1.1 — Config + Alert Management
- [ ] `rosscope.yaml` — configure collection interval, anomaly threshold, excluded topics, alert channels
- [ ] Alert management system — firing → acknowledged → resolved states with notes
- [ ] Slack / email / PagerDuty notifications
- [ ] Port consolidation — single port 8080 for all ROSscope endpoints
### v2.0 — Web UI + Distribution
- [ ] Full ROSscope web UI on port 8080 — overview, topics, services, nodes, alerts, graph
- [ ] Docker Hub distribution — `docker pull jawadglitch/rosscope:latest`
- [ ] GitHub Actions CI/CD — auto-publish on tag
- [ ] `docker-compose.prod.yml` — pull from Docker Hub, no build required
- [ ] Semantic versioning — v1.0.0 release
### v3.0 — Intelligence + Scale
- [ ] Root cause correlation — trace failure cascades upstream to origin node
- [ ] TimescaleDB — persistent metric history, survives restarts
- [ ] Predictive maintenance — ML-based failure forecasting
- [ ] Auto-remediation — node restart, traffic reroute, failover
- [ ] Multi-machine fleet aggregation
- [ ] TF tree freshness monitoring
- [ ] ROS 2 bag replay for post-mortem analysis
- [ ] Helm chart for Kubernetes fleet deployment
- [ ] Grafana deprecation once web UI covers all functionality
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
 
## Author
 
Muhammad Jawad — DevOps & AIOps Engineer
[github.com/jawad-glitch](https://github.com/jawad-glitch)
muhammadjawadok@gmail.com
 
---
 
## License
 
MIT License - use it, fork it, build on it.