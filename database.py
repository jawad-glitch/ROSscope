#!/usr/bin/env python3
import queue
import threading
import time
import psycopg2
from psycopg2.extras import execute_values
from datetime import datetime, timezone


class TimeScaleWriter:
    def __init__(self, host='localhost', port=5432, dbname='rosscope',
                 user='rosscope', password='rosscope'):
        self.dsn = f"host={host} port={port} dbname={dbname} user={user} password={password}"
        self._queue = queue.Queue()
        self._conn = None
        self._running = False

    def connect(self, retries=10, delay=3):
        """Connect with retries — TimescaleDB may take a few seconds to start."""
        for attempt in range(retries):
            try:
                self._conn = psycopg2.connect(self.dsn)
                self._conn.autocommit = False
                self._init_schema()
                print("[ROSscope] TimescaleDB connected.")
                return True
            except psycopg2.OperationalError as e:
                print(f"[ROSscope] DB connection attempt {attempt + 1}/{retries} failed: {e}")
                time.sleep(delay)
        print("[ROSscope] Could not connect to TimescaleDB. Metrics will not be persisted.")
        return False

    def _init_schema(self):
        with self._conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS timescaledb;")

            cur.execute("""
                CREATE TABLE IF NOT EXISTS topic_metrics (
                    time         TIMESTAMPTZ NOT NULL,
                    topic        TEXT NOT NULL,
                    msg_type     TEXT NOT NULL,
                    rate_hz      DOUBLE PRECISION,
                    msg_count    INTEGER,
                    pub_count    INTEGER,
                    is_anomaly   BOOLEAN,
                    z_score      DOUBLE PRECISION
                );
            """)
            cur.execute("""
                SELECT create_hypertable('topic_metrics', 'time',
                    if_not_exists => TRUE);
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS service_metrics (
                    time             TIMESTAMPTZ NOT NULL,
                    service          TEXT NOT NULL,
                    service_type     TEXT NOT NULL,
                    response_time_ms DOUBLE PRECISION,
                    server_count     INTEGER,
                    healthy          BOOLEAN
                );
            """)
            cur.execute("""
                SELECT create_hypertable('service_metrics', 'time',
                    if_not_exists => TRUE);
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS node_metrics (
                    time      TIMESTAMPTZ NOT NULL,
                    node      TEXT NOT NULL,
                    state_id  INTEGER,
                    is_active BOOLEAN
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS alerts (
                    id           TEXT PRIMARY KEY,
                    topic        TEXT NOT NULL,
                    z_score      DOUBLE PRECISION,
                    state        TEXT NOT NULL,
                    fired_at     TIMESTAMPTZ NOT NULL,
                    acknowledged_at TIMESTAMPTZ,
                    resolved_at  TIMESTAMPTZ,
                    note         TEXT
                );
            """)
            cur.execute("""
                SELECT create_hypertable('node_metrics', 'time',
                    if_not_exists => TRUE);
            """)

        self._conn.commit()
        print("[ROSscope] TimescaleDB schema ready.")

    def write_topics(self, metrics):
        """Queue topic metrics for async write."""
        self._queue.put(('topics', metrics, datetime.now(timezone.utc)))

    def write_services(self, metrics):
        """Queue service metrics for async write."""
        self._queue.put(('services', metrics, datetime.now(timezone.utc)))

    def write_nodes(self, metrics):
        """Queue node metrics for async write."""
        self._queue.put(('nodes', metrics, datetime.now(timezone.utc)))

    def _write_topics(self, metrics, ts):
        rows = [(ts, m['topic'], m['type'], m['rate'],
                 m['count'], m['publishers'], bool(m['is_anomaly']), m['z_score'])
                for m in metrics]
        with self._conn.cursor() as cur:
            execute_values(cur,
                """INSERT INTO topic_metrics
                   (time, topic, msg_type, rate_hz, msg_count, pub_count, is_anomaly, z_score)
                   VALUES %s""", rows)
        self._conn.commit()

    def _write_services(self, metrics, ts):
        rows = [(ts, m.get('service', m.get('Service', '')), 
                m.get('service_type', m.get('Service_type', '')),
                m.get('response_time', 0.0),
                m.get('server_count', 0),
                m.get('server_count', 0) > 0)
                for m in metrics]
        with self._conn.cursor() as cur:
            execute_values(cur,
                """INSERT INTO service_metrics
                   (time, service, service_type, response_time_ms, server_count, healthy)
                   VALUES %s""", rows)
        self._conn.commit()

    def _write_nodes(self, metrics, ts):
        rows = [(ts, m['node'], m['state_id'], bool(m['is_active']))
                for m in metrics]
        with self._conn.cursor() as cur:
            execute_values(cur,
                """INSERT INTO node_metrics
                   (time, node, state_id, is_active)
                   VALUES %s""", rows)
        self._conn.commit()

    def _writer_loop(self):
        """Background thread — reads from queue and writes to DB."""
        while self._running:
            try:
                kind, metrics, ts = self._queue.get(timeout=1)
                if not metrics:
                    continue
                if kind == 'topics':
                    self._write_topics(metrics, ts)
                elif kind == 'services':
                    self._write_services(metrics, ts)
                elif kind == 'nodes':
                    self._write_nodes(metrics, ts)
            except queue.Empty:
                continue
            except Exception as e:
                print(f"[ROSscope] DB write error: {e}")
                try:
                    self._conn = psycopg2.connect(self.dsn)
                    self._conn.autocommit = False
                except Exception:
                    pass
    
    def save_alert(self, alert):
        """Insert or update an alert in the DB."""
        if self._conn is None:
            return
        try:
            with self._conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO alerts (id, topic, z_score, state, fired_at, acknowledged_at, resolved_at, note)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        state = EXCLUDED.state,
                        acknowledged_at = EXCLUDED.acknowledged_at,
                        resolved_at = EXCLUDED.resolved_at,
                        note = EXCLUDED.note
                """, (
                    alert['id'], alert['topic'], alert['z_score'],
                    alert['state'], alert['fired_at'],
                    alert.get('acknowledged_at'),
                    alert.get('resolved_at'),
                    alert.get('note')
                ))
            self._conn.commit()
        except Exception as e:
            print(f"[ROSscope] Alert save error: {e}")

    def load_unresolved_alerts(self):
        """Load firing and acknowledged alerts on startup."""
        if self._conn is None:
            return []
        try:
            with self._conn.cursor() as cur:
                cur.execute("""
                    SELECT id, topic, z_score, state, fired_at,
                        acknowledged_at, resolved_at, note
                    FROM alerts
                    WHERE state IN ('firing', 'acknowledged')
                    ORDER BY fired_at DESC
                """)
                rows = cur.fetchall()
                return [{
                    'id': r[0], 'topic': r[1], 'z_score': r[2],
                    'state': r[3],
                    'fired_at': r[4].isoformat() if r[4] else None,
                    'acknowledged_at': r[5].isoformat() if r[5] else None,
                    'resolved_at': r[6].isoformat() if r[6] else None,
                    'note': r[7]
                } for r in rows]
        except Exception as e:
            print(f"[ROSscope] Alert load error: {e}")
            return []

    def get_topic_history(self, topic=None, minutes=60):
        """Get topic metrics history."""
        if self._conn is None:
            return []
        try:
            with self._conn.cursor() as cur:
                if topic:
                    cur.execute("""
                        SELECT time, topic, rate_hz, msg_count, pub_count, is_anomaly, z_score
                        FROM topic_metrics
                        WHERE time > NOW() - INTERVAL '%s minutes'
                        AND topic = %s
                        ORDER BY time DESC
                        LIMIT 200
                    """, (minutes, topic))
                else:
                    cur.execute("""
                        SELECT time, topic, rate_hz, msg_count, pub_count, is_anomaly, z_score
                        FROM topic_metrics
                        WHERE time > NOW() - INTERVAL '%s minutes'
                        ORDER BY time DESC
                        LIMIT 200
                    """, (minutes,))
                rows = cur.fetchall()
                return [{
                    'time': r[0].isoformat(),
                    'topic': r[1],
                    'rate_hz': r[2],
                    'msg_count': r[3],
                    'pub_count': r[4],
                    'is_anomaly': r[5],
                    'z_score': r[6]
                } for r in rows]
        except Exception as e:
            print(f"[ROSscope] History query error: {e}")
            return []

    def get_anomaly_events(self, minutes=60):
        """Get all anomaly events in the last N minutes."""
        if self._conn is None:
            return []
        try:
            with self._conn.cursor() as cur:
                cur.execute("""
                    SELECT time, topic, rate_hz, z_score
                    FROM topic_metrics
                    WHERE is_anomaly = true
                    AND time > NOW() - INTERVAL '%s minutes'
                    ORDER BY time DESC
                    LIMIT 100
                """, (minutes,))
                rows = cur.fetchall()
                return [{
                    'time': r[0].isoformat(),
                    'topic': r[1],
                    'rate_hz': r[2],
                    'z_score': r[3]
                } for r in rows]
        except Exception as e:
            print(f"[ROSscope] Anomaly query error: {e}")
            return []

    def start(self):
        """Start the background writer thread."""
        if self._conn is None:
            return
        self._running = True
        thread = threading.Thread(target=self._writer_loop, daemon=True)
        thread.start()
        print("[ROSscope] TimescaleDB writer thread started.")

    def stop(self):
        self._running = False
        if self._conn:
            self._conn.close()