"""
v2 — Football-Data ->matches_v2 Ingest
========================================

Football-Data.co.uk CSV'lerinden matches_v2'ye standardize ingest.

Sezon kodu standardize:
    '2122' ->'2021-22'
    '2425' ->'2024-25'
    '2526' ->'2025-26'

6 lig × 5 sezon × ~340 maç = ~10,000 satır beklenir.

Odds:
    Opening = B365H/D/A, B365>2.5, B365<2.5
    Closing = PSCH/D/A, PC>2.5, PC<2.5 (Pinnacle)
"""
from __future__ import annotations

import hashlib
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

THIS_DIR = Path(__file__).resolve().parent
RAW_DIR = THIS_DIR / "raw"
sys.path.insert(0, str(THIS_DIR))

import database as db


LEAGUES = ["T1", "E0", "D1", "SP1", "I1", "F1"]
SEASONS_MAP = {
    "1718": "2017-18",
    "1819": "2018-19",
    "1920": "2019-20",
    "2021": "2020-21",
    "2122": "2021-22",
    "2223": "2022-23",
    "2324": "2023-24",
    "2425": "2024-25",
    "2526": "2025-26",
}


def make_row_hash(row, league, season_canon) -> str:
    """Football-Data row için unique hash."""
    key = f"{league}|{season_canon}|{row.get('Date')}|{row.get('HomeTeam')}|{row.get('AwayTeam')}"
    return hashlib.md5(key.encode()).hexdigest()[:16]


def parse_date(d) -> str:
    """'DD/MM/YYYY' veya 'DD/MM/YY' ->'YYYY-MM-DD'."""
    if d is None or pd.isna(d):
        return None
    s = str(d).strip()
    for fmt in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            return pd.to_datetime(s, format=fmt).strftime("%Y-%m-%d")
        except Exception:
            continue
    try:
        return pd.to_datetime(s, dayfirst=True).strftime("%Y-%m-%d")
    except Exception:
        return None


def safe_float(v):
    try:
        if v is None or pd.isna(v): return None
        return float(v)
    except Exception:
        return None


def safe_int(v):
    try:
        if v is None or pd.isna(v): return None
        return int(v)
    except Exception:
        return None


def quality_score(row_data: dict) -> float:
    score = 1.0
    if not row_data.get("has_full_odds"): score -= 0.30
    if not row_data.get("has_opening_odds"): score -= 0.20
    if not row_data.get("has_xg"): score -= 0.15
    if not row_data.get("has_result"): score -= 0.25
    return max(0.0, score)


