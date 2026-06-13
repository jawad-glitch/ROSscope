#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from lifecycle_msgs.srv import GetState

class LifecycleCollector(Node):
    """
    Monitors ROS 2 lifecycle managed nodes by querying their /get_state service.
    
    Note: Service calls across the Docker/WSL2 boundary are unreliable due to
    DDS unicast limitations. This collector works correctly on native Linux.
    For WSL2 development, use 'ros2 lifecycle list' to manually verify states.
    """
    
    STATE_MAP = {
        'unconfigured': 0,
        'inactive': 1,
        'active': 2,
        'finalized': 3,
        'unknown': -1,
        'unreachable': -1
    }

    def __init__(self, exporter=None):
        super().__init__('rosscope_lifecycle_collector')
        self.exporter = exporter
        self.node_clients = {}
        self.timer = self.create_timer(5.0, self.collect_metrics)
        self.db = None

    def discover_managed_nodes(self):
        """Find all lifecycle managed nodes by scanning for /get_state services."""
        managed_nodes = []
        
        for service_name, _ in self.get_service_names_and_types():
            if service_name.endswith('/get_state'):
                # Extract node name from service path e.g. /lc_talker/get_state -> /lc_talker
                node_name = service_name[:-len('/get_state')]
                # Skip ROSscope's own internal nodes
                if 'rosscope' not in node_name:
                    managed_nodes.append(node_name)
        
        return managed_nodes

    def probe_lifecycle_state(self, node_name):
        service_path = f"{node_name}/get_state"
        
        if service_path not in self.node_clients:
            self.node_clients[service_path] = self.create_client(GetState, service_path)
        
        client = self.node_clients[service_path]
        if not client.service_is_ready():
            return "unreachable"

        try:
            response = client.call(GetState.Request())
            if response:
                return response.current_state.label.lower()
        except Exception:
            pass
        return "unknown"

    def collect_metrics(self):
        managed_nodes = self.discover_managed_nodes()
        metrics = []
        
        for node_name in managed_nodes:
            state = self.probe_lifecycle_state(node_name)
            
            metrics.append({
                'node': node_name,
                'state_label': state,
                'state_id': self.STATE_MAP.get(state, -1),
                'is_active': 1 if state == 'active' else 0
            })
        
        self.get_logger().info(f"Lifecycle status: {metrics}")
        if self.exporter:
            self.exporter.update_lifecycle(metrics)
        self.latest_lifecycle_metrics = metrics

        if self.db:
            self.db.write_nodes(metrics)

def main():
    rclpy.init()
    node = LifecycleCollector()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == "__main__":
    main()