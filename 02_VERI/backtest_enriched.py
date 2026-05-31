"""
ENRICHED BACKTEST v1.0
======================
historical_enricher tamalandiktan sonra caliştirilir.
Yeni ozelliklerle (H2H, standings, form, YC/korner) model performansini test eder.

Karsilastirma:
  BASELINE  → Edge65 (sadece piyasa implied prob)
  +xG       → Edge65 + xG baskı onayı
  +H2H      → Edge65 + H2H ev galibiyeti gecmisi
  +STANDINGS→ Edge65 + motivasyon (düşme/şampiyonluk baskısı)
  +FORM     → Edge65 + form 5G trendu
  +ALL      → Tüm katmanlar birlikte

Calıştır:
  python backtest_enriched.py
  python backtest_enriched.py --league T1
"""
from __future__ import annotations
import argparse
import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

DB_PATH = Path(__file__).resolve().parent / "bahis_agent.db"


def calc_true_prob(odds_list):
    raw = [1.0 / o for o in odds_list if o and o > 0]
    total = sum(raw)
    if total <= 0:
        return [0.0] * len(odds_list)
    return [r / total for r in raw]


def form_score(form_str: str | None) -> float:
    """WWDLL → 0.0-1.0 arası skor. W=1, D=0.5, L=0."""
    if not form_str:
        return 0.5
    scores = {"W": 1.0, "D": 0.5, "L": 0.0}
    vals = [scores.get(c, 0.5) for c in (form_str or "")[:5]]
    return sum(vals) / len(vals) if vals else 0.5


