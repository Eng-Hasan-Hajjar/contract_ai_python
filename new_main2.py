"""
╔══════════════════════════════════════════════════════════════════╗
║      نظام تحليل العقود التجارية  –  الإصدار 4.0               ║
║      مشروع تخرج  |  تحليل ذكي بـ TF-IDF + كاشف نوع العقد     ║
║      OCR للصور  |  تكبير/تصغير  |  حفظ الإعدادات              ║
╚══════════════════════════════════════════════════════════════════╝
  pip install customtkinter pdfplumber scikit-learn
  (pytesseract pillow: اختياري للـ OCR)
  (sentence-transformers: اختياري للدقة العالية)
"""

import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
import threading, time, os, re
from datetime import datetime

# ── قاعدة البيانات والمصادقة ─────────────────────────────────
from database import init_db, save_analysis, get_user_history, get_user_stats
from auth import show_login

# ── الملفات الجديدة ───────────────────────────────────────────
import config
from pdf_reader        import extract_headings as _extract_pdf
from clause_matcher    import match_clause, init_matcher, get_mode
from contract_detector import check_mismatch
from font_manager      import FontManager, ZoomBar
from image_analyzer    import ImageAnalysisView

# تهيئة المطابقة الذكية بالوضع المحفوظ
_matcher_mode = config.get("matcher_mode") or "tfidf"
init_matcher(_matcher_mode)

# مدير الخطوط الديناميكي
FM = FontManager()


AI_OK = False   # Claude API محذوف — النظام يعمل بالقواعد الذكية

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors as RC
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import (SimpleDocTemplate, Paragraph,
                                    Spacer, Table, TableStyle, HRFlowable)
    from reportlab.lib.units import cm
    RL_OK = True
except ImportError:
    RL_OK = False

# ══════════════════════════════════════════════
#  الألوان
# ══════════════════════════════════════════════
C = {
    "bg":      "#080C18", "bg1":    "#0F1525", "bg2":    "#151D35",
    "bg3":     "#1C2640", "card":   "#111829", "border": "#1E2A45",
    "bhi":     "#2A3D6A", "blue":   "#2563EB", "blt":    "#3B82F6",
    "cyan":    "#06B6D4", "purple": "#7C3AED", "gold":   "#D97706",
    "green":   "#059669", "glt":    "#10B981", "red":    "#DC2626",
    "orange":  "#EA580C", "text":   "#F1F5FF", "t2":     "#94A3B8",
    "t3":      "#4B5E82", "white":  "#FFFFFF",
}

# ── الخطوط — تُدار بـ FontManager (F يُحدَّث عند الضغط +/-) ──
F = FM.F

# ══════════════════════════════════════════════
#  أنواع العقود وبنودها المعيارية
# ══════════════════════════════════════════════
CONTRACT_TYPES = {
    "🌐  العقد الدولي": {
        "color": C["blue"], "risk": "عالي",
        "clauses": [
            "القانون الواجب التطبيق",
            "الاختصاص القضائي",
            "التحكيم الدولي",
            "اللغة المعتمدة",
            "آلية حل النزاعات",
            "القوة القاهرة",
            "السرية والحماية الدولية",
            "شروط التسليم",
            "العملة وآلية السداد",
            "الضرائب والرسوم الجمركية",
        ],
    },
    "📋  البند العام": {
        "color": C["cyan"], "risk": "منخفض",
        "clauses": [
            "أطراف العقد",
            "موضوع العقد",
            "مدة العقد",
            "شروط الدفع",
            "التزامات الأطراف",
            "الإنهاء والفسخ",
            "الجزاءات والتعويضات",
            "السرية",
        ],
    },
    "🏢  عقد الشراكة التجارية": {
        "color": C["purple"], "risk": "عالي",
        "clauses": [
            "نسب الملكية والحصص",
            "توزيع الأرباح والخسائر",
            "إدارة المشروع",
            "صنع القرار",
            "حقوق وواجبات الشركاء",
            "انسحاب الشريك",
            "حل النزاعات",
            "السرية التجارية",
            "حق الأولوية",
            "تقييم الشركة",
        ],
    },
    "💼  عقد الخدمات المهنية": {
        "color": C["gold"], "risk": "متوسط",
        "clauses": [
            "نطاق الخدمات",
            "جدول التسليمات",
            "معايير الجودة",
            "الأتعاب والسداد",
            "الملكية الفكرية",
            "السرية وحماية البيانات",
            "تغيير نطاق العمل",
            "الضمان والعيوب",
            "تعارض المصالح",
            "المقاولون من الباطن",
        ],
    },
    "🏠  عقد الإيجار العقاري": {
        "color": C["glt"], "risk": "متوسط",
        "clauses": [
            "وصف العقار",
            "مدة الإيجار",
            "قيمة الإيجار",
            "التأمين والضمانات",
            "الصيانة والإصلاح",
            "شروط الإنهاء",
            "استخدام العقار",
            "التحسينات والتعديلات",
            "التأمين على العقار",
            "الرسوم والفواتير",
        ],
    },
    "👔  عقد العمل": {
        "color": C["orange"], "risk": "متوسط",
        "clauses": [
            "المسمى الوظيفي والمهام",
            "الراتب والمزايا",
            "ساعات العمل",
            "الإجازات",
            "التدريب والتطوير",
            "السرية وعدم المنافسة",
            "إنهاء العقد",
            "السلوك المهني",
            "حل النزاعات العمالية",
            "الملكية الفكرية للموظف",
        ],
    },
}

# ══════════════════════════════════════════════
#  حالة التطبيق
# ══════════════════════════════════════════════
class State:
    def reset(self):
        self.contract_type  = None
        self.pdf_path       = None
        self.raw_text       = ""
        self.found_headings = []
        self.result         = {}
    def __init__(self):
        self.reset()
        self.current_user   = None
        self.api_key        = config.get_api_key()   # تحميل من settings.json

ST = State()

