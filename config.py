#!/usr/bin/env python3
import yaml
import os

class ROSScopeConfig:
    DEFAULTS = {
        'collection_interval': 5,
        'anomaly_threshold': 3.0,
        'anomaly_window': 60,
        'anomaly_min_samples': 10,
        'exclude_topics': ['/rosout', '/parameter_events'],
        'exclude_topic_prefixes': ['/rosscope'],
        'metrics_port': 8000,
        'graph_port': 8001,
        'ui_port': 8080,
        'ros_domain_id': 0,
        'grafana_password': 'rosscope',
        'alerts': {
            'slack': {'enabled': False, 'webhook_url': ''},
            'email': {'enabled': False, 'smtp_host': '', 'smtp_port': 587, 'sender': '', 'recipients': []},
            'pagerduty': {'enabled': False, 'integration_key': ''}
        }
    }

    def __init__(self, config_path=None):
        if config_path is None:
            config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rosscope.yaml')

        self._config = self._load(config_path)
        self._validate()

    def _load(self, path):
        if not os.path.exists(path):
            print(f"[ROSscope] No config file found at {path}, using defaults")
            return self.DEFAULTS.copy()

        with open(path, 'r') as f:
            data = yaml.safe_load(f)

        if not data or 'rosscope' not in data:
            print("[ROSscope] Config file empty or missing 'rosscope' key, using defaults")
            return self.DEFAULTS.copy()

        config = self.DEFAULTS.copy()
        config.update(data['rosscope'])
        print(f"[ROSscope] Config loaded from {path}")
        return config

    def _validate(self):
        for port_key in ['metrics_port', 'graph_port', 'ui_port']:
            port = self._config.get(port_key)
            if not isinstance(port, int) or not (1024 <= port <= 65535):
                print(f"[ROSscope] Invalid {port_key}: {port}, using default")
                self._config[port_key] = self.DEFAULTS[port_key]

        threshold = self._config.get('anomaly_threshold')
        if not isinstance(threshold, (int, float)) or threshold <= 0:
            print(f"[ROSscope] Invalid anomaly_threshold: {threshold}, using default 3.0")
            self._config['anomaly_threshold'] = 3.0

        interval = self._config.get('collection_interval')
        if not isinstance(interval, int) or interval <= 0:
            print(f"[ROSscope] Invalid collection_interval: {interval}, using default 5")
            self._config['collection_interval'] = 5

    def __getattr__(self, key):
        if key.startswith('_'):
            raise AttributeError(key)
        if key in self._config:
            return self._config[key]
        raise AttributeError(f"[ROSscope] Unknown config key: {key}")

    def get(self, key, default=None):
        return self._config.get(key, default)

    def __repr__(self):
        return f"ROSScopeConfig({self._config})"

config = ROSScopeConfig()