"""
v2 — A4: Football-Data stats kolonlarını matches_v2'ye ekle

CSV'de zaten var:
    HS, AS       — toplam shots
    HST, AST     — shots on target
    HF, AF       — fouls
    HC, AC       — corners
    HY, AY       — yellow cards
    HR, AR       — red cards
    Referee      — hakem

Bunları matches_v2'ye UPDATE et.
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

THIS_DIR = Path(__file__).resolve().parent
RAW_DIR = THIS_DIR / "raw"
sys.path.insert(0, str(THIS_DIR))

import database as db


SEASONS_MAP = {
    "1718": "2017-18", "1819": "2018-19", "1920": "2019-20", "2021": "2020-21",
    "2122": "2021-22", "2223": "2022-23", "2324": "2023-24",
    "2425": "2024-25", "2526": "2025-26",
}


EXTEND_SCHEMA = """
-- Match statistics (Football-Data CSV)
ALTER TABLE matches_v2 ADD COLUMN home_shots_total INTEGER;
ALTER TABLE matches_v2 ADD COLUMN away_shots_total INTEGER;
ALTER TABLE matches_v2 ADD COLUMN home_shots_on INTEGER;
ALTER TABLE matches_v2 ADD COLUMN away_shots_on INTEGER;
ALTER TABLE matches_v2 ADD COLUMN home_fouls INTEGER;
ALTER TABLE matches_v2 ADD COLUMN away_fouls INTEGER;
ALTER TABLE matches_v2 ADD COLUMN home_corners INTEGER;
ALTER TABLE matches_v2 ADD COLUMN away_corners INTEGER;
ALTER TABLE matches_v2 ADD COLUMN home_yellows INTEGER;
ALTER TABLE matches_v2 ADD COLUMN away_yellows INTEGER;
ALTER TABLE matches_v2 ADD COLUMN home_reds INTEGER;
ALTER TABLE matches_v2 ADD COLUMN away_reds INTEGER;
ALTER TABLE matches_v2 ADD COLUMN referee TEXT;
ALTER TABLE matches_v2 ADD COLUMN has_match_stats INTEGER DEFAULT 0;
"""


def safe_int(v):
    try:
        if v is None or pd.isna(v): return None
        return int(v)
    except Exception:
        return None


def add_columns():
    conn = db.connect()
    try:
        for stmt in EXTEND_SCHEMA.strip().split(";"):
            stmt = stmt.strip()
            if not stmt: continue
            try:
                conn.execute(stmt)
            except Exception as e:
                if "duplicate column" not in str(e).lower():
                    print(f"  ALTER err: {e}")
        conn.commit()
        print("[OK] Sütunlar eklendi (varsa atlandı)")
    finally:
        conn.close()


def update_stats():
    """Her CSV satırı için matches_v2 row'ı bul ve stats UPDATE."""
    conn = db.connect()
    now = datetime.utcnow().isoformat()
    n_updated = 0

    for csv_file in sorted(RAW_DIR.glob("*.csv")):
        # Parse lig + sezon
        name_parts = csv_file.stem.split("_")
        if len(name_parts) != 2:
            continue
        lg, ss_code = name_parts
        season = SEASONS_MAP.get(ss_code)
        if not season:
            continue

        df = pd.read_csv(csv_file, encoding="latin-1")
        # Try 4-digit year first, fallback to 2-digit
        dc = pd.to_datetime(df["Date"], format="%d/%m/%Y", errors="coerce")
        if dc.isna().sum() > len(df) / 2:
            dc = pd.to_datetime(df["Date"], format="%d/%m/%y", errors="coerce")
        df["Date_canon"] = dc

        for _, row in df.iterrows():
            if pd.isna(row["Date_canon"]):
                continue
            matchday = row["Date_canon"].strftime("%Y-%m-%d")
            home = str(row.get("HomeTeam", "")).strip()
            away = str(row.get("AwayTeam", "")).strip()

            # Match stats
            hs = safe_int(row.get("HS"));  as_ = safe_int(row.get("AS"))
            hst = safe_int(row.get("HST")); ast = safe_int(row.get("AST"))
            hf = safe_int(row.get("HF"));  af = safe_int(row.get("AF"))
            hc = safe_int(row.get("HC"));  ac = safe_int(row.get("AC"))
            hy = safe_int(row.get("HY"));  ay = safe_int(row.get("AY"))
            hr = safe_int(row.get("HR"));  ar = safe_int(row.get("AR"))
            ref = str(row.get("Referee", "")).strip() if pd.notna(row.get("Referee")) else None

            has_stats = 1 if hs is not None else 0

            try:
                conn.execute("""
                    UPDATE matches_v2
                    SET home_shots_total=?, away_shots_total=?,
                        home_shots_on=?, away_shots_on=?,
                        home_fouls=?, away_fouls=?,
                        home_corners=?, away_corners=?,
                        home_yellows=?, away_yellows=?,
                        home_reds=?, away_reds=?,
                        referee=?, has_match_stats=?,
                        refreshed_at=?
                    WHERE league_code=? AND season=? AND matchday=?
                      AND home_team=? AND away_team=?
                """, (
                    hs, as_, hst, ast, hf, af, hc, ac, hy, ay, hr, ar,
                    ref, has_stats, now,
                    lg, season, matchday, home, away
                ))
                if conn.total_changes > 0:
                    n_updated += 1
            except Exception:
                pass

    conn.commit()
    conn.close()
    return n_updated


def stats_report():
    conn = db.connect()
    try:
        for r in conn.execute(
            "SELECT league_code, COUNT(*) as n, "
            "SUM(has_match_stats) as has_stats "
            "FROM matches_v2 GROUP BY league_code ORDER BY league_code"
        ).fetchall():
            pct = r["has_stats"] / r["n"] * 100 if r["n"] else 0
            print(f"  {r['league_code']:5s}: {r['has_stats']}/{r['n']} ({pct:.0f}%) has stats")
    finally:
        conn.close()


def run():
    print("=" * 70)
    print("A4 — Football-Data stats -> matches_v2")
    print("=" * 70)

    add_columns()
    n = update_stats()
    print(f"\n[OK] {n} satir update edildi")

    print(f"\nStats coverage:")
    stats_report()


if __name__ == "__main__":
    run()
