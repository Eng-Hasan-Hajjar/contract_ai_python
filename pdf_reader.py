"""
pdf_reader.py  —  قراءة ملفات PDF بشكل موثوق
═══════════════════════════════════════════════════════════════
يدعم:
  1. PDF نصي عادي       → pdfplumber
  2. PDF صور ممسوحة     → pytesseract + Pillow (OCR)
  3. PDF مختلط         → يكتشف تلقائياً ويختار الأفضل

يُعيد دائماً نتيجة واضحة مع رسالة حالة للمستخدم.

لا يعود أبداً لبيانات وهمية (demo).
═══════════════════════════════════════════════════════════════
"""

import re
import os
from dataclasses import dataclass, field
from typing import Optional

# ── اختبار المكتبات ──────────────────────────────────────
try:
    import pdfplumber
    _HAS_PDFPLUMBER = True
except ImportError:
    _HAS_PDFPLUMBER = False

try:
    from PIL import Image
    import pytesseract
    _HAS_OCR = True
except ImportError:
    _HAS_OCR = False


# ══════════════════════════════════════════════════════════
#  نتيجة القراءة
# ══════════════════════════════════════════════════════════
@dataclass
class ReadResult:
    """نتيجة قراءة ملف PDF."""
    text:       str       = ""
    pages:      int       = 0
    method:     str       = ""    # "pdfplumber" | "ocr" | "mixed" | "failed"
    ok:         bool      = False
    error:      str       = ""
    warnings:   list[str] = field(default_factory=list)


# ══════════════════════════════════════════════════════════
#  تصحيح النص العربي المعكوس (Visual-RTL)
# ══════════════════════════════════════════════════════════
def _is_reversed(s: str) -> bool:
    if not s:
        return False
    if re.search(r'\d[\.\:]$', s):
        return True
    if s[0] in '.،؛:؟!':
        return True
    if re.match(r'^\d+[\.\-\)]\s', s[::-1]):
        return True
    if re.search(r'[\u0600-\u06FF]', s) and '\u0600' <= s[0] <= '\u06FF':
        return True
    return False


def fix_line(line: str) -> str:
    """يُصحّح سطراً عربياً معكوساً من PDF Visual-RTL."""
    s = line.strip()
    if not s or not _is_reversed(s):
        return line
    rev = s[::-1]
    rev = re.sub(r'^\.(\d+)', r'\1.', rev)
    rev = re.sub(r'^(\d+\.)(\S)', r'\1 \2', rev)
    rev = re.sub(r'\d{2,4}', lambda m: m.group(0)[::-1], rev)
    return re.sub(r'  +', ' ', rev).strip()


def fix_arabic(text: str) -> str:
    """يُصحّح النص العربي المعكوس سطراً سطراً."""
    if not text:
        return text
    return "\n".join(fix_line(ln) for ln in text.split("\n"))


# ══════════════════════════════════════════════════════════
#  قراءة النص من صفحة pdfplumber
# ══════════════════════════════════════════════════════════
def _text_from_page(page) -> str:
    """يستخرج النص من صفحة واحدة."""
    try:
        raw = page.extract_text() or ""
        return fix_arabic(raw)
    except Exception:
        return ""


def _is_scanned_page(page, text: str) -> bool:
    """
    يُقدّر إذا كانت الصفحة صورة ممسوحة بدون نص قابل للاستخراج.
    معيار: نص أقل من 20 حرفاً رغم وجود صور في الصفحة.
    """
    if len(text.strip()) >= 20:
        return False
    try:
        images = page.images
        return len(images) > 0
    except Exception:
        return False


# ══════════════════════════════════════════════════════════
#  OCR على صفحة ممسوحة
# ══════════════════════════════════════════════════════════
def _ocr_page(page, dpi: int = 200) -> str:
    """
    يحوّل صفحة PDF إلى صورة ثم يُطبّق OCR عليها.
    يُعيد النص المستخرج أو نصاً فارغاً عند الفشل.
    """
    if not _HAS_OCR:
        return ""
    try:
        # تحويل الصفحة إلى صورة
        img = page.to_image(resolution=dpi).original
        # OCR باللغتين العربية والإنجليزية
        text = pytesseract.image_to_string(
            img,
            lang="ara+eng",
            config="--psm 6 --oem 3"
        )
        return fix_arabic(text)
    except Exception as e:
        return ""


