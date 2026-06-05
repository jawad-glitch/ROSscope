#!/usr/bin/env python3
import rclpy
import rclpy.executors
from rclpy.node import Node
from rosidl_runtime_py.utilities import get_service
import time
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import config

class ServiceCollector(Node):
    SAFE_SERVICE_PREFIXES = [
        'rcl_interfaces/srv/GetParameters',
        'rcl_interfaces/srv/ListParameters', 
        'rcl_interfaces/srv/DescribeParameters',
    ]

    def __init__(self):
        super().__init__('rosscope_service_collector')
        self.service_status = {}
        self.exporter = None
        self.service_clients = {}
        
        # Timer - check the services every 5 seconds
        self.timer = self.create_timer(5.0, self.collect_metrics)

    def is_safe_to_probe(self, service_type_str):
        """Returns True if the service is on the allow-list."""
        return any(service_type_str.startswith(p) for p in self.SAFE_SERVICE_PREFIXES)

    def probe_service(self, service_name, service_type):
        if service_name not in self.service_clients:
            self.service_clients[service_name] = self.create_client(
                service_type, service_name
            )

        client = self.service_clients[service_name]

        if not client.service_is_ready():
            return None

        req = service_type.Request()
        start_time = time.perf_counter()

        try:
            response = client.call(req)
            if response is not None:
                return (time.perf_counter() - start_time) * 1000
        except Exception as e:
            self.get_logger().warn(f'Service call failed for {service_name}: {e}')

        return None

    def collect_metrics(self):
        """Discover services and track server counts."""
        service_list = self.get_service_names_and_types()
        metrics = []

        for service_name, service_types in service_list:
            if service_name in config.exclude_topics:
                continue
            if any(service_name.startswith(p) for p in config.exclude_topic_prefixes):
                continue

            type_str = service_types[0]

            try:
                srv_type = get_service(type_str)
                if service_name not in self.service_clients:
                    self.service_clients[service_name] = self.create_client(
                        srv_type, service_name
                    )
                server_available = 1 if self.service_clients[service_name].service_is_ready() else 0
            except Exception:
                server_available = 0

            metrics.append({
                'Service': service_name,
                'Service_type': type_str,
                'response_time': 0.0,
                'server_count': server_available
            })

        if self.exporter:
            self.exporter.update_services(metrics)

def main():
    rclpy.init()
    node = ServiceCollector()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == "__main__":
    main()