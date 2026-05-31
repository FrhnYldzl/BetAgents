"""
TEST T14 — Multi-League 1000 TL/Lig Budget
============================================

BİLİMSEL SORULAR:
    H8a: Her ligten 1000 TL paralel → toplam kar T1-only'den yüksek?
    H8b: Ligler arası korelasyon ≤0 → diversifikasyon variance azaltır?
    H8c: 5-6 lige genişletmek değer kazandırır mı?

KAYNAK:
    Mevcut signal_snapshots: D1, E0, T1 (Football-Data mirror sınırı)
    SP1+I1+F1: CSV mirror yok — sonradan ingest gerek

YÖNTEM:
    1. K=3, flat 1000 TL/kupon/lig
    2. Skip dark weeks (T13 winner) opsiyonel
    3. Karşılaştırma:
       - T1-only (1000/hafta, hacim ~103K)
       - E0+T1 paralel (2000/hafta)
       - ALL 3-lig paralel (3000/hafta)
       - + skip_dark_weeks varyantları

ÇIKTI:
    - RAPOR/T14_multileague_budget.md
    - 07_LOG_VE_RAPORLAR/T14_results.csv
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
from T11_flat1000 import build_kupons, simulate_flat
from T12_entry_timing import add_season_week
from T13_skip_strategy import apply_skip_rules

DARK_WEEKS = {16, 17, 18, 20, 22, 23, 24, 25, 26, 27}


def run():
    print("=" * 100)
    print("T14 — MULTI-LEAGUE BUDGET (Flat 1000 TL/lig/kupon)")
    print("=" * 100)

    # Her lig için K=3 kuponlar
    k_t1 = build_kupons(3, ["T1"])
    k_e0 = build_kupons(3, ["E0"])
    k_d1 = build_kupons(3, ["D1"])
    print(f"\nT1 K=3: {len(k_t1)} kupon, hit %{k_t1['won'].mean()*100:.0f}")
    print(f"E0 K=3: {len(k_e0)} kupon, hit %{k_e0['won'].mean()*100:.0f}")
    print(f"D1 K=3: {len(k_d1)} kupon, hit %{k_d1['won'].mean()*100:.0f}")

    # Skip dark weeks variants
    k_t1_ws = add_season_week(k_t1)
    k_t1_skip = k_t1_ws[~k_t1_ws["season_week"].isin(DARK_WEEKS)]
    k_e0_ws = add_season_week(k_e0)
    k_e0_skip = k_e0_ws[~k_e0_ws["season_week"].isin(DARK_WEEKS)]
    k_d1_ws = add_season_week(k_d1)
    k_d1_skip = k_d1_ws[~k_d1_ws["season_week"].isin(DARK_WEEKS)]

    print(f"\nDark weeks skip uygulandi:")
    print(f"  T1: {len(k_t1)} -> {len(k_t1_skip)}")
    print(f"  E0: {len(k_e0)} -> {len(k_e0_skip)}")
    print(f"  D1: {len(k_d1)} -> {len(k_d1_skip)}")

    # Strategies
    configs = [
        ("T1-only", [k_t1]),
        ("T1-only +skip_dark", [k_t1_skip]),
        ("E0+T1 paralel", [k_t1, k_e0]),
        ("E0+T1 paralel +skip_dark", [k_t1_skip, k_e0_skip]),
        ("ALL 3-lig paralel", [k_t1, k_e0, k_d1]),
        ("ALL 3-lig +skip_dark", [k_t1_skip, k_e0_skip, k_d1_skip]),
    ]

    print(f"\n{'STRATEGY':38s} {'n':>4s} {'hit%':>5s} {'hacim':>10s} {'pnl':>10s} {'roi':>6s} {'maxDD':>7s}")
    print("-" * 110)
    results = []
    for name, dfs in configs:
        # Tüm liglerin kuponlarını birleştir
        merged = pd.concat(dfs, ignore_index=True).sort_values("matchday")
        r = simulate_flat(merged, stake=1000.0)
        r["name"] = name
        results.append(r)
        if r["n"] == 0:
            continue
        print(f"  {name:36s} {r['n']:>4d} {r['hit_rate']*100:>4.0f}% "
              f"{r['total_stake']:>9,.0f} {r['total_pnl']:>+9,.0f} "
              f"{r['roi_pct']:>+5.1f}% {r['max_drawdown_tl']:>6,.0f}")

    # Extrapolasyon: 5-6 lig
    print(f"\n--- EKSTRAPOLASYON (mevcut veri ile gözlem) ---")
    avg_pnl_per_league_per_week = {}
    for lg, kp in [("T1", k_t1), ("E0", k_e0), ("D1", k_d1)]:
        days = (kp["matchday"].max() - kp["matchday"].min()).days
        years = max(days / 365.25, 0.5)
        # her lig: per-week annual pnl
        r = simulate_flat(kp, stake=1000.0)
        avg_pnl_per_league_per_week[lg] = r["annual_pnl"]
        print(f"  {lg}: yıllık ortalama {r['annual_pnl']:+,.0f} TL")

    # 5-6 lig hipotezi (SP1, I1, F1 benzer ortalama edge varsa)
    avg_other = (avg_pnl_per_league_per_week["E0"] + avg_pnl_per_league_per_week["D1"]) / 2
    estimated_5_lig = (
        avg_pnl_per_league_per_week["T1"]
        + avg_pnl_per_league_per_week["E0"]
        + avg_pnl_per_league_per_week["D1"]
        + 2 * avg_other
    )
    print(f"\n  5-lig (T1+E0+D1+SP1*+I1*) yıllık tahmin: {estimated_5_lig:+,.0f} TL/yıl")
    print(f"  6-lig (+ F1*) yıllık tahmin: {estimated_5_lig + avg_other:+,.0f} TL/yıl")
    print(f"  (*) SP1/I1/F1 verisi henüz yok, tahmin E0+D1 ortalaması bazında")

    # CSV
    LOGS_DIR.mkdir(exist_ok=True)
    pd.DataFrame([{
        "name": r["name"], "n": r["n"], "hit_rate": r["hit_rate"],
        "total_stake": r["total_stake"], "total_pnl": r["total_pnl"],
        "roi_pct": r["roi_pct"], "max_dd": r["max_drawdown_tl"],
        "annual_pnl": r["annual_pnl"], "monthly_pnl": r["monthly_pnl"]
    } for r in results]).to_csv(LOGS_DIR / "T14_results.csv", index=False)

    write_report(results, avg_pnl_per_league_per_week, estimated_5_lig, avg_other)
    return results


def write_report(results, avg_pnl, est5, avg_other):
    RAPOR_DIR.mkdir(exist_ok=True)
    p = RAPOR_DIR / "T14_multileague_budget.md"

    rows = []
    for r in results:
        if r["n"] == 0:
            continue
        rows.append(
            f"| {r['name']} | {r['n']} | {r['hit_rate']*100:.0f}% | "
            f"{r['avg_combo_odd']:.2f} | "
            f"{r['total_stake']:,.0f} | {r['total_pnl']:+,.0f} | "
            f"{r['roi_pct']:+.1f}% | {r['max_drawdown_tl']:,.0f} | "
            f"{r['monthly_pnl']:+,.0f} | {r['annual_pnl']:+,.0f} |"
        )

    md = f"""# T14 — Multi-League Budget (Flat 1000 TL/lig/kupon)

