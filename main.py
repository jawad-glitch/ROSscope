#!/usr/bin/env python3
import rclpy
from rclpy.executors import MultiThreadedExecutor
from collector.topic_collector import TopicCollector
from collector.service_collector import ServiceCollector
from exporter.prometheus_exporter import ROSScopeExporter


def main():
    rclpy.init()

    exporter = ROSScopeExporter(port=8000)
    exporter.start()

    topic_node = TopicCollector()
    topic_node.exporter = exporter

    service_node = ServiceCollector()
    service_node.exporter = exporter

    executor = MultiThreadedExecutor()
    executor.add_node(topic_node)
    executor.add_node(service_node)

    try:
        print("[ROSscope] Starting collectors...")
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        executor.shutdown()
        topic_node.destroy_node()
        service_node.destroy_node()
        rclpy.shutdown()
        print("[ROSscope] Shut down cleanly.")


if __name__ == "__main__":
    main()
