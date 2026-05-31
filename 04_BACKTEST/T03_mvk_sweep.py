"""
TEST T03 — Minimum Viable Kombin (MVK)
=======================================

ODAK: Her hafta için AT LEAST 1 kombin yapmak. Eşik gevşetilebilir.

SÜPÜRME:
    K (combo legs)   : 1, 2, 3
    min_signals      : 2, 3
    min_agree        : 2, 3
    direction_source : "consensus" / "favorite + agree"

HEDEF: positive_weeks_ratio (PWR) en yüksek konfigürasyon, COMBO ROI > 0.

Şarşı (constraint):
    Her hafta en az 1 kombin yapılabilir → coverage_ratio yüksek olsun.

ÇIKTI:
    - RAPOR/T03_mvk_sweep.md (tüm grid)
    - 07_LOG_VE_RAPORLAR/T03_grid.csv
    - 07_LOG_VE_RAPORLAR/T03_best_picks.csv
"""
from __future__ import annotations

import itertools
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

THIS_DIR = Path(__file__).resolve().parent
YAZILIM = THIS_DIR.parent
RAPOR_DIR = YAZILIM / "RAPOR"
LOGS_DIR = YAZILIM / "07_LOG_VE_RAPORLAR"
DB_PATH = YAZILIM / "02_VERI" / "bahis_agent.db"

sys.path.insert(0, str(THIS_DIR))
from T01_consensus_survival import load_snapshots
from T02_combo_kupon import get_odd_for_direction, did_win


def evaluate_combo(candidates: pd.DataFrame, K: int, direction_col: str):
    """K-leg combo per matchday. Return list of weekly results."""
    candidates = candidates.sort_values("score_v13", ascending=False)
    weekly = []
    n_weeks_total = candidates["matchday"].nunique()
    for matchday, group in candidates.groupby("matchday"):
        top_k = group.head(K)
        if len(top_k) < K:
            continue
        combo_odd = 1.0
        all_won = True
        valid = True
        for _, leg in top_k.iterrows():
            d = leg.get(direction_col)
            if not d:
                valid = False; break
            o = get_odd_for_direction(leg, d)
            w = did_win(leg, d)
            if not o or o < 1.01:
                valid = False; break
            combo_odd *= o
            if not w:
                all_won = False
        if not valid:
            continue
        pnl = (combo_odd - 1) if all_won else -1
        weekly.append({"matchday": matchday, "pnl": pnl,
                       "combo_odd": combo_odd, "won": all_won})
    return weekly, n_weeks_total


def run_sweep():
    df = load_snapshots()
    df["matchday"] = pd.to_datetime(df["kickoff_iso"]).dt.normalize()
    df_settled = df[df["settled"] == 1].copy()
    n_total_weeks = df_settled["matchday"].nunique()
    print(f"Toplam settled mac: {len(df_settled)}, hafta sayisi: {n_total_weeks}")

    # Add: dir_from_fav_plus_agree → favori dir + en az 1 sinyal teyidi
    def fav_with_agreement(r):
        fav = r.get("dir_favorite")
        if not fav:
            return None
        fav_norm = {"H": "HOME", "1": "HOME", "A": "AWAY", "2": "AWAY", "D": "DRAW"}.get(fav, fav)
        sigs = [r.get("dir_model"), r.get("dir_anomaly"),
                r.get("dir_xg"), r.get("dir_form")]
        # Match normalize
        def norm(d):
            if d in ("HOME", "H", "1"): return "HOME"
            if d in ("AWAY", "A", "2"): return "AWAY"
            if d in ("DRAW", "D", "X"): return "DRAW"
            return d
        agreeing = [s for s in sigs if s and norm(s) == fav_norm]
        return fav if len(agreeing) >= 1 else None
    df_settled["dir_fav_confirmed"] = df_settled.apply(fav_with_agreement, axis=1)

    # GRID
    configs = []
    for K in [1, 2, 3]:
        for min_sig in [2, 3]:
            for min_ag in [2, 3]:
                if min_ag > min_sig:
                    continue
                configs.append({"K": K, "min_sig": min_sig, "min_ag": min_ag,
                               "dir_col": "dir_consensus", "name": f"K{K} cons sig{min_sig}/ag{min_ag}"})
        # "Favori + en az 1 teyit"
        for K2 in [1, 2, 3]:
            configs.append({"K": K2, "min_sig": 0, "min_ag": 0,
                           "dir_col": "dir_fav_confirmed",
                           "name": f"K{K2} FAV_CONFIRMED",
                           "fav_confirmed": True})
        # Just favori
        configs.append({"K": 1, "min_sig": 0, "min_ag": 0,
                       "dir_col": "dir_favorite",
                       "name": f"K1 just_FAV",
                       "fav_only": True})

    # Dedup
    seen = set()
    unique_configs = []
    for c in configs:
        key = (c["K"], c["min_sig"], c["min_ag"], c["dir_col"])
        if key in seen:
            continue
        seen.add(key)
        unique_configs.append(c)

    print(f"\nGrid: {len(unique_configs)} config\n")
    grid_results = []
    rng = np.random.RandomState(42)
    for cfg in unique_configs:
        if cfg.get("fav_confirmed"):
            cand = df_settled[df_settled["dir_fav_confirmed"].notna()].copy()
        elif cfg.get("fav_only"):
            cand = df_settled[df_settled["dir_favorite"].notna()].copy()
        else:
            cand = df_settled[
                (df_settled["signal_count"] >= cfg["min_sig"]) &
                (df_settled["agree_count"] >= cfg["min_ag"]) &
                (df_settled["dir_consensus"].notna())
            ].copy()

        weekly, _ = evaluate_combo(cand, cfg["K"], cfg["dir_col"])
        n = len(weekly)
        if n == 0:
            continue
        n_won = sum(1 for w in weekly if w["won"])
        pwr = n_won / n
        total_pnl = sum(w["pnl"] for w in weekly)
        avg_pnl = total_pnl / n
        avg_combo_odd = sum(w["combo_odd"] for w in weekly) / n
        # CI
        pnls = [w["pnl"] for w in weekly]
        boot = [rng.choice(pnls, size=n, replace=True).mean() for _ in range(1000)]
        ci_low, ci_high = float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))
        coverage = n / n_total_weeks

        grid_results.append({
            "name": cfg["name"],
            "K": cfg["K"], "min_sig": cfg["min_sig"], "min_ag": cfg["min_ag"],
            "dir_col": cfg["dir_col"],
            "n_weeks": n,
            "coverage": coverage,
            "n_won": n_won,
            "pwr": pwr,
            "avg_combo_odd": avg_combo_odd,
            "avg_pnl": avg_pnl,
            "total_pnl": total_pnl,
            "ci_low": ci_low,
            "ci_high": ci_high,
            "edge_pos": ci_low > 0,
        })

    # SORT BY (coverage > 0.30 AND avg_pnl positive AND ci_low > -0.05)
    # PRIMARY KEY: avg_pnl
    grid_results.sort(key=lambda x: (x["edge_pos"], x["coverage"] >= 0.30,
                                     x["avg_pnl"]), reverse=True)
    return grid_results, n_total_weeks