# ══════════════════════════════════════════════════════════
#  الدالة الرئيسية
# ══════════════════════════════════════════════════════════
def read_pdf(path: str, ocr_enabled: bool = True) -> ReadResult:
    """
    يقرأ ملف PDF ويُعيد النص الكامل مع معلومات الحالة.

    المنطق:
    ┌──────────────────────────────────────────────────────┐
    │ 1. تحقق من وجود الملف                               │
    │ 2. افتح بـ pdfplumber                               │
    │ 3. لكل صفحة:                                        │
    │    • استخرج النص النصي                              │
    │    • إذا فارغة وفيها صور → جرّب OCR               │
    │ 4. أعد النص الكامل مع تقرير الحالة                 │
    └──────────────────────────────────────────────────────┘

    يُعيد: ReadResult مع .ok=False ورسالة .error واضحة
           عند أي فشل — لا بيانات وهمية أبداً.
    """
    result = ReadResult()

    # ── 1. التحقق من الملف ──────────────────────────────
    if not path:
        result.error = "لم يُحدَّد مسار الملف."
        return result

    if not os.path.exists(path):
        result.error = f"الملف غير موجود:\n{path}"
        return result

    if not path.lower().endswith(".pdf"):
        result.error = "الملف المحدد ليس بصيغة PDF."
        return result

    size_mb = os.path.getsize(path) / (1024 * 1024)
    if size_mb > 100:
        result.warnings.append(f"الملف كبير ({size_mb:.1f} MB) — قد يستغرق التحليل وقتاً.")

    # ── 2. التحقق من pdfplumber ─────────────────────────
    if not _HAS_PDFPLUMBER:
        result.error = (
            "مكتبة pdfplumber غير مثبّتة.\n"
            "لتثبيتها: pip install pdfplumber"
        )
        return result

    # ── 3. فتح الملف واستخراج النص ─────────────────────
    all_pages_text = []
    pdfplumber_ok  = False
    ocr_pages      = 0
    text_pages     = 0

    try:
        with pdfplumber.open(path) as pdf:
            result.pages = len(pdf.pages)
            pdfplumber_ok = True

            for pnum, page in enumerate(pdf.pages, 1):
                # استخراج النص النصي
                page_text = _text_from_page(page)

                # إذا كانت الصفحة ممسوحة → OCR
                if _is_scanned_page(page, page_text):
                    if ocr_enabled and _HAS_OCR:
                        ocr_text = _ocr_page(page)
                        if ocr_text.strip():
                            page_text = ocr_text
                            ocr_pages += 1
                        else:
                            result.warnings.append(
                                f"ص{pnum}: صورة ممسوحة — فشل OCR في استخراج نص.")
                    elif ocr_enabled and not _HAS_OCR:
                        result.warnings.append(
                            f"ص{pnum}: صورة ممسوحة — OCR غير متوفر "
                            f"(pip install pytesseract pillow).")
                    else:
                        result.warnings.append(
                            f"ص{pnum}: صورة ممسوحة — OCR مُعطَّل.")
                else:
                    if page_text.strip():
                        text_pages += 1

                all_pages_text.append(page_text)

    except Exception as e:
        err_msg = str(e)
        # ترجمة أخطاء شائعة لرسائل مفهومة
        if "password" in err_msg.lower() or "encrypt" in err_msg.lower():
            result.error = "الملف محمي بكلمة مرور — لا يمكن قراءته."
        elif "invalid" in err_msg.lower() or "corrupt" in err_msg.lower():
            result.error = "الملف تالف أو غير صالح."
        elif "permission" in err_msg.lower():
            result.error = "لا توجد صلاحية لفتح الملف."
        else:
            result.error = f"خطأ في فتح الملف:\n{err_msg}"
        return result

    # ── 4. تجميع النتائج ────────────────────────────────
    full_text = "\n".join(all_pages_text)

    if not full_text.strip():
        result.error = (
            "لم يُستخرج أي نص من الملف.\n"
            "• إذا كان الملف صوراً ممسوحة، تأكد من تثبيت pytesseract.\n"
            "• إذا كان الملف مشفراً، أزل الحماية أولاً."
        )
        return result

    # تحديد الطريقة
    if ocr_pages > 0 and text_pages > 0:
        result.method = "mixed"
    elif ocr_pages > 0:
        result.method = "ocr"
    else:
        result.method = "pdfplumber"

    if ocr_pages > 0:
        result.warnings.append(
            f"{ocr_pages} صفحة استُخرجت بـ OCR (قد تحتوي على أخطاء إملائية).")

    result.text = full_text
    result.ok   = True
    return result


