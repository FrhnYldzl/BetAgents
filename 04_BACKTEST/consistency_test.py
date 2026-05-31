"""
SELECTIVE EDGE v1.2 — PROPER CONSISTENCY TEST

Önceki test (selective_backtest.py): n=45, p>0.05, hiçbir şey kanıtlanmadı.

Bu test daha sıkı:
    1. OUT-OF-SAMPLE: 2021-22 + 2022-23 sezonlari (DC modeli sadece 2023-24 gördü)
    2. TUM HAFTALAR: 3 lig × ~1000 maç = ~3000 fixture
    3. ÇOKLU STRATEJİ:
       - TOP-1, TOP-3, TOP-5, TOP-10 per matchday
       - Score thresholds (>0.85, >0.80, >0.75)
       - Decile analysis
       - Baselines: always_home_fav, always_over25, random
    4. ÇOKLU METRİK: hit%, ROI, Sharpe, bootstrap CI95, p-value, Spearman ρ
    5. DİREKSİYON: model_direction (DC'nin söylediği)

Hipotez:
    H0: SELECTIVE score, PnL ile korele DEĞİLDİR (rastgele).
    H1: Yüksek score → yüksek PnL (Spearman ρ > 0, p < 0.05).
"""
from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

THIS_DIR = Path(__file__).resolve().parent
YAZILIM = THIS_DIR.parent
RAW_DIR = YAZILIM / "02_VERI" / "raw"
MODELS_DIR = YAZILIM / "06_PRODUCTION" / "models"
sys.path.insert(0, str(YAZILIM / "03_MODELLER"))
sys.path.insert(0, str(YAZILIM / "03_MODELLER" / "selective"))

from base.dixon_coles import DCParams, score_matrix
from base.markets import prob_1x2, prob_over_under

from selective_backtest import (
    load_dc, load_week, fd_signals, evaluate_pick,
)


# ============================================================
# DATA AGGREGATION
# ============================================================

LEAGUES = ["E0", "D1", "T1"]
SEASONS = ["2122", "2223"]  # OUT-OF-SAMPLE


def load_all_oos() -> dict[str, pd.DataFrame]:
    """Tum out-of-sample fixture'lar (league + season birleştirilmiş)."""
    dfs = {}
    for lg in LEAGUES:
        for ss in SEASONS:
            try:
                df = load_week(lg, ss)
                df["league"] = lg
                df["season"] = ss
                dfs[f"{lg}_{ss}"] = df
            except FileNotFoundError:
                pass
    return dfs


def compute_signals_all(dfs: dict, verbose: bool = False) -> pd.DataFrame:
    """Tum match'ler için sinyalleri hesapla."""
    all_rows = []
    for key, df in dfs.items():
        lg = key.split("_")[0]
        params = load_dc(lg)
        if verbose:
            print(f"[{key}] {len(df)} mac, DC model: {'yuklendi' if params else 'YOK'}")
        for _, row in df.iterrows():
            sig = fd_signals(row, params)
            sig["league"] = lg
            sig["season"] = key.split("_")[1]
            sig["matchday"] = pd.Timestamp(sig["date"]).normalize()
            all_rows.append(sig)
    return pd.DataFrame(all_rows)


# ============================================================
# STRATEGIES
# ============================================================

def strategy_top_n(df: pd.DataFrame, n: int, by: str = "selection_score") -> pd.DataFrame:
    """Her matchday için en yüksek N maç."""
    picks = []
    for _, group in df.groupby("matchday"):
        chunk = group.sort_values(by, ascending=False).head(n)
        picks.append(chunk)
    return pd.concat(picks) if picks else pd.DataFrame()


def strategy_threshold(df: pd.DataFrame, threshold: float,
                       by: str = "selection_score") -> pd.DataFrame:
    return df[df[by] >= threshold]


def strategy_random_n(df: pd.DataFrame, n: int, seed: int = 42) -> pd.DataFrame:
    rng = np.random.RandomState(seed)
    picks = []
    for _, group in df.groupby("matchday"):
        if len(group) <= n:
            picks.append(group)
        else:
            idx = rng.choice(len(group), size=n, replace=False)
            picks.append(group.iloc[idx])
    return pd.concat(picks) if picks else pd.DataFrame()


