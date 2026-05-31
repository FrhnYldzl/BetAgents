"""
Railway başlatıcı — tek imaj, ROLE değişkeniyle servis ayrımı.
=============================================================
  ROLE=worker  → python worker.py        (auto_play + auto_settle zamanlayıcı)
  ROLE (boş)   → streamlit app_unified    (web UI, $PORT)

Böylece web ve worker AYNI Docker imajını kullanır; fark sadece ROLE
ortam değişkenidir (Railway CLI ile set edilebilir → dashboard'a gerek yok).
"""
import os
import sys
from pathlib import Path

THIS = Path(__file__).resolve().parent
role = (os.environ.get("ROLE") or "web").strip().lower()
port = os.environ.get("PORT", "8080")
app_file = THIS / "08_AI_TRADER" / "app_unified.py"

# ── BOOT TANI (Railway loglarında görünür) ─────────────────────
print("=" * 56, flush=True)
print(f"[start.py] BOOT", flush=True)
print(f"  python      : {sys.version.split()[0]}", flush=True)
print(f"  cwd         : {os.getcwd()}", flush=True)
print(f"  ROLE        : {role}", flush=True)
print(f"  PORT        : {port}", flush=True)
print(f"  DATABASE_URL: {'SET ('+os.environ['DATABASE_URL'][:11]+'…)' if os.environ.get('DATABASE_URL') else 'YOK → SQLite (veri olmayabilir)'}", flush=True)
print(f"  app dosyası : {app_file}  (var mı: {app_file.exists()})", flush=True)
try:
    import streamlit  # noqa
    print(f"  streamlit   : {streamlit.__version__}", flush=True)
except Exception as e:
    print(f"  streamlit   : IMPORT HATASI → {e}", flush=True)
print("=" * 56, flush=True)

if role == "worker":
    os.execvp(sys.executable, [sys.executable, str(THIS / "worker.py")])
else:
    os.execvp(sys.executable, [
        sys.executable, "-m", "streamlit", "run", str(app_file),
        "--server.port", port,
        "--server.address", "0.0.0.0",
        "--server.headless", "true",
    ])
