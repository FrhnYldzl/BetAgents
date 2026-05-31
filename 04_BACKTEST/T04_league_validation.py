"""
TEST T04 — Lig-bazlı Konsensüs Validasyon
==========================================

ODAK: T03 winner (K2 FAV_CONFIRMED) hangi liglerde tutarlı çalışıyor?

YÖNTEM:
    K2 FAV_CONFIRMED stratejisi:
        - Her lig için ayrı çalıştır
        - Her sezon × lig için PWR, ROI, edge_pos
    K1 FAV_CONFIRMED için aynısı (kontrol)

HEDEF: Hangi liglerde GÜVENLE production'a alabiliriz?

ÇIKTI:
    - RAPOR/T04_league_validation.md
    - 07_LOG_VE_RAPORLAR/T04_league_breakdown.csv
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
from T01_consensus_survival import load_snapshots
from T02_combo_kupon import get_odd_for_direction, did_win
from T03_mvk_sweep import evaluate_combo


def add_fav_confirmed(df: pd.DataFrame) -> pd.DataFrame:
    """dir_fav_confirmed sütununu ekle."""
    def fav_with_agreement(r):
        fav = r.get("dir_favorite")
        if not fav:
            return None
        fav_norm = {"H": "HOME", "1": "HOME", "A": "AWAY", "2": "AWAY", "D": "DRAW"}.get(fav, fav)
        sigs = [r.get("dir_model"), r.get("dir_anomaly"),
                r.get("dir_xg"), r.get("dir_form")]
        def norm(d):
            if d in ("HOME", "H", "1"): return "HOME"
            if d in ("AWAY", "A", "2"): return "AWAY"
            if d in ("DRAW", "D", "X"): return "DRAW"
            return d
        agreeing = [s for s in sigs if s and norm(s) == fav_norm]
        return fav if len(agreeing) >= 1 else None
    df["dir_fav_confirmed"] = df.apply(fav_with_agreement, axis=1)
    return df


def eval_strategy(cand: pd.DataFrame, K: int) -> dict:
    """K-leg combo per matchday."""
    weekly, _ = evaluate_combo(cand, K, "dir_fav_confirmed")
    n = len(weekly)
    if n == 0:
        return {"n": 0}
    pnls = [w["pnl"] for w in weekly]
    n_won = sum(1 for w in weekly if w["won"])
    pwr = n_won / n
    avg_pnl = sum(pnls) / n
    avg_odd = sum(w["combo_odd"] for w in weekly) / n
    rng = np.random.RandomState(42)
    boot = [rng.choice(pnls, size=n, replace=True).mean() for _ in range(1000)]
    ci_low, ci_high = float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))
    return {
        "n": n, "n_won": n_won, "pwr": pwr,
        "avg_pnl": avg_pnl, "avg_odd": avg_odd,
        "ci_low": ci_low, "ci_high": ci_high,
        "total_pnl": sum(pnls),
        "edge_pos": ci_low > 0,
    }


def run():
    print("=" * 90)
    print("T04 — LIG-BAZLI VALIDASYON (K2 FAV_CONFIRMED + K1 FAV_CONFIRMED)")
    print("=" * 90)

    df = load_snapshots()
    df["matchday"] = pd.to_datetime(df["kickoff_iso"]).dt.normalize()
    df_settled = df[df["settled"] == 1].copy()
    df_settled = add_fav_confirmed(df_settled)
    cand = df_settled[df_settled["dir_fav_confirmed"].notna()].copy()

    rows = []
    # 1. OVERALL
    for K in [1, 2]:
        ev = eval_strategy(cand, K)
        ev["league"] = "ALL"; ev["season"] = "ALL"; ev["K"] = K
        rows.append(ev)

    # 2. PER LEAGUE
    for lg in sorted(cand["league_code"].unique()):
        sub = cand[cand["league_code"] == lg]
        for K in [1, 2]:
            ev = eval_strategy(sub, K)
            ev["league"] = lg; ev["season"] = "ALL"; ev["K"] = K
            rows.append(ev)

    # 3. PER LEAGUE × SEASON
    for lg in sorted(cand["league_code"].unique()):
        for ss in sorted(cand["season"].unique()):
            sub = cand[(cand["league_code"] == lg) & (cand["season"] == ss)]
            for K in [1, 2]:
                ev = eval_strategy(sub, K)
                if ev["n"] == 0:
                    continue
                ev["league"] = lg; ev["season"] = ss; ev["K"] = K
                rows.append(ev)

    df_out = pd.DataFrame(rows)
    df_out.to_csv(LOGS_DIR / "T04_league_breakdown.csv", index=False)

    # PRINT
    print(f"\n{'lig':6s} {'sezon':6s} {'K':>3s} {'n':>4s} {'PWR%':>5s} {'avgOdd':>7s} {'avgPnL%':>8s} {'CI95':>17s} {'verdict':10s}")
    print("-" * 90)
    for r in rows:
        if r["n"] == 0:
            continue
        verdict = "EDGE" if r.get("edge_pos") else (" + " if r["avg_pnl"] > 0 else " - ")
        print(f"  {r['league']:5s} {r['season']:5s} {r['K']:>3d} {r['n']:>4d} "
              f"{r['pwr']*100:>4.1f}% {r['avg_odd']:>7.2f} "
              f"{r['avg_pnl']*100:>+7.2f}% "
              f"[{r['ci_low']*100:>+5.1f},{r['ci_high']*100:>+5.1f}] {verdict}")

    # MARKDOWN REPORT
    write_report(rows)
    return rows


def write_report(rows):
    RAPOR_DIR.mkdir(exist_ok=True)
    p = RAPOR_DIR / "T04_league_validation.md"

    # ALL üzerinden
    overall_k1 = next((r for r in rows if r["league"]=="ALL" and r["K"]==1), None)
    overall_k2 = next((r for r in rows if r["league"]=="ALL" and r["K"]==2), None)

    # Per league özet
    league_lines = []
    for lg in ["E0", "D1", "T1"]:
        for K in [1, 2]:
            r = next((x for x in rows if x["league"]==lg and x["season"]=="ALL" and x["K"]==K), None)
            if r:
                edge_marker = "✅" if r.get("edge_pos") else ("➕" if r["avg_pnl"] > 0 else "➖")
                league_lines.append(
                    f"| {lg} | K{K} | {r['n']} | {r['pwr']*100:.1f}% | "
                    f"{r['avg_odd']:.2f} | {r['avg_pnl']*100:+.2f}% | "
                    f"[{r['ci_low']*100:+.1f}%, {r['ci_high']*100:+.1f}%] | {edge_marker} |"
                )

    # Per season
    season_lines = []
    for lg in ["E0", "D1", "T1"]:
        for ss in ["2122", "2223", "2324", "2425"]:
            r = next((x for x in rows if x["league"]==lg and x["season"]==ss and x["K"]==2), None)
            if r:
                edge_marker = "✅" if r.get("edge_pos") else ("➕" if r["avg_pnl"] > 0 else "➖")
                season_lines.append(
                    f"| {lg} | {ss} | {r['n']} | {r['pwr']*100:.1f}% | "
                    f"{r['avg_pnl']*100:+.2f}% | {edge_marker} |"
                )

    md = f"""# T04 — Lig-bazlı Konsensüs Validasyon

