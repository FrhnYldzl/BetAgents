"""app_pro tek-geçiş denetim — st.tabs tüm sayfaları birlikte render eder."""
import sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parent / "app_pro.py")
print("=== app_pro.py TEK-GEÇİŞ DENETİM (10 sayfa birlikte) ===")
at = AppTest.from_file(APP, default_timeout=90)
at.run()
if at.exception:
    for e in at.exception:
        print(f"  [HATA] {e.value}")
else:
    print("  [TEMIZ] 10 sayfanın hepsi hatasız render edildi")
