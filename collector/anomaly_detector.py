#!/usr/bin/env python3
import statistics
from collections import deque

class AnomalyDetector:
    def __init__(self, window_size=60, threshold=3.0, min_samples=10):
        """
        :param window_size: Number of readings to keep (60 = 5 mins at 5s interval).
        :param threshold: Z-score threshold (3.0 is a standard statistical anomaly).
        """
        self.window_size = window_size
        self.threshold = threshold
        self.min_samples = min_samples
        self.history = {}

    def update(self, topic, value):
        """Adds a new reading to the rolling window."""
        if topic not in self.history:
            self.history[topic] = deque(maxlen=self.window_size)
        
        self.history[topic].append(value)

    def check(self, topic, value):
        """Returns (is_anomaly, z_score) tuple."""
        readings = self.history.get(topic, [])
        
        if len(readings) < self.min_samples:
            return False, 0.0
            
        mean = statistics.mean(readings)
        stdev = statistics.stdev(readings)
        
        if stdev == 0:
            return False, 0.0
            
        z_score = abs(value - mean) / stdev
        return z_score > self.threshold, round(z_score, 3)