"""
font_manager.py  —  إدارة حجم الخط والتكبير/التصغير
═══════════════════════════════════════════════════════════════
يُوفّر:
  • FontManager: مدير مركزي لتغيير حجم الخط في الوقت الفعلي
  • ZoomBar:     شريط التكبير/التصغير (أزرار + + -)
  • make_fonts(): يُعيد قاموس الخطوط المُعدَّلة

التكامل مع main.py:
  from font_manager import FontManager, ZoomBar
  fm = FontManager()
  zoom_bar = ZoomBar(root, fm)
═══════════════════════════════════════════════════════════════
"""

import customtkinter as ctk
from typing import Callable
import config

# ══════════════════════════════════════════════════════════
#  الخطوط الأساسية (عند scale = 1.0)
# ══════════════════════════════════════════════════════════
_BASE_FONTS: dict[str, tuple] = {
    "title":   ("Arial", 26, "bold"),
    "heading": ("Arial", 22, "bold"),
    "sub":     ("Arial", 18, "bold"),
    "body":    ("Arial", 16),
    "body_b":  ("Arial", 16, "bold"),
    "sm":      ("Arial", 14),
    "sm_b":    ("Arial", 14, "bold"),
    "xs":      ("Arial", 12),
    "badge":   ("Arial", 13, "bold"),
    "btn":     ("Arial", 16, "bold"),
    "btn_sm":  ("Arial", 14, "bold"),
    "score":   ("Arial", 52, "bold"),
}

_SCALE_MIN  = 0.7
_SCALE_MAX  = 1.8
_SCALE_STEP = 0.1


def make_fonts(scale: float = 1.0) -> dict[str, tuple]:
    """
    يُعيد قاموس الخطوط مُعدَّلاً بعامل التكبير.
    مثال: scale=1.2 يُكبّر كل الخطوط 20%.
    """
    scale = max(_SCALE_MIN, min(_SCALE_MAX, scale))
    result = {}
    for name, spec in _BASE_FONTS.items():
        font_name = spec[0]
        base_size = spec[1]
        rest      = spec[2:]
        new_size  = max(10, round(base_size * scale))
        result[name] = (font_name, new_size) + rest
    return result


# ══════════════════════════════════════════════════════════
#  مدير الخطوط المركزي
# ══════════════════════════════════════════════════════════
class FontManager:
    """
    يُدير حجم الخط لكل التطبيق.
    الأدجت Widgets المسجّلة تُحدَّث تلقائياً عند التغيير.
    """

    def __init__(self):
        self._scale: float = config.get_font_scale()
        self._fonts: dict  = make_fonts(self._scale)
        self._listeners: list[Callable] = []

    # ── الخصائص ─────────────────────────────────────────
    @property
    def scale(self) -> float:
        return self._scale

    @property
    def F(self) -> dict[str, tuple]:
        """قاموس الخطوط الحالية — استخدمه بدل F الثابت في main.py."""
        return self._fonts

    # ── تغيير الحجم ──────────────────────────────────────
    def set_scale(self, scale: float) -> None:
        """يضبط عامل التكبير ويُحدّث جميع المستمعين."""
        new = max(_SCALE_MIN, min(_SCALE_MAX, round(scale, 2)))
        if new == self._scale:
            return
        self._scale = new
        self._fonts = make_fonts(new)
        config.save_font_scale(new)
        self._notify()

    def zoom_in(self) -> None:
        self.set_scale(self._scale + _SCALE_STEP)

    def zoom_out(self) -> None:
        self.set_scale(self._scale - _SCALE_STEP)

    def reset(self) -> None:
        self.set_scale(1.0)

    # ── تسجيل/إلغاء المستمعين ────────────────────────────
    def add_listener(self, cb: Callable) -> None:
        """
        يُسجّل دالة تُستدعى عند تغيير الحجم.
        cb() تُحدّث الـ widget المربوط بها.
        """
        if cb not in self._listeners:
            self._listeners.append(cb)

    def remove_listener(self, cb: Callable) -> None:
        self._listeners = [l for l in self._listeners if l != cb]

    def _notify(self) -> None:
        """يُبلّغ جميع المستمعين بالتغيير."""
        for cb in self._listeners:
            try:
                cb()
            except Exception as e:
                print(f"[FontManager] تحذير listener: {e}")

    # ── اختصارات ─────────────────────────────────────────
    def font(self, name: str) -> tuple:
        """يُعيد خط واحد بالاسم."""
        return self._fonts.get(name, self._fonts["body"])

    def bind_label(self, label: ctk.CTkLabel, font_name: str) -> None:
        """
        يُربط CTkLabel بالمدير — يُحدَّث خطه تلقائياً.
        """
        def update():
            try:
                label.configure(font=self.font(font_name))
            except Exception:
                pass
        self.add_listener(update)

    def bind_button(self, btn: ctk.CTkButton, font_name: str) -> None:
        def update():
            try:
                btn.configure(font=self.font(font_name))
            except Exception:
                pass
        self.add_listener(update)


