"""
CANLI · VERİTABANI — yalnız `cl_*` tabloları
=============================================
Üçüncü ürün: BetAgents ve Süper Toto'dan AYRI. Ortak olan tek şey bağlantı
yardımcısı (02_VERI/db.py). CANLI, `toto_*` ve BetAgents tablolarını yalnız
OKUR; kendi tablolarından başkasına yazmaz.

  cl_mac     izlenen canlı maç (iddaa olayı ↔ API-Football fikstürü eşleşmesi)
  cl_anlik   anlık görüntü: dakika, skor, iddaa 1/0/2 fiyatı, bizim olasılığımız
  cl_kupon   Toto kuponunun canlı durumu (hangi kademe ayakta, beklenen ödeme)
  cl_kayit   olay günlüğü
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_V = Path(__file__).resolve().parent.parent / "02_VERI"
if str(_V) not in sys.path:
    sys.path.insert(0, str(_V))

import db  # noqa: E402

SEMA = [
    """CREATE TABLE IF NOT EXISTS cl_mac (
        mac_id TEXT PRIMARY KEY, iddaa_id INTEGER, af_id INTEGER, lig TEXT,
        ev TEXT, dep TEXT, baslangic TEXT, ilk_gorulme TEXT, son_gorulme TEXT,
        toto_hafta INTEGER, toto_sira INTEGER, durum TEXT,
        sonuc_ev INTEGER, sonuc_dep INTEGER, oran_once TEXT)""",
    """CREATE TABLE IF NOT EXISTS cl_anlik (
        mac_id TEXT, ts TEXT, dakika INTEGER, safha TEXT, ev_skor INTEGER, dep_skor INTEGER,
        kirmizi_ev INTEGER, kirmizi_dep INTEGER, oran TEXT, p_piyasa TEXT, p_model TEXT,
        PRIMARY KEY (mac_id, ts))""",
    """CREATE TABLE IF NOT EXISTS cl_kupon (
        hafta_id INTEGER, profil TEXT, butce INTEGER, ts TEXT, icerik TEXT,
        PRIMARY KEY (hafta_id, profil, butce, ts))""",
    """CREATE TABLE IF NOT EXISTS cl_kayit (ts TEXT, tur TEXT, mesaj TEXT)""",
]


def simdi() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def kur() -> None:
    c = db.connect()
    try:
        for s in SEMA:
            c.execute(s)
        c.commit()
    finally:
        c.close()


def kayit(tur: str, mesaj: str) -> None:
    try:
        c = db.connect()
        try:
            c.execute("INSERT INTO cl_kayit (ts, tur, mesaj) VALUES (?, ?, ?)", (simdi(), tur, mesaj[:2000]))
            c.commit()
        finally:
            c.close()
    except Exception:
        pass


# ── maçlar ────────────────────────────────────────────────────────
def mac_yaz(m: dict) -> None:
    """Maçı yaz/güncelle. `oran_once` bir kez yazılır (maç öncesi fiyat kaybolmasın)."""
    c = db.connect()
    try:
        var = c.execute("SELECT ilk_gorulme, oran_once FROM cl_mac WHERE mac_id = ?",
                        (m["mac_id"],)).fetchone()
        ilk = var[0] if var else simdi()
        once = (var[1] if var and var[1] else None)
        if once is None and m.get("oran_once"):
            once = json.dumps(m["oran_once"])
        c.execute(
            "INSERT INTO cl_mac (mac_id, iddaa_id, af_id, lig, ev, dep, baslangic, ilk_gorulme, son_gorulme, "
            "toto_hafta, toto_sira, durum, sonuc_ev, sonuc_dep, oran_once) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT (mac_id) DO UPDATE SET af_id=excluded.af_id, lig=excluded.lig, "
            "son_gorulme=excluded.son_gorulme, toto_hafta=excluded.toto_hafta, toto_sira=excluded.toto_sira, "
            "durum=excluded.durum, sonuc_ev=excluded.sonuc_ev, sonuc_dep=excluded.sonuc_dep, "
            "oran_once=excluded.oran_once",
            (m["mac_id"], m.get("iddaa_id"), m.get("af_id"), m.get("lig"), m.get("ev"), m.get("dep"),
             m.get("baslangic"), ilk, simdi(), m.get("toto_hafta"), m.get("toto_sira"),
             m.get("durum"), m.get("sonuc_ev"), m.get("sonuc_dep"), once))
        c.commit()
    finally:
        c.close()


def oran_once_harita() -> dict:
    """mac_id → maç öncesi 1/0/2 oranı (modelin girdisi)."""
    c = db.connect()
    try:
        r = c.execute("SELECT mac_id, oran_once FROM cl_mac WHERE oran_once IS NOT NULL").fetchall()
    except Exception:
        return {}
    finally:
        c.close()
    out = {}
    for mid, v in r:
        try:
            out[mid] = json.loads(v)
        except Exception:
            pass
    return out


def anlik_yaz(mac_id: str, a: dict) -> None:
    c = db.connect()
    try:
        c.execute(
            "INSERT INTO cl_anlik (mac_id, ts, dakika, safha, ev_skor, dep_skor, kirmizi_ev, kirmizi_dep, "
            "oran, p_piyasa, p_model) VALUES (?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT (mac_id, ts) DO NOTHING",
            (mac_id, a.get("ts") or simdi(), a.get("dakika"), a.get("safha"), a.get("ev_skor"),
             a.get("dep_skor"), a.get("kirmizi_ev"), a.get("kirmizi_dep"),
             json.dumps(a.get("oran"), ensure_ascii=False) if a.get("oran") else None,
             json.dumps(a.get("p_piyasa")) if a.get("p_piyasa") else None,
             json.dumps(a.get("p_model")) if a.get("p_model") else None))
        c.commit()
    finally:
        c.close()


def canli_maclar(n: int = 60) -> list[dict]:
    """Son görülme sırasına göre, oynanmakta olan maçlar ve son anlık görüntüleri."""
    c = db.connect()
    try:
        r = c.execute(
            "SELECT m.mac_id, m.lig, m.ev, m.dep, m.baslangic, m.toto_hafta, m.toto_sira, m.durum, "
            "a.ts, a.dakika, a.safha, a.ev_skor, a.dep_skor, a.oran, a.p_piyasa, a.p_model, m.oran_once "
            "FROM cl_mac m JOIN cl_anlik a ON a.mac_id = m.mac_id "
            "WHERE a.ts = (SELECT MAX(ts) FROM cl_anlik b WHERE b.mac_id = m.mac_id) "
            "AND m.durum = 'canli' "
            "ORDER BY (m.toto_hafta IS NULL), m.toto_sira, a.dakika DESC").fetchall()
    except Exception:
        c.close()
        return []
    c.close()
    ad = ["mac_id", "lig", "ev", "dep", "baslangic", "toto_hafta", "toto_sira", "durum", "ts", "dakika",
          "safha", "ev_skor", "dep_skor", "oran", "p_piyasa", "p_model", "oran_once"]
    out = []
    for x in r[:n]:
        d = dict(zip(ad, x))
        for k in ("oran", "p_piyasa", "p_model", "oran_once"):
            try:
                d[k] = json.loads(d[k]) if d[k] else None
            except Exception:
                d[k] = None
        out.append(d)
    return out


def seri(mac_id: str, n: int = 400) -> list[dict]:
    """Bir maçın fiyat/durum serisi — canlı grafiğin kaynağı."""
    c = db.connect()
    try:
        r = c.execute("SELECT ts, dakika, ev_skor, dep_skor, oran, p_piyasa, p_model FROM cl_anlik "
                      "WHERE mac_id = ? ORDER BY ts", (mac_id,)).fetchall()
    finally:
        c.close()
    out = []
    for x in r[-n:]:
        d = {"ts": x[0], "dakika": x[1], "ev_skor": x[2], "dep_skor": x[3]}
        for k, v in (("oran", x[4]), ("p_piyasa", x[5]), ("p_model", x[6])):
            try:
                d[k] = json.loads(v) if v else None
            except Exception:
                d[k] = None
        out.append(d)
    return out


def kupon_yaz(hafta_id: int, profil: str, butce: int, icerik: dict) -> None:
    c = db.connect()
    try:
        c.execute("INSERT INTO cl_kupon (hafta_id, profil, butce, ts, icerik) VALUES (?,?,?,?,?) "
                  "ON CONFLICT (hafta_id, profil, butce, ts) DO NOTHING",
                  (hafta_id, profil, butce, simdi(), json.dumps(icerik, ensure_ascii=False, default=str)))
        c.commit()
    finally:
        c.close()


def son_kupon(hafta_id: int | None = None) -> list[dict]:
    c = db.connect()
    try:
        if hafta_id is None:
            r = c.execute("SELECT hafta_id, profil, butce, ts, icerik FROM cl_kupon "
                          "ORDER BY ts DESC").fetchall()
        else:
            r = c.execute("SELECT hafta_id, profil, butce, ts, icerik FROM cl_kupon WHERE hafta_id = ? "
                          "ORDER BY ts DESC", (hafta_id,)).fetchall()
    finally:
        c.close()
    gorulen, out = set(), []
    for x in r:
        k = (x[0], x[1], x[2])
        if k in gorulen:
            continue
        gorulen.add(k)
        try:
            ic = json.loads(x[4])
        except Exception:
            continue
        out.append({"hafta_id": x[0], "profil": x[1], "butce": x[2], "ts": x[3], **ic})
    return out


def sayim() -> dict:
    c = db.connect()
    try:
        m = c.execute("SELECT COUNT(*) FROM cl_mac").fetchone()[0]
        a = c.execute("SELECT COUNT(*) FROM cl_anlik").fetchone()[0]
        cl = c.execute("SELECT COUNT(*) FROM cl_mac WHERE durum = 'canli'").fetchone()[0]
    except Exception:
        return {"mac": 0, "anlik": 0, "canli": 0}
    finally:
        c.close()
    return {"mac": m, "anlik": a, "canli": cl}
