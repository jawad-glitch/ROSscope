#!/bin/bash
set -e

VERSION=$(curl -s https://api.github.com/repos/jawad-glitch/ROSscope/releases/latest | grep '"tag_name"' | cut -d'"' -f4)
if [ -z "$VERSION" ]; then
    VERSION="latest"
fi

echo "======================================"
echo "  ROSscope — Installing ${VERSION}"
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
echo "  ROSscope ${VERSION} is running!"
echo "======================================"
echo "  UI:      http://localhost:8001"
echo "  Grafana: http://localhost:3000  (admin / rosscope)"
echo "  Metrics: http://localhost:8001/metrics"
echo ""
echo "  ROSscope will automatically detect"
echo "  your ROS 2 nodes and topics."
echo ""
echo "  Useful commands:"
echo "  docker logs rosscope_collector     # collector logs"
echo "  docker logs rosscope_prometheus    # prometheus logs"
echo "  docker compose -f docker-compose.prod.yml down  # stop"
echo "======================================"