# ══════════════════════════════════════════════════════════════
#  خوارزمية استخراج العناوين
# ══════════════════════════════════════════════════════════════
HEADING_KEYWORDS = [
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

def is_heading(line: str) -> bool:
    line = line.strip()
    if not line or len(line) < 4:
        return False
    if re.match(r'^[١٢٣٤٥٦٧٨٩٠\d]+[\.\-\)\:]\s+\S', line):
        return True
    if re.match(r'^(Article|Section|Clause|Chapter)\s+[\dIVX]+', line, re.I):
        return True
    # كلمة مفتاحية في البداية + السطر قصير (< 65 حرف)
    for kw in HEADING_KEYWORDS:
        if line.startswith(kw) and len(line) < 65:
            return True
    if line.isupper() and 5 < len(line) < 80:
        return True
    return False

def extract_headings(path: str):
    """
    يستخرج العناوين من PDF باستخدام pdf_reader المحسَّن.
    يدعم: PDF نصي + OCR للصور الممسوحة.
    يرفع ValueError برسالة واضحة عند الفشل (لا بيانات وهمية).
    """
    return _extract_pdf(path, ocr_enabled=config.get("ocr_enabled"))




# ══════════════════════════════════════════════════════════════
#  خوارزمية تقييم قوة العقد
# ══════════════════════════════════════════════════════════════
SUB_PATTERNS = [
    r'\d+[\.\-\)]\d+', r'[أ-ي]\)', r'[\u0660-\u0669]+[\.\-]', r'[-•\*]\s+\S',
]

def count_sub(text_block: str) -> int:
    return sum(len(re.findall(p, text_block)) for p in SUB_PATTERNS)




# match_clause مُوفَّرة من clause_matcher.py (TF-IDF + مرادفات)
# (الاستيراد في أعلى الملف)

def analyze_rules(headings: list, full_text: str, expected: list) -> dict:
    total = len(expected)
    found_map, missing = {}, []

    for h in headings:
        m = match_clause(h["title"], expected)
        if m and m not in found_map:
            found_map[m] = {
                "heading": h["title"],
                "page":    h["page"],
                "bold":    h.get("bold", False),
                "sub_count": 0,
                "strength": "ضعيف",
            }

    # حساب البنود الفرعية
    lines = full_text.split("\n")
    for clause_name, info in found_map.items():
        block, capture = "", False
        for line in lines:
            if info["heading"][:28] in line:
                capture = True
                continue
            if capture:
                if is_heading(line) and line.strip() != info["heading"].strip():
                    break
                block += line + "\n"
        sub = count_sub(block)
        info["sub_count"] = sub
        info["strength"] = (
            "قوي"    if sub >= 4 else
            "جيد"    if sub == 3 else
            "متوسط"  if sub == 2 else
            "مقبول"  if sub == 1 else
            "ضعيف"
        )

    for exp in expected:
        if exp not in found_map:
            missing.append(exp)

    # الدرجة
    max_score = total * (10 + 2 + 8) if total else 1
    raw = 0
    for info in found_map.values():
        raw += 10
        if info["bold"]: raw += 2
        sc = info["sub_count"]
        raw += (8 if sc>=4 else 5 if sc==3 else 3 if sc==2 else 1 if sc==1 else 0)

    score = min(round((raw / max_score) * 100), 100)

    if   score >= 80: level, lev_col = "قوي جداً",  C["glt"]
    elif score >= 65: level, lev_col = "جيد",       C["cyan"]
    elif score >= 50: level, lev_col = "متوسط",     C["gold"]
    elif score >= 35: level, lev_col = "ضعيف",      C["orange"]
    else:             level, lev_col = "ضعيف جداً", C["red"]

    risks = []
    if len(missing) > total * 0.4:
        risks.append({"title":"بنود أساسية مفقودة",
                       "desc":f"يفتقر العقد لـ {len(missing)} بنوداً من {total}",
                       "level":"عالي"})
    weak = [n for n,i in found_map.items() if i["strength"] in ("ضعيف","مقبول")]
    if weak:
        risks.append({"title":"بنود ذات تفصيل منخفض",
                       "desc":f"{len(weak)} بنود تحتاج تفصيلاً: " + "، ".join(weak[:3]),
                       "level":"متوسط"})
    non_bold = [n for n,i in found_map.items() if not i["bold"]]
    if len(non_bold) > len(found_map)*0.5:
        risks.append({"title":"عناوين غير بارزة",
                       "desc":"أكثر من نصف العناوين غير غامقة، مما يضعف وضوح الهيكل",
                       "level":"منخفض"})

    return {"score":score,"level":level,"level_color":lev_col,
            "found":found_map,"missing":missing,"risks":risks,
            "total_exp":total,"total_found":len(found_map)}




# ══════════════════════════════════════════════════════════════
#  مساعدات UI
# ══════════════════════════════════════════════════════════════
def sep(parent, color=None, h=1, padx=0, pady=6):
    ctk.CTkFrame(parent, fg_color=color or C["border"],
                 height=h, corner_radius=0).pack(fill="x", padx=padx, pady=pady)

def lbl(parent, text, font=None, color=None, anchor="w", **kw):
    return ctk.CTkLabel(parent, text=text,
                         font=font or F["body"],
                         text_color=color or C["text"],
                         anchor=anchor, **kw)

# ══════════════════════════════════════════════════════════════
#  شريط العنوان
# ══════════════════════════════════════════════════════════════
class TopBar(ctk.CTkFrame):
    def __init__(self, master, nav_cb, **kw):
        super().__init__(master, fg_color=C["bg1"], corner_radius=0, **kw)
        ctk.CTkFrame(self, fg_color=C["blue"], height=4, corner_radius=0).pack(fill="x")
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=12)

        ic = ctk.CTkFrame(row, fg_color=C["bg2"], corner_radius=12, width=52, height=52)
        ic.pack(side="left")
        ic.pack_propagate(False)
        ctk.CTkLabel(ic, text="⚖", font=("Arial",28), text_color=C["cyan"]
                     ).place(relx=.5, rely=.5, anchor="center")

        tb = ctk.CTkFrame(row, fg_color="transparent")
        tb.pack(side="left", padx=14)
        lbl(tb, "نظام تحليل العقود الذكي", F["heading"], C["text"]).pack(anchor="w")
        lbl(tb, "مشروع تخرج  •  تحليل بقواعد ذكية  •  v4.0", F["sm"], C["t3"]).pack(anchor="w")

        nav = ctk.CTkFrame(row, fg_color="transparent")
        nav.pack(side="right")
        for txt, view in [("🏠  الرئيسية","home"),("📊  التحليل","analysis"),
                          ("📋  سجلاتي","history"),("📄  التقرير","report")]:
            ctk.CTkButton(nav, text=txt, width=120, height=38,
                          fg_color="transparent", hover_color=C["bg3"],
                          text_color=C["t2"], border_width=1,
                          border_color=C["border"], corner_radius=10,
                          font=F["sm_b"],
                          command=lambda v=view: nav_cb(v)).pack(side="left", padx=5)

        # زر تسجيل الخروج
        ctk.CTkButton(nav, text="🚪  خروج", width=90, height=38,
                      fg_color="transparent", hover_color=C["red"],
                      text_color=C["t3"], border_width=1,
                      border_color=C["border"], corner_radius=10,
                      font=F["sm_b"],
                      command=lambda: nav_cb("logout")).pack(side="left", padx=(5,0))

        # ── شريط التكبير/التصغير ────────────────────────────────
        ZoomBar(row, FM).pack(side="right", padx=(0, 8))

        sb = ctk.CTkFrame(row, fg_color=C["bg2"], corner_radius=20,
                          border_width=1, border_color=C["glt"])
        sb.pack(side="right", padx=8)
        lbl(sb,"●",("Arial",10),C["glt"]).pack(side="left",padx=(10,4),pady=8)
        lbl(sb,"جاهز",F["sm_b"],C["glt"]).pack(side="left",padx=(0,12))

# ══════════════════════════════════════════════════════════════
#  اللوحة الجانبية
# ══════════════════════════════════════════════════════════════
class SidePanel(ctk.CTkFrame):
    STEPS = [
        ("١","اختيار نوع العقد",   "حدد طبيعة العلاقة التعاقدية"),
        ("٢","تحميل ملف PDF",      "ارفع ملف العقد"),
        ("٣","استخراج العناوين",   "كشف البنود تلقائياً"),
        ("٤","تقييم قوة العقد",    "درجة عبر خوارزمية ذكية"),
        ("٥","عرض التقرير",        "النتائج والتوصيات"),
    ]
    def __init__(self, master, **kw):
        super().__init__(master, fg_color=C["bg1"], corner_radius=0, width=265, **kw)
        self.pack_propagate(False)
        self._cards = []
        self._build()

    def _build(self):
        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=14, pady=16)
        lbl(inner,"مسار العمل",F["sm_b"],C["t3"]).pack(anchor="w",pady=(0,10))
        for num,title,desc in self.STEPS:
            c = self._make(inner,num,title,desc,False,False)
            c.pack(fill="x",pady=4)
            self._cards.append(c)
        sep(inner, C["border"], pady=12)



        tip = ctk.CTkFrame(inner, fg_color=C["bg2"], corner_radius=10,
                           border_width=1, border_color=C["bhi"])
        tip.pack(fill="x")
        lbl(tip,"💡  كيف يعمل النظام؟",F["sm_b"],C["gold"]).pack(anchor="w",padx=12,pady=(10,4))
        lbl(tip,
            "• يستخرج عناوين العقد\n"
            "• يكشف العناوين الغامقة\n"
            "• يقارن بالبنود المعيارية\n"
            "• يحسب قوة العقد تلقائياً\n"
            "• يعمل بدون إنترنت",
            F["xs"],C["t3"],justify="left").pack(anchor="w",padx=12,pady=(0,10))
        lbl(inner,"v4.0 – مشروع تخرج",F["xs"],C["t3"]).pack(side="bottom")

    def _make(self, parent, num, title, desc, active, done):
        col = C["blue"] if active else C["glt"] if done else C["t3"]
        fg  = C["bg2"]  if active else C["bg1"]
        bc  = C["blue"] if active else C["glt"] if done else C["border"]
        f = ctk.CTkFrame(parent, fg_color=fg, corner_radius=10,
                         border_width=1, border_color=bc)
        row = ctk.CTkFrame(f, fg_color="transparent")
        row.pack(fill="x", padx=12, pady=9)
        ctk.CTkLabel(row, text="✓" if done else num, font=F["sm_b"],
                     text_color=C["white"], fg_color=col,
                     width=28, height=28, corner_radius=14).pack(side="left",padx=(0,10))
        col2 = ctk.CTkFrame(row, fg_color="transparent")
        col2.pack(side="left")
        lbl(col2, title, F["sm_b"], C["text"] if active or done else C["t2"]).pack(anchor="w")
        lbl(col2, desc, F["xs"], C["t3"]).pack(anchor="w")
        return f

    def _save_key(self):
        k = self.api_entry.get().strip()
        if k.startswith("sk-"):
            ST.api_key = k
            config.save_api_key(k)
            self.key_lbl.configure(text="✓  تم الحفظ", text_color=C["glt"])
        else:
            self.key_lbl.configure(text="✗  مفتاح غير صالح", text_color=C["red"])

    def update(self, active_i, done_list):
        for i, card in enumerate(self._cards):
            num, title, desc = self.STEPS[i]
            active = (i == active_i)
            done   = (i in done_list)
            for ch in card.winfo_children(): ch.destroy()
            col = C["blue"] if active else C["glt"] if done else C["t3"]
            fg  = C["bg2"]  if active else C["bg1"]
            bc  = C["blue"] if active else C["glt"] if done else C["border"]
            card.configure(fg_color=fg, border_color=bc)
            row = ctk.CTkFrame(card, fg_color="transparent")
            row.pack(fill="x", padx=12, pady=9)
            ctk.CTkLabel(row, text="✓" if done else num, font=F["sm_b"],
                         text_color=C["white"], fg_color=col,
                         width=28, height=28, corner_radius=14).pack(side="left",padx=(0,10))
            col2 = ctk.CTkFrame(row, fg_color="transparent")
            col2.pack(side="left")
            lbl(col2, title, F["sm_b"], C["text"] if active or done else C["t2"]).pack(anchor="w")
            lbl(col2, desc, F["xs"], C["t3"]).pack(anchor="w")


