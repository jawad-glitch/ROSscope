#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from ros2topic.api import get_topic_names_and_types
from rosidl_runtime_py.utilities import get_message
from collector.anomaly_detector import AnomalyDetector
import time
import os
import threading
import sys
import tty
import termios
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import config

class TopicCollector(Node):
    def __init__(self):
        super().__init__('rosscope_topic_collector')
        self.topic_counts = {}
        self.topic_types = {}
        self.subscribers = {}
        self.exporter = None

        self.anomaly_detector = AnomalyDetector(
            window_size=config.anomaly_window,
            threshold=config.anomaly_threshold,
            min_samples=config.anomaly_min_samples
        )

        self.last_check_time = time.time()
        self.timer = self.create_timer(5.0, self.collect_metrics)
        os.system('clear')

    def subscribe_to_topic(self, topic_name, topic_type_str):
        if topic_name in self.subscribers:
            return
        try:
            msg_type = get_message(topic_type_str)
            self.subscribers[topic_name] = self.create_subscription(
                msg_type, topic_name, lambda msg, t=topic_name: self.increment_count(t), 10
            )
        except Exception:
            pass

    def collect_metrics(self):
        current_time = time.time()
        time_delta = current_time - self.last_check_time
        self.last_check_time = current_time

        topic_list = self.get_topic_names_and_types()

        active_topics = set()
        for topic_name, topic_types in topic_list:
            if topic_name in config.exclude_topics:
                continue
            if any(topic_name.startswith(p) for p in config.exclude_topic_prefixes):
                continue
            if self.count_publishers(topic_name) > 0:
                active_topics.add(topic_name)

        # Check anomaly on dying topics before cleanup
        for topic_name in list(self.topic_counts.keys()):
            if topic_name not in active_topics:
                is_anomaly, z_score = self.anomaly_detector.check(topic_name, 0.0)
                self.anomaly_detector.update(topic_name, 0.0)
                if is_anomaly and self.exporter:
                    msg_type = self.topic_types.get(topic_name, 'unknown')
                    self.exporter.topic_anomaly.labels(
                        topic=topic_name, msg_type=msg_type
                    ).set(1)
                    self.exporter.topic_z_score.labels(
                        topic=topic_name, msg_type=msg_type
                    ).set(z_score)
                    self.get_logger().warn(
                        f'ANOMALY DETECTED: {topic_name} dropped to 0Hz (z={z_score})'
                    )

        # Zero out metrics then clean up dead topics
        for topic_name in list(self.topic_counts.keys()):
            if topic_name not in active_topics:
                if self.exporter:
                    msg_type = self.topic_types.get(topic_name, 'unknown')
                    self.exporter.topic_publisher_count.labels(
                        topic=topic_name, msg_type=msg_type
                    ).set(0)
                    self.exporter.topic_rate_hz.labels(
                        topic=topic_name, msg_type=msg_type
                    ).set(0)
                del self.topic_counts[topic_name]
                del self.topic_types[topic_name]
                if topic_name in self.subscribers:
                    self.destroy_subscription(self.subscribers[topic_name])
                    del self.subscribers[topic_name]

        metrics = []
        for topic_name, topic_types in topic_list:
            if topic_name not in active_topics:
                continue

            if topic_name not in self.topic_counts:
                self.topic_counts[topic_name] = 0
                self.topic_types[topic_name] = topic_types[0] if topic_types else 'unknown'
                self.subscribe_to_topic(topic_name, self.topic_types[topic_name])

            interval_messages = self.topic_counts[topic_name]
            msg_rate_hz = interval_messages / time_delta if time_delta > 0 else 0.0
            rate = round(msg_rate_hz, 1)

            is_anomaly, z_score = self.anomaly_detector.check(topic_name, rate)
            self.anomaly_detector.update(topic_name, rate)

            metrics.append({
                'topic': topic_name,
                'type': self.topic_types[topic_name],
                'count': interval_messages,
                'rate': rate,
                'publishers': self.count_publishers(topic_name),
                'is_anomaly': int(is_anomaly),
                'z_score': z_score
            })
            self.topic_counts[topic_name] = 0

        if self.exporter:
            self.exporter.update(metrics)
        self.render_dashboard(metrics)

    def increment_count(self, topic_name):
        if topic_name in self.topic_counts:
            self.topic_counts[topic_name] += 1

    def render_dashboard(self, metrics):
        sys.stdout.write("\r\033[H\033[J")
        sys.stdout.write("================================================================================\r\n")
        sys.stdout.write("     ROSscope Live Dashboard | Publisher-Verified Metrics                       \r\n")
        sys.stdout.write("================================================================================\r\n")

        row_format = " │ {:<28} │ {:<22} │ {:<4} │ {:<7} │ {:<4} │ {:<6} │ {:<5} │\r\n"
        sys.stdout.write(row_format.format("TOPIC", "TYPE", "MSGS", "RATE", "PUBS", "ZSCORE", "ALERT"))
        sys.stdout.write("────────────────────────────────────────────────────────────────────────────────\r\n")

        if not metrics:
            sys.stdout.write(" │ No active publishers found...                                              │\r\n")
        else:
            for item in metrics:
                topic = item['topic'] if len(item['topic']) <= 28 else "..." + item['topic'][-25:]
                msg_type = item['type'] if len(item['type']) <= 22 else item['type'][:19] + "..."
                alert = "⚠ YES" if item['is_anomaly'] else "OK"
                sys.stdout.write(row_format.format(
                    topic, msg_type, item['count'], f"{item['rate']}Hz",
                    item['publishers'], item['z_score'], alert
                ))

        sys.stdout.write("================================================================================\r\n")
        sys.stdout.flush()


def keyboard_listener():
    while rclpy.ok():
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(sys.stdin.fileno())
            if sys.stdin.read(1).lower() == 'q':
                rclpy.shutdown()
                break
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def main():
    rclpy.init()
    node = TopicCollector()
    threading.Thread(target=keyboard_listener, daemon=True).start()
    try:
        rclpy.spin(node)
    except:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()