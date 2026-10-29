
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "output" / "traffic_violations.db"


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
        connection.execute("""
            CREATE TABLE IF NOT EXISTS plates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                video TEXT NOT NULL,
                track_id INTEGER,
                vehicle TEXT,
                plate_number TEXT NOT NULL,
                plate_confidence REAL,
                first_seen_sec REAL,
                last_seen_sec REAL,
                image TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
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


def update_violation_plate(row_id, plate_number, plate_confidence):
    with get_connection() as connection:
        connection.execute(
            "UPDATE violations SET plate_number = ?, plate_confidence = ? WHERE id = ?",
            (plate_number, plate_confidence, row_id),
        )


def clear_violations():
    with get_connection() as connection:
        connection.execute("DELETE FROM violations")


def save_plate(video, track_id, vehicle, plate_number, plate_confidence,
               first_seen_sec, last_seen_sec, image):
    """Insert a plate, or merge into an existing row for the same plate in
    the same video (the tracker sometimes gives one vehicle two IDs)."""
    with get_connection() as connection:
        existing = connection.execute(
            "SELECT * FROM plates WHERE video = ? AND plate_number = ?",
            (video, plate_number),
        ).fetchone()

        if existing:
            better = plate_confidence > (existing["plate_confidence"] or 0)
            connection.execute("""
                UPDATE plates SET
                    first_seen_sec = MIN(first_seen_sec, ?),
                    last_seen_sec = MAX(last_seen_sec, ?),
                    plate_confidence = MAX(plate_confidence, ?),
                    image = ?
                WHERE id = ?
            """, (
                first_seen_sec, last_seen_sec, plate_confidence,
                image if better and image else existing["image"],
                existing["id"],
            ))
            return existing["id"]

        cursor = connection.execute("""
            INSERT INTO plates (video, track_id, vehicle, plate_number,
                plate_confidence, first_seen_sec, last_seen_sec, image)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (video, track_id, vehicle, plate_number, plate_confidence,
              first_seen_sec, last_seen_sec, image))
        return cursor.lastrowid


def get_plates(video=None):
    with get_connection() as connection:
        if video:
            rows = connection.execute(
                "SELECT * FROM plates WHERE video = ? ORDER BY first_seen_sec",
                (video,),
            ).fetchall()
        else:
            rows = connection.execute(
                "SELECT * FROM plates ORDER BY id DESC"
            ).fetchall()
        return [dict(row) for row in rows]


def clear_plates(video=None):
    with get_connection() as connection:
        if video:
            connection.execute("DELETE FROM plates WHERE video = ?", (video,))
        else:
            connection.execute("DELETE FROM plates")


def get_all_violations():
    with get_connection() as connection:
        rows = connection.execute("""
            SELECT * FROM violations ORDER BY id DESC
        """).fetchall()
        return [dict(row) for row in rows]


initialize_database()
