"""
TEST T06 — K=3 Cross-League Validasyon
=======================================

ODAK: 3-leg kombin (klasik kupon). Ligler KARIŞABILIR (E0+T1+D1).

HİPOTEZ:
    K=3 FAV_CONFIRMED stratejisi, ligler karışık halde çalışıyor mu?
    Backtest in T03'te K=3 sadece n=338 saf E0+T1+D1'di. Tek lig kısıtı yoktu.

DENEYLER:
    A) ALL leagues (E0+D1+T1) — T03 base case
    B) E0 + T1 only (D1 hariç, T04'ten kanıtlandı)
    C) E0 + D1
    D) D1 + T1
    E) Hep aynı lig (homojen)
    F) Cross-league only (her leg farklı lig)

BAŞARI:
    PWR > breakeven (1/avg_combo_odd) tutarlı
    CI95 sıfır üstü tercih
    Coverage > %30 (yeterli hafta)

ÇIKTI:
    - RAPOR/T06_k3_crossleague.md
    - 07_LOG_VE_RAPORLAR/T06_picks.csv
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
from T04_league_validation import add_fav_confirmed


def evaluate_k3_combo(cand: pd.DataFrame, mode: str = "any") -> dict:
    """
    K=3 combo evaluator.

    mode:
      'any': her hafta top-3 score, lig kısıtı yok
      'homogenous': her hafta lig başına ayrı top-3 (yani aynı liginden 3 leg)
      'cross_only': 3 leg 3 ayrı ligden
    """
    cand = cand.sort_values("score_v13", ascending=False)
    weekly = []

    for matchday, group in cand.groupby("matchday"):
        legs_chosen = []

        if mode == "any":
            top = group.head(3)
            if len(top) < 3:
                continue
            legs_chosen = list(top.iterrows())

        elif mode == "homogenous":
            # Her lig için en yüksek 3 leg AYNI ligten
            for lg, sub in group.groupby("league_code"):
                top3 = sub.head(3)
                if len(top3) == 3:
                    legs_chosen = list(top3.iterrows())
                    break  # ilk uygun lig kullanılır
            if not legs_chosen:
                continue

        elif mode == "cross_only":
            # Her ligten en yüksek 1, en az 3 farklı lig olmalı
            picks = []
            seen_leagues = set()
            for _, row in group.iterrows():
                lg = row["league_code"]
                if lg in seen_leagues:
                    continue
                picks.append((None, row))
                seen_leagues.add(lg)
                if len(picks) == 3:
                    break
            if len(picks) < 3:
                continue
            legs_chosen = picks

        # Combo PnL hesabı
        combo_odd = 1.0
        all_won = True
        valid = True
        leg_data = []
        for _, leg in legs_chosen:
            d = leg.get("dir_fav_confirmed")
            if not d:
                valid = False; break
            o = get_odd_for_direction(leg, d)
            w = did_win(leg, d)
            if not o or o < 1.01:
                valid = False; break
            combo_odd *= o
            if not w:
                all_won = False
            leg_data.append({
                "match": f"{leg['home_team']} vs {leg['away_team']}",
                "league": leg["league_code"], "season": leg["season"],
                "dir": d, "odd": o, "won": w,
                "result": leg.get("result_1x2"),
                "score": leg["score_v13"],
            })
        if not valid:
            continue

        pnl = (combo_odd - 1) if all_won else -1
        weekly.append({
            "matchday": matchday, "K": 3, "combo_odd": combo_odd,
            "all_won": all_won, "pnl": pnl,
            "legs": leg_data,
        })

    if not weekly:
        return {"n": 0}

    n = len(weekly)
    n_won = sum(1 for w in weekly if w["all_won"])
    pnls = [w["pnl"] for w in weekly]
    rng = np.random.RandomState(42)
    boot = [rng.choice(pnls, size=n, replace=True).mean() for _ in range(2000)]
    ci_low, ci_high = float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))
    avg_combo_odd = sum(w["combo_odd"] for w in weekly) / n
    return {
        "n": n,
        "n_won": n_won,
        "pwr": n_won / n,
        "avg_combo_odd": avg_combo_odd,
        "breakeven_pwr": 1.0 / avg_combo_odd,
        "avg_pnl": sum(pnls) / n,
        "total_pnl": sum(pnls),
        "ci_low": ci_low,
        "ci_high": ci_high,
        "edge_pos": ci_low > 0,
        "picks": weekly,
    }


def run():
    print("=" * 100)
    print("T06 — K=3 CROSS-LEAGUE VALIDASYON")
    print("=" * 100)

    df = load_snapshots()
    df["matchday"] = pd.to_datetime(df["kickoff_iso"]).dt.normalize()
    df_settled = df[df["settled"] == 1].copy()
    df_settled = add_fav_confirmed(df_settled)
    cand_all = df_settled[df_settled["dir_fav_confirmed"].notna()].copy()

    print(f"Toplam FAV_CONFIRMED maç: {len(cand_all)}")
    n_total_weeks = df_settled["matchday"].nunique()
    print(f"Toplam matchday: {n_total_weeks}\n")

    experiments = []

    # A) ALL leagues
    ev = evaluate_k3_combo(cand_all, mode="any")
    ev["name"] = "A) ALL leagues (E0+D1+T1)"
    ev["league_filter"] = "E0+D1+T1"
    experiments.append(ev)

    # B) E0 + T1 only (T04 winners)
    ev = evaluate_k3_combo(
        cand_all[cand_all["league_code"].isin(["E0", "T1"])], mode="any"
    )
    ev["name"] = "B) E0 + T1 only"
    ev["league_filter"] = "E0+T1"
    experiments.append(ev)

    # C) E0 + D1
    ev = evaluate_k3_combo(
        cand_all[cand_all["league_code"].isin(["E0", "D1"])], mode="any"
    )
    ev["name"] = "C) E0 + D1"
    ev["league_filter"] = "E0+D1"
    experiments.append(ev)

    # D) D1 + T1
    ev = evaluate_k3_combo(
        cand_all[cand_all["league_code"].isin(["D1", "T1"])], mode="any"
    )
    ev["name"] = "D) D1 + T1"
    ev["league_filter"] = "D1+T1"
    experiments.append(ev)

    # E) Cross-only — 3 ayrı lig
    ev = evaluate_k3_combo(cand_all, mode="cross_only")
    ev["name"] = "E) CROSS-ONLY (3 ayrı lig)"
    ev["league_filter"] = "cross_only"
    experiments.append(ev)

    # F) Homogenous — aynı lig
    ev = evaluate_k3_combo(cand_all, mode="homogenous")
    ev["name"] = "F) HOMOGENOUS (aynı lig 3 leg)"
    ev["league_filter"] = "homogenous"
    experiments.append(ev)

    # Lig-tek tek
    for lg in ["E0", "D1", "T1"]:
        ev = evaluate_k3_combo(cand_all[cand_all["league_code"] == lg], mode="any")
        ev["name"] = f"Z) Sadece {lg}"
        ev["league_filter"] = lg
        experiments.append(ev)

    # PRINT
    print(f"{'STRATEJI':38s} {'n':>4s} {'won':>4s} {'PWR':>6s} {'BE':>6s} {'avgOdd':>7s} {'avgPnL':>8s} {'CI95':>17s} {'verdict':10s}")
    print("-" * 110)
    for e in experiments:
        if e["n"] == 0:
            continue
        verdict = "EDGE" if e.get("edge_pos") else (" +" if e["avg_pnl"] > 0 else " -")
        print(f"  {e['name']:36s} {e['n']:>4d} {e['n_won']:>4d} {e['pwr']*100:>5.1f}% "
              f"{e['breakeven_pwr']*100:>5.1f}% {e['avg_combo_odd']:>7.2f} "
              f"{e['avg_pnl']*100:>+7.2f}% "
              f"[{e['ci_low']*100:>+5.1f},{e['ci_high']*100:>+5.1f}] {verdict}")

    # CSV
    rows = []
    for e in experiments:
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
        pd.DataFrame(rows).to_csv(LOGS_DIR / "T06_picks.csv", index=False)

    # MARKDOWN
    write_report(experiments)
    return experiments


def write_report(experiments):
    RAPOR_DIR.mkdir(exist_ok=True)
    p = RAPOR_DIR / "T06_k3_crossleague.md"
    rows = []
    for e in experiments:
        if e["n"] == 0:
            continue
        verdict = "✅ EDGE" if e.get("edge_pos") else ("➕ marjinal" if e["avg_pnl"] > 0 else "➖ negatif")
        rows.append(
            f"| {e['name']} | {e['n']} | {e['n_won']} | "
            f"{e['pwr']*100:.1f}% | {e['breakeven_pwr']*100:.1f}% | "
            f"{e['avg_combo_odd']:.2f} | {e['avg_pnl']*100:+.2f}% | "
            f"[{e['ci_low']*100:+.1f}%, {e['ci_high']*100:+.1f}%] | {verdict} |"
        )

    md = f"""# T06 — K=3 Cross-League Validasyon

**Versiyon:** v1.0
**Tarih:** {datetime.now().isoformat()[:19]}

---

## Hipotez

K=3 FAV_CONFIRMED stratejisi, ligler karışık halde çalışıyor mu?
Lig kombinasyonları ve cross-only modu test edildi.

---

## Sonuçlar — K=3 farklı lig kombinasyonları

| Strateji | n | Won | PWR | Breakeven | Avg Odd | Avg PnL | CI95 | Verdikt |
|---|---:|---:|---:|---:|---:|---:|---|:---:|
{chr(10).join(rows)}

---

## Yorum

PWR > Breakeven & CI95 sıfır üstü olan strateji = production-ready.

CSV: `07_LOG_VE_RAPORLAR/T06_picks.csv`
"""
    p.write_text(md, encoding="utf-8")
    print(f"\nRapor: {p}")


if __name__ == "__main__":
    run()
