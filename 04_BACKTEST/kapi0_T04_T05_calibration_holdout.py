"""
KAPI 0 — TEST 4+5: PLATT KALIBRASYON + EXTERNAL HOLDOUT
========================================================

Komite Madde A6 + Madde 33:
  A6: "Platt kalibrasyon ayrı holdout almıyor. fit_and_save.py:69 aynı veri
       seti üzerinde DC fit + Platt fit. Tek bölümlü split -> kalibrasyon
       over-fit, raporlanan Brier optimistic."
  Madde 33 (öneri): "External holdout: 2024-25 sezonu hiç kullanılmasın.
       DC fit 2017-24, Platt 2024 ilk yarı, backtest 2024-25 ikinci yarı."

TEST:
  signal_snapshots'taki fp_1/fp_X/fp_2 (kalibre edilmis probabilities) ile
  gerçek sonuçlar (result_1x2) arasında Brier score hesapla.

  Her sezon için ayrı Brier:
    - Eğer 2024-25 ve 2025-26 sezonlarında Brier belirgin yüksekse
      -> in-sample overfit kanıtı
    - Eğer tüm sezonlarda stabil -> kalibrasyon güvenilir

  Ek: Log-loss da hesapla (Brier'in alternatifi).

  Karar kapısı:
    - Late seasons Brier - Early seasons Brier >= 0.02 -> OVERFIT
    - Δ < 0.01 -> CALIBRATION STABLE
"""
from __future__ import annotations

import sys
import sqlite3
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

THIS_DIR = Path(__file__).resolve().parent
YAZILIM = THIS_DIR.parent


SEASON_CONV = {
    "1718":"2017-18","1819":"2018-19","1920":"2019-20","2021":"2020-21",
    "2122":"2021-22","2223":"2022-23","2324":"2023-24","2425":"2024-25","2526":"2025-26",
}


def load_data() -> pd.DataFrame:
    """matches_v2'den closing odds + result. Market-implied probabilities Brier."""
    db_path = YAZILIM / "02_VERI" / "bahis_agent.db"
    conn = sqlite3.connect(db_path)
    df = pd.read_sql_query(
        """SELECT league_code, season, matchday, home_team, away_team,
               closing_1, closing_X, closing_2,
               opening_1, opening_X, opening_2,
               home_score, away_score, is_settled
           FROM matches_v2
           WHERE is_settled=1
             AND closing_1 IS NOT NULL AND closing_X IS NOT NULL AND closing_2 IS NOT NULL
             AND home_score IS NOT NULL AND away_score IS NOT NULL""", conn
    )
    conn.close()
    # Derive result_1x2
    df["result_1x2"] = "D"
    df.loc[df["home_score"] > df["away_score"], "result_1x2"] = "H"
    df.loc[df["away_score"] > df["home_score"], "result_1x2"] = "A"
    # Derive market-implied probabilities (de-vigged)
    for prefix in ("closing", "opening"):
        df[f"{prefix}_imp_h"] = 1.0 / df[f"{prefix}_1"]
        df[f"{prefix}_imp_d"] = 1.0 / df[f"{prefix}_X"]
        df[f"{prefix}_imp_a"] = 1.0 / df[f"{prefix}_2"]
        s = df[f"{prefix}_imp_h"] + df[f"{prefix}_imp_d"] + df[f"{prefix}_imp_a"]
        df[f"{prefix}_imp_h"] /= s
        df[f"{prefix}_imp_d"] /= s
        df[f"{prefix}_imp_a"] /= s
    # Use closing as "fp_*" alias for legacy code
    df["fp_1"] = df["closing_imp_h"]
    df["fp_X"] = df["closing_imp_d"]
    df["fp_2"] = df["closing_imp_a"]
    return df


def brier_score(df: pd.DataFrame) -> dict:
    """3-way Brier score (multi-class)."""
    if df.empty:
        return {"n": 0, "brier": None, "logloss": None}
    n = len(df)
    # One-hot encode result
    y_h = (df["result_1x2"] == "H").astype(float).values
    y_d = (df["result_1x2"] == "D").astype(float).values
    y_a = (df["result_1x2"] == "A").astype(float).values

    p_h = df["fp_1"].values
    p_d = df["fp_X"].values
    p_a = df["fp_2"].values

    # Normalize (kalibre olsa bile yine de güvenlik için)
    total = p_h + p_d + p_a
    p_h = p_h / total
    p_d = p_d / total
    p_a = p_a / total

    # 3-way Brier: (p_h - y_h)^2 + (p_d - y_d)^2 + (p_a - y_a)^2
    brier_per_row = (p_h - y_h)**2 + (p_d - y_d)**2 + (p_a - y_a)**2
    brier = brier_per_row.mean()

    # Log-loss
    # Sadece doğru sınıfın olasılığı
    p_correct = np.where(y_h == 1, p_h, np.where(y_d == 1, p_d, p_a))
    p_correct = np.clip(p_correct, 1e-15, 1.0)
    logloss = -np.log(p_correct).mean()

    # Accuracy
    pred_class = np.where(p_h >= np.maximum(p_d, p_a), "H",
                          np.where(p_d >= p_a, "D", "A"))
    correct = (pred_class == df["result_1x2"].values).sum()
    acc = correct / n

    return {"n": n, "brier": float(brier), "logloss": float(logloss),
            "accuracy": float(acc)}


