"""
clause_matcher.py  —  مطابقة البنود بالمعنى لا بالنص الحرفي
═══════════════════════════════════════════════════════════════
وضعان:
  1. TF-IDF (افتراضي — يعمل بدون تثبيت إضافي)
     يحسب التشابه الدلالي باستخدام مصفوفة TF-IDF + cosine similarity
     دقة جيدة للعربية دون الحاجة لنماذج ضخمة.

  2. sentence-transformers (اختياري — دقة أعلى)
     نموذج paraphrase-multilingual-MiniLM-L12-v2
     يفهم المعنى الحقيقي للجمل متعددة اللغات.

الاستخدام:
  from clause_matcher import match_clause, init_matcher
  init_matcher(mode="tfidf")   # أو "transformers"
  result = match_clause("مدة الإيجار", expected_list)
═══════════════════════════════════════════════════════════════
"""

import re
from typing import Optional

# ── مكتبات TF-IDF ────────────────────────────────────────
try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    import numpy as np
    _HAS_SKLEARN = True
except ImportError:
    _HAS_SKLEARN = False

# ── مكتبات sentence-transformers ─────────────────────────
try:
    from sentence_transformers import SentenceTransformer
    _HAS_TRANSFORMERS = True
except ImportError:
    _HAS_TRANSFORMERS = False


# ══════════════════════════════════════════════════════════
#  الحالة الداخلية للـ matcher
# ══════════════════════════════════════════════════════════
_mode:        str                            = "tfidf"
_model:       Optional["SentenceTransformer"] = None
_model_loaded: bool                          = False

# حد التشابه الأدنى للقبول
_MIN_TFIDF       = 0.12   # TF-IDF أكثر تحفظاً
_MIN_TRANSFORMERS = 0.40   # transformers أكثر ثقة بالنتائج


# ══════════════════════════════════════════════════════════
#  مرادفات مساعدة — تُعزّز TF-IDF للمصطلحات الفقهية
# ══════════════════════════════════════════════════════════
_SYNONYMS: dict[str, list[str]] = {
    # مصطلحات الوقت والمدة
    "مدة العقد":       ["فترة التعاقد","مدة الاتفاقية","سريان العقد","مدة التعاقد"],
    "مدة الإيجار":     ["فترة الإيجار","مدة الاستئجار","فترة السكن","مدة التأجير"],
    "تجديد العقد":     ["مد العقد","تمديد الاتفاقية","استمرار التعاقد"],
    # مصطلحات المال
    "شروط الدفع":      ["آلية السداد","طريقة الدفع","موعد الدفع","شروط السداد"],
    "الأتعاب":         ["المكافأة","الأجر","الراتب","قيمة الخدمة","التعويض المالي"],
    "قيمة الإيجار":    ["الأجرة","مبلغ الإيجار","الإيجار الشهري","بدل الإيجار"],
    # الأطراف
    "أطراف العقد":     ["المتعاقدون","أصحاب العقد","الأطراف المتعاقدة"],
    "الطرف الأول":     ["المؤجر","البائع","الموكل","المقاول","المعيّن"],
    "الطرف الثاني":    ["المستأجر","المشتري","الوكيل","المقاول الفرعي"],
    # الإنهاء
    "الإنهاء والفسخ":  ["إنهاء التعاقد","فسخ الاتفاقية","إلغاء العقد","إنهاء مبكر"],
    # السرية
    "السرية":          ["عدم الإفصاح","الحفاظ على السر","سرية المعلومات"],
    # النزاعات
    "آلية حل النزاعات":["تسوية الخلافات","فض النزاعات","حل الخلافات","التحكيم"],
    # الملكية
    "الملكية الفكرية": ["حقوق التأليف","براءات الاختراع","حقوق النشر"],
    # العقارات
    "وصف العقار":      ["بيانات العقار","تفاصيل الشقة","مواصفات المكتب","موقع العقار"],
    "الصيانة":         ["الإصلاح","الترميم","صيانة العقار","متطلبات الصيانة"],
    # التوظيف
    "المسمى الوظيفي":  ["طبيعة العمل","وصف الوظيفة","مهام الوظيفة","طبيعة المهمة"],
    "الراتب والمزايا": ["الأجر والمنافع","التعويض والمزايا","الراتب الشهري"],
}


