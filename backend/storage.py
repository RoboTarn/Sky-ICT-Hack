"""Transactional cloud snapshot store; SQLite remains the local default."""
import json
import threading
import psycopg


class PostgresState:
    def __init__(self, engine, url):
        self.engine, self.url = engine, url
        self.local = threading.RLock()
        self.depth = 0
        self.connection = None
        with psycopg.connect(url, connect_timeout=10) as connection:
            connection.execute('CREATE TABLE IF NOT EXISTS swarm_state (id integer PRIMARY KEY, payload jsonb NOT NULL)')
            connection.execute('CREATE TABLE IF NOT EXISTS swarm_events (seq bigserial PRIMARY KEY, run_id text NOT NULL, payload jsonb NOT NULL)')

    def __enter__(self):
        self.local.acquire()
        try:
            if self.depth == 0:
                self.connection = psycopg.connect(self.url, connect_timeout=10)
                self.connection.execute("SET LOCAL lock_timeout = '10s'")
                # Also serializes the first seed insert across cold starts.
                self.connection.execute('SELECT pg_advisory_xact_lock(884201)')
                self.connection.execute('INSERT INTO swarm_state VALUES (1, %s::jsonb) ON CONFLICT (id) DO NOTHING',
                                        (json.dumps(self.engine.state, ensure_ascii=False),))
                row = self.connection.execute('SELECT payload FROM swarm_state WHERE id=1 FOR UPDATE').fetchone()
                self.engine.state = row[0]
            self.depth += 1
            return self
        except BaseException:
            if self.connection:
                self.connection.rollback()
                self.connection.close()
                self.connection = None
            self.local.release()
            raise

    def __exit__(self, kind, value, traceback):
        self.depth -= 1
        try:
            if self.depth == 0:
                if kind: self.connection.rollback()
                else: self.connection.commit()
                self.connection.close()
                self.connection = None
        finally: self.local.release()

    def save(self, state):
        self.connection.execute('UPDATE swarm_state SET payload=%s::jsonb WHERE id=1', (json.dumps(state, ensure_ascii=False),))

    def event(self, event):
        return self.connection.execute('INSERT INTO swarm_events(run_id,payload) VALUES (%s,%s::jsonb) RETURNING seq',
                                       (event['runId'], json.dumps(event, ensure_ascii=False))).fetchone()[0]