def ingest_csv(league: str, season_code: str) -> int:
    """Bir CSV'yi matches_v2'ye ingest et."""
    csv_path = RAW_DIR / f"{league}_{season_code}.csv"
    if not csv_path.exists():
        return 0
    df = pd.read_csv(csv_path, encoding="latin-1")
    season_canon = SEASONS_MAP.get(season_code, season_code)

    conn = db.connect()
    now = datetime.utcnow().isoformat()
    n_inserted = 0

    try:
        for _, row in df.iterrows():
            try:
                matchday = parse_date(row.get("Date"))
                if not matchday:
                    continue
                home = str(row.get("HomeTeam", "")).strip()
                away = str(row.get("AwayTeam", "")).strip()
                if not home or not away:
                    continue

                # FTR (result)
                ftr = str(row.get("FTR", "")).strip()
                has_result = ftr in ("H", "D", "A")
                home_score = safe_int(row.get("FTHG"))
                away_score = safe_int(row.get("FTAG"))

                # Closing odds (Pinnacle)
                closing_1 = safe_float(row.get("PSCH"))
                closing_X = safe_float(row.get("PSCD"))
                closing_2 = safe_float(row.get("PSCA"))
                closing_over = safe_float(row.get("PC>2.5"))
                closing_under = safe_float(row.get("PC<2.5"))
                has_full_odds = 1 if (closing_1 and closing_X and closing_2) else 0

                # Opening odds (B365)
                opening_1 = safe_float(row.get("B365H"))
                opening_X = safe_float(row.get("B365D"))
                opening_2 = safe_float(row.get("B365A"))
                opening_over = safe_float(row.get("B365>2.5"))
                opening_under = safe_float(row.get("B365<2.5"))
                has_opening_odds = 1 if (opening_1 and opening_X and opening_2) else 0

                ext_id = make_row_hash(row, league, season_canon)

                # Quality
                qsc_input = {
                    "has_full_odds": has_full_odds,
                    "has_opening_odds": has_opening_odds,
                    "has_xg": 0,  # Sprint 1.3'te update edilecek
                    "has_result": 1 if has_result else 0,
                }
                qsc = quality_score(qsc_input)

                # INSERT OR REPLACE
                conn.execute("""
                    INSERT OR REPLACE INTO matches_v2 (
                        external_id_fd, league_code, season, matchday,
                        kickoff_utc, home_team, away_team,
                        status, home_score, away_score,
                        opening_1, opening_X, opening_2,
                        opening_over25, opening_under25, opening_source, opening_fetched_at,
                        closing_1, closing_X, closing_2,
                        closing_over25, closing_under25, closing_source, closing_fetched_at,
                        has_full_odds, has_opening_odds, has_xg, has_result, is_settled,
                        quality_score, ingested_at, refreshed_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                              ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                              ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    ext_id, league, season_canon, matchday,
                    matchday, home, away,
                    "FT" if has_result else "NS", home_score, away_score,
                    opening_1, opening_X, opening_2,
                    opening_over, opening_under, "B365", now,
                    closing_1, closing_X, closing_2,
                    closing_over, closing_under, "Pinnacle", now,
                    has_full_odds, has_opening_odds, 0, 1 if has_result else 0,
                    1 if has_result else 0,
                    qsc, now, now
                ))
                n_inserted += 1
            except Exception as e:
                pass
        conn.commit()
    finally:
        conn.close()
    return n_inserted


def update_seasons_meta():
    """seasons_meta tablosunu güncel matches_v2 kapsamından çıkar."""
    conn = db.connect()
    now = datetime.utcnow().isoformat()
    try:
        rows = conn.execute("""
            SELECT league_code, season, COUNT(*) as n,
                   SUM(is_settled) as settled,
                   MIN(matchday) as start_d, MAX(matchday) as end_d
            FROM matches_v2
            GROUP BY league_code, season
        """).fetchall()
        for r in rows:
            cov = (r["settled"] / r["n"] * 100) if r["n"] else 0
            conn.execute("""
                INSERT OR REPLACE INTO seasons_meta(
                    league_code, season, start_date, end_date,
                    n_total_matches, n_settled, coverage_pct, last_refresh
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (r["league_code"], r["season"], r["start_d"], r["end_d"],
                  r["n"], r["settled"], cov, now))
        conn.commit()
    finally:
        conn.close()


def run():
    print("=" * 70)
    print("Sprint 1.2 — Football-Data ->matches_v2 Ingest")
    print("=" * 70)

    total = 0
    for lg in LEAGUES:
        for ss_code in SEASONS_MAP.keys():
            n = ingest_csv(lg, ss_code)
            if n > 0:
                print(f"  [{lg}/{ss_code}->{SEASONS_MAP[ss_code]}] {n:>4} satir")
                total += n

    print(f"\nToplam ingest: {total} satir")

    update_seasons_meta()
    print("\nseasons_meta güncellendi.")

    # Stats
    conn = db.connect()
    try:
        n_m2 = conn.execute("SELECT COUNT(*) FROM matches_v2").fetchone()[0]
        n_settled = conn.execute("SELECT COUNT(*) FROM matches_v2 WHERE is_settled=1").fetchone()[0]
        avg_q = conn.execute("SELECT AVG(quality_score) FROM matches_v2").fetchone()[0]
        print(f"\nmatches_v2: {n_m2} satir, {n_settled} settled, avg_quality {avg_q:.2f}")
    finally:
        conn.close()


if __name__ == "__main__":
    run()
