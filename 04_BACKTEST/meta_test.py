"""
SELECTIVE EDGE v1.4 — META TEST (her iki sezonda da tutarlı stratejileri test)

Replikasyon başarısız olunca dürüst yaklaşım: HANGİ STRATEJİ HER İKİ SEZONDA
DA pozitif kaldı?

Ön bulgu:
    xG alone:    +11.4% (2223) → +8.3%  (2425) ✓ TUTARLI POZITIF
    Hep favori:  +2.1%  (2223) → +3.0%  (2425) ✓ TUTARLI POZITIF
    AGREE 2/3:   +40%   (2223) → -4.3%  (2425) ✗ TUTARSIZ
    TOP-3:       -3.1%  (2223) → +2.5%  (2425) ✗ TUTARSIZ

Bu test:
    1. Stratejiyi 2122 + 2223 + 2324 + 2425 (4 sezon!) birleşik ile test et
    2. Tutarlı + n>=200 olanları belirle
    3. Yeni kombinasyon: "Favori yön + xG agree" hipotezi
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS_DIR))

from consistency_test_v2 import (
    compute_signals_v13, filter_all_agree, filter_sweet_spot, filter_decile,
    strategy_top_n, evaluate_picks,
)
import consistency_test_v2


def run():
    print("=" * 110)
    print("META TEST — 4 SEZON BIRLESIK (2021-22 + 2022-23 + 2023-24 + 2024-25)")
    print("=" * 110)

    consistency_test_v2.SEASONS = ["2122", "2223", "2324", "2425"]
    consistency_test_v2.LEAGUES = ["E0", "D1", "T1"]

    print("\n[1/3] 4 sezon birlikte yukleniyor...")
    df = compute_signals_v13(verbose=True)
    print(f"Toplam: {len(df)} mac, {df['season'].value_counts().to_dict()}")

    df_valid = df[
        df["score_v13"].notna() &
        df["psc_h"].notna() &
        df["ftr"].notna()
    ].copy()

    # xG agree with favori
    def xg_agrees_with_fav(r):
        if not r.get("xg_direction") or not r.get("fav_dir"):
            return False
        fav = r["fav_dir"]
        xg = r["xg_direction"]
        # Match (HOME/H/1, AWAY/A/2)
        fav_norm = {"H": "HOME", "1": "HOME", "A": "AWAY", "2": "AWAY", "D": "DRAW"}.get(fav, fav)
        return fav_norm == xg
    df_valid["xg_fav_agree"] = df_valid.apply(xg_agrees_with_fav, axis=1)

    # Model agree with favori
    def model_agrees_with_fav(r):
        m = r.get("model_direction")
        f = r.get("fav_dir")
        if not m or not f:
            return False
        m_norm = {"1": "HOME", "H": "HOME", "2": "AWAY", "A": "AWAY", "X": "DRAW", "D": "DRAW"}.get(m, m)
        f_norm = {"H": "HOME", "1": "HOME", "A": "AWAY", "2": "AWAY", "D": "DRAW"}.get(f, f)
        return m_norm == f_norm
    df_valid["model_fav_agree"] = df_valid.apply(model_agrees_with_fav, axis=1)

    print("\n[2/3] STRATEJI TEST (4 sezon birlikte)")
    print("=" * 110)

    strategies = []

    # Baseline favori
    ev = evaluate_picks(df_valid, direction_col="fav_dir")
    ev["name"] = "Hep favori (tum)"
    strategies.append(ev)

    # Favori + xG agree
    sub = df_valid[df_valid["xg_fav_agree"]]
    ev = evaluate_picks(sub, direction_col="fav_dir")
    ev["name"] = "Favori + xG agree"
    strategies.append(ev)

    # Favori + xG DISagree (kontrol)
    sub = df_valid[(df_valid["s_xg"] > 0) & (~df_valid["xg_fav_agree"])]
    ev = evaluate_picks(sub, direction_col="fav_dir")
    ev["name"] = "Favori + xG DISagree (control)"
    strategies.append(ev)

    # xG_direction'a bet (favori değil — xG'nin önerdiği)
    sub = df_valid[df_valid["s_xg"] >= 0.5]
    ev = evaluate_picks(sub, direction_col="xg_direction")
    ev["name"] = "xG_dir (>=0.5)"
    strategies.append(ev)

    sub = df_valid[df_valid["s_xg"] >= 0.7]
    ev = evaluate_picks(sub, direction_col="xg_direction")
    ev["name"] = "xG_dir (>=0.7)"
    strategies.append(ev)

    sub = df_valid[df_valid["s_xg"] >= 1.0]
    ev = evaluate_picks(sub, direction_col="xg_direction")
    ev["name"] = "xG_dir (>=1.0 max)"
    strategies.append(ev)

    # Model + xG agree
    sub = df_valid[
        (df_valid["s_xg"] > 0) &
        (df_valid.apply(lambda r: r.get("model_direction") in (None, "") or
                        r.get("xg_direction") == r.get("model_direction") or
                        (r.get("model_direction") in ("1","H","HOME") and r.get("xg_direction")=="HOME") or
                        (r.get("model_direction") in ("2","A","AWAY") and r.get("xg_direction")=="AWAY"),
                        axis=1))
    ]
    ev = evaluate_picks(sub, direction_col="xg_direction")
    ev["name"] = "xG_dir + model_dir agree"
    strategies.append(ev)

    # Favori + sweet odd range
    sub = df_valid[
        (df_valid["psc_h"] >= 1.5) &
        (df_valid["psc_h"] <= 2.5)
    ]
    ev = evaluate_picks(sub, direction_col="fav_dir")
    ev["name"] = "Favori (odd 1.5-2.5)"
    strategies.append(ev)

    # Hep Under (kontrol)
    df_valid_u = df_valid.copy(); df_valid_u["u_dir"] = "Under"
    ev = evaluate_picks(df_valid_u, direction_col="u_dir")
    ev["name"] = "Hep Under 2.5 (kontrol)"
    strategies.append(ev)

    df_valid_o = df_valid.copy(); df_valid_o["o_dir"] = "Over"
    ev = evaluate_picks(df_valid_o, direction_col="o_dir")
    ev["name"] = "Hep Over 2.5 (kontrol)"
    strategies.append(ev)

    # AGREE 2/3 (original "winner" — 4 sezonda)
    sub = filter_all_agree(df_valid, min_signals=3, min_agree=2)
    ev = evaluate_picks(sub, direction_col="consensus_direction")
    ev["name"] = "AGREE 2/3 (orig winner)"
    strategies.append(ev)

    # Decile 10
    chunk = filter_decile(df_valid, "score_v13", 10)
    ev = evaluate_picks(chunk, direction_col="model_direction")
    ev["name"] = "Decile 10 (score_v13)"
    strategies.append(ev)

    # ROI sort
    strategies = [s for s in strategies if s["n"] > 0]
    strategies.sort(key=lambda x: x["roi"], reverse=True)

    print(f"\n{'Strategy':35s} {'n':>5s} {'hit%':>6s} {'ROI%':>8s} {'CI95':>17s} {'p':>6s}")
    print("-" * 90)
    for s in strategies:
        ci = f"[{s['ci_low']*100:+.1f},{s['ci_high']*100:+.1f}]"
        sig = " *" if s.get("p_value", 1) < 0.05 else ""
        print(f"  {s['name']:33s} {s['n']:>5d} {s['hit_rate']*100:>5.1f}% "
              f"{s['roi']*100:>+7.2f}% {ci:>17s} {s['p_value']:>6.3f}{sig}")

    print("\n[3/3] PER-SEZON BREAKDOWN — en iyi 3 strateji")
    print("=" * 110)
    top_strategies = [s for s in strategies if s["n"] >= 50][:5]
    for s in top_strategies:
        name = s["name"]
        # 4 sezonu tek tek hesapla
        print(f"\n  {name} (TUM: n={s['n']}, ROI={s['roi']*100:+.1f}%, p={s['p_value']:.3f})")
        for season in ["2122", "2223", "2324", "2425"]:
            sub = df_valid[df_valid["season"] == season]
            # Aynı filtreyi uygula
            if name == "Hep favori (tum)":
                picks = sub
                dir_col = "fav_dir"
            elif name == "Favori + xG agree":
                picks = sub[sub["xg_fav_agree"]]
                dir_col = "fav_dir"
            elif name == "xG_dir (>=0.5)":
                picks = sub[sub["s_xg"] >= 0.5]
                dir_col = "xg_direction"
            elif name == "xG_dir (>=0.7)":
                picks = sub[sub["s_xg"] >= 0.7]
                dir_col = "xg_direction"
            elif name == "AGREE 2/3 (orig winner)":
                picks = filter_all_agree(sub, min_signals=3, min_agree=2)
                dir_col = "consensus_direction"
            elif name == "Decile 10 (score_v13)":
                picks = filter_decile(sub, "score_v13", 10)
                dir_col = "model_direction"
            elif name == "Favori (odd 1.5-2.5)":
                picks = sub[(sub["psc_h"] >= 1.5) & (sub["psc_h"] <= 2.5)]
                dir_col = "fav_dir"
            elif name == "xG_dir + model_dir agree":
                picks = sub[
                    (sub["s_xg"] > 0) &
                    (sub.apply(lambda r: r.get("model_direction") in (None,"") or
                              (r.get("model_direction") in ("1","H","HOME") and r.get("xg_direction")=="HOME") or
                              (r.get("model_direction") in ("2","A","AWAY") and r.get("xg_direction")=="AWAY"),
                              axis=1))
                ]
                dir_col = "xg_direction"
            else:
                picks = pd.DataFrame()
                dir_col = "fav_dir"

            if len(picks) > 0:
                ev = evaluate_picks(picks, direction_col=dir_col)
                if ev["n"] > 0:
                    print(f"    {season}: n={ev['n']:>3} hit={ev['hit_rate']*100:.0f}% ROI={ev['roi']*100:+.1f}% p={ev['p_value']:.3f}")
                else:
                    print(f"    {season}: 0 bet")
            else:
                print(f"    {season}: 0 mac")


if __name__ == "__main__":
    run()