# ============================================================
# EVALUATION
# ============================================================

def evaluate_picks(picks: pd.DataFrame, direction_col: str = "model_direction") -> dict:
    """
    Her pick için outcome ölç + agregate istatistik.
    direction_col: 'model_direction' veya 'signal_direction'
    """
    pnls = []
    wins = []
    odds = []
    for _, row in picks.iterrows():
        sig = row.to_dict()
        direction = sig.get(direction_col) or sig.get("signal_direction") or sig.get("model_direction")
        ev = evaluate_pick(sig, direction=direction)
        if ev["placed"]:
            pnls.append(ev["pnl"])
            wins.append(1 if ev["won"] else 0)
            odds.append(ev["odd"])

    n = len(pnls)
    if n == 0:
        return {"n": 0, "hit_rate": None, "roi": None, "sharpe": None,
                "ci_low": None, "ci_high": None, "p_value": None}

    mean_pnl = sum(pnls) / n
    var_pnl = sum((p - mean_pnl) ** 2 for p in pnls) / max(1, n - 1)
    sd_pnl = math.sqrt(var_pnl)
    # Sharpe = mean/SD per bet (bigger is better)
    sharpe_per_bet = mean_pnl / sd_pnl if sd_pnl > 0 else 0

    # Bootstrap %95 CI on ROI
    rng = np.random.RandomState(42)
    boot_means = []
    for _ in range(2000):
        sample = rng.choice(pnls, size=n, replace=True)
        boot_means.append(sample.mean())
    ci_low = float(np.percentile(boot_means, 2.5))
    ci_high = float(np.percentile(boot_means, 97.5))

    # t-test ROI > 0 (one-sided)
    se = sd_pnl / math.sqrt(n) if n > 0 else 1e-9
    t_stat = mean_pnl / se if se > 0 else 0
    # Approx p-value (one-sided, t ~ normal for n>30)
    def normal_cdf(x):
        return 0.5 * (1 + math.erf(x / math.sqrt(2)))
    p_value = 1 - normal_cdf(t_stat)

    return {
        "n": n,
        "wins": sum(wins),
        "hit_rate": sum(wins) / n,
        "roi": mean_pnl,
        "sd_pnl": sd_pnl,
        "sharpe_per_bet": sharpe_per_bet,
        "ci_low": ci_low,
        "ci_high": ci_high,
        "p_value": p_value,
        "avg_odd": sum(odds) / n if odds else 0,
        "total_pnl": sum(pnls),
    }


def baseline_always(picks: pd.DataFrame, direction: str) -> dict:
    """Her maça aynı yönde bet baseline."""
    picks2 = picks.copy()
    picks2["forced_dir"] = direction
    return evaluate_picks(picks2, direction_col="forced_dir")


def spearman_rho(x: list, y: list) -> tuple[float, float]:
    """Spearman rank correlation + p-value (approximate)."""
    n = len(x)
    if n < 5:
        return 0, 1.0
    rx = pd.Series(x).rank().tolist()
    ry = pd.Series(y).rank().tolist()
    mx = sum(rx) / n; my = sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    dx = math.sqrt(sum((a - mx) ** 2 for a in rx))
    dy = math.sqrt(sum((b - my) ** 2 for b in ry))
    rho = num / (dx * dy) if dx * dy > 0 else 0
    # Approx p-value: t = ρ × sqrt((n-2)/(1-ρ²))
    if abs(rho) < 0.9999:
        t = rho * math.sqrt((n - 2) / (1 - rho * rho))
        # one-sided p (normal approx)
        p = 1 - 0.5 * (1 + math.erf(t / math.sqrt(2)))
    else:
        p = 0
    return rho, p


# ============================================================
# MAIN
# ============================================================

