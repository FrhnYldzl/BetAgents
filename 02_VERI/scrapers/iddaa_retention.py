"""
SELECTIVE EDGE v1.1 — iddaa_odds Retention Policy

Saatlik scrape edilirse iddaa_odds tablosu sınırsız büyür.
Bu modül eski snapshotları siler, sadece şu kuralları uygular:

    - En son 24 saatlik snapshotlar: HEPSİ KALSIN (line movement icin lazim)
    - 24 saatten eski: günlük 1 snapshot (T-30dk yakın olan)
    - 30 günden eski: sil (artik datalik degil)

Kullanım:
    python iddaa_retention.py prune          → kuralları uygula
    python iddaa_retention.py stats          → tablo boyut özeti
"""
from __future__ import annotations

import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS_DIR.parent))
import database as db


def stats():
    conn = db.connect()
    try:
        n = conn.execute("SELECT COUNT(*) FROM iddaa_odds").fetchone()[0]
        snaps = conn.execute(
            "SELECT snapshot_id, COUNT(*) as n, COUNT(DISTINCT iddaa_match_id) as m "
            "FROM iddaa_odds GROUP BY snapshot_id ORDER BY snapshot_id"
        ).fetchall()
        print("=== IDDAA_ODDS RETENTION STATS ===")
        print(f"Toplam satir: {n:,}")
        print(f"Snapshot sayisi: {len(snaps)}")
        for s in snaps:
            print(f"  {s['snapshot_id']}  satir={s['n']:>6,}  mac={s['m']:>3}")
    finally:
        conn.close()


def prune():
    """
    Retention kurallarini uygula.
    snapshot_id format: 'YYYY-MM-DD-HHMM'
    """
    conn = db.connect()
    try:
        now = datetime.utcnow()
        cutoff_24h = (now - timedelta(hours=24)).strftime("%Y-%m-%d-%H%M")
        cutoff_30d = (now - timedelta(days=30)).strftime("%Y-%m-%d-%H%M")

        # 1. >30 gun: sil
        deleted_30d = conn.execute(
            "DELETE FROM iddaa_odds WHERE snapshot_id < ?",
            (cutoff_30d,)
        ).rowcount

        # 2. 24h-30d arasi: gunde 1 snapshot tut (gun basina en eski)
        snaps = conn.execute(
            "SELECT DISTINCT snapshot_id FROM iddaa_odds "
            "WHERE snapshot_id < ? ORDER BY snapshot_id",
            (cutoff_24h,)
        ).fetchall()
        # Group by date
        by_date = {}
        for r in snaps:
            d = r[0][:10]
            by_date.setdefault(d, []).append(r[0])
        to_delete = []
        for d, snap_list in by_date.items():
            if len(snap_list) > 1:
                # Hepsi haric sonuncusu sil
                to_delete.extend(snap_list[:-1])
        deleted_intermediate = 0
        for snap in to_delete:
            n = conn.execute(
                "DELETE FROM iddaa_odds WHERE snapshot_id = ?", (snap,)
            ).rowcount
            deleted_intermediate += n

        # 3. Anomaly tablosu da temizle
        deleted_anom = conn.execute("""
            DELETE FROM odds_anomaly_signals
            WHERE snapshot_id NOT IN (SELECT DISTINCT snapshot_id FROM iddaa_odds)
        """).rowcount

        conn.commit()
        print(f"[OK] Retention uygulandi:")
        print(f"     >30g silindi      : {deleted_30d:,} satir")
        print(f"     gunluk indirgendi : {deleted_intermediate:,} satir")
        print(f"     orphan anomaly    : {deleted_anom:,} satir")
    finally:
        conn.close()


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "stats"
    if cmd == "stats":
        stats()
    elif cmd == "prune":
        stats()
        print()
        prune()
        print()
        stats()
    else:
        print("Komutlar: stats | prune")
