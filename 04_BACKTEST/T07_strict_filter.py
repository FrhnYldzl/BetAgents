"""
TEST T07 — K=3 Strict Filter (>=2 Confirmers)
=============================================

ODAK: T06'da T1 K=3 +60% ROI buldu (n=103, CI tamamen pozitif).
      Filter daha sıkı yaparsak (favori + >=2 teyit) PWR ve tutarlılık artar mı?

DENEYLER:
    Min confirmers ∈ {1, 2, 3, 4}  (en az kaç sinyal favoriyi teyit etmeli)
    Ligler: ALL, T1 only, E0+T1, E0 only
    K=3

BAŞARI:
    Tutarlı CI95 sıfır üstü
    Coverage > %20 (yeterli hafta)
    PWR > Breakeven en az 5pp marj

ÇIKTI:
    - RAPOR/T07_strict_filter.md
    - 07_LOG_VE_RAPORLAR/T07_picks.csv
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
from T06_k3_crossleague import evaluate_k3_combo


def normalize_dir(d):
    if d in ("HOME", "H", "1"): return "HOME"
    if d in ("AWAY", "A", "2"): return "AWAY"
    if d in ("DRAW", "D", "X"): return "DRAW"
    return d


def fav_with_n_confirmations(row, n_min: int) -> str | None:
    """Favori yön + >=n sinyal teyit ediyorsa favori yönünü dön."""
    fav = row.get("dir_favorite")
    if not fav:
        return None
    fav_n = normalize_dir(fav)
    sigs = [row.get("dir_model"), row.get("dir_anomaly"),
            row.get("dir_xg"), row.get("dir_form")]
    agreeing = [s for s in sigs if s and normalize_dir(s) == fav_n]
    return fav if len(agreeing) >= n_min else None


def run():
    print("=" * 110)
    print("T07 — K=3 STRICT FILTER (>=N confirmers)")
    print("=" * 110)

    df = load_snapshots()
    df["matchday"] = pd.to_datetime(df["kickoff_iso"]).dt.normalize()
    df_settled = df[df["settled"] == 1].copy()

    league_combinations = [
        ("ALL", ["E0", "D1", "T1"]),
        ("T1 only", ["T1"]),
        ("E0+T1", ["E0", "T1"]),
        ("E0 only", ["E0"]),
    ]

    confirmer_levels = [1, 2, 3]

    print(f"\n{'STRATEJI':35s} {'n_conf':>6s} {'n':>4s} {'won':>4s} {'PWR':>6s} {'BE':>6s} "
          f"{'avgOdd':>7s} {'avgPnL':>8s} {'CI95':>17s} {'verdict':10s}")
    print("-" * 120)

    results = []
    for lg_name, lg_codes in league_combinations:
        for n_conf in confirmer_levels:
            # Filter
            cand = df_settled.copy()
            cand["dir_fav_confirmed"] = cand.apply(
                lambda r: fav_with_n_confirmations(r, n_conf), axis=1
            )
            cand = cand[
                cand["dir_fav_confirmed"].notna() &
                cand["league_code"].isin(lg_codes)
            ]
            if cand.empty:
                continue

            ev = evaluate_k3_combo(cand, mode="any")
            ev["name"] = f"{lg_name} (>={n_conf} confirm)"
            ev["league_filter"] = lg_name
            ev["n_confirmers_min"] = n_conf
            results.append(ev)

            if ev["n"] == 0:
                continue
            verdict = "EDGE" if ev.get("edge_pos") else (" +" if ev["avg_pnl"] > 0 else " -")
            print(f"  {ev['name']:33s} {n_conf:>6d} {ev['n']:>4d} {ev['n_won']:>4d} "
                  f"{ev['pwr']*100:>5.1f}% {ev['breakeven_pwr']*100:>5.1f}% "
                  f"{ev['avg_combo_odd']:>7.2f} {ev['avg_pnl']*100:>+7.2f}% "
                  f"[{ev['ci_low']*100:>+5.1f},{ev['ci_high']*100:>+5.1f}] {verdict}")

    # SORT & EXPORT
    results.sort(key=lambda x: (x.get("edge_pos", False), x.get("avg_pnl", 0)), reverse=True)

    # CSV
    rows = []
    for e in results:
        for w in e.get("picks", []):
            for i, leg in enumerate(w["legs"]):
                rows.append({
                    "strategy": e["name"], "matchday": w["matchday"],
                    "leg_no": i+1, "league": leg["league"], "season": leg["season"],
                    "match": leg["match"], "dir": leg["dir"], "odd": leg["odd"],
                    "won": leg["won"], "result": leg["result"],
                    "combo_odd": w["combo_odd"], "all_won": w["all_won"], "pnl": w["pnl"],
                })
    if rows:
        pd.DataFrame(rows).to_csv(LOGS_DIR / "T07_picks.csv", index=False)

    write_report(results)
    return results


def write_report(results):
    RAPOR_DIR.mkdir(exist_ok=True)
    p = RAPOR_DIR / "T07_strict_filter.md"
    rows = []
    for e in results:
        if e["n"] == 0:
            continue
        verdict = "✅ EDGE" if e.get("edge_pos") else ("➕" if e["avg_pnl"] > 0 else "➖")
        rows.append(
            f"| {e['name']} | {e['n']} | {e['n_won']} | "
            f"{e['pwr']*100:.1f}% | {e['breakeven_pwr']*100:.1f}% | "
            f"{e['avg_combo_odd']:.2f} | {e['avg_pnl']*100:+.2f}% | "
            f"[{e['ci_low']*100:+.1f}%, {e['ci_high']*100:+.1f}%] | {verdict} |"
        )

    md = f"""# T07 — K=3 Strict Filter (>=N confirmers)

**Versiyon:** v1.0
**Tarih:** {datetime.now().isoformat()[:19]}

---

## Hipotez

K=3 FAV_CONFIRMED stratejisinde **kaç sinyal favoriyi teyit etmeli?**
Sıkı filtre PWR'yi artırır mı yoksa sample küçülüp gürültü mü artar?

---

## Sonuçlar — Lig × N_confirmers

| Strateji | n | Won | PWR | Breakeven | Avg Odd | Avg PnL | CI95 | Verdikt |
|---|---:|---:|---:|---:|---:|---:|---|:---:|
{chr(10).join(rows)}

---

## Yorum

CI95 sıfır üstü olan en sıkı filtre = optimum production config.

Picks CSV: `07_LOG_VE_RAPORLAR/T07_picks.csv`
"""
    p.write_text(md, encoding="utf-8")
    print(f"\nRapor: {p}")


if __name__ == "__main__":
    run()
