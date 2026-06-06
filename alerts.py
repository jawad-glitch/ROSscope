#!/usr/bin/env python3
import uuid
import threading
from datetime import datetime


class AlertManager:
    def __init__(self):
        self._alerts = {}  # id > alert dict
        self._lock = threading.Lock()  # thread safety

    def fire(self, topic, z_score):
        """Create a new firing alert only if no active alert exists for this topic."""
        with self._lock:
            for alert in self._alerts.values():
                if alert['topic'] == topic and alert['state'] in ('firing', 'acknowledged'):
                    return alert['id'] 

            alert_id = str(uuid.uuid4())
            alert = {
                'id': alert_id,
                'topic': topic,
                'z_score': round(z_score, 3),
                'state': 'firing',
                'fired_at': datetime.utcnow().isoformat(),
                'acknowledged_at': None,
                'resolved_at': None,
                'note': None
            }
            self._alerts[alert_id] = alert
            return alert_id

    def acknowledge(self, alert_id):
        """Transition firing → acknowledged."""
        with self._lock:
            alert = self._alerts.get(alert_id)
            if not alert:
                return False
            if alert['state'] != 'firing':
                return False
            alert['state'] = 'acknowledged'
            alert['acknowledged_at'] = datetime.utcnow().isoformat()
        return True

    def resolve(self, alert_id, note=None):
        """Transition acknowledged/firing → resolved."""
        with self._lock:
            alert = self._alerts.get(alert_id)
            if not alert:
                return False
            if alert['state'] == 'resolved':
                return False
            alert['state'] = 'resolved'
            alert['resolved_at'] = datetime.utcnow().isoformat()
            alert['note'] = note
        return True

    def get_active(self):
        """Return all firing and acknowledged alerts."""
        with self._lock:
            return [
                a for a in self._alerts.values()
                if a['state'] in ('firing', 'acknowledged')
            ]

    def get_all(self):
        """Return all alerts including resolved."""
        with self._lock:
            return list(self._alerts.values())

    def get_by_id(self, alert_id):
        """Return a single alert by id."""
        with self._lock:
            return self._alerts.get(alert_id)

alert_manager = AlertManager()