# ══════════════════════════════════════════════════════════════
#  الشاشة الرئيسية
# ══════════════════════════════════════════════════════════════
class HomeView(ctk.CTkFrame):
    def __init__(self, master, on_select, **kw):
        super().__init__(master, fg_color=C["bg"], corner_radius=0, **kw)
        self.on_select = on_select
        self._build()

    def _build(self):
        hero = ctk.CTkFrame(self, fg_color=C["bg1"], corner_radius=16,
                            border_width=1, border_color=C["bhi"])
        hero.pack(fill="x", padx=20, pady=(16,12))
        h = ctk.CTkFrame(hero, fg_color="transparent")
        h.pack(padx=30, pady=22)
        lbl(h,"⚖",("Arial",60),C["blue"],"center").pack()
        lbl(h,"نظام ذكاء اصطناعي لتحليل العقود التجارية",
            F["heading"],C["text"],"center").pack(pady=(10,6))
        lbl(h,
            "يستخرج النظام عناوين عقدك تلقائياً ويقارنها بالبنود المعيارية\n"
            "ثم يحسب درجة قوة العقد ويكشف البنود المفقودة",
            F["body"],C["t2"],"center",wraplength=620,justify="center").pack()
        pills = ctk.CTkFrame(h, fg_color="transparent")
        pills.pack(pady=14)
        for icon,txt,col in [
            ("🔍","كشف العناوين",C["blue"]),("📊","مقارنة البنود",C["cyan"]),
            ("⚡","بدون إنترنت",C["purple"]),("📈","درجة القوة",C["gold"]),
            ("📄","تقرير PDF",C["glt"])]:
            p = ctk.CTkFrame(pills, fg_color=C["bg2"], corner_radius=20,
                             border_width=1, border_color=col)
            p.pack(side="left", padx=6)
            lbl(p,f" {icon} {txt} ",F["sm"],col).pack(padx=8,pady=7)

        lbl(self,"اختر نوع العلاقة التعاقدية",F["sub"],C["t2"]
            ).pack(anchor="w",padx=24,pady=(8,4))

        # ── زر تحليل صورة العقد ──────────────────────────────
        img_bar = ctk.CTkFrame(self, fg_color="transparent")
        img_bar.pack(fill="x", padx=24, pady=(0, 4))
        ctk.CTkButton(
            img_bar, text="🖼  تحليل صورة عقد  (OCR)",
            width=240, height=42,
            fg_color=C["purple"], hover_color="#6D28D9",
            text_color=C["white"], font=F["sm_b"],
            corner_radius=12,
            command=lambda: self.on_select("__image__")
        ).pack(side="right")

        sc = ctk.CTkScrollableFrame(self, fg_color=C["bg"], corner_radius=0)
        sc.pack(fill="both", expand=True, padx=16, pady=(0,16))
        sc.grid_columnconfigure(0, weight=1)
        sc.grid_columnconfigure(1, weight=1)
        for idx,(name,info) in enumerate(CONTRACT_TYPES.items()):
            self._card(sc, name, info, idx//2, idx%2)

    def _card(self, parent, name, info, row, col):
        cc = info["color"]
        rc = C["red"] if info["risk"]=="عالي" else C["orange"] if info["risk"]=="متوسط" else C["glt"]
        card = ctk.CTkFrame(parent, fg_color=C["card"], corner_radius=14,
                            border_width=1, border_color=C["border"], cursor="hand2")
        card.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="both", padx=18, pady=16)
        ctk.CTkFrame(inner, fg_color=cc, height=5, corner_radius=3).pack(fill="x",pady=(0,14))
        top = ctk.CTkFrame(inner, fg_color="transparent")
        top.pack(fill="x")
        lbl(top, name.split("  ")[0], ("Arial",34), anchor="w").pack(side="left")
        rb = ctk.CTkFrame(top, fg_color=rc, corner_radius=14)
        rb.pack(side="right", pady=6)
        lbl(rb,f" خطر {info['risk']} ",F["badge"],C["white"]).pack(padx=8,pady=4)
        lbl(inner, "  ".join(name.split("  ")[1:]), F["sub"], C["text"]).pack(anchor="w",pady=(10,4))
        lbl(inner, f"{len(info['clauses'])} بنداً معيارياً", F["sm"], cc).pack(anchor="w",pady=(0,12))
        ctk.CTkButton(inner, text="ابدأ التحليل  ←",
                       fg_color=cc, hover_color=C["blue"],
                       text_color=C["white"], font=F["btn"],
                       corner_radius=10, height=44,
                       command=lambda n=name: self.on_select(n)).pack(fill="x")
        card.bind("<Enter>", lambda e,c=card,x=cc: c.configure(border_color=x,fg_color=C["bg2"]))
        card.bind("<Leave>", lambda e,c=card: c.configure(border_color=C["border"],fg_color=C["card"]))

