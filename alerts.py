#!/usr/bin/env python3
import uuid
import threading
from datetime import datetime


# ── Alert Manager ──────────────────────────────────────────────

class AlertManager:
    def __init__(self):
        self._alerts = {}
        self._lock = threading.Lock()

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

        from notifier import notification_manager
        notification_manager.notify(alert)
        return alert_id

    def acknowledge(self, alert_id):
        with self._lock:
            alert = self._alerts.get(alert_id)
            if not alert or alert['state'] != 'firing':
                return False
            alert['state'] = 'acknowledged'
            alert['acknowledged_at'] = datetime.utcnow().isoformat()
        return True

    def resolve(self, alert_id, note=None):
        with self._lock:
            alert = self._alerts.get(alert_id)
            if not alert or alert['state'] == 'resolved':
                return False
            alert['state'] = 'resolved'
            alert['resolved_at'] = datetime.utcnow().isoformat()
            alert['note'] = note
        return True

    def get_active(self):
        with self._lock:
            return [a for a in self._alerts.values() if a['state'] in ('firing', 'acknowledged')]

    def get_all(self):
        with self._lock:
            return list(self._alerts.values())

    def get_by_id(self, alert_id):
        with self._lock:
            return self._alerts.get(alert_id)


# Singleton
alert_manager = AlertManager()


# ── Root Cause Correlation ──────────────────────────────────────

def find_upstream(topic, edges):
    """Find publishers of a topic and what topics they subscribe to."""
    publishers = [e['publisher'] for e in edges if e['topic'] == topic]
    upstream_topics = []
    for publisher in publishers:
        upstream_topics += [e['topic'] for e in edges if e['subscriber'] == publisher]
    return publishers, upstream_topics


def correlate(alert_id: str) -> dict:
    from collector.registry import registry

    alert = alert_manager.get_by_id(alert_id)
    if not alert:
        return {'error': 'Alert not found'}

    topic = alert['topic']
    fired_at = alert['fired_at']

    if not registry.graph:
        return {'error': 'Graph collector not available'}

    edges = registry.graph.edges
    visited_topics = set()
    queue = [topic]
    path = []
    root_cause = None
    root_cause_alert = None
    all_alerts = alert_manager.get_all()

    while queue:
        current_topic = queue.pop(0)
        if current_topic in visited_topics:
            continue
        visited_topics.add(current_topic)
        path.append(current_topic)

        publishers, upstream_topics = find_upstream(current_topic, edges)
        path += publishers

        for upstream_topic in upstream_topics:
            for a in all_alerts:
                if a['topic'] == upstream_topic and a['state'] != 'resolved':
                    if a['fired_at'] < fired_at:
                        root_cause = upstream_topic
                        root_cause_alert = a
                        break
            if root_cause:
                break
            queue.append(upstream_topic)

    if root_cause:
        delta = _seconds_between(root_cause_alert['fired_at'], fired_at)
        return {
            'alert_id': alert_id,
            'topic': topic,
            'root_cause': root_cause,
            'path': list(dict.fromkeys(path)),
            'confidence': f'upstream alert fired {delta}s earlier'
        }

    return {
        'alert_id': alert_id,
        'topic': topic,
        'root_cause': None,
        'path': list(dict.fromkeys(path)),
        'confidence': 'no upstream cause found'
    }


def _seconds_between(earlier: str, later: str) -> int:
    try:
        t1 = datetime.fromisoformat(earlier)
        t2 = datetime.fromisoformat(later)
        return max(0, int((t2 - t1).total_seconds()))
    except Exception:
        return 0