**Versiyon:** v1.0
**Tarih:** {datetime.now().isoformat()[:19]}
**Strateji:** FAV_CONFIRMED (favori + ≥1 sinyal teyit)

---

## Genel Sonuç (4 sezon × 3 lig)

| K | n hafta | PWR | Avg Odd | Avg PnL | CI95 | Verdikt |
|---|---:|---:|---:|---:|---|:---:|
| K1 | {overall_k1['n']} | {overall_k1['pwr']*100:.1f}% | {overall_k1['avg_odd']:.2f} | {overall_k1['avg_pnl']*100:+.2f}% | [{overall_k1['ci_low']*100:+.1f}%, {overall_k1['ci_high']*100:+.1f}%] | {'✅ EDGE' if overall_k1.get('edge_pos') else '➕ marjinal'} |
| K2 | {overall_k2['n']} | {overall_k2['pwr']*100:.1f}% | {overall_k2['avg_odd']:.2f} | {overall_k2['avg_pnl']*100:+.2f}% | [{overall_k2['ci_low']*100:+.1f}%, {overall_k2['ci_high']*100:+.1f}%] | {'✅ EDGE' if overall_k2.get('edge_pos') else '➕ marjinal'} |

## Lig Bazlı (4 sezon birlikte)

| Lig | K | n | PWR | Avg Odd | Avg PnL | CI95 | Edge |
|---|---|---:|---:|---:|---:|---|:---:|
{chr(10).join(league_lines)}

## Lig × Sezon (K=2)

| Lig | Sezon | n | PWR | Avg PnL | Edge |
|---|---|---:|---:|---:|:---:|
{chr(10).join(season_lines)}

---

## Yorum

Strateji tutarlı çalışan ligler **production'a alınacak**.

CSV: `07_LOG_VE_RAPORLAR/T04_league_breakdown.csv`
"""
    p.write_text(md, encoding="utf-8")
    print(f"\nRapor: {p}")


if __name__ == "__main__":
    run()
