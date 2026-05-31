"""
TEST T15 — Optimum Kombinasyon (Cross-Validation)
==================================================

BİLİMSEL SORU:
    H9a: T12 (entry) + T13 (skip) + T14 (multi-league) birleşik en iyi config
         tek-faktöre üstün mü?
    OVERFIT KORKUSU: T13 dark_weeks bulgusu in-sample. Out-of-sample doğrula.

YÖNTEM (Cross-Validation):
    1. TRAIN seasons: 2122 + 2223 (dark_weeks belirlemek için)
    2. TEST seasons: 2324 + 2425 (out-of-sample skip rule)
    3. Train'de dark_weeks_v2 belirle (yeni karanlık bölge)
    4. Test'te skip uygula → ROI hâlâ pozitif mi?

GRID:
    - Lig: T1, E0+T1, ALL
    - Skip: none, train_dark
    - K: 3
    - Entry: 1

ÇIKTI:
    - RAPOR/T15_optimum_combo.md
    - 07_LOG_VE_RAPORLAR/T15_cv_results.csv
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


def find_dark_weeks(kupons: pd.DataFrame, threshold_hit_rate: float = 0.10) -> set:
    """Bir veri setinde 'dark week'leri keşfet (hit rate düşük)."""
    week_stats = kupons.groupby("season_week").agg(
        n=("won", "size"), wins=("won", "sum"),
    )
    week_stats["hit_rate"] = week_stats["wins"] / week_stats["n"]
    # n>=3 olan haftalar arasında hit_rate < threshold
    dark = week_stats[
        (week_stats["n"] >= 3) &
        (week_stats["hit_rate"] <= threshold_hit_rate)
    ].index.tolist()
    return set(int(w) for w in dark)


def run():
    print("=" * 100)
    print("T15 — OPTIMUM KOMBINASYON (CROSS-VALIDATION)")
    print("=" * 100)

    # Tüm 4 sezon picks
    kupons = build_kupons(K=3, leagues=["T1"])
    kupons = add_season_week(kupons)
    print(f"\nT1 K=3 kupons: {len(kupons)}, sezonlar: {sorted(kupons['season_id'].unique())}")

    # CV: train 2122+2223, test 2324+2425
    train_seasons = ["2021-22", "2022-23"]
    test_seasons = ["2023-24", "2024-25"]
    train = kupons[kupons["season_id"].isin(train_seasons)]
    test = kupons[kupons["season_id"].isin(test_seasons)]
    print(f"Train (2122+2223): {len(train)} kupon, hit %{train['won'].mean()*100:.0f}")
    print(f"Test  (2324+2425): {len(test)} kupon, hit %{test['won'].mean()*100:.0f}")

    # Find dark weeks on TRAIN only
    dark_weeks_train = find_dark_weeks(train, threshold_hit_rate=0.10)
    print(f"\nTrain-only dark weeks: {sorted(dark_weeks_train)}")

    # Apply to TEST (out-of-sample!)
    test_no_skip = test
    test_skip = test[~test["season_week"].isin(dark_weeks_train)]
    train_no_skip = train
    train_skip = train[~train["season_week"].isin(dark_weeks_train)]

    print(f"\nTest after skip: {len(test_no_skip)} -> {len(test_skip)} kupon")

    # Simulate
    print(f"\n{'Variant':30s} {'n':>4s} {'won':>4s} {'hit%':>5s} {'pnl':>10s} {'roi':>8s}")
    print("-" * 80)
    variants = [
        ("TRAIN no skip", train_no_skip),
        ("TRAIN +skip_dark (in-sample)", train_skip),
        ("TEST no skip (baseline)", test_no_skip),
        ("TEST +skip_dark (out-of-sample!)", test_skip),
    ]
    results = []
    for name, df in variants:
        r = simulate_flat(df, stake=1000.0)
        r["variant"] = name
        results.append(r)
        if r["n"] == 0:
            continue
        print(f"  {name:28s} {r['n']:>4d} {r['n_won']:>4d} {r['hit_rate']*100:>4.0f}% "
              f"{r['total_pnl']:>+9,.0f} {r['roi_pct']:>+7.1f}%")

    # OVERFIT TEST
    test_baseline = next(r for r in results if "TEST no skip" in r["variant"])
    test_skip_r = next(r for r in results if "TEST +skip_dark" in r["variant"])
    overfit_delta = test_skip_r["roi_pct"] - test_baseline["roi_pct"]
    print(f"\n=== OUT-OF-SAMPLE OVERFIT TESTİ ===")
    print(f"Test ROI (no skip)  : {test_baseline['roi_pct']:+.1f}%")
    print(f"Test ROI (with skip): {test_skip_r['roi_pct']:+.1f}%")
    print(f"Delta              : {overfit_delta:+.1f} pp")
    if overfit_delta > 5:
        verdict = "[OK]Skip rule out-of-sample GERÇEK (overfit değil)"
    elif overfit_delta > 0:
        verdict = "[+]Skip rule marjinal fayda, doğrulanmaya devam"
    else:
        verdict = "[X]OVERFIT — train'de iyi, test'te kötü"
    print(f"Verdikt           : {verdict}")

    # CSV
    LOGS_DIR.mkdir(exist_ok=True)
    pd.DataFrame([{
        "variant": r["variant"], "n": r["n"], "hit_rate": r["hit_rate"],
        "roi_pct": r["roi_pct"], "total_pnl": r["total_pnl"],
    } for r in results]).to_csv(LOGS_DIR / "T15_cv_results.csv", index=False)

    write_report(results, dark_weeks_train, overfit_delta, verdict)
    return results


def write_report(results, dark_weeks, overfit_delta, verdict):
    RAPOR_DIR.mkdir(exist_ok=True)
    p = RAPOR_DIR / "T15_optimum_combo.md"

    rows = []
    for r in results:
        if r["n"] == 0:
            continue
        rows.append(
            f"| {r['variant']} | {r['n']} | {r['n_won']} | "
            f"{r['hit_rate']*100:.0f}% | {r['total_stake']:,.0f} | "
            f"{r['total_pnl']:+,.0f} | {r['roi_pct']:+.1f}% |"
        )

    md = f"""# T15 — Optimum Kombinasyon (Cross-Validation)

