"""
negotiation/ui.py
══════════════════════════════════════════════════════════════
شاشة إدارة التفاوض — تُدمج في main.py بسطرين.

الاستخدام في main.py:
  from negotiation.ui import NegotiationView
  self.neg_v = NegotiationView(self.content, get_user=lambda: ST.current_user)
══════════════════════════════════════════════════════════════
"""

from __future__ import annotations
import customtkinter as ctk
from tkinter import messagebox
from typing import Callable, Optional

from negotiation.db_negotiation import (
    ClauseStatus, SessionStatus, STATUS_AR,
    create_session, get_session, close_session,
    get_user_sessions, get_clauses, get_clause_history,
    add_clause, respond_party_b, save_suggestion, agree_clause,
)
from negotiation.engine import analyze_gap, suggest_clause, session_summary


# ══════════════════════════════════════════════════════════════
#  الهوية البصرية — متوافقة مع main.py
# ══════════════════════════════════════════════════════════════
C = {
    "bg":     "#080C18", "bg1":   "#0F1525", "bg2":  "#151D35",
    "bg3":    "#1C2640", "card":  "#111829", "border":"#1E2A45",
    "bhi":    "#2A3D6A", "blue":  "#2563EB", "blt":  "#3B82F6",
    "cyan":   "#06B6D4", "purple":"#7C3AED", "gold": "#D97706",
    "green":  "#059669", "glt":   "#10B981", "red":  "#DC2626",
    "orange": "#EA580C", "text":  "#F1F5FF", "t2":   "#94A3B8",
    "t3":     "#4B5E82", "white": "#FFFFFF",
    # ألوان التفاوض
    "pa":     "#1E3A8A",  # الطرف الأول — أزرق
    "pb":     "#4C1D95",  # الطرف الثاني — بنفسجي
    "sys":    "#064E3B",  # مقترح النظام — أخضر
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
}

# لون كل حالة
STATUS_COLOR = {
    ClauseStatus.PENDING:  C["gold"],
    ClauseStatus.ACCEPTED: C["glt"],
    ClauseStatus.REJECTED: C["red"],
    ClauseStatus.MODIFIED: C["cyan"],
    ClauseStatus.AGREED:   C["green"],
    "suggested":           C["purple"],
}


# ══════════════════════════════════════════════════════════════
#  مساعدات UI — دوال صغيرة نظيفة
# ══════════════════════════════════════════════════════════════
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


def _btn(parent, text: str, color: str, cmd: Callable,
         width: int = 0, height: int = 40) -> ctk.CTkButton:
    kw = {"width": width} if width else {}
    return ctk.CTkButton(
        parent, text=text,
        fg_color=color, hover_color=C["bg3"],
        text_color=C["white"], font=F["btn_sm"],
        corner_radius=10, height=height,
        command=cmd, **kw
    )


def _entry(parent, placeholder: str, height: int = 42) -> ctk.CTkEntry:
    return ctk.CTkEntry(
        parent,
        placeholder_text=placeholder,
        height=height, corner_radius=10,
        fg_color=C["bg2"], border_color=C["bhi"],
        text_color=C["text"],
        placeholder_text_color=C["t3"],
        font=F["body"],
    )


def _textbox(parent, h: int = 100) -> ctk.CTkTextbox:
    return ctk.CTkTextbox(
        parent, height=h,
        fg_color=C["bg2"], border_color=C["bhi"],
        border_width=1, corner_radius=10,
        text_color=C["text"], font=F["body"],
        wrap="word",
    )


def _badge(parent, text: str, color: str) -> ctk.CTkFrame:
    f = ctk.CTkFrame(parent, fg_color=color, corner_radius=8)
    _lbl(f, f"  {text}  ", F["xs"], C["white"]).pack(padx=4, pady=3)
    return f


