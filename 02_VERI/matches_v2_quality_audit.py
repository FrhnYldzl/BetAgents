"""
v2 — matches_v2 Quality Audit
==============================

Sprint 1 Gate Kriter: quality_score >=0.7 olan satır oranı >=%85

Detaylı audit:
    - Per lig × sezon coverage
    - Quality distribution
    - Eksik veri raporu
    - Sprint 1 PASS/FAIL kararı
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS_DIR))

import database as db


def run():
    print("=" * 80)
    print("Sprint 1 GATE — matches_v2 Quality Audit")
    print("=" * 80)

    conn = db.connect()

    # OVERALL
    n_total = conn.execute("SELECT COUNT(*) FROM matches_v2").fetchone()[0]
    n_q70 = conn.execute("SELECT COUNT(*) FROM matches_v2 WHERE quality_score >= 0.7").fetchone()[0]
    n_q85 = conn.execute("SELECT COUNT(*) FROM matches_v2 WHERE quality_score >= 0.85").fetchone()[0]
    avg_q = conn.execute("SELECT AVG(quality_score) FROM matches_v2").fetchone()[0]

    print(f"\nTOPLAM: {n_total} satir")
    print(f"  quality >= 0.70: {n_q70} ({n_q70/n_total*100:.1f}%)")
    print(f"  quality >= 0.85: {n_q85} ({n_q85/n_total*100:.1f}%)")
    print(f"  Avg quality:     {avg_q:.3f}")

    # PER LIG x SEZON
    print(f"\n=== Per Lig × Sezon ===")
    print(f"{'lig':5s} {'sezon':>8s} {'n':>4s} {'odds%':>6s} {'open%':>6s} {'xG%':>5s} {'set%':>5s} {'avgQ':>5s}")
    print("-" * 60)
    rows = conn.execute("""
        SELECTOR league_code, season, COUNT(*) as n,
               SUM(has_full_odds) as has_odds,
               SUM(has_opening_odds) as has_open,
               SUM(has_xg) as has_xg_n,
               SUM(is_settled) as settled,
               AVG(quality_score) as avg_q
        FROM matches_v2
        GROUP BY league_code, season
        ORDER BY league_code, season
    """.replace("SELECTOR", "SELECT")).fetchall()
    for r in rows:
        odds_pct = r["has_odds"]/r["n"]*100
        open_pct = r["has_open"]/r["n"]*100
        xg_pct = r["has_xg_n"]/r["n"]*100
        set_pct = r["settled"]/r["n"]*100
        print(f"  {r['league_code']:4s} {r['season']:>8s} {r['n']:>4d} "
              f"{odds_pct:>5.0f}% {open_pct:>5.0f}% {xg_pct:>4.0f}% "
              f"{set_pct:>4.0f}% {r['avg_q']:>5.2f}")

    # PER LIG ÖZET
    print(f"\n=== Per Lig Özet ===")
    print(f"{'lig':5s} {'n_total':>7s} {'q>=0.7':>7s} {'q>=0.85':>8s} {'avg_q':>6s}")
    print("-" * 45)
    rows = conn.execute("""
        SELECT league_code, COUNT(*) as n,
               SUM(CASE WHEN quality_score >= 0.7 THEN 1 ELSE 0 END) as q70,
               SUM(CASE WHEN quality_score >= 0.85 THEN 1 ELSE 0 END) as q85,
               AVG(quality_score) as avg_q
        FROM matches_v2
        GROUP BY league_code
        ORDER BY league_code
    """).fetchall()
    for r in rows:
        print(f"  {r['league_code']:4s} {r['n']:>7d} "
              f"{r['q70']/r['n']*100:>6.0f}% "
              f"{r['q85']/r['n']*100:>7.0f}% "
              f"{r['avg_q']:>6.2f}")

    # GATE KARARI
    print(f"\n" + "=" * 80)
    print(f"SPRINT 1 GATE KRİTERİ: quality_score >=0.7 olan satır oranı >=%85")
    print("=" * 80)
    gate_pct = n_q70 / n_total * 100
    if gate_pct >= 85:
        print(f"  [OK] PASS — {gate_pct:.1f}% (hedef %85)")
        print(f"  Sprint 1 BAŞARILI. Sprint 2 (CLV) için hazır.")
    else:
        print(f"  [X] FAIL — {gate_pct:.1f}% (hedef %85)")
        print(f"  Eksik veri kaynaklarını gözden geçir.")

    conn.close()


if __name__ == "__main__":
    run()
