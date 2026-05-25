"""
config.py  —  إدارة الإعدادات الدائمة
═══════════════════════════════════════════════════════════════
يحفظ ويُحمّل:
  • مفتاح Claude API
  • حجم الخط الحالي
  • مستوى التكبير
  • آخر نوع عقد مختار

الملف: settings.json  (في نفس مجلد المشروع)
═══════════════════════════════════════════════════════════════
"""

import json
import os
from typing import Any

# ── مسار ملف الإعدادات ────────────────────────────────────
_DIR      = os.path.dirname(os.path.abspath(__file__))
SETTINGS_PATH = os.path.join(_DIR, "settings.json")

# ── القيم الافتراضية ──────────────────────────────────────
_DEFAULTS: dict[str, Any] = {
    "api_key":           "",
    "font_scale":        1.0,    # مُضاعِف حجم الخط (0.7 → 1.5)
    "last_contract_type": "",
    "window_geometry":   "",     # مثال: "1240x790+100+50"
    "ocr_enabled":       True,
    "matcher_mode":      "tfidf",  # "tfidf" | "transformers"
}


def load() -> dict:
    """يُحمّل الإعدادات من الملف، ويُعيد الافتراضي عند غيابه."""
    if not os.path.exists(SETTINGS_PATH):
        return dict(_DEFAULTS)
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        # دمج مع الافتراضي لضمان وجود المفاتيح الجديدة
        merged = dict(_DEFAULTS)
        merged.update(data)
        return merged
    except Exception:
        return dict(_DEFAULTS)


def save(settings: dict) -> None:
    """يحفظ الإعدادات في الملف."""
    try:
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[config] تحذير: فشل حفظ الإعدادات — {e}")


def get(key: str) -> Any:
    """يُعيد قيمة مفتاح واحد من الإعدادات."""
    return load().get(key, _DEFAULTS.get(key))


def set_key(key: str, value: Any) -> None:
    """يُحدّث مفتاح واحد ويحفظ."""
    s = load()
    s[key] = value
    save(s)


# ── واجهة مختصرة للـ API key ─────────────────────────────
def get_api_key() -> str:
    return get("api_key")


def save_api_key(key: str) -> None:
    set_key("api_key", key.strip())


# ── واجهة مختصرة لحجم الخط ──────────────────────────────
def get_font_scale() -> float:
    try:
        return float(get("font_scale"))
    except Exception:
        return 1.0


def save_font_scale(scale: float) -> None:
    scale = max(0.7, min(1.8, scale))   # حدود آمنة
    set_key("font_scale", round(scale, 2))