"""
install_tesseract.py  —  مثبّت Tesseract OCR تلقائي
══════════════════════════════════════════════════════
شغّل هذا الملف مرة واحدة قبل استخدام ميزة تحليل الصور:
    python install_tesseract.py
══════════════════════════════════════════════════════
"""

import subprocess
import sys
import os
import platform
import urllib.request
import tempfile

DIVIDER = "═" * 55


def run(cmd: list, label: str) -> bool:
    """يُشغّل أمراً ويُعيد True عند النجاح."""
    print(f"\n⏳  {label}...")
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8", errors="replace"
        )
        if result.returncode == 0:
            print(f"  ✓  {label} — نجح")
            return True
        else:
            print(f"  ✗  {label} — فشل")
            if result.stderr:
                print(f"     {result.stderr[:200]}")
            return False
    except FileNotFoundError:
        print(f"  ✗  الأمر غير موجود: {cmd[0]}")
        return False
    except Exception as e:
        print(f"  ✗  خطأ: {e}")
        return False


def check_tesseract() -> bool:
    """يتحقق من وجود Tesseract."""
    try:
        result = subprocess.run(
            ["tesseract", "--version"],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            ver = result.stdout.split("\n")[0]
            print(f"  ✓  Tesseract موجود: {ver}")
            return True
    except FileNotFoundError:
        pass
    return False


def check_arabic() -> bool:
    """يتحقق من دعم اللغة العربية."""
    try:
        result = subprocess.run(
            ["tesseract", "--list-langs"],
            capture_output=True, text=True
        )
        langs = result.stdout + result.stderr
        if "ara" in langs:
            print("  ✓  اللغة العربية مدعومة (ara)")
            return True
        else:
            print("  ✗  اللغة العربية غير موجودة")
            return False
    except Exception:
        return False


def install_via_winget() -> bool:
    """يثبّت Tesseract عبر winget (Windows 10/11)."""
    return run(
        ["winget", "install", "--id", "UB-Mannheim.TesseractOCR",
         "--accept-source-agreements", "--accept-package-agreements",
         "--silent"],
        "تثبيت Tesseract عبر winget"
    )


def install_via_choco() -> bool:
    """يثبّت Tesseract عبر Chocolatey."""
    return run(
        ["choco", "install", "tesseract", "--yes"],
        "تثبيت Tesseract عبر Chocolatey"
    )


def install_via_download() -> bool:
    """
    يحمّل مثبّت Tesseract مباشرةً ويُشغّله (Windows).
    """
    url = (
        "https://github.com/UB-Mannheim/tesseract/releases/download/"
        "v5.3.3.20231005/tesseract-ocr-w64-setup-5.3.3.20231005.exe"
    )
    tmp = os.path.join(tempfile.gettempdir(), "tesseract_setup.exe")

    print(f"\n⏳  تحميل مثبّت Tesseract ({url[-40:]})...")
    try:
        urllib.request.urlretrieve(url, tmp)
        print(f"  ✓  تم التحميل: {tmp}")
    except Exception as e:
        print(f"  ✗  فشل التحميل: {e}")
        return False

    print("⏳  تشغيل المثبّت (قد تظهر نافذة تثبيت)...")
    try:
        subprocess.run([tmp, "/S"], check=True)   # /S = silent install
        print("  ✓  تم التثبيت")
        return True
    except Exception as e:
        print(f"  ✗  فشل التشغيل: {e}")
        print(f"     يمكنك تشغيل المثبّت يدوياً من: {tmp}")
        return False


def install_python_libs() -> bool:
    """يثبّت مكتبات Python المطلوبة."""
    return run(
        [sys.executable, "-m", "pip", "install",
         "pytesseract", "pillow", "--quiet", "--upgrade"],
        "تثبيت pytesseract و Pillow"
    )


def fix_path_windows() -> None:
    """يُضيف مسار Tesseract لـ PATH في Windows."""
    candidates = [
        r"C:\Program Files\Tesseract-OCR",
        r"C:\Program Files (x86)\Tesseract-OCR",
        os.path.expanduser(r"~\AppData\Local\Programs\Tesseract-OCR"),
    ]
    for path in candidates:
        if os.path.exists(os.path.join(path, "tesseract.exe")):
            current = os.environ.get("PATH", "")
            if path not in current:
                print(f"\n⏳  إضافة {path} لـ PATH...")
                try:
                    subprocess.run(
                        ["setx", "PATH", f"{current};{path}"],
                        capture_output=True, check=True
                    )
                    os.environ["PATH"] = current + ";" + path
                    print(f"  ✓  تم إضافة المسار")
                except Exception as e:
                    print(f"  ⚠  أضف المسار يدوياً: {path}")
            else:
                print(f"  ✓  المسار موجود في PATH")
            return


def main():
    print(DIVIDER)
    print("  مثبّت Tesseract OCR  —  نظام تحليل العقود v4.0")
    print(DIVIDER)
    print(f"  النظام : {platform.system()} {platform.release()}")
    print(f"  Python : {sys.version.split()[0]}")

    # ── الخطوة ١: تحقق مما هو موجود ──────────────────────
    print(f"\n{DIVIDER}")
    print("  الخطوة ١: فحص البيئة الحالية")
    print(DIVIDER)

    tess_ok = check_tesseract()
    if tess_ok:
        ara_ok  = check_arabic()
    else:
        ara_ok  = False

    pip_ok = run([sys.executable, "-m", "pip", "show", "pytesseract"],
                 "فحص pytesseract") if True else False
    try:
        import pytesseract
        pyt_ok = True
        print("  ✓  pytesseract مثبّت")
    except ImportError:
        pyt_ok = False
        print("  ✗  pytesseract غير مثبّت")

    try:
        from PIL import Image
        pil_ok = True
        print("  ✓  Pillow مثبّت")
    except ImportError:
        pil_ok = False
        print("  ✗  Pillow غير مثبّت")

    # ── الخطوة ٢: تثبيت مكتبات Python ─────────────────────
    if not pyt_ok or not pil_ok:
        print(f"\n{DIVIDER}")
        print("  الخطوة ٢: تثبيت مكتبات Python")
        print(DIVIDER)
        install_python_libs()

    # ── الخطوة ٣: تثبيت Tesseract إن لم يكن موجوداً ───────
    if not tess_ok:
        print(f"\n{DIVIDER}")
        print("  الخطوة ٣: تثبيت Tesseract OCR")
        print(DIVIDER)

        if platform.system() == "Windows":
            # جرّب winget أولاً
            if not install_via_winget():
                print("\n  ← winget فشل، جرّب Chocolatey...")
                if not install_via_choco():
                    print("\n  ← جميع الطرق فشلت، جرّب التحميل المباشر...")
                    install_via_download()
            fix_path_windows()
        else:
            print("\n  نظام Linux/Mac — استخدم:")
            print("    Ubuntu/Debian: sudo apt install tesseract-ocr tesseract-ocr-ara")
            print("    Mac:           brew install tesseract tesseract-lang")

    # ── الخطوة ٤: التحقق النهائي ───────────────────────────
    print(f"\n{DIVIDER}")
    print("  الخطوة ٤: فحص نهائي")
    print(DIVIDER)

    tess_final = check_tesseract()
    if tess_final:
        ara_final = check_arabic()
    else:
        ara_final = False

    try:
        import pytesseract
        from PIL import Image
        pyt_final = True
        print("  ✓  pytesseract + Pillow جاهزان")
    except ImportError as e:
        pyt_final = False
        print(f"  ✗  {e}")

    # ── النتيجة ────────────────────────────────────────────
    print(f"\n{DIVIDER}")
    if tess_final and pyt_final:
        if ara_final:
            print("  ✅  كل شيء جاهز! شغّل: python new_main.py")
        else:
            print("  ⚠   Tesseract موجود لكن اللغة العربية غير مثبّتة.")
            print("      أعد تثبيت Tesseract مع تحديد Arabic language data.")
    else:
        print("  ❌  التثبيت غير مكتمل. اتبع الخطوات اليدوية:")
        print()
        print("  1. افتح PowerShell كمدير (كليك يمين → Run as Administrator)")
        print("  2. اكتب:")
        print("       winget install UB-Mannheim.TesseractOCR")
        print("  3. أعد تشغيل PowerShell")
        print("  4. اكتب:")
        print("       pip install pytesseract pillow")
        print("  5. شغّل البرنامج: python new_main.py")
    print(DIVIDER)


if __name__ == "__main__":
    main()
    input("\nاضغط Enter للإغلاق...")