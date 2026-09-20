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
# VARSAYILAN: V2 (app_v2.py) — 01.09.2026'da cevrildi.
#   APP=v1 (veya "unified") → eski 40 sayfalik app_unified.py
#   APP bos / v2 / desk     → yeni Desk
#
# Neden varsayilan cevrildi: Railway panel erisimi olmadan yayina
# almanin tek yolu buydu. GERI ALMAK icin iki yol var —
#   (a) Railway degiskeni: APP=v1
#   (b) bu satiri eski haline dondur, push et
# V1 kod tabaninda AYNEN duruyor, silinmedi.
_app = (os.environ.get("APP") or "").strip().lower()
_eski = _app in ("v1", "unified", "legacy")
app_file = (THIS / "08_AI_TRADER" /
            ("app_unified.py" if _eski else "app_v2.py"))

# ── BOOT TANI (Railway loglarında görünür) ─────────────────────
print("=" * 56, flush=True)
print(f"[start.py] BOOT", flush=True)
print(f"  python      : {sys.version.split()[0]}", flush=True)
print(f"  cwd         : {os.getcwd()}", flush=True)
print(f"  ROLE        : {role}", flush=True)
print(f"  APP         : {_app or '(varsayilan)'} -> {app_file.name}", flush=True)
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
    # SÜPER TOTO — BetAgents'tan AYRI süreç, yalnız toto_* tablolarına yazar.
    # TOTO_WORKER=0 ile kapanır; çökerse yalnız Toto durur.
    _toto = THIS / "09_TOTO" / "toto_worker.py"
    if (os.environ.get("TOTO_WORKER", "1").strip() != "0") and _toto.exists():
        try:
            subprocess.Popen([sys.executable, str(_toto)])
            print("[start.py] Toto zamanlayıcı başlatıldı (ayrı süreç)", flush=True)
        except Exception as e:
            print(f"[start.py] Toto zamanlayıcı başlatılamadı: {e}", flush=True)
    # CANLI — üçüncü ürün, yine AYRI süreç, yalnız cl_* tablolarına yazar.
    # CANLI_WORKER=0 ile kapanır; çökerse yalnız canlı toplama durur.
    _canli = THIS / "10_CANLI" / "canli_worker.py"
    if (os.environ.get("CANLI_WORKER", "1").strip() != "0") and _canli.exists():
        try:
            subprocess.Popen([sys.executable, str(_canli)])
            print("[start.py] CANLI toplayıcı başlatıldı (ayrı süreç)", flush=True)
        except Exception as e:
            print(f"[start.py] CANLI toplayıcı başlatılamadı: {e}", flush=True)
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
