"""
v2 — Understat xG → matches_v2 Join
=====================================

xg_data tablosundan matches_v2.home_xg / away_xg güncelle.

Sorun: takım isimleri farklı
    Understat: "Bayer Leverkusen", "Borussia M.Gladbach"
    Football-Data: "Leverkusen", "M'gladbach"

Çözüm: fuzzy team match (similarity ≥0.70)
       + tarihsel +/- 2 gün toleransı
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS_DIR))
sys.path.insert(0, str(THIS_DIR.parent / "03_MODELLER" / "selective"))

import database as db
from team_match import similarity


SEASON_INT_TO_CANON = {
    2021: "2021-22",
    2022: "2022-23",
    2023: "2023-24",
    2024: "2024-25",
    2025: "2025-26",
}


def fetch_xg_data():
    """xg_data tablosunu dict olarak yükle."""
    conn = db.connect()
    rows = conn.execute(
        "SELECT league_code, season, match_date, home_team, away_team, "
        "home_xg, away_xg FROM xg_data "
        "WHERE home_xg IS NOT NULL AND away_xg IS NOT NULL"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def fetch_matches_v2():
    """matches_v2'den league, season, matchday, home, away."""
    conn = db.connect()
    rows = conn.execute(
        "SELECT match_id, league_code, season, matchday, home_team, away_team "
        "FROM matches_v2"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def build_team_lookup(xg_rows):
    """xg_data'da takım isimlerini sezon × lig için topla."""
    lookup = {}
    for r in xg_rows:
        canon_season = SEASON_INT_TO_CANON.get(r["season"], None)
        if not canon_season:
            continue
        key = (r["league_code"], canon_season)
        lookup.setdefault(key, set())
        lookup[key].add(r["home_team"])
        lookup[key].add(r["away_team"])
    return lookup


def find_best_xg_team(team_v2: str, xg_team_set: set) -> str | None:
    """v2 takım ismini xg_data takım ismine eşle."""
    if team_v2 in xg_team_set:
        return team_v2
    best = None; best_sim = 0
    for xg_team in xg_team_set:
        s = similarity(team_v2, xg_team)
        if s > best_sim:
            best_sim = s; best = xg_team
    return best if best_sim >= 0.70 else None


def run():
    print("=" * 70)
    print("Sprint 1.3 — Understat xG -> matches_v2 Join")
    print("=" * 70)

    xg_rows = fetch_xg_data()
    print(f"xg_data rows: {len(xg_rows)}")
    if not xg_rows:
        print("xG verisi yok.")
        return

    # Index: (league, season, home, away) → (home_xg, away_xg)
    # Use fuzzy match through team_lookup
    team_lookup = build_team_lookup(xg_rows)
    print(f"Team lookups built for {len(team_lookup)} (lig, sezon) çifti")

    # xg lookup: tam key match için
    xg_index = {}
    for r in xg_rows:
        canon_season = SEASON_INT_TO_CANON.get(r["season"])
        if not canon_season:
            continue
        key = (r["league_code"], canon_season, r["home_team"], r["away_team"])
        xg_index[key] = (r["home_xg"], r["away_xg"], r["match_date"])

    # matches_v2 satırlarını al ve eşleştir
    m2_rows = fetch_matches_v2()
    print(f"matches_v2 rows: {len(m2_rows)}")

    conn = db.connect()
    now = datetime.utcnow().isoformat()
    n_updated = 0; n_fuzzy = 0; n_skipped = 0

    # Her m2 satırı için xg ara
    for m in m2_rows:
        lg = m["league_code"]; ss = m["season"]
        home_v2 = m["home_team"]; away_v2 = m["away_team"]

        # T1 xG yok
        if lg == "T1":
            n_skipped += 1
            continue

        team_set = team_lookup.get((lg, ss), set())
        if not team_set:
            n_skipped += 1
            continue

        # Fuzzy match
        home_xg_name = find_best_xg_team(home_v2, team_set)
        away_xg_name = find_best_xg_team(away_v2, team_set)
        if not home_xg_name or not away_xg_name:
            n_skipped += 1
            continue

        # XG lookup
        key = (lg, ss, home_xg_name, away_xg_name)
        xg_val = xg_index.get(key)
        if not xg_val:
            # Tarih bazlı bir alternatif?
            n_skipped += 1
            continue

        home_xg, away_xg, match_date = xg_val
        if home_xg_name != home_v2 or away_xg_name != away_v2:
            n_fuzzy += 1

        # UPDATE
        conn.execute("""
            UPDATE matches_v2
            SET home_xg = ?, away_xg = ?, has_xg = 1, refreshed_at = ?
            WHERE match_id = ?
        """, (home_xg, away_xg, now, m["match_id"]))
        n_updated += 1

    conn.commit()

    # Recompute quality_score
    rows = conn.execute("""
        SELECT match_id, has_full_odds, has_opening_odds, has_xg, has_result, is_settled
        FROM matches_v2
    """).fetchall()
    for r in rows:
        score = 1.0
        if not r["has_full_odds"]: score -= 0.30
        if not r["has_opening_odds"]: score -= 0.20
        if not r["has_xg"]: score -= 0.15
        if not r["has_result"]: score -= 0.25
        score = max(0.0, score)
        conn.execute("UPDATE matches_v2 SET quality_score = ? WHERE match_id = ?",
                     (score, r["match_id"]))
    conn.commit()
    conn.close()

    print(f"\nGuncellenen xG: {n_updated}")
    print(f"  Fuzzy match yapilan: {n_fuzzy}")
    print(f"  xG bulunamayan: {n_skipped}")

    # Stats
    conn = db.connect()
    try:
        for lg in ["T1", "E0", "D1", "SP1", "I1", "F1"]:
            n_total = conn.execute(
                "SELECT COUNT(*) FROM matches_v2 WHERE league_code=?", (lg,)
            ).fetchone()[0]
            n_xg = conn.execute(
                "SELECT COUNT(*) FROM matches_v2 WHERE league_code=? AND has_xg=1", (lg,)
            ).fetchone()[0]
            avg_q = conn.execute(
                "SELECT AVG(quality_score) FROM matches_v2 WHERE league_code=?", (lg,)
            ).fetchone()[0]
            xg_pct = n_xg / n_total * 100 if n_total else 0
            print(f"  {lg:4s}: {n_xg:>4}/{n_total:>4} ({xg_pct:>4.0f}%) xG, avg_quality {avg_q:.2f}")
    finally:
        conn.close()


if __name__ == "__main__":
    run()
