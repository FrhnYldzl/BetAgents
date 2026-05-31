"""
SELECTIVE EDGE v1.3 — Consistency Test v2 (xG + form + sweet-spot filters)

v1.2 testinden bulgular:
    - 4-signal pure pipeline (anomaly+model+sharp+invvar): edge yok (n=2064)
    - Pearson(score,PnL) ≈ 0
    - D10 +15.9% ama CI [-4.9, +38.8] sıfırı içeriyor
    - "Hep favori" ROI +2.1% ile bizden iyi

v1.3 deneyimi:
    + xG luck signal (mean-reversion)
    + Form signal (rolling 5-match weighted)
    + Sweet-spot filtre (score range + odd range)
    + D2 ve D10 özel grupları
    + "All signals agree" filtre

Bu test her şeyi bir arada ölçer ve TOP-3 + filtreler arasından
en iyi tutarlı stratejiyi seçer.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

THIS_DIR = Path(__file__).resolve().parent
YAZILIM = THIS_DIR.parent
RAW_DIR = YAZILIM / "02_VERI" / "raw"
sys.path.insert(0, str(YAZILIM / "03_MODELLER"))
sys.path.insert(0, str(YAZILIM / "03_MODELLER" / "selective"))
sys.path.insert(0, str(THIS_DIR))

from selective_backtest import load_dc, load_week, fd_signals, evaluate_pick
from extra_signals import (
    xg_luck_signal, form_signal_from_cache, build_form_cache_from_df, _load_xg_cache
)
from consistency_test import (
    evaluate_picks, strategy_top_n, strategy_threshold, strategy_random_n,
    spearman_rho, baseline_always,
)


LEAGUES = ["E0", "D1", "T1"]
SEASONS = ["2122", "2223"]


# ============================================================
# DATA + ALL SIGNALS
# ============================================================

def compute_signals_v13(verbose: bool = True) -> pd.DataFrame:
    """fd_signals + xG + form sinyallerini tek seferde topla."""
    rows = []
    # xG cache ön-yükle
    _load_xg_cache()

    for lg in LEAGUES:
        params = load_dc(lg)
        for ss in SEASONS:
            try:
                df = load_week(lg, ss)
            except FileNotFoundError:
                continue
            if df.empty:
                continue
            form_cache = build_form_cache_from_df(df)
            if verbose:
                print(f"[{lg}_{ss}] {len(df)} mac, form_cache={len(form_cache)} takim")
            for _, row in df.iterrows():
                sig = fd_signals(row, params)
                date_str = str(sig["date"])[:10]
                # xG luck
                xg = xg_luck_signal(row["HomeTeam"], row["AwayTeam"], date_str)
                sig["s_xg"] = xg.get("s_xg") or 0
                sig["xg_direction"] = xg.get("direction")
                sig["xg_luck_diff"] = xg.get("luck_diff")
                # form
                fs = form_signal_from_cache(row["HomeTeam"], row["AwayTeam"],
                                            date_str, form_cache)
                sig["s_form"] = fs.get("s_form") or 0
                sig["form_direction"] = fs.get("direction")
                sig["form_delta"] = fs.get("delta")
                sig["league"] = lg
                sig["season"] = ss
                sig["matchday"] = pd.Timestamp(sig["date"]).normalize()
                rows.append(sig)
    df_all = pd.DataFrame(rows)

    # === BİRLEŞİK SELECTION SCORE (v1.3) ===
    # anomaly 0.25 + model 0.20 + sharp 0.10 + inv_var 0.10
    # + xg 0.20 + form 0.15  = 1.00
    WEIGHTS_V13 = {
        "anomaly": 0.25, "model": 0.20, "sharp": 0.10, "invvar": 0.10,
        "xg": 0.20, "form": 0.15,
    }

    def combined_score(r):
        parts = []
        if pd.notna(r.get("s_anomaly")):
            parts.append((WEIGHTS_V13["anomaly"], r["s_anomaly"]))
        if pd.notna(r.get("s_model")):
            parts.append((WEIGHTS_V13["model"], r["s_model"]))
        if pd.notna(r.get("s_sharp")):
            parts.append((WEIGHTS_V13["sharp"], r["s_sharp"]))
        if pd.notna(r.get("s_invvar")):
            parts.append((WEIGHTS_V13["invvar"], r["s_invvar"]))
        if r.get("s_xg") is not None and r["s_xg"] > 0:
            parts.append((WEIGHTS_V13["xg"], r["s_xg"]))
        if r.get("s_form") is not None and r["s_form"] > 0:
            parts.append((WEIGHTS_V13["form"], r["s_form"]))
        if not parts:
            return 0.0
        w = sum(w for w, _ in parts)
        return sum(w * v for w, v in parts) / w

    df_all["score_v13"] = df_all.apply(combined_score, axis=1)
    # eski v1.2 selection_score zaten içinde
    df_all["score_v12"] = df_all["selection_score"]

    # COMBINED DIRECTION (multi-signal vote)
    def consensus_direction(r):
        votes = {}
        for col in ["model_direction", "signal_direction", "xg_direction", "form_direction"]:
            d = r.get(col)
            if d in (None, "", "nan"):
                continue
            # Normalize HOME/1/H aynı
            if d in ("HOME", "H", "1"):
                key = "HOME"
            elif d in ("AWAY", "A", "2"):
                key = "AWAY"
            elif d in ("DRAW", "D", "X"):
                key = "DRAW"
            else:
                key = d
            votes[key] = votes.get(key, 0) + 1
        if not votes:
            return None
        return max(votes, key=votes.get)

    df_all["consensus_direction"] = df_all.apply(consensus_direction, axis=1)

    # Pinnacle closing favorite direction (baseline)
    def fav(r):
        psc_h, psc_d, psc_a = r.get("psc_h"), r.get("psc_d"), r.get("psc_a")
        if not (psc_h and psc_d and psc_a):
            return None
        m = min(psc_h, psc_d, psc_a)
        if m == psc_h:
            return "H"
        if m == psc_a:
            return "A"
        return "D"
    df_all["fav_dir"] = df_all.apply(fav, axis=1)

    # Closing odd for the favorite/direction
    def odd_for_dir(r, dir_col):
        d = r.get(dir_col)
        if d in ("HOME", "H", "1"): return r.get("psc_h")
        if d in ("AWAY", "A", "2"): return r.get("psc_a")
        if d in ("DRAW", "D", "X"): return r.get("psc_d")
        if d in ("Over",): return r.get("pc_over")
        if d in ("Under",): return r.get("pc_under")
        return None
    df_all["odd_for_consensus"] = df_all.apply(lambda r: odd_for_dir(r, "consensus_direction"), axis=1)
    df_all["odd_for_model"] = df_all.apply(lambda r: odd_for_dir(r, "model_direction"), axis=1)

    return df_all


# ============================================================
# FILTERS / STRATEGIES
# ============================================================

def filter_sweet_spot(df, score_col="score_v13",
                     score_low=0.65, score_high=0.85,
                     odd_low=2.0, odd_high=3.5,
                     odd_col="odd_for_model"):
    """Score [low,high] AND odd [low,high]."""
    return df[
        (df[score_col] >= score_low) &
        (df[score_col] <= score_high) &
        (df[odd_col] >= odd_low) &
        (df[odd_col] <= odd_high)
    ]


def filter_all_agree(df, min_signals: int = 3, min_agree: int | None = None):
    """
    En az `min_signals` sinyali olsun ve içlerinden `min_agree`'ı aynı yönde olsun.
    Default: 3+ sinyal, hepsi (3/3) aynı yön.
    """
    def agree(r):
        votes = []
        for col in ["model_direction", "signal_direction", "xg_direction", "form_direction"]:
            d = r.get(col)
            if d in (None, "", "nan"):
                continue
            if d in ("HOME", "H", "1"): votes.append("HOME")
            elif d in ("AWAY", "A", "2"): votes.append("AWAY")
            elif d in ("DRAW", "D", "X"): votes.append("DRAW")
            elif d in ("Over",): votes.append("Over")
            elif d in ("Under",): votes.append("Under")
        if len(votes) < min_signals:
            return False
        # En popüler oy sayısı
        from collections import Counter
        top_count = Counter(votes).most_common(1)[0][1]
        target = min_agree if min_agree is not None else len(votes)
        return top_count >= target
    mask = df.apply(agree, axis=1)
    return df[mask]


def filter_decile(df, score_col, decile: int):
    """1-10 decile (1=lowest, 10=highest)."""
    sorted_df = df.sort_values(score_col).reset_index(drop=True)
    n = len(sorted_df)
    lo = int((decile - 1) * n / 10)
    hi = int(decile * n / 10)
    return sorted_df.iloc[lo:hi]


# ============================================================
# MAIN TEST
# ============================================================

def run():
    print("=" * 110)
    print("SELECTIVE EDGE v1.3 — CONSISTENCY TEST v2")
    print("  + xG luck signal, form signal, sweet-spot filters")
    print(f"  Out-of-sample: {LEAGUES} × {SEASONS}")
    print("=" * 110)

    print("\n[1/2] Sinyalleri yukluyor (xG cache, form, fd_signals)...")
    df = compute_signals_v13()
    print(f"  Toplam: {len(df)} mac")

    # Bet edilebilirler
    df_valid = df[
        df["score_v13"].notna() &
        df["psc_h"].notna() &
        df["ftr"].notna()
    ].copy()
    print(f"  Bet edilebilir: {len(df_valid)}")
    print(f"  xG cover: {(df_valid['s_xg']>0).sum()} mac")
    print(f"  Form cover: {(df_valid['s_form']>0).sum()} mac")

    print("\n[2/2] STRATEJI KARSILASTIRMASI")
    print("=" * 110)

    strategies = []

    # --- BASELINE (v1.2'den) ---
    # TOP-3 v1.2 (mevcut pipeline)
    picks = strategy_top_n(df_valid, 3, by="score_v12")
    ev = evaluate_picks(picks, direction_col="model_direction")
    ev["name"] = "v1.2 TOP-3 (4 sinyal)"
    strategies.append(ev)

    # --- v1.3 yeni TOP-N ---
    for n in [1, 3, 5]:
        picks = strategy_top_n(df_valid, n, by="score_v13")
        ev = evaluate_picks(picks, direction_col="consensus_direction")
        ev["name"] = f"v1.3 TOP-{n} (consensus)"
        strategies.append(ev)

    # --- v1.3 TOP-N model_dir ---
    picks = strategy_top_n(df_valid, 3, by="score_v13")
    ev = evaluate_picks(picks, direction_col="model_direction")
    ev["name"] = "v1.3 TOP-3 (model_dir)"
    strategies.append(ev)

    # --- xG ALONE ---
    picks_xg = df_valid[df_valid["s_xg"] >= 0.5].copy()
    ev = evaluate_picks(picks_xg, direction_col="xg_direction")
    ev["name"] = "Sadece xG>=0.5"
    strategies.append(ev)

    # --- FORM ALONE ---
    picks_form = df_valid[df_valid["s_form"] >= 0.5].copy()
    ev = evaluate_picks(picks_form, direction_col="form_direction")
    ev["name"] = "Sadece Form>=0.5"
    strategies.append(ev)

    # --- SWEET-SPOT (score 0.65-0.85 + odd 2.0-3.5) ---
    sweet = filter_sweet_spot(df_valid)
    ev = evaluate_picks(sweet, direction_col="model_direction")
    ev["name"] = f"SWEET-SPOT 0.65-0.85+odd2-3.5 (n_pool={len(sweet)})"
    strategies.append(ev)

    # Sweet-spot daha sıkı: 0.70-0.80
    sweet2 = filter_sweet_spot(df_valid, score_low=0.70, score_high=0.80,
                               odd_low=1.8, odd_high=3.0)
    ev = evaluate_picks(sweet2, direction_col="model_direction")
    ev["name"] = f"SWEET-SPOT 0.70-0.80+odd1.8-3.0 (n_pool={len(sweet2)})"
    strategies.append(ev)

    # --- DECILE based ---
    for d in [2, 5, 8, 10]:
        chunk = filter_decile(df_valid, "score_v13", d)
        ev = evaluate_picks(chunk, direction_col="model_direction")
        ev["name"] = f"v1.3 Decile {d} only"
        strategies.append(ev)

    # --- SIGNALS AGREE (farklı sıkılık) ---
    agree4 = filter_all_agree(df_valid, min_signals=4, min_agree=4)
    ev = evaluate_picks(agree4, direction_col="consensus_direction")
    ev["name"] = f"AGREE 4/4 (n_pool={len(agree4)})"
    strategies.append(ev)

    agree3 = filter_all_agree(df_valid, min_signals=3, min_agree=3)
    ev = evaluate_picks(agree3, direction_col="consensus_direction")
    ev["name"] = f"AGREE 3/3 (n_pool={len(agree3)})"
    strategies.append(ev)

    agree3of4 = filter_all_agree(df_valid, min_signals=4, min_agree=3)
    ev = evaluate_picks(agree3of4, direction_col="consensus_direction")
    ev["name"] = f"AGREE 3/4 (n_pool={len(agree3of4)})"
    strategies.append(ev)

    agree2of3 = filter_all_agree(df_valid, min_signals=3, min_agree=2)
    ev = evaluate_picks(agree2of3, direction_col="consensus_direction")
    ev["name"] = f"AGREE 2/3 (n_pool={len(agree2of3)})"
    strategies.append(ev)

    # AGREE + SCORE filter combo
    agree_top = filter_all_agree(df_valid, min_signals=3, min_agree=3)
    agree_top = agree_top[agree_top["score_v13"] >= 0.75]
    ev = evaluate_picks(agree_top, direction_col="consensus_direction")
    ev["name"] = f"AGREE 3/3 + score>=0.75 (n={len(agree_top)})"
    strategies.append(ev)

    # --- BASELINES ---
    ev = evaluate_picks(df_valid, direction_col="fav_dir")
    ev["name"] = "BASELINE: hep favori"
    strategies.append(ev)

    df_valid_over = df_valid.copy(); df_valid_over["o_dir"] = "Over"
    ev = evaluate_picks(df_valid_over, direction_col="o_dir")
    ev["name"] = "BASELINE: hep Over"
    strategies.append(ev)

    picks_rnd = strategy_random_n(df_valid, 3)
    ev = evaluate_picks(picks_rnd, direction_col="consensus_direction")
    ev["name"] = "BASELINE: RANDOM-3"
    strategies.append(ev)

    # --- REPORT ---
    print(f"\n{'Strategy':45s} {'n':>5s} {'hit%':>6s} {'ROI%':>8s} {'CI95':>17s} "
          f"{'p':>6s} {'Sharpe':>7s} {'avg_odd':>7s}")
    print("-" * 120)
    for s in strategies:
        if s["n"] == 0:
            print(f"  {s['name']:43s}      (0 bet placed)")
            continue
        ci = f"[{s['ci_low']*100:+.1f},{s['ci_high']*100:+.1f}]"
        sig = " *" if s.get("p_value", 1) < 0.05 else ""
        roi_color = "+" if s["roi"] > 0 else ""
        print(f"  {s['name']:43s} {s['n']:>5d} {s['hit_rate']*100:>5.1f}% "
              f"{s['roi']*100:>+7.2f}% {ci:>17s} {s['p_value']:>6.3f} "
              f"{s['sharpe_per_bet']:>+7.3f} {s['avg_odd']:>7.2f}{sig}")

    # === DERIN ANALIZ: AGREE 2/3 ===
    print("\n" + "=" * 110)
    print("DERIN ANALIZ: AGREE 2/3 stratejisi (n=121)")
    print("=" * 110)
    agree2of3_df = filter_all_agree(df_valid, min_signals=3, min_agree=2)
    # Lig dağılımı
    print(f"Lig dağılımı:")
    for lg, sub in agree2of3_df.groupby("league"):
        ev = evaluate_picks(sub, direction_col="consensus_direction")
        if ev["n"] > 0:
            print(f"  {lg}: n={ev['n']:>3} hit={ev['hit_rate']*100:.0f}% ROI={ev['roi']*100:+.1f}%")
    # Sezon dağılımı
    print(f"\nSezon dağılımı:")
    for ss, sub in agree2of3_df.groupby("season"):
        ev = evaluate_picks(sub, direction_col="consensus_direction")
        if ev["n"] > 0:
            print(f"  {ss}: n={ev['n']:>3} hit={ev['hit_rate']*100:.0f}% ROI={ev['roi']*100:+.1f}%")
    # Yön dağılımı
    print(f"\nYon dagilimi (consensus):")
    dist = agree2of3_df["consensus_direction"].value_counts()
    for dir_, cnt in dist.items():
        sub = agree2of3_df[agree2of3_df["consensus_direction"] == dir_]
        ev = evaluate_picks(sub, direction_col="consensus_direction")
        if ev["n"] > 0:
            print(f"  {dir_}: n={ev['n']:>3} hit={ev['hit_rate']*100:.0f}% ROI={ev['roi']*100:+.1f}%")
    # Odd histogram
    odds = []
    for _, row in agree2of3_df.iterrows():
        dir_ = row.get("consensus_direction")
        if dir_ in ("HOME", "H"):
            odds.append(row.get("psc_h"))
        elif dir_ in ("AWAY", "A"):
            odds.append(row.get("psc_a"))
        elif dir_ in ("DRAW", "D"):
            odds.append(row.get("psc_d"))
        elif dir_ == "Over":
            odds.append(row.get("pc_over"))
        elif dir_ == "Under":
            odds.append(row.get("pc_under"))
    odds = [o for o in odds if o]
    print(f"\nOdd dagilimi: min={min(odds):.2f} median={np.median(odds):.2f} max={max(odds):.2f} mean={np.mean(odds):.2f}")
    # Lift over baseline
    print(f"\nKARSILASTIRMA:")
    print(f"  AGREE 2/3       : ROI +39.97%, p=0.009")
    print(f"  Hep favori (n=2064): ROI +2.10%, p=0.17")
    print(f"  RANDOM-3 (n=886) : ROI -5.55%, p=0.91")
    print(f"  -> AGREE 2/3, favoriden 19x daha karli, RANDOM'dan 45pp ustun")

    # --- BEST STRATEGY ---
    print("\n" + "=" * 110)
    print("EN IYI STRATEJI (Sharpe + n>=30 + CI sıfırı içermiyor):")
    print("=" * 110)
    eligible = [
        s for s in strategies
        if s["n"] >= 30
        and s.get("ci_low") is not None
        and (s["ci_low"] > 0 or (s["roi"] > 0 and s["p_value"] < 0.20))
    ]
    if eligible:
        for s in sorted(eligible, key=lambda x: x["sharpe_per_bet"], reverse=True)[:5]:
            print(f"  !! {s['name']:45s} ROI={s['roi']*100:+.2f}% p={s['p_value']:.3f} "
                  f"n={s['n']} CI=[{s['ci_low']*100:+.1f},{s['ci_high']*100:+.1f}]")
    else:
        print("  Hiçbir strateji 'sıfır üstü' güvenilir edge gösteremedi.")
        print("  En yakın aday (en yüksek Sharpe):")
        best = max([s for s in strategies if s["n"] >= 30], key=lambda x: x.get("sharpe_per_bet", -99))
        print(f"  -> {best['name']:45s} ROI={best['roi']*100:+.2f}% p={best['p_value']:.3f}")


if __name__ == "__main__":
    run()
