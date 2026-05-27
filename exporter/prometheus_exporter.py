#!/usr/bin/env python3
from prometheus_client import start_http_server, Gauge
import time
import threading

class ROSScopeExporter:
    """
    Exposes ROSscope metrics over HTTP for Prometheus to scrape.
    Runs on port 8000 by default.
    """

    def __init__(self, port=8000):
        self.port = port

        # Define Prometheus metrics
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

    def start(self):
        """Start the HTTP server in a background thread."""
        thread = threading.Thread(
            target=start_http_server,
            args=(self.port,),
            daemon=True
        )
        thread.start()
        print(f"[ROSscope] Prometheus exporter live at http://localhost:{self.port}/metrics")

    def update(self, metrics):
        """
        Called by TopicCollector every collection window.
        metrics: list of dicts with topic, type, count, rate, publishers
        """
        self.active_topics_total.set(len(metrics))

        for item in metrics:
            topic = item['topic']
            msg_type = item['type']

            self.topic_rate_hz.labels(topic=topic, msg_type=msg_type).set(item['rate'])
            self.topic_msg_count.labels(topic=topic, msg_type=msg_type).set(item['count'])
            self.topic_publisher_count.labels(topic=topic, msg_type=msg_type).set(item['publishers'])