# ══════════════════════════════════════════════════════════════
#  نافذة إنشاء جلسة جديدة
# ══════════════════════════════════════════════════════════════
class _NewSessionDlg(ctk.CTkToplevel):
    def __init__(self, master, user_id: int, on_ok: Callable):
        super().__init__(master)
        self._user_id = user_id
        self._on_ok   = on_ok
        self.title("إنشاء جلسة تفاوض جديدة")
        self.geometry("520x560")
        self.minsize(480, 520)
        self.resizable(True, True)
        self.configure(fg_color=C["bg"])
        self._center()
        self._build()
        self.grab_set(); self.lift(); self.focus_force()

    def _center(self):
        self.update_idletasks()
        x = (self.winfo_screenwidth()  - 520) // 2
        y = (self.winfo_screenheight() - 560) // 2
        self.geometry(f"520x560+{x}+{y}")

    def _build(self):
        # ── رأس ثابت ─────────────────────────────────────────
        hdr = ctk.CTkFrame(self, fg_color=C["bg1"], corner_radius=0)
        hdr.pack(fill="x", side="top")
        ctk.CTkFrame(hdr, fg_color=C["blue"], height=4, corner_radius=0).pack(fill="x")
        _lbl(hdr, "  🤝  جلسة تفاوض جديدة", F["sub"], C["text"]).pack(padx=16, pady=14)

        # ── أزرار ثابتة في الأسفل ─────────────────────────────
        footer = ctk.CTkFrame(self, fg_color=C["bg1"], corner_radius=0)
        footer.pack(fill="x", side="bottom", padx=0, pady=0)
        ctk.CTkFrame(footer, fg_color=C["border"], height=1, corner_radius=0).pack(fill="x")
        btn_row = ctk.CTkFrame(footer, fg_color="transparent")
        btn_row.pack(fill="x", padx=20, pady=12)

        self._err = _lbl(btn_row, "", F["xs"], C["red"])
        self._err.pack(anchor="w", pady=(0, 6))

        _btn(btn_row, "✅  إنشاء الجلسة وحفظها", C["blue"],
             self._create, height=48).pack(fill="x", pady=(0, 6))
        _btn(btn_row, "✕  إلغاء", C["bg2"],
             self.destroy, height=38).pack(fill="x")

        # ── حقول الإدخال في المنتصف ──────────────────────────
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=24, pady=(12, 8))

        fields = [
            ("عنوان الجلسة *",     "مثال: التفاوض على بنود عقد التوريد", "e_title"),
            ("اسم الطرف الأول *",  "مثال: شركة النور للتجارة",            "e_a"),
            ("اسم الطرف الثاني *", "مثال: مؤسسة الشرق للاستيراد",         "e_b"),
            ("نوع العقد (اختياري)","مثال: عقد توريد تجاري",               "e_ct"),
        ]
        for label, ph, attr in fields:
            _lbl(body, label, F["sm_b"], C["t2"]).pack(anchor="w", pady=(10, 2))
            e = _entry(body, ph)
            e.pack(fill="x")
            setattr(self, attr, e)

        # Enter يُنشئ الجلسة مباشرة
        for attr in ("e_title", "e_a", "e_b", "e_ct"):
            getattr(self, attr).bind("<Return>", lambda e: self._create())

    def _create(self):
        title = self.e_title.get().strip()
        a     = self.e_a.get().strip()
        b     = self.e_b.get().strip()
        ct    = self.e_ct.get().strip()
        if not title:
            self._err.configure(text="⚠  عنوان الجلسة مطلوب"); return
        if not a or not b:
            self._err.configure(text="⚠  أسماء الطرفين مطلوبة"); return
        sid = create_session(self._user_id, title, a, b, ct)
        self.destroy()
        self._on_ok(sid)


# ══════════════════════════════════════════════════════════════
#  نافذة إضافة بند (المدير يدخل موقف الطرف الأول)
# ══════════════════════════════════════════════════════════════
class _AddClauseDlg(ctk.CTkToplevel):
    def __init__(self, master, session: dict, on_ok: Callable):
        super().__init__(master)
        self._session = session
        self._on_ok   = on_ok
        self.title("إضافة بند للتفاوض")
        self.geometry("580x540")
        self.minsize(520, 500)
        self.resizable(True, True)
        self.configure(fg_color=C["bg"])
        self._center()
        self._build()
        self.grab_set(); self.lift(); self.focus_force()

    def _center(self):
        self.update_idletasks()
        x = (self.winfo_screenwidth()  - 580) // 2
        y = (self.winfo_screenheight() - 540) // 2
        self.geometry(f"580x540+{x}+{y}")

    def _build(self):
        # ── رأس ثابت ─────────────────────────────────────────
        hdr = ctk.CTkFrame(self, fg_color=C["pa"], corner_radius=0)
        hdr.pack(fill="x", side="top")
        ctk.CTkFrame(hdr, fg_color=C["blt"], height=3, corner_radius=0).pack(fill="x")
        _lbl(hdr, "  📄  إضافة بند جديد", F["sub"], C["white"]).pack(padx=16, pady=12)

        # ── أزرار ثابتة في الأسفل ─────────────────────────────
        footer = ctk.CTkFrame(self, fg_color=C["bg1"], corner_radius=0)
        footer.pack(fill="x", side="bottom")
        ctk.CTkFrame(footer, fg_color=C["border"], height=1, corner_radius=0).pack(fill="x")
        btn_row = ctk.CTkFrame(footer, fg_color="transparent")
        btn_row.pack(fill="x", padx=20, pady=12)

        self._err = _lbl(btn_row, "", F["xs"], C["red"])
        self._err.pack(anchor="w", pady=(0, 6))

        btns = ctk.CTkFrame(btn_row, fg_color="transparent")
        btns.pack(fill="x")
        _btn(btns, "➕  إضافة البند وحفظه", C["blue"],
             self._add, height=46).pack(side="left", expand=True, fill="x", padx=(0, 8))
        _btn(btns, "✕  إلغاء", C["bg2"],
             self.destroy, width=110, height=46).pack(side="right")

        # ── حقول الإدخال ─────────────────────────────────────
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=24, pady=12)

        _lbl(body, "عنوان البند *", F["sm_b"], C["t2"]).pack(anchor="w", pady=(0, 4))
        self._e_title = _entry(body, "مثال: بند الدفع والسداد")
        self._e_title.pack(fill="x", pady=(0, 12))

        name_a = self._session.get("party_a_name", "الطرف الأول")
        _lbl(body, f"موقف {name_a} *", F["sm_b"], C["blt"]).pack(anchor="w", pady=(0, 4))
        self._tb_a = _textbox(body, h=130)
        self._tb_a.pack(fill="x")

    def _add(self):
        title = self._e_title.get().strip()
        text_a = self._tb_a.get("0.0", "end").strip()
        if not title:
            self._err.configure(text="⚠  عنوان البند مطلوب"); return
        if not text_a:
            self._err.configure(text="⚠  موقف الطرف الأول مطلوب"); return
        add_clause(self._session["id"], title, text_a)
        self.destroy()
        self._on_ok()