**Versiyon:** v1.0
**Tarih:** {datetime.now().isoformat()[:19]}

---

## Bilimsel Soru

T13'te bulduğumuz **skip_dark_weeks** stratejisi gerçek edge mi yoksa **overfit** mi?

### Yöntem
- **Train:** 2021-22 + 2022-23 sezonu → dark_weeks tanımla
- **Test:** 2023-24 + 2024-25 sezonu → skip uygulanmış mı kazanıyor?

---

## Train'de keşfedilen Dark Weeks (hit≤%10, n≥3)

```
{sorted(dark_weeks)}
```

---

## Sonuçlar

| Variant | n | Won | Hit% | Hacim | Net PnL | ROI |
|---|---:|---:|---:|---:|---:|---:|
{chr(10).join(rows)}

---

## Overfit Verdict

**Delta (Test ROI with skip − Test ROI no skip):** {overfit_delta:+.1f} pp

**Karar:** {verdict}

---

## Yorum

{f'''Skip rule TRAIN'de güçlü performans verdi. Out-of-sample TEST'te de ROI artışı devam ediyorsa
gerçek bir desenden bahsediyoruz. Yoksa overfit kanıtı ortada.

**Sonuç:** {verdict}'''}

CSV: `07_LOG_VE_RAPORLAR/T15_cv_results.csv`
"""
    p.write_text(md, encoding="utf-8")
    print(f"\nRapor: {p}")


if __name__ == "__main__":
    run()
