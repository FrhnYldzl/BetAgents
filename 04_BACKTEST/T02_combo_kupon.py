"""
TEST T02 — Combo Kupon Konsensüs
=================================

ODAK: User vizyonu = "haftanın 1 kombini" (3-leg kupon klasik).

HİPOTEZ:
    Her hafta için konsensüs adaylarından (sig>=3, agree>=2) en yüksek score'lu
    K maçı seç → K-leg combo. Tüm leg'ler tutarsa kazanç.

DEĞİŞKEN: K ∈ {2, 3, 4}

BAŞARI:
    Combo breakeven hit rate = 1 / (avg_odd^K)
    K=2 @ odd 1.97 → ~25.8% hit rate yeterli
    K=3 @ odd 1.97 → ~13.1% hit rate yeterli
    Hedef: PWR_combo > %30 (3-leg için yeterli, 2-leg için kolay)

ÇIKTI:
    - RAPOR/T02_combo_kupon.md
    - 07_LOG_VE_RAPORLAR/T02_picks.csv
"""
from __future__ import annotations

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
from T01_consensus_survival import load_snapshots, compute_pnl


def get_odd_for_direction(row, direction: str):
    """Direction için odd."""
    if direction in ("HOME", "H", "1"): return row.get("odd_1")
    if direction in ("AWAY", "A", "2"): return row.get("odd_2")
    if direction in ("DRAW", "D", "X"): return row.get("odd_X")
    if direction == "Over": return row.get("odd_over25")
    if direction == "Under": return row.get("odd_under25")
    return None


def did_win(row, direction: str) -> bool:
    ftr = row.get("result_1x2")
    tg = row.get("total_goals")
    if direction in ("HOME", "H", "1"): return ftr == "H"
    if direction in ("AWAY", "A", "2"): return ftr == "A"
    if direction in ("DRAW", "D", "X"): return ftr == "D"
    if direction == "Over": return tg is not None and tg > 2.5
    if direction == "Under": return tg is not None and tg < 2.5
    return False


def run_combo_test(K: int, min_signals: int = 3, min_agree: int = 2) -> dict:
    print(f"\n--- COMBO K={K} (sig>={min_signals}, agree>={min_agree}) ---")
    df = load_snapshots()
    df["matchday"] = pd.to_datetime(df["kickoff_iso"]).dt.normalize()

    candidates = df[
        (df["signal_count"] >= min_signals) &
        (df["agree_count"] >= min_agree) &
        (df["dir_consensus"].notna()) &
        (df["settled"] == 1)
    ].copy()

    # Per matchday: en yüksek K score
    candidates = candidates.sort_values("score_v13", ascending=False)
    combos = []
    weeks = []
    weekly_pnl = []
    weekly_won = []

    for matchday, group in candidates.groupby("matchday"):
        top_k = group.head(K)
        if len(top_k) < K:
            continue
        # Combo PnL
        legs = []
        all_won = True
        combo_odd = 1.0
        for _, leg in top_k.iterrows():
            d = leg["dir_consensus"]
            o = get_odd_for_direction(leg, d)
            w = did_win(leg, d)
            if not o or o < 1.01:
                all_won = None
                break
            combo_odd *= o
            if not w:
                all_won = False
            legs.append({
                "match": f"{leg['home_team']} vs {leg['away_team']}",
                "dir": d, "odd": o, "won": w,
                "result": leg.get("result_1x2"),
            })
        if all_won is None:
            continue
        # PnL: combo (stake=1, kazanırsa combine_odd - 1, kaybederse -1)
        pnl = (combo_odd - 1) if all_won else -1
        combos.append({
            "matchday": matchday,
            "K": K,
            "combo_odd": combo_odd,
            "all_won": all_won,
            "pnl": pnl,
            "legs": legs,
        })
        weeks.append(matchday)
        weekly_pnl.append(pnl)
        weekly_won.append(all_won)

    if not combos:
        return {"K": K, "n_weeks": 0}

    n = len(combos)
    n_won = sum(1 for w in weekly_won if w)
    pwr = n_won / n
    total_pnl = sum(weekly_pnl)
    avg_pnl = total_pnl / n
    avg_combo_odd = sum(c["combo_odd"] for c in combos) / n
    breakeven_hr = 1.0 / avg_combo_odd

    # Bootstrap CI
    rng = np.random.RandomState(42)
    boot = [rng.choice(weekly_pnl, size=n, replace=True).mean()
            for _ in range(2000)]
    ci_low, ci_high = float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))

    return {
        "K": K,
        "n_weeks": n,
        "n_won": n_won,
        "pwr": pwr,
        "avg_combo_odd": avg_combo_odd,
        "breakeven_hit_rate": breakeven_hr,
        "total_pnl": total_pnl,
        "avg_pnl_per_week": avg_pnl,
        "ci_low": ci_low,
        "ci_high": ci_high,
        "combos": combos,
        "edge_positive": ci_low > 0,
    }