# ══════════════════════════════════════════════════════════════
#  نافذة تفاصيل البند + جميع الإجراءات
# ══════════════════════════════════════════════════════════════
class _ClauseDetailDlg(ctk.CTkToplevel):
    """
    نافذة منبثقة تعرض:
    • موقف الطرف الأول
    • إدخال موقف الطرف الثاني (قبول / رفض / تعديل)
    • تحليل الفجوة
    • الصيغة المقترحة من النظام
    • إقرار البند النهائي
    """

    def __init__(self, master, clause: dict, session: dict, on_close: Callable):
        super().__init__(master)
        self._clause  = clause
        self._session = session
        self._on_close = on_close
        self.title(f"بند: {clause['clause_title']}")
        self.geometry("740x720")
        self.resizable(True, True)
        self.configure(fg_color=C["bg"])
        self._center()
        self._build()
        self.grab_set(); self.lift()

    def _center(self):
        self.update_idletasks()
        x = (self.winfo_screenwidth()  - 740) // 2
        y = (self.winfo_screenheight() - 720) // 2
        self.geometry(f"740x720+{x}+{y}")

    # ── رسم الواجهة ──────────────────────────────────────────
    def _build(self):
        # رأس ملون
        status_col = STATUS_COLOR.get(self._clause["status"], C["t3"])
        hdr = ctk.CTkFrame(self, fg_color=C["bg1"], corner_radius=0)
        hdr.pack(fill="x")
        ctk.CTkFrame(hdr, fg_color=status_col, height=4, corner_radius=0).pack(fill="x")
        hi = ctk.CTkFrame(hdr, fg_color="transparent")
        hi.pack(fill="x", padx=18, pady=12)
        _lbl(hi, f"⚖  {self._clause['clause_title']}", F["sub"], C["text"]).pack(side="left")
        _badge(hi, STATUS_AR.get(self._clause["status"], self._clause["status"]),
               status_col).pack(side="right")

        # محتوى قابل للتمرير
        sc = ctk.CTkScrollableFrame(self, fg_color=C["bg"], corner_radius=0)
        sc.pack(fill="both", expand=True, padx=16, pady=8)
        self._sc = sc
        self._render_content()

        # شريط أزرار أسفل
        self._build_action_bar()

    def _render_content(self):
        """يرسم محتوى النافذة — يُعاد رسمه بعد كل إجراء."""
        for w in self._sc.winfo_children():
            w.destroy()

        c = self._clause
        is_open = self._session["status"] == SessionStatus.OPEN

        # ── موقف الطرف الأول ─────────────────────────────────
        self._party_block(
            self._sc,
            title=f"موقف {self._session['party_a_name']}",
            text=c["party_a_text"] or "— لم يُدخل موقف بعد —",
            color=C["pa"],
        )

        # ── موقف الطرف الثاني ────────────────────────────────
        name_b = self._session["party_b_name"]
        if c["party_b_text"]:
            self._party_block(self._sc, f"موقف {name_b}",
                              c["party_b_text"], C["pb"])
        elif is_open and c["status"] == ClauseStatus.PENDING:
            # حقل إدخال موقف الطرف الثاني
            self._build_party_b_input(name_b)
        else:
            self._party_block(self._sc, f"موقف {name_b}",
                              "— لم يُدخل موقف بعد —", C["pb"])

        # ── تحليل الفجوة (إن وُجد الموقفان) ─────────────────
        if c["party_a_text"] and c["party_b_text"]:
            self._gap_block()

        # ── الصيغة المقترحة ───────────────────────────────────
        if c["suggested_text"]:
            self._suggested_block(is_open)

        # ── البند النهائي ─────────────────────────────────────
        if c["final_text"]:
            self._final_block()

    def _party_block(self, parent, title: str, text: str, color: str):
        card = ctk.CTkFrame(parent, fg_color=C["bg1"], corner_radius=12,
                            border_width=1, border_color=color)
        card.pack(fill="x", pady=5)
        hdr_bar = ctk.CTkFrame(card, fg_color=color, corner_radius=0, height=34)
        hdr_bar.pack(fill="x")
        hdr_bar.pack_propagate(False)
        _lbl(hdr_bar, f"  📌  {title}", F["sm_b"], C["white"]).pack(
            side="left", padx=12, pady=6)
        _lbl(card, text, F["body"], C["text"],
             wraplength=650, justify="right").pack(
            anchor="e", padx=14, pady=10)

    def _build_party_b_input(self, name_b: str):
        """يبني قسم إدخال موقف الطرف الثاني مع أزرار الرد."""
        card = ctk.CTkFrame(self._sc, fg_color=C["bg1"], corner_radius=12,
                            border_width=1, border_color=C["pb"])
        card.pack(fill="x", pady=5)
        hdr_bar = ctk.CTkFrame(card, fg_color=C["pb"], corner_radius=0, height=34)
        hdr_bar.pack(fill="x")
        hdr_bar.pack_propagate(False)
        _lbl(hdr_bar, f"  ✏  موقف {name_b} — أدخل الرد",
             F["sm_b"], C["white"]).pack(side="left", padx=12, pady=6)

        body = ctk.CTkFrame(card, fg_color="transparent")
        body.pack(fill="x", padx=14, pady=10)
        _lbl(body, "نص موقف / رد الطرف الثاني:", F["sm_b"], C["t2"]).pack(anchor="w")
        self._tb_b = _textbox(body, h=90)
        self._tb_b.pack(fill="x", pady=6)

        btns = ctk.CTkFrame(body, fg_color="transparent")
        btns.pack(fill="x")
        _btn(btns, "✅  موافقة",   C["glt"],    self._accept).pack(side="left", padx=(0, 6))
        _btn(btns, "❌  رفض",      C["red"],    self._reject).pack(side="left", padx=(0, 6))
        _btn(btns, "✏  تعديل واقتراح", C["cyan"], self._modify).pack(side="left")

    def _gap_block(self):
        gap = analyze_gap(self._clause["party_a_text"], self._clause["party_b_text"])
        sim = gap["similarity"]
        sim_color = C["glt"] if sim >= 0.6 else C["gold"] if sim >= 0.3 else C["red"]

        card = ctk.CTkFrame(self._sc, fg_color=C["bg1"], corner_radius=12,
                            border_width=1, border_color=C["cyan"])
        card.pack(fill="x", pady=5)
        hdr_bar = ctk.CTkFrame(card, fg_color=C["bg2"], corner_radius=0)
        hdr_bar.pack(fill="x")
        _lbl(hdr_bar, "  📊  تحليل الفجوة", F["sm_b"], C["cyan"]).pack(
            side="left", padx=12, pady=8)

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=14, pady=10)

        # شريط التشابه
        row = ctk.CTkFrame(inner, fg_color="transparent")
        row.pack(fill="x", pady=4)
        _lbl(row, f"نسبة التشابه: {int(sim*100)}%  —  الفجوة: {gap['gap_level']}",
             F["sm"], sim_color).pack(side="left")
        pb = ctk.CTkProgressBar(row, height=10, corner_radius=5,
                                 fg_color=C["bg2"], progress_color=sim_color, width=220)
        pb.pack(side="right")
        pb.set(sim)

        if gap["common_words"]:
            _lbl(inner, "كلمات مشتركة: " + "  ·  ".join(gap["common_words"][:10]),
                 F["xs"], C["glt"]).pack(anchor="w", pady=2)

    def _suggested_block(self, is_open: bool):
        card = ctk.CTkFrame(self._sc, fg_color=C["bg1"], corner_radius=12,
                            border_width=2, border_color=C["sys"])
        card.pack(fill="x", pady=5)
        hdr_bar = ctk.CTkFrame(card, fg_color=C["sys"], corner_radius=0, height=34)
        hdr_bar.pack(fill="x")
        hdr_bar.pack_propagate(False)
        _lbl(hdr_bar, "  🤖  الصيغة المقترحة من النظام",
             F["sm_b"], C["white"]).pack(side="left", padx=12, pady=6)

        _lbl(card, self._clause["suggested_text"],
             F["body"], C["text"], wraplength=650, justify="right").pack(
            anchor="e", padx=14, pady=10)

        if is_open and self._clause["status"] != ClauseStatus.AGREED:
            row = ctk.CTkFrame(card, fg_color="transparent")
            row.pack(fill="x", padx=14, pady=(0, 10))
            _btn(row, "📝  إقرار هذه الصيغة نهائياً", C["blue"],
                 self._finalize_suggested).pack(side="left")

    def _final_block(self):
        card = ctk.CTkFrame(self._sc, fg_color=C["bg1"], corner_radius=12,
                            border_width=2, border_color=C["glt"])
        card.pack(fill="x", pady=5)
        hdr_bar = ctk.CTkFrame(card, fg_color=C["glt"], corner_radius=0, height=34)
        hdr_bar.pack(fill="x")
        hdr_bar.pack_propagate(False)
        _lbl(hdr_bar, "  ✅  البند النهائي المتفق عليه",
             F["sm_b"], C["white"]).pack(side="left", padx=12, pady=6)
        _lbl(card, self._clause["final_text"],
             F["body"], C["text"], wraplength=650, justify="right").pack(
            anchor="e", padx=14, pady=10)

    def _build_action_bar(self):
        bar = ctk.CTkFrame(self, fg_color=C["bg1"], corner_radius=0)
        bar.pack(fill="x")
        _sep(bar, C["bhi"], pady=2)
        inner = ctk.CTkFrame(bar, fg_color="transparent")
        inner.pack(fill="x", padx=14, pady=10)

        is_open = self._session["status"] == SessionStatus.OPEN
        c       = self._clause
        has_both = bool(c["party_a_text"] and c["party_b_text"])

        # اقتراح الصيغة
        if has_both and not c["suggested_text"] and c["status"] != ClauseStatus.AGREED and is_open:
            _btn(inner, "🤖  توليد صيغة مقترحة", C["purple"],
                 self._generate_suggestion).pack(side="left", padx=(0, 6))

        # إغلاق
        _btn(inner, "✕  إغلاق", C["bg2"],
             self._close, width=110).pack(side="right")

    # ── الإجراءات ─────────────────────────────────────────────
    def _get_b_text(self) -> str:
        if hasattr(self, "_tb_b"):
            return self._tb_b.get("0.0", "end").strip()
        return ""

    def _accept(self):
        respond_party_b(self._clause["id"], self._session["id"], "accepted", "")
        messagebox.showinfo("تم", "✅ تم تسجيل موافقة الطرف الثاني.")
        self._close()

    def _reject(self):
        respond_party_b(self._clause["id"], self._session["id"], "rejected",
                        self._get_b_text())
        messagebox.showinfo("تم", "❌ تم تسجيل رفض الطرف الثاني.")
        self._close()

    def _modify(self):
        text_b = self._get_b_text()
        if not text_b:
            messagebox.showwarning("تنبيه", "أدخل نص التعديل المقترح."); return
        respond_party_b(self._clause["id"], self._session["id"], "modified", text_b)
        messagebox.showinfo("تم", "✏ تم تسجيل اقتراح التعديل.")
        self._close()

    def _generate_suggestion(self):
        c   = self._clause
        sug = suggest_clause(c["clause_title"], c["party_a_text"], c["party_b_text"])
        save_suggestion(c["id"], self._session["id"], sug)
        messagebox.showinfo("تم", "🤖 تم توليد الصيغة المقترحة.")
        self._close()

    def _finalize_suggested(self):
        dlg = ctk.CTkInputDialog(
            text="راجع الصيغة النهائية وعدّلها إن أردت:",
            title="إقرار البند النهائي",
        )
        result = dlg.get_input()
        if result is not None:
            final = result.strip() or self._clause["suggested_text"]
            agree_clause(self._clause["id"], self._session["id"], final)
            messagebox.showinfo("تم", "✅ تم إقرار البند النهائي.")
            self._close()

    def _close(self):
        self.destroy()
        self._on_close()


