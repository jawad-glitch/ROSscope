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