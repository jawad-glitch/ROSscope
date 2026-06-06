#!/bin/bash
set -e

echo "======================================"
echo "  ROSscope — Installing v0.1.0"
echo "======================================"

# Create rosscope directory
mkdir -p rosscope && cd rosscope

# Download everything needed
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

echo "[4/5] Downloading config..."
curl -sO https://raw.githubusercontent.com/jawad-glitch/ROSscope/main/rosscope.yaml

echo "[5/5] Starting ROSscope..."
docker compose -f docker-compose.prod.yml up -d

echo ""
echo "======================================"
echo "  ROSscope is running!"
echo "======================================"
echo "  UI:      http://localhost:8001"
echo "  Grafana: http://localhost:3000"
echo "  Metrics: http://localhost:8000/metrics"
echo ""
echo "  Start your ROS 2 nodes and ROSscope"
echo "  will detect them automatically."
echo ""
echo "  To start the collector:"
echo "  cd rosscope && python3 main.py"
echo "======================================"