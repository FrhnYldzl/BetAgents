"""
TOTO · YEREL ÇALIŞTIRICI — üretime DOKUNMADAN önizleme verisini doldurur
=======================================================================
Toto zamanlayıcısının işlerini bir kez, arayüz önizlemesinin SQLite dosyasına
(02_VERI/ui_onizleme.db) karşı çalıştırır. DATABASE_URL boşlukla ayarlanır ki
.env'deki üretim adresi devreye girmesin (railway-genel-proxy dersi).

    python 09_TOTO/yerel.py            # senkron + analiz → önizleme DB
    python 08_AI_TRADER/onizleme.py    # http://127.0.0.1:8610 → SÜPER TOTO
"""
import os
import sys

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ["BETAGENTS_DB"] = "sqlite"
os.environ["DATABASE_URL"] = " "
os.environ["BETAGENTS_SQLITE_PATH"] = os.path.join(KOK, "02_VERI", "ui_onizleme.db")
if not os.path.isfile(os.environ["BETAGENTS_SQLITE_PATH"]):
    sys.exit("Önizleme verisi yok — önce: python 02_VERI/ui_onizleme_al.py")
sys.path.insert(0, os.path.join(KOK, "09_TOTO"))

import toto_db  # noqa: E402
import toto_worker  # noqa: E402

import db  # noqa: E402

assert not db.is_postgres(), "yerel.py yalnız SQLite önizlemesine yazar"
toto_db.kur()
toto_worker.senkron()
toto_worker.analiz()
print("önizleme verisi hazır:", os.environ["BETAGENTS_SQLITE_PATH"])
