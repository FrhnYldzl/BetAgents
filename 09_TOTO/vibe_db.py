"""
VIBE BETTING · VERİTABANI — yalnız `vibe_*` tabloları
======================================================
Sohbet oturumları, mesajlar, geri bildirimler ve iş istekleri. Toto ve BetAgents
tablolarına YAZMAZ (onları yalnız okur — bkz. vibe_arac.py). Bağlantı yardımcısı
ortak (02_VERI/db.py); her işlem kısa ömürlü bağlantı açar-kapatır.

  vibe_oturum        sohbet oturumu (Claude'daki "session")
  vibe_mesaj         oturumun mesajları + o turda çağrılan araçların izi
  vibe_geri_bildirim kullanıcının yazılım/oyun geri bildirimi — geliştirme kanalı
  vibe_istek         panelden istenen iş (ör. analizi tazele); worker yürütür
"""
from __future__ import annotations

import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

_V = Path(__file__).resolve().parent.parent / "02_VERI"
if str(_V) not in sys.path:
    sys.path.insert(0, str(_V))

import db  # noqa: E402

SEMA = [
    """CREATE TABLE IF NOT EXISTS vibe_oturum (
        oturum_id TEXT PRIMARY KEY, baslik TEXT, olusturma TEXT, guncelleme TEXT, n_mesaj INTEGER)""",
    """CREATE TABLE IF NOT EXISTS vibe_mesaj (
        oturum_id TEXT, sira INTEGER, rol TEXT, metin TEXT, arac TEXT, ts TEXT,
        PRIMARY KEY (oturum_id, sira))""",
    """CREATE TABLE IF NOT EXISTS vibe_geri_bildirim (
        gb_id TEXT PRIMARY KEY, oturum_id TEXT, tur TEXT, baslik TEXT, metin TEXT, ts TEXT, durum TEXT)""",
    """CREATE TABLE IF NOT EXISTS vibe_istek (
        istek_id TEXT PRIMARY KEY, oturum_id TEXT, tur TEXT, param TEXT, ts TEXT, durum TEXT,
        sonuc TEXT, bitis TEXT)""",
]
TURLER = ("hata", "istek", "fikir", "soru")


def simdi() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _kimlik() -> str:
    return uuid.uuid4().hex[:16]


def kur() -> None:
    c = db.connect()
    try:
        for s in SEMA:
            c.execute(s)
        c.commit()
    finally:
        c.close()


# ── oturumlar ─────────────────────────────────────────────────────
def oturum_ac(baslik: str = "Yeni oturum") -> str:
    oid = _kimlik()
    c = db.connect()
    try:
        c.execute("INSERT INTO vibe_oturum (oturum_id, baslik, olusturma, guncelleme, n_mesaj) "
                  "VALUES (?, ?, ?, ?, 0)", (oid, baslik[:120], simdi(), simdi()))
        c.commit()
    finally:
        c.close()
    return oid


def oturumlar(n: int = 40) -> list[dict]:
    c = db.connect()
    try:
        r = c.execute("SELECT oturum_id, baslik, olusturma, guncelleme, n_mesaj FROM vibe_oturum "
                      "ORDER BY guncelleme DESC").fetchall()
    finally:
        c.close()
    return [{"oturum_id": x[0], "baslik": x[1], "olusturma": x[2], "guncelleme": x[3], "n_mesaj": x[4] or 0}
            for x in r[:n]]


def baslik_yaz(oturum_id: str, baslik: str) -> None:
    c = db.connect()
    try:
        c.execute("UPDATE vibe_oturum SET baslik = ? WHERE oturum_id = ?", (baslik[:120], oturum_id))
        c.commit()
    finally:
        c.close()


def oturum_sil(oturum_id: str) -> None:
    c = db.connect()
    try:
        c.execute("DELETE FROM vibe_mesaj WHERE oturum_id = ?", (oturum_id,))
        c.execute("DELETE FROM vibe_oturum WHERE oturum_id = ?", (oturum_id,))
        c.commit()
    finally:
        c.close()


# ── mesajlar ──────────────────────────────────────────────────────
def mesajlar(oturum_id: str) -> list[dict]:
    c = db.connect()
    try:
        r = c.execute("SELECT sira, rol, metin, arac, ts FROM vibe_mesaj WHERE oturum_id = ? ORDER BY sira",
                      (oturum_id,)).fetchall()
    finally:
        c.close()
    out = []
    for x in r:
        try:
            arac = json.loads(x[3]) if x[3] else []
        except Exception:
            arac = []
        out.append({"sira": x[0], "rol": x[1], "metin": x[2] or "", "arac": arac, "ts": x[4]})
    return out


