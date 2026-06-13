#!/usr/bin/env python3
from prometheus_client import Gauge

class ROSScopeExporter:
    def __init__(self):
        self.topic_rate_hz = Gauge(
            'rosscope_topic_rate_hz',
            'Message publish rate in Hz for a ROS 2 topic',
            ['topic', 'msg_type']
        )
        self.topic_msg_count = Gauge(
            'rosscope_topic_msg_count',
            'Number of messages received in the last collection window',
            ['topic', 'msg_type']
        )
        self.topic_publisher_count = Gauge(
            'rosscope_topic_publisher_count',
            'Number of active publishers on a ROS 2 topic',
            ['topic', 'msg_type']
        )
        self.active_topics_total = Gauge(
            'rosscope_active_topics_total',
            'Total number of active topics with at least one publisher'
        )
        self.service_response_time = Gauge(
            'rosscope_service_response_time_ms',
            'Service response latency in milliseconds',
            ['service', 'service_type']
        )
        self.service_healthy = Gauge(
            'rosscope_service_healthy',
            '1 if service responded successfully, 0 if timeout',
            ['service', 'service_type']
        )
        self.service_server_count = Gauge(
            'rosscope_service_server_count',
            'Number of servers available for a ROS 2 service',
            ['service', 'service_type']
        )
        self.active_services_total = Gauge(
            'rosscope_active_services_total',
            'Total number of discovered services'
        )
        self.node_state_id = Gauge(
            'rosscope_node_state_id',
            'Lifecycle state: unconfigured=0, inactive=1, active=2, finalized=3',
            ['node']
        )
        self.node_is_active = Gauge(
            'rosscope_node_is_active',
            '1 if node is in active lifecycle state, 0 otherwise',
            ['node']
        )
        self.managed_nodes_total = Gauge(
            'rosscope_managed_nodes_total',
            'Total number of discovered lifecycle managed nodes'
        )
        self.topic_anomaly = Gauge(
            'rosscope_topic_anomaly',
            '1 if topic rate is anomalous, 0 if normal',
            ['topic', 'msg_type']
        )
        self.topic_z_score = Gauge(
            'rosscope_topic_z_score',
            'Z-score of current topic rate vs rolling baseline',
            ['topic', 'msg_type']
        )

    def update(self, metrics):
        self.active_topics_total.set(len(metrics))
        for item in metrics:
            topic = item['topic']
            msg_type = item['type']
            self.topic_rate_hz.labels(topic=topic, msg_type=msg_type).set(item['rate'])
            self.topic_msg_count.labels(topic=topic, msg_type=msg_type).set(item['count'])
            self.topic_publisher_count.labels(topic=topic, msg_type=msg_type).set(item['publishers'])
            self.topic_anomaly.labels(topic=topic, msg_type=msg_type).set(item['is_anomaly'])
            self.topic_z_score.labels(topic=topic, msg_type=msg_type).set(item['z_score'])

    def update_services(self, metrics):
        self.active_services_total.set(len(metrics))
        for item in metrics:
            service = item.get('service', item.get('Service', ''))
            stype = item.get('service_type', item.get('Service_type', ''))
            self.service_response_time.labels(service=service, service_type=stype).set(
                item.get('response_time', 0.0)
            )
            self.service_healthy.labels(service=service, service_type=stype).set(
                1.0 if item.get('response_time', 0.0) > 0 else 0.0
            )
            self.service_server_count.labels(service=service, service_type=stype).set(
                item.get('server_count', 0)
            )

    def update_lifecycle(self, metrics):
        self.managed_nodes_total.set(len(metrics))
        for item in metrics:
            node = item['node']
            self.node_state_id.labels(node=node).set(item['state_id'])
            self.node_is_active.labels(node=node).set(item['is_active'])