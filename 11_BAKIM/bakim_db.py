"""
HAFTALIK BAKIM · KAYIT — yalnız `bk_*` tabloları
=================================================
Her çalıştırmanın sonucu saklanır; böylece "geçen hafta 19 sahipsiz bahis
vardı, bu hafta 23" gibi EĞİLİM görünür. BetAgents tablolarına yazılmaz.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_V = Path(__file__).resolve().parent.parent / "02_VERI"
if str(_V) not in sys.path:
    sys.path.insert(0, str(_V))

import db  # noqa: E402

SEMA = ["""CREATE TABLE IF NOT EXISTS bk_kosu (ts TEXT PRIMARY KEY, ozet TEXT)"""]


def kur() -> None:
    c = db.connect()
    try:
        for s in SEMA:
            c.execute(s)
        c.commit()
    finally:
        c.close()


def kaydet(R: dict) -> None:
    c = db.connect()
    try:
        c.execute("INSERT INTO bk_kosu (ts, ozet) VALUES (?, ?) ON CONFLICT (ts) DO NOTHING",
                  (R["ts"], json.dumps(R, ensure_ascii=False, default=str)))
        c.commit()
    finally:
        c.close()


def son(n: int = 12) -> list[dict]:
    """En yeniden eskiye çalıştırma sonuçları."""
    c = db.connect()
    try:
        r = c.execute("SELECT ts, ozet FROM bk_kosu ORDER BY ts DESC").fetchall()
    except Exception:
        return []
    finally:
        c.close()
    out = []
    for ts, oz in r[:n]:
        try:
            out.append(json.loads(oz))
        except Exception:
            pass
    return out