def mesaj_yaz(oturum_id: str, rol: str, metin: str, arac: list | None = None) -> int:
    c = db.connect()
    try:
        r = c.execute("SELECT COALESCE(MAX(sira), 0) FROM vibe_mesaj WHERE oturum_id = ?", (oturum_id,)).fetchone()
        sira = int(r[0] or 0) + 1
        c.execute("INSERT INTO vibe_mesaj (oturum_id, sira, rol, metin, arac, ts) VALUES (?,?,?,?,?,?)",
                  (oturum_id, sira, rol, metin, json.dumps(arac or [], ensure_ascii=False), simdi()))
        c.execute("UPDATE vibe_oturum SET guncelleme = ?, n_mesaj = ? WHERE oturum_id = ?",
                  (simdi(), sira, oturum_id))
        c.commit()
        return sira
    finally:
        c.close()


# ── geri bildirim (geliştirme kanalı) ─────────────────────────────
def geri_bildirim_yaz(oturum_id: str | None, tur: str, baslik: str, metin: str) -> str:
    gid = _kimlik()
    c = db.connect()
    try:
        c.execute("INSERT INTO vibe_geri_bildirim (gb_id, oturum_id, tur, baslik, metin, ts, durum) "
                  "VALUES (?,?,?,?,?,?,?)",
                  (gid, oturum_id, tur if tur in TURLER else "istek", baslik[:160], metin[:4000], simdi(), "acik"))
        c.commit()
    finally:
        c.close()
    return gid


def geri_bildirimler(durum: str | None = "acik", n: int = 50) -> list[dict]:
    c = db.connect()
    try:
        if durum:
            r = c.execute("SELECT gb_id, oturum_id, tur, baslik, metin, ts, durum FROM vibe_geri_bildirim "
                          "WHERE durum = ? ORDER BY ts DESC", (durum,)).fetchall()
        else:
            r = c.execute("SELECT gb_id, oturum_id, tur, baslik, metin, ts, durum FROM vibe_geri_bildirim "
                          "ORDER BY ts DESC").fetchall()
    finally:
        c.close()
    return [{"gb_id": x[0], "oturum_id": x[1], "tur": x[2], "baslik": x[3], "metin": x[4], "ts": x[5],
             "durum": x[6]} for x in r[:n]]


def geri_bildirim_kapat(gb_id: str) -> None:
    c = db.connect()
    try:
        c.execute("UPDATE vibe_geri_bildirim SET durum = 'kapali' WHERE gb_id = ?", (gb_id,))
        c.commit()
    finally:
        c.close()


# ── iş istekleri (worker yürütür) ─────────────────────────────────
def istek_yaz(oturum_id: str | None, tur: str, param: dict | None = None) -> str:
    """Aynı türde bekleyen istek varsa yenisini açmaz (kuyruk şişmesin)."""
    c = db.connect()
    try:
        var = c.execute("SELECT istek_id FROM vibe_istek WHERE tur = ? AND durum = 'bekliyor'", (tur,)).fetchone()
        if var:
            return var[0]
        iid = _kimlik()
        c.execute("INSERT INTO vibe_istek (istek_id, oturum_id, tur, param, ts, durum) VALUES (?,?,?,?,?,?)",
                  (iid, oturum_id, tur, json.dumps(param or {}, ensure_ascii=False), simdi(), "bekliyor"))
        c.commit()
        return iid
    finally:
        c.close()


def bekleyen_istekler() -> list[dict]:
    c = db.connect()
    try:
        r = c.execute("SELECT istek_id, oturum_id, tur, param, ts FROM vibe_istek WHERE durum = 'bekliyor' "
                      "ORDER BY ts").fetchall()
    finally:
        c.close()
    out = []
    for x in r:
        try:
            p = json.loads(x[3]) if x[3] else {}
        except Exception:
            p = {}
        out.append({"istek_id": x[0], "oturum_id": x[1], "tur": x[2], "param": p, "ts": x[4]})
    return out


def istek_kapat(istek_id: str, durum: str, sonuc: str = "") -> None:
    c = db.connect()
    try:
        c.execute("UPDATE vibe_istek SET durum = ?, sonuc = ?, bitis = ? WHERE istek_id = ?",
                  (durum, sonuc[:1000], simdi(), istek_id))
        c.commit()
    finally:
        c.close()


def istek_durum(n: int = 10) -> list[dict]:
    c = db.connect()
    try:
        r = c.execute("SELECT istek_id, tur, ts, durum, sonuc, bitis FROM vibe_istek ORDER BY ts DESC").fetchall()
    finally:
        c.close()
    return [{"istek_id": x[0], "tur": x[1], "ts": x[2], "durum": x[3], "sonuc": x[4], "bitis": x[5]}
            for x in r[:n]]