def write_report(results: dict):
    RAPOR_DIR.mkdir(exist_ok=True)
    p = RAPOR_DIR / "T02_combo_kupon.md"
    md_rows = []
    for K in [2, 3, 4]:
        r = results.get(K)
        if not r or r.get("n_weeks", 0) == 0:
            continue
        verdict = "✅ POZITIF" if r.get("edge_positive") else "⚠️ BELİRSİZ"
        md_rows.append(
            f"| **{K}** | {r['n_weeks']} | {r['n_won']} | "
            f"{r['pwr']*100:.1f}% | {r['breakeven_hit_rate']*100:.1f}% | "
            f"{r['avg_combo_odd']:.2f} | "
            f"{r['avg_pnl_per_week']*100:+.2f}% | "
            f"[{r['ci_low']*100:+.1f}%, {r['ci_high']*100:+.1f}%] | "
            f"{r['total_pnl']:+.2f} | {verdict} |"
        )
    md_table = "\n".join(md_rows)
    md = f"""# T02 — Combo Kupon Konsensüs

**Versiyon:** v1.0
**Tarih:** {datetime.now().isoformat()[:19]}

---

## Hipotez

Her hafta konsensüs maçlardan en yüksek score'lu K'sını seç → K-leg combo kuponu.
Tüm leg'ler tutarsa kazanırız.

**Başarı:** PWR > 1/avg_combo_odd^K (breakeven üzerinde olan tutarlı oran)

---

## Sonuçlar — K ∈ {{2, 3, 4}}

| K | n hafta | Won | **PWR** | Breakeven | Avg Odd | Avg PnL/hafta | CI95 | Tot PnL | Verdikt |
|---|---:|---:|---:|---:|---:|---:|---|---:|:---:|
{md_table}

---

## Yorum

- K=2 combo: kombinli oran düşük (~3-4) → kolayca breakeven üstü olabilir
- K=3 combo: oran ~7-10 → daha az hafta kazanır ama oran yüksek
- K=4 combo: oran ~20+ → çok riskli ama büyük getiri

**En tutarlı PWR**: hangi K?

Picks CSV: `07_LOG_VE_RAPORLAR/T02_picks.csv`
"""
    p.write_text(md, encoding="utf-8")
    print(f"\nRapor: {p}")

    # CSV'ye combo legler
    rows = []
    for K, r in results.items():
        for c in r.get("combos", []):
            for i, leg in enumerate(c["legs"]):
                rows.append({
                    "K": K, "matchday": c["matchday"], "leg_no": i+1,
                    "match": leg["match"], "dir": leg["dir"],
                    "odd": leg["odd"], "won": leg["won"], "result": leg["result"],
                    "combo_odd": c["combo_odd"], "all_won": c["all_won"], "pnl": c["pnl"],
                })
    if rows:
        df_out = pd.DataFrame(rows)
        df_out.to_csv(LOGS_DIR / "T02_picks.csv", index=False)


if __name__ == "__main__":
    results = {}
    for K in [2, 3, 4]:
        results[K] = run_combo_test(K)

    print("\n" + "=" * 80)
    print("T02 SONUÇ ÖZETİ")
    print("=" * 80)
    print(f"{'K':>3s} {'n':>5s} {'won':>4s} {'PWR':>5s} {'breakeven':>10s} {'avg_odd':>8s} {'tot_pnl':>9s} {'verdict':10s}")
    for K, r in results.items():
        if r.get("n_weeks", 0) == 0:
            continue
        print(f"{K:>3d} {r['n_weeks']:>5d} {r['n_won']:>4d} {r['pwr']*100:>4.1f}% "
              f"{r['breakeven_hit_rate']*100:>9.1f}% {r['avg_combo_odd']:>8.2f} "
              f"{r['total_pnl']:>+8.2f}  {'POZITIF' if r.get('edge_positive') else 'belirsiz':10s}")
    write_report(results)
