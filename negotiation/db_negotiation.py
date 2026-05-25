"""
negotiation/db_negotiation.py
══════════════════════════════════════════════════════════════
طبقة قاعدة البيانات لنظام التفاوض — نظيفة وبدون AI.

الجداول الثلاثة تُضاف لنفس contracts.db:
  neg_sessions  → جلسات التفاوض
  neg_clauses   → بنود كل جلسة
  neg_history   → سجل كل إجراء (audit log)
══════════════════════════════════════════════════════════════
"""

import sqlite3
import os
from datetime import datetime
from typing import Optional

# ── نفس قاعدة بيانات المشروع الرئيسي ──────────────────────
_ROOT   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(_ROOT, "contracts.db")


# ══════════════════════════════════════════════════════════════
#  ثوابت الحالات — مركزية ومقروءة
# ══════════════════════════════════════════════════════════════
class ClauseStatus:
    PENDING   = "pending"    # بانتظار رد الطرف الثاني
    ACCEPTED  = "accepted"   # وافق الطرف الثاني
    REJECTED  = "rejected"   # رفض الطرف الثاني
    MODIFIED  = "modified"   # الطرف الثاني يقترح تعديلاً
    AGREED    = "agreed"     # اتُّفق عليه نهائياً بإقرار المدير

class SessionStatus:
    OPEN   = "open"    # الجلسة نشطة
    CLOSED = "closed"  # أُغلقت

# تسميات الحالات بالعربية
STATUS_AR = {
    ClauseStatus.PENDING:  "بانتظار الرد",
    ClauseStatus.ACCEPTED: "مقبول",
    ClauseStatus.REJECTED: "مرفوض",
    ClauseStatus.MODIFIED: "معدَّل",
    ClauseStatus.AGREED:   "متفق عليه",
}


# ══════════════════════════════════════════════════════════════
#  إنشاء الجداول (آمن للتكرار)
# ══════════════════════════════════════════════════════════════
def init_negotiation_db() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript("""
        PRAGMA foreign_keys = ON;

        CREATE TABLE IF NOT EXISTS neg_sessions (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            title         TEXT    NOT NULL,
            party_a_name  TEXT    NOT NULL DEFAULT 'الطرف الأول',
            party_b_name  TEXT    NOT NULL DEFAULT 'الطرف الثاني',
            contract_type TEXT    NOT NULL DEFAULT '',
            status        TEXT    NOT NULL DEFAULT 'open',
            agreed_count  INTEGER NOT NULL DEFAULT 0,
            total_count   INTEGER NOT NULL DEFAULT 0,
            created_at    TEXT    NOT NULL DEFAULT (datetime('now')),
            updated_at    TEXT    NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS neg_clauses (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id     INTEGER NOT NULL REFERENCES neg_sessions(id) ON DELETE CASCADE,
            clause_title   TEXT    NOT NULL,
            party_a_text   TEXT    NOT NULL DEFAULT '',
            party_b_text   TEXT    NOT NULL DEFAULT '',
            suggested_text TEXT    NOT NULL DEFAULT '',
            status         TEXT    NOT NULL DEFAULT 'pending',
            final_text     TEXT    NOT NULL DEFAULT '',
            priority       INTEGER NOT NULL DEFAULT 0,
            created_at     TEXT    NOT NULL DEFAULT (datetime('now')),
            updated_at     TEXT    NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS neg_history (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            clause_id  INTEGER NOT NULL REFERENCES neg_clauses(id) ON DELETE CASCADE,
            actor      TEXT    NOT NULL,
            action     TEXT    NOT NULL,
            content    TEXT    NOT NULL DEFAULT '',
            created_at TEXT    NOT NULL DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_neg_sess_user
            ON neg_sessions(user_id, updated_at DESC);
        CREATE INDEX IF NOT EXISTS idx_neg_cls_sess
            ON neg_clauses(session_id, priority);
        CREATE INDEX IF NOT EXISTS idx_neg_hist_cls
            ON neg_history(clause_id, created_at);
        """)


# ══════════════════════════════════════════════════════════════
#  دوال الجلسات
# ══════════════════════════════════════════════════════════════
def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _refresh_counts(session_id: int, conn: sqlite3.Connection) -> None:
    """يُحدّث agreed_count و total_count تلقائياً."""
    row = conn.execute(
        "SELECT COUNT(*), SUM(status='agreed') FROM neg_clauses WHERE session_id=?",
        (session_id,)
    ).fetchone()
    conn.execute(
        "UPDATE neg_sessions SET agreed_count=?, total_count=?, updated_at=? WHERE id=?",
        (row[1] or 0, row[0] or 0, _now(), session_id)
    )