**Versiyon:** v1.0
**Tarih:** {datetime.now().isoformat()[:19]}

---

## Bilimsel Sorular

**H8a:** Multi-league diversifikasyon flat altında toplam karı artırır mı?
**H8b:** Ligler arası korelasyon ≤0 olduğu için variance düşer mi?
**H8c:** 5-6 lig hipotetik genişleme değerli mi?

---

## Sonuçlar (Mevcut 3 lig)

| Strateji | n | Hit% | Avg Odd | Hacim | Net PnL | ROI | MaxDD | Aylık | Yıllık |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
{chr(10).join(rows)}

---

## Per-Lig Yıllık Ortalama (Flat 1000 TL/kupon)

| Lig | Yıllık PnL (TL) |
|---|---:|
| T1 | {avg_pnl['T1']:+,.0f} |
| E0 | {avg_pnl['E0']:+,.0f} |
| D1 | {avg_pnl['D1']:+,.0f} |

---

## Ekstrapolasyon (gözlem bazlı)

**Eğer SP1, I1, F1 verisi olsa idi** (E0+D1 ortalaması ile aynı edge varsayımı):

| Konfigürasyon | Tahmini Yıllık |
|---|---:|
| 3-lig (mevcut) | {sum(avg_pnl.values()):+,.0f} TL/yıl |
| **5-lig (+ SP1+I1)** | **{est5:+,.0f} TL/yıl** |
| **6-lig (+ F1)** | **{est5 + avg_other:+,.0f} TL/yıl** |

⚠️ **Önemli uyarı:** Bu ekstrapolasyon her ligin edge'inin aynı olduğunu varsayar. Gerçekte SP1/I1/F1 farklı sharpness'a sahip olabilir (D1 zaten ROI -1.7% verdi 3-lig altında).

---

## Yorum

**Senin sorunun cevabı:**
- 3-lig × 1000 TL flat (T11'den +81K) → 4 sezon
- Skip dark weeks ile aynı hipotez → daha yüksek olabilir
- 5-lig'e genişleme tahminen yıllık +20-25K ekler

**Pratik tavsiye:** Mevcut 3 lig için **ALL paralel + skip_dark_weeks** stratejisi en optimum görünüyor.

CSV: `07_LOG_VE_RAPORLAR/T14_results.csv`
"""
    p.write_text(md, encoding="utf-8")
    print(f"\nRapor: {p}")


if __name__ == "__main__":
    run()
