#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from ros2topic.api import get_topic_names_and_types
from rosidl_runtime_py.utilities import get_message
import time
import os
import threading
import sys
import tty
import termios

class TopicCollector(Node):
    def __init__(self):
        super().__init__('rosscope_topic_collector')
        self.topic_counts = {}
        self.topic_types = {}
        self.subscribers = {}
        self.exporter = None

        # timer
        self.last_check_time = time.time()
        self.timer = self.create_timer(5.0, self.collect_metrics)
        os.system('clear')

    def subscribe_to_topic(self, topic_name, topic_type_str):
        if topic_name in self.subscribers: return
        try:
            msg_type = get_message(topic_type_str)
            self.subscribers[topic_name] = self.create_subscription(
                msg_type, topic_name, lambda msg, t=topic_name: self.increment_count(t), 10
            )
        except Exception: pass

    def collect_metrics(self):
        current_time = time.time()
        time_delta = current_time - self.last_check_time
        self.last_check_time = current_time

        topic_list = self.get_topic_names_and_types()

        active_topics = set()
        for topic_name, topic_types in topic_list:
            if topic_name.startswith('/rosout') or topic_name.startswith('/parameter'):
                continue
            if self.count_publishers(topic_name) > 0:
                active_topics.add(topic_name)

        for topic_name in list(self.topic_counts.keys()):
            if topic_name not in active_topics:
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

            metrics.append({
                'topic': topic_name,
                'type': self.topic_types[topic_name],
                'count': interval_messages,
                'rate': round(msg_rate_hz, 1),
                'publishers': self.count_publishers(topic_name)
            })
            self.topic_counts[topic_name] = 0

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
        
        # Updated format string to include Publishers
        row_format = " │ {:<32} │ {:<25} │ {:<4} │ {:<8} │ {:<4} │\r\n"
        sys.stdout.write(row_format.format("TOPIC", "TYPE", "MSGS", "RATE (Hz)", "PUBS"))
        sys.stdout.write("────────────────────────────────────────────────────────────────────────────────\r\n")
        
        if not metrics:
            sys.stdout.write(" │ No active publishers found...                                              │\r\n")
        else:
            for item in metrics:
                topic = item['topic'] if len(item['topic']) <= 32 else "..." + item['topic'][-29:]
                msg_type = item['type'] if len(item['type']) <= 25 else item['type'][:22] + "..."
                sys.stdout.write(row_format.format(
                    topic, msg_type, item['count'], f"{item['rate']} Hz", item['publishers']
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
    except: pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == "__main__":
    main()