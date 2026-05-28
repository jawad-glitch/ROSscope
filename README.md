# ROSscope 🔭
 
> Production-grade observability for ROS 2 robot fleets.
 
ROSscope is an open source monitoring platform that gives robotics engineers real-time visibility into their ROS 2 systems — topic health, service availability, node lifecycle states, and AI-powered anomaly detection. Think Datadog, built for robots.
 
---
 
## The Problem
 
When something goes wrong on a robot fleet, you find out when the robot stops working. There's no unified tool that:
- Watches your entire ROS 2 graph in real time
- Detects degraded communication before it causes failures
- Tells you the root cause, not just the symptom
- Deploys in one command
ROSscope fixes that.
 
---
 
## Features
 
- **Topic monitoring** — publish rate (Hz), message count, publisher count per topic
- **Service monitoring** — discovery and server availability across the fleet
- **Lifecycle monitoring** — managed node state tracking (unconfigured/inactive/active/finalized)
- **Anomaly detection** — z-score statistical baseline per topic, no threshold tuning required
- **Prometheus exporter** — 15 custom metrics over HTTP, scrape-ready
- **Grafana dashboard** — pre-built, auto-provisioned, zero manual setup
- **One command deploy** — `docker compose up -d`
---
 
## Architecture
 
```
ROS 2 Robot Fleet
       │
       ▼
┌─────────────────────────────────┐
│         ROSscope Collectors      │
│  TopicCollector                  │
│  ServiceCollector                │
│  LifecycleCollector              │
│  AnomalyDetector                 │
└────────────┬────────────────────┘
             │
             ▼
    Prometheus Exporter :8000
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
- ROS 2 Humble running on the host
- Same `ROS_DOMAIN_ID` on host and container
```bash
git clone https://github.com/jawad-glitch/rosscope.git
cd rosscope
docker compose up -d
```
 
Open Grafana at `http://localhost:3000`
- Username: `admin`
- Password: `rosscope`
Your ROSscope Live dashboard loads automatically. No manual setup required.
 
---
 
## Metrics Reference
 
| Metric | Type | Description |
|--------|------|-------------|
| `rosscope_topic_rate_hz` | Gauge | Publish rate per topic in Hz |
| `rosscope_topic_msg_count` | Gauge | Messages received in last 5s window |
| `rosscope_topic_publisher_count` | Gauge | Active publishers per topic |
| `rosscope_active_topics_total` | Gauge | Total topics with active publishers |
| `rosscope_topic_anomaly` | Gauge | 1 if rate is anomalous, 0 if normal |
| `rosscope_topic_z_score` | Gauge | Z-score vs rolling 5-min baseline |
| `rosscope_service_server_count` | Gauge | Active servers per service |
| `rosscope_service_response_time_ms` | Gauge | Service latency in milliseconds |
| `rosscope_service_healthy` | Gauge | 1 if service responded, 0 if timeout |
| `rosscope_active_services_total` | Gauge | Total discovered services |
| `rosscope_node_state_id` | Gauge | Lifecycle state as integer (0–3) |
| `rosscope_node_is_active` | Gauge | 1 if node is active, 0 otherwise |
| `rosscope_managed_nodes_total` | Gauge | Total lifecycle managed nodes |
 
---
 
## Anomaly Detection
 
ROSscope uses a **z-score rolling window** (60 readings, ~5 minutes at 5s intervals) to detect topic rate anomalies without manual threshold configuration.
 
```
z = |current_rate - rolling_mean| / rolling_std
anomaly flagged if z > 3.0
```
 
A z-score above 3.0 means the current reading is statistically unlikely (~0.3% chance) given the established baseline. No per-topic configuration required — ROSscope learns what normal looks like for each topic automatically.
 
---
 
## Project Structure
 
```
rosscope/
├── collector/
│   ├── topic_collector.py      # DDS topic scanning + Hz measurement
│   ├── service_collector.py    # Service discovery + availability
│   ├── lifecycle_collector.py  # Managed node state monitoring
│   └── anomaly_detector.py     # Z-score statistical detector
├── exporter/
│   └── prometheus_exporter.py  # Prometheus HTTP exporter
├── dashboard/
│   ├── rosscope.json           # Pre-built Grafana dashboard
│   └── provisioning/           # Auto-provisioning configs
├── docker/
│   ├── Dockerfile.collector
│   └── prometheus/
│       └── prometheus.yml
├── docker-compose.yml
└── main.py
```
 
---
 
## Known Limitations
 
- **WSL2:** DDS multicast bridging between Docker and WSL2 host is unreliable. Service probing and some topic discovery may not work correctly on WSL2. Native Linux is recommended for full functionality.
- **Service probing:** Active latency measurement requires native Linux for DDS unicast to work reliably. Server availability tracking (`service_is_ready`) works on all platforms.
- **Lifecycle probing:** Querying node lifecycle state via `/get_state` requires reliable DDS service calls — native Linux recommended.
---
 
## Roadmap
 
- [ ] Root cause correlation engine across nodes
- [ ] Predictive maintenance — failure forecasting via ML
- [ ] Auto-remediation — node restart, traffic reroute, failover
- [ ] Helm chart for Kubernetes fleet deployment
- [ ] Multi-robot fleet map view in Grafana
- [ ] REST API for external integrations and webhooks
- [ ] TF tree freshness monitoring
- [ ] ROS 2 bag replay for post-mortem analysis
- [ ] Alert channels — Slack, PagerDuty, email
---
 
## Built With
 
- [ROS 2 Humble](https://docs.ros.org/en/humble/)
- [Prometheus](https://prometheus.io/)
- [Grafana](https://grafana.com/)
- [Docker](https://docker.com/)
- [Python 3.10](https://python.org/)
---
 
## Author
 
Muhammad Jawad — DevOps & AIOps Engineer
[github.com/jawad-glitch](https://github.com/jawad-glitch)
muhammadjawadok@gmail.com
 
---
 
## License
 
MIT License — use it, fork it, build on it.
