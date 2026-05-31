"""
CLV (Closing Line Value) TEST

Hipotez:
    Gerçek edge varsa, B365 opening odds'da alınan pick PINNACLE closing'de
    daha kötü oran gösterecek (oran düştü = sharp money seguio).

    CLV = (opening_odd / closing_odd) - 1
    Positive CLV = sharp confirmation (uzun vadeli +EV göstergesi)
    Negative CLV = sharp money tersine gitti

Bu test:
    1. Her strateji için CLV ortalaması ve dağılımı
    2. CLV > 0 ratio (% bet'lerin uygun yönde hareket etti)
    3. ROI vs CLV korelasyonu
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS_DIR))

from consistency_test_v2 import (
    compute_signals_v13, filter_all_agree, filter_decile, strategy_top_n,
)
import consistency_test_v2


def compute_clv_for_row(row, direction: str) -> dict:
    """
    direction: "HOME"/"AWAY"/"DRAW"/"Over"/"Under"
    Returns: {opening_odd, closing_odd, clv_pct, sharp_confirmed}
    """
    # Direction → opening + closing column
    if direction in ("HOME", "H", "1"):
        opening = row.get("B365H_open") or row.get("B365H")  # B365 opening
        closing = row.get("psc_h")  # Pinnacle closing
    elif direction in ("AWAY", "A", "2"):
        opening = row.get("B365A_open") or row.get("B365A")
        closing = row.get("psc_a")
    elif direction in ("DRAW", "D", "X"):
        opening = row.get("B365D_open") or row.get("B365D")
        closing = row.get("psc_d")
    elif direction == "Over":
        opening = row.get("B365Over_open") or row.get("B365>2.5")
        closing = row.get("pc_over")
    elif direction == "Under":
        opening = row.get("B365Under_open") or row.get("B365<2.5")
        closing = row.get("pc_under")
    else:
        return {"opening_odd": None, "closing_odd": None, "clv_pct": None,
                "sharp_confirmed": None}

    if not opening or not closing or opening <= 1.01 or closing <= 1.01:
        return {"opening_odd": opening, "closing_odd": closing,
                "clv_pct": None, "sharp_confirmed": None}

    # CLV: opening / closing - 1 (yüksek opening = kötü, oran düştü = pick için iyi)
    clv = opening / closing - 1.0
    return {
        "opening_odd": opening,
        "closing_odd": closing,
        "clv_pct": clv * 100,
        "sharp_confirmed": clv > 0,
    }


def evaluate_with_clv(picks: pd.DataFrame, direction_col: str = "fav_dir") -> dict:
    """Pick'ler için ROI + CLV birlikte."""
    clvs = []
    confirmed = []
    for _, row in picks.iterrows():
        d = row.get(direction_col)
        if not d:
            continue
        clv = compute_clv_for_row(row, d)
        if clv["clv_pct"] is not None:
            clvs.append(clv["clv_pct"])
            confirmed.append(1 if clv["sharp_confirmed"] else 0)
    if not clvs:
        return {"n_clv": 0, "mean_clv": None, "median_clv": None,
                "pct_positive_clv": None}
    return {
        "n_clv": len(clvs),
        "mean_clv": np.mean(clvs),
        "median_clv": np.median(clvs),
        "std_clv": np.std(clvs),
        "pct_positive_clv": sum(confirmed) / len(confirmed) * 100,
    }