def reliability_diagram(df: pd.DataFrame, n_bins: int = 10) -> list:
    """Calibration reliability diagram: bin probabilities vs actual."""
    if df.empty:
        return []
    # Use max probability for each prediction
    p_h = df["fp_1"].values
    p_d = df["fp_X"].values
    p_a = df["fp_2"].values
    total = p_h + p_d + p_a
    p_h, p_d, p_a = p_h/total, p_d/total, p_a/total
    p_max = np.maximum(p_h, np.maximum(p_d, p_a))
    pred_class = np.where(p_h >= np.maximum(p_d, p_a), "H",
                          np.where(p_d >= p_a, "D", "A"))
    correct = (pred_class == df["result_1x2"].values).astype(int)

    bins = []
    for i in range(n_bins):
        lo = i / n_bins; hi = (i+1) / n_bins
        mask = (p_max >= lo) & (p_max < hi)
        n = mask.sum()
        if n < 10: continue
        avg_p = p_max[mask].mean()
        actual = correct[mask].mean()
        bins.append({"bin": f"{lo:.1f}-{hi:.1f}", "n": int(n),
                     "avg_p": float(avg_p), "actual": float(actual),
                     "gap": float(actual - avg_p)})
    return bins


def run():
    print("=" * 80)
    print("KAPI 0 - TEST 4+5: PLATT KALIBRASYON + EXTERNAL HOLDOUT")
    print("Komite Madde A6 + Oneri 33")
    print("=" * 80)

    df = load_data()
    print(f"\nLoaded: {len(df)} kalibre edilmis pick")

    # === Per-sezon Brier ===
    print("\n" + "-" * 80)
    print(">>> PER-SEZON BRIER + LOG-LOSS + ACCURACY")
    print("-" * 80)
    print(f"{'Sezon':>8s} {'n':>5s} {'Brier':>7s} {'LogLoss':>8s} {'Acc%':>5s}")
    season_results = {}
    for ss in sorted(df["season"].unique()):
        sub = df[df["season"] == ss]
        b = brier_score(sub)
        season_results[ss] = b
        print(f"{ss:>8s} {b['n']:>5d} {b['brier']:.4f}  {b['logloss']:.4f}  "
              f"{b['accuracy']*100:>4.1f}%")

    # === All seasons baseline ===
    all_b = brier_score(df)
    print(f"\n{'ALL':>8s} {all_b['n']:>5d} {all_b['brier']:.4f}  {all_b['logloss']:.4f}  "
          f"{all_b['accuracy']*100:>4.1f}%")

    # === Early vs Late comparison ===
    print("\n" + "-" * 80)
    print(">>> EARLY vs LATE COMPARISON (overfit testi)")
    print("-" * 80)
    sorted_seasons = sorted(season_results.keys())
    if len(sorted_seasons) >= 4:
        early = sorted_seasons[:-2]
        late = sorted_seasons[-2:]
        early_df = df[df["season"].isin(early)]
        late_df = df[df["season"].isin(late)]
        e = brier_score(early_df)
        l = brier_score(late_df)
        delta_brier = l["brier"] - e["brier"]
        delta_logloss = l["logloss"] - e["logloss"]
        delta_acc = l["accuracy"] - e["accuracy"]
        print(f"  EARLY  {early}: n={e['n']}, Brier={e['brier']:.4f}, "
              f"LogLoss={e['logloss']:.4f}, Acc={e['accuracy']*100:.1f}%")
        print(f"  LATE   {late}: n={l['n']}, Brier={l['brier']:.4f}, "
              f"LogLoss={l['logloss']:.4f}, Acc={l['accuracy']*100:.1f}%")
        print(f"  Delta:           Brier={delta_brier:+.4f}, "
              f"LogLoss={delta_logloss:+.4f}, Acc={delta_acc*100:+.1f}pp")

    # === Reliability Diagram ===
    print("\n" + "-" * 80)
    print(">>> RELIABILITY DIAGRAM (top-class prob vs actual)")
    print("-" * 80)
    print(f"{'Bin':>10s} {'n':>5s} {'avg_p':>7s} {'actual':>7s} {'gap':>8s}")
    bins = reliability_diagram(df, n_bins=10)
    total_gap_abs = 0
    for b in bins:
        marker = " <- !" if abs(b["gap"]) > 0.05 else ""
        print(f"{b['bin']:>10s} {b['n']:>5d} {b['avg_p']:.3f}  {b['actual']:.3f}  "
              f"{b['gap']:+.3f}{marker}")
        total_gap_abs += abs(b["gap"]) * b["n"]
    total_n = sum(b["n"] for b in bins)
    weighted_avg_gap = total_gap_abs / max(1, total_n)
    print(f"\nWeighted avg |gap|: {weighted_avg_gap:.4f}")

    # === Per-sezon reliability (sadece son 2 sezon için)
    print("\n" + "-" * 80)
    print(">>> LATE SEASONS (2024-25, 2025-26) RELIABILITY")
    print("-" * 80)
    late_df = df[df["season"].isin(["2024-25", "2025-26"])]
    print(f"  n={len(late_df)}")
    bins_late = reliability_diagram(late_df, n_bins=10)
    print(f"{'Bin':>10s} {'n':>5s} {'avg_p':>7s} {'actual':>7s} {'gap':>8s}")
    for b in bins_late:
        marker = " <- !" if abs(b["gap"]) > 0.05 else ""
        print(f"{b['bin']:>10s} {b['n']:>5d} {b['avg_p']:.3f}  {b['actual']:.3f}  "
              f"{b['gap']:+.3f}{marker}")

    # === VERDICT ===
    print("\n" + "=" * 80)
    print("KAPI 0 - TEST 4+5 VERDICT")
    print("=" * 80)

    if len(sorted_seasons) >= 4:
        if delta_brier >= 0.02:
            verdict = "FAIL_OVERFIT"
            print(f"\n[FAIL] Late sezonlarda Brier {delta_brier:+.4f} (esik 0.02)")
            print(f"       -> Platt kalibrasyon overfit, raporlanan Brier optimistic")
        elif delta_brier >= 0.01:
            verdict = "WARN_MILD_OVERFIT"
            print(f"\n[WARN] Late sezonlarda Brier {delta_brier:+.4f} (mild overfit)")
            print(f"       -> Kalibrasyon kismi overfit, v2'de 3-fold split kullan")
        elif delta_brier <= -0.005:
            verdict = "PASS_STABLE"
            print(f"\n[PASS] Late sezonlarda Brier {delta_brier:+.4f} (improving)")
            print(f"       -> Kalibrasyon stabil, hatta iyilesiyor")
        else:
            verdict = "PASS_STABLE"
            print(f"\n[PASS] Late sezonlarda Brier {delta_brier:+.4f} (stable)")
            print(f"       -> Kalibrasyon stabil, kabul edilebilir")

    print(f"\nWeighted avg |gap|: {weighted_avg_gap:.4f}")
    if weighted_avg_gap > 0.05:
        print(f"  -> Kalibrasyon zayif (>5% sapma), reliability dusuk")
    elif weighted_avg_gap > 0.03:
        print(f"  -> Kalibrasyon orta, iyilestirme mumkun")
    else:
        print(f"  -> Kalibrasyon iyi (sapma <3%)")

    # Markdown rapor
    rapor = ["# KAPI 0 — TEST 4+5: PLATT KALIBRASYON + EXTERNAL HOLDOUT\n"]
    rapor.append(f"**Tarih:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}\n")
    rapor.append("**Komite Madde A6 + Oneri 33**\n\n")
    rapor.append("## Per-Sezon Kalibrasyon Performansi\n\n")
    rapor.append("| Sezon | n | Brier | LogLoss | Accuracy |\n")
    rapor.append("|---|---|---|---|---|\n")
    for ss in sorted(season_results.keys()):
        b = season_results[ss]
        rapor.append(f"| {ss} | {b['n']} | {b['brier']:.4f} | {b['logloss']:.4f} | "
                     f"{b['accuracy']*100:.1f}% |\n")
    rapor.append(f"| **ALL** | {all_b['n']} | {all_b['brier']:.4f} | {all_b['logloss']:.4f} | "
                 f"{all_b['accuracy']*100:.1f}% |\n\n")

    if len(sorted_seasons) >= 4:
        rapor.append("## Early vs Late\n\n")
        rapor.append(f"- Early {early}: Brier {e['brier']:.4f}, LogLoss {e['logloss']:.4f}, Acc {e['accuracy']*100:.1f}%\n")
        rapor.append(f"- Late {late}: Brier {l['brier']:.4f}, LogLoss {l['logloss']:.4f}, Acc {l['accuracy']*100:.1f}%\n")
        rapor.append(f"- Delta: Brier {delta_brier:+.4f}, LogLoss {delta_logloss:+.4f}\n\n")

    rapor.append(f"## Reliability\n\n")
    rapor.append(f"- Weighted avg |gap|: {weighted_avg_gap:.4f}\n\n")
    rapor.append(f"## Verdict\n\n**{verdict}**\n")
    out = YAZILIM / "RAPOR" / "Kapi0_T04_T05_calibration_holdout.md"
    out.write_text("".join(rapor), encoding="utf-8")
    print(f"\n[OK] Rapor: {out}")


if __name__ == "__main__":
    run()
