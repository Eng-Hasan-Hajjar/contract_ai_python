"""
contract_detector.py  —  كاشف نوع العقد التلقائي
═══════════════════════════════════════════════════════════════
يُحلّل نص العقد ويُقدّر نوعه الأقرب من الأنواع الستة.
يُستخدم للتحقق من توافق الاختيار اليدوي مع محتوى الملف.

إذا اختار المستخدم "عقد دولي" لكن الملف يحتوي على "عقد إيجار"،
يُظهر النظام تحذيراً واضحاً.
═══════════════════════════════════════════════════════════════
"""

import re
from dataclasses import dataclass


# ══════════════════════════════════════════════════════════
#  مؤشرات كل نوع عقد
# ══════════════════════════════════════════════════════════
#  كل نوع له قائمة كلمات/عبارات مميزة له
#  الوزن = عدد مرات الظهور × وزن الكلمة
# ══════════════════════════════════════════════════════════

_INDICATORS: dict[str, list[tuple[str, float]]] = {
    "🌐  العقد الدولي": [
        ("دولي", 3.0), ("دولية", 3.0), ("international", 3.0),
        ("تحكيم", 2.5), ("التحكيم", 2.5), ("arbitration", 2.5),
        ("القانون الواجب", 2.0), ("governing law", 2.0),
        ("العملة", 1.5), ("currency", 1.5), ("دولار", 1.5), ("يورو", 1.5),
        ("جمركية", 1.5), ("customs", 1.5), ("تصدير", 1.5), ("استيراد", 1.5),
        ("اتفاقية", 1.0), ("بلد", 1.0), ("جنسية", 1.0),
    ],
    "📋  البند العام": [
        ("أطراف العقد", 2.5), ("موضوع العقد", 2.5),
        ("اتفاقية عامة", 2.0), ("بنود العقد", 2.0),
        ("الشروط العامة", 1.5), ("أحكام عامة", 1.5),
        ("التزامات", 1.0), ("الجزاءات", 1.0),
    ],
    "🏢  عقد الشراكة التجارية": [
        ("شراكة", 3.0), ("شريك", 3.0), ("partnership", 3.0),
        ("حصة", 2.5), ("ملكية", 2.5), ("نسبة", 2.0),
        ("أرباح", 2.0), ("خسائر", 2.0), ("رأس المال", 2.0),
        ("إدارة المشروع", 1.5), ("القرار", 1.5),
        ("انسحاب", 1.5), ("تقييم الشركة", 1.5),
    ],
    "💼  عقد الخدمات المهنية": [
        ("خدمات", 2.5), ("مهني", 2.5), ("استشارة", 2.5),
        ("مكتب", 2.0), ("مستشار", 2.0), ("أتعاب", 2.0),
        ("تسليم", 1.5), ("مخرجات", 1.5), ("مواصفات", 1.5),
        ("ملكية فكرية", 1.5), ("ضمان", 1.0), ("جودة", 1.0),
        ("مقاول", 1.0), ("مشروع", 1.0),
    ],
    "🏠  عقد الإيجار العقاري": [
        ("إيجار", 3.0), ("مستأجر", 3.0), ("مؤجر", 3.0), ("rental", 3.0),
        ("شقة", 2.5), ("عقار", 2.5), ("مسكن", 2.5), ("مكتب", 2.0),
        ("أجرة", 2.0), ("الوحدة السكنية", 2.0), ("مبنى", 1.5),
        ("ودية", 1.5), ("تأمين", 1.5), ("صيانة", 1.5),
        ("الطابق", 1.0), ("المساحة", 1.0), ("متر", 1.0),
    ],
    "👔  عقد العمل": [
        ("توظيف", 3.0), ("موظف", 3.0), ("عمل", 2.5), ("employment", 3.0),
        ("راتب", 2.5), ("أجر", 2.5), ("salary", 2.5),
        ("إجازة", 2.0), ("دوام", 2.0), ("ساعات العمل", 2.0),
        ("التأمين الاجتماعي", 2.0), ("نهاية الخدمة", 2.0),
        ("مسمى وظيفي", 2.0), ("قسم", 1.5), ("منصب", 1.5),
        ("تدريب", 1.0), ("ترقية", 1.0),
    ],
}


