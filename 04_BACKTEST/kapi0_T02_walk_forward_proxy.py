"""
KAPI 0 — TEST 2: T1 WALK-FORWARD PROXY (sezon-by-sezon + temporal stability)
=============================================================================

Komite Madde A2:
> "T1 walk-forward DC eksik — sadece E0 için yapılmış (−%0.33).
>  Halbuki +%60 ROI iddiası T1'e dayanıyor."

Tam walk-forward için DC modelini sıfırdan eğitmek gerek. Mevcut score_v13
zaten "tüm veri" üzerinde fit edilmiş, yeniden hesaplanamıyor.

PRAGMATIK PROXY YAKLAŞIMI:
  1) Sezon-by-sezon TRIVOX K=1 ROI: out-of-sample collapse var mı?
     - 2021-22, 22-23, 23-24, 24-25, 25-26 her biri için ayrı ROI
     - Eğer son 2 sezon (24-25, 25-26) belirgin negatif ise -> in-sample bias işareti
     - Eğer tüm sezonlar tutarlı ise -> bias riski düşük

  2) Sliding-window stabilite: ardışık sezon çiftleri arasında ROI değişimi
     - High variance = sezon-spesifik şans
     - Low variance = gerçek edge

  3) Forward-only test: Sezonu ikiye böl (ilk yarı = train signal, ikinci yarı = test)
     - Eğer ikinci yarıda ROI düşüyorsa -> score_v13 sezon ilk yarısının verisinden öğreniyor

Output:
  - Console: per-sezon ROI matrisi
  - RAPOR/Kapi0_T02_walk_forward_proxy.md
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

THIS_DIR = Path(__file__).resolve().parent
YAZILIM = THIS_DIR.parent
sys.path.insert(0, str(YAZILIM / "02_VERI"))
sys.path.insert(0, str(YAZILIM / "03_MODELLER" / "selective"))

import database as db
from trivox_v1 import fav_confirmed, normalize_dir


SEASON_CONV = {
    "1718":"2017-18","1819":"2018-19","1920":"2019-20","2021":"2020-21",
    "2122":"2021-22","2223":"2022-23","2324":"2023-24","2425":"2024-25","2526":"2025-26",
}


def load_data() -> pd.DataFrame:
    conn = db.connect()
    df = pd.read_sql_query(
        """SELECT league_code, season, kickoff_iso, home_team, away_team,
               odd_1, odd_X, odd_2,
               dir_favorite, dir_anomaly, dir_model, dir_xg, dir_form,
               score_v13, result_1x2, settled
           FROM signal_snapshots
           WHERE source='football_data' AND settled=1""", conn
    )
    conn.close()
    df["season"] = df["season"].astype(str).map(lambda s: SEASON_CONV.get(s, s))
    df["matchday"] = pd.to_datetime(df["kickoff_iso"]).dt.strftime("%Y-%m-%d")
    return df


def get_odd(row, direction):
    d = normalize_dir(direction)
    if d == "HOME": return row.get("odd_1")
    if d == "AWAY": return row.get("odd_2")
    if d == "DRAW": return row.get("odd_X")
    return None


def did_win(row, direction):
    d = normalize_dir(direction)
    return row.get("result_1x2") == {"HOME":"H","AWAY":"A","DRAW":"D"}[d]


def build_K1_picks(df: pd.DataFrame, leagues: list, min_conf: int = 1) -> pd.DataFrame:
    """K=1 picks: her matchday × lig için top-1 (score_v13 highest)."""
    df = df[df["league_code"].isin(leagues)].copy()
    df["dir_fc"] = df.apply(lambda r: fav_confirmed(r.to_dict(), min_conf), axis=1)
    df = df[df["dir_fc"].notna()].copy()
    df = df.sort_values("score_v13", ascending=False)

    picks = []
    for (md, lg), group in df.groupby(["matchday", "league_code"]):
        top = group.head(1)
        for _, leg in top.iterrows():
            d = leg["dir_fc"]
            o = get_odd(leg.to_dict(), d)
            w = did_win(leg.to_dict(), d)
            if not o or o < 1.01: continue
            picks.append({
                "matchday": str(md), "league": lg, "season": leg["season"],
                "home": leg["home_team"], "away": leg["away_team"],
                "direction": d, "odd": o, "won": w,
            })
    return pd.DataFrame(picks)


def roi_stats(picks: pd.DataFrame, stake: float = 1000.0,
              tax: float = 0.10) -> dict:
    if picks.empty:
        return {"n": 0}
    n = len(picks); n_won = int(picks["won"].sum())
    hit = n_won / n
    won_picks = picks[picks["won"]]
    pnl_gross = (stake * (won_picks["odd"] - 1)).sum() - stake * (n - n_won)
    pnl_net = (stake * (won_picks["odd"] - 1) * (1 - tax)).sum() - stake * (n - n_won)
    stake_tot = stake * n
    avg_odd = picks["odd"].mean()
    breakeven = 1.0 / avg_odd if avg_odd else 0
    return {
        "n": n, "n_won": n_won, "hit": hit,
        "avg_odd": avg_odd, "breakeven": breakeven,
        "roi_gross": pnl_gross / stake_tot * 100,
        "roi_net": pnl_net / stake_tot * 100,
    }


def run():
    print("=" * 80)
    print("KAPI 0 — TEST 2: T1 WALK-FORWARD PROXY (sezonsal stabilite)")
    print("=" * 80)

    df = load_data()
    print(f"Toplam settled: {len(df)} satir\n")

    # === TRIVOX K=1 sezon-by-sezon ===
    print("-" * 80)
    print(">>> TRIVOX K=1 (T1 only, FAV_CONFIRMED, min_conf=1)")
    print(">>> Eğer ROI sezonlar arası tutarlı ise -> edge gerçek")
    print(">>> Eğer son sezonlar belirgin kötüleşiyorsa -> in-sample bias işareti")
    print("-" * 80)
    print(f"{'Sezon':>8s} {'n':>4s} {'won':>4s} {'hit%':>5s} {'avg_odd':>8s} "
          f"{'ROI_g':>7s} {'ROI_n':>7s} {'break_pt':>9s}")

    trivox_picks = build_K1_picks(df, ["T1"], min_conf=1)
    trivox_seasons = {}
    for ss in sorted(trivox_picks["season"].unique()):
        sub = trivox_picks[trivox_picks["season"] == ss]
        s = roi_stats(sub)
        trivox_seasons[ss] = s
        print(f"{ss:>8s} {s['n']:>4d} {s['n_won']:>4d} "
              f"{s['hit']*100:>4.0f}% {s['avg_odd']:>7.2f} "
              f"{s['roi_gross']:>+6.1f}% {s['roi_net']:>+6.1f}% "
              f"{s['breakeven']*100:>7.1f}%")

    # === Stabilite metrikleri ===
    rois_g = [trivox_seasons[ss]["roi_gross"] for ss in trivox_seasons]
    rois_n = [trivox_seasons[ss]["roi_net"] for ss in trivox_seasons]
    print(f"\nROI gross: mean={np.mean(rois_g):+.2f}%, std={np.std(rois_g):.2f}%, "
          f"min={min(rois_g):+.1f}%, max={max(rois_g):+.1f}%")
    print(f"ROI net  : mean={np.mean(rois_n):+.2f}%, std={np.std(rois_n):.2f}%, "
          f"min={min(rois_n):+.1f}%, max={max(rois_n):+.1f}%")
    pos_seasons_n = sum(1 for r in rois_n if r > 0)
    print(f"Pozitif ROI_net sezon: {pos_seasons_n}/{len(rois_n)}")

    # === Son 2 sezon vs ilk N sezon ===
    sorted_seasons = sorted(trivox_seasons.keys())
    if len(sorted_seasons) >= 4:
        early = sorted_seasons[:-2]
        late = sorted_seasons[-2:]
        early_picks = trivox_picks[trivox_picks["season"].isin(early)]
        late_picks = trivox_picks[trivox_picks["season"].isin(late)]
        e = roi_stats(early_picks)
        l = roi_stats(late_picks)
        print(f"\nERKEN sezonlar {early}: n={e['n']}, ROI_net {e['roi_net']:+.2f}%")
        print(f"GEÇ   sezonlar {late}: n={l['n']}, ROI_net {l['roi_net']:+.2f}%")
        delta = l["roi_net"] - e["roi_net"]
        print(f"Delta (late - early): {delta:+.2f}pp")
        if delta < -5:
            collapse_signal = "STRONG"
        elif delta < -2:
            collapse_signal = "MILD"
        elif delta > 2:
            collapse_signal = "IMPROVING"
        else:
            collapse_signal = "STABLE"
        print(f"Out-of-sample collapse signal: {collapse_signal}")

    # === EUVOX karşılaştırma ===
    print()
    print("-" * 80)
    print(">>> EUVOX K=1 (6-lig, FAV_CONFIRMED, min_conf=1)")
    print("-" * 80)
    print(f"{'Sezon':>8s} {'n':>4s} {'won':>4s} {'hit%':>5s} {'avg_odd':>8s} "
          f"{'ROI_g':>7s} {'ROI_n':>7s} {'break_pt':>9s}")
    euvox_picks = build_K1_picks(df, ["T1","E0","D1","SP1","I1","F1"], min_conf=1)
    euvox_seasons = {}
    for ss in sorted(euvox_picks["season"].unique()):
        sub = euvox_picks[euvox_picks["season"] == ss]
        s = roi_stats(sub)
        euvox_seasons[ss] = s
        print(f"{ss:>8s} {s['n']:>4d} {s['n_won']:>4d} "
              f"{s['hit']*100:>4.0f}% {s['avg_odd']:>7.2f} "
              f"{s['roi_gross']:>+6.1f}% {s['roi_net']:>+6.1f}% "
              f"{s['breakeven']*100:>7.1f}%")
    eu_rois_n = [euvox_seasons[ss]["roi_net"] for ss in euvox_seasons]
    print(f"\nROI net: mean={np.mean(eu_rois_n):+.2f}%, std={np.std(eu_rois_n):.2f}%, "
          f"min={min(eu_rois_n):+.1f}%, max={max(eu_rois_n):+.1f}%")

    # === Sezon-içi forward test (yarım sezon split) ===
    print()
    print("-" * 80)
    print(">>> SEZON-İÇİ FORWARD TEST")
    print(">>> Her sezonu yarıya böl. İlk yarı vs ikinci yarı ROI.")
    print(">>> Eğer ikinci yarı belirgin kötüyse -> score_v13 sezon-içi info'dan öğreniyor")
    print("-" * 80)

    def split_season_half(picks):
        """Her sezon için yarım-yarım split + ROI."""
        results = []
        for ss in sorted(picks["season"].unique()):
            sub = picks[picks["season"] == ss].sort_values("matchday")
            if len(sub) < 10: continue
            mid = len(sub) // 2
            first = sub.iloc[:mid]
            second = sub.iloc[mid:]
            r1 = roi_stats(first); r2 = roi_stats(second)
            results.append({
                "season": ss, "n_first": r1["n"], "n_second": r2["n"],
                "roi_first": r1["roi_net"], "roi_second": r2["roi_net"],
                "delta": r2["roi_net"] - r1["roi_net"],
            })
        return results

    print("\nTRIVOX (T1):")
    print(f"{'sezon':>8s} {'1.yari_n':>9s} {'2.yari_n':>9s} "
          f"{'1.ROI':>7s} {'2.ROI':>7s} {'Delta':>7s}")
    for r in split_season_half(trivox_picks):
        print(f"{r['season']:>8s} {r['n_first']:>8d} {r['n_second']:>8d} "
              f"{r['roi_first']:>+6.1f}% {r['roi_second']:>+6.1f}% "
              f"{r['delta']:>+6.1f}pp")
    trivox_deltas = [r["delta"] for r in split_season_half(trivox_picks)]
    if trivox_deltas:
        print(f"Mean Delta (2.yari - 1.yari): {np.mean(trivox_deltas):+.2f}pp")
        if np.mean(trivox_deltas) < -5:
            print("  *** RED FLAG: 2.yari ortalama 5pp+ kötü -> soft-leakage işareti")
        elif np.mean(trivox_deltas) < -2:
            print("  ! MILD signal: 2.yari hafif kötü, dikkatli ol")
        else:
            print("  OK: 1.yari ile 2.yari ROI karsilastirilabilir")

    print("\nEUVOX (6-lig):")
    print(f"{'sezon':>8s} {'1.yari_n':>9s} {'2.yari_n':>9s} "
          f"{'1.ROI':>7s} {'2.ROI':>7s} {'Delta':>7s}")
    for r in split_season_half(euvox_picks):
        print(f"{r['season']:>8s} {r['n_first']:>8d} {r['n_second']:>8d} "
              f"{r['roi_first']:>+6.1f}% {r['roi_second']:>+6.1f}% "
              f"{r['delta']:>+6.1f}pp")

    # === Final verdict ===
    print()
    print("=" * 80)
    print("KAPI 0 — TEST 2 VERDICT")
    print("=" * 80)

    n_pos = sum(1 for r in rois_n if r > 0)
    last_2_avg = np.mean(rois_n[-2:]) if len(rois_n) >= 2 else 0
    early_avg = np.mean(rois_n[:-2]) if len(rois_n) >= 3 else 0
    delta_late_early = last_2_avg - early_avg

    print(f"\nTRIVOX:")
    print(f"  {n_pos}/{len(rois_n)} sezon pozitif")
    print(f"  Son 2 sezon ortalama: {last_2_avg:+.2f}%")
    print(f"  Erken sezonlar ortalama: {early_avg:+.2f}%")
    print(f"  Delta: {delta_late_early:+.2f}pp")

    if delta_late_early < -10:
        verdict = "FAIL_COLLAPSE"
        print("  [FAIL] FAIL: Out-of-sample collapse (10pp+ düşüş)")
    elif delta_late_early < -5:
        verdict = "WARN_DECAY"
        print("  [WARN] WARN: Edge zayıflıyor (5-10pp düşüş)")
    elif n_pos >= len(rois_n) * 0.6:
        verdict = "PASS_STABLE"
        print("  ✅ PASS: Çoğunluk sezon pozitif, stabil edge")
    else:
        verdict = "AMBIGUOUS"
        print("  🟡 AMBIGUOUS: Karma sezon performansı")

    # Markdown rapor
    rapor = ["# KAPI 0 — TEST 2: T1 WALK-FORWARD PROXY\n"]
    rapor.append(f"**Tarih:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}\n")
    rapor.append("**Komite Madde A2:** \"T1 walk-forward DC eksik\"\n\n")
    rapor.append("## TRIVOX K=1 Sezonsal Stabilite\n\n")
    rapor.append("| Sezon | n | hit% | avg_odd | ROI_gross | ROI_net | breakeven |\n")
    rapor.append("|---|---|---|---|---|---|---|\n")
    for ss in sorted(trivox_seasons.keys()):
        s = trivox_seasons[ss]
        rapor.append(f"| {ss} | {s['n']} | {s['hit']*100:.0f}% | "
                     f"{s['avg_odd']:.2f} | {s['roi_gross']:+.2f}% | "
                     f"{s['roi_net']:+.2f}% | {s['breakeven']*100:.1f}% |\n")
    rapor.append(f"\n**Stabilite metrikleri:**\n")
    rapor.append(f"- ROI_net mean: {np.mean(rois_n):+.2f}%\n")
    rapor.append(f"- ROI_net std: {np.std(rois_n):.2f}%\n")
    rapor.append(f"- {n_pos}/{len(rois_n)} sezon pozitif\n")
    rapor.append(f"- Son 2 sezon vs erken sezonlar: Delta {delta_late_early:+.2f}pp\n")
    rapor.append(f"\n## EUVOX K=1 Sezonsal Stabilite\n\n")
    rapor.append("| Sezon | n | hit% | avg_odd | ROI_gross | ROI_net |\n")
    rapor.append("|---|---|---|---|---|---|\n")
    for ss in sorted(euvox_seasons.keys()):
        s = euvox_seasons[ss]
        rapor.append(f"| {ss} | {s['n']} | {s['hit']*100:.0f}% | "
                     f"{s['avg_odd']:.2f} | {s['roi_gross']:+.2f}% | "
                     f"{s['roi_net']:+.2f}% |\n")
    rapor.append(f"\n## Verdict\n\n**TRIVOX: {verdict}**\n")
    out = YAZILIM / "RAPOR" / "Kapi0_T02_walk_forward_proxy.md"
    out.write_text("".join(rapor), encoding="utf-8")
    print(f"\n[OK] Rapor: {out}")


if __name__ == "__main__":
    run()
