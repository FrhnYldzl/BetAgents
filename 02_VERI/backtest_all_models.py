"""
TÜM MODEL BACKTEST v1.0
========================
signal_snapshots (TRIVOX/EUVOX pipeline) + matches_v2 (enriched) join.

Test edilen modeller:
  M1  FAV_ONLY         → Sadece piyasa favorisi
  M2  FAV_CONFIRMED    → Favori + en az 1 sinyal teyit
  M3  SCORE_V13        → TRIVOX score_v13 top picks
  M4  SCORE_V14        → TRIVOX score_v14 (shots+referee eklendi)
  M5  AGREE_2/3        → En az 2/3 sinyal aynı yönde
  M6  M3 + H2H         → score_v13 + H2H enriched filtre
  M7  M3 + STANDINGS   → score_v13 + düşme/şampiyonluk filtresi
  M8  M4 + H2H + STAND → score_v14 + her iki enriched filtre (EN GÜÇLÜ?)

Çalıştır:
  python backtest_all_models.py
  python backtest_all_models.py --league T1
"""
from __future__ import annotations
import argparse
import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
DB = Path(__file__).resolve().parent / "bahis_agent.db"

WINNING_LEAGUES = ("SP1", "T1", "D1", "E0")

def run():
    parser = argparse.ArgumentParser()
    parser.add_argument("--league", default=None)
    args = parser.parse_args()

    conn = sqlite3.connect(str(DB))
    conn.row_factory = sqlite3.Row

    # JOIN: signal_snapshots + matches_v2 enriched kolonlar
    # Join key: league_code + kickoff date (ilk 10 karakter) + home_team lower
    league_clause = f"AND ss.league_code = '{args.league}'" if args.league else \
                    f"AND ss.league_code IN {WINNING_LEAGUES}"

    rows = conn.execute(f"""
        SELECT
            ss.league_code, ss.season, ss.kickoff_iso,
            ss.home_team, ss.away_team,
            ss.odd_1, ss.odd_X, ss.odd_2,
            ss.dir_favorite, ss.dir_consensus,
            ss.s_anomaly, ss.s_model, ss.s_xg, ss.s_form,
            ss.s_shots, ss.s_cards,
            ss.score_v13, ss.score_v14,
            ss.agree_count, ss.result_1x2,
            ss.settled,
            -- Enriched from matches_v2
            m.h2h_n, m.h2h_home_wins, m.h2h_away_wins, m.h2h_btts_rate,
            m.home_league_pos, m.away_league_pos,
            m.home_relegation_gap, m.away_relegation_gap,
            m.home_title_gap, m.away_title_gap,
            m.home_form_5g, m.away_form_5g,
            m.home_yc_5g_avg, m.away_yc_5g_avg
        FROM signal_snapshots ss
        LEFT JOIN matches_v2 m
            ON ss.league_code = m.league_code
            AND substr(ss.kickoff_iso, 1, 10) = substr(m.kickoff_utc, 1, 10)
            AND lower(replace(ss.home_team,' ','')) = lower(replace(m.home_team,' ',''))
        WHERE ss.settled = 1
          AND ss.result_1x2 IS NOT NULL
          AND ss.odd_1 IS NOT NULL
          {league_clause}
        ORDER BY ss.kickoff_iso
    """).fetchall()
    conn.close()

    total = len(rows)
    enriched = sum(1 for r in rows if r["h2h_n"] is not None)
    print(f"\nKayıt: {total:,} sinyal  (enriched join: {enriched:,}, {enriched/total*100:.0f}%)")
    if args.league:
        print(f"Lig filtresi: {args.league}")
    print()

    # ── Yardımcılar ───────────────────────────────────────────────────
    def norm(d):
        if not d: return None
        d = str(d).upper()
        if d in ("HOME","H","1"): return "HOME"
        if d in ("AWAY","A","2"): return "AWAY"
        if d in ("DRAW","D","X"): return "DRAW"
        return d

    def actual_win(row, direction):
        ftr = row["result_1x2"]
        d = norm(direction)
        return (d == "HOME" and ftr == "H") or \
               (d == "AWAY" and ftr == "A") or \
               (d == "DRAW" and ftr == "D")

    def get_odds(row, direction):
        d = norm(direction)
        if d == "HOME": return row["odd_1"]
        if d == "AWAY": return row["odd_2"]
        if d == "DRAW": return row["odd_X"]
        return None

    def h2h_ok(row, direction):
        """H2H destekliyor mu?"""
        n = row["h2h_n"] or 0
        if n < 3: return True  # Yeterli veri yok → kabul
        hw = row["h2h_home_wins"] or 0
        aw = row["h2h_away_wins"] or 0
        d = norm(direction)
        if d == "HOME": return (hw / n) >= 0.45
        if d == "AWAY": return (aw / n) >= 0.40
        return True

    def standings_ok(row):
        """Düşme hattına ≤4 pt → 1X2 tehlikeli."""
        hr = row["home_relegation_gap"]
        ar = row["away_relegation_gap"]
        if hr is not None and hr <= 4: return False
        if ar is not None and ar <= 4: return False
        return True

    # ── Model tanımları ───────────────────────────────────────────────
    def test_model(label, pick_fn, min_odds=1.15):
        """pick_fn(row) → (direction, odds) veya None"""
        picks = wins = 0
        roi = 0.0
        for r in rows:
            result = pick_fn(r)
            if result is None:
                continue
            direction, odds = result
            if not odds or odds < min_odds:
                continue
            picks += 1
            if actual_win(r, direction):
                wins += 1
                roi += odds - 1
            else:
                roi -= 1
        if picks == 0:
            return label, 0, 0, 0.0, 0.0
        return label, picks, wins, wins/picks*100, roi/picks*100

    # M1: FAV_ONLY — sadece piyasa favorisi
    def m1(r):
        fav = norm(r["dir_favorite"])
        if not fav or fav == "DRAW": return None
        odds = get_odds(r, fav)
        return (fav, odds)

    # M2: FAV_CONFIRMED — favori + en az 1 sinyal
    def m2(r):
        fav = norm(r["dir_favorite"])
        if not fav or fav == "DRAW": return None
        sigs = [norm(r["dir_consensus"])]
        if not any(s == fav for s in sigs if s): return None
        if (r["agree_count"] or 0) < 1: return None
        odds = get_odds(r, fav)
        return (fav, odds)

    # M3: score_v13 threshold
    def m3(r):
        s = r["score_v13"] or 0
        if s < 0.75: return None
        fav = norm(r["dir_favorite"])
        if not fav or fav == "DRAW": return None
        odds = get_odds(r, fav)
        return (fav, odds)

    # M4: score_v14 threshold (shots+referee sinyali dahil)
    def m4(r):
        s = r["score_v14"] or 0
        if s < 0.75: return None
        fav = norm(r["dir_favorite"])
        if not fav or fav == "DRAW": return None
        odds = get_odds(r, fav)
        return (fav, odds)

    # M5: AGREE_2/3 — en az 2 sinyal aynı yönde
    def m5(r):
        fav = norm(r["dir_favorite"])
        if not fav or fav == "DRAW": return None
        if (r["agree_count"] or 0) < 2: return None
        odds = get_odds(r, fav)
        return (fav, odds)

    # M6: score_v13 + H2H
    def m6(r):
        result = m3(r)
        if not result: return None
        direction, odds = result
        if not h2h_ok(r, direction): return None
        return result

    # M7: score_v13 + Standings
    def m7(r):
        result = m3(r)
        if not result: return None
        if not standings_ok(r): return None
        return result

    # M8: score_v14 + H2H + Standings (EN GÜÇLÜ ADAY)
    def m8(r):
        result = m4(r)
        if not result: return None
        direction, odds = result
        if not h2h_ok(r, direction): return None
        if not standings_ok(r): return None
        return result

    # M9: score_v14 + H2H + Standings + agree>=2
    def m9(r):
        result = m8(r)
        if not result: return None
        if (r["agree_count"] or 0) < 2: return None
        return result

    # ── Çalıştır ve göster ────────────────────────────────────────────
    models = [
        ("M1  FAV_ONLY",               m1),
        ("M2  FAV + 1 sinyal",          m2),
        ("M3  score_v13 ≥0.75",         m3),
        ("M4  score_v14 ≥0.75",         m4),
        ("M5  AGREE 2/3+",              m5),
        ("M6  M3 + H2H",                m6),
        ("M7  M3 + Standings",          m7),
        ("★M8 M4 + H2H + Standings",   m8),
        ("★M9 M4+H2H+Stand+Agree2",    m9),
    ]

    print(f"{'Model':<30} {'Pick':>6} {'Win':>6} {'Hit%':>6} {'ROI%':>8} {'100TL Kâr':>10}")
    print("─" * 68)

    best_roi = -999
    best_label = ""
    results = []
    for label, fn in models:
        lbl, picks, wins, hit, roi = test_model(label, fn)
        profit = roi * picks  # toplam 100TL flat kâr
        marker = " ✅" if roi > 3 else (" ⚠️" if roi > 1 else " ❌")
        results.append((lbl, picks, wins, hit, roi, profit))
        print(f"{lbl:<30} {picks:>6,} {wins:>6,} {hit:>5.1f}% {roi:>+7.1f}% {profit:>+9.0f} TL{marker}")
        if roi > best_roi and picks >= 30:
            best_roi = roi
            best_label = lbl

    print()

    # Lig bazında M8
    print("★M8 (score_v14 + H2H + Standings) — Lig Bazında:")
    print(f"{'Lig':<6} {'Pick':>5} {'Hit%':>6} {'ROI%':>7} {'Kâr':>9}")
    print("─" * 32)
    conn2 = sqlite3.connect(str(DB))
    conn2.row_factory = sqlite3.Row
    for lg in WINNING_LEAGUES:
        sub = [r for r in rows if r["league_code"] == lg]
        picks = wins = 0; roi2 = 0.0
        for r in sub:
            result = m8(r)
            if not result: continue
            direction, odds = result
            if not odds or odds < 1.15: continue
            picks += 1
            if actual_win(r, direction):
                wins += 1; roi2 += odds - 1
            else:
                roi2 -= 1
        if picks < 10: continue
        hit2 = wins/picks*100
        roi_pct2 = roi2/picks*100
        marker = " ✅" if roi_pct2 > 3 else (" ⚠️" if roi_pct2 > 0 else " ❌")
        print(f"{lg:<6} {picks:>5,} {hit2:>5.1f}% {roi_pct2:>+6.1f}% {roi2*100:>+8.0f} TL{marker}")
    conn2.close()

    print()

    # T1 sezon bazında M8
    print("★M8 — T1 Sezon Bazında:")
    print(f"{'Sezon':<10} {'Pick':>4} {'Hit%':>6} {'ROI%':>7}")
    print("─" * 28)
    t1_rows = [r for r in rows if r["league_code"] == "T1"]
    seasons = {}
    for r in t1_rows:
        ssn = r["season"]
        if ssn not in seasons: seasons[ssn] = {"p":0,"w":0,"roi":0.0}
        result = m8(r)
        if not result: continue
        direction, odds = result
        if not odds or odds < 1.15: continue
        seasons[ssn]["p"] += 1
        if actual_win(r, direction):
            seasons[ssn]["w"] += 1
            seasons[ssn]["roi"] += odds - 1
        else:
            seasons[ssn]["roi"] -= 1
    for ssn, v in sorted(seasons.items()):
        if v["p"] < 3: continue
        hit3 = v["w"]/v["p"]*100
        roi3 = v["roi"]/v["p"]*100
        marker = " ✅" if roi3 > 3 else (" ⚠️" if roi3 > 0 else " ❌")
        print(f"{ssn:<10} {v['p']:>4} {hit3:>5.1f}% {roi3:>+6.1f}%{marker}")

    print()
    baseline = results[0]
    best_result = max(results, key=lambda x: x[4] if x[1] >= 30 else -999)
    print("=" * 68)
    print(f"BASELINE (FAV_ONLY):   {baseline[3]:.1f}% hit  {baseline[4]:+.1f}% ROI  ({baseline[1]:,} pick)")
    print(f"EN İYİ MODEL:          {best_result[0]} → {best_result[3]:.1f}% hit  {best_result[4]:+.1f}% ROI  ({best_result[1]:,} pick)")
    imp = best_result[4] - baseline[4]
    red = (baseline[1] - best_result[1]) / baseline[1] * 100
    print(f"İYİLEŞME:              +{imp:.1f} puan ROI  |  Pick azalması: {red:.0f}%")
    print("=" * 68)

if __name__ == "__main__":
    run()
