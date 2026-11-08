"""
SWAT · VERİ KATMANI — ilk yarı skoru ve maç istatistikleri
===========================================================
Kullanıcı kararı (08.11.2026): *"SoccersAPI dene ama karıştırma, diğer
ajanlar veya modeller yeni bir TAKIM kur buna odaklansın."*

⚠️ İZOLASYON ŞARTI. Bu modül KENDİ tablolarına yazar (`swat_*`).
`matches_v2`'ye tek bir sütun bile yazmaz — özellikle boş duran
`home_score_ht` alanına DOKUNMAZ. Sebep: oraya yazılsa ilk yarı skoru
bütün ajanlara açılır ve SWAT'ın ölçümü diğer takımlarınkiyle karışır.
BetAgists tablolarını yalnız OKUR (eşleştirme için).

NEDEN İLK YARI
---------------
Ölçüldü (01.11.2026, market_odds · 4.688 maç): iddaa ilk yarı pazarlarını
çok geniş açıyor ve bu pazarların fiyatı ELİMİZDE — oynamıyoruz çünkü
sonuçlandıramıyoruz.

    İY Maç Sonucu      %77,5 maçta açık   marj %16,6
    İY Alt/Üst 1.5     %63,1              marj %16,4
    İY Alt/Üst 0.5     %44,5              marj %15,8  ← ölçülen EN UCUZ
    İY/MS              %22,2              marj %26,4  ← en pahalı, oynanmaz

Tek eksik `home_score_ht` (matches_v2'de %0 dolu). O alan ayrıca İKİNCİ
YARI pazarlarını da açar: 2. yarı = maç sonu − ilk yarı.

⚠️ DOLULUK ORANI, KAPSAM DEĞİL
Her sağlayıcının "şu ligi kapsıyoruz" iddiası bir ŞEMA iddiasıdır, veri
iddiası değil. API-Football kendi dokümanında `coverage: true` bayrağının
"her maç için veri garantisi vermediğini" yazıyor; alt liglerde ilk
kaybolan alanlar şut ve topla oynamadır. Bu, projenin `iddaa veri
tuzakları` notundaki arızanın aynısı: veri gürültülü değil, SESSİZCE yok.
Bu yüzden `doluluk()` lig × alan bazında ölçer ve ajan yalnız doluluğu
ölçülmüş ligde oynar.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

KOK = Path(__file__).resolve().parent
for _p in (str(KOK), str(KOK.parent / "02_VERI")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import db  # noqa: E402

# Bir ligin oynanabilir sayılması için istenen asgari maç ve doluluk.
# Eşik altındaki lig SWAT'a kapalıdır — eksik veri sessizce yanlış
# sonuçlandırmaya değil, HİÇ oynamamaya yol açmalı.
ASGARI_MAC = 30
ASGARI_DOLULUK = 0.90

# İstatistik alanları — (sütun, insan okunur ad)
STAT_ALAN = (
    ("sut", "şut"), ("isabet", "isabetli şut"), ("korner", "korner"),
    ("sari", "sarı kart"), ("kirmizi", "kırmızı kart"),
    ("topla", "topla oynama %"),
)


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def kur(conn=None) -> None:
    kapat = conn is None
    conn = conn or db.connect()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS swat_mac (
                mac_id      TEXT PRIMARY KEY,
                iddaa_id    TEXT,
                kaynak      TEXT,
                kaynak_id   TEXT,
                lig         TEXT,
                sezon       TEXT,
                ev          TEXT,
                dep         TEXT,
                baslangic   TEXT,
                -- İLK YARI (asıl aradığımız) ve maç sonu (çapraz kontrol)
                iy_ev       INTEGER,
                iy_dep      INTEGER,
                ms_ev       INTEGER,
                ms_dep      INTEGER,
                -- maç istatistikleri
                sut_ev      INTEGER, sut_dep      INTEGER,
                isabet_ev   INTEGER, isabet_dep   INTEGER,
                korner_ev   INTEGER, korner_dep   INTEGER,
                sari_ev     INTEGER, sari_dep     INTEGER,
                kirmizi_ev  INTEGER, kirmizi_dep  INTEGER,
                topla_ev    REAL,    topla_dep    REAL,
                cekim_ts    TEXT
            )""")
        conn.execute("CREATE INDEX IF NOT EXISTS ix_swat_iddaa "
                     "ON swat_mac (iddaa_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS ix_swat_lig "
                     "ON swat_mac (lig)")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS swat_kayit (
                ts TEXT, tur TEXT, mesaj TEXT)""")
        conn.commit()
    finally:
        if kapat:
            conn.close()


def kayit(tur: str, mesaj: str, conn=None) -> None:
    kapat = conn is None
    conn = conn or db.connect()
    try:
        kur(conn)
        conn.execute("INSERT INTO swat_kayit (ts, tur, mesaj) VALUES (?,?,?)",
                     (_ts(), tur, str(mesaj)[:500]))
        conn.commit()
    except Exception:
        pass
    finally:
        if kapat:
            conn.close()


# ----------------------------------------------------------------------
# YAZMA
# ----------------------------------------------------------------------
SUTUNLAR = ("mac_id", "iddaa_id", "kaynak", "kaynak_id", "lig", "sezon",
            "ev", "dep", "baslangic", "iy_ev", "iy_dep", "ms_ev", "ms_dep",
            "sut_ev", "sut_dep", "isabet_ev", "isabet_dep",
            "korner_ev", "korner_dep", "sari_ev", "sari_dep",
            "kirmizi_ev", "kirmizi_dep", "topla_ev", "topla_dep", "cekim_ts")


def yaz(satirlar: list[dict], conn=None) -> int:
    """Maçları yaz/güncelle. Aynı maç yeniden çekilirse ÜZERİNE yazar —
    sağlayıcı sonradan istatistik tamamlayabiliyor."""
    if not satirlar:
        return 0
    kapat = conn is None
    conn = conn or db.connect()
    n = 0
    try:
        kur(conn)
        for s in satirlar:
            if not s.get("mac_id"):
                continue
            d = {k: s.get(k) for k in SUTUNLAR}
            d["cekim_ts"] = _ts()
            conn.execute(
                "INSERT INTO swat_mac (" + ",".join(SUTUNLAR) + ") VALUES ("
                + ",".join("?" * len(SUTUNLAR)) + ") "
                "ON CONFLICT (mac_id) DO UPDATE SET " + ",".join(
                    f"{k}=excluded.{k}" for k in SUTUNLAR if k != "mac_id"),
                tuple(d[k] for k in SUTUNLAR))
            n += 1
        conn.commit()
    finally:
        if kapat:
            conn.close()
    return n


# ----------------------------------------------------------------------
# OKUMA
# ----------------------------------------------------------------------
def ilk_yari(mac_id, conn=None):
    """(iy_ev, iy_dep) ya da None. Sonuçlandırmanın tek kapısı.

    None dönerse bahis KAPANMAZ (açık kalır) — void sayılmaz. Void,
    "sonucu belli oldu, iade" demektir; burada ise sonuç henüz bilinmiyor.
    İkisini karıştırmak ajanın karnesini sessizce bozar.
    """
    kapat = conn is None
    conn = conn or db.connect()
    try:
        r = conn.execute("SELECT iy_ev, iy_dep FROM swat_mac WHERE mac_id = ?",
                         (str(mac_id),)).fetchone()
    except Exception:
        return None
    finally:
        if kapat:
            conn.close()
    if not r or r[0] is None or r[1] is None:
        return None
    return int(r[0]), int(r[1])


def doluluk(conn=None) -> list[dict]:
    """Lig × alan doluluk oranı — hangi ligde hangi alan GERÇEKTEN var.

    Sağlayıcının kapsam iddiası değil, bizim ölçümümüz. `oynanabilir`
    yalnız ilk yarı skoru yeterince doluysa ve örneklem yeterliyse True.
    """
    kapat = conn is None
    conn = conn or db.connect()
    try:
        kur(conn)
        alanlar = ["iy_ev"] + [f"{a}_ev" for a, _ in STAT_ALAN]
        sec = ", ".join(f"SUM(CASE WHEN {a} IS NULL THEN 0 ELSE 1 END)"
                        for a in alanlar)
        # ⚠️ Doluluk YALNIZ BİTMİŞ maçlar üzerinden ölçülür. Tabloda
        # oynanmamış maçlar da duruyor (SWAT'ın evrenini tanımlamak için
        # gelecek fikstür de yazılıyor) ve onların ilk yarı skoru
        # doğal olarak boş. Hepsini saymak, sağlam bir ligi "verisi
        # eksik" diye kapatırdı — sezonun yarısı henüz oynanmadığı için.
        r = conn.execute(
            f"SELECT lig, COUNT(*), {sec} FROM swat_mac "
            "WHERE ms_ev IS NOT NULL GROUP BY lig").fetchall()
    finally:
        if kapat:
            conn.close()
    out = []
    for sat in r:
        lig, n = sat[0], int(sat[1])
        if not n:
            continue
        d = {"lig": lig or "?", "n": n}
        for i, a in enumerate(alanlar):
            d[a] = int(sat[2 + i]) / n
        d["oynanabilir"] = bool(n >= ASGARI_MAC
                                and d["iy_ev"] >= ASGARI_DOLULUK)
        out.append(d)
    return sorted(out, key=lambda x: -x["n"])


def oynanabilir_ligler(conn=None) -> set:
    """SWAT'ın oynamasına izin verilen ligler — ölçülmüş doluluğa göre."""
    return {d["lig"] for d in doluluk(conn) if d["oynanabilir"]}


