"""
database.py  –  طبقة قاعدة البيانات SQLite
=============================================
جداول:
  • users      → المستخدمون (تسجيل + دخول)
  • analyses   → سجل التحليلات لكل مستخدم

الاستخدام:
  from database import init_db, save_analysis, get_history, ...
"""

import sqlite3
import hashlib
import os
from datetime import datetime
from typing import Optional

# ── مسار ملف قاعدة البيانات ────────────────────────────────
DB_PATH = os.path.join(os.path.dirname(__file__), "contracts.db")

# ══════════════════════════════════════════════════════════════
#  إنشاء الجداول
# ══════════════════════════════════════════════════════════════
def init_db() -> None:
    """يُنشئ الجداول إذا لم تكن موجودة"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript("""
        PRAGMA journal_mode = WAL;
        PRAGMA foreign_keys = ON;

        -- ── جدول المستخدمين ───────────────────────────────
        CREATE TABLE IF NOT EXISTS users (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            username     TEXT    NOT NULL UNIQUE COLLATE NOCASE,
            email        TEXT    NOT NULL UNIQUE COLLATE NOCASE,
            password_hash TEXT   NOT NULL,
            plan         TEXT    NOT NULL DEFAULT 'free',
            created_at   TEXT    NOT NULL DEFAULT (datetime('now')),
            last_login   TEXT
        );

        -- ── جدول التحليلات ────────────────────────────────
        CREATE TABLE IF NOT EXISTS analyses (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            pdf_filename    TEXT    NOT NULL,
            pdf_size_kb     INTEGER,
            contract_type   TEXT    NOT NULL,
            score           INTEGER NOT NULL,
            level           TEXT    NOT NULL,
            found_count     INTEGER NOT NULL DEFAULT 0,
            missing_count   INTEGER NOT NULL DEFAULT 0,
            total_expected  INTEGER NOT NULL DEFAULT 0,
            found_clauses   TEXT,        -- JSON list
            missing_clauses TEXT,        -- JSON list
            risks           TEXT,        -- JSON list
            analyzed_at     TEXT    NOT NULL DEFAULT (datetime('now'))
        );

        -- ── فهارس للبحث السريع ────────────────────────────
        CREATE INDEX IF NOT EXISTS idx_analyses_user
            ON analyses(user_id, analyzed_at DESC);
        """)

# ══════════════════════════════════════════════════════════════
#  إدارة المستخدمين
# ══════════════════════════════════════════════════════════════
def _hash(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

def register_user(username: str, email: str, password: str) -> dict:
    """
    يُسجّل مستخدماً جديداً.
    يُعيد: {"ok": True, "user_id": int}
             أو {"ok": False, "error": str}
    """
    if len(username.strip()) < 3:
        return {"ok": False, "error": "اسم المستخدم يجب أن يكون 3 أحرف على الأقل"}
    if "@" not in email:
        return {"ok": False, "error": "البريد الإلكتروني غير صالح"}
    if len(password) < 6:
        return {"ok": False, "error": "كلمة المرور يجب أن تكون 6 أحرف على الأقل"}
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.execute(
                "INSERT INTO users (username, email, password_hash) VALUES (?,?,?)",
                (username.strip(), email.strip().lower(), _hash(password))
            )
            return {"ok": True, "user_id": cur.lastrowid}
    except sqlite3.IntegrityError as e:
        msg = str(e)
        if "username" in msg:
            return {"ok": False, "error": "اسم المستخدم مستخدم بالفعل"}
        if "email" in msg:
            return {"ok": False, "error": "البريد الإلكتروني مستخدم بالفعل"}
        return {"ok": False, "error": "خطأ في التسجيل"}

def login_user(username: str, password: str) -> dict:
    """
    يتحقق من بيانات الدخول.
    يُعيد: {"ok": True, "user": {...}}
             أو {"ok": False, "error": str}
    """
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM users WHERE username = ? COLLATE NOCASE",
            (username.strip(),)
        ).fetchone()
    if not row:
        return {"ok": False, "error": "اسم المستخدم غير موجود"}
    if row["password_hash"] != _hash(password):
        return {"ok": False, "error": "كلمة المرور غير صحيحة"}
    # تحديث آخر دخول
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "UPDATE users SET last_login=? WHERE id=?",
            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), row["id"])
        )
    return {
        "ok": True,
        "user": {
            "id":       row["id"],
            "username": row["username"],
            "email":    row["email"],
            "plan":     row["plan"],
        }
    }

def get_user_by_id(user_id: int) -> Optional[dict]:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    if not row:
        return None
    return dict(row)

# ══════════════════════════════════════════════════════════════
#  سجل التحليلات
# ══════════════════════════════════════════════════════════════
def save_analysis(user_id: int, result: dict, pdf_path: str,
                  contract_type: str) -> int:
    """
    يحفظ نتيجة تحليل عقد في قاعدة البيانات.
    يُعيد: ID السجل المُضاف
    """
    import json
    fname   = os.path.basename(pdf_path) if pdf_path else "غير معروف"
    size_kb = (os.path.getsize(pdf_path) // 1024) if pdf_path and os.path.exists(pdf_path) else 0

    found   = list(result.get("found", {}).keys())
    missing = result.get("missing", [])
    risks   = [r.get("title","") for r in result.get("risks", [])]

    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute("""
            INSERT INTO analyses
              (user_id, pdf_filename, pdf_size_kb, contract_type,
               score, level, found_count, missing_count, total_expected,
               found_clauses, missing_clauses, risks)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            user_id, fname, size_kb, contract_type,
            result.get("score", 0),
            result.get("level", "—"),
            result.get("total_found", 0),
            len(missing),
            result.get("total_exp", 0),
            json.dumps(found,    ensure_ascii=False),
            json.dumps(missing,  ensure_ascii=False),
            json.dumps(risks,    ensure_ascii=False),
        ))
        return cur.lastrowid