# ══════════════════════════════════════════════════════════
#  اكتشاف العناوين المُحسَّن
# ══════════════════════════════════════════════════════════
_HEADING_KEYWORDS = [
    "البند","المادة","الفصل","القسم","الملحق","الجدول","الشرط",
    "أولاً","ثانياً","ثالثاً","رابعاً","خامساً","سادساً",
    "سابعاً","ثامناً","تاسعاً","عاشراً",
    "الأطراف","التعريفات","الموضوع","المدة","الدفع","السداد",
    "الالتزامات","المسؤوليات","الإنهاء","الفسخ","الجزاءات",
    "التعويضات","السرية","النزاعات","التحكيم","القانون",
    "الضمانات","الملكية","الإيجار","الراتب","التأمين",
    "الصيانة","التسليم","الجودة","الخدمات","الشراكة",
    "التوزيع","الأرباح","الخسائر","الانسحاب",
]

# أنماط تدل على نهاية بند معروف داخل السطر
_INLINE_CLAUSE_RE = re.compile(
    r'(?:^|[،.]\s*)('
    + '|'.join(re.escape(kw) for kw in _HEADING_KEYWORDS)
    + r')\s*[:\-]?\s*',
    re.UNICODE
)


def is_heading(line: str) -> bool:
    """يكتشف إذا كان السطر عنوان بند."""
    line = line.strip()
    if not line or len(line) < 3:
        return False
    # رقم + نقطة في البداية
    if re.match(r'^[١٢٣٤٥٦٧٨٩٠\d]+[\.\-\)\:]\s+\S', line):
        return True
    # Article / Section / Clause
    if re.match(r'^(Article|Section|Clause|Chapter)\s+[\dIVX]+', line, re.I):
        return True
    # كلمة مفتاحية في بداية السطر + طول مناسب
    for kw in _HEADING_KEYWORDS:
        if line.startswith(kw) and len(line) < 70:
            return True
    # أحرف كبيرة كلياً
    if line.isupper() and 5 < len(line) < 80:
        return True
    return False


def extract_inline_clauses(text: str) -> list[str]:
    """
    يُستخرج البنود المضمّنة في منتصف السطر.
    مثال: "...الدفع المذكور أعلاه مدة العقد ثلاثة أشهر..."
    يستخرج: ["مدة العقد ثلاثة أشهر"]
    """
    clauses = []
    for match in _INLINE_CLAUSE_RE.finditer(text):
        start = match.start(1)
        # خذ 60 حرف من بداية الكلمة المفتاحية
        snippet = text[start: start + 60].split("\n")[0].strip()
        if len(snippet) > 5:
            clauses.append(snippet)
    return clauses


def extract_headings(path: str, ocr_enabled: bool = True) -> tuple[str, list[dict]]:
    """
    الدالة الرئيسية: يستخرج العناوين من PDF.
    يُعيد: (full_text, headings_list)
    يرفع ValueError برسالة واضحة عند الفشل.
    """
    result = read_pdf(path, ocr_enabled=ocr_enabled)

    if not result.ok:
        raise ValueError(result.error)

    # اكتشاف العناوين
    heads = []
    for pnum, page_text in enumerate(result.text.split("\f") or [result.text], 1):
        for line in page_text.split("\n"):
            line_s = line.strip()
            if line_s and is_heading(line_s):
                heads.append({
                    "title": line_s[:100],
                    "page":  pnum,
                    "bold":  len(line_s) < 60,
                    "inline": False,
                })
            # البحث عن عناوين مضمّنة
            inline = extract_inline_clauses(line_s)
            for snippet in inline:
                if not any(h["title"][:30] == snippet[:30] for h in heads):
                    heads.append({
                        "title":  snippet[:100],
                        "page":   pnum,
                        "bold":   False,
                        "inline": True,
                    })

    # إزالة مكررات
    seen, unique = set(), []
    for h in heads:
        k = re.sub(r'\s+', ' ', h["title"])[:50]
        if k and k not in seen:
            seen.add(k)
            unique.append(h)

    # تحذيرات
    for w in result.warnings:
        print(f"[pdf_reader] ⚠ {w}")

    return result.text, unique