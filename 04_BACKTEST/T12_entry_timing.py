"""
TEST T12 — Entry Timing Analizi (Hangi haftadan başlamalı?)
============================================================

BİLİMSEL SORULAR:
    H6a: Sezon başında ROI düşük mü? (Warm-up gerek mi?)
    H6b: Sezon ortasında (matchday 10-25) ROI en yüksek mi?
    H6c: Sezon sonu motivasyon düşer mi?

YÖNTEM:
    1. T1 K=3 picks → her sezon için "season_week" indexle
    2. "Entry week N'den başlasaydım" simülasyonu:
       - N ∈ {1, 5, 10, 15, 20, 25, 30}
       - Sezon-bazlı + cross-sezon aggregate
    3. ROI vs entry week grafiği

ÇIKTI:
    - RAPOR/T12_entry_timing.md
    - 07_LOG_VE_RAPORLAR/T12_entry_curve.csv
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

THIS_DIR = Path(__file__).resolve().parent
YAZILIM = THIS_DIR.parent
RAPOR_DIR = YAZILIM / "RAPOR"
LOGS_DIR = YAZILIM / "07_LOG_VE_RAPORLAR"

sys.path.insert(0, str(THIS_DIR))
from T08_bankroll_singleleague import build_t1_k3_picks
from T11_flat1000 import build_kupons, simulate_flat


def add_season_week(df: pd.DataFrame) -> pd.DataFrame:
    """Her satıra sezon içi hafta numarası (1-N) ekle."""
    df = df.copy()
    df["matchday"] = pd.to_datetime(df["matchday"])
    df["season_year"] = df["matchday"].dt.year
    df["season_month"] = df["matchday"].dt.month
    # Sezon: Aug-May → start year = sezon başı
    df["season_id"] = df.apply(
        lambda r: f"{r['season_year']-1}-{str(r['season_year'])[2:]}"
                  if r["season_month"] <= 5
                  else f"{r['season_year']}-{str(r['season_year']+1)[2:]}",
        axis=1
    )
    # season_week: her sezon içinde sıralı kupon numarası
    df["season_week"] = df.groupby("season_id").cumcount() + 1
    return df


def simulate_entry(kupons: pd.DataFrame, entry_week: int,
                  stake: float = 1000.0) -> dict:
    """Belli bir season_week'ten itibaren oynamaya başlayan strateji."""
    filtered = kupons[kupons["season_week"] >= entry_week]
    if len(filtered) == 0:
        return {"n": 0, "entry_week": entry_week}
    r = simulate_flat(filtered, stake)
    r["entry_week"] = entry_week
    return r


def run():
    print("=" * 100)
    print("T12 — ENTRY TIMING ANALIZI")
    print("=" * 100)

    # T1 K=3 picks
    kupons = build_kupons(K=3, leagues=["T1"])
    kupons = add_season_week(kupons)
    print(f"\nT1 K=3 kupon: {len(kupons)}")
    print(f"Sezonlar: {sorted(kupons['season_id'].unique())}")
    print(f"Sezon başına ortalama: {kupons.groupby('season_id').size().mean():.0f} kupon")

    # Sezon-bazlı detay
    print(f"\n--- Sezon-bazlı kupon dağılımı ---")
    for s in sorted(kupons["season_id"].unique()):
        sub = kupons[kupons["season_id"] == s]
        won = sub["won"].sum()
        print(f"  {s}: {len(sub)} kupon, {won} tuttu ({won/len(sub)*100:.0f}%)")

    # Entry timing sweep
    entry_weeks = [1, 5, 10, 15, 20, 25, 30]
    print(f"\n--- Entry week sweep (her sezon N'den başla) ---")
    print(f"  {'entry':>5s} {'n':>4s} {'won':>4s} {'hit%':>5s} {'avgOdd':>7s} {'hacim':>8s} {'pnl':>9s} {'roi':>6s}")

    results = []
    for ew in entry_weeks:
        r = simulate_entry(kupons, ew)
        results.append(r)
        if r["n"] == 0:
            continue
        print(f"  {ew:>5d} {r['n']:>4d} {r['n_won']:>4d} {r['hit_rate']*100:>4.0f}% "
              f"{r['avg_combo_odd']:>7.2f} {r['total_stake']:>7,.0f} "
              f"{r['total_pnl']:>+8,.0f} {r['roi_pct']:>+5.1f}%")

    # Sezon-içi per-matchday ROI distribution
    print(f"\n--- Sezon içi haftalık dağılım (T1 K=3 hit rate her season_week) ---")
    week_stats = kupons.groupby("season_week").agg(
        n=("won", "size"),
        wins=("won", "sum"),
        avg_odd=("combo_odd", "mean"),
    ).reset_index()
    week_stats["hit_rate"] = week_stats["wins"] / week_stats["n"]
    week_stats["pnl_per_pick"] = week_stats.apply(
        lambda r: r["hit_rate"] * (r["avg_odd"] - 1) - (1 - r["hit_rate"]),
        axis=1
    )
    print(f"  {'week':>4s} {'n':>3s} {'wins':>4s} {'hit%':>5s} {'avgOdd':>7s} {'EV per kupon':>13s}")
    for _, w in week_stats.iterrows():
        if w["n"] >= 2:
            print(f"  {w['season_week']:>4.0f} {w['n']:>3.0f} {w['wins']:>4.0f} "
                  f"{w['hit_rate']*100:>4.0f}% {w['avg_odd']:>7.2f} "
                  f"{w['pnl_per_pick']*1000:>+12,.0f}")

    # Cumulative ROI by entry week (chart data)
    LOGS_DIR.mkdir(exist_ok=True)
    pd.DataFrame(results).to_csv(LOGS_DIR / "T12_entry_curve.csv", index=False)
    week_stats.to_csv(LOGS_DIR / "T12_week_stats.csv", index=False)

    write_report(results, week_stats)
    return results, week_stats