def run_backtest(league_filter: str | None = None):
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    query = """
        SELECT closing_1, closing_X, closing_2,
               closing_over25, closing_under25,
               closing_btts_yes, closing_btts_no,
               home_score, away_score,
               home_xg, away_xg,
               -- Enriched columns
               h2h_n, h2h_home_wins, h2h_away_wins, h2h_draws, h2h_btts_rate,
               home_league_pos, away_league_pos,
               home_relegation_gap, away_relegation_gap,
               home_title_gap, away_title_gap,
               home_form_5g, away_form_5g,
               home_avg_goals_5g, away_avg_goals_5g,
               home_yc_5g_avg, away_yc_5g_avg,
               home_corners_5g_avg, away_corners_5g_avg,
               league_code, season
        FROM matches_v2
        WHERE is_settled=1
          AND closing_1 IS NOT NULL
          AND home_score IS NOT NULL
    """
    params = []
    if league_filter:
        query += " AND league_code=?"
        params.append(league_filter)

    rows = conn.execute(query, params).fetchall()
    conn.close()

    # Kaç maçın enriched verisi var?
    enriched = sum(1 for r in rows if r["h2h_n"] is not None)
    print(f"\nAnaliz edilen maç: {len(rows):,}  (enriched: {enriched:,}, {enriched/len(rows)*100:.0f}%)")
    if league_filter:
        print(f"Lig filtresi: {league_filter}")
    print()

    # ── Strateji tanımları ────────────────────────────────────────────
    # Her strateji: (label, filter_fn, pick_fn)
    # filter_fn(row, mp, odds, side) → bool (bu pick'i al mı?)
    # Tüm stratejiler Edge65 temelini paylaşır (mp>=0.65, odds>=1.20)

    def base_filter(row, mp, odds, side):
        """Edge65 baseline."""
        return mp >= 0.65 and odds >= 1.20

    def xg_filter(row, mp, odds, side):
        """Edge65 + xG onayı."""
        if not base_filter(row, mp, odds, side):
            return False
        hxg = row["home_xg"] or 0
        axg = row["away_xg"] or 0
        total = hxg + axg
        if total <= 0:
            return True  # xG yoksa kabul et (veri eksikliği)
        share = hxg / total
        if side == "1":
            return share >= 0.55
        elif side == "2":
            return share <= 0.45
        return True

    def h2h_filter(row, mp, odds, side):
        """Edge65 + H2H gecmisi destekliyor."""
        if not base_filter(row, mp, odds, side):
            return False
        n = row["h2h_n"] or 0
        if n < 3:
            return True  # Yeterli H2H yok → kabul et
        hw = row["h2h_home_wins"] or 0
        aw = row["h2h_away_wins"] or 0
        if side == "1":
            return (hw / n) >= 0.50  # Ev tarihsel üstünlüğü
        elif side == "2":
            return (aw / n) >= 0.45
        return True

    def standings_filter(row, mp, odds, side):
        """Edge65 + Motivasyon (düşme/şampiyonluk baskısı altındaki maçları elek)."""
        if not base_filter(row, mp, odds, side):
            return False
        # Düşme hattı çok yakınsa (≤4 pt) → belirsizlik yüksek → filtrele
        h_rel = row["home_relegation_gap"]
        a_rel = row["away_relegation_gap"]
        if h_rel is not None and h_rel <= 4:
            return False  # Ev sahibi hayatta kalma modu
        if a_rel is not None and a_rel <= 4:
            return False  # Deplasman hayatta kalma modu
        return True

    def form_filter(row, mp, odds, side):
        """Edge65 + son 5 maç formu destekliyor."""
        if not base_filter(row, mp, odds, side):
            return False
        hf = form_score(row["home_form_5g"])
        af = form_score(row["away_form_5g"])
        if side == "1":
            return hf >= 0.55 and hf > af  # Ev iyi formda VE dep'tan iyi
        elif side == "2":
            return af >= 0.55 and af > hf
        return True

    def yc_corner_filter(row, mp, odds, side):
        """Edge65 + YC/korner geçmişi (agresif / defensif oyun tarzı)."""
        if not base_filter(row, mp, odds, side):
            return False
        # Çok sarı kart olan takımlar → disiplin riski → 1X2 de geç
        h_yc = row["home_yc_5g_avg"] or 0
        a_yc = row["away_yc_5g_avg"] or 0
        if h_yc > 3.5 or a_yc > 3.5:
            return False  # Sarı kart yoğun maç → tehlikeli
        return True

    def all_filter(row, mp, odds, side):
        """Tüm katmanlar birlikte."""
        return (
            xg_filter(row, mp, odds, side) and
            h2h_filter(row, mp, odds, side) and
            standings_filter(row, mp, odds, side) and
            form_filter(row, mp, odds, side)
        )

    strategies = [
        ("BASELINE (Edge65)",      base_filter),
        ("+xG onayı",              xg_filter),
        ("+H2H filtresi",          h2h_filter),
        ("+Standings filtresi",    standings_filter),
        ("+Form 5G filtresi",      form_filter),
        ("+YC/Korner filtresi",    yc_corner_filter),
        ("★ TÜM KATMANLAR",        all_filter),
    ]

    print(f"{'Strateji':<26} {'Pick':>6} {'Win':>6} {'Hit%':>6} {'ROI%':>8} {'100TL Kâr':>10}")
    print("─" * 68)

    results = []
    for label, filt in strategies:
        picks = wins = 0
        roi = 0.0

        for r in rows:
            o1 = r["closing_1"]
            oX = r["closing_X"]
            o2 = r["closing_2"]
            hs = r["home_score"]
            as_ = r["away_score"]
            if not all([o1, oX, o2, hs is not None, as_ is not None]):
                continue

            tp = calc_true_prob([o1, oX, o2])
            mp1, mpX, mp2 = tp
            result = "1" if hs > as_ else ("X" if hs == as_ else "2")

            for side, mp, odds in [("1", mp1, o1), ("2", mp2, o2)]:
                if filt(r, mp, odds, side):
                    picks += 1
                    if side == result:
                        wins += 1
                        roi += odds - 1
                    else:
                        roi -= 1

        if picks == 0:
            print(f"{label:<26} {'—':>6} {'—':>6} {'—':>6} {'—':>8} {'—':>10}")
            continue

        hit = wins / picks * 100
        roi_pct = roi / picks * 100
        profit_100 = roi * 100

        results.append((label, picks, wins, hit, roi_pct, profit_100))
        marker = " ✅" if roi_pct > 2 else (" ⚠️" if roi_pct > 0 else " ❌")
        print(f"{label:<26} {picks:>6,} {wins:>6,} {hit:>5.1f}% {roi_pct:>+7.1f}% {profit_100:>+9.0f} TL{marker}")

    print()

    # ── Lig bazında TÜM KATMANLAR performansı ──────────────────────────
    print("★ TÜM KATMANLAR — Lig Bazında:")
    print(f"{'Lig':<8} {'Pick':>5} {'Hit%':>6} {'ROI%':>7} {'100TL Kâr':>10}")
    print("─" * 36)

    lig_stats: dict[str, dict] = {}
    for r in rows:
        lg = r["league_code"]
        if lg not in lig_stats:
            lig_stats[lg] = {"p": 0, "w": 0, "roi": 0.0}

        o1 = r["closing_1"]; oX = r["closing_X"]; o2 = r["closing_2"]
        hs = r["home_score"]; as_ = r["away_score"]
        if not all([o1, oX, o2, hs is not None, as_ is not None]):
            continue

        tp = calc_true_prob([o1, oX, o2])
        mp1, mpX, mp2 = tp
        result = "1" if hs > as_ else ("X" if hs == as_ else "2")

        for side, mp, odds in [("1", mp1, o1), ("2", mp2, o2)]:
            if all_filter(r, mp, odds, side):
                lig_stats[lg]["p"] += 1
                if side == result:
                    lig_stats[lg]["w"] += 1
                    lig_stats[lg]["roi"] += odds - 1
                else:
                    lig_stats[lg]["roi"] -= 1

    for lg, v in sorted(lig_stats.items()):
        p = v["p"]
        if p < 20:
            continue
        hit = v["w"] / p * 100
        roi_pct = v["roi"] / p * 100
        profit = v["roi"] * 100
        marker = " ✅" if roi_pct > 2 else (" ⚠️" if roi_pct > 0 else " ❌")
        print(f"{lg:<8} {p:>5,} {hit:>5.1f}% {roi_pct:>+6.1f}% {profit:>+9.0f} TL{marker}")

    print()

    # ── Sezon bazında TÜM KATMANLAR (T1) ───────────────────────────────
    if not league_filter:
        print("★ TÜM KATMANLAR — T1 Sezon Bazında:")
        print(f"{'Sezon':<12} {'Pick':>4} {'Hit%':>6} {'ROI%':>7} {'100TL Kâr':>10}")
        print("─" * 40)

        season_stats: dict[str, dict] = {}
        for r in rows:
            if r["league_code"] != "T1":
                continue
            ssn = r["season"]
            if ssn not in season_stats:
                season_stats[ssn] = {"p": 0, "w": 0, "roi": 0.0}

            o1 = r["closing_1"]; oX = r["closing_X"]; o2 = r["closing_2"]
            hs = r["home_score"]; as_ = r["away_score"]
            if not all([o1, oX, o2, hs is not None, as_ is not None]):
                continue

            tp = calc_true_prob([o1, oX, o2])
            mp1, mpX, mp2 = tp
            result = "1" if hs > as_ else ("X" if hs == as_ else "2")

            for side, mp, odds in [("1", mp1, o1), ("2", mp2, o2)]:
                if all_filter(r, mp, odds, side):
                    season_stats[ssn]["p"] += 1
                    if side == result:
                        season_stats[ssn]["w"] += 1
                        season_stats[ssn]["roi"] += odds - 1
                    else:
                        season_stats[ssn]["roi"] -= 1

        for ssn, v in sorted(season_stats.items()):
            p = v["p"]
            if p < 5:
                continue
            hit = v["w"] / p * 100
            roi_pct = v["roi"] / p * 100
            profit = v["roi"] * 100
            marker = " ✅" if roi_pct > 2 else (" ⚠️" if roi_pct > 0 else " ❌")
            print(f"{ssn:<12} {p:>4} {hit:>5.1f}% {roi_pct:>+6.1f}% {profit:>+9.0f} TL{marker}")

    print()
    print("=" * 68)
    if results:
        best = max(results, key=lambda x: x[4])
        baseline = results[0]
        print(f"BASELINE ROI:    {baseline[4]:+.1f}%  ({baseline[1]:,} pick)")
        print(f"EN İYİ STRATEJİ: {best[0]} → ROI {best[4]:+.1f}%  ({best[1]:,} pick)")
        improvement = best[4] - baseline[4]
        pick_reduction = (baseline[1] - best[1]) / baseline[1] * 100
        print(f"İYİLEŞME:        +{improvement:.1f} puan ROI  |  Pick azalması: {pick_reduction:.0f}%")
    print("=" * 68)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--league", type=str, default=None)
    args = parser.parse_args()
    run_backtest(args.league)