def _expand_with_synonyms(text: str) -> str:
    """يُضيف المرادفات لتعزيز التمثيل الدلالي."""
    extra = []
    for key, syns in _SYNONYMS.items():
        if key in text:
            extra.extend(syns)
        for s in syns:
            if s in text:
                extra.append(key)
    return text + " " + " ".join(extra)


# ══════════════════════════════════════════════════════════
#  تهيئة الـ matcher
# ══════════════════════════════════════════════════════════
def init_matcher(mode: str = "tfidf") -> str:
    """
    يُهيّئ الـ matcher.
    mode: "tfidf" | "transformers"
    يُعيد الوضع الفعلي المُستخدم.
    """
    global _mode, _model, _model_loaded

    if mode == "transformers":
        if _HAS_TRANSFORMERS:
            if not _model_loaded:
                try:
                    _model = SentenceTransformer(
                        "paraphrase-multilingual-MiniLM-L12-v2"
                    )
                    _model_loaded = True
                    _mode = "transformers"
                    print("[clause_matcher] ✓ sentence-transformers جاهز")
                except Exception as e:
                    print(f"[clause_matcher] ✗ فشل تحميل النموذج: {e}")
                    print("[clause_matcher] → تراجع لـ TF-IDF")
                    _mode = "tfidf"
            else:
                _mode = "transformers"
        else:
            print("[clause_matcher] ✗ sentence-transformers غير مثبّت")
            print("  pip install sentence-transformers")
            print("[clause_matcher] → يُستخدم TF-IDF")
            _mode = "tfidf"
    else:
        _mode = "tfidf"
        if not _HAS_SKLEARN:
            print("[clause_matcher] ✗ scikit-learn غير مثبّت")
            print("  pip install scikit-learn")
            _mode = "fallback"

    return _mode


# ══════════════════════════════════════════════════════════
#  مطابقة بـ TF-IDF
# ══════════════════════════════════════════════════════════
def _match_tfidf(heading: str, candidates: list[str]) -> Optional[str]:
    """
    يُطابق عنوان مع قائمة البنود المتوقعة باستخدام TF-IDF.
    يُراعي المرادفات والمصطلحات المترادفة.
    """
    if not _HAS_SKLEARN or not candidates:
        return _match_fallback(heading, candidates)

    # تنظيف وتوسيع النصوص
    h_expanded = _expand_with_synonyms(heading.lower())
    c_expanded  = [_expand_with_synonyms(c.lower()) for c in candidates]

    corpus = [h_expanded] + c_expanded

    try:
        vec = TfidfVectorizer(
            analyzer="char_wb",      # n-grams على مستوى الأحرف — أفضل للعربية
            ngram_range=(2, 4),
            min_df=1,
            sublinear_tf=True,
        )
        tfidf_matrix = vec.fit_transform(corpus)
        sims = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:]).flatten()

        best_idx   = int(np.argmax(sims))
        best_score = float(sims[best_idx])

        if best_score >= _MIN_TFIDF:
            return candidates[best_idx]
        return None

    except Exception as e:
        print(f"[clause_matcher] TF-IDF خطأ: {e}")
        return _match_fallback(heading, candidates)


# ══════════════════════════════════════════════════════════
#  مطابقة بـ sentence-transformers
# ══════════════════════════════════════════════════════════
def _match_transformers(heading: str, candidates: list[str]) -> Optional[str]:
    """
    يُطابق عنوان مع قائمة البنود باستخدام embeddings دلالية.
    دقة أعلى لكن أبطأ عند أول استخدام.
    """
    if not _model or not candidates:
        return _match_tfidf(heading, candidates)

    try:
        import numpy as np
        texts   = [heading] + candidates
        embeds  = _model.encode(texts, normalize_embeddings=True)
        sims    = embeds[0] @ embeds[1:].T      # dot product = cosine (بعد التطبيع)

        best_idx   = int(np.argmax(sims))
        best_score = float(sims[best_idx])

        if best_score >= _MIN_TRANSFORMERS:
            return candidates[best_idx]
        return None

    except Exception as e:
        print(f"[clause_matcher] Transformers خطأ: {e}")
        return _match_tfidf(heading, candidates)