def write_report(results, week_stats):
    RAPOR_DIR.mkdir(exist_ok=True)
    p = RAPOR_DIR / "T12_entry_timing.md"

    rows = []
    for r in results:
        if r["n"] == 0:
            continue
        rows.append(
            f"| {r['entry_week']} | {r['n']} | {r['hit_rate']*100:.0f}% | "
            f"{r['avg_combo_odd']:.2f} | {r['total_stake']:,.0f} | "
            f"{r['total_pnl']:+,.0f} | {r['roi_pct']:+.1f}% |"
        )

    # En iyi entry week
    valid = [r for r in results if r["n"] > 0]
    best = max(valid, key=lambda x: x["roi_pct"]) if valid else None

    # En iyi season_week (yeterli n>=3)
    week_high = week_stats[week_stats["n"] >= 3].sort_values("pnl_per_pick", ascending=False).head(5)
    week_low = week_stats[week_stats["n"] >= 3].sort_values("pnl_per_pick").head(5)

    week_rows = []
    for _, w in week_high.iterrows():
        week_rows.append(
            f"| W{int(w['season_week'])} | {int(w['n'])} | {int(w['wins'])} | "
            f"{w['hit_rate']*100:.0f}% | {w['avg_odd']:.2f} | {w['pnl_per_pick']*1000:+,.0f} |"
        )
    week_low_rows = []
    for _, w in week_low.iterrows():
        week_low_rows.append(
            f"| W{int(w['season_week'])} | {int(w['n'])} | {int(w['wins'])} | "
            f"{w['hit_rate']*100:.0f}% | {w['avg_odd']:.2f} | {w['pnl_per_pick']*1000:+,.0f} |"
        )

    md = f"""# T12 — Entry Timing Analizi (T1 K=3)

**Versiyon:** v1.0
**Tarih:** {datetime.now().isoformat()[:19]}

---

## Hipotez

**H6a:** Sezon başında ROI düşük (warm-up gerek).
**H6b:** Sezon ortası (W10-25) ROI en yüksek.
**H6c:** Sezon sonu motivasyon dağılır, gürültü.

---

## Entry Week Sweep (T1 K=3, 1000 TL flat)

| Entry W | n | Hit% | Avg Odd | Hacim | Net PnL | ROI |
|---|---:|---:|---:|---:|---:|---:|
{chr(10).join(rows)}

**En iyi entry:** {f"W{best['entry_week']} ROI {best['roi_pct']:+.1f}%" if best else 'yok'}

---

## En Karlı Haftalar (sezon içi)

| Week | n | Wins | Hit% | Avg Odd | EV per kupon (TL) |
|---|---:|---:|---:|---:|---:|
{chr(10).join(week_rows)}

## En Az Karlı (KAÇINILACAK) Haftalar

| Week | n | Wins | Hit% | Avg Odd | EV per kupon (TL) |
|---|---:|---:|---:|---:|---:|
{chr(10).join(week_low_rows)}

---

## Yorum

- **Sezon-içi ROI dalgalanması** açık görünüyor mu?
- **Warm-up week** kaç haftası kayıp ediyor?
- **Sezon sonu** noise artıyor mu?

Bu sorulara T13 (skip-week) test cevap verecek.

CSV: `07_LOG_VE_RAPORLAR/T12_entry_curve.csv`, `T12_week_stats.csv`
"""
    p.write_text(md, encoding="utf-8")
    print(f"\nRapor: {p}")


if __name__ == "__main__":
    run()
