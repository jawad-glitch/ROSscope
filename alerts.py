#!/usr/bin/env python3
from datetime import datetime
from alerts import alert_manager
from collector.registry import registry


def find_upstream(topic, edges):
    """Find publishers of a topic and what topics they subscribe to."""
    publishers = [e['publisher'] for e in edges if e['topic'] == topic]

    upstream_topics = []
    for publisher in publishers:
        upstream_topics += [e['topic'] for e in edges if e['subscriber'] == publisher]

    return publishers, upstream_topics


def correlate(alert_id: str) -> dict:
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
            'path': list(dict.fromkeys(path)),  # deduplicated, order preserved
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
    """Calculate seconds between two ISO timestamp strings."""
    fmt = '%Y-%m-%dT%H:%M:%S.%f'
    try:
        t1 = datetime.fromisoformat(earlier)
        t2 = datetime.fromisoformat(later)
        return max(0, int((t2 - t1).total_seconds()))
    except Exception:
        return 0