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

def main():
    rclpy.init()

    exporter = ROSScopeExporter(port=config.metrics_port)
    exporter.start()

    topic_node = TopicCollector()
    topic_node.exporter = exporter

    service_node = ServiceCollector()
    service_node.exporter = exporter

    lifecycle_node = LifecycleCollector()
    lifecycle_node.exporter = exporter

    graph_node = GraphCollector()
    graph_node.topic_collector = topic_node
    graph_node.service_collector = service_node
    graph_node.lifecycle_collector = lifecycle_node

    api_thread = threading.Thread(target=start_api, args=(graph_node,), daemon=True)
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
        print("[ROSscope] Shut down cleanly.")


if __name__ == "__main__":
    main()