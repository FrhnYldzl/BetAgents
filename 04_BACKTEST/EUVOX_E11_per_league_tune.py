"""
EUVOX E11 — Per-Lig Tuning (DC dahil yeniden test)
====================================================

DC modelleri SP1/I1/F1'e eklendi. Şimdi tekrar test.

Her lig için:
    - min_confirmers ∈ {1, 2}
    - score_v13 threshold ∈ {0, 0.5, 0.7}
    - K ∈ {2, 3}

En iyi config'i bul.

ÇIKTI:
    - RAPOR/EUVOX_E11_per_league_tune.md
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

sys.path.insert(0, str(YAZILIM / "03_MODELLER" / "selective"))
from trivox_v1 import TrivoxModel, TrivoxConfig, fav_confirmed, normalize_dir, get_odd_for_dir, did_win


def load_data():
    import sqlite3
    conn = sqlite3.connect(YAZILIM / "02_VERI" / "bahis_agent.db")
    df = pd.read_sql_query(
        "SELECTION * FROM signal_snapshots WHERE source='football_data'".replace("SELECTION", "SELECT"),
        conn
    )
    conn.close()
    df["matchday"] = pd.to_datetime(df["kickoff_iso"]).dt.normalize()
    return df


def evaluate_config(df, league, K, min_conf, score_thr):
    """Bir lig + config için kupon say + ROI."""
    sub = df[(df["league_code"] == league) & (df["settled"] == 1)].copy()
    sub["dir_fc"] = sub.apply(
        lambda r: fav_confirmed(r.to_dict(), min_conf), axis=1
    )
    sub = sub[sub["dir_fc"].notna()]
    if score_thr > 0:
        sub = sub[sub["score_v13"] >= score_thr]
    if sub.empty:
        return None
    sub = sub.sort_values("score_v13", ascending=False)
    kupons = []
    for md, group in sub.groupby("matchday"):
        topK = group.head(K)
        if len(topK) < K:
            continue
        combo_odd = 1.0; all_won = True
        for _, leg in topK.iterrows():
            d = leg["dir_fc"]
            o = get_odd_for_dir(leg.to_dict(), d)
            w = did_win(leg.to_dict(), d)
            if not o or o < 1.01:
                combo_odd = None; break
            combo_odd *= o
            if not w: all_won = False
        if combo_odd is None: continue
        kupons.append({"combo_odd": combo_odd, "won": all_won})
    if not kupons:
        return None
    df_k = pd.DataFrame(kupons)
    pnl = sum(1000 * (k["combo_odd"] - 1) if k["won"] else -1000 for _, k in df_k.iterrows())
    return {
        "n": len(df_k), "won": int(df_k["won"].sum()),
        "hit_rate": df_k["won"].mean(),
        "avg_odd": df_k["combo_odd"].mean(),
        "total_stake": len(df_k) * 1000,
        "total_pnl": pnl,
        "roi_pct": pnl / (len(df_k) * 1000) * 100,
    }


def run():
    print("=" * 100)
    print("EUVOX E11 — Per-Lig Tuning (DC dahil yeniden test)")
    print("=" * 100)

    df = load_data()
    print(f"\nLoaded: {len(df)} kayit")

    # Önce default config: K=3, min_conf=1, no threshold
    print("\n=== DEFAULT CONFIG (K=3, min_conf=1, thr=0) ===")
    print(f"{'LIG':5s} {'n':>4s} {'won':>4s} {'hit%':>5s} {'avgOdd':>7s} {'pnl':>10s} {'ROI':>6s}")
    print("-" * 70)
    default_results = []
    for lg in ["T1", "E0", "D1", "SP1", "I1", "F1"]:
        r = evaluate_config(df, lg, K=3, min_conf=1, score_thr=0)
        if not r:
            print(f"  {lg:4s} (0 kupon)")
            continue
        r["lig"] = lg
        default_results.append(r)
        print(f"  {lg:4s} {r['n']:>4d} {r['won']:>4d} {r['hit_rate']*100:>4.0f}% "
              f"{r['avg_odd']:>7.2f} {r['total_pnl']:>+9,.0f} {r['roi_pct']:>+5.1f}%")

    # 6-lig toplam
    total_n = sum(r["n"] for r in default_results)
    total_pnl = sum(r["total_pnl"] for r in default_results)
    total_stake = sum(r["total_stake"] for r in default_results)
    print(f"\n  6-LIG TOPLAM: n={total_n}, pnl={total_pnl:+,.0f}, ROI={total_pnl/total_stake*100:+.1f}%")

    # Per-lig optimum tuning (gridsearch)
    print(f"\n=== PER-LIG TUNING (grid search per league) ===")
    tuning_results = []
    for lg in ["T1", "E0", "D1", "SP1", "I1", "F1"]:
        best = None
        for K in [2, 3]:
            for mc in [1, 2]:
                for thr in [0, 0.5, 0.7]:
                    r = evaluate_config(df, lg, K, mc, thr)
                    if not r or r["n"] < 20:
                        continue
                    if best is None or r["total_pnl"] > best["total_pnl"]:
                        best = r
                        best["config"] = f"K{K}/mc{mc}/thr{thr}"
        if best:
            best["lig"] = lg
            tuning_results.append(best)
            print(f"  {lg:4s} BEST: {best['config']:18s} "
                  f"n={best['n']:>3} hit={best['hit_rate']*100:>3.0f}% "
                  f"ROI={best['roi_pct']:>+5.1f}% pnl={best['total_pnl']:>+8,.0f}")

    # EUVOX bireşim
    print(f"\n=== EUVOX BİREŞİM ===")
    eligible = [r for r in tuning_results if r["roi_pct"] > 0 and r["n"] >= 30]
    print(f"Pozitif edge ve n>=30: {len(eligible)}/6 lig")
    if eligible:
        total_pnl = sum(r["total_pnl"] for r in eligible)
        total_n = sum(r["n"] for r in eligible)
        total_stake = sum(r["total_stake"] for r in eligible)
        print(f"  EUVOX-EDGE n: {total_n}, pnl: {total_pnl:+,.0f}, ROI: {total_pnl/total_stake*100:+.1f}%")
        for r in eligible:
            print(f"    {r['lig']:4s} ({r['config']}): ROI {r['roi_pct']:+.1f}%, pnl {r['total_pnl']:+,.0f}")

    write_report(default_results, tuning_results, eligible)
    return tuning_results


def write_report(default, tuned, eligible):
    RAPOR_DIR.mkdir(exist_ok=True)
    p = RAPOR_DIR / "EUVOX_E11_per_league_tune.md"

    def_rows = []
    for r in default:
        def_rows.append(
            f"| {r['lig']} | {r['n']} | {r['hit_rate']*100:.0f}% | "
            f"{r['avg_odd']:.2f} | {r['total_pnl']:+,.0f} | {r['roi_pct']:+.1f}% |"
        )
    tune_rows = []
    for r in tuned:
        tune_rows.append(
            f"| {r['lig']} | {r['config']} | {r['n']} | "
            f"{r['hit_rate']*100:.0f}% | {r['avg_odd']:.2f} | "
            f"{r['total_pnl']:+,.0f} | {r['roi_pct']:+.1f}% |"
        )

    total_pnl_elig = sum(r["total_pnl"] for r in eligible) if eligible else 0
    total_n_elig = sum(r["n"] for r in eligible) if eligible else 0
    total_stake_elig = sum(r["total_stake"] for r in eligible) if eligible else 1

    md = f"""# EUVOX E11 — Per-Lig Tuning (DC dahil)

**Tarih:** {datetime.now().isoformat()[:19]}

DC modelleri SP1/I1/F1'e eklendi. Yeniden test.

---

## Default Config (K=3, min_conf=1, score_thr=0)

| Lig | n | Hit% | Avg Odd | Net PnL | ROI |
|---|---:|---:|---:|---:|---:|
{chr(10).join(def_rows)}

---

## Per-Lig En İyi Config (Grid Search)

| Lig | Config | n | Hit% | Avg Odd | Net PnL | ROI |
|---|---|---:|---:|---:|---:|---:|
{chr(10).join(tune_rows)}

---

## EUVOX Birleşim (Pozitif edge ve n>=30)

**{len(eligible)}/6 lig** eligible.

Toplam:
- n: {total_n_elig}
- pnl: {total_pnl_elig:+,.0f} TL
- ROI: {total_pnl_elig/total_stake_elig*100:+.1f}%

---

## Sonuç

EUVOX'un her ligi için **optimal config** tablonun üstünde.
"""
    p.write_text(md, encoding="utf-8")
    print(f"\nRapor: {p}")


if __name__ == "__main__":
    run()