def kendi_testi() -> list[str]:
    """Veritabanısız: şema, yazma/okuma ve doluluk eşiği."""
    import os
    import sqlite3
    import tempfile
    hata = []
    yol = os.path.join(tempfile.gettempdir(), f"swat_{os.getpid()}.db")
    try:
        os.unlink(yol)
    except OSError:
        pass
    try:
        c = sqlite3.connect(yol)
        kur(c)
        # 1) İlk yarı skoru yoksa None dönmeli — "void" DEĞİL
        yaz([{"mac_id": "m1", "lig": "T1", "iy_ev": None, "iy_dep": None,
               "ms_ev": 1, "ms_dep": 0}], c)
        if ilk_yari("m1", c) is not None:
            hata.append("ilk yarı skoru yokken None dönmeli")
        yaz([{"mac_id": "m2", "lig": "T1", "iy_ev": 1, "iy_dep": 0,
               "ms_ev": 2, "ms_dep": 0}], c)
        if ilk_yari("m2", c) != (1, 0):
            hata.append(f"ilk yarı skoru okunamadı: {ilk_yari('m2', c)}")
        # 2) Üzerine yazma: sağlayıcı sonradan tamamlayabiliyor
        yaz([{"mac_id": "m1", "lig": "T1", "iy_ev": 2, "iy_dep": 2,
               "ms_ev": 3, "ms_dep": 2}], c)
        if ilk_yari("m1", c) != (2, 2):
            hata.append("ikinci çekim üzerine yazmalı")
        # 3) Doluluk eşiği: az maçlı lig OYNANABİLİR OLMAMALI
        d = {x["lig"]: x for x in doluluk(c)}
        if d.get("T1", {}).get("oynanabilir"):
            hata.append(f"n=2 ile lig oynanabilir sayıldı (asgari "
                        f"{ASGARI_MAC})")
        # 4) Eşiği geçen lig oynanabilir olmalı
        yaz([{"mac_id": f"x{i}", "lig": "L2", "iy_ev": 0, "iy_dep": 0,
              "ms_ev": 1, "ms_dep": 1} for i in range(ASGARI_MAC)], c)
        if "L2" not in oynanabilir_ligler(c):
            hata.append("eşiği geçen lig oynanabilir olmalı")
        # 5) İlk yarısı eksik lig eşiği geçmemeli
        yaz([{"mac_id": f"y{i}", "lig": "L3", "ms_ev": 1, "ms_dep": 0,
              "iy_ev": (0 if i % 2 else None),
              "iy_dep": (0 if i % 2 else None)}
             for i in range(ASGARI_MAC + 10)], c)
        if "L3" in oynanabilir_ligler(c):
            hata.append("ilk yarı doluluğu %50 olan lig oynanabilir sayıldı")
        # 6) OYNANMAMIŞ maçlar doluluğu düşürmemeli: sağlam bir lige
        #    sezonun kalan fikstürü eklenince kapanmamalı.
        yaz([{"mac_id": f"z{i}", "lig": "L2"} for i in range(200)], c)
        if "L2" not in oynanabilir_ligler(c):
            hata.append("gelecek fikstür sağlam ligi kapattı — doluluk "
                        "yalnız bitmiş maçlar üzerinden ölçülmeli")
        c.close()
    except Exception as e:
        hata.append(f"{type(e).__name__}: {e}")
    finally:
        try:
            os.unlink(yol)
        except OSError:
            pass
    return hata


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    h = kendi_testi()
    print("kendi testi:", "TEMİZ" if not h else f"{len(h)} sorun")
    for x in h:
        print("  ", x)
