"""
auth.py  –  نوافذ تسجيل الدخول وإنشاء الحساب
===============================================
يستورد من database.py ويستخدم CustomTkinter.

الاستخدام من main.py:
    from auth import show_login
    user = show_login(root)   # يُعيد dict المستخدم أو None
"""

import customtkinter as ctk
from tkinter import messagebox
from database import login_user, register_user

# ── نفس الألوان المستخدمة في main.py ─────────────────────────
C = {
    "bg":     "#080C18", "bg1":   "#0F1525", "bg2":  "#151D35",
    "bg3":    "#1C2640", "card":  "#111829", "border":"#1E2A45",
    "bhi":    "#2A3D6A", "blue":  "#2563EB", "blt":  "#3B82F6",
    "cyan":   "#06B6D4", "purple":"#7C3AED", "gold": "#D97706",
    "green":  "#059669", "glt":   "#10B981", "red":  "#DC2626",
    "orange": "#EA580C", "text":  "#F1F5FF", "t2":   "#94A3B8",
    "t3":     "#4B5E82", "white": "#FFFFFF",
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
}

# ══════════════════════════════════════════════════════════════
#  مساعد: حقل إدخال موحّد
# ══════════════════════════════════════════════════════════════
def _entry(parent, placeholder: str, show: str = "") -> ctk.CTkEntry:
    return ctk.CTkEntry(
        parent,
        placeholder_text=placeholder,
        show=show,
        height=44,
        corner_radius=10,
        fg_color=C["bg2"],
        border_color=C["border"],
        text_color=C["text"],
        placeholder_text_color=C["t3"],
        font=F["body"],
    )

def _btn(parent, text: str, color: str, command) -> ctk.CTkButton:
    return ctk.CTkButton(
        parent,
        text=text,
        fg_color=color,
        hover_color=C["blt"],
        text_color=C["white"],
        font=F["btn"],
        height=46,
        corner_radius=10,
        command=command,
    )

def _lbl(parent, text, font=None, color=None, **kw):
    return ctk.CTkLabel(
        parent, text=text,
        font=font or F["body"],
        text_color=color or C["text"],
        **kw
    )

# ══════════════════════════════════════════════════════════════
#  نافذة تسجيل الدخول
# ══════════════════════════════════════════════════════════════
class LoginWindow(ctk.CTkToplevel):
    def __init__(self, master):
        super().__init__(master)
        self.result = None          # يُعيَّن عند النجاح
        self._switch_to_register = False

        self.title("تسجيل الدخول")
        self.geometry("460x540")
        self.resizable(False, False)
        self.configure(fg_color=C["bg"])
        self._center()
        self._build()
        self.grab_set()
        self.lift()
        self.focus_force()

    def _center(self):
        self.update_idletasks()
        x = (self.winfo_screenwidth()  - 460) // 2
        y = (self.winfo_screenheight() - 540) // 2
        self.geometry(f"460x540+{x}+{y}")

    def _build(self):
        # ── رأس النافذة ──────────────────────────────────────
        hdr = ctk.CTkFrame(self, fg_color=C["bg1"], corner_radius=0)
        hdr.pack(fill="x")
        ctk.CTkFrame(hdr, fg_color=C["blue"], height=3, corner_radius=0).pack(fill="x")
        ctk.CTkLabel(hdr, text="⚖", font=("Arial", 40),
                     text_color=C["cyan"]).pack(pady=(20, 4))
        _lbl(hdr, "نظام تحليل العقود الذكي",
             F["sub"], C["text"]).pack()
        _lbl(hdr, "سجّل دخولك للمتابعة",
             F["sm"], C["t3"]).pack(pady=(2, 18))

        # ── نموذج الدخول ─────────────────────────────────────
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=32, pady=24)

        _lbl(body, "اسم المستخدم", F["sm_b"], C["t2"]).pack(anchor="w", pady=(0, 4))
        self.ent_user = _entry(body, "أدخل اسم المستخدم")
        self.ent_user.pack(fill="x", pady=(0, 14))

        _lbl(body, "كلمة المرور", F["sm_b"], C["t2"]).pack(anchor="w", pady=(0, 4))
        self.ent_pass = _entry(body, "أدخل كلمة المرور", show="●")
        self.ent_pass.pack(fill="x", pady=(0, 6))

        self.err_lbl = _lbl(body, "", F["xs"], C["red"])
        self.err_lbl.pack(anchor="w", pady=(0, 16))

        _btn(body, "🔓  تسجيل الدخول", C["blue"],
             self._do_login).pack(fill="x", pady=(0, 10))

        # خط فاصل
        sep_row = ctk.CTkFrame(body, fg_color="transparent")
        sep_row.pack(fill="x", pady=4)
        ctk.CTkFrame(sep_row, fg_color=C["border"], height=1).pack(
            side="left", expand=True, fill="x", padx=(0,10))
        _lbl(sep_row, "أو", F["xs"], C["t3"]).pack(side="left")
        ctk.CTkFrame(sep_row, fg_color=C["border"], height=1).pack(
            side="right", expand=True, fill="x", padx=(10,0))

        _btn(body, "✨  إنشاء حساب جديد", C["bg2"],
             self._go_register).pack(fill="x", pady=(10, 0))

        # Enter key
        self.ent_pass.bind("<Return>", lambda e: self._do_login())
        self.ent_user.bind("<Return>", lambda e: self.ent_pass.focus())

    def _do_login(self):
        user = self.ent_user.get().strip()
        pw   = self.ent_pass.get()
        if not user or not pw:
            self.err_lbl.configure(text="⚠  يرجى ملء جميع الحقول")
            return
        res = login_user(user, pw)
        if res["ok"]:
            self.result = res["user"]
            self.destroy()
        else:
            self.err_lbl.configure(text=f"✗  {res['error']}")

    def _go_register(self):
        self._switch_to_register = True
        self.destroy()

