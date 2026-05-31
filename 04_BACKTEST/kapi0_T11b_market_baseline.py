"""
KAPI 0 — TEST 11b: Market Baseline (1X2, A/U 2.5, KG)
========================================================

signal_snapshots'ta multi-market model prob yok (eski schema).
Pragmatik plan:
  matches_v2'den 3 pazarda PIYASA KALIBRASYON + FAVORI HIT testi.
  Bu, "DC Poisson'dan türettiğimiz modeller bu pazarlar için DAYANAK alan
  bulabilir mi?" sorusuna kaba bir cevap verir.

Test edilen pazarlar:
  1. Maç Sonucu (closing_1, closing_X, closing_2)
  2. Alt/Üst 2.5 (closing_over25, closing_under25)
  3. (KG yok matches_v2'de — Football-Data BTS kolonu var, ingest etmemişiz)

Her pazar için:
  - Pazar marjı (overround)
  - Favori-taraf hit rate
  - Hit rate vs implied prob (kalibre mi?)
"""
from __future__ import annotations

import sys
import sqlite3
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

THIS_DIR = Path(__file__).resolve().parent
YAZILIM = THIS_DIR.parent
sys.path.insert(0, str(YAZILIM / "02_VERI"))


def load_data() -> pd.DataFrame:
    db_path = YAZILIM / "02_VERI" / "bahis_agent.db"
    conn = sqlite3.connect(db_path)
    df = pd.read_sql_query(
        """SELECT league_code, season, matchday, home_team, away_team,
               closing_1, closing_X, closing_2,
               closing_over25, closing_under25,
               home_score, away_score,
               is_settled
           FROM matches_v2
           WHERE is_settled=1
             AND closing_1 IS NOT NULL
             AND home_score IS NOT NULL""", conn
    )
    conn.close()
    df["over25_actual"] = ((df["home_score"] + df["away_score"]) > 2).astype(int)
    df["btts_actual"] = ((df["home_score"] > 0) & (df["away_score"] > 0)).astype(int)
    # 1X2 result
    df["result"] = "D"
    df.loc[df["home_score"] > df["away_score"], "result"] = "H"
    df.loc[df["away_score"] > df["home_score"], "result"] = "A"
    return df


def market_1x2_baseline(df: pd.DataFrame, leagues: list = None) -> dict:
    if leagues:
        df = df[df["league_code"].isin(leagues)]
    if df.empty: return {}
    # Overround
    df = df.copy()
    df["imp_1"] = 1/df["closing_1"]
    df["imp_X"] = 1/df["closing_X"]
    df["imp_2"] = 1/df["closing_2"]
    df["overround"] = df["imp_1"] + df["imp_X"] + df["imp_2"]
    overround_pct = (df["overround"].mean() - 1) * 100

    # Favori-taraf hit rate (en düşük closing = en güçlü favori)
    def fav_dir(r):
        odds = {"H": r["closing_1"], "X": r["closing_X"], "A": r["closing_2"]}
        return min(odds, key=odds.get)
    df["fav_dir"] = df.apply(fav_dir, axis=1)
    df["fav_odd"] = df.apply(lambda r: r[f"closing_{ {'H':1,'X':'X','A':2}[r['fav_dir']]}"
                                          if r['fav_dir'] in ('H','A')
                                          else "closing_X"], axis=1)
    df["fav_odd"] = df.apply(lambda r:
        r["closing_1"] if r["fav_dir"]=="H" else
        (r["closing_2"] if r["fav_dir"]=="A" else r["closing_X"]), axis=1)
    df["fav_won"] = df["fav_dir"] == df["result"]
    fav_hit = df["fav_won"].mean()
    fav_avg_odd = df["fav_odd"].mean()
    fav_breakeven = 1 / fav_avg_odd
    fav_edge_pp = (fav_hit - fav_breakeven) * 100
    return {
        "n": len(df),
        "overround_pct": float(overround_pct),
        "fav_hit": float(fav_hit),
        "fav_avg_odd": float(fav_avg_odd),
        "fav_breakeven": float(fav_breakeven),
        "fav_edge_pp": float(fav_edge_pp),
    }


