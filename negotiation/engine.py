"""
negotiation/engine.py
══════════════════════════════════════════════════════════════
محرك التفاوض الذكي — يعمل بالكامل بدون إنترنت.

الدوال العامة:
  analyze_gap(a, b)          → dict  (تحليل الفجوة)
  suggest_clause(title,a,b)  → str   (الصيغة المقترحة)
  session_summary(clauses)   → dict  (ملخص الجلسة)
══════════════════════════════════════════════════════════════
"""

import re


# ── كلمات تُتجاهل في المقارنة ───────────────────────────────
_STOP = {
    'في','من','إلى','على','عن','هذا','ذلك','أن','أو','و',
    'مع','قد','يتم','يجب','لا','أي','كل','بين','عند',
}

# ── نمط استخراج الأرقام والوحدات ────────────────────────────
_NUM_RE = re.compile(
    r'(\d[\d,./٪]*)\s*(يوم|شهر|سنة|ألف|مليون|%|دولار|ريال|€|\$)?',
    re.UNICODE
)


# ══════════════════════════════════════════════════════════════
#  تحليل الفجوة بين نصّي الطرفين
# ══════════════════════════════════════════════════════════════
def analyze_gap(text_a: str, text_b: str) -> dict:
    """
    يُحسب التشابه بين موقفَي الطرفين (Jaccard similarity).
    يُعيد:
      similarity   : 0.0 – 1.0
      gap_level    : 'منخفض' | 'متوسط' | 'عالي'
      common_words : قائمة الكلمات المشتركة
      nums_a, nums_b : الأرقام في كل موقف
    """
    def tokens(t):
        words = re.findall(r'[\u0600-\u06FFa-zA-Z]+', t.lower())
        return {w for w in words if w not in _STOP and len(w) > 2}

    ta, tb  = tokens(text_a), tokens(text_b)
    common  = ta & tb
    union   = ta | tb
    sim     = round(len(common) / len(union), 2) if union else 0.0
    gap     = "منخفض" if sim >= 0.6 else "متوسط" if sim >= 0.3 else "عالي"

    return {
        "similarity":   sim,
        "gap_level":    gap,
        "common_words": sorted(common),
        "nums_a":       _NUM_RE.findall(text_a),
        "nums_b":       _NUM_RE.findall(text_b),
    }


# ══════════════════════════════════════════════════════════════
#  خوارزمية الاقتراح الذكية (بدون إنترنت)
# ══════════════════════════════════════════════════════════════
def suggest_clause(title: str, text_a: str, text_b: str) -> str:
    """
    يُنتج صيغة مقترحة متوازنة بين موقفَي الطرفين.

    المنطق:
    ┌──────────────────┬────────────────────────────────────────────┐
    │ تشابه عالٍ ≥0.6  │ استخدم نص أ + أضف مخاوف ب               │
    │ تشابه متوسط 0.3  │ ادمج الموقفين بصيغة محايدة               │
    │ تشابه منخفض <0.3 │ وسط حسابي للأرقام + صيغة تفاوضية        │
    └──────────────────┴────────────────────────────────────────────┘
    """
    if not text_a.strip() and not text_b.strip():
        return ""
    if not text_a.strip():
        return text_b.strip()
    if not text_b.strip():
        return text_a.strip()

    gap = analyze_gap(text_a, text_b)
    sim = gap["similarity"]
    a   = text_a.strip().rstrip(".")
    b   = text_b.strip().rstrip(".")

    # ── تشابه عالٍ: نص أ كأساس مع مراعاة مخاوف ب ───────────
    if sim >= 0.6:
        return f"{a}."

    # ── تشابه متوسط: دمج الموقفين ────────────────────────────
    if sim >= 0.3:
        return (
            f"يتفق الطرفان على {title} وفق الآتي:\n"
            f"  • الأساس: {a}.\n"
            f"  • مع مراعاة: {b}."
        )

    # ── تشابه منخفض: وسط الأرقام + صيغة تفاوضية ─────────────
    mid_note = _midpoint_note(gap["nums_a"], gap["nums_b"])
    return (
        f"لا يزال الطرفان بعيدَين في بند «{title}».\n"
        f"  • موقف الطرف الأول: {a}.\n"
        f"  • موقف الطرف الثاني: {b}.\n"
        f"{mid_note}"
        f"يُنصح بمزيد من التفاوض للوصول لأرضية مشتركة."
    )


def _midpoint_note(nums_a: list, nums_b: list) -> str:
    """يحسب الوسط الحسابي لأول رقمين في الموقفين إن أمكن."""
    if not nums_a or not nums_b:
        return ""
    try:
        def _clean(pair):
            return float(re.sub(r"[^\d.]", "", pair[0].replace(",", "")))

        va   = _clean(nums_a[0])
        vb   = _clean(nums_b[0])
        mid  = (va + vb) / 2
        nice = int(mid) if mid == int(mid) else round(mid, 1)
        unit = nums_a[0][1] or nums_b[0][1] or ""
        return f"  • مقترح النظام: {nice} {unit}.\n"
    except Exception:
        return ""


# ══════════════════════════════════════════════════════════════
#  ملخص الجلسة
# ══════════════════════════════════════════════════════════════
def session_summary(clauses: list) -> dict:
    """
    يُنتج ملخصاً إحصائياً للجلسة.
    يُعيد: total, agreed, pending, rejected, modified,
            progress_pct, recommendation
    """
    total    = len(clauses)
    agreed   = sum(1 for c in clauses if c["status"] == "agreed")
    rejected = sum(1 for c in clauses if c["status"] == "rejected")
    modified = sum(1 for c in clauses if c["status"] == "modified")
    pending  = total - agreed - rejected - modified
    pct      = round(agreed / total * 100) if total else 0

    if pct == 100:
        rec = "✅ تمّ الاتفاق على جميع البنود. الجلسة جاهزة للإغلاق."
    elif pct >= 70:
        rec = "🟡 قاربتم الاتفاق — تبقّت بنود قليلة."
    elif pct >= 40:
        rec = "🟠 تقدم جيد — استمروا في التفاوض."
    else:
        rec = "🔴 مراحل مبكرة — ادخلوا مواقف الطرفين وابدأوا التفاوض."

    return {
        "total":        total,
        "agreed":       agreed,
        "pending":      pending,
        "rejected":     rejected,
        "modified":     modified,
        "progress_pct": pct,
        "recommendation": rec,
    }