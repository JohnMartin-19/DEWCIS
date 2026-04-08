#!/usr/bin/env python3
import argparse
import grp
import pwd
import os
import shutil
import sys
import datetime
import psycopg2
from psycopg2.extras import RealDictCursor

# ─── Config ───────────────────────────────────────────────────────────────────
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "postgres"),
    "port": os.getenv("DB_PORT", "5432"),
    "dbname": os.getenv("DB_NAME", "archivedb"),
    "user": os.getenv("DB_USER", "archiveuser"),
    "password": os.getenv("DB_PASSWORD", "archivepass"),
}
ARCHIVE_ROOT = os.getenv("ARCHIVE_DIR", "/tmp/archive")


# ─── Database ─────────────────────────────────────────────────────────────────
def get_connection():
    return psycopg2.connect(**DB_CONFIG)


def create_schema(conn):
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS archive_runs (
                id          SERIAL PRIMARY KEY,
                group_name  VARCHAR(100) NOT NULL,
                started_at  TIMESTAMP NOT NULL,
                finished_at TIMESTAMP,
                duration    FLOAT,
                total_moved   INT DEFAULT 0,
                total_skipped INT DEFAULT 0,
                total_errors  INT DEFAULT 0,
                status      VARCHAR(20) DEFAULT 'running'
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS archive_events (
                id          SERIAL PRIMARY KEY,
                run_id      INT REFERENCES archive_runs(id),
                source      TEXT,
                destination TEXT,
                status      VARCHAR(20),
                reason      TEXT,
                timestamp   TIMESTAMP NOT NULL
            );
        """)
        conn.commit()


def start_run(conn, group_name):
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO archive_runs (group_name, started_at, status)
            VALUES (%s, %s, 'running') RETURNING id
        """, (group_name, datetime.datetime.utcnow()))
        run_id = cur.fetchone()[0]
        conn.commit()
        return run_id


def log_event(conn, run_id, source, destination, status, reason=None):
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO archive_events (run_id, source, destination, status, reason, timestamp)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (run_id, source, destination, status, reason, datetime.datetime.utcnow()))
        conn.commit()


def finish_run(conn, run_id, moved, skipped, errors, started_at):
    finished_at = datetime.datetime.utcnow()
    duration = (finished_at - started_at).total_seconds()
    status = "completed" if errors == 0 else "completed_with_errors"
    with conn.cursor() as cur:
        cur.execute("""
            UPDATE archive_runs
            SET finished_at = %s, duration = %s,
                total_moved = %s, total_skipped = %s, total_errors = %s, status = %s
            WHERE id = %s
        """, (finished_at, duration, moved, skipped, errors, status, run_id))
        conn.commit()


# ─── Archiver ─────────────────────────────────────────────────────────────────
def archive_group(group_name):
    # Resolve group
    try:
        group = grp.getgrnam(group_name)
    except KeyError:
        print(f"Error: group '{group_name}' not found on this system.", file=sys.stderr)
        sys.exit(1)

    members = group.gr_mem
    if not members:
        print(f"Group '{group_name}' has no members. Nothing to archive.")
        sys.exit(0)

    # Connect to DB
    try:
        conn = get_connection()
    except psycopg2.OperationalError as e:
        print(f"Error: could not connect to database: {e}", file=sys.stderr)
        sys.exit(1)

    create_schema(conn)
    started_at = datetime.datetime.utcnow()
    run_id = start_run(conn, group_name)

    moved = skipped = errors = 0

    for username in members:
        # Resolve home directory
        try:
            pw = pwd.getpwnam(username)
            home_dir = pw.pw_dir
        except KeyError:
            print(f"  Warning: user '{username}' not found, skipping.")
            continue

        if not os.path.isdir(home_dir):
            print(f"  Warning: home directory '{home_dir}' does not exist, skipping.")
            continue

        # Walk files in home directory
        for filename in os.listdir(home_dir):
            src = os.path.join(home_dir, filename)
            if not os.path.isfile(src):
                continue

            # Preserve directory structure: archive_root/group/username/filename
            dest_dir = os.path.join(ARCHIVE_ROOT, group_name, username)
            os.makedirs(dest_dir, exist_ok=True)
            dest = os.path.join(dest_dir, filename)

            # Already archived
            if os.path.exists(dest):
                print(f"  SKIP  {src} → already at destination")
                log_event(conn, run_id, src, dest, "skipped", "file already at destination")
                skipped += 1
                continue

            # Move the file
            try:
                shutil.move(src, dest)
                print(f"  MOVED {src} → {dest}")
                log_event(conn, run_id, src, dest, "moved")
                moved += 1
            except PermissionError as e:
                print(f"  ERROR {src} → {e}")
                log_event(conn, run_id, src, dest, "error", str(e))
                errors += 1

    finish_run(conn, run_id, moved, skipped, errors, started_at)
    conn.close()

    print(f"\nRun complete — moved: {moved}, skipped: {skipped}, errors: {errors}")


# ─── Entry point ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Archive files for a Linux group.")
    parser.add_argument("--group", required=True, help="Linux group name to archive")
    args = parser.parse_args()
    archive_group(args.group)