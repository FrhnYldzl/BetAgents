"""
PAGE AUDIT — Tüm sayfaları headless render edip hataları yakala.
Streamlit AppTest kullanır (tarayıcı gerektirmez).
"""
import sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")

from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parent / "app_trader.py")

PAGES = ["Overview", "Matches", "Charts", "Positions",
         "Orders", "Risk", "Journal", "Settings"]

print("=" * 60)
print("  PAGE AUDIT — app_trader.py")
print("=" * 60)

results = {}
for page in PAGES:
    try:
        at = AppTest.from_file(APP, default_timeout=30)
        at.session_state["page"] = page
        at.run()
        if at.exception:
            # at.exception is a list of ElementList
            excs = at.exception
            msg = "; ".join(str(e.value)[:120] for e in excs) if excs else "?"
            results[page] = ("FAIL", msg)
            print(f"  [FAIL] {page:12s} → {msg}")
        else:
            results[page] = ("OK", "")
            print(f"  [ OK ] {page:12s}")
    except Exception as e:
        import traceback
        results[page] = ("CRASH", str(e)[:200])
        print(f"  [CRASH] {page:12s} → {type(e).__name__}: {str(e)[:160]}")

print()
n_ok = sum(1 for v in results.values() if v[0] == "OK")
print(f"SONUC: {n_ok}/{len(PAGES)} sayfa temiz")
fails = {k: v for k, v in results.items() if v[0] != "OK"}
if fails:
    print("\nHATALAR:")
    for page, (status, msg) in fails.items():
        print(f"  {page}: [{status}] {msg}")