def run():
    print("=" * 110)
    print("CLV TEST — Opening (B365) vs Closing (Pinnacle)")
    print("=" * 110)

    # 4 sezon birlikte
    consistency_test_v2.SEASONS = ["2122", "2223", "2324", "2425"]
    consistency_test_v2.LEAGUES = ["E0", "D1", "T1"]

    print("\n[1/2] Sinyaller hesaplaniyor...")
    df = compute_signals_v13(verbose=False)
    df_valid = df[
        df["psc_h"].notna() &
        df["ftr"].notna()
    ].copy()
    print(f"Toplam: {len(df_valid)} mac")

    # Sinyal-direction lookup (compute_signals_v13'te yapıldı)
    # B365 opening odd direkt CSV'den fd_signals içinde geliyor
    # ama bu test için ekstra rebuild gerek

    # B365 columns'u tekrar Football-Data'dan çek - opening
    # fd_signals zaten psc_*, pc_* (closing) çekiyor; B365 opening fields'i ekleyelim
    # Trick: load_week zaten df olarak getiriyor B365 ile birlikte

    from selective_backtest import load_week, fd_signals, load_dc
    rows = []
    for lg in consistency_test_v2.LEAGUES:
        params = load_dc(lg)
        for ss in consistency_test_v2.SEASONS:
            try:
                df_raw = load_week(lg, ss)
            except FileNotFoundError:
                continue
            for _, row in df_raw.iterrows():
                sig = fd_signals(row, params)
                # B365 opening fields
                sig["B365H"] = row.get("B365H")
                sig["B365D"] = row.get("B365D")
                sig["B365A"] = row.get("B365A")
                sig["B365>2.5"] = row.get("B365>2.5")
                sig["B365<2.5"] = row.get("B365<2.5")
                sig["league"] = lg
                sig["season"] = ss
                rows.append(sig)
    df_full = pd.DataFrame(rows)

    # Favori direction
    def fav(r):
        psc_h, psc_d, psc_a = r.get("psc_h"), r.get("psc_d"), r.get("psc_a")
        if not (psc_h and psc_d and psc_a):
            return None
        m = min(psc_h, psc_d, psc_a)
        if m == psc_h: return "H"
        if m == psc_a: return "A"
        return "D"
    df_full["fav_dir"] = df_full.apply(fav, axis=1)

    print(f"Bet edilebilir + tum odd'lar: {df_full[df_full['fav_dir'].notna()].shape[0]}")

    print("\n[2/2] CLV ANALIZ")
    print("=" * 110)

    strategies = []

    # Hep favori
    sub = df_full[df_full["fav_dir"].notna()]
    clv = evaluate_with_clv(sub, "fav_dir")
    clv["name"] = "Hep favori"
    strategies.append(clv)

    # Favori - lig bazlı
    for lg in ["E0", "D1", "T1"]:
        sub = df_full[(df_full["league"] == lg) & (df_full["fav_dir"].notna())]
        clv = evaluate_with_clv(sub, "fav_dir")
        clv["name"] = f"Hep favori ({lg})"
        strategies.append(clv)

    # Favori - sezon bazlı
    for ss in ["2122", "2223", "2324", "2425"]:
        sub = df_full[(df_full["season"] == ss) & (df_full["fav_dir"].notna())]
        clv = evaluate_with_clv(sub, "fav_dir")
        clv["name"] = f"Hep favori ({ss})"
        strategies.append(clv)

    # Hep Over
    sub_o = df_full[df_full["pc_over"].notna()].copy()
    sub_o["o_dir"] = "Over"
    clv = evaluate_with_clv(sub_o, "o_dir")
    clv["name"] = "Hep Over 2.5"
    strategies.append(clv)

    # Hep Under
    sub_u = df_full[df_full["pc_under"].notna()].copy()
    sub_u["u_dir"] = "Under"
    clv = evaluate_with_clv(sub_u, "u_dir")
    clv["name"] = "Hep Under 2.5"
    strategies.append(clv)

    print(f"\n{'Strategy':30s} {'n_clv':>6s} {'mean_clv%':>10s} {'median%':>9s} {'%pos_clv':>9s}")
    print("-" * 75)
    for s in strategies:
        if s["n_clv"] == 0:
            continue
        # %pos>50 → strateji ortalama sharp money tarafında
        pos_marker = " *" if s["pct_positive_clv"] > 55 else ""
        print(f"  {s['name']:28s} {s['n_clv']:>6d} "
              f"{s['mean_clv']:>+9.2f}% {s['median_clv']:>+8.2f}% "
              f"{s['pct_positive_clv']:>8.1f}%{pos_marker}")

    # === YORUM ===
    print("\n" + "=" * 110)
    print("YORUM:")
    print("=" * 110)
    fav_all = next(s for s in strategies if s["name"] == "Hep favori")
    if fav_all["mean_clv"] > 0:
        print(f"  Hep favori CLV ortalama: {fav_all['mean_clv']:+.2f}%")
        print(f"  -> POZITIF CLV: B365 opening favori oranlari Pinnacle closing'den HIGH.")
        print(f"     Yani opening'de favoriye girersek, sharp money zamanla bizim yonumuze geliyor.")
        print(f"     Bu, '+2.3% ROI' bulgusunun gercek edge oldugunun ek kaniti.")
    else:
        print(f"  Hep favori CLV ortalama: {fav_all['mean_clv']:+.2f}%")
        print(f"  -> NEGATIF CLV: opening'de favori oranlari Pinnacle closing'den DUSUK.")
        print(f"     Bu, hep favori ROI'sinin gurultu olabilecegini gosterir.")


if __name__ == "__main__":
    run()