# ══════════════════════════════════════════════════════════
#  نتيجة الكشف
# ══════════════════════════════════════════════════════════
@dataclass
class DetectResult:
    detected_type:   str            # النوع المُكتشف
    confidence:      float          # 0.0 – 1.0
    scores:          dict           # نقاط كل نوع
    is_mismatch:     bool           # هل يختلف عن الاختيار؟
    warning_msg:     str            # رسالة التحذير (فارغة إذا لا يوجد)
    suggestion:      str            # الاقتراح للمستخدم


# ══════════════════════════════════════════════════════════
#  الكشف
# ══════════════════════════════════════════════════════════
def detect_contract_type(text: str) -> DetectResult:
    """
    يُحلّل نص العقد ويُعيد أقرب نوع مع درجة الثقة.
    """
    text_lower = text.lower()
    scores: dict[str, float] = {}

    for ctype, indicators in _INDICATORS.items():
        score = 0.0
        for phrase, weight in indicators:
            # عدد مرات الظهور × الوزن
            count = len(re.findall(re.escape(phrase.lower()), text_lower))
            score += count * weight
        scores[ctype] = round(score, 2)

    if not any(scores.values()):
        # لم يُكتشف شيء
        return DetectResult(
            detected_type="غير محدد",
            confidence=0.0,
            scores=scores,
            is_mismatch=False,
            warning_msg="",
            suggestion="",
        )

    # ترتيب النتائج
    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    best_type, best_score = sorted_scores[0]
    second_score = sorted_scores[1][1] if len(sorted_scores) > 1 else 0

    # حساب الثقة النسبية
    total = sum(scores.values()) or 1
    confidence = min(best_score / total, 1.0)

    # إذا كانت الفجوة بين الأول والثاني صغيرة → ثقة منخفضة
    if second_score > 0 and (best_score - second_score) < best_score * 0.3:
        confidence *= 0.7

    return DetectResult(
        detected_type=best_type,
        confidence=round(confidence, 2),
        scores=scores,
        is_mismatch=False,
        warning_msg="",
        suggestion="",
    )


def check_mismatch(text: str, selected_type: str) -> DetectResult:
    """
    يتحقق من توافق النوع المختار مع محتوى الملف.
    إذا وجد تعارضاً يُعيد تحذيراً.

    selected_type: النوع الذي اختاره المستخدم (مثل "🌐  العقد الدولي")
    """
    result = detect_contract_type(text)

    # إذا كانت الثقة منخفضة → لا نحكم
    if result.confidence < 0.15:
        result.is_mismatch = False
        return result

    # هل يختلف المُكتشف عن المختار؟
    if result.detected_type != selected_type and result.detected_type != "غير محدد":
        result.is_mismatch = True

        # رتّب النوعين للعرض بشكل مقروء
        sel_short = selected_type.split("  ")[-1] if "  " in selected_type else selected_type
        det_short = result.detected_type.split("  ")[-1] if "  " in result.detected_type else result.detected_type
        conf_pct  = int(result.confidence * 100)

        result.warning_msg = (
            f"⚠  تحذير: النوع المختار «{sel_short}» لا يتطابق مع محتوى الملف.\n"
            f"يبدو أن هذا الملف «{det_short}» بنسبة ثقة {conf_pct}%."
        )
        result.suggestion = (
            f"يُنصح باختيار «{det_short}» للحصول على تحليل دقيق.\n"
            f"هل تريد الاستمرار بـ «{sel_short}» رغم ذلك؟"
        )

    return result


def get_top_suggestions(text: str, top_n: int = 3) -> list[tuple[str, float]]:
    """
    يُعيد أفضل top_n أنواع عقود مع نسب ثقتها.
    """
    result = detect_contract_type(text)
    sorted_s = sorted(result.scores.items(), key=lambda x: x[1], reverse=True)
    total = sum(result.scores.values()) or 1
    return [
        (ctype, round(score / total, 2))
        for ctype, score in sorted_s[:top_n]
        if score > 0
    ]