# ══════════════════════════════════════════════════════════
#  شريط التكبير/التصغير
# ══════════════════════════════════════════════════════════
class ZoomBar(ctk.CTkFrame):
    """
    شريط صغير يحتوي على:
      🔍-  تصغير
      100% نسبة التكبير الحالية
      🔍+  تكبير
      ↺    إعادة ضبط

    يُضاف في main.py:
      zoom_bar = ZoomBar(some_frame, font_manager)
      zoom_bar.pack(side="right")
    """

    _C_BG     = "#151D35"
    _C_BORDER = "#1E2A45"
    _C_TEXT   = "#94A3B8"
    _C_HOVER  = "#1C2640"

    def __init__(self, master, fm: FontManager, **kw):
        super().__init__(master,
                         fg_color=self._C_BG,
                         corner_radius=20,
                         border_width=1,
                         border_color=self._C_BORDER,
                         **kw)
        self._fm = fm
        self._build()
        # تسجيل لتحديث نسبة العرض
        fm.add_listener(self._update_label)

    def _build(self):
        # ── زر تصغير ─────────────────────────────────────
        ctk.CTkButton(
            self, text="−", width=32, height=28,
            fg_color="transparent", hover_color=self._C_HOVER,
            text_color=self._C_TEXT, font=("Arial", 16, "bold"),
            corner_radius=14, border_width=0,
            command=self._zoom_out,
        ).pack(side="left", padx=(6, 2), pady=4)

        # ── عرض النسبة ───────────────────────────────────
        self._pct_lbl = ctk.CTkLabel(
            self, text=self._pct_text(),
            font=("Arial", 12, "bold"),
            text_color=self._C_TEXT,
            width=46,
        )
        self._pct_lbl.pack(side="left", padx=2)

        # ── زر تكبير ─────────────────────────────────────
        ctk.CTkButton(
            self, text="+", width=32, height=28,
            fg_color="transparent", hover_color=self._C_HOVER,
            text_color=self._C_TEXT, font=("Arial", 16, "bold"),
            corner_radius=14, border_width=0,
            command=self._zoom_in,
        ).pack(side="left", padx=(2, 2), pady=4)

        # ── زر إعادة ضبط ─────────────────────────────────
        ctk.CTkButton(
            self, text="↺", width=28, height=28,
            fg_color="transparent", hover_color=self._C_HOVER,
            text_color=self._C_TEXT, font=("Arial", 14),
            corner_radius=14, border_width=0,
            command=self._reset,
        ).pack(side="left", padx=(0, 6), pady=4)

    def _pct_text(self) -> str:
        return f"{int(self._fm.scale * 100)}%"

    def _update_label(self) -> None:
        try:
            self._pct_lbl.configure(text=self._pct_text())
        except Exception:
            pass

    def _zoom_in(self):
        self._fm.zoom_in()

    def _zoom_out(self):
        self._fm.zoom_out()

    def _reset(self):
        self._fm.reset()