# ══════════════════════════════════════════════════════════
#  مطابقة احتياطية بالنقاط (من الكود الأصلي — معززة)
# ══════════════════════════════════════════════════════════
_COMMON_WORDS = {
    'العقد','هذا','من','في','على','إلى','بين','عن','كل','ما',
    'وأن','أن','أو','عند','لا','يتم','مدى','لكل','حق','كما',
    'عبر','هذه','ذلك','تلك','التي','الذي','مع','حيث','قد',
}

_CLAUSE_KEYWORDS: dict[str, list[str]] = {
    "القانون الواجب التطبيق":    ["القانون","التطبيق","قانون","القوانين"],
    "الاختصاص القضائي":         ["الاختصاص","القضائي","محكمة","قضائي"],
    "التحكيم الدولي":            ["التحكيم","تحكيم"],
    "اللغة المعتمدة":            ["اللغة","لغة","معتمدة"],
    "آلية حل النزاعات":          ["النزاعات","نزاع","حل","تسوية"],
    "القوة القاهرة":              ["القوة","قاهرة","استثنائية"],
    "السرية والحماية الدولية":   ["السرية","سرية","حماية"],
    "شروط التسليم":              ["التسليم","تسليم","توريد"],
    "العملة وآلية السداد":       ["الدفع","السداد","عملة"],
    "الضرائب والرسوم الجمركية":  ["الضرائب","جمركية","رسوم"],
    "أطراف العقد":               ["الأطراف","أطراف","طرف","تعريف"],
    "موضوع العقد":               ["موضوع","الموضوع","غرض","هدف"],
    "مدة العقد":                 ["المدة","مدة","سنوات","تجديد"],
    "شروط الدفع":                ["الدفع","دفع","السداد","فاتورة"],
    "التزامات الأطراف":          ["المسؤوليات","الالتزامات","مسؤوليات"],
    "الإنهاء والفسخ":            ["الإنهاء","فسخ","إنهاء"],
    "الجزاءات والتعويضات":       ["الجزاءات","التعويضات","العقوبات","إخلال"],
    "السرية":                    ["السرية","سرية","إفصاح","سري"],
    "نسب الملكية والحصص":        ["ملكية","حصص","نسبة","حصة"],
    "توزيع الأرباح والخسائر":    ["أرباح","خسائر","توزيع"],
    "إدارة المشروع":              ["إدارة","مشروع"],
    "صنع القرار":                 ["قرار","اتخاذ"],
    "حقوق وواجبات الشركاء":      ["شركاء","شريك","حقوق","واجبات"],
    "انسحاب الشريك":             ["انسحاب","خروج","تنازل"],
    "حق الأولوية":                ["أولوية","أفضلية"],
    "تقييم الشركة":               ["تقييم","تثمين"],
    "السرية التجارية":            ["السرية","تجارية","سر"],
    "نطاق الخدمات":               ["الخدمات","نطاق","خدمة"],
    "جدول التسليمات":             ["التسليمات","مخرجات"],
    "معايير الجودة":              ["الجودة","جودة","مواصفات"],
    "الأتعاب والسداد":            ["الأتعاب","أتعاب","مكافأة"],
    "الملكية الفكرية":            ["الملكية","فكرية","براءة"],
    "السرية وحماية البيانات":    ["السرية","سرية","بيانات","حماية"],
    "تغيير نطاق العمل":           ["تغيير","نطاق","تعديل"],
    "الضمان والعيوب":             ["الضمان","عيوب","ضمان"],
    "تعارض المصالح":              ["تعارض","مصالح","منافس"],
    "المقاولون من الباطن":        ["مقاول","باطن"],
    "وصف العقار":                 ["العقار","عقار","شقة","مكتب"],
    "مدة الإيجار":                ["الإيجار","إيجار","مدة"],
    "قيمة الإيجار":               ["الإيجار","أجرة","قيمة"],
    "التأمين والضمانات":          ["التأمين","تأمين","كفالة"],
    "الصيانة والإصلاح":           ["الصيانة","إصلاح"],
    "شروط الإنهاء":               ["الإنهاء","إنهاء","فسخ"],
    "استخدام العقار":             ["استخدام","الغرض"],
    "التحسينات والتعديلات":       ["تحسينات","تعديلات","ترميم"],
    "التأمين على العقار":         ["التأمين","تأمين"],
    "الرسوم والفواتير":           ["الرسوم","فواتير"],
    "المسمى الوظيفي والمهام":     ["وظيفي","مهام","منصب"],
    "الراتب والمزايا":            ["الراتب","مزايا","أجر"],
    "ساعات العمل":                ["ساعات","دوام"],
    "الإجازات":                   ["الإجازات","إجازة","عطلة"],
    "التدريب والتطوير":           ["التدريب","تطوير","تأهيل"],
    "السرية وعدم المنافسة":       ["السرية","منافسة"],
    "إنهاء العقد":                ["الإنهاء","إنهاء","فسخ"],
    "السلوك المهني":              ["السلوك","مهني","انضباط"],
    "حل النزاعات العمالية":       ["النزاعات","نزاع","عمالية"],
    "الملكية الفكرية للموظف":     ["الملكية","فكرية","موظف"],
}


