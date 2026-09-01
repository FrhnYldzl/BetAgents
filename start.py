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
# ── HANGI UYGULAMA? ────────────────────────────────────────────
# APP=v2  → yeni Desk (app_v2.py)
# APP boş → mevcut birleşik uygulama (app_unified.py)
#
# İki sürüm YAN YANA çalışabilsin diye anahtar env'de: Railway'de
# ikinci bir servis açıp APP=v2 vermek yeterli. Mevcut servise
# dokunmadan V2 yayına alınır; hazır olunca anahtar çevrilir.
_app = (os.environ.get("APP") or "").strip().lower()
app_file = (THIS / "08_AI_TRADER" /
            ("app_v2.py" if _app in ("v2", "desk") else "app_unified.py"))

# ── BOOT TANI (Railway loglarında görünür) ─────────────────────
print("=" * 56, flush=True)
print(f"[start.py] BOOT", flush=True)
print(f"  python      : {sys.version.split()[0]}", flush=True)
print(f"  cwd         : {os.getcwd()}", flush=True)
print(f"  ROLE        : {role}", flush=True)
print(f"  APP         : {_app or '(v1 · app_unified)'}", flush=True)
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
    _wc = [sys.executable, str(THIS / "worker.py")]
    if os.name == "nt":
        sys.exit(subprocess.call(_wc))
    os.execvp(sys.executable, _wc)
else:
    # Web servisi → otomasyonu arka planda ayrı süreç olarak başlat (tek-servis otonomi),
    # sonra streamlit'i ön planda çalıştır. Popen child, execvp'den sonra yaşamaya devam eder.
    if inline_worker:
        try:
            subprocess.Popen([sys.executable, str(THIS / "worker.py")])
            print("[start.py] inline worker başlatıldı (arka plan: auto_play + auto_settle)", flush=True)
        except Exception as e:
            print(f"[start.py] inline worker başlatılamadı: {e}", flush=True)
    _cmd = [sys.executable, "-m", "streamlit", "run", str(app_file),
            "--server.port", port,
            "--server.address", "0.0.0.0",
            "--server.headless", "true"]
    # ⚠️ Windows'ta os.execvp, bosluklu yolu ("C:\Program Files\...")
    # boluyor ve "C:\Program" diye acmaya calisiyor. Linux'ta (Railway)
    # exec dogru davranis — sinyaller dogrudan surece gider. Bu yuzden
    # platforma gore ayriliyor.
    if os.name == "nt":
        sys.exit(subprocess.call(_cmd))
    os.execvp(sys.executable, _cmd)