# ══════════════════════════════════════════════════════════════
#  شاشة التحليل
# ══════════════════════════════════════════════════════════════
class AnalysisView(ctk.CTkFrame):
    def __init__(self, master, side, nav_cb, **kw):
        super().__init__(master, fg_color=C["bg"], corner_radius=0, **kw)
        self.side, self.nav_cb, self._busy = side, nav_cb, False
        self._build()

    def _build(self):
        # شريط معلومات
        self.info_bar = ctk.CTkFrame(self, fg_color=C["bg1"], corner_radius=12,
                                     border_width=1, border_color=C["border"])
        self.info_bar.pack(fill="x", padx=16, pady=(12,8))
        ib = ctk.CTkFrame(self.info_bar, fg_color="transparent")
        ib.pack(fill="x", padx=18, pady=12)
        self.type_badge = ctk.CTkLabel(ib, text="", font=F["body_b"],
                                        text_color=C["white"], fg_color=C["blue"],
                                        corner_radius=10, padx=14, pady=6)
        self.type_badge.pack(side="left")
        self.file_lbl = lbl(ib,"لم يتم اختيار ملف بعد",F["sm"],C["t3"])
        self.file_lbl.pack(side="left", padx=16)
        ctk.CTkButton(ib, text="← تغيير النوع", width=145, height=36,
                       fg_color="transparent", hover_color=C["bg3"],
                       text_color=C["t2"], border_width=1, border_color=C["border"],
                       corner_radius=10, font=F["sm_b"],
                       command=lambda: self.nav_cb("home")).pack(side="right")

        # عمودان
        cols = ctk.CTkFrame(self, fg_color="transparent")
        cols.pack(fill="both", expand=True, padx=16, pady=(0,8))
        left = ctk.CTkFrame(cols, fg_color=C["bg1"], corner_radius=14,
                            border_width=1, border_color=C["border"])
        left.pack(side="left", fill="both", expand=True, padx=(0,8))
        self._build_left(left)
        right = ctk.CTkFrame(cols, fg_color=C["bg1"], corner_radius=14,
                             border_width=1, border_color=C["border"])
        right.pack(side="right", fill="both", expand=True, padx=(8,0))
        self._build_right(right)
        self._build_actions()

    def _build_left(self, parent):
        hdr = ctk.CTkFrame(parent, fg_color=C["bg2"], corner_radius=10)
        hdr.pack(fill="x", padx=12, pady=(12,6))
        lbl(hdr,"📂  رفع ملف العقد",F["sub"],C["text"]).pack(side="left",padx=14,pady=10)

        self.dz = ctk.CTkFrame(parent, fg_color=C["bg2"], corner_radius=12,
                               border_width=2, border_color=C["bhi"],
                               cursor="hand2", height=135)
        self.dz.pack(fill="x", padx=12, pady=6)
        self.dz.pack_propagate(False)
        dzc = ctk.CTkFrame(self.dz, fg_color="transparent")
        dzc.place(relx=.5, rely=.5, anchor="center")
        self.dz_icon = lbl(dzc,"📂",("Arial",36),anchor="center")
        self.dz_icon.pack()
        self.dz_txt  = lbl(dzc,"انقر لاختيار ملف PDF",F["body_b"],C["cyan"],"center")
        self.dz_txt.pack(pady=4)
        self.dz_hint = lbl(dzc,"PDF فقط  •  حتى 50 ميجابايت",F["sm"],C["t3"],"center")
        self.dz_hint.pack()
        for w in [self.dz,dzc,self.dz_icon,self.dz_txt,self.dz_hint]:
            w.bind("<Button-1>", lambda e: self._pick())

        self.prog_lbl = lbl(parent,"",F["xs"],C["t3"])
        self.prog_lbl.pack(anchor="w", padx=14, pady=(2,0))
        self.prog = ctk.CTkProgressBar(parent, height=6, corner_radius=3,
                                        fg_color=C["bg2"], progress_color=C["cyan"])
        self.prog.pack(fill="x", padx=12, pady=(2,8))
        self.prog.set(0)

        hdr2 = ctk.CTkFrame(parent, fg_color=C["bg2"], corner_radius=10)
        hdr2.pack(fill="x", padx=12, pady=(0,4))
        lbl(hdr2,"📋  العناوين المستخرجة",F["sm_b"],C["t2"]).pack(side="left",padx=14,pady=8)
        self.heads_cnt = lbl(hdr2,"",F["xs"],C["t3"])
        self.heads_cnt.pack(side="right",padx=14)

        self.heads_box = ctk.CTkScrollableFrame(parent, fg_color=C["bg"],
                                                 corner_radius=10,
                                                 border_width=1, border_color=C["border"])
        self.heads_box.pack(fill="both", expand=True, padx=12, pady=(0,12))
        lbl(self.heads_box,
            "بعد تحميل الملف ستظهر هنا\nعناوين البنود المكتشفة",
            F["body"],C["t3"],"center",justify="center").pack(expand=True,pady=30)

    def _build_right(self, parent):
        hdr = ctk.CTkFrame(parent, fg_color=C["bg2"], corner_radius=10)
        hdr.pack(fill="x", padx=12, pady=(12,6))
        lbl(hdr,"📊  نتائج التقييم",F["sub"],C["text"]).pack(side="left",padx=14,pady=10)
        self.res_status = lbl(hdr,"بانتظار التحليل...",F["sm"],C["t3"])
        self.res_status.pack(side="right",padx=14)

        self.result_box = ctk.CTkScrollableFrame(parent, fg_color=C["bg"],
                                                  corner_radius=10,
                                                  border_width=1, border_color=C["border"])
        self.result_box.pack(fill="both", expand=True, padx=12, pady=(0,12))
        lbl(self.result_box,
            "⚙\n\nبعد تحميل الملف\nاضغط زر تحليل العقد\nلعرض النتائج",
            F["body"],C["t3"],"center",justify="center").pack(expand=True,pady=50)

    def _build_actions(self):
        bar = ctk.CTkFrame(self, fg_color=C["bg1"], corner_radius=12,
                           border_width=1, border_color=C["border"])
        bar.pack(fill="x", padx=16, pady=(0,12))
        inner = ctk.CTkFrame(bar, fg_color="transparent")
        inner.pack(fill="x", padx=18, pady=12)

        self.btn_upload = ctk.CTkButton(inner, text="📂  تحميل PDF",
                                         width=180, height=48,
                                         fg_color=C["blue"], hover_color=C["blt"],
                                         text_color=C["white"], font=F["btn"],
                                         corner_radius=10, command=self._pick)
        self.btn_upload.pack(side="left", padx=(0,10))

        self.btn_analyze = ctk.CTkButton(inner, text="⚡  تحليل العقد الآن",
                                          width=230, height=48,
                                          fg_color=C["purple"], hover_color="#6D28D9",
                                          text_color=C["white"], font=F["btn"],
                                          corner_radius=10, state="disabled",
                                          command=self._run)
        self.btn_analyze.pack(side="left", padx=(0,10))

        self.btn_report = ctk.CTkButton(inner, text="📄  عرض التقرير",
                                         width=180, height=48,
                                         fg_color=C["glt"], hover_color=C["green"],
                                         text_color=C["white"], font=F["btn"],
                                         corner_radius=10, state="disabled",
                                         command=lambda: self.nav_cb("report"))
        self.btn_report.pack(side="left")

        sc_card = ctk.CTkFrame(inner, fg_color=C["bg2"], corner_radius=12,
                               border_width=1, border_color=C["bhi"])
        sc_card.pack(side="right")
        self.score_lbl = ctk.CTkLabel(sc_card, text="—", font=F["score"], text_color=C["t2"])
        self.score_lbl.pack(padx=22, pady=(8,0))
        lbl(sc_card,"قوة العقد",F["sm"],C["t3"],"center").pack(padx=22,pady=(0,8))

    def refresh_type(self):
        ct   = ST.contract_type or ""
        info = CONTRACT_TYPES.get(ct,{})
        self.type_badge.configure(text=f"  {ct}  ",
                                   fg_color=info.get("color",C["blue"]))

    def _pick(self):
        path = filedialog.askopenfilename(
            title="اختر ملف العقد",
            filetypes=[("PDF","*.pdf"),("All","*.*")])
        if not path: return
        ST.pdf_path = path
        fname = os.path.basename(path)
        size  = os.path.getsize(path)//1024
        self.dz_icon.configure(text="✅")
        self.dz_txt.configure(text=fname[:44]+("..." if len(fname)>44 else ""),
                               text_color=C["glt"])
        self.dz_hint.configure(text=f"{size} KB  •  جاهز للقراءة",
                               text_color=C["t2"])
        self.dz.configure(border_color=C["glt"])
        self.file_lbl.configure(text=f"📄  {fname}  ({size} KB)",
                                 text_color=C["t2"])
        threading.Thread(target=self._extract_thread, daemon=True).start()

    def _extract_thread(self):
        self.after(0, lambda: self.btn_analyze.configure(state="disabled"))
        for v,t in [(0.2,"قراءة الملف..."),(0.5,"استخراج النص..."),
                    (0.8,"تحليل الهيكل...")]:
            self.after(0, self._upd_prog, v, t)
            time.sleep(0.3)
        try:
            text, heads = extract_headings(ST.pdf_path)
            ST.raw_text, ST.found_headings = text, heads
            self.after(0, self._upd_prog, 1.0, "✓  اكتملت القراءة")
            self.after(0, self._show_headings, heads)
            self.after(0, lambda: self.side.update(1,[0]))
        except ValueError as e:
            # رسالة خطأ واضحة — لا بيانات وهمية
            self.after(0, lambda msg=str(e): messagebox.showerror(
                "خطأ في قراءة الملف", msg))
            self.after(0, self._upd_prog, 0, "✗  فشل قراءة الملف")
            self.after(0, lambda: self.btn_analyze.configure(state="disabled"))

    def _upd_prog(self, v, t):
        self.prog.set(v)
        self.prog_lbl.configure(text=t,
                                 text_color=C["glt"] if v==1.0 else C["t3"])

    def _show_headings(self, heads):
        for w in self.heads_box.winfo_children(): w.destroy()
        ct  = ST.contract_type or ""
        col = CONTRACT_TYPES.get(ct,{}).get("color",C["blue"])
        self.heads_cnt.configure(text=f"{len(heads)} عنوان", text_color=C["glt"])
        bold_cnt = sum(1 for h in heads if h.get("bold"))

        # ملخص سريع
        summ = ctk.CTkFrame(self.heads_box, fg_color=C["bg2"], corner_radius=10,
                            border_width=1, border_color=C["bhi"])
        summ.pack(fill="x", padx=4, pady=(4,8))
        sr = ctk.CTkFrame(summ, fg_color="transparent")
        sr.pack(fill="x", padx=14, pady=10)
        for txt, clr in [
            (f"{len(heads)}\nإجمالي العناوين",C["cyan"]),
            (f"{bold_cnt}\nعناوين غامقة",C["gold"]),
            (f"{len(heads)-bold_cnt}\nعناوين عادية",C["t2"])]:
            b = ctk.CTkFrame(sr, fg_color=C["bg3"], corner_radius=8)
            b.pack(side="left", padx=6, expand=True, fill="x")
            lbl(b, txt, F["sm"], clr, "center", justify="center").pack(padx=10,pady=8)

        for i, h in enumerate(heads):
            bold = h.get("bold",False)
            row  = ctk.CTkFrame(self.heads_box,
                                fg_color=C["bg2"] if i%2==0 else C["bg"],
                                corner_radius=8)
            row.pack(fill="x", padx=4, pady=2)
            inner = ctk.CTkFrame(row, fg_color="transparent")
            inner.pack(fill="x", padx=12, pady=9)
            ctk.CTkLabel(inner, text=str(i+1), font=F["sm_b"],
                         text_color=C["white"], fg_color=col,
                         width=28, height=28, corner_radius=14
                         ).pack(side="left",padx=(0,10))
            lbl(inner, h["title"], F["body"],
                C["text"] if bold else C["t2"],
                anchor="w", justify="left",
                wraplength=280).pack(side="left",fill="x",expand=True)
            right_b = ctk.CTkFrame(inner, fg_color="transparent")
            right_b.pack(side="right")
            if bold:
                bb = ctk.CTkFrame(right_b, fg_color=C["gold"], corner_radius=8)
                bb.pack(side="left",padx=3)
                lbl(bb," غامق ",F["xs"],C["white"]).pack(padx=5,pady=3)
            pb = ctk.CTkFrame(right_b, fg_color=C["bg3"], corner_radius=8)
            pb.pack(side="left",padx=2)
            lbl(pb,f" ص{h['page']} ",F["xs"],C["t3"]).pack(padx=5,pady=3)

        self.btn_analyze.configure(state="normal")

    def _run(self):
        if self._busy: return
        # ── فحص ١: هل اختار المستخدم نوع العقد؟ ─────────────
        if not ST.contract_type:
            messagebox.showwarning(
                "لم يتم اختيار نوع العقد",
                "⚠  يرجى الذهاب للشاشة الرئيسية\n"
                "واختيار نوع العقد قبل البدء بالتحليل."
            )
            return
        # ── فحص ٢: هل رُفع ملف؟ ─────────────────────────────
        if not ST.pdf_path:
            messagebox.showwarning(
                "لم يتم رفع ملف",
                "⚠  يرجى رفع ملف PDF أولاً."
            )
            return
        self._busy = True
        self.btn_analyze.configure(state="disabled", text="⏳  جارٍ التحليل...")
        self.res_status.configure(text="يعمل...", text_color=C["cyan"])
        threading.Thread(target=self._analysis_thread, daemon=True).start()

    def _analysis_thread(self):
        ct   = ST.contract_type or ""
        info = CONTRACT_TYPES.get(ct,{})
        exp  = info.get("clauses",[])
        res  = analyze_rules(ST.found_headings, ST.raw_text, exp)
        ST.result = res
        self.after(0, self._show_result, res, info)

        # ── فحص توافق نوع العقد مع المحتوى ──────────────────
        # نستخدم نص العناوين + النص الكامل لتشخيص أدق
        if ST.raw_text and len(ST.raw_text) > 50:
            detect = self._smart_mismatch_check(res, ct)
            if detect:
                self.after(600, lambda d=detect: self._warn_mismatch(d))

    def _smart_mismatch_check(self, res: dict, selected_type: str) -> dict | None:
        """
        فحص ذكي للتوافق يعتمد على:
        1. نسبة البنود الموجودة (إذا كانت 0% → خطأ واضح)
        2. كاشف النوع على نص العناوين المستخرجة فعلاً
        3. كلمات مفتاحية حصرية لكل نوع

        يُعيد dict تحذير أو None إذا كل شيء طبيعي.
        """
        from contract_detector import detect_contract_type

        total_found = res.get("total_found", 0)
        total_exp   = res.get("total_exp", 1)
        score       = res.get("score", 0)

        # ── المؤشر الأول: درجة 0 مع وجود عناوين → خطأ تصنيف ─
        heads = ST.found_headings or []
        has_headings = len(heads) > 0

        if has_headings and total_found == 0 and score == 0:
            # لم يُطابق ولا بند → خطأ تصنيف واضح
            # استخدم نص العناوين للكشف الأدق
            headings_text = " ".join(h.get("title","") for h in heads)
            det = detect_contract_type(headings_text)

            # إذا لم يُكتشف نوع واضح → جرب النص الكامل مع تجاهل أسماء الشركات
            if det.confidence < 0.25:
                # احذف أول 3 أسطر (غالباً اسم الشركة والتاريخ)
                clean_text = "\n".join(ST.raw_text.split("\n")[3:])
                det = detect_contract_type(clean_text)

            detected = det.detected_type
            sel_short = selected_type.split("  ")[-1] if "  " in selected_type else selected_type
            det_short = detected.split("  ")[-1]       if "  " in detected      else detected

            if detected != selected_type and detected != "غير محدد":
                return {
                    "warning_msg": (
                        f"⚠  لم يُعثر على أي بند مطابق من بنود «{sel_short}».\n\n"
                        f"يبدو أن الملف المرفوع هو «{det_short}» وليس «{sel_short}»."
                    ),
                    "suggestion": (
                        f"يُنصح باختيار «{det_short}» للحصول على تحليل صحيح.\n\n"
                        f"هل تريد العودة للصفحة الرئيسية لتغيير التصنيف؟"
                    ),
                }
            elif detected == "غير محدد" and total_found == 0:
                return {
                    "warning_msg": (
                        f"⚠  لم يُعثر على أي بند مطابق من بنود «{sel_short}».\n\n"
                        f"تأكد أنك اخترت النوع الصحيح للعقد المرفوع."
                    ),
                    "suggestion": "هل تريد العودة للصفحة الرئيسية لتغيير التصنيف؟",
                }

        # ── المؤشر الثاني: نسبة مطابقة ضعيفة جداً (< 20%) ──
        match_rate = total_found / total_exp if total_exp > 0 else 0
        if match_rate < 0.20 and total_exp >= 6 and has_headings:
            # نص العناوين للكشف الأدق (بدون أسماء الشركات)
            headings_text = " ".join(h.get("title","") for h in heads)
            det = detect_contract_type(headings_text)
            detected = det.detected_type
            sel_short = selected_type.split("  ")[-1] if "  " in selected_type else selected_type

            if detected != selected_type and detected != "غير محدد" and det.confidence > 0.30:
                det_short = detected.split("  ")[-1] if "  " in detected else detected
                conf_pct  = int(det.confidence * 100)
                return {
                    "warning_msg": (
                        f"⚠  نسبة التطابق منخفضة جداً ({int(match_rate*100)}%) "
                        f"لبنود «{sel_short}».\n\n"
                        f"يبدو أن الملف أقرب لـ«{det_short}» بثقة {conf_pct}%."
                    ),
                    "suggestion": (
                        f"يُنصح باختيار «{det_short}».\n\n"
                        f"هل تريد العودة للصفحة الرئيسية لتغيير التصنيف؟"
                    ),
                }

        return None   # لا تعارض

    def _warn_mismatch(self, detect: dict):
        """يُظهر تحذير عدم التوافق مع اقتراح النوع الصحيح."""
        answer = messagebox.askyesno(
            "⚠  تحذير: نوع العقد قد لا يكون صحيحاً",
            f"{detect['warning_msg']}\n\n{detect['suggestion']}",
            icon="warning"
        )
        if answer:
            self.nav_cb("home")

    def _show_result(self, res, info):
        self._busy = False
        self.btn_analyze.configure(state="normal", text="⚡  إعادة التحليل")
        self.res_status.configure(text="✓  اكتمل", text_color=C["glt"])
        for w in self.result_box.winfo_children(): w.destroy()

        score   = res.get("score",0)
        level   = res.get("level","—")
        lev_col = res.get("level_color",C["t2"])
        found   = res.get("found",{})
        missing = res.get("missing",[])
        risks   = res.get("risks",[])
        col     = info.get("color",C["blue"])

        sc_col = C["glt"] if score>=75 else C["gold"] if score>=50 else C["red"]
        self.score_lbl.configure(text=f"{score}%", text_color=sc_col)
        self.side.update(3,[0,1,2])

        # بطاقة الدرجة
        sc_card = ctk.CTkFrame(self.result_box, fg_color=C["bg1"],
                               corner_radius=14, border_width=2, border_color=lev_col)
        sc_card.pack(fill="x", padx=6, pady=(6,10))
        si = ctk.CTkFrame(sc_card, fg_color="transparent")
        si.pack(padx=20, pady=18)
        lbl(si, f"{score}", F["score"], lev_col, "center").pack()
        lbl(si,"من 100  –  قوة العقد الإجمالية",F["body"],C["t2"],"center").pack(pady=(4,2))
        pb2 = ctk.CTkProgressBar(si, height=16, corner_radius=8,
                                   fg_color=C["bg2"], progress_color=lev_col, width=300)
        pb2.pack(pady=6)
        pb2.set(score/100)
        lbl(si,f"المستوى:  {level}",F["sub"],lev_col,"center").pack(pady=(4,0))
        stats = ctk.CTkFrame(si, fg_color="transparent")
        stats.pack(pady=10)
        for txt,clr in [
            (f"✓  {res.get('total_found',0)}\nبند موجود",C["glt"]),
            (f"✗  {len(missing)}\nبند مفقود",C["red"]),
            (f"⚠  {len(risks)}\nتنبيه",C["orange"])]:
            b = ctk.CTkFrame(stats, fg_color=C["bg2"], corner_radius=10)
            b.pack(side="left",padx=8)
            lbl(b,txt,F["body_b"],clr,"center",justify="center").pack(padx=16,pady=10)

        # مقارنة البنود
        self._sec("📊  مقارنة البنود المعيارية", col)
        for clause_name, cinfo in found.items():
            str_  = cinfo.get("strength","")
            bold_ = cinfo.get("bold",False)
            sub_  = cinfo.get("sub_count",0)
            str_c = (C["glt"] if str_=="قوي" else C["cyan"] if str_=="جيد"
                     else C["gold"] if str_=="متوسط" else C["orange"] if str_=="مقبول"
                     else C["red"])
            row = ctk.CTkFrame(self.result_box, fg_color=C["bg2"], corner_radius=8,
                               border_width=1, border_color=C["border"])
            row.pack(fill="x",padx=6,pady=3)
            ri = ctk.CTkFrame(row, fg_color="transparent")
            ri.pack(fill="x",padx=12,pady=9)
            lbl(ri,"✓",F["body_b"],C["glt"],width=26).pack(side="left")
            lbl(ri,clause_name,F["body"],C["text"],anchor="w"
                ).pack(side="left",padx=8,fill="x",expand=True)
            rb2 = ctk.CTkFrame(ri, fg_color="transparent")
            rb2.pack(side="right")
            if bold_:
                bb = ctk.CTkFrame(rb2, fg_color=C["gold"], corner_radius=8)
                bb.pack(side="left",padx=3)
                lbl(bb," غامق ",F["xs"],C["white"]).pack(padx=5,pady=3)
            sb2 = ctk.CTkFrame(rb2, fg_color=str_c, corner_radius=8)
            sb2.pack(side="left",padx=3)
            lbl(sb2,f" {str_} ",F["xs"],C["white"]).pack(padx=5,pady=3)
            lbl(rb2,f" {sub_} فرعي ",F["xs"],C["t3"]).pack(side="left",padx=4)

        # مفقودة
        if missing:
            self._sec("❌  البنود المفقودة", C["red"])
            for m in missing:
                row = ctk.CTkFrame(self.result_box, fg_color=C["bg"], corner_radius=8,
                                   border_width=1, border_color=C["border"])
                row.pack(fill="x",padx=6,pady=3)
                ri = ctk.CTkFrame(row, fg_color="transparent")
                ri.pack(fill="x",padx=12,pady=9)
                lbl(ri,"✗",F["body_b"],C["red"],width=26).pack(side="left")
                lbl(ri,m,F["body"],C["t3"],anchor="w").pack(side="left",padx=8,fill="x",expand=True)
                mb = ctk.CTkFrame(ri, fg_color=C["red"], corner_radius=8)
                mb.pack(side="right")
                lbl(mb," مفقود ",F["xs"],C["white"]).pack(padx=5,pady=3)

        # مخاطر
        if risks:
            self._sec("⚠  التنبيهات والمخاطر", C["orange"])
            for r in risks:
                rc = C["red"] if r["level"]=="عالي" else C["orange"] if r["level"]=="متوسط" else C["glt"]
                rf = ctk.CTkFrame(self.result_box, fg_color=C["bg2"], corner_radius=10,
                                  border_width=1, border_color=rc)
                rf.pack(fill="x",padx=6,pady=4)
                rh = ctk.CTkFrame(rf, fg_color="transparent")
                rh.pack(fill="x",padx=14,pady=(10,4))
                lbl(rh,f"● {r['title']}",F["body_b"],rc).pack(side="left")
                rlb = ctk.CTkFrame(rh, fg_color=rc, corner_radius=10)
                rlb.pack(side="right")
                lbl(rlb,f" {r['level']} ",F["sm_b"],C["white"]).pack(padx=6,pady=3)
                lbl(rf,r["desc"],F["body"],C["t2"],
                    wraplength=360,justify="right",anchor="e").pack(anchor="e",padx=14,pady=(0,10))

        self.btn_report.configure(state="normal")
        self.side.update(4,[0,1,2,3])

        # ── حفظ النتيجة في قاعدة البيانات ───────────────────
        if ST.current_user:
            try:
                save_analysis(
                    user_id       = ST.current_user["id"],
                    result        = res,
                    pdf_path      = ST.pdf_path or "",
                    contract_type = ST.contract_type or "",
                )
            except Exception as e:
                print(f"[save_analysis] تحذير: {e}")

    def _sec(self, title, color):
        f = ctk.CTkFrame(self.result_box, fg_color=C["bg2"], corner_radius=10)
        f.pack(fill="x",padx=4,pady=(10,2))
        lbl(f,title,F["sub"],color).pack(anchor="w",padx=14,pady=10)