def run():
    print("=" * 110)
    print("SELECTIVE EDGE v1.2 — PROPER CONSISTENCY TEST")
    print(f"  Out-of-sample sezonlar: {SEASONS}")
    print(f"  Ligler: {LEAGUES}")
    print("=" * 110)

    print("\n[1/3] Datayi yukluyor...")
    dfs = load_all_oos()
    total = sum(len(d) for d in dfs.values())
    print(f"  {len(dfs)} dosya, {total} fixture")

    print("\n[2/3] Sinyalleri hesapliyor (bu birkac dakika alabilir)...")
    sigs = compute_signals_all(dfs, verbose=True)
    print(f"  {len(sigs)} satir, {sigs['matchday'].nunique()} matchday")

    # Sadece bet edilebilir maçlar (kapanış oranı + sonuç var)
    sigs_valid = sigs[
        sigs["selection_score"].notna() &
        sigs["psc_h"].notna() &
        sigs["ftr"].notna()
    ].copy()
    print(f"  Bet edilebilir: {len(sigs_valid)} satir")

    print("\n[3/3] STRATEJI KARSILASTIRMASI")
    print("=" * 110)

    # === STRATEGY EVAL ===
    strategies = []

    # TOP-N
    for n in [1, 3, 5, 10]:
        picks = strategy_top_n(sigs_valid, n)
        ev = evaluate_picks(picks, direction_col="model_direction")
        ev["name"] = f"TOP-{n} (model_dir)"
        strategies.append(ev)

    # TOP-N anomaly_dir
    for n in [3, 5]:
        picks = strategy_top_n(sigs_valid, n)
        ev = evaluate_picks(picks, direction_col="signal_direction")
        ev["name"] = f"TOP-{n} (anom_dir)"
        strategies.append(ev)

    # Score threshold
    for thr in [0.85, 0.80, 0.75, 0.70]:
        picks = strategy_threshold(sigs_valid, thr)
        ev = evaluate_picks(picks, direction_col="model_direction")
        ev["name"] = f"score>={thr}"
        strategies.append(ev)

    # Random baseline
    for n in [3]:
        picks = strategy_random_n(sigs_valid, n)
        ev = evaluate_picks(picks, direction_col="model_direction")
        ev["name"] = f"RANDOM-{n}"
        strategies.append(ev)

    # Always-favorite (Pinnacle implied lowest odd)
    sigs_valid["fav_dir"] = sigs_valid.apply(
        lambda r: "H" if r["psc_h"] <= min(r["psc_d"] or 99, r["psc_a"] or 99)
        else ("A" if r["psc_a"] <= min(r["psc_h"] or 99, r["psc_d"] or 99) else "D"),
        axis=1
    )
    ev_fav = evaluate_picks(sigs_valid, direction_col="fav_dir")
    ev_fav["name"] = "BASELINE: hep favori"
    strategies.append(ev_fav)

    # Always Over 2.5
    sigs_valid["over_dir"] = "Over"
    ev_over = evaluate_picks(sigs_valid, direction_col="over_dir")
    ev_over["name"] = "BASELINE: hep Over 2.5"
    strategies.append(ev_over)

    # Always Under 2.5
    sigs_valid["under_dir"] = "Under"
    ev_under = evaluate_picks(sigs_valid, direction_col="under_dir")
    ev_under["name"] = "BASELINE: hep Under 2.5"
    strategies.append(ev_under)

    # === REPORT ===
    print(f"\n{'Strategy':30s} {'n':>5s} {'hit%':>6s} {'ROI%':>8s} {'CI95':>16s} "
          f"{'p':>6s} {'Sharpe':>7s} {'avg_odd':>7s}")
    print("-" * 110)
    for s in strategies:
        if s["n"] == 0:
            continue
        ci = f"[{s['ci_low']*100:+.1f},{s['ci_high']*100:+.1f}]" if s.get("ci_low") is not None else "-"
        sig_marker = " *" if s.get("p_value", 1) < 0.05 else ""
        # Highlight selective strategies
        is_baseline = s["name"].startswith("BASELINE") or "RANDOM" in s["name"]
        prefix = "  " if not is_baseline else "[B]"
        print(f"{prefix} {s['name']:27s} {s['n']:>5d} {s['hit_rate']*100:>5.1f}% "
              f"{s['roi']*100:>+7.2f}% {ci:>16s} {s['p_value']:>6.3f} "
              f"{s['sharpe_per_bet']:>7.3f} {s['avg_odd']:>7.2f}{sig_marker}")

    # === DECILE ANALYSIS ===
    print("\n" + "=" * 110)
    print("DECILE ANALYSIS — score sırasıyla 10 grup")
    print("=" * 110)
    sigs_sorted = sigs_valid.sort_values("selection_score").reset_index(drop=True)
    n = len(sigs_sorted)
    decile_results = []
    for d in range(10):
        chunk = sigs_sorted.iloc[int(d*n/10):int((d+1)*n/10)]
        ev = evaluate_picks(chunk, direction_col="model_direction")
        ev["decile"] = d + 1
        ev["avg_score"] = chunk["selection_score"].mean()
        decile_results.append(ev)

    print(f"{'D':>3s} {'n':>5s} {'avg_score':>10s} {'hit%':>6s} {'ROI%':>7s} {'CI95':>16s} {'avg_odd':>7s}")
    print("-" * 80)
    for d in decile_results:
        if d["n"] == 0:
            continue
        ci = f"[{d['ci_low']*100:+.1f},{d['ci_high']*100:+.1f}]"
        print(f"D{d['decile']:>2d} {d['n']:>5d} {d['avg_score']:>10.3f} "
              f"{d['hit_rate']*100:>5.1f}% {d['roi']*100:>+6.2f}% {ci:>16s} {d['avg_odd']:>7.2f}")

    # === CORRELATIONS ===
    print("\n" + "=" * 110)
    print("KORELASYON: selection_score <-> outcome (tum bet'ler)")
    print("=" * 110)
    pnls = []
    wons = []
    scores = []
    for _, row in sigs_valid.iterrows():
        sig = row.to_dict()
        direction = sig.get("model_direction") or sig.get("signal_direction")
        ev = evaluate_pick(sig, direction=direction)
        if ev["placed"]:
            pnls.append(ev["pnl"])
            wons.append(1 if ev["won"] else 0)
            scores.append(sig["selection_score"])
    if scores:
        # Pearson
        ms = sum(scores)/len(scores); mp = sum(pnls)/len(pnls)
        num = sum((a-ms)*(b-mp) for a,b in zip(scores,pnls))
        dx = math.sqrt(sum((a-ms)**2 for a in scores))
        dy = math.sqrt(sum((b-mp)**2 for b in pnls))
        r_p = num/(dx*dy) if dx*dy > 0 else 0
        # Spearman
        r_s, p_s = spearman_rho(scores, pnls)
        r_sw, p_sw = spearman_rho(scores, wons)
        print(f"  n={len(scores)}")
        print(f"  Pearson(score, PnL)  : {r_p:+.4f}")
        print(f"  Spearman(score, PnL) : {r_s:+.4f}  p~{p_s:.4f}  "
              f"({'ANLAMLI' if p_s<0.05 else 'anlamsiz'})")
        print(f"  Spearman(score, Won) : {r_sw:+.4f}  p~{p_sw:.4f}  "
              f"({'ANLAMLI' if p_sw<0.05 else 'anlamsiz'})")

    # === FINAL VERDICT ===
    print("\n" + "=" * 110)
    print("SONUC")
    print("=" * 110)
    top3 = next(s for s in strategies if s["name"] == "TOP-3 (model_dir)")
    rand3 = next(s for s in strategies if "RANDOM" in s["name"])
    print(f"  TOP-3 ROI       : {top3['roi']*100:+.2f}%  (p={top3['p_value']:.3f}, n={top3['n']})")
    print(f"  RANDOM-3 ROI    : {rand3['roi']*100:+.2f}%  (n={rand3['n']})")
    print(f"  Fark            : {(top3['roi']-rand3['roi'])*100:+.2f} pp")
    print(f"  Top-3 CI95      : [{top3['ci_low']*100:+.1f}, {top3['ci_high']*100:+.1f}]")
    if top3["ci_low"] > 0:
        print(f"  -> KARAR: %95 guvenle EDGE POZITIF")
    elif top3["ci_high"] < 0:
        print(f"  -> KARAR: %95 guvenle EDGE NEGATIF (bahse girme)")
    else:
        print(f"  -> KARAR: CI sifiri iceriyor → BELIRSIZ (gercek edge yok denilebilir)")


if __name__ == "__main__":
    run()