# ══════════════════════════════════════════════════════════════
#  NegotiationView — الشاشة الرئيسية
# ══════════════════════════════════════════════════════════════
class NegotiationView(ctk.CTkFrame):
    """
    شاشة إدارة التفاوض الكاملة.
    تُضاف في main.py بسطرين:
        from negotiation.ui import NegotiationView
        self.neg_v = NegotiationView(self.content, get_user=lambda: ST.current_user)
    """

    def __init__(self, master, get_user: Callable, **kw):
        super().__init__(master, fg_color=C["bg"], corner_radius=0, **kw)
        self._get_user   = get_user
        self._session_id: Optional[int] = None
        self._session:    Optional[dict] = None
        self._build()

    # ── بناء الواجهة الرئيسية ────────────────────────────────
    def _build(self):
        self._build_header()
        _sep(self, C["border"])

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=14, pady=8)

        # يسار: قائمة الجلسات
        left = ctk.CTkFrame(body, fg_color=C["bg1"], corner_radius=14,
                            border_width=1, border_color=C["border"], width=270)
        left.pack(side="left", fill="y", padx=(0, 10))
        left.pack_propagate(False)
        self._build_sessions_panel(left)

        # يمين: تفاصيل الجلسة
        right = ctk.CTkFrame(body, fg_color=C["bg1"], corner_radius=14,
                             border_width=1, border_color=C["border"])
        right.pack(side="right", fill="both", expand=True)
        self._build_detail_panel(right)

    def _build_header(self):
        hdr = ctk.CTkFrame(self, fg_color=C["bg1"], corner_radius=0)
        hdr.pack(fill="x")
        ctk.CTkFrame(hdr, fg_color=C["blue"], height=4, corner_radius=0).pack(fill="x")
        row = ctk.CTkFrame(hdr, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=14)
        _lbl(row, "🤝  إدارة التفاوض بين الأطراف",
             F["heading"], C["text"]).pack(side="left")
        self._btn_new = _btn(row, "➕  جلسة جديدة", C["blue"],
                             self._new_session, height=38)
        self._btn_new.pack(side="right")

    def _build_sessions_panel(self, parent):
        hdr = ctk.CTkFrame(parent, fg_color=C["bg2"], corner_radius=10)
        hdr.pack(fill="x", padx=10, pady=(10, 4))
        _lbl(hdr, "📋  جلساتي", F["sm_b"], C["t2"]).pack(side="left", padx=12, pady=8)
        ctk.CTkButton(hdr, text="🔄", width=30, height=26,
                      fg_color="transparent", hover_color=C["bg3"],
                      text_color=C["t2"], font=F["xs"],
                      command=self._reload_sessions).pack(side="right", padx=6)

        self._sessions_sc = ctk.CTkScrollableFrame(
            parent, fg_color=C["bg"], corner_radius=10,
            border_width=1, border_color=C["border"])
        self._sessions_sc.pack(fill="both", expand=True, padx=10, pady=(4, 10))

    def _build_detail_panel(self, parent):
        # عنوان الجلسة
        self._detail_title = _lbl(
            parent, "  اختر جلسة من القائمة أو أنشئ جلسة جديدة",
            F["sub"], C["t3"])
        self._detail_title.pack(anchor="w", padx=16, pady=(12, 4))

        # شريط إحصاء
        self._stats_bar = ctk.CTkFrame(parent, fg_color=C["bg2"],
                                       corner_radius=10,
                                       border_width=1, border_color=C["bhi"])
        self._stats_bar.pack(fill="x", padx=14, pady=(0, 6))

        # شريط أزرار الجلسة
        acts = ctk.CTkFrame(parent, fg_color="transparent")
        acts.pack(fill="x", padx=14, pady=(0, 6))

        self._btn_add = _btn(acts, "➕  إضافة بند", C["blue"],
                             self._add_clause, height=38)
        self._btn_add.configure(state="disabled")
        self._btn_add.pack(side="left", padx=(0, 6))

        self._btn_suggest_all = _btn(acts, "🤖  اقتراح الكل", C["purple"],
                                     self._suggest_all, height=38)
        self._btn_suggest_all.configure(state="disabled")
        self._btn_suggest_all.pack(side="left", padx=(0, 6))

        self._btn_close_sess = _btn(acts, "🔒  إغلاق الجلسة", C["glt"],
                                    self._close_session, height=38)
        self._btn_close_sess.configure(state="disabled")
        self._btn_close_sess.pack(side="left")

        # قائمة البنود
        _lbl(parent, "📄  بنود التفاوض", F["sm_b"], C["t2"]).pack(
            anchor="w", padx=14, pady=(4, 2))

        self._clauses_sc = ctk.CTkScrollableFrame(
            parent, fg_color=C["bg"], corner_radius=10,
            border_width=1, border_color=C["border"])
        self._clauses_sc.pack(fill="both", expand=True, padx=14, pady=(0, 14))

        _lbl(self._clauses_sc,
             "⚙\n\nاختر جلسة لعرض بنودها",
             F["body"], C["t3"], "center",
             justify="center").pack(expand=True, pady=50)

    # ══════════════════════════════════════════════════════════
    #  عرض الجلسات
    # ══════════════════════════════════════════════════════════
    def refresh(self):
        """يُستدعى عند الانتقال للتبويب."""
        self._reload_sessions()
        if self._session_id:
            self._load_session(self._session_id)

    def _reload_sessions(self):
        for w in self._sessions_sc.winfo_children():
            w.destroy()
        user = self._get_user()
        if not user:
            _lbl(self._sessions_sc, "⚠  سجّل دخولك أولاً",
                 F["sm"], C["orange"], "center").pack(pady=20)
            return
        sessions = get_user_sessions(user["id"])
        if not sessions:
            _lbl(self._sessions_sc,
                 "لا توجد جلسات\nاضغط «جلسة جديدة»",
                 F["sm"], C["t3"], "center",
                 justify="center").pack(pady=30)
            return
        for s in sessions:
            self._session_card(s)

    def _session_card(self, s: dict):
        total   = s.get("total_count", 0)
        agreed  = s.get("agreed_count", 0)
        pct     = int(agreed / total * 100) if total else 0
        is_sel  = (s["id"] == self._session_id)
        is_open = (s["status"] == SessionStatus.OPEN)
        bc      = C["blue"] if is_sel else C["border"]
        pct_col = C["glt"] if pct == 100 else C["gold"] if pct >= 50 else C["t3"]

        card = ctk.CTkFrame(self._sessions_sc, fg_color=C["bg1"],
                            corner_radius=10, border_width=1,
                            border_color=bc, cursor="hand2")
        card.pack(fill="x", pady=3)
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=10, pady=8)

        # سطر العنوان + حالة
        row1 = ctk.CTkFrame(inner, fg_color="transparent")
        row1.pack(fill="x")
        title_short = s["title"][:30] + ("..." if len(s["title"]) > 30 else "")
        _lbl(row1, title_short, F["sm_b"], C["text"]).pack(side="left")
        st_col = C["glt"] if is_open else C["t3"]
        _badge(row1, "مفتوحة" if is_open else "مغلقة", st_col).pack(side="right")

        # الأطراف
        _lbl(inner, f"{s['party_a_name']}  ⟺  {s['party_b_name']}",
             F["xs"], C["t2"]).pack(anchor="w", pady=2)

        # شريط التقدم
        if total:
            pb = ctk.CTkProgressBar(inner, height=5, corner_radius=3,
                                     fg_color=C["bg2"], progress_color=pct_col)
            pb.pack(fill="x", pady=2)
            pb.set(pct / 100)
            _lbl(inner, f"{agreed}/{total} بند  ({pct}%)",
                 F["xs"], pct_col).pack(anchor="w")

        # حدث النقر — كل أبناء الكارد ينقلون الحدث
        def _click(e, sid=s["id"]):
            self._load_session(sid)

        for w in [card, inner] + inner.winfo_children():
            try:
                w.bind("<Button-1>", _click)
            except Exception:
                pass

    # ══════════════════════════════════════════════════════════
    #  تحميل جلسة
    # ══════════════════════════════════════════════════════════
    def _load_session(self, session_id: int):
        self._session_id = session_id
        self._session    = get_session(session_id)
        if not self._session:
            return

        is_open = self._session["status"] == SessionStatus.OPEN
        state   = "normal" if is_open else "disabled"

        self._detail_title.configure(
            text=f"  🤝  {self._session['title']}",
            text_color=C["text"])

        self._btn_add.configure(state=state)
        self._btn_suggest_all.configure(state=state)
        self._btn_close_sess.configure(
            state="normal" if is_open else "disabled")

        self._redraw_stats()
        self._redraw_clauses()
        self._reload_sessions()   # تحديث التحديد البصري

    def _redraw_stats(self):
        for w in self._stats_bar.winfo_children():
            w.destroy()
        if not self._session:
            return
        clauses = get_clauses(self._session["id"])
        sm      = session_summary(clauses)
        row     = ctk.CTkFrame(self._stats_bar, fg_color="transparent")
        row.pack(fill="x", padx=12, pady=8)
        for txt, clr in [
            (f"✅ {sm['agreed']}\nمتفق عليه", C["glt"]),
            (f"⏳ {sm['pending']}\nبانتظار",   C["gold"]),
            (f"✏  {sm['modified']}\nمعدَّل",  C["cyan"]),
            (f"❌ {sm['rejected']}\nمرفوض",    C["red"]),
            (f"📊 {sm['progress_pct']}%\nالإنجاز", C["blue"]),
        ]:
            b = ctk.CTkFrame(row, fg_color=C["bg2"], corner_radius=8)
            b.pack(side="left", padx=3, expand=True, fill="x")
            _lbl(b, txt, F["xs"], clr, "center",
                 justify="center").pack(padx=6, pady=6)

        rec_col = (C["glt"]    if "✅" in sm["recommendation"] else
                   C["gold"]   if "🟡" in sm["recommendation"] else
                   C["orange"])
        _lbl(self._stats_bar, sm["recommendation"],
             F["sm"], rec_col, "center").pack(pady=(0, 8))

    def _redraw_clauses(self):
        for w in self._clauses_sc.winfo_children():
            w.destroy()
        if not self._session:
            return
        clauses = get_clauses(self._session["id"])
        if not clauses:
            _lbl(self._clauses_sc,
                 "لا توجد بنود — اضغط «إضافة بند» للبدء",
                 F["body"], C["t3"], "center").pack(pady=40)
            return
        for i, cl in enumerate(clauses):
            self._clause_row(cl, i)

    def _clause_row(self, cl: dict, idx: int):
        status    = cl["status"]
        sc        = STATUS_COLOR.get(status, C["t3"])
        sl        = STATUS_AR.get(status, status)
        bg        = C["bg2"] if idx % 2 == 0 else C["bg"]

        row = ctk.CTkFrame(self._clauses_sc, fg_color=bg, corner_radius=10,
                           border_width=1, border_color=C["border"])
        row.pack(fill="x", pady=3)
        inner = ctk.CTkFrame(row, fg_color="transparent")
        inner.pack(fill="x", padx=12, pady=10)

        # رقم + عنوان + حالة
        top = ctk.CTkFrame(inner, fg_color="transparent")
        top.pack(fill="x")

        num_f = ctk.CTkFrame(top, fg_color=sc, corner_radius=14,
                             width=28, height=28)
        num_f.pack(side="left", padx=(0, 10))
        num_f.pack_propagate(False)
        ctk.CTkLabel(num_f, text=str(idx + 1), font=F["xs"],
                     text_color=C["white"]).place(relx=.5, rely=.5, anchor="center")

        _lbl(top, cl["clause_title"], F["body_b"], C["text"]).pack(
            side="left", fill="x", expand=True)
        _badge(top, sl, sc).pack(side="right")

        # معاينة نصوص الطرفين
        if cl["party_a_text"]:
            pa = cl["party_a_text"][:80] + ("..." if len(cl["party_a_text"]) > 80 else "")
            _lbl(inner, f"أ: {pa}", F["xs"], C["t2"], wraplength=520).pack(anchor="w", pady=1)
        if cl["party_b_text"]:
            pb_t = cl["party_b_text"][:80] + ("..." if len(cl["party_b_text"]) > 80 else "")
            _lbl(inner, f"ب: {pb_t}", F["xs"], C["cyan"], wraplength=520).pack(anchor="w", pady=1)

        # زر التفاصيل
        _btn(inner, "📋  عرض التفاصيل والإجراءات",
             C["bg3"], lambda c=cl: self._open_detail(c),
             height=32).pack(anchor="e", pady=(6, 0))

    def _open_detail(self, clause: dict):
        if not self._session:
            return
        _ClauseDetailDlg(
            self, clause, self._session,
            on_close=self._on_detail_closed
        )

    def _on_detail_closed(self):
        """يُستدعى بعد إغلاق نافذة تفاصيل البند."""
        self._session = get_session(self._session_id)
        self._redraw_stats()
        self._redraw_clauses()
        self._reload_sessions()

    # ══════════════════════════════════════════════════════════
    #  الإجراءات
    # ══════════════════════════════════════════════════════════
    def _new_session(self):
        user = self._get_user()
        if not user:
            messagebox.showinfo("تنبيه", "سجّل دخولك أولاً لإنشاء جلسة.")
            return
        _NewSessionDlg(self, user["id"], self._on_session_created)

    def _on_session_created(self, session_id: int):
        self._reload_sessions()
        self._load_session(session_id)

    def _add_clause(self):
        if not self._session:
            return
        _AddClauseDlg(self, self._session, self._on_detail_closed)

    def _suggest_all(self):
        """يولّد اقتراحات لكل البنود التي لها موقفان ولم تُقترح بعد."""
        if not self._session:
            return
        clauses = get_clauses(self._session_id)
        count   = 0
        for c in clauses:
            if (c["party_a_text"] and c["party_b_text"]
                    and not c["suggested_text"]
                    and c["status"] != ClauseStatus.AGREED):
                sug = suggest_clause(
                    c["clause_title"], c["party_a_text"], c["party_b_text"])
                save_suggestion(c["id"], self._session_id, sug)
                count += 1
        msg = f"تم توليد {count} اقتراح." if count else "لا توجد بنود جاهزة للاقتراح."
        messagebox.showinfo("نتيجة", msg)
        self._on_detail_closed()

    def _close_session(self):
        if not self._session:
            return
        clauses = get_clauses(self._session_id)
        agreed  = sum(1 for c in clauses if c["status"] == ClauseStatus.AGREED)
        total   = len(clauses)
        msg     = (f"هل تريد إغلاق الجلسة نهائياً؟\n"
                   f"تم الاتفاق على {agreed} من {total} بند.")
        if messagebox.askyesno("تأكيد إغلاق الجلسة", msg):
            close_session(self._session_id)
            messagebox.showinfo("تم", "✅ تم إغلاق الجلسة.")
            self._on_detail_closed()