def create_session(user_id: int, title: str,
                   party_a: str, party_b: str,
                   contract_type: str = "") -> int:
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute(
            "INSERT INTO neg_sessions (user_id,title,party_a_name,party_b_name,contract_type)"
            " VALUES (?,?,?,?,?)",
            (user_id, title.strip(), party_a.strip(), party_b.strip(), contract_type)
        )
        return cur.lastrowid


def get_session(session_id: int) -> Optional[dict]:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM neg_sessions WHERE id=?", (session_id,)).fetchone()
    return dict(row) if row else None


def close_session(session_id: int) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("UPDATE neg_sessions SET status='closed', updated_at=? WHERE id=?",
                     (_now(), session_id))


def get_user_sessions(user_id: int, limit: int = 40) -> list:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM neg_sessions WHERE user_id=? ORDER BY updated_at DESC LIMIT ?",
            (user_id, limit)
        ).fetchall()
    return [dict(r) for r in rows]


# ══════════════════════════════════════════════════════════════
#  دوال البنود
# ══════════════════════════════════════════════════════════════
def add_clause(session_id: int, title: str,
               party_a_text: str = "", priority: int = 0) -> int:
    now = _now()
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute(
            "INSERT INTO neg_clauses (session_id,clause_title,party_a_text,priority,created_at,updated_at)"
            " VALUES (?,?,?,?,?,?)",
            (session_id, title.strip(), party_a_text.strip(), priority, now, now)
        )
        cid = cur.lastrowid
        if party_a_text.strip():
            conn.execute(
                "INSERT INTO neg_history (clause_id,actor,action,content,created_at) VALUES (?,?,?,?,?)",
                (cid, "party_a", "propose", party_a_text.strip(), now)
            )
        _refresh_counts(session_id, conn)
        return cid


def respond_party_b(clause_id: int, session_id: int,
                    action: str, text: str = "") -> None:
    """
    يُسجّل رد الطرف الثاني.
    action: 'accepted' | 'rejected' | 'modified'
    """
    status_map = {
        "accepted": ClauseStatus.ACCEPTED,
        "rejected":  ClauseStatus.REJECTED,
        "modified":  ClauseStatus.MODIFIED,
    }
    new_status = status_map.get(action, ClauseStatus.PENDING)
    now = _now()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "UPDATE neg_clauses SET party_b_text=?, status=?, updated_at=? WHERE id=?",
            (text.strip(), new_status, now, clause_id)
        )
        conn.execute(
            "INSERT INTO neg_history (clause_id,actor,action,content,created_at) VALUES (?,?,?,?,?)",
            (clause_id, "party_b", action, text.strip(), now)
        )
        _refresh_counts(session_id, conn)


def save_suggestion(clause_id: int, session_id: int, suggested: str) -> None:
    now = _now()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "UPDATE neg_clauses SET suggested_text=?, status='suggested', updated_at=? WHERE id=?",
            (suggested.strip(), now, clause_id)
        )
        conn.execute(
            "INSERT INTO neg_history (clause_id,actor,action,content,created_at) VALUES (?,?,?,?,?)",
            (clause_id, "system", "suggest", suggested.strip(), now)
        )


def agree_clause(clause_id: int, session_id: int, final_text: str) -> None:
    now = _now()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "UPDATE neg_clauses SET final_text=?, status='agreed', updated_at=? WHERE id=?",
            (final_text.strip(), now, clause_id)
        )
        conn.execute(
            "INSERT INTO neg_history (clause_id,actor,action,content,created_at) VALUES (?,?,?,?,?)",
            (clause_id, "system", "agree", final_text.strip(), now)
        )
        _refresh_counts(session_id, conn)


def get_clauses(session_id: int) -> list:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM neg_clauses WHERE session_id=? ORDER BY priority, id",
            (session_id,)
        ).fetchall()
    return [dict(r) for r in rows]


def get_clause_history(clause_id: int) -> list:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM neg_history WHERE clause_id=? ORDER BY created_at",
            (clause_id,)
        ).fetchall()
    return [dict(r) for r in rows]


# ── تهيئة تلقائية عند الاستيراد ────────────────────────────
init_negotiation_db()