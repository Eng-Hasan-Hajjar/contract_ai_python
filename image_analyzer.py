"""
image_analyzer.py  —  شاشة تحليل صورة العقد
══════════════════════════════════════════════════════════════
يُوفّر:
  • ImageAnalysisView  — الشاشة الكاملة (تُضاف في main.py)
  • Scanner animation  — خط يتحرك فوق الصورة أثناء القراءة
  • OCR باللغة العربية والإنجليزية
  • نفس خوارزميات تحليل العقود (analyze_rules + match_clause)

الاستخدام في main.py:
    from image_analyzer import ImageAnalysisView
    self.img_v = ImageAnalysisView(self.content, self.side, self._nav,
                                   get_state=lambda: ST,
                                   analyze_fn=analyze_rules,
                                   contract_types=CONTRACT_TYPES)
══════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import customtkinter as ctk
from tkinter import filedialog, messagebox
import threading
import time
import os
import re
from typing import Callable, Optional
from datetime import datetime

# ── مكتبات الصور ─────────────────────────────────────────
try:
    from PIL import Image, ImageTk, ImageFilter, ImageEnhance
    _HAS_PIL = True
except ImportError:
    _HAS_PIL = False

try:
    import pytesseract
    _HAS_OCR = True
except ImportError:
    _HAS_OCR = False


# ══════════════════════════════════════════════════════════
#  الألوان — متوافقة مع main.py
# ══════════════════════════════════════════════════════════
C = {
    "bg":      "#080C18", "bg1":    "#0F1525", "bg2":    "#151D35",
    "bg3":     "#1C2640", "card":   "#111829", "border": "#1E2A45",
    "bhi":     "#2A3D6A", "blue":   "#2563EB", "blt":    "#3B82F6",
    "cyan":    "#06B6D4", "purple": "#7C3AED", "gold":   "#D97706",
    "green":   "#059669", "glt":    "#10B981", "red":    "#DC2626",
    "orange":  "#EA580C", "text":   "#F1F5FF", "t2":     "#94A3B8",
    "t3":      "#4B5E82", "white":  "#FFFFFF",
    # ألوان خاصة بالـ scanner
    "scan_line":  "#00FF88",   # اللون الأخضر المضيء للخط الماسح
    "scan_glow":  "#10B98140", # توهج خفيف
}

F = {
    "heading": ("Arial", 20, "bold"),
    "sub":     ("Arial", 17, "bold"),
    "body":    ("Arial", 15),
    "body_b":  ("Arial", 15, "bold"),
    "sm":      ("Arial", 13),
    "sm_b":    ("Arial", 13, "bold"),
    "xs":      ("Arial", 11),
    "btn":     ("Arial", 15, "bold"),
    "btn_sm":  ("Arial", 13, "bold"),
    "score":   ("Arial", 48, "bold"),
}


# ══════════════════════════════════════════════════════════
#  مساعدات UI
# ══════════════════════════════════════════════════════════
def _sep(parent, color=None, pady=4):
    ctk.CTkFrame(parent, fg_color=color or C["border"],
                 height=1, corner_radius=0).pack(fill="x", pady=pady)


def _lbl(parent, text, font=None, color=None, anchor="w", **kw):
    return ctk.CTkLabel(
        parent, text=text,
        font=font or F["body"],
        text_color=color or C["text"],
        anchor=anchor, **kw
    )


def _btn(parent, text, color, cmd, width=0, height=44):
    kw = {"width": width} if width else {}
    return ctk.CTkButton(
        parent, text=text,
        fg_color=color, hover_color=C["bhi"],
        text_color=C["white"], font=F["btn"],
        corner_radius=10, height=height,
        command=cmd, **kw
    )


# ══════════════════════════════════════════════════════════
#  Scanner Canvas — الأنيميشن
# ══════════════════════════════════════════════════════════
class ScannerCanvas(ctk.CTkCanvas):
    """
    Canvas يعرض الصورة مع خط ماسح يتحرك من أعلى لأسفل.

    الاستخدام:
        sc = ScannerCanvas(parent, width=400, height=500)
        sc.set_image(pil_image)
        sc.start_scan(on_complete_callback)
        sc.stop_scan()
    """

    SCAN_SPEED   = 2      # بكسل في كل إطار
    FRAME_DELAY  = 16     # ~60 FPS
    LINE_HEIGHT  = 4      # سماكة خط الماسح
    GLOW_HEIGHT  = 20     # ارتفاع التوهج

    def __init__(self, master, **kw):
        super().__init__(
            master,
            bg=C["bg"],
            highlightthickness=0,
            **kw
        )
        self._img_tk:     Optional[ImageTk.PhotoImage] = None
        self._pil_img:    Optional[Image.Image]        = None
        self._scan_y:     int   = 0
        self._scanning:   bool  = False
        self._on_complete: Optional[Callable] = None
        self._canvas_w:   int   = int(kw.get("width",  400))
        self._canvas_h:   int   = int(kw.get("height", 500))
        self._img_y_off:  int   = 0   # إزاحة الصورة عموديًا للتمركز
        self._img_h_disp: int   = 0   # ارتفاع الصورة المعروضة

    # ── تحميل الصورة ─────────────────────────────────────
    def set_image(self, pil_img: Image.Image) -> None:
        """يُحدّث الصورة المعروضة ويُعيد ضبط الماسح."""
        self._pil_img = pil_img
        self._render_image()
        self._scan_y = 0
        self.delete("scanline")

    def _render_image(self) -> None:
        """يُعيد رسم الصورة مُناسَبة للـ canvas."""
        if not self._pil_img:
            return
        # احسب الأبعاد مع الحفاظ على النسبة
        img_w, img_h = self._pil_img.size
        canvas_w = self._canvas_w
        canvas_h = self._canvas_h
        scale    = min(canvas_w / img_w, canvas_h / img_h, 1.0)
        new_w    = int(img_w * scale)
        new_h    = int(img_h * scale)

        resized = self._pil_img.resize((new_w, new_h), Image.LANCZOS)
        self._img_tk  = ImageTk.PhotoImage(resized)
        self._img_h_disp = new_h
        x_off = (canvas_w - new_w) // 2
        y_off = (canvas_h - new_h) // 2
        self._img_y_off = y_off

        self.delete("all")
        self.create_image(x_off, y_off, anchor="nw",
                          image=self._img_tk, tags="img")

    # ── الماسح ───────────────────────────────────────────
    def start_scan(self, on_complete: Callable = None) -> None:
        """يبدأ أنيميشن المسح من أعلى الصورة."""
        if not self._pil_img:
            return
        self._scan_y      = 0
        self._scanning    = True
        self._on_complete = on_complete
        self._animate()

    def stop_scan(self) -> None:
        """يوقف المسح فوراً."""
        self._scanning = False
        self.delete("scanline")

    def _animate(self) -> None:
        """الحلقة الرئيسية للأنيميشن."""
        if not self._scanning:
            return

        canvas_w  = self._canvas_w
        y_abs     = self._img_y_off + self._scan_y   # موقع الخط على الـ canvas

        # احذف الخط القديم وارسم الجديد
        self.delete("scanline")

        # التوهج (gradient-like باستخدام مستطيلات متعددة بشفافية مختلفة)
        glow_colors = ["#10B98108", "#10B98120", "#10B98140",
                       "#00FF8860", "#00FF88B0", "#00FF88FF",
                       "#00FF88B0", "#00FF8860", "#10B98140",
                       "#10B98120", "#10B98108"]
        step = self.GLOW_HEIGHT // len(glow_colors)
        for i, gc in enumerate(glow_colors):
            gy = y_abs - self.GLOW_HEIGHT // 2 + i * step
            try:
                self.create_rectangle(
                    0, gy, canvas_w, gy + step,
                    fill=gc, outline="", tags="scanline"
                )
            except Exception:
                pass

        # الخط الرئيسي المضيء
        self.create_rectangle(
            0, y_abs - self.LINE_HEIGHT // 2,
            canvas_w, y_abs + self.LINE_HEIGHT // 2,
            fill=C["scan_line"], outline="", tags="scanline"
        )

        # تقدم الخط
        self._scan_y += self.SCAN_SPEED

        # هل وصل لنهاية الصورة؟
        if self._scan_y >= self._img_h_disp:
            self._scanning = False
            self.delete("scanline")
            if self._on_complete:
                self._on_complete()
            return

        # جدول الإطار التالي
        try:
            self.after(self.FRAME_DELAY, self._animate)
        except Exception:
            pass

    def on_resize(self, w: int, h: int) -> None:
        """يُحدّث الأبعاد عند تغيير حجم النافذة."""
        self._canvas_w = w
        self._canvas_h = h
        if self._pil_img:
            self._render_image()


# ══════════════════════════════════════════════════════════
#  استخراج النص بـ OCR
# ══════════════════════════════════════════════════════════
def _ocr_image(pil_img: Image.Image) -> str:
    """
    يُطبّق OCR على صورة ويُعيد النص.
    يُحسّن الصورة قبل OCR للحصول على دقة أفضل.
    """
    if not _HAS_OCR:
        raise ValueError(
            "مكتبة pytesseract غير مثبّتة.\n"
            "لتثبيتها: pip install pytesseract pillow\n"
            "ثم ثبّت Tesseract من: https://github.com/UB-Mannheim/tesseract/wiki"
        )

    try:
        # تحسين الصورة قبل OCR
        img = pil_img.convert("L")                    # تحويل لرمادي
        img = ImageEnhance.Contrast(img).enhance(2.0)  # زيادة التباين
        img = img.filter(ImageFilter.SHARPEN)           # تحديد الحواف

        # OCR بالعربية والإنجليزية
        text = pytesseract.image_to_string(
            img,
            lang="ara+eng",
            config="--psm 6 --oem 3"
        )
        return text.strip()

    except pytesseract.TesseractNotFoundError:
        raise ValueError(
            "Tesseract غير مثبّت على جهازك.\n"
            "حمّله من: https://github.com/UB-Mannheim/tesseract/wiki\n"
            "ثم أضف مساره إلى PATH."
        )
    except Exception as e:
        raise ValueError(f"خطأ في قراءة الصورة:\n{str(e)}")


# ══════════════════════════════════════════════════════════
#  شاشة تحليل الصورة الكاملة
# ══════════════════════════════════════════════════════════
class ImageAnalysisView(ctk.CTkFrame):
    """
    شاشة تحليل صورة العقد.

    المعاملات:
      master          — الـ parent widget
      side            — SidePanel للتحديث
      nav_cb          — دالة الانتقال بين الشاشات
      get_state       — lambda: ST  (كائن State من main.py)
      analyze_fn      — دالة analyze_rules من main.py
      contract_types  — قاموس CONTRACT_TYPES من main.py
      save_fn         — دالة save_analysis (اختياري)
    """

    # الأنواع المدعومة للصور
    IMG_TYPES = [
        ("صور العقود", "*.png *.jpg *.jpeg *.bmp *.tiff *.webp"),
        ("PNG",  "*.png"),
        ("JPEG", "*.jpg *.jpeg"),
        ("جميع الملفات", "*.*"),
    ]

    def __init__(self, master, side, nav_cb: Callable,
                 get_state: Callable,
                 analyze_fn: Callable,
                 contract_types: dict,
                 save_fn: Callable = None,
                 **kw):
        super().__init__(master, fg_color=C["bg"], corner_radius=0, **kw)
        self._side          = side
        self._nav           = nav_cb
        self._get_state     = get_state
        self._analyze_fn    = analyze_fn
        self._contract_types = contract_types
        self._save_fn       = save_fn

        self._img_path:   Optional[str]         = None
        self._pil_img:    Optional[Image.Image]  = None
        self._ocr_text:   str                   = ""
        self._busy:       bool                  = False

        if not _HAS_PIL:
            self._build_missing_lib("Pillow", "pip install pillow")
            return
        if not _HAS_OCR:
            self._build_missing_lib("pytesseract", "pip install pytesseract")
            return

        self._build()

    # ── بناء واجهة الخطأ ─────────────────────────────────
    def _build_missing_lib(self, lib_name: str, install_cmd: str) -> None:
        card = ctk.CTkFrame(self, fg_color=C["bg1"], corner_radius=16,
                            border_width=1, border_color=C["red"])
        card.pack(expand=True, padx=60, pady=60)
        _lbl(card, "⚠", ("Arial", 60), C["orange"], "center").pack(pady=(30, 10))
        _lbl(card, f"مكتبة {lib_name} غير مثبّتة",
             F["sub"], C["text"], "center").pack()
        _lbl(card, f"لتثبيتها:\n{install_cmd}",
             F["body"], C["t2"], "center", justify="center").pack(pady=(10, 20))

        # ── زر التثبيت التلقائي ──────────────────────────
        def _auto_install():
            import subprocess, sys, platform
            btn.configure(state="disabled", text="⏳  جارٍ التثبيت...")

            def _run():
                try:
                    if platform.system() == "Windows":
                        # تثبيت Tesseract بـ winget
                        subprocess.run(
                            ["winget", "install", "--id",
                             "UB-Mannheim.TesseractOCR",
                             "--accept-source-agreements",
                             "--accept-package-agreements"],
                            check=True, capture_output=True
                        )
                    # تثبيت pytesseract و pillow
                    subprocess.run(
                        [sys.executable, "-m", "pip", "install",
                         "pytesseract", "pillow", "--quiet"],
                        check=True, capture_output=True
                    )
                    self.after(0, lambda: messagebox.showinfo(
                        "تم التثبيت ✅",
                        "تم تثبيت Tesseract و pytesseract بنجاح!\n\n"
                        "أعد تشغيل البرنامج لتفعيل ميزة تحليل الصور."
                    ))
                except Exception as e:
                    self.after(0, lambda err=str(e): messagebox.showerror(
                        "فشل التثبيت",
                        f"فشل التثبيت التلقائي:\n{err}\n\n"
                        "يرجى التثبيت يدوياً:\n"
                        "1. افتح PowerShell كمدير\n"
                        "2. اكتب: winget install UB-Mannheim.TesseractOCR\n"
                        "3. أعد تشغيل البرنامج"
                    ))
                finally:
                    self.after(0, lambda: btn.configure(
                        state="normal", text="🔄  إعادة محاولة التثبيت"))

            threading.Thread(target=_run, daemon=True).start()

        btn = ctk.CTkButton(
            card, text="⚡  تثبيت Tesseract تلقائياً",
            fg_color=C["blue"], hover_color=C["blt"],
            text_color=C["white"], font=F["btn"],
            height=46, corner_radius=10,
            command=_auto_install
        )
        btn.pack(fill="x", padx=30, pady=(0, 10))

        # زر التثبيت اليدوي
        def _open_manual():
            import webbrowser
            webbrowser.open("https://github.com/UB-Mannheim/tesseract/wiki")

        ctk.CTkButton(
            card, text="🌐  فتح صفحة التثبيت اليدوي",
            fg_color="transparent", hover_color=C["bg2"],
            text_color=C["t2"], font=F["btn_sm"],
            height=38, corner_radius=10,
            border_width=1, border_color=C["border"],
            command=_open_manual
        ).pack(fill="x", padx=30, pady=(0, 30))

    # ── بناء الواجهة الكاملة ────────────────────────────
    def _build(self) -> None:
        # ── شريط المعلومات العلوي ─────────────────────
        info_bar = ctk.CTkFrame(self, fg_color=C["bg1"], corner_radius=12,
                                border_width=1, border_color=C["border"])
        info_bar.pack(fill="x", padx=16, pady=(12, 8))
        ib = ctk.CTkFrame(info_bar, fg_color="transparent")
        ib.pack(fill="x", padx=18, pady=12)

        # نوع العقد
        self._type_badge = ctk.CTkLabel(
            ib, text="", font=F["body_b"],
            text_color=C["white"], fg_color=C["purple"],
            corner_radius=10, padx=14, pady=6
        )
        self._type_badge.pack(side="left")

        self._file_lbl = _lbl(ib, "لم يتم اختيار صورة بعد", F["sm"], C["t3"])
        self._file_lbl.pack(side="left", padx=16)

        ctk.CTkButton(
            ib, text="← تغيير النوع", width=145, height=36,
            fg_color="transparent", hover_color=C["bg3"],
            text_color=C["t2"], border_width=1, border_color=C["border"],
            corner_radius=10, font=F["sm_b"],
            command=lambda: self._nav("home")
        ).pack(side="right")

        # ── عمودان رئيسيان ──────────────────────────────
        cols = ctk.CTkFrame(self, fg_color="transparent")
        cols.pack(fill="both", expand=True, padx=16, pady=(0, 8))

        # يسار — الصورة والماسح
        left = ctk.CTkFrame(cols, fg_color=C["bg1"], corner_radius=14,
                            border_width=1, border_color=C["border"])
        left.pack(side="left", fill="both", expand=True, padx=(0, 8))
        self._build_left(left)

        # يمين — النتائج
        right = ctk.CTkFrame(cols, fg_color=C["bg1"], corner_radius=14,
                             border_width=1, border_color=C["border"])
        right.pack(side="right", fill="both", expand=True, padx=(8, 0))
        self._build_right(right)

        # ── شريط الأزرار السفلي ──────────────────────────
        self._build_actions()

    def _build_left(self, parent) -> None:
        # العنوان
        hdr = ctk.CTkFrame(parent, fg_color=C["bg2"], corner_radius=10)
        hdr.pack(fill="x", padx=12, pady=(12, 6))
        _lbl(hdr, "🖼  رفع صورة العقد", F["sub"], C["text"]).pack(
            side="left", padx=14, pady=10)
        self._ocr_mode_lbl = _lbl(hdr, "OCR جاهز ✓", F["xs"], C["glt"])
        self._ocr_mode_lbl.pack(side="right", padx=12)

        # منطقة رفع الصورة (Drag zone)
        self._dz = ctk.CTkFrame(
            parent, fg_color=C["bg2"], corner_radius=12,
            border_width=2, border_color=C["bhi"],
            cursor="hand2", height=60
        )
        self._dz.pack(fill="x", padx=12, pady=6)
        self._dz.pack_propagate(False)
        dzc = ctk.CTkFrame(self._dz, fg_color="transparent")
        dzc.place(relx=.5, rely=.5, anchor="center")
        self._dz_icon = _lbl(dzc, "🖼", ("Arial", 28), anchor="center")
        self._dz_icon.pack()
        self._dz_txt = _lbl(dzc, "انقر لاختيار صورة العقد",
                             F["sm_b"], C["cyan"], "center")
        self._dz_txt.pack(pady=2)
        self._dz_hint = _lbl(dzc, "PNG  •  JPG  •  JPEG  •  TIFF",
                              F["xs"], C["t3"], "center")
        self._dz_hint.pack()
        for w in [self._dz, dzc, self._dz_icon, self._dz_txt, self._dz_hint]:
            w.bind("<Button-1>", lambda e: self._pick_image())

        # شريط التقدم
        self._prog_lbl = _lbl(parent, "", F["xs"], C["t3"])
        self._prog_lbl.pack(anchor="w", padx=14, pady=(2, 0))
        self._prog = ctk.CTkProgressBar(
            parent, height=6, corner_radius=3,
            fg_color=C["bg2"], progress_color=C["purple"])
        self._prog.pack(fill="x", padx=12, pady=(2, 8))
        self._prog.set(0)

        # ── Scanner Canvas ─────────────────────────────
        scan_frame = ctk.CTkFrame(parent, fg_color=C["bg"], corner_radius=10,
                                  border_width=1, border_color=C["border"])
        scan_frame.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        self._scan_label = _lbl(scan_frame, "🖼  سيظهر هنا خط المسح الضوئي\nعند تحميل الصورة",
                                 F["body"], C["t3"], "center", justify="center")
        self._scan_label.pack(expand=True)

        # ScannerCanvas يُنشأ لاحقاً عند اختيار الصورة
        self._scanner:   Optional[ScannerCanvas] = None
        self._scan_frame = scan_frame

    def _build_right(self, parent) -> None:
        hdr = ctk.CTkFrame(parent, fg_color=C["bg2"], corner_radius=10)
        hdr.pack(fill="x", padx=12, pady=(12, 6))
        _lbl(hdr, "📊  نتائج تحليل الصورة", F["sub"], C["text"]).pack(
            side="left", padx=14, pady=10)
        self._res_status = _lbl(hdr, "بانتظار المسح...", F["sm"], C["t3"])
        self._res_status.pack(side="right", padx=14)

        self._result_box = ctk.CTkScrollableFrame(
            parent, fg_color=C["bg"], corner_radius=10,
            border_width=1, border_color=C["border"])
        self._result_box.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        _lbl(self._result_box,
             "🖼\n\nارفع صورة العقد\nثم اضغط «مسح وتحليل»\nليظهر هنا التقرير",
             F["body"], C["t3"], "center", justify="center").pack(expand=True, pady=50)

    def _build_actions(self) -> None:
        bar = ctk.CTkFrame(self, fg_color=C["bg1"], corner_radius=12,
                           border_width=1, border_color=C["border"])
        bar.pack(fill="x", padx=16, pady=(0, 12))
        inner = ctk.CTkFrame(bar, fg_color="transparent")
        inner.pack(fill="x", padx=18, pady=12)

        # زر رفع الصورة
        _btn(inner, "🖼  اختيار صورة", C["purple"],
             self._pick_image, height=48).pack(side="left", padx=(0, 10))

        # زر المسح والتحليل
        self._btn_scan = ctk.CTkButton(
            inner, text="📡  مسح وتحليل",
            width=220, height=48,
            fg_color=C["blue"], hover_color=C["blt"],
            text_color=C["white"], font=F["btn"],
            corner_radius=10, state="disabled",
            command=self._start_scan
        )
        self._btn_scan.pack(side="left", padx=(0, 10))

        # زر عرض التقرير
        self._btn_report = ctk.CTkButton(
            inner, text="📄  عرض التقرير",
            width=160, height=48,
            fg_color=C["glt"], hover_color=C["green"],
            text_color=C["white"], font=F["btn"],
            corner_radius=10, state="disabled",
            command=lambda: self._nav("report")
        )
        self._btn_report.pack(side="left")

        # درجة القوة
        sc_card = ctk.CTkFrame(inner, fg_color=C["bg2"], corner_radius=12,
                               border_width=1, border_color=C["bhi"])
        sc_card.pack(side="right")
        self._score_lbl = ctk.CTkLabel(
            sc_card, text="—", font=F["score"], text_color=C["t2"])
        self._score_lbl.pack(padx=22, pady=(8, 0))
        _lbl(sc_card, "قوة العقد", F["sm"], C["t3"], "center").pack(padx=22, pady=(0, 8))

    # ══════════════════════════════════════════════════════
    #  منطق اختيار الصورة
    # ══════════════════════════════════════════════════════
    def refresh_type(self) -> None:
        """يُحدّث شارة نوع العقد من ST."""
        st   = self._get_state()
        ct   = st.contract_type or ""
        info = self._contract_types.get(ct, {})
        self._type_badge.configure(
            text=f"  {ct}  ",
            fg_color=info.get("color", C["purple"])
        )

    def _pick_image(self) -> None:
        path = filedialog.askopenfilename(
            title="اختر صورة العقد",
            filetypes=self.IMG_TYPES
        )
        if not path:
            return

        try:
            img = Image.open(path)
            img.verify()          # تحقق أنها صورة صالحة
            img = Image.open(path)  # أعد الفتح بعد verify
        except Exception as e:
            messagebox.showerror("خطأ", f"الملف المحدد ليس صورة صالحة:\n{e}")
            return

        self._img_path  = path
        self._pil_img   = img
        self._ocr_text  = ""

        fname = os.path.basename(path)
        size  = os.path.getsize(path) // 1024
        w, h  = img.size

        # تحديث منطقة الرفع
        self._dz_icon.configure(text="✅")
        self._dz_txt.configure(
            text=fname[:42] + ("..." if len(fname) > 42 else ""),
            text_color=C["glt"]
        )
        self._dz_hint.configure(
            text=f"{w}×{h}  •  {size} KB",
            text_color=C["t2"]
        )
        self._dz.configure(border_color=C["glt"])
        self._file_lbl.configure(
            text=f"🖼  {fname}  ({size} KB  —  {w}×{h})",
            text_color=C["t2"]
        )

        # أنشئ/حدّث ScannerCanvas
        self._setup_scanner()
        self._btn_scan.configure(state="normal")
        self._prog.set(0)
        self._prog_lbl.configure(text="الصورة جاهزة — اضغط «مسح وتحليل»",
                                  text_color=C["cyan"])

    def _setup_scanner(self) -> None:
        """يُنشئ ScannerCanvas ويُحمّل الصورة فيه."""
        # احسب الحجم المتاح
        self._scan_frame.update_idletasks()
        w = max(self._scan_frame.winfo_width(),  380)
        h = max(self._scan_frame.winfo_height(), 300)

        # احذف الـ label وأنشئ Canvas جديد
        for widget in self._scan_frame.winfo_children():
            widget.destroy()

        self._scanner = ScannerCanvas(
            self._scan_frame,
            width=w, height=h,
        )
        self._scanner.pack(fill="both", expand=True)
        self._scanner.set_image(self._pil_img)

        # ربط resize
        self._scan_frame.bind("<Configure>", self._on_frame_resize)

    def _on_frame_resize(self, event) -> None:
        if self._scanner and self._pil_img:
            self._scanner.on_resize(event.width, event.height)

    # ══════════════════════════════════════════════════════
    #  المسح والتحليل
    # ══════════════════════════════════════════════════════
    def _start_scan(self) -> None:
        """يبدأ أنيميشن المسح ثم OCR ثم التحليل."""
        if self._busy or not self._pil_img:
            return

        st = self._get_state()
        if not st.contract_type:
            messagebox.showwarning(
                "لم يتم اختيار نوع العقد",
                "⚠  يرجى الذهاب للشاشة الرئيسية\nواختيار نوع العقد أولاً."
            )
            return

        self._busy = True
        self._btn_scan.configure(state="disabled", text="⏳  جارٍ المسح...")
        self._res_status.configure(text="يُفحص...", text_color=C["cyan"])
        self._prog.set(0)
        self._prog_lbl.configure(text="يُجهّز خط المسح...", text_color=C["t3"])

        # إعادة ضبط الماسح
        if self._scanner:
            self._scanner.set_image(self._pil_img)

        # ابدأ الأنيميشن — عند انتهائه يبدأ OCR
        if self._scanner:
            self._scanner.start_scan(on_complete=self._on_scan_done)
        else:
            self._on_scan_done()

        # شريط التقدم يتحرك بالتوازي
        self._animate_progress()

    def _animate_progress(self) -> None:
        """يُحرّك شريط التقدم أثناء المسح."""
        if not self._busy:
            return
        current = self._prog.get()
        if current < 0.85:
            self._prog.set(current + 0.008)
            self._prog_lbl.configure(
                text=f"جارٍ مسح الصورة...  {int(current * 100)}%",
                text_color=C["t3"]
            )
            try:
                self.after(50, self._animate_progress)
            except Exception:
                pass

    def _on_scan_done(self) -> None:
        """يُستدعى عند انتهاء أنيميشن المسح → ابدأ OCR."""
        self._prog.set(0.88)
        self._prog_lbl.configure(text="جارٍ قراءة النص بـ OCR...", text_color=C["gold"])
        threading.Thread(target=self._ocr_thread, daemon=True).start()

    def _ocr_thread(self) -> None:
        """خيط منفصل لـ OCR (لا يجمّد الواجهة)."""
        try:
            text = _ocr_image(self._pil_img)
            self._ocr_text = text
            self.after(0, self._on_ocr_done, text)
        except ValueError as e:
            self.after(0, lambda msg=str(e): self._on_ocr_error(msg))

    def _on_ocr_done(self, text: str) -> None:
        """OCR انتهى بنجاح → ابدأ التحليل."""
        self._prog.set(0.95)
        self._prog_lbl.configure(text="جارٍ تحليل البنود...", text_color=C["cyan"])

        if not text.strip():
            self._on_ocr_error(
                "لم يُستخرج أي نص من الصورة.\n"
                "تأكد أن الصورة واضحة وذات دقة كافية."
            )
            return

        # استخرج العناوين من النص
        threading.Thread(target=self._analyze_thread, args=(text,), daemon=True).start()

    def _on_ocr_error(self, msg: str) -> None:
        self._busy = False
        self._btn_scan.configure(state="normal", text="📡  إعادة المسح")
        self._res_status.configure(text="✗  فشل", text_color=C["red"])
        self._prog.set(0)
        self._prog_lbl.configure(text="✗  فشل القراءة", text_color=C["red"])
        messagebox.showerror("خطأ في OCR", msg)

    def _analyze_thread(self, text: str) -> None:
        """يستخرج العناوين ويُحلّل البنود."""
        try:
            # استخراج العناوين من النص
            from pdf_reader import is_heading, fix_arabic
            fixed_text = fix_arabic(text)
            heads = []
            seen  = set()
            for i, line in enumerate(fixed_text.split("\n")):
                line_s = line.strip()
                if line_s and is_heading(line_s):
                    k = re.sub(r'\s+', ' ', line_s)[:50]
                    if k not in seen:
                        seen.add(k)
                        heads.append({
                            "title": line_s[:100],
                            "page":  1,
                            "bold":  len(line_s) < 55,
                            "inline": False,
                        })

            # حفظ في ST
            st = self._get_state()
            st.raw_text       = fixed_text
            st.found_headings = heads

            # التحليل
            ct   = st.contract_type or ""
            info = self._contract_types.get(ct, {})
            exp  = info.get("clauses", [])
            res  = self._analyze_fn(heads, fixed_text, exp)
            st.result = res

            self.after(0, self._show_result, res, info, len(heads))

        except Exception as e:
            self.after(0, lambda msg=str(e): self._on_ocr_error(msg))

    # ══════════════════════════════════════════════════════
    #  عرض النتائج
    # ══════════════════════════════════════════════════════
    def _show_result(self, res: dict, info: dict, heads_count: int) -> None:
        self._busy = False
        self._btn_scan.configure(state="normal", text="📡  إعادة المسح")
        self._res_status.configure(text="✓  اكتمل", text_color=C["glt"])
        self._prog.set(1.0)
        self._prog_lbl.configure(
            text=f"✓  اكتمل  —  {heads_count} عنوان مستخرج",
            text_color=C["glt"]
        )

        # نظّف منطقة النتائج
        for w in self._result_box.winfo_children():
            w.destroy()

        score   = res.get("score",   0)
        level   = res.get("level",   "—")
        lev_col = res.get("level_color", C["t2"])
        found   = res.get("found",   {})
        missing = res.get("missing", [])
        risks   = res.get("risks",   [])
        col     = info.get("color",  C["blue"])

        # تحديث درجة الزاوية
        sc_col = C["glt"] if score >= 75 else C["gold"] if score >= 50 else C["red"]
        self._score_lbl.configure(text=f"{score}%", text_color=sc_col)

        # ── بطاقة الدرجة ─────────────────────────────
        sc_card = ctk.CTkFrame(self._result_box, fg_color=C["bg1"],
                               corner_radius=14, border_width=2,
                               border_color=lev_col)
        sc_card.pack(fill="x", padx=6, pady=(6, 10))
        si = ctk.CTkFrame(sc_card, fg_color="transparent")
        si.pack(padx=20, pady=16)

        _lbl(si, "🖼  تحليل الصورة", F["sm_b"], C["purple"], "center").pack()
        _lbl(si, f"{score}", F["score"], lev_col, "center").pack()
        _lbl(si, "من 100 — قوة العقد", F["body"], C["t2"], "center").pack(pady=(2, 4))

        pb = ctk.CTkProgressBar(si, height=14, corner_radius=7,
                                 fg_color=C["bg2"], progress_color=lev_col, width=280)
        pb.pack(pady=4)
        pb.set(score / 100)
        _lbl(si, f"المستوى:  {level}", F["sub"], lev_col, "center").pack(pady=(4, 0))

        stats = ctk.CTkFrame(si, fg_color="transparent")
        stats.pack(pady=8)
        for txt, clr in [
            (f"✓  {res.get('total_found', 0)}\nبند موجود",  C["glt"]),
            (f"✗  {len(missing)}\nبند مفقود",               C["red"]),
            (f"🖼  {heads_count}\nعنوان OCR",                C["purple"]),
        ]:
            b = ctk.CTkFrame(stats, fg_color=C["bg2"], corner_radius=10)
            b.pack(side="left", padx=6)
            _lbl(b, txt, F["sm_b"], clr, "center",
                 justify="center").pack(padx=14, pady=8)

        # ── البنود الموجودة ────────────────────────────
        self._sec("📊  البنود المطابقة", col)
        if found:
            for clause_name, cinfo in found.items():
                str_  = cinfo.get("strength", "")
                bold_ = cinfo.get("bold", False)
                sub_  = cinfo.get("sub_count", 0)
                str_c = (C["glt"]    if str_ == "قوي"   else
                         C["cyan"]   if str_ == "جيد"   else
                         C["gold"]   if str_ == "متوسط" else
                         C["orange"] if str_ == "مقبول" else C["red"])
                row = ctk.CTkFrame(self._result_box, fg_color=C["bg2"],
                                   corner_radius=8, border_width=1,
                                   border_color=C["border"])
                row.pack(fill="x", padx=6, pady=3)
                ri = ctk.CTkFrame(row, fg_color="transparent")
                ri.pack(fill="x", padx=12, pady=8)
                _lbl(ri, "✓", F["body_b"], C["glt"], width=26).pack(side="left")
                _lbl(ri, clause_name, F["body"], C["text"],
                     anchor="w").pack(side="left", padx=8, fill="x", expand=True)
                rb = ctk.CTkFrame(ri, fg_color="transparent")
                rb.pack(side="right")
                sb2 = ctk.CTkFrame(rb, fg_color=str_c, corner_radius=8)
                sb2.pack(side="left", padx=3)
                _lbl(sb2, f" {str_} ", F["xs"], C["white"]).pack(padx=5, pady=3)
        else:
            _lbl(self._result_box,
                 "لم يُعثر على بنود مطابقة من الصورة",
                 F["body"], C["t3"], "center").pack(pady=12)

        # ── البنود المفقودة ────────────────────────────
        if missing:
            self._sec("❌  البنود المفقودة", C["red"])
            for m in missing:
                row = ctk.CTkFrame(self._result_box, fg_color=C["bg"],
                                   corner_radius=8, border_width=1,
                                   border_color=C["border"])
                row.pack(fill="x", padx=6, pady=3)
                ri = ctk.CTkFrame(row, fg_color="transparent")
                ri.pack(fill="x", padx=12, pady=8)
                _lbl(ri, "✗", F["body_b"], C["red"], width=26).pack(side="left")
                _lbl(ri, m, F["body"], C["t3"],
                     anchor="w").pack(side="left", padx=8, fill="x", expand=True)
                mb = ctk.CTkFrame(ri, fg_color=C["red"], corner_radius=8)
                mb.pack(side="right")
                _lbl(mb, " مفقود ", F["xs"], C["white"]).pack(padx=5, pady=3)

        # ── التنبيهات ─────────────────────────────────
        if risks:
            self._sec("⚠  التنبيهات", C["orange"])
            for r in risks:
                rc = (C["red"]    if r["level"] == "عالي"  else
                      C["orange"] if r["level"] == "متوسط" else C["glt"])
                rf = ctk.CTkFrame(self._result_box, fg_color=C["bg2"],
                                  corner_radius=10, border_width=1,
                                  border_color=rc)
                rf.pack(fill="x", padx=6, pady=4)
                rh = ctk.CTkFrame(rf, fg_color="transparent")
                rh.pack(fill="x", padx=14, pady=(8, 4))
                _lbl(rh, f"● {r['title']}", F["body_b"], rc).pack(side="left")
                rlb = ctk.CTkFrame(rh, fg_color=rc, corner_radius=10)
                rlb.pack(side="right")
                _lbl(rlb, f" {r['level']} ", F["sm_b"], C["white"]).pack(padx=6, pady=3)
                _lbl(rf, r["desc"], F["body"], C["t2"],
                     wraplength=340, justify="right", anchor="e").pack(
                    anchor="e", padx=14, pady=(0, 8))

        # ── تفعيل زر التقرير ─────────────────────────
        self._btn_report.configure(state="normal")
        if self._side:
            self._side.update(4, [0, 1, 2, 3])

        # ── حفظ في قاعدة البيانات ────────────────────
        st = self._get_state()
        if self._save_fn and st.current_user:
            try:
                self._save_fn(
                    user_id=st.current_user["id"],
                    result=res,
                    pdf_path=self._img_path or "",
                    contract_type=st.contract_type or "",
                )
            except Exception as e:
                print(f"[ImageAnalysisView] save_analysis: {e}")

    def _sec(self, title: str, color: str) -> None:
        f = ctk.CTkFrame(self._result_box, fg_color=C["bg2"], corner_radius=10)
        f.pack(fill="x", padx=4, pady=(10, 2))
        _lbl(f, title, F["sub"], color).pack(anchor="w", padx=14, pady=10)