# ══════════════════════════════════════════════════════════════
#  شاشة التقرير
# ══════════════════════════════════════════════════════════════
class ReportView(ctk.CTkFrame):
    def __init__(self, master, **kw):
        super().__init__(master, fg_color=C["bg"], corner_radius=0, **kw)
        self._build()

    def _build(self):
        hdr = ctk.CTkFrame(self, fg_color=C["bg1"], corner_radius=0)
        hdr.pack(fill="x")
        hi = ctk.CTkFrame(hdr, fg_color="transparent")
        hi.pack(fill="x", padx=20, pady=14)
        lbl(hi,"📄  التقرير التفصيلي الكامل",F["heading"],C["text"]).pack(side="left")
        ctk.CTkButton(hi, text="💾  تصدير PDF", width=160, height=40,
                       fg_color=C["glt"], hover_color=C["green"],
                       text_color=C["white"], font=F["btn_sm"],
                       corner_radius=10, command=self._export).pack(side="right")
        sep(self, C["border"])
        self.sc = ctk.CTkScrollableFrame(self, fg_color=C["bg"], corner_radius=0)
        self.sc.pack(fill="both", expand=True, padx=16, pady=(0,12))
        lbl(self.sc,
            "🔍\n\nقم بتحليل عقد أولاً\nثم انتقل لهذه الشاشة\nلعرض التقرير الكامل",
            F["heading"],C["t3"],"center",justify="center").pack(expand=True,pady=100)

    def refresh(self):
        for w in self.sc.winfo_children(): w.destroy()
        res = ST.result
        if not res:
            lbl(self.sc,"لا توجد بيانات",F["body"],C["t3"],"center").pack(pady=40)
            return
        ct    = ST.contract_type or ""
        info  = CONTRACT_TYPES.get(ct,{})
        col   = info.get("color",C["blue"])
        score = res.get("score",0)
        level = res.get("level","—")
        lev_c = res.get("level_color",C["t2"])

        # بطاقة الدرجة
        sc_card = ctk.CTkFrame(self.sc, fg_color=C["bg1"], corner_radius=16,
                               border_width=2, border_color=lev_c)
        sc_card.pack(fill="x",padx=10,pady=(10,6))
        si = ctk.CTkFrame(sc_card, fg_color="transparent")
        si.pack(padx=30, pady=24)
        lbl(si,f"{score}",F["score"],lev_c,"center").pack()
        lbl(si,"درجة قوة العقد من 100",F["sub"],C["t2"],"center").pack(pady=(6,4))
        pb = ctk.CTkProgressBar(si,height=20,corner_radius=10,
                                  fg_color=C["bg2"],progress_color=lev_c,width=420)
        pb.pack(pady=8)
        pb.set(score/100)
        lbl(si,f"التصنيف:  {level}",F["heading"],lev_c,"center").pack(pady=(4,0))
        lbl(si,ct,F["body"],col,"center").pack(pady=4)
        sr = ctk.CTkFrame(si, fg_color="transparent")
        sr.pack(pady=12)
        for txt,clr in [
            (f"✓  {res.get('total_found',0)}\nبند موجود",C["glt"]),
            (f"✗  {len(res.get('missing',[]))}\nبند مفقود",C["red"]),
            (f"◈  {res.get('total_exp',0)}\nإجمالي متوقع",C["cyan"]),
            (f"⚠  {len(res.get('risks',[]))}\nتنبيه",C["orange"])]:
            b = ctk.CTkFrame(sr, fg_color=C["bg2"], corner_radius=10)
            b.pack(side="left",padx=8)
            lbl(b,txt,F["body_b"],clr,"center",justify="center").pack(padx=18,pady=12)

        # جدول البنود
        self._sec("📊  جدول البنود المعيارية مقارنةً بالعقد", col)
        hdr2 = ctk.CTkFrame(self.sc, fg_color=col, corner_radius=8)
        hdr2.pack(fill="x",padx=10,pady=(0,2))
        hr = ctk.CTkFrame(hdr2, fg_color="transparent")
        hr.pack(fill="x",padx=14,pady=10)
        for txt,w_ in [("البند المعياري",300),("الحالة",90),
                        ("القوة",90),("فرعي",90),("غامق",70)]:
            lbl(hr,txt,F["sm_b"],C["white"],width=w_).pack(side="left",padx=4)

        exp    = info.get("clauses",[])
        found  = res.get("found",{})
        missing= res.get("missing",[])
        for i,clause in enumerate(exp):
            bg = C["bg2"] if i%2==0 else C["bg"]
            row = ctk.CTkFrame(self.sc, fg_color=bg, corner_radius=8)
            row.pack(fill="x",padx=10,pady=2)
            ri = ctk.CTkFrame(row, fg_color="transparent")
            ri.pack(fill="x",padx=14,pady=10)
            is_f = clause in found
            ci   = found.get(clause,{})
            str_ = ci.get("strength","—")
            bold_= ci.get("bold",False)
            sub_ = ci.get("sub_count",0)
            str_c= (C["glt"] if str_=="قوي" else C["cyan"] if str_=="جيد"
                    else C["gold"] if str_=="متوسط" else C["orange"] if str_=="مقبول"
                    else C["red"] if str_!="—" else C["t3"])
            lbl(ri,clause,F["body"],C["text"] if is_f else C["t3"],
                width=300,anchor="w").pack(side="left",padx=4)
            lbl(ri,"✓ موجود" if is_f else "✗ مفقود",F["sm_b"],
                C["glt"] if is_f else C["red"],width=90).pack(side="left",padx=4)
            lbl(ri,str_,F["sm_b"],str_c if is_f else C["t3"],width=90).pack(side="left",padx=4)
            lbl(ri,str(sub_) if is_f else "—",F["sm"],C["t2"],
                width=90,anchor="center").pack(side="left",padx=4)
            lbl(ri,"✓" if bold_ else ("✗" if is_f else "—"),
                F["sm"],C["gold"] if bold_ else C["t3"],
                width=70,anchor="center").pack(side="left",padx=4)

        # مخاطر
        risks = res.get("risks",[])
        if risks:
            self._sec("⚠  المخاطر والتنبيهات",C["orange"])
            for r in risks:
                rc = C["red"] if r["level"]=="عالي" else C["orange"] if r["level"]=="متوسط" else C["glt"]
                rf = ctk.CTkFrame(self.sc, fg_color=C["bg2"], corner_radius=10,
                                  border_width=1, border_color=rc)
                rf.pack(fill="x",padx=10,pady=4)
                rh = ctk.CTkFrame(rf, fg_color="transparent")
                rh.pack(fill="x",padx=16,pady=(12,4))
                lbl(rh,f"● {r['title']}",F["body_b"],rc).pack(side="left")
                rlb = ctk.CTkFrame(rh, fg_color=rc, corner_radius=10)
                rlb.pack(side="right")
                lbl(rlb,f" {r['level']} ",F["sm_b"],C["white"]).pack(padx=8,pady=4)
                lbl(rf,r["desc"],F["body"],C["t2"],
                    wraplength=700,justify="right").pack(anchor="e",padx=16,pady=(0,12))

        # شرح الخوارزمية
        self._sec("📈  منطق الخوارزمية المستخدمة",col)
        lbl(self.sc,
            "وجود البند  →  +10 نقطة  |  "
            "خط غامق  →  +2  |  "
            "بند فرعي واحد  →  +1  |  "
            "بندان  →  +3  |  "
            "ثلاثة  →  +5  |  "
            "أربعة فأكثر  →  +8",
            F["sm"],C["t3"],"w",wraplength=750).pack(anchor="w",padx=16,pady=6)

        for name,cinfo in found.items():
            pts = 10 + (2 if cinfo.get("bold") else 0)
            sc2 = cinfo.get("sub_count",0)
            pts += (8 if sc2>=4 else 5 if sc2==3 else 3 if sc2==2 else 1 if sc2==1 else 0)
            rf = ctk.CTkFrame(self.sc, fg_color=C["bg2"], corner_radius=8)
            rf.pack(fill="x",padx=10,pady=2)
            ri = ctk.CTkFrame(rf, fg_color="transparent")
            ri.pack(fill="x",padx=14,pady=8)
            lbl(ri,name,F["body"],C["text"],anchor="w").pack(side="left",fill="x",expand=True)
            lbl(ri,f"+{pts} نقطة",F["sm_b"],C["glt"]).pack(side="right")

    def _sec(self, title, color):
        f = ctk.CTkFrame(self.sc, fg_color=C["bg1"], corner_radius=10)
        f.pack(fill="x",padx=8,pady=(14,2))
        lbl(f,title,F["sub"],color).pack(anchor="w",padx=16,pady=12)

    def _export(self):
        if not ST.result:
            messagebox.showinfo("تنبيه","قم بالتحليل أولاً")
            return
        out = filedialog.asksaveasfilename(
            title="حفظ التقرير",
            defaultextension=".pdf",
            filetypes=[("PDF","*.pdf"),("نص","*.txt")],
            initialfile=f"تقرير_العقد_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf")
        if not out: return
        if RL_OK and out.endswith(".pdf") and self._gen_pdf(out):
            messagebox.showinfo("تم","✓  تم حفظ التقرير:\n"+out)
            return
        txt = out if out.endswith(".txt") else out.replace(".pdf",".txt")
        res = ST.result
        with open(txt,"w",encoding="utf-8") as f:
            f.write(f"تقرير تحليل العقد\n{'='*50}\n")
            f.write(f"النوع: {ST.contract_type}\n")
            f.write(f"التاريخ: {datetime.now().strftime('%Y/%m/%d %H:%M')}\n")
            f.write(f"الدرجة: {res.get('score',0)}/100  –  {res.get('level','')}\n\n")
            f.write("البنود الموجودة:\n")
            for n,i in res.get("found",{}).items():
                f.write(f"  ✓ {n}  [{i.get('strength','')} • {i.get('sub_count',0)} فرعي]\n")
            f.write("\nالبنود المفقودة:\n")
            for m in res.get("missing",[]): f.write(f"  ✗ {m}\n")
            f.write("\nالمخاطر:\n")
            for r in res.get("risks",[]): f.write(f"  [{r['level']}] {r['title']}: {r['desc']}\n")
        messagebox.showinfo("تم",f"✓  تم الحفظ:\n{txt}")

    def _gen_pdf(self, path):
        try:
            from reportlab.lib.styles import ParagraphStyle as PS
            doc = SimpleDocTemplate(path,pagesize=A4,
                                    rightMargin=2*cm,leftMargin=2*cm,
                                    topMargin=2*cm,bottomMargin=2*cm)
            story=[]
            def P(txt,size=12,bold=False,color="#000000",align=2):
                st=PS("x",fontSize=size,textColor=RC.HexColor(color),
                      alignment=align,
                      fontName="Helvetica-Bold" if bold else "Helvetica",
                      leading=size*1.6)
                return Paragraph(txt,st)
            res   = ST.result
            score = res.get("score",0)
            sc    = "#059669" if score>=75 else "#D97706" if score>=50 else "#DC2626"
            story+=[
                P("تقرير تحليل العقد التجاري",18,True,"#1E3A8A",1),
                P(f"النوع: {ST.contract_type}",12,False,"#374151",1),
                P(f"التاريخ: {datetime.now().strftime('%Y/%m/%d  %H:%M')}",10,False,"#6B7280",1),
                Spacer(1,0.4*cm),
                HRFlowable(width="100%",thickness=2,color=RC.HexColor("#2563EB")),
                Spacer(1,0.4*cm),
                P(f"درجة قوة العقد: {score}/100  –  {res.get('level','')}",16,True,sc,1),
                Spacer(1,0.4*cm),
            ]
            ct  = ST.contract_type or ""
            exp = CONTRACT_TYPES.get(ct,{}).get("clauses",[])
            found= res.get("found",{})
            data=[["البند","الحالة","القوة","فرعي","غامق"]]
            for c in exp:
                if c in found:
                    ci=found[c]
                    data.append([c,"✓ موجود",ci.get("strength","—"),
                                 str(ci.get("sub_count",0)),"✓" if ci.get("bold") else "✗"])
                else:
                    data.append([c,"✗ مفقود","—","—","—"])
            t=Table(data,colWidths=[7*cm,2.5*cm,2.5*cm,1.8*cm,1.5*cm])
            t.setStyle(TableStyle([
                ("BACKGROUND",(0,0),(-1,0),RC.HexColor("#1E3A8A")),
                ("TEXTCOLOR",(0,0),(-1,0),RC.white),
                ("ALIGN",(0,0),(-1,-1),"RIGHT"),
                ("FONTSIZE",(0,0),(-1,-1),10),
                ("ROWBACKGROUNDS",(0,1),(-1,-1),[RC.HexColor("#F0F9FF"),RC.white]),
                ("GRID",(0,0),(-1,-1),0.5,RC.HexColor("#CBD5E1")),
                ("TEXTCOLOR",(1,1),(1,len(found)),RC.HexColor("#059669")),
                ("TEXTCOLOR",(1,len(found)+1),(1,-1),RC.HexColor("#DC2626")),
            ]))
            story.append(t)
            story.append(Spacer(1,0.5*cm))
            for r in res.get("risks",[]):
                rc="#DC2626" if r["level"]=="عالي" else "#D97706" if r["level"]=="متوسط" else "#059669"
                story.append(P(f"⚠ {r['title']}  [{r['level']}]",12,True,rc))
                story.append(P(r["desc"],10,False,"#374151"))
                story.append(Spacer(1,0.2*cm))
            story.append(HRFlowable(width="100%",thickness=1,color=RC.HexColor("#CBD5E1")))
            story.append(P("تم إعداد هذا التقرير بواسطة نظام تحليل العقود الذكي  •  مشروع تخرج",
                           8,False,"#9CA3AF",1))
            doc.build(story)
            return True
        except Exception as e:
            print("PDF error:",e)
            return False

