"""
Arayüz önizlemesi için üretimin SALT OKUMA anlık görüntüsü (geliştirici aracı).

Üretimden tek bağlantıyla okur, 02_VERI/ui_onizleme.db'ye (SQLite, git
dışında — **/*.db) yazar. Üretime hiçbir şey yazmaz. Önizlemeyi başlatmak:
python 08_AI_TRADER/onizleme.py

    python ui_onizleme_al.py
"""
from __future__ import annotations

import datetime as dt
import decimal
import sqlite3
import sys
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS_DIR))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import db

HEDEF = THIS_DIR / "ui_onizleme.db"


def _cevir(v):
    if isinstance(v, decimal.Decimal):
        return float(v)
    if isinstance(v, (dt.datetime, dt.date)):
        return v.isoformat()
    return v


def al() -> None:
    simdi = dt.datetime.utcnow()
    once = lambda gun: (simdi - dt.timedelta(days=gun)).isoformat()  # noqa: E731
    plan = [
        ("paper_portfolio", "SELECT * FROM paper_portfolio", ()),
        ("paper_coupons", "SELECT * FROM paper_coupons", ()),
        ("paper_bets", "SELECT * FROM paper_bets", ()),
        ("matches_v2", "SELECT * FROM matches_v2 WHERE kickoff_utc >= ?", (once(80),)),
        ("agent_diag", "SELECT * FROM agent_diag WHERE ts >= ?", (once(14),)),
        ("agent_runs", "SELECT * FROM agent_runs WHERE ts >= ?", (once(10),)),
        ("measurement_runs", "SELECT * FROM measurement_runs", ()),
        ("exec_reports", "SELECT * FROM exec_reports", ()),
        ("paper_journal", "SELECT * FROM paper_journal WHERE created_at >= ?", (once(20),)),
        ("agent_license", "SELECT * FROM agent_license", ()),
    ]
    src = db.connect()
    dst = sqlite3.connect(HEDEF)
    try:
        for tablo, q, p in plan:
            try:
                rows = [dict(r) for r in src.execute(q, p).fetchall()]
            except Exception as e:
                src.rollback()
                print(f"  {tablo}: atlandı ({type(e).__name__})")
                continue
            if not rows:
                print(f"  {tablo}: boş")
                continue
            cols = list(rows[0].keys())
            dst.execute(f'DROP TABLE IF EXISTS "{tablo}"')
            dst.execute(f'CREATE TABLE "{tablo}" (' +
                        ", ".join(f'"{c}"' for c in cols) + ")")
            dst.executemany(
                f'INSERT INTO "{tablo}" VALUES (' + ",".join("?" * len(cols)) + ")",
                [tuple(_cevir(r.get(c)) for c in cols) for r in rows])
            dst.commit()
            print(f"  {tablo}: {len(rows)} satır")
    finally:
        src.close()
        dst.close()
    print(f"✅ {HEDEF.name} · {HEDEF.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    al()
