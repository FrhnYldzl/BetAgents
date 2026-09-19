"""
Arayüzü ÜRETİME DOKUNMADAN yerelde çalıştır (geliştirici aracı).

Veri: 02_VERI/ui_onizleme.db — üretimin salt okuma anlık görüntüsü (SQLite,
git dışında). Tazelemek için: python 02_VERI/ui_onizleme_al.py

NEDEN: yerelde çalışan arayüz üretime bağlanırsa Railway'in genel proxy'sini
tutar ve canlı siteyi dondurabilir (bu projede yaşandı). Burada DATABASE_URL
boşlukla ayarlanır ki .env onu üretim adresiyle doldurmasın; BETAGENTS_DB
'local' olmasın ki uygulama Railway tüneli beklemesin.

⚠️ SQLite'ta PostgreSQL'e özgü birkaç sorgu (string_agg) boş döner — kasa
eğrisi önizlemede görünmez; canlıda görünür.

    python 08_AI_TRADER/onizleme.py        # http://127.0.0.1:8610
"""
import os
import subprocess
import sys

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ["BETAGENTS_DB"] = "sqlite"
os.environ["DATABASE_URL"] = " "
os.environ["BETAGENTS_SQLITE_PATH"] = os.path.join(KOK, "02_VERI", "ui_onizleme.db")
if not os.path.isfile(os.environ["BETAGENTS_SQLITE_PATH"]):
    sys.exit("Önizleme verisi yok — önce: python 02_VERI/ui_onizleme_al.py")
sys.exit(subprocess.call([
    sys.executable, "-m", "streamlit", "run",
    os.path.join(KOK, "08_AI_TRADER", "app_v2.py"),
    "--server.port", "8610", "--server.headless", "true",
    "--server.address", "127.0.0.1", "--browser.gatherUsageStats", "false",
    "--theme.base", "light", "--theme.backgroundColor", "#fcfdfe",
    "--theme.secondaryBackgroundColor", "#f6f9fb", "--theme.textColor", "#0a1220",
    "--theme.primaryColor", "#9a6410"]))
