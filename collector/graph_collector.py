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

# ── FastAPI setup ────
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

_collector = None

@app.get("/api/graph")
def get_graph():
    if _collector is None:
        return {"nodes": [], "edges": []}

    edges = _collector.edges
    node_ids = set()

    for edge in edges:
        node_ids.add(edge['publisher'])
        if edge['subscriber']:
            node_ids.add(edge['subscriber'])
        node_ids.add(edge['topic'])

    nodes = []
    for node_id in node_ids:
        node_type = 'topic' if node_id.count('/') > 1 or (node_id.count('/') == 1 and node_id != f"/{node_id.lstrip('/')}".split('/')[1]) else 'node'
        nodes.append({'id': node_id, 'type': node_type})

    edges_out = []
    for e in edges:
        edges_out.append({
            "source": e['publisher'],
            "target": e['topic'],
            "type": "publishes"
        })
        if e['subscriber']:
            edges_out.append({
                "source": e['topic'],
                "target": e['subscriber'],
                "type": "subscribes"
            })

    return {"nodes": nodes, "edges": edges_out}


@app.get("/api/health")
def health():
    return {"status": "ok", "edges": len(_collector.edges) if _collector else 0}

@app.get("/")
def serve_graph_ui():
    html_path = os.path.join(os.path.dirname(__file__), '..', 'dashboard', 'graph.html')
    return FileResponse(html_path)

def start_api(collector_node):
    global _collector
    _collector = collector_node
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

# ── ROS 2 Node ────
class GraphCollector(Node):
    def __init__(self):
        super().__init__('rosscope_graph_collector')
        self.edges = []
        self.timer = self.create_timer(5.0, self.collect_metrics)

    def collect_metrics(self):
        topic_list = self.get_topic_names_and_types()
        edges = []

        for topic_name, _ in topic_list:
            if topic_name.startswith('/rosout') or topic_name.startswith('/parameter'):
                continue

            publishers = self.get_publishers_info_by_topic(topic_name)
            subscribers = self.get_subscriptions_info_by_topic(topic_name)

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

        self.edges = edges
        self.get_logger().info(f'Graph: {len(edges)} edges discovered')


def main():
    rclpy.init()
    node = GraphCollector()

    api_thread = threading.Thread(target=start_api, args=(node,), daemon=True)
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