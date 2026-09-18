"""
Utilities to wait for PostgreSQL and MinIO services to become healthy on cold start.
"""

import os
import time
import urllib.request
import psycopg2

def wait_for_postgres(max_retries=30, delay=1.5):
    host = os.environ.get('POSTGRES_HOST', 'postgres')
    port = os.environ.get('POSTGRES_PORT', '5432')
    db = os.environ.get('POSTGRES_DB', 'annapurna')
    user = os.environ.get('POSTGRES_USER', 'annapurna')
    pwd = os.environ.get('POSTGRES_PASSWORD', 'annapurna')

    print(f"[Wait] Waiting for PostgreSQL at {host}:{port}/{db}...")
    for i in range(max_retries):
        try:
            conn = psycopg2.connect(
                host=host, port=port, dbname=db, user=user, password=pwd, connect_timeout=3
            )
            cur = conn.cursor()
            cur.execute("SELECT 1;")
            # Check if masters.sql has finished loading
            cur.execute("SELECT count(*) FROM products;")
            cnt = cur.fetchone()[0]
            conn.close()
            print(f"[Wait] PostgreSQL is healthy! (Found {cnt} products in master catalog)")
            return True
        except Exception as e:
            time.sleep(delay)
    raise TimeoutError(f"PostgreSQL at {host}:{port} did not become ready in time.")

def wait_for_minio(max_retries=30, delay=1.5):
    endpoint = os.environ.get('MINIO_ENDPOINT', 'minio:9000')
    if not endpoint.startswith('http'):
        endpoint = f"http://{endpoint}"
    health_url = f"{endpoint}/minio/health/live"

    print(f"[Wait] Waiting for MinIO at {health_url}...")
    for i in range(max_retries):
        try:
            req = urllib.request.Request(health_url, method='GET')
            with urllib.request.urlopen(req, timeout=3) as resp:
                if resp.status == 200:
                    print(f"[Wait] MinIO is healthy and responding at {endpoint}!")
                    return True
        except Exception:
            time.sleep(delay)
    raise TimeoutError(f"MinIO at {endpoint} did not become ready in time.")

def wait_for_all_services():
    wait_for_postgres()
    wait_for_minio()