def _match_fallback(heading: str, candidates: list[str]) -> Optional[str]:
    """
    مطابقة بالنقاط — fallback عند غياب sklearn.
    معززة بالمرادفات.
    """
    h_raw    = heading.lower().strip()
    h_clean  = re.sub(r'^\d+[\.\-\)]\s*', '', h_raw).strip()
    h_bare   = re.sub(r'^بند\s+', '', h_clean).strip()
    h_bare_ns = re.sub(r'\s+', '', h_bare)
    h_words  = {w for w in h_clean.split() if w not in _COMMON_WORDS and len(w) > 2}

    # إضافة مرادفات لكلمات العنوان
    extra_words = set()
    for word in list(h_words):
        for key, syns in _SYNONYMS.items():
            if word in key.lower():
                extra_words.update(key.lower().split())
            for s in syns:
                if word in s.lower():
                    extra_words.update(s.lower().split())
    h_words.update(extra_words)

    best_match, best_score = None, 0
    for exp in candidates:
        kws   = _CLAUSE_KEYWORDS.get(exp, [w for w in exp.split() if len(w) > 2])
        # أضف مرادفات البند المتوقع
        for key, syns in _SYNONYMS.items():
            if exp == key:
                kws = kws + [w for s in syns for w in s.split()]
        score = 0
        for kw in kws:
            kw_l  = kw.lower()
            kw_ns = re.sub(r'\s+', '', kw_l)
            if kw_l in h_words:
                score += len(kw_l) * 2
            elif kw_ns in h_bare_ns:
                score += len(kw_l)
            elif kw_l in h_bare or kw_l in h_clean:
                score += len(kw_l)
        if score > best_score:
            best_score = score
            best_match = exp

    return best_match if best_score >= 6 else None


# ══════════════════════════════════════════════════════════
#  الدالة الرئيسية العامة
# ══════════════════════════════════════════════════════════
def match_clause(heading: str, expected_list: list[str]) -> Optional[str]:
    """
    يُطابق عنوان بند مع أقرب بند في القائمة المتوقعة.
    يستخدم الوضع المُهيَّأ (TF-IDF أو transformers أو fallback).

    لا تُخلط نتائج أنواع مختلفة — يُعيد None إذا لم يجد تشابهاً كافياً.
    """
    if not heading.strip() or not expected_list:
        return None

    if _mode == "transformers" and _model_loaded:
        return _match_transformers(heading, expected_list)
    elif _mode == "tfidf" and _HAS_SKLEARN:
        return _match_tfidf(heading, expected_list)
    else:
        return _match_fallback(heading, expected_list)


def get_mode() -> str:
    """يُعيد الوضع الحالي للـ matcher."""
    return _mode


# ── تهيئة تلقائية عند الاستيراد ───────────────────────
init_matcher("tfidf")