def write_report(grid: list, n_total_weeks: int):
    RAPOR_DIR.mkdir(exist_ok=True)
    p = RAPOR_DIR / "T03_mvk_sweep.md"

    rows = []
    for g in grid[:20]:
        verdict = "POZITIF" if g["edge_pos"] else ("MARJINAL" if g["avg_pnl"] > 0 else "negatif")
        rows.append(
            f"| {g['name']} | {g['n_weeks']} | {g['coverage']*100:.0f}% | "
            f"{g['pwr']*100:.1f}% | {g['avg_combo_odd']:.2f} | "
            f"{g['avg_pnl']*100:+.2f}% | "
            f"[{g['ci_low']*100:+.1f}%, {g['ci_high']*100:+.1f}%] | "
            f"{g['total_pnl']:+.1f} | {verdict} |"
        )

    md = f"""# T03 — Minimum Viable Kombin (MVK) Sweep

**Versiyon:** v1.0
**Tarih:** {datetime.now().isoformat()[:19]}
**Toplam hafta:** {n_total_weeks}

---

## Yöntem

Her config için: K-leg combo per matchday, eşikler farklı.

**Sırala:** Önce edge_pos (CI sıfır üstü), sonra coverage (en az %30), sonra avg_pnl.

---

## TOP 20 Konfig

| Strateji | n hafta | Coverage | PWR | Avg Odd | Avg PnL | CI95 | Total PnL | Verdikt |
|---|---:|---:|---:|---:|---:|---|---:|:---:|
{chr(10).join(rows)}

---

## Sonraki Adım

En iyi config (verdikt POZITIF + coverage > %30 + PWR > %50) production'a alınacak.

Picks CSV: `07_LOG_VE_RAPORLAR/T03_best_picks.csv`
"""
    p.write_text(md, encoding="utf-8")
    print(f"\nRapor: {p}")

    # CSV
    df_grid = pd.DataFrame(grid)
    df_grid.to_csv(LOGS_DIR / "T03_grid.csv", index=False)


if __name__ == "__main__":
    grid, n_total = run_sweep()
    print(f"\n{'STRATEGY':35s} {'n':>4s} {'cov%':>5s} {'PWR%':>5s} {'avgOdd':>7s} {'avgPnL%':>8s} {'CI95':>17s} {'totPnL':>8s}")
    print("-" * 100)
    for g in grid[:20]:
        verdict = "EDGE" if g["edge_pos"] else (" +" if g["avg_pnl"] > 0 else " -")
        print(f"  {g['name']:33s} {g['n_weeks']:>4d} {g['coverage']*100:>4.0f}% "
              f"{g['pwr']*100:>4.1f}% {g['avg_combo_odd']:>7.2f} "
              f"{g['avg_pnl']*100:>+7.2f}% "
              f"[{g['ci_low']*100:>+5.1f},{g['ci_high']*100:>+5.1f}] "
              f"{g['total_pnl']:>+7.1f} {verdict}")
    write_report(grid, n_total)