# ══════════════════════════════════════════════════════════════
#  نافذة إنشاء الحساب
# ══════════════════════════════════════════════════════════════
class RegisterWindow(ctk.CTkToplevel):
    def __init__(self, master):
        super().__init__(master)
        self.result = None

        self.title("إنشاء حساب جديد")
        self.geometry("460x620")
        self.resizable(False, False)
        self.configure(fg_color=C["bg"])
        self._center()
        self._build()
        self.grab_set()
        self.lift()
        self.focus_force()

    def _center(self):
        self.update_idletasks()
        x = (self.winfo_screenwidth()  - 460) // 2
        y = (self.winfo_screenheight() - 620) // 2
        self.geometry(f"460x620+{x}+{y}")

    def _build(self):
        hdr = ctk.CTkFrame(self, fg_color=C["bg1"], corner_radius=0)
        hdr.pack(fill="x")
        ctk.CTkFrame(hdr, fg_color=C["purple"], height=3, corner_radius=0).pack(fill="x")
        ctk.CTkLabel(hdr, text="✨", font=("Arial", 36),
                     text_color=C["purple"]).pack(pady=(18, 4))
        _lbl(hdr, "إنشاء حساب جديد", F["sub"], C["text"]).pack()
        _lbl(hdr, "أنشئ حسابك مجاناً وابدأ التحليل",
             F["sm"], C["t3"]).pack(pady=(2, 16))

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=32, pady=20)

        _lbl(body, "اسم المستخدم", F["sm_b"], C["t2"]).pack(anchor="w", pady=(0,4))
        self.ent_user = _entry(body, "اسم مستخدم فريد (3 أحرف+)")
        self.ent_user.pack(fill="x", pady=(0,12))

        _lbl(body, "البريد الإلكتروني", F["sm_b"], C["t2"]).pack(anchor="w", pady=(0,4))
        self.ent_email = _entry(body, "example@email.com")
        self.ent_email.pack(fill="x", pady=(0,12))

        _lbl(body, "كلمة المرور", F["sm_b"], C["t2"]).pack(anchor="w", pady=(0,4))
        self.ent_pass = _entry(body, "6 أحرف على الأقل", show="●")
        self.ent_pass.pack(fill="x", pady=(0,12))

        _lbl(body, "تأكيد كلمة المرور", F["sm_b"], C["t2"]).pack(anchor="w", pady=(0,4))
        self.ent_pass2 = _entry(body, "أعد كتابة كلمة المرور", show="●")
        self.ent_pass2.pack(fill="x", pady=(0,6))

        self.err_lbl = _lbl(body, "", F["xs"], C["red"])
        self.err_lbl.pack(anchor="w", pady=(0,14))

        _btn(body, "✅  إنشاء الحساب", C["purple"],
             self._do_register).pack(fill="x", pady=(0,10))

        _btn(body, "← العودة لتسجيل الدخول", C["bg2"],
             self.destroy).pack(fill="x")

        self.ent_pass2.bind("<Return>", lambda e: self._do_register())

    def _do_register(self):
        user  = self.ent_user.get().strip()
        email = self.ent_email.get().strip()
        pw    = self.ent_pass.get()
        pw2   = self.ent_pass2.get()
        if not all([user, email, pw, pw2]):
            self.err_lbl.configure(text="⚠  يرجى ملء جميع الحقول")
            return
        if pw != pw2:
            self.err_lbl.configure(text="✗  كلمتا المرور غير متطابقتين")
            return
        res = register_user(user, email, pw)
        if res["ok"]:
            messagebox.showinfo(
                "تم بنجاح",
                f"✓  تم إنشاء حسابك!\nمرحباً {user}، يمكنك الآن تسجيل الدخول."
            )
            self.result = {"registered": True, "username": user}
            self.destroy()
        else:
            self.err_lbl.configure(text=f"✗  {res['error']}")

# ══════════════════════════════════════════════════════════════
#  الدالة الرئيسية: تُظهر نافذة الدخول وتُعيد المستخدم
# ══════════════════════════════════════════════════════════════
def show_login(master) -> dict | None:
    """
    تُظهر نافذة تسجيل الدخول (وتنتقل لإنشاء حساب إذا طُلب).
    تُعيد dict المستخدم عند النجاح، أو None إذا أغلق المستخدم النافذة.
    """
    while True:
        win = LoginWindow(master)
        master.wait_window(win)

        if win.result:                          # دخول ناجح
            return win.result

        if win._switch_to_register:             # طلب إنشاء حساب
            reg = RegisterWindow(master)
            master.wait_window(reg)
            if reg.result and reg.result.get("registered"):
                # بعد التسجيل، أعد لنافذة الدخول
                continue
            # أغلق نافذة التسجيل بدون تسجيل → أعد لنافذة الدخول
            continue

        # أغلق نافذة الدخول بدون دخول → إلغاء
        return None