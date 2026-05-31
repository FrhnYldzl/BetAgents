"""
TEST T13 — Skip Week (PAS) Stratejisi
======================================

BİLİMSEL SORULAR:
    H7a: Düşük sinyal yoğunluklu haftalar kaybettiriyor.
    H7b: Belirli season_week aralıkları sürekli kötü.
    H7c: Combo odd çok yüksek olduğunda hit rate çok düşer.

YÖNTEM:
    1. Baseline = T1 K=3 hep oyna (T11'den +62K)
    2. Skip kuralları:
        a) season_week ∈ {16,17,18,22,23,24,25,26,27} (T12'den karanlık bölge)
        b) max score_v13 < 0.75 (zayıf sinyal hafta)
        c) avg combo_odd > 9.0 (aşırı uzak combo)
        d) signal_count < ortalama
        e) Multi: a + c
    3. Her kural için: net PnL, kaç hafta atlanır, kaybedilen fırsat var mı

ÇIKTI:
    - RAPOR/T13_skip_strategy.md
    - 07_LOG_VE_RAPORLAR/T13_skip_results.csv
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
from T01_consensus_survival import load_snapshots
from T02_combo_kupon import get_odd_for_direction, did_win
from T04_league_validation import add_fav_confirmed


def enrich_kupons_with_metadata() -> pd.DataFrame:
    """Her T1 K=3 kupon için max_score, signal_count vb. metadata ekle."""
    df = load_snapshots()
    df["matchday"] = pd.to_datetime(df["kickoff_iso"]).dt.normalize()
    df = df[df["settled"] == 1].copy()
    df = add_fav_confirmed(df)
    df = df[(df["league_code"] == "T1") & (df["dir_fav_confirmed"].notna())]
    df = df.sort_values("score_v13", ascending=False)

    kupons = []
    for md, group in df.groupby("matchday"):
        top3 = group.head(3)
        if len(top3) < 3:
            continue
        combo_odd = 1.0; all_won = True
        for _, leg in top3.iterrows():
            d = leg["dir_fav_confirmed"]
            o = get_odd_for_direction(leg, d)
            w = did_win(leg, d)
            if not o or o < 1.01:
                combo_odd = None; break
            combo_odd *= o
            if not w:
                all_won = False
        if combo_odd is None:
            continue
        kupons.append({
            "matchday": md, "league": "T1",
            "combo_odd": combo_odd, "won": all_won,
            "max_score": top3["score_v13"].max(),
            "min_score": top3["score_v13"].min(),
            "avg_score": top3["score_v13"].mean(),
            "max_signal_count": top3["signal_count"].max() if "signal_count" in top3 else 0,
            "min_agree_count": top3["agree_count"].min() if "agree_count" in top3 else 0,
        })
    df_kupons = pd.DataFrame(kupons).sort_values("matchday").reset_index(drop=True)
    df_kupons = add_season_week(df_kupons)
    return df_kupons


def apply_skip_rules(kupons: pd.DataFrame, rule_name: str) -> pd.DataFrame:
    """Verilen kuralı uygula, kalan kuponları dön."""
    if rule_name == "baseline":
        return kupons.copy()
    elif rule_name == "skip_dark_weeks":
        # T12'den karanlık bölge: W16-18 + W22-27
        dark = {16, 17, 18, 20, 22, 23, 24, 25, 26, 27}
        return kupons[~kupons["season_week"].isin(dark)]
    elif rule_name == "skip_low_score":
        # max_score < 0.75
        return kupons[kupons["max_score"] >= 0.75]
    elif rule_name == "skip_high_odd":
        # avg combo_odd > 9.0 (aşırı uzak)
        return kupons[kupons["combo_odd"] <= 9.0]
    elif rule_name == "skip_low_signals":
        # max_signal_count < 3
        return kupons[kupons["max_signal_count"] >= 3]
    elif rule_name == "multi_dark_high":
        dark = {16, 17, 18, 20, 22, 23, 24, 25, 26, 27}
        return kupons[
            (~kupons["season_week"].isin(dark)) &
            (kupons["combo_odd"] <= 9.0)
        ]
    elif rule_name == "season_start_only":
        # sadece W1-15
        return kupons[kupons["season_week"] <= 15]
    elif rule_name == "season_end_only":
        # sadece W28+
        return kupons[kupons["season_week"] >= 28]
    elif rule_name == "skip_first5":
        return kupons[kupons["season_week"] >= 6]
    elif rule_name == "midseason_W6_15":
        return kupons[(kupons["season_week"] >= 6) & (kupons["season_week"] <= 15)]
    return kupons


def run():
    print("=" * 100)
    print("T13 — SKIP WEEK (PAS) STRATEJISI")
    print("=" * 100)

    kupons = enrich_kupons_with_metadata()
    print(f"\nT1 K=3 kupon: {len(kupons)}")
    print(f"Score dağılımı: median={kupons['max_score'].median():.2f}, "
          f"avg={kupons['max_score'].mean():.2f}")
    print(f"Combo odd dağılımı: median={kupons['combo_odd'].median():.2f}, "
          f"avg={kupons['combo_odd'].mean():.2f}")

    rules = [
        "baseline",
        "skip_dark_weeks",
        "skip_low_score",
        "skip_high_odd",
        "skip_low_signals",
        "multi_dark_high",
        "season_start_only",
        "season_end_only",
        "skip_first5",
        "midseason_W6_15",
    ]

    print(f"\n{'RULE':25s} {'n':>4s} {'won':>4s} {'hit%':>5s} {'hacim':>8s} {'pnl':>9s} {'roi':>7s} {'vs_base':>9s}")
    print("-" * 90)

    results = []
    baseline_pnl = None
    for rule in rules:
        sub = apply_skip_rules(kupons, rule)
        if len(sub) == 0:
            continue
        r = simulate_flat(sub, stake=1000.0)
        r["rule"] = rule
        r["n_skipped"] = len(kupons) - len(sub)
        results.append(r)
        if rule == "baseline":
            baseline_pnl = r["total_pnl"]
        diff = r["total_pnl"] - baseline_pnl if baseline_pnl is not None else 0
        diff_pct = (diff / baseline_pnl * 100) if baseline_pnl else 0
        print(f"  {rule:23s} {r['n']:>4d} {r['n_won']:>4d} {r['hit_rate']*100:>4.0f}% "
              f"{r['total_stake']:>7,.0f} {r['total_pnl']:>+8,.0f} "
              f"{r['roi_pct']:>+6.1f}% {diff:>+8,.0f}")

    # CSV
    LOGS_DIR.mkdir(exist_ok=True)
    pd.DataFrame([{
        "rule": r["rule"], "n": r["n"], "n_skipped": r["n_skipped"],
        "hit_rate": r["hit_rate"], "roi_pct": r["roi_pct"],
        "total_pnl": r["total_pnl"]
    } for r in results]).to_csv(LOGS_DIR / "T13_skip_results.csv", index=False)

    write_report(results, baseline_pnl)
    return results


def write_report(results, baseline_pnl):
    RAPOR_DIR.mkdir(exist_ok=True)
    p = RAPOR_DIR / "T13_skip_strategy.md"

    rows = []
    for r in results:
        diff = r["total_pnl"] - baseline_pnl if baseline_pnl is not None else 0
        rows.append(
            f"| {r['rule']} | {r['n']} | {r['n_skipped']} | "
            f"{r['hit_rate']*100:.0f}% | {r['avg_combo_odd']:.2f} | "
            f"{r['total_stake']:,.0f} | {r['total_pnl']:+,.0f} | "
            f"{r['roi_pct']:+.1f}% | {diff:+,.0f} |"
        )

    valid = [r for r in results if r["rule"] != "baseline"]
    best = max(valid, key=lambda x: x["total_pnl"]) if valid else None
    worst = min(valid, key=lambda x: x["total_pnl"]) if valid else None

    md = f"""# T13 — Skip Week (PAS) Stratejisi