def get_user_history(user_id: int, limit: int = 50) -> list[dict]:
    """
    يُعيد آخر `limit` تحليلاً للمستخدم مرتبةً من الأحدث.
    """
    import json
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT * FROM analyses
            WHERE user_id = ?
            ORDER BY analyzed_at DESC
            LIMIT ?
        """, (user_id, limit)).fetchall()

    result = []
    for r in rows:
        d = dict(r)
        for field in ("found_clauses", "missing_clauses", "risks"):
            try:
                d[field] = json.loads(d[field] or "[]")
            except Exception:
                d[field] = []
        result.append(d)
    return result

def delete_analysis(analysis_id: int, user_id: int) -> bool:
    """يحذف تحليلاً معيناً (يتحقق أن المستخدم هو صاحبه)"""
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute(
            "DELETE FROM analyses WHERE id=? AND user_id=?",
            (analysis_id, user_id)
        )
        return cur.rowcount > 0

def get_user_stats(user_id: int) -> dict:
    """إحصاء سريع للمستخدم"""
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute("""
            SELECT
                COUNT(*)          AS total,
                ROUND(AVG(score)) AS avg_score,
                MAX(score)        AS best_score,
                MIN(score)        AS worst_score
            FROM analyses WHERE user_id=?
        """, (user_id,)).fetchone()
    return {
        "total":       row[0] or 0,
        "avg_score":   int(row[1] or 0),
        "best_score":  row[2] or 0,
        "worst_score": row[3] or 0,
    }

# ══════════════════════════════════════════════════════════════
#  التهيئة التلقائية عند الاستيراد
# ══════════════════════════════════════════════════════════════
init_db()

if __name__ == "__main__":
    print("✓ قاعدة البيانات جاهزة:", DB_PATH)
    # اختبار سريع
    r = register_user("مستخدم_تجربة", "test@example.com", "123456")
    print("تسجيل:", r)
    r2 = login_user("مستخدم_تجربة", "123456")
    print("دخول: ", r2)