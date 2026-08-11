"""
db.py
-----
Petite couche d'accès à la base de données Supabase (PostgreSQL).
Volontairement simple (psycopg2 brut, pas d'ORM) pour rester lisible
dans le cadre d'un stage académique.
"""

import os
import json
import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager

DATABASE_URL = os.getenv("DATABASE_URL")


@contextmanager
def get_connection():
    conn = psycopg2.connect(DATABASE_URL)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_or_create_candidate(phone_number: str, full_name: str = None) -> dict:
    """Récupère un candidat existant, ou le crée s'il contacte le bot pour la première fois."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM candidates WHERE phone_number = %s", (phone_number,)
            )
            candidate = cur.fetchone()

            if candidate:
                # Met à jour le nom si on ne l'avait pas encore (ex: premier contact anonyme)
                if full_name and not candidate.get("full_name"):
                    cur.execute(
                        "UPDATE candidates SET full_name = %s WHERE id = %s",
                        (full_name, candidate["id"]),
                    )
                    candidate["full_name"] = full_name
                return dict(candidate)

            cur.execute(
                """INSERT INTO candidates (phone_number, full_name)
                   VALUES (%s, %s) RETURNING *""",
                (phone_number, full_name),
            )
            return dict(cur.fetchone())


def set_candidate_language(phone_number: str, language: str):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE candidates SET preferred_language = %s WHERE phone_number = %s",
                (language, phone_number),
            )


def create_request(
    candidate_id: int,
    input_type: str,
    raw_text: str = None,
    cv_filename: str = None,
    cv_extracted_text: str = None,
) -> int:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO requests (candidate_id, input_type, raw_text, cv_filename, cv_extracted_text)
                   VALUES (%s, %s, %s, %s, %s) RETURNING id""",
                (candidate_id, input_type, raw_text, cv_filename, cv_extracted_text),
            )
            return cur.fetchone()[0]


def update_request_result(
    request_id: int,
    detected_domain: str,
    detected_skills: list,
    recommended_link: str,
    status: str,
):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE requests
                   SET detected_domain = %s, detected_skills = %s,
                       recommended_link = %s, status = %s
                   WHERE id = %s""",
                (detected_domain, json.dumps(detected_skills or []), recommended_link, status, request_id),
            )


def log_message(candidate_id: int, request_id: int, sender: str, content: str):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO messages (request_id, candidate_id, sender, content)
                   VALUES (%s, %s, %s, %s)""",
                (request_id, candidate_id, sender, content),
            )


def create_escalation(request_id, reason: str, notified_contact: str = None):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO escalations (request_id, reason, notified_contact)
                   VALUES (%s, %s, %s)""",
                (request_id, reason, notified_contact),
            )


def list_staff_contacts() -> list:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM staff_contacts WHERE is_active = TRUE")
            return [dict(row) for row in cur.fetchall()]


def get_staff_contact_by_name(name: str):
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM staff_contacts WHERE name ILIKE %s AND is_active = TRUE LIMIT 1",
                (f"%{name}%",),
            )
            row = cur.fetchone()
            return dict(row) if row else None


def get_candidate_by_phone(phone_number: str):
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM candidates WHERE phone_number = %s", (phone_number,))
            row = cur.fetchone()
            return dict(row) if row else None


def get_last_request(candidate_id: int):
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """SELECT * FROM requests WHERE candidate_id = %s
                   ORDER BY created_at DESC LIMIT 1""",
                (candidate_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None


def create_notification(recipient_phone: str, message: str, reason: str = None) -> int:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO notifications (recipient_phone, message, reason)
                   VALUES (%s, %s, %s) RETURNING id""",
                (recipient_phone, message, reason),
            )
            return cur.fetchone()[0]


def get_unsent_notifications() -> list:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM notifications WHERE sent = FALSE ORDER BY created_at")
            return [dict(row) for row in cur.fetchall()]


def mark_notification_sent(notification_id: int):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE notifications SET sent = TRUE WHERE id = %s", (notification_id,))


def get_latest_cv_by_candidate(candidate_id: int):
    """Récupère le texte du CV le plus récent pour ce candidat pour le RAG."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """SELECT cv_extracted_text, cv_filename FROM requests
                   WHERE candidate_id = %s AND input_type = 'document' AND cv_extracted_text IS NOT NULL AND cv_extracted_text != ''
                   ORDER BY created_at DESC LIMIT 1""",
                (candidate_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None