**Versiyon:** v1.0
**Tarih:** {datetime.now().isoformat()[:19]}

---

## Bilimsel Sorular

**H7a:** Düşük sinyal yoğunluklu haftalar kaybettiriyor?
**H7b:** Belirli season_week aralıkları sürekli kötü?
**H7c:** Combo odd çok yüksek olduğunda hit rate düşer?

---

## Sonuçlar

| Skip Rule | n play | n skip | Hit% | Avg Odd | Hacim | Net PnL | ROI | vs Baseline |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
{chr(10).join(rows)}

---

## Yorum

**En iyi skip rule:** {f"`{best['rule']}` → ROI {best['roi_pct']:+.1f}%, net {best['total_pnl']:+,.0f} TL (baseline'dan {best['total_pnl']-baseline_pnl:+,.0f} TL üstün)" if best else 'yok'}

**En kötü skip rule:** {f"`{worst['rule']}` → ROI {worst['roi_pct']:+.1f}%" if worst else 'yok'}

### Önemli sorular:
1. **Skip rule edge'i artırdı mı?** Evet/hayır → veriye göre
2. **Sample boyutu yeterli mi?** Skip sonrası n düşmemeli
3. **Out-of-sample doğrulanır mı?** 2425 sezonu için test edilmeli

CSV: `07_LOG_VE_RAPORLAR/T13_skip_results.csv`
"""
    p.write_text(md, encoding="utf-8")
    print(f"\nRapor: {p}")


if __name__ == "__main__":
    run()
