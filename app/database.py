
import sqlite3
from pathlib import Path

DB_PATH = Path("output/traffic_violations.db")


def get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database():
    with get_connection() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS violations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plate_number TEXT,
                plate_confidence REAL,
                violation_type TEXT NOT NULL,
                track_id INTEGER,
                timestamp TEXT NOT NULL,
                evidence_image TEXT
            )
        """)


def save_violation(
    plate_number,
    plate_confidence,
    violation_type,
    track_id,
    timestamp,
    evidence_image
):
    with get_connection() as connection:
        cursor = connection.execute("""
            INSERT INTO violations (
                plate_number,
                plate_confidence,
                violation_type,
                track_id,
                timestamp,
                evidence_image
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (
            plate_number,
            plate_confidence,
            violation_type,
            track_id,
            timestamp,
            evidence_image
        ))
        return cursor.lastrowid


def get_all_violations():
    with get_connection() as connection:
        rows = connection.execute("""
            SELECT * FROM violations ORDER BY id DESC
        """).fetchall()
        return [dict(row) for row in rows]


initialize_database()