def market_ou_baseline(df: pd.DataFrame, leagues: list = None) -> dict:
    if leagues:
        df = df[df["league_code"].isin(leagues)]
    df = df[df["closing_over25"].notna() & df["closing_under25"].notna()].copy()
    if df.empty: return {}
    df["imp_over"] = 1/df["closing_over25"]
    df["imp_under"] = 1/df["closing_under25"]
    df["overround"] = df["imp_over"] + df["imp_under"]
    overround_pct = (df["overround"].mean() - 1) * 100

    # Favori (en düşük odd)
    df["fav_dir"] = np.where(df["closing_over25"] < df["closing_under25"], "Ust", "Alt")
    df["fav_odd"] = np.where(df["fav_dir"]=="Ust", df["closing_over25"], df["closing_under25"])
    df["fav_won"] = np.where(df["fav_dir"]=="Ust",
                              df["over25_actual"] == 1,
                              df["over25_actual"] == 0)
    fav_hit = df["fav_won"].mean()
    fav_avg_odd = df["fav_odd"].mean()
    fav_breakeven = 1/fav_avg_odd
    fav_edge_pp = (fav_hit - fav_breakeven) * 100
    return {
        "n": len(df),
        "overround_pct": float(overround_pct),
        "fav_hit": float(fav_hit),
        "fav_avg_odd": float(fav_avg_odd),
        "fav_breakeven": float(fav_breakeven),
        "fav_edge_pp": float(fav_edge_pp),
    }


def reliability_ou(df: pd.DataFrame) -> list:
    """A/U piyasa kalibrasyon: market implied prob vs actual hit."""
    df = df[df["closing_over25"].notna()].copy()
    if df.empty: return []
    df["imp_over"] = 1/df["closing_over25"]
    df["imp_under"] = 1/df["closing_under25"]
    s = df["imp_over"] + df["imp_under"]
    df["p_over"] = df["imp_over"] / s  # de-vigged
    # 10 bin
    bins = []
    for lo in np.arange(0.3, 0.8, 0.05):
        hi = lo + 0.05
        mask = (df["p_over"] >= lo) & (df["p_over"] < hi)
        n = mask.sum()
        if n < 30: continue
        avg_p = df.loc[mask, "p_over"].mean()
        actual = df.loc[mask, "over25_actual"].mean()
        bins.append({
            "range": f"{lo:.2f}-{hi:.2f}",
            "n": int(n), "avg_p": float(avg_p),
            "actual": float(actual), "gap": float(actual - avg_p),
        })
    return bins


