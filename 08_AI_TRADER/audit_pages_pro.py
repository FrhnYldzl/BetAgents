"""PAGE AUDIT — app_pro.py (8503) tüm sayfalar."""
import sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parent / "app_pro.py")
PAGES = ["Overview", "Live Calendar", "Trading Desk", "Coupon Engineer",
         "Model Catalog", "Analytics", "Data Excellency", "Risk Management",
         "Playbook", "Paper Trader"]

print("=" * 60)
print("  PAGE AUDIT — app_pro.py")
print("=" * 60)
for page in PAGES:
    try:
        at = AppTest.from_file(APP, default_timeout=40)
        at.session_state["nav_page"] = page
        at.session_state["page"] = page
        at.run()
        if at.exception:
            msg = "; ".join(str(e.value)[:140] for e in at.exception)
            print(f"  [FAIL] {page:18s} → {msg}")
        else:
            print(f"  [ OK ] {page:18s}")
    except Exception as e:
        print(f"  [CRASH] {page:18s} → {type(e).__name__}: {str(e)[:160]}")
