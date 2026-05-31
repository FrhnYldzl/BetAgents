"""
Railway başlatıcı — tek imaj, ROLE değişkeniyle servis ayrımı.
=============================================================
  ROLE=worker  → python worker.py        (auto_play + auto_settle zamanlayıcı)
  ROLE (boş)   → streamlit app_unified    (web UI, $PORT)
                 + arka planda worker.py (INLINE_WORKER=0 ile kapatılabilir)

Web servisi varsayılan olarak otomasyon zamanlayıcısını da AYNI container'da
arka plan süreci olarak başlatır → ayrı worker servisine / Railway login'e
GEREK YOK, sistem tek serviste 7/24 otonom çalışır.

Ayrı bir 'worker' servisi açarsan, web'de INLINE_WORKER=0 ver (çift tetikleme olmasın).
"""
import os
import sys
import subprocess
from pathlib import Path

THIS = Path(__file__).resolve().parent
role = (os.environ.get("ROLE") or "web").strip().lower()
port = os.environ.get("PORT", "8080")
inline_worker = (os.environ.get("INLINE_WORKER", "1").strip() != "0")
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
print(f"  INLINE_WORKER: {'AÇIK (web + otomasyon)' if (role != 'worker' and inline_worker) else 'kapalı/uygulanmaz'}", flush=True)
print("=" * 56, flush=True)

if role == "worker":
    # Adanmış worker servisi → sadece zamanlayıcı.
    os.execvp(sys.executable, [sys.executable, str(THIS / "worker.py")])
else:
    # Web servisi → otomasyonu arka planda ayrı süreç olarak başlat (tek-servis otonomi),
    # sonra streamlit'i ön planda çalıştır. Popen child, execvp'den sonra yaşamaya devam eder.
    if inline_worker:
        try:
            subprocess.Popen([sys.executable, str(THIS / "worker.py")])
            print("[start.py] inline worker başlatıldı (arka plan: auto_play + auto_settle)", flush=True)
        except Exception as e:
            print(f"[start.py] inline worker başlatılamadı: {e}", flush=True)
    os.execvp(sys.executable, [
        sys.executable, "-m", "streamlit", "run", str(app_file),
        "--server.port", port,
        "--server.address", "0.0.0.0",
        "--server.headless", "true",
    ])
