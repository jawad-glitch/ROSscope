from alerts import alert_manager
from collector.registry import registry

def find_upstream(topic, edges):
    publishers = [e['publisher'] for e in edges if e['topic'] == topic]
    
    upstream = []
    for publisher in publishers:
        upstream += [e['topic'] for e in edges if e['subscriber'] == publisher]
    
    return publishers, upstream

def find_alert_id()