# ══════════════════════════════════════════════════════════════
#  شاشة السجل التاريخي
# ══════════════════════════════════════════════════════════════
class HistoryView(ctk.CTkFrame):
    def __init__(self, master, **kw):
        super().__init__(master, fg_color=C["bg"], corner_radius=0, **kw)
        self._build()

    def _build(self):
        hdr = ctk.CTkFrame(self, fg_color=C["bg1"], corner_radius=0)
        hdr.pack(fill="x")
        hi = ctk.CTkFrame(hdr, fg_color="transparent")
        hi.pack(fill="x", padx=20, pady=14)
        lbl(hi, "📋  سجل التحليلات", F["heading"], C["text"]).pack(side="left")
        self.refresh_btn = ctk.CTkButton(
            hi, text="🔄  تحديث", width=120, height=36,
            fg_color=C["bg2"], hover_color=C["bg3"],
            text_color=C["t2"], border_width=1,
            border_color=C["border"], corner_radius=10,
            font=F["sm_b"], command=self.refresh)
        self.refresh_btn.pack(side="right")
        sep(self, C["border"])

        # إحصاء سريع
        self.stats_bar = ctk.CTkFrame(self, fg_color=C["bg1"],
                                       corner_radius=10,
                                       border_width=1, border_color=C["border"])
        self.stats_bar.pack(fill="x", padx=16, pady=(10,0))

        self.sc = ctk.CTkScrollableFrame(self, fg_color=C["bg"], corner_radius=0)
        self.sc.pack(fill="both", expand=True, padx=16, pady=(8,12))

        lbl(self.sc,
            "📋\n\nسجّل دخولك وحلّل عقداً\nلتظهر هنا سجلاتك",
            F["heading"], C["t3"], "center",
            justify="center").pack(expand=True, pady=80)

    def refresh(self):
        """يُحدّث قائمة السجلات من قاعدة البيانات"""
        for w in self.stats_bar.winfo_children(): w.destroy()
        for w in self.sc.winfo_children():         w.destroy()

        if not ST.current_user:
            lbl(self.sc, "⚠  يرجى تسجيل الدخول أولاً",
                F["body"], C["orange"], "center").pack(pady=40)
            return

        user_id = ST.current_user["id"]
        from database import get_user_stats
        stats   = get_user_stats(user_id)
        history = get_user_history(user_id, limit=50)

        # ── إحصاء ────────────────────────────────────────────
        si = ctk.CTkFrame(self.stats_bar, fg_color="transparent")
        si.pack(fill="x", padx=16, pady=12)
        for txt, clr in [
            (f"📊  {stats['total']}\nإجمالي التحليلات", C["cyan"]),
            (f"⭐  {stats['avg_score']}%\nمتوسط الدرجة",  C["gold"]),
            (f"🏆  {stats['best_score']}%\nأعلى درجة",    C["glt"]),
            (f"📉  {stats['worst_score']}%\nأدنى درجة",   C["orange"]),
        ]:
            b = ctk.CTkFrame(si, fg_color=C["bg2"], corner_radius=10)
            b.pack(side="left", padx=6, expand=True, fill="x")
            lbl(b, txt, F["sm"], clr, "center",
                justify="center").pack(padx=14, pady=10)

        if not history:
            lbl(self.sc,
                "لا توجد تحليلات بعد\nارفع ملف PDF وحلّله للبدء",
                F["body"], C["t3"], "center",
                justify="center").pack(pady=60)
            return

        # ── قائمة السجلات ─────────────────────────────────────
        lbl(self.sc,
            f"آخر {len(history)} تحليل",
            F["sm_b"], C["t3"]).pack(anchor="w", pady=(4,8))

        for i, rec in enumerate(history):
            sc_val  = rec["score"]
            sc_col  = (C["glt"]    if sc_val >= 75 else
                       C["gold"]   if sc_val >= 50 else C["red"])
            ct_name = rec["contract_type"]
            ct_col  = CONTRACT_TYPES.get(ct_name, {}).get("color", C["blue"])
            dt_str  = rec["analyzed_at"][:16].replace("T", "  ")

            card = ctk.CTkFrame(self.sc,
                                fg_color=C["bg1"] if i%2==0 else C["bg"],
                                corner_radius=12,
                                border_width=1, border_color=C["border"])
            card.pack(fill="x", pady=4)

            row = ctk.CTkFrame(card, fg_color="transparent")
            row.pack(fill="x", padx=16, pady=12)

            # درجة دائرية
            score_f = ctk.CTkFrame(row, fg_color=sc_col,
                                   corner_radius=24, width=52, height=52)
            score_f.pack(side="left", padx=(0,14))
            score_f.pack_propagate(False)
            ctk.CTkLabel(score_f, text=str(sc_val),
                         font=("Arial",15,"bold"),
                         text_color=C["white"]).place(relx=.5,rely=.5,anchor="center")

            # معلومات
            info_col = ctk.CTkFrame(row, fg_color="transparent")
            info_col.pack(side="left", fill="both", expand=True)

            fname = rec["pdf_filename"]
            lbl(info_col,
                fname[:48] + ("..." if len(fname)>48 else ""),
                F["body_b"], C["text"]).pack(anchor="w")

            meta_row = ctk.CTkFrame(info_col, fg_color="transparent")
            meta_row.pack(anchor="w", pady=2)

            # شارة نوع العقد
            ct_b = ctk.CTkFrame(meta_row, fg_color=ct_col, corner_radius=8)
            ct_b.pack(side="left", padx=(0,8))
            lbl(ct_b,
                f" {ct_name.split('  ')[-1] if '  ' in ct_name else ct_name[:12]} ",
                F["xs"], C["white"]).pack(padx=4, pady=2)

            lbl(meta_row, dt_str, F["xs"], C["t3"]).pack(side="left", padx=4)
            lbl(meta_row,
                f"  {rec['found_count']}/{rec['total_expected']} بنود",
                F["xs"], C["t2"]).pack(side="left")

            # المفقود
            if rec["missing_clauses"]:
                miss_txt = "مفقود: " + "، ".join(rec["missing_clauses"][:3])
                if len(rec["missing_clauses"]) > 3:
                    miss_txt += f" (+{len(rec['missing_clauses'])-3})"
                lbl(info_col, miss_txt, F["xs"], C["red"],
                    wraplength=500).pack(anchor="w")

            # مستوى
            lev_col = (C["glt"] if rec["level"] in ("قوي جداً","جيد")
                       else C["gold"] if rec["level"]=="متوسط"
                       else C["red"])
            lev_b = ctk.CTkFrame(row, fg_color=lev_col, corner_radius=8)
            lev_b.pack(side="right", padx=(14,0))
            lbl(lev_b, f" {rec['level']} ", F["xs"], C["white"]).pack(padx=6,pady=3)

