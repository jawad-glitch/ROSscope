#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import threading
from fastapi.responses import FileResponse
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import config
from alerts import alert_manager
from collector.registry import registry
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from fastapi.responses import Response, FileResponse
from alerts import correlate

# ── FastAPI setup ────
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.get("/api/graph")
def get_graph():
    if registry.graph is None:
        return {"nodes": [], "edges": []}

    edges = registry.graph.edges
    known_nodes = registry.graph.known_nodes
    known_topics = registry.graph.known_topics

    nodes = []
    for nid in known_nodes:
        nodes.append({'id': nid, 'type': 'node'})
    for tid in known_topics:
        nodes.append({'id': tid, 'type': 'topic'})

    edges_out = []
    for e in edges:
        edges_out.append({"source": e['publisher'], "target": e['topic'], "type": "publishes"})
        if e['subscriber']:
            edges_out.append({"source": e['topic'], "target": e['subscriber'], "type": "subscribes"})

    return {"nodes": nodes, "edges": edges_out}

@app.get("/api/health")
def health():
    g = registry.graph
    return {"status": "ok", "edges": len(g.edges) if g else 0}

@app.get("/")
def serve_ui():
    html_path = os.path.join(os.path.dirname(__file__), '..', 'dashboard', 'ui.html')
    return FileResponse(html_path)

def start_api():
    uvicorn.run(app, host="0.0.0.0", port=config.graph_port, log_level="error")

@app.get("/api/alerts")
def get_alerts():
    """Return all active and resolved alerts."""
    return {
        "active": alert_manager.get_active(),
        "all": alert_manager.get_all()
    }

@app.post("/api/alerts/{alert_id}/acknowledge")
def acknowledge_alert(alert_id: str):
    """Acknowledge a firing alert."""
    success = alert_manager.acknowledge(alert_id)
    if not success:
        return {"success": False, "error": "Alert not found or not in firing state"}
    return {"success": True}

@app.post("/api/alerts/{alert_id}/resolve")
def resolve_alert(alert_id: str, note: str = None):
    """Resolve an alert with optional note."""
    success = alert_manager.resolve(alert_id, note=note)
    if not success:
        return {"success": False, "error": "Alert not found or already resolved"}
    return {"success": True}

@app.get("/api/alerts/{alert_id}/correlate")
def correlate_alert(alert_id: str):
    return correlate(alert_id)

@app.get("/api/history/topics")
def get_topic_history(topic: str = None, minutes: int = 60):
    from collector.registry import registry
    if not registry.topic or not registry.topic.db:
        return {"events": []}
    return {"events": registry.topic.db.get_topic_history(topic, minutes)}

@app.get("/api/history/anomalies")
def get_anomaly_events(minutes: int = 60):
    from collector.registry import registry
    if not registry.topic or not registry.topic.db:
        return {"events": []}
    return {"events": registry.topic.db.get_anomaly_events(minutes)}

@app.get("/api/topics")
def get_topics():
    if not registry.topic:
        return {"topics": []}
    return {"topics": getattr(registry.topic, 'latest_metrics', [])}

@app.get("/api/services")
def get_services():
    if not registry.service:
        return {"services": []}
    return {"services": getattr(registry.service, 'latest_service_metrics', [])}

@app.get("/api/nodes")
def get_nodes():
    if not registry.lifecycle:
        return {"nodes": []}
    return {"nodes": getattr(registry.lifecycle, 'latest_lifecycle_metrics', [])}

@app.delete("/api/history/clear")
def clear_history():
    """Delete all historical metrics from TimescaleDB."""
    from collector.registry import registry
    if not registry.topic or not registry.topic.db:
        return {"success": False, "error": "DB not connected"}
    try:
        conn = registry.topic.db._conn
        with conn.cursor() as cur:
            cur.execute("TRUNCATE TABLE topic_metrics;")
            cur.execute("TRUNCATE TABLE service_metrics;")
            cur.execute("TRUNCATE TABLE node_metrics;")
        conn.commit()
        return {"success": True, "message": "All metric history cleared"}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.delete("/api/alerts/clear/resolved")
def clear_resolved_alerts():
    """Delete all resolved alerts from DB and memory."""
    from collector.registry import registry
    # Clear from memory
    alert_manager._alerts = {k: v for k, v in alert_manager._alerts.items() 
                              if v['state'] != 'resolved'}
    # Clear from DB
    if registry.topic and registry.topic.db:
        try:
            conn = registry.topic.db._conn
            with conn.cursor() as cur:
                cur.execute("DELETE FROM alerts WHERE state = 'resolved';")
            conn.commit()
        except Exception as e:
            return {"success": False, "error": str(e)}
    return {"success": True, "message": "Resolved alerts cleared"}

@app.get("/graph-viz")
def serve_graph():
    html_path = os.path.join(os.path.dirname(__file__), '..', 'dashboard', 'graph.html')
    return FileResponse(html_path)

# ── ROS 2 Node ────
class GraphCollector(Node):
    def __init__(self):
        super().__init__('rosscope_graph_collector')
        self._edges = []
        self._known_nodes = set()
        self._known_topics = set()
        self._lock = threading.Lock()
        self.timer = self.create_timer(5.0, self.collect_metrics)

    @property
    def edges(self):
        with self._lock:
            return list(self._edges) 
    
    @property
    def known_nodes(self):
        with self._lock:
            return set(self._known_nodes)

    @property
    def known_topics(self):
        with self._lock:
            return set(self._known_topics)

    def collect_metrics(self):
        topic_list = self.get_topic_names_and_types()
        edges = []
        known_nodes = set()
        known_topics = set()

        for topic_name, _ in topic_list:
            if topic_name.startswith('/rosout') or topic_name.startswith('/parameter'):
                continue

            known_topics.add(topic_name)

            publishers = self.get_publishers_info_by_topic(topic_name)
            subscribers = self.get_subscriptions_info_by_topic(topic_name)

            for pub in publishers:
                known_nodes.add(pub.node_name)
            for sub in subscribers:
                known_nodes.add(sub.node_name)

            for pub in publishers:
                for sub in subscribers:
                    edges.append({
                        'publisher': pub.node_name,
                        'topic': topic_name,
                        'subscriber': sub.node_name
                    })

            if publishers and not subscribers:
                for pub in publishers:
                    edges.append({
                        'publisher': pub.node_name,
                        'topic': topic_name,
                        'subscriber': None
                    })

        with self._lock:
            self._edges = edges
            self._known_nodes = known_nodes
            self._known_topics = known_topics

        self.get_logger().info(f'Graph: {len(edges)} edges, {len(known_nodes)} nodes, {len(known_topics)} topics')


def main():
    rclpy.init()
    node = GraphCollector()

    api_thread = threading.Thread(target=start_api, daemon=True)
    api_thread.start()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()