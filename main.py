#!/usr/bin/env python3
import rclpy
import threading
from rclpy.executors import MultiThreadedExecutor
from collector.topic_collector import TopicCollector
from collector.service_collector import ServiceCollector
from collector.lifecycle_collector import LifecycleCollector
from collector.graph_collector import GraphCollector, start_api
from exporter.prometheus_exporter import ROSScopeExporter
from config import config
from collector.registry import registry
from database import TimeScaleWriter
from alerts import alert_manager


def main():
    rclpy.init()

    exporter = ROSScopeExporter()

    db = TimeScaleWriter()
    if db.connect():
        db.start()
        alert_manager.load_from_db(db)

    topic_node = TopicCollector()
    topic_node.exporter = exporter
    topic_node.db = db

    service_node = ServiceCollector()
    service_node.exporter = exporter
    service_node.db = db

    lifecycle_node = LifecycleCollector()
    lifecycle_node.exporter = exporter
    lifecycle_node.db = db

    graph_node = GraphCollector()

    registry.topic = topic_node
    registry.service = service_node
    registry.lifecycle = lifecycle_node
    registry.graph = graph_node

    api_thread = threading.Thread(target=start_api, daemon=True)
    api_thread.start()

    executor = MultiThreadedExecutor()
    executor.add_node(topic_node)
    executor.add_node(service_node)
    executor.add_node(lifecycle_node)
    executor.add_node(graph_node)

    try:
        print("[ROSscope] Starting collectors...")
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        executor.shutdown()
        topic_node.destroy_node()
        service_node.destroy_node()
        lifecycle_node.destroy_node()
        graph_node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
        db.stop()
        print("[ROSscope] Shut down cleanly.")


if __name__ == "__main__":
    main()