#!/bin/bash
set -e

VERSION=$(curl -s https://api.github.com/repos/jawad-glitch/ROSscope/releases/latest | grep '"tag_name"' | cut -d'"' -f4)
if [ -z "$VERSION" ]; then
    VERSION="main"
fi

echo "======================================"
echo "  ROSscope — Installing ${VERSION}"
echo "======================================"

mkdir -p rosscope && cd rosscope

echo "[1/5] Downloading docker-compose..."
curl -sO https://raw.githubusercontent.com/jawad-glitch/ROSscope/main/docker-compose.prod.yml

echo "[2/5] Downloading Prometheus config..."
mkdir -p docker/prometheus
curl -so docker/prometheus/prometheus.yml https://raw.githubusercontent.com/jawad-glitch/ROSscope/main/docker/prometheus/prometheus.yml

echo "[3/5] Downloading dashboard..."
mkdir -p dashboard/provisioning/dashboards dashboard/provisioning/datasources
curl -so dashboard/rosscope.json https://raw.githubusercontent.com/jawad-glitch/ROSscope/main/dashboard/rosscope.json
curl -so dashboard/provisioning/dashboards/dashboards.yml https://raw.githubusercontent.com/jawad-glitch/ROSscope/main/dashboard/provisioning/dashboards/dashboards.yml
curl -so dashboard/provisioning/datasources/prometheus.yml https://raw.githubusercontent.com/jawad-glitch/ROSscope/main/dashboard/provisioning/datasources/prometheus.yml

echo "[4/5] Downloading config and requirements..."
curl -sO https://raw.githubusercontent.com/jawad-glitch/ROSscope/main/rosscope.yaml
curl -sO https://raw.githubusercontent.com/jawad-glitch/ROSscope/main/requirements.txt
curl -sO https://raw.githubusercontent.com/jawad-glitch/ROSscope/main/main.py
curl -sO https://raw.githubusercontent.com/jawad-glitch/ROSscope/main/config.py
curl -sO https://raw.githubusercontent.com/jawad-glitch/ROSscope/main/alerts.py
curl -sO https://raw.githubusercontent.com/jawad-glitch/ROSscope/main/notifier.py
curl -sO https://raw.githubusercontent.com/jawad-glitch/ROSscope/main/database.py
mkdir -p collector exporter
curl -so collector/__init__.py https://raw.githubusercontent.com/jawad-glitch/ROSscope/main/collector/__init__.py
curl -so collector/topic_collector.py https://raw.githubusercontent.com/jawad-glitch/ROSscope/main/collector/topic_collector.py
curl -so collector/service_collector.py https://raw.githubusercontent.com/jawad-glitch/ROSscope/main/collector/service_collector.py
curl -so collector/lifecycle_collector.py https://raw.githubusercontent.com/jawad-glitch/ROSscope/main/collector/lifecycle_collector.py
curl -so collector/graph_collector.py https://raw.githubusercontent.com/jawad-glitch/ROSscope/main/collector/graph_collector.py
curl -so collector/anomaly_detector.py https://raw.githubusercontent.com/jawad-glitch/ROSscope/main/collector/anomaly_detector.py
curl -so collector/registry.py https://raw.githubusercontent.com/jawad-glitch/ROSscope/main/collector/registry.py
curl -so exporter/__init__.py https://raw.githubusercontent.com/jawad-glitch/ROSscope/main/exporter/__init__.py
curl -so exporter/prometheus_exporter.py https://raw.githubusercontent.com/jawad-glitch/ROSscope/main/exporter/prometheus_exporter.py
mkdir -p dashboard
curl -so dashboard/graph.html https://raw.githubusercontent.com/jawad-glitch/ROSscope/main/dashboard/graph.html
curl -so dashboard/ui.html https://raw.githubusercontent.com/jawad-glitch/ROSscope/main/dashboard/ui.html

echo "[5/5] Starting infrastructure (Prometheus, Grafana, TimescaleDB)..."
docker compose -f docker-compose.prod.yml up -d

pip3 install -r requirements.txt --quiet

echo ""
echo "======================================"
echo "  ROSscope ${VERSION} installed!"
echo "======================================"
echo ""
echo "  Infrastructure is running."
echo "  Start the collector with:"
echo ""
echo "    source /opt/ros/humble/setup.bash"
echo "    python3 main.py"
echo ""
echo "  Then open:"
echo "  UI:      http://localhost:8001"
echo "  Grafana: http://localhost:3000  (admin / rosscope)"
echo ""
echo "  To stop infrastructure:"
echo "  docker compose -f docker-compose.prod.yml down"
echo "======================================"
