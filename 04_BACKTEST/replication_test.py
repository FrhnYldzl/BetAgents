"""
SELECTIVE EDGE v1.3 — REPLIKASYON TESTI

Hipotez:
    consistency_test_v2.py'de bulduğumuz AGREE 2/3 ROI +40% (n=121, 2022-23),
    AYNI strateji 2024-25 sezonunda da kâr eder mi?

2024-25 = DC out-of-sample (DC 2023-24'e eğitildi).
        = xG out-of-sample (xg_data season=2024 = 2024-25 sezonu).

Replikasyon başarılı = pipeline gerçek edge sağlar, gürültü değildir.
Replikasyon başarısız = bulgular overfit/sample-specific olabilir.
"""
from __future__ import annotations

import sys
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS_DIR))

# consistency_test_v2'yi import et ama SEASONS'ı override et
from consistency_test_v2 import (
    compute_signals_v13, filter_all_agree, filter_sweet_spot, filter_decile,
    strategy_top_n, evaluate_picks, run as run_v13,
)
import consistency_test_v2

# === 2024-25 sezonu ===
ORIGINAL_SEASONS = consistency_test_v2.SEASONS.copy()
ORIGINAL_LEAGUES = consistency_test_v2.LEAGUES.copy()
TEST_SEASONS = ["2425"]
TEST_LEAGUES = ["E0", "D1", "T1"]


def run_replication():
    print("=" * 110)
    print("SELECTIVE EDGE v1.3 — REPLIKASYON TESTI (2024-25 sezonu)")
    print("  DC training: 2023-24 (in-sample) -> bu test: 2024-25 (out-of-sample)")
    print("=" * 110)

    consistency_test_v2.SEASONS = TEST_SEASONS
    consistency_test_v2.LEAGUES = TEST_LEAGUES

    print("\n[1/2] 2024-25 verisi + sinyaller yukleniyor...")
    df = compute_signals_v13(verbose=True)
    print(f"  Toplam: {len(df)} mac")

    df_valid = df[
        df["score_v13"].notna() &
        df["psc_h"].notna() &
        df["ftr"].notna()
    ].copy()
    print(f"  Bet edilebilir: {len(df_valid)}")
    print(f"  xG cover: {(df_valid['s_xg']>0).sum()} mac ({(df_valid['s_xg']>0).mean()*100:.0f}%)")
    print(f"  Form cover: {(df_valid['s_form']>0).sum()} mac")

    print("\n[2/2] STRATEJI REPLIKASYONU")
    print("=" * 110)

    strategies = []

    # 2022-23 ile aynı stratejileri tekrar test et
    # AGREE 2/3 (anchor finding)
    picks = filter_all_agree(df_valid, min_signals=3, min_agree=2)
    ev = evaluate_picks(picks, direction_col="consensus_direction")
    ev["name"] = "AGREE 2/3 (REPLICATION)"
    strategies.append(ev)

    # AGREE 3/3
    picks = filter_all_agree(df_valid, min_signals=3, min_agree=3)
    ev = evaluate_picks(picks, direction_col="consensus_direction")
    ev["name"] = "AGREE 3/3"
    strategies.append(ev)

    # AGREE 4/4
    picks = filter_all_agree(df_valid, min_signals=4, min_agree=4)
    ev = evaluate_picks(picks, direction_col="consensus_direction")
    ev["name"] = "AGREE 4/4"
    strategies.append(ev)

    # AGREE 3/4
    picks = filter_all_agree(df_valid, min_signals=4, min_agree=3)
    ev = evaluate_picks(picks, direction_col="consensus_direction")
    ev["name"] = "AGREE 3/4"
    strategies.append(ev)

    # xG alone
    picks = df_valid[df_valid["s_xg"] >= 0.5]
    ev = evaluate_picks(picks, direction_col="xg_direction")
    ev["name"] = "Sadece xG>=0.5"
    strategies.append(ev)

    # v1.2 TOP-3 (önceki başarısız strateji — replication için)
    picks = strategy_top_n(df_valid, 3, by="score_v12")
    ev = evaluate_picks(picks, direction_col="model_direction")
    ev["name"] = "v1.2 TOP-3 (baseline)"
    strategies.append(ev)

    # Decile 10
    chunk = filter_decile(df_valid, "score_v13", 10)
    ev = evaluate_picks(chunk, direction_col="model_direction")
    ev["name"] = "Decile 10"
    strategies.append(ev)

    # Always favorite
    ev = evaluate_picks(df_valid, direction_col="fav_dir")
    ev["name"] = "BASELINE: hep favori"
    strategies.append(ev)

    print(f"\n{'Strategy':30s} {'n':>5s} {'hit%':>6s} {'ROI%':>8s} {'CI95':>17s} "
          f"{'p':>6s} {'avg_odd':>7s}")
    print("-" * 95)
    for s in strategies:
        if s["n"] == 0:
            print(f"  {s['name']:28s}    (0 bet)")
            continue
        ci = f"[{s['ci_low']*100:+.1f},{s['ci_high']*100:+.1f}]"
        sig = " *" if s.get("p_value", 1) < 0.05 else ""
        print(f"  {s['name']:28s} {s['n']:>5d} {s['hit_rate']*100:>5.1f}% "
              f"{s['roi']*100:>+7.2f}% {ci:>17s} {s['p_value']:>6.3f} "
              f"{s['avg_odd']:>7.2f}{sig}")

    # === REPLIKASYON KARARI ===
    agree23 = next(s for s in strategies if s["name"] == "AGREE 2/3 (REPLICATION)")
    print("\n" + "=" * 110)
    print("REPLIKASYON KARARI")
    print("=" * 110)
    print(f"  ORIGINAL (2022-23): ROI +40.0%  p=0.009  n=121  CI=[+7.9, +74.4]")
    print(f"  REPLICATION (2024-25): ROI {agree23['roi']*100:+.2f}%  "
          f"p={agree23['p_value']:.3f}  n={agree23['n']}  ", end="")
    if agree23["ci_low"] is not None:
        print(f"CI=[{agree23['ci_low']*100:+.1f}, {agree23['ci_high']*100:+.1f}]")
    else:
        print("CI=N/A")

    if agree23["n"] >= 30 and agree23.get("ci_low", -99) > 0:
        print(f"\n  KARAR: REPLIKASYON BASARILI (95% CI tamamen pozitif)")
    elif agree23["roi"] > 0 and agree23["p_value"] < 0.10:
        print(f"\n  KARAR: KISMI BASARI (ROI pozitif, p<0.10)")
    elif agree23["n"] < 30:
        print(f"\n  KARAR: SAMPLE YETERSIZ (n<30)")
    else:
        print(f"\n  KARAR: REPLIKASYON BASARISIZ (gercek edge degil)")

    # restore for cleanliness
    consistency_test_v2.SEASONS = ORIGINAL_SEASONS
    consistency_test_v2.LEAGUES = ORIGINAL_LEAGUES
    return strategies


if __name__ == "__main__":
    run_replication()