# ══════════════════════════════════════════════════════════════
#  التطبيق الرئيسي
# ══════════════════════════════════════════════════════════════
class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("نظام تحليل العقود الذكي  –  v4.0  |  مشروع تخرج")
        self.geometry("1240x790")
        self.minsize(1050,680)
        self.configure(fg_color=C["bg"])
        self._center()
        self._build()

    def _center(self):
        self.update_idletasks()
        x=(self.winfo_screenwidth()-1240)//2
        y=(self.winfo_screenheight()-790)//2
        self.geometry(f"1240x790+{x}+{y}")

    def _build(self):
        TopBar(self, nav_cb=self._nav).pack(fill="x")
        body = ctk.CTkFrame(self, fg_color=C["bg"], corner_radius=0)
        body.pack(fill="both", expand=True)
        self.side = SidePanel(body)
        self.side.pack(side="left", fill="y")
        ctk.CTkFrame(body,fg_color=C["border"],width=1,corner_radius=0).pack(side="left",fill="y")
        self.content = ctk.CTkFrame(body, fg_color=C["bg"], corner_radius=0)
        self.content.pack(side="right", fill="both", expand=True)

        self.home_v     = HomeView(self.content, on_select=self._on_type)
        self.analysis_v = AnalysisView(self.content, self.side, self._nav)
        self.report_v   = ReportView(self.content)
        self.history_v  = HistoryView(self.content)
        self.img_v      = ImageAnalysisView(
            self.content,
            side           = self.side,
            nav_cb         = self._nav,
            get_state      = lambda: ST,
            analyze_fn     = analyze_rules,
            contract_types = CONTRACT_TYPES,
            save_fn        = save_analysis,
        )

        self._build_status()
        # ── تسجيل الدخول عند الإطلاق ──────────────────────
        self.after(100, self._do_login)

    def _build_status(self):
        sb = ctk.CTkFrame(self, fg_color=C["bg1"], corner_radius=0, height=30)
        sb.pack(fill="x", side="bottom")
        sb.pack_propagate(False)
        si = ctk.CTkFrame(sb, fg_color="transparent")
        si.pack(fill="x", padx=16)
        self.status = lbl(si,
            "مرحباً! ابدأ باختيار نوع العقد من الشاشة الرئيسية",
            F["xs"],C["t3"])
        self.status.pack(side="left",pady=6)
        # تحقق من المكتبات المطلوبة
        missing_libs = []
        try:
            import pdfplumber
        except ImportError:
            missing_libs.append("pdfplumber")
        if not RL_OK:
            missing_libs.append("reportlab (اختياري)")
        if missing_libs:
            lbl(si,f"⚠  تثبيت مطلوب: {', '.join(missing_libs)}  (pip install ...)",
                F["xs"],C["orange"]).pack(side="right",padx=14,pady=6)

    def _nav(self, view):
        for v in [self.home_v, self.analysis_v, self.report_v,
                  self.history_v, self.img_v]:
            v.pack_forget()
        if view=="home":
            self.home_v.pack(fill="both",expand=True)
            self.status.configure(text="الشاشة الرئيسية – اختر نوع العقد")
            self.side.update(0,[])
        elif view=="analysis":
            if not ST.contract_type:
                messagebox.showinfo("تنبيه","اختر نوع العقد أولاً")
                self.home_v.pack(fill="both",expand=True)
                return
            self.analysis_v.refresh_type()
            self.analysis_v.pack(fill="both",expand=True)
            self.status.configure(text=f"التحليل  –  {ST.contract_type}")
            done=[0]
            if ST.pdf_path:       done.append(1)
            if ST.found_headings: done.append(2)
            if ST.result:         done.append(3)
            self.side.update(1,done)
        elif view=="report":
            if not ST.result:
                messagebox.showinfo("تنبيه","قم بتحليل العقد أولاً")
                self._nav("analysis" if ST.contract_type else "home")
                return
            self.report_v.refresh()
            self.report_v.pack(fill="both",expand=True)
            self.status.configure(text="التقرير التفصيلي")
            self.side.update(4,[0,1,2,3])
        elif view=="history":
            self.history_v.pack(fill="both",expand=True)
            self.history_v.refresh()
            self.status.configure(text="سجل التحليلات")
        elif view=="image":
            self.img_v.pack(fill="both", expand=True)
            self.img_v.refresh_type()
            self.status.configure(text="تحليل صورة العقد — OCR ذكي")
        elif view=="logout":
            if messagebox.askyesno("تأكيد","هل تريد تسجيل الخروج؟"):
                ST.current_user = None
                ST.reset()
                self.status.configure(text="تم تسجيل الخروج")
                self._do_login()

    def _do_login(self):
        """يُظهر نافذة تسجيل الدخول ويُحدّث واجهة المستخدم"""
        user = show_login(self)
        if user:
            ST.current_user = user
            uname = user.get("username","")
            self.status.configure(
                text=f"مرحباً {uname}!  ابدأ باختيار نوع العقد من الشاشة الرئيسية")
            self._nav("home")
        else:
            # المستخدم أغلق نافذة الدخول → أغلق البرنامج
            self.destroy()

    def _on_type(self, name):
        if name == "__image__":
            self._nav("image")
            return
        ST.reset()
        ST.contract_type = name
        self.status.configure(text=f"تم اختيار: {name}")
        self._nav("analysis")

# ══════════════════════════════════════════════════════════════
#  نقطة الدخول
# ══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    # فحص المكتبات
    def _chk(name):
        try: __import__(name); return "✓"
        except ImportError: return "✗"

    print("═"*55)
    print("  نظام تحليل العقود  –  v4.0  |  مشروع تخرج")
    print("═"*55)
    print(f"  pdfplumber       : {_chk('pdfplumber')}")
    print(f"  scikit-learn     : {_chk('sklearn')}")
    print(f"  reportlab        : {_chk('reportlab')}  (اختياري)")
    print(f"  pytesseract      : {_chk('pytesseract')}  (اختياري - للصور الممسوحة)")
    print(f"  sentence_transf  : {_chk('sentence_transformers')}  (اختياري - دقة أعلى)")
    print(f"  matcher_mode     : {get_mode()}")
    print("═"*55)
    App().mainloop()