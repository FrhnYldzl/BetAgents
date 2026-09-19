"""
TOTO · VERİTABANI — yalnız `toto_*` tabloları
=============================================
BetAgents ile aynı veritabanı sunucusunu paylaşır ama AYRI tablolarda yaşar:
BetAgents kodu bu tablolara dokunmaz, Toto kodu BetAgents tablolarına YAZMAZ.
Bağlantı yardımcısı ortak (02_VERI/db.py — yerelde SQLite, Railway'de PostgreSQL);
her işlem kısa ömürlü bağlantı açar-kapatır (kilit kuyruğu ve bağlantı kotası dersi).

Tablolar
  toto_hafta   Spor Toto haftası: kapanış, ilk görülme (yayın), kazanan/ikramiye, D, devir
  toto_mac     haftanın 15 maçı ve sonuçları
  toto_analiz  canlı analizin tam çıktısı (JSON) — panel buradan çizer
  toto_kupon   önerilen kâğıt kuponlar (profil × bütçe) ve gerçekleşen sonuçları
  toto_cuzdan  ajan pazarının hafta sonu cüzdanları
  toto_ders    hafta sonrası inceleme (neden kazandık/kaybettik)
  toto_kayit   olay günlüğü (yayın, analiz, hata)
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_V = Path(__file__).resolve().parent.parent / "02_VERI"
if str(_V) not in sys.path:
    sys.path.insert(0, str(_V))

import db  # noqa: E402  (ortak bağlantı yardımcısı — yalnız bağlantı)

SEMA = [
    """CREATE TABLE IF NOT EXISTS toto_hafta (
        hafta_id INTEGER PRIMARY KEY, sezon TEXT, ad TEXT, kapanis TEXT, ilk_gorulme TEXT,
        liste_gorseli TEXT, durum TEXT,
        n15 INTEGER, n14 INTEGER, n13 INTEGER, n12 INTEGER,
        odul15 DOUBLE PRECISION, odul14 DOUBLE PRECISION, odul13 DOUBLE PRECISION, odul12 DOUBLE PRECISION,
        dagitilan DOUBLE PRECISION, devir_json TEXT, guncelleme TEXT)""",
    """CREATE TABLE IF NOT EXISTS toto_mac (
        hafta_id INTEGER, sira INTEGER, tarih TEXT, turnuva TEXT, aile TEXT, ev TEXT, dep TEXT,
        sonuc TEXT, noter INTEGER, PRIMARY KEY (hafta_id, sira))""",
    """CREATE TABLE IF NOT EXISTS toto_analiz (
        hafta_id INTEGER, ts TEXT, icerik TEXT, PRIMARY KEY (hafta_id, ts))""",
    """CREATE TABLE IF NOT EXISTS toto_kupon (
        hafta_id INTEGER, profil TEXT, butce INTEGER, ts TEXT, kolon INTEGER,
        maliyet DOUBLE PRECISION, isaret TEXT, ev DOUBLE PRECISION, p15 DOUBLE PRECISION,
        p12p DOUBLE PRECISION, dogru INTEGER, odeme DOUBLE PRECISION, durum TEXT, sonuc_ts TEXT,
        PRIMARY KEY (hafta_id, profil, butce))""",
    """CREATE TABLE IF NOT EXISTS toto_cuzdan (
        hafta_id INTEGER, ajan TEXT, servet DOUBLE PRECISION, PRIMARY KEY (hafta_id, ajan))""",
    """CREATE TABLE IF NOT EXISTS toto_ders (hafta_id INTEGER PRIMARY KEY, ts TEXT, icerik TEXT)""",
    """CREATE TABLE IF NOT EXISTS toto_kayit (ts TEXT, tur TEXT, mesaj TEXT)""",
]


def simdi() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _baglan():
    return db.connect()


def kur() -> None:
    c = _baglan()
    try:
        for s in SEMA:
            c.execute(s)
        c.commit()
    finally:
        c.close()


def kayit(tur: str, mesaj: str) -> None:
    try:
        c = _baglan()
        try:
            c.execute("INSERT INTO toto_kayit (ts, tur, mesaj) VALUES (?, ?, ?)", (simdi(), tur, mesaj[:2000]))
            c.commit()
        finally:
            c.close()
    except Exception:
        pass


def hafta_yaz(h: dict, ilk_gorulme: str | None = None) -> bool:
    """Haftayı yaz/güncelle. Dönen: bu hafta İLK KEZ mi görüldü (yayın anı)."""
    c = _baglan()
    try:
        var = c.execute("SELECT ilk_gorulme FROM toto_hafta WHERE hafta_id = ?", (h["id"],)).fetchone()
        ilk = ilk_gorulme or (var[0] if var else simdi())
        n, o = h.get("n") or {}, h.get("odul") or {}
        durum = "sonuclandi" if h.get("ikramiye") else ("kapandi" if (h.get("kapanis") or "") < _tr_simdi() else "acik")
        c.execute(
            "INSERT INTO toto_hafta (hafta_id, sezon, ad, kapanis, ilk_gorulme, liste_gorseli, durum, n15, n14, n13, "
            "n12, odul15, odul14, odul13, odul12, dagitilan, devir_json, guncelleme) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT (hafta_id) DO UPDATE SET "
            "sezon=excluded.sezon, ad=excluded.ad, kapanis=excluded.kapanis, liste_gorseli=excluded.liste_gorseli, "
            "durum=excluded.durum, n15=excluded.n15, n14=excluded.n14, n13=excluded.n13, n12=excluded.n12, "
            "odul15=excluded.odul15, odul14=excluded.odul14, odul13=excluded.odul13, odul12=excluded.odul12, "
            "dagitilan=excluded.dagitilan, devir_json=excluded.devir_json, guncelleme=excluded.guncelleme",
            (h["id"], h.get("sezon"), h.get("ad"), h.get("kapanis"), ilk, h.get("liste_gorseli"), durum,
             n.get(15), n.get(14), n.get(13), n.get(12), o.get(15), o.get(14), o.get(13), o.get(12),
             h.get("D"), json.dumps({"gelen": h.get("devir_gelen"), "giden": h.get("devir_giden")}), simdi()))
        for i, m in enumerate(h.get("maclar") or [], 1):
            c.execute(
                "INSERT INTO toto_mac (hafta_id, sira, tarih, turnuva, aile, ev, dep, sonuc, noter) "
                "VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT (hafta_id, sira) DO UPDATE SET tarih=excluded.tarih, "
                "turnuva=excluded.turnuva, aile=excluded.aile, ev=excluded.ev, dep=excluded.dep, "
                "sonuc=excluded.sonuc, noter=excluded.noter",
                (h["id"], i, m.get("tarih"), str(m.get("turnuva")), m.get("aile"), m.get("ev"), m.get("dep"),
                 None if m.get("sonuc") is None else ("1", "0", "2")[m["sonuc"]],
                 1 if m.get("noter") else 0))
        c.commit()
        return var is None
    finally:
        c.close()


def _tr_simdi() -> str:
    from datetime import timedelta
    return (datetime.now(timezone.utc) + timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M:%S")


def analiz_yaz(hafta_id: int, icerik: str) -> None:
    c = _baglan()
    try:
        c.execute("INSERT INTO toto_analiz (hafta_id, ts, icerik) VALUES (?, ?, ?)", (hafta_id, simdi(), icerik))
        # hafta başına yalnız son 3 analiz (≈80 KB/analiz; kupon ve ders ayrı tablolarda kalıcı)
        eski = c.execute("SELECT ts FROM toto_analiz WHERE hafta_id = ? ORDER BY ts DESC", (hafta_id,)).fetchall()
        for r in eski[3:]:
            c.execute("DELETE FROM toto_analiz WHERE hafta_id = ? AND ts = ?", (hafta_id, r[0]))
        c.commit()
    finally:
        c.close()


def son_analiz(hafta_id: int | None = None) -> dict | None:
    c = _baglan()
    try:
        if hafta_id is None:
            r = c.execute("SELECT icerik FROM toto_analiz ORDER BY hafta_id DESC, ts DESC LIMIT 1").fetchone()
        else:
            r = c.execute("SELECT icerik FROM toto_analiz WHERE hafta_id = ? ORDER BY ts DESC LIMIT 1",
                          (hafta_id,)).fetchone()
        return json.loads(r[0]) if r else None
    finally:
        c.close()


def kupon_yaz(hafta_id: int, kuponlar: list[dict]) -> None:
    c = _baglan()
    try:
        for k in kuponlar:
            c.execute(
                "INSERT INTO toto_kupon (hafta_id, profil, butce, ts, kolon, maliyet, isaret, ev, p15, p12p, durum) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT (hafta_id, profil, butce) DO UPDATE SET ts=excluded.ts, "
                "kolon=excluded.kolon, maliyet=excluded.maliyet, isaret=excluded.isaret, ev=excluded.ev, "
                "p15=excluded.p15, p12p=excluded.p12p, durum=excluded.durum",
                (hafta_id, k["profil"], k["butce"], simdi(), k["kolon"], k["maliyet"], json.dumps(k["S"]),
                 k["ev"], k["p15"], k["p12p"], "kagit"))
        c.commit()
    finally:
        c.close()


def kuponlar(hafta_id: int | None = None) -> list[dict]:
    c = _baglan()
    try:
        q = ("SELECT hafta_id, profil, butce, ts, kolon, maliyet, isaret, ev, p15, p12p, dogru, odeme, durum "
             "FROM toto_kupon")
        rows = c.execute(q + (" WHERE hafta_id = ?" if hafta_id else "") + " ORDER BY hafta_id DESC",
                         (hafta_id,) if hafta_id else None).fetchall()
        ad = ["hafta_id", "profil", "butce", "ts", "kolon", "maliyet", "isaret", "ev", "p15", "p12p", "dogru",
              "odeme", "durum"]
        return [dict(zip(ad, r)) for r in rows]
    finally:
        c.close()


def kupon_kapat(hafta_id: int, profil: str, butce: int, dogru: int, odeme: float) -> None:
    c = _baglan()
    try:
        c.execute("UPDATE toto_kupon SET dogru = ?, odeme = ?, durum = 'sonuclandi', sonuc_ts = ? "
                  "WHERE hafta_id = ? AND profil = ? AND butce = ?", (dogru, odeme, simdi(), hafta_id, profil, butce))
        c.commit()
    finally:
        c.close()


def cuzdan_yaz(hafta_id: int, W: dict) -> None:
    c = _baglan()
    try:
        for a, w in W.items():
            c.execute("INSERT INTO toto_cuzdan (hafta_id, ajan, servet) VALUES (?,?,?) ON CONFLICT (hafta_id, ajan) "
                      "DO UPDATE SET servet=excluded.servet", (hafta_id, a, float(w)))
        c.commit()
    finally:
        c.close()


def son_cuzdan() -> dict | None:
    c = _baglan()
    try:
        r = c.execute("SELECT MAX(hafta_id) FROM toto_cuzdan").fetchone()
        if not r or r[0] is None:
            return None
        rows = c.execute("SELECT ajan, servet FROM toto_cuzdan WHERE hafta_id = ?", (r[0],)).fetchall()
        return {a: float(w) for a, w in rows}
    finally:
        c.close()


def cuzdan_gecmisi() -> list[tuple]:
    c = _baglan()
    try:
        return c.execute("SELECT hafta_id, ajan, servet FROM toto_cuzdan ORDER BY hafta_id").fetchall()
    finally:
        c.close()


def ders_yaz(hafta_id: int, icerik: dict) -> None:
    c = _baglan()
    try:
        c.execute("INSERT INTO toto_ders (hafta_id, ts, icerik) VALUES (?,?,?) ON CONFLICT (hafta_id) DO UPDATE "
                  "SET ts=excluded.ts, icerik=excluded.icerik", (hafta_id, simdi(), json.dumps(icerik, ensure_ascii=False)))
        c.commit()
    finally:
        c.close()


def dersler(n: int = 20) -> list[dict]:
    c = _baglan()
    try:
        rows = c.execute("SELECT hafta_id, ts, icerik FROM toto_ders ORDER BY hafta_id DESC LIMIT ?", (n,)).fetchall()
        return [{"hafta_id": r[0], "ts": r[1], **json.loads(r[2])} for r in rows]
    finally:
        c.close()


def haftalar_tablo(n: int = 30) -> list[dict]:
    c = _baglan()
    try:
        rows = c.execute("SELECT hafta_id, sezon, ad, kapanis, ilk_gorulme, durum, n15, odul15, dagitilan, devir_json "
                         "FROM toto_hafta ORDER BY hafta_id DESC LIMIT ?", (n,)).fetchall()
        ad = ["hafta_id", "sezon", "ad", "kapanis", "ilk_gorulme", "durum", "n15", "odul15", "dagitilan", "devir_json"]
        return [dict(zip(ad, r)) for r in rows]
    finally:
        c.close()


def son_kayitlar(n: int = 30) -> list[tuple]:
    c = _baglan()
    try:
        return c.execute("SELECT ts, tur, mesaj FROM toto_kayit ORDER BY ts DESC LIMIT ?", (n,)).fetchall()
    finally:
        c.close()