def run():
    print("=" * 80)
    print("KAPI 0 - TEST 11b: MARKET BASELINE (matches_v2 19K)")
    print("Multi-market potansiyel kaba olcum")
    print("=" * 80)

    df = load_data()
    print(f"\nLoaded {len(df)} settled mac\n")

    leagues = [
        ("ALL 6 LIG", None),
        ("T1 (Turk)", ["T1"]),
        ("E0 (Premier)", ["E0"]),
        ("SP1 (LaLiga)", ["SP1"]),
        ("D1 (Bundes)", ["D1"]),
        ("I1 (Serie A)", ["I1"]),
        ("F1 (Ligue 1)", ["F1"]),
    ]

    # === 1X2 BASELINE ===
    print("-" * 80)
    print(">>> 1X2 PIYASA BASELINE (favori-taraf hit)")
    print("-" * 80)
    print(f"  {'Lig':<14s} {'n':>5s} {'overround%':>10s} {'fav_hit%':>9s} "
          f"{'fav_odd':>8s} {'breakeven%':>10s} {'edge_pp':>8s}")
    for name, lgs in leagues:
        s = market_1x2_baseline(df, lgs)
        if not s: continue
        print(f"  {name:<14s} {s['n']:>5d} {s['overround_pct']:>+9.2f}% "
              f"{s['fav_hit']*100:>8.1f}% {s['fav_avg_odd']:>7.2f} "
              f"{s['fav_breakeven']*100:>9.1f}% {s['fav_edge_pp']:>+7.2f}")

    # === A/U BASELINE ===
    print("\n" + "-" * 80)
    print(">>> A/U 2.5 PIYASA BASELINE")
    print("-" * 80)
    print(f"  {'Lig':<14s} {'n':>5s} {'overround%':>10s} {'fav_hit%':>9s} "
          f"{'fav_odd':>8s} {'breakeven%':>10s} {'edge_pp':>8s}")
    for name, lgs in leagues:
        s = market_ou_baseline(df, lgs)
        if not s: continue
        print(f"  {name:<14s} {s['n']:>5d} {s['overround_pct']:>+9.2f}% "
              f"{s['fav_hit']*100:>8.1f}% {s['fav_avg_odd']:>7.2f} "
              f"{s['fav_breakeven']*100:>9.1f}% {s['fav_edge_pp']:>+7.2f}")

    # === A/U RELIABILITY ===
    print("\n" + "-" * 80)
    print(">>> A/U KALIBRE — Market implied vs Actual")
    print("-" * 80)
    bins = reliability_ou(df)
    print(f"  {'p_over range':<14s} {'n':>5s} {'avg_p':>7s} {'actual':>7s} {'gap':>8s}")
    for b in bins:
        marker = " <- !" if abs(b["gap"]) > 0.05 else ""
        print(f"  {b['range']:<14s} {b['n']:>5d} {b['avg_p']:.3f}  {b['actual']:.3f}  "
              f"{b['gap']:+.3f}{marker}")

    # === ÖZET ===
    print("\n" + "=" * 80)
    print("OZET — Multi-market potansiyel")
    print("=" * 80)
    all_1x2 = market_1x2_baseline(df)
    all_ou = market_ou_baseline(df)
    print(f"\nALL 6 LIG genelinde:")
    print(f"  1X2: overround %{all_1x2['overround_pct']:.2f}, "
          f"favori hit %{all_1x2['fav_hit']*100:.1f}, edge {all_1x2['fav_edge_pp']:+.2f}pp")
    print(f"  A/U: overround %{all_ou['overround_pct']:.2f}, "
          f"favori hit %{all_ou['fav_hit']*100:.1f}, edge {all_ou['fav_edge_pp']:+.2f}pp")
    print()
    if all_ou["overround_pct"] > all_1x2["overround_pct"]:
        diff = all_ou["overround_pct"] - all_1x2["overround_pct"]
        print(f"  A/U pazari %{diff:.2f}pp daha YUKSEK marj -> value avi icin daha geni s")
    if abs(all_ou["fav_edge_pp"]) > 1:
        print(f"  A/U favori edge {all_ou['fav_edge_pp']:+.2f}pp -> piyasa kalibre DEGIL")
        print(f"  -> Modelin bu pazarda value bulma sansi yuksek")
    else:
        print(f"  A/U favori edge {all_ou['fav_edge_pp']:+.2f}pp -> piyasa kalibre")
        print(f"  -> Modelin bu pazarda value bulmasi orta zorluk")

    # Rapor
    rapor = ["# KAPI 0 — TEST 11b: MARKET BASELINE\n"]
    rapor.append(f"**Tarih:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}\n\n")
    rapor.append("## 1X2 Baseline\n\n")
    rapor.append("| Lig | n | overround% | fav_hit% | fav_odd | breakeven% | edge_pp |\n")
    rapor.append("|---|---|---|---|---|---|---|\n")
    for name, lgs in leagues:
        s = market_1x2_baseline(df, lgs)
        if not s: continue
        rapor.append(f"| {name} | {s['n']} | {s['overround_pct']:+.2f}% | "
                     f"{s['fav_hit']*100:.1f}% | {s['fav_avg_odd']:.2f} | "
                     f"{s['fav_breakeven']*100:.1f}% | {s['fav_edge_pp']:+.2f}pp |\n")
    rapor.append("\n## A/U 2.5 Baseline\n\n")
    rapor.append("| Lig | n | overround% | fav_hit% | fav_odd | breakeven% | edge_pp |\n")
    rapor.append("|---|---|---|---|---|---|---|\n")
    for name, lgs in leagues:
        s = market_ou_baseline(df, lgs)
        if not s: continue
        rapor.append(f"| {name} | {s['n']} | {s['overround_pct']:+.2f}% | "
                     f"{s['fav_hit']*100:.1f}% | {s['fav_avg_odd']:.2f} | "
                     f"{s['fav_breakeven']*100:.1f}% | {s['fav_edge_pp']:+.2f}pp |\n")
    out = YAZILIM / "RAPOR" / "Kapi0_T11b_market_baseline.md"
    out.write_text("".join(rapor), encoding="utf-8")
    print(f"\n[OK] Rapor: {out}")


if __name__ == "__main__":
    run()
