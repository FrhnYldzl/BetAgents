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

if role == "worker":
    os.execvp(sys.executable, [sys.executable, str(THIS / "worker.py")])
else:
    port = os.environ.get("PORT", "8080")
    os.execvp(sys.executable, [
        sys.executable, "-m", "streamlit", "run",
        str(THIS / "08_AI_TRADER" / "app_unified.py"),
        "--server.port", port,
        "--server.address", "0.0.0.0",
    ])
