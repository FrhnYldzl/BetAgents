"""
KAPI 0 — TEST 7: SEZON-İÇİ ÖĞRENME PATERNİ
============================================

Kullanıcı sezgisi:
> "TRIVOX bence daha mantıklı, model o sezondaki maç verisiyle oluşuyor.
>  Seçili haftalardaki girişlerde pozitifleşme ve gelecek tahmini olmayacağı
>  için makul sanki mantıken."

TEST:
  Sezonu 4 dilime böl:
    Hafta 1-9   (sezon başı: model az veri ile çalışıyor)
    Hafta 10-18 (sezon ortası 1: veri biriktirme başlıyor)
    Hafta 19-27 (sezon ortası 2: model olgunlaşıyor)
    Hafta 28-38 (sezon sonu: maksimum veri)

  Her dilim için TRIVOX K=1 ROI ölç.

  Eğer ROI hafta ilerledikçe ARTIYORSA -> model sezon-içi öğreniyor (sağlıklı)
  Eğer DÜŞÜYORSA -> sezon başında "şanslı"; sonra mean-reversion (sahte edge)
  Eğer RASTGELE ise -> sezon faktörü yok

Bu, soft-leakage'ın YOKLUĞUNU teyit eder + canlı production stratejisi için
karar verir: "İlk N haftada bahis koyma, sezon olgunlaşsın".
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


def add_week_in_season(df: pd.DataFrame) -> pd.DataFrame:
    """Her maç için sezon-içi hafta numarası ekle."""
    df = df.copy()
    df["matchday_dt"] = pd.to_datetime(df["matchday"])
    out_dfs = []
    for (lg, ss), grp in df.groupby(["league_code", "season"]):
        grp = grp.sort_values("matchday_dt").copy()
        first = grp["matchday_dt"].min()
        grp["week_in_season"] = ((grp["matchday_dt"] - first).dt.days // 7) + 1
        out_dfs.append(grp)
    return pd.concat(out_dfs, ignore_index=True)


def build_K1_picks(df: pd.DataFrame, leagues: list, min_conf: int = 1) -> pd.DataFrame:
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
                "week_in_season": leg["week_in_season"],
            })
    return pd.DataFrame(picks)


def roi_stats(picks: pd.DataFrame, stake: float = 1000.0,
              tax: float = 0.10) -> dict:
    if picks.empty:
        return {"n": 0, "hit": 0, "avg_odd": 0,
                "roi_gross": 0, "roi_net": 0}
    n = len(picks); n_won = int(picks["won"].sum())
    hit = n_won / n
    won_picks = picks[picks["won"]]
    pnl_gross = (stake * (won_picks["odd"] - 1)).sum() - stake * (n - n_won)
    pnl_net = (stake * (won_picks["odd"] - 1) * (1 - tax)).sum() - stake * (n - n_won)
    stake_tot = stake * n
    avg_odd = picks["odd"].mean()
    return {
        "n": n, "n_won": n_won, "hit": hit,
        "avg_odd": float(avg_odd),
        "roi_gross": pnl_gross / stake_tot * 100,
        "roi_net": pnl_net / stake_tot * 100,
    }


def analyze_intraseason(picks: pd.DataFrame, name: str):
    """Sezon-içi haftalara göre ROI analizi."""
    print(f"\n{'-' * 80}")
    print(f">>> {name} — SEZON-ICI OGRENME PATERNI")
    print(f"{'-' * 80}")

    if picks.empty:
        print("  Pick yok")
        return

    # 4 dilime böl
    bins = [
        ("Hafta 1-9   (sezon basi)",    1, 9),
        ("Hafta 10-18 (orta-1)",        10, 18),
        ("Hafta 19-27 (orta-2)",        19, 27),
        ("Hafta 28-38 (sezon sonu)",    28, 38),
        ("Hafta 39+   (playoff/extra)", 39, 999),
    ]

    print(f"  {'Dilim':<32s} {'n':>4s} {'won':>4s} {'hit%':>5s} {'avg_odd':>8s} "
          f"{'ROI_g':>7s} {'ROI_n':>7s}")
    results = []
    for label, lo, hi in bins:
        sub = picks[(picks["week_in_season"] >= lo) & (picks["week_in_season"] <= hi)]
        s = roi_stats(sub)
        if s["n"] == 0:
            continue
        results.append({"label": label, "lo": lo, "hi": hi, **s})
        print(f"  {label:<32s} {s['n']:>4d} {s['n_won']:>4d} "
              f"{s['hit']*100:>4.0f}% {s['avg_odd']:>7.2f} "
              f"{s['roi_gross']:>+6.1f}% {s['roi_net']:>+6.1f}%")

    # Trend analizi
    if len(results) >= 3:
        rois_n = [r["roi_net"] for r in results if r["lo"] < 39]
        # Linear regression: hafta_orta vs ROI
        x = np.array([(r["lo"] + r["hi"]) / 2 for r in results if r["lo"] < 39])
        y = np.array(rois_n)
        if len(x) >= 3:
            slope, intercept = np.polyfit(x, y, 1)
            print(f"\n  Linear trend (ROI_net vs week):")
            print(f"    slope = {slope:+.3f}pp/week,  intercept = {intercept:+.2f}%")
            if slope > 0.3:
                print(f"    -> POZITIF EGIM: model sezon ilerledikce iyilesiyor")
                print(f"       (kullanici sezgisini DOGRULAR)")
            elif slope < -0.3:
                print(f"    -> NEGATIF EGIM: sezon basi sansli, sonra mean-reversion")
                print(f"       (uyari: sahte edge isareti)")
            else:
                print(f"    -> DUSUK EGIM: sezon-ici degisim onemsiz")

    # Hafta-ay alternatif: ilk N hafta vs sonraki
    print(f"\n  ILK YARI vs SONRAKI YARI (week_in_season cutoff=19):")
    early = picks[picks["week_in_season"] < 19]
    late = picks[picks["week_in_season"] >= 19]
    e = roi_stats(early); l = roi_stats(late)
    print(f"    Erken (1-18):  n={e['n']:>4d}, ROI_net {e['roi_net']:+.2f}%")
    print(f"    Gec   (19+ ):  n={l['n']:>4d}, ROI_net {l['roi_net']:+.2f}%")
    delta = l["roi_net"] - e["roi_net"]
    print(f"    Delta (gec - erken): {delta:+.2f}pp")
    if delta > 5:
        print(f"    -> STRONG: gec sezon belirgin iyi -> production'da ilk 8 hafta atla")
    elif delta > 2:
        print(f"    -> MILD: gec sezon hafif iyi")
    elif delta < -5:
        print(f"    -> RED FLAG: erken sezon daha iyi -> mean-reversion var")
    else:
        print(f"    -> STABLE: sezon-ici fark onemsiz")

    return results


def run():
    print("=" * 80)
    print("KAPI 0 - TEST 7: SEZON-ICI OGRENME PATERNI")
    print("Kullanici Sezgisi: 'model o sezondaki maç verisiyle oluşuyor'")
    print("=" * 80)

    df = load_data()
    df = add_week_in_season(df)
    print(f"Loaded: {len(df)} settled mac (sezon-ici hafta no eklendi)")

    # TRIVOX
    trivox = build_K1_picks(df, ["T1"], min_conf=1)
    trivox_results = analyze_intraseason(trivox, "TRIVOX K=1 (T1)")

    # EUVOX
    euvox = build_K1_picks(df, ["T1","E0","D1","SP1","I1","F1"], min_conf=1)
    euvox_results = analyze_intraseason(euvox, "EUVOX K=1 (6-lig)")

    # === BONUS: DIVOX testi (E0+D1) ===
    divox_e0 = build_K1_picks(df, ["E0"], min_conf=1)
    divox_d1 = build_K1_picks(df, ["D1"], min_conf=1)
    print(f"\n{'-' * 80}")
    print(f">>> DIVOX KESFI — E0, D1 ayri K=1 baseline (EUVOX'un yedek planı)")
    print(f"{'-' * 80}")
    print(f"  {'Lig':<10s} {'n':>5s} {'hit%':>5s} {'avg_odd':>8s} {'ROI_g':>7s} {'ROI_n':>7s}")
    for lg, pks in [("E0 (PL)", divox_e0), ("D1 (Bundes)", divox_d1)]:
        s = roi_stats(pks)
        print(f"  {lg:<10s} {s['n']:>5d} {s['hit']*100:>4.0f}% {s['avg_odd']:>7.2f} "
              f"{s['roi_gross']:>+6.1f}% {s['roi_net']:>+6.1f}%")
    # SP1, I1, F1 da
    for code, name in [("SP1","La Liga"),("I1","Serie A"),("F1","Ligue 1")]:
        pks = build_K1_picks(df, [code], min_conf=1)
        s = roi_stats(pks)
        print(f"  {code+' ('+name+')':<10s} {s['n']:>5d} {s['hit']*100:>4.0f}% "
              f"{s['avg_odd']:>7.2f} {s['roi_gross']:>+6.1f}% {s['roi_net']:>+6.1f}%")

    # === Karar ===
    print("\n" + "=" * 80)
    print("KAPI 0 - TEST 7 VERDICT")
    print("=" * 80)

    # Markdown rapor
    rapor = ["# KAPI 0 — TEST 7: SEZON-ICI OGRENME PATERNI\n"]
    rapor.append(f"**Tarih:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}\n")
    rapor.append("**Kullanici sezgisi:** \"model o sezondaki mac verisiyle olusuyor\"\n\n")

    rapor.append("## TRIVOX K=1 — Sezon-Ici Patern\n\n")
    rapor.append("| Dilim | n | hit% | avg_odd | ROI_gross | ROI_net |\n")
    rapor.append("|---|---|---|---|---|---|\n")
    if trivox_results:
        for r in trivox_results:
            rapor.append(f"| {r['label']} | {r['n']} | {r['hit']*100:.0f}% | "
                         f"{r['avg_odd']:.2f} | {r['roi_gross']:+.2f}% | "
                         f"{r['roi_net']:+.2f}% |\n")

    rapor.append("\n## EUVOX K=1 — Sezon-Ici Patern\n\n")
    rapor.append("| Dilim | n | hit% | avg_odd | ROI_gross | ROI_net |\n")
    rapor.append("|---|---|---|---|---|---|\n")
    if euvox_results:
        for r in euvox_results:
            rapor.append(f"| {r['label']} | {r['n']} | {r['hit']*100:.0f}% | "
                         f"{r['avg_odd']:.2f} | {r['roi_gross']:+.2f}% | "
                         f"{r['roi_net']:+.2f}% |\n")

    rapor.append("\n## DIVOX Kesfi — Per-Lig K=1 Baseline\n\n")
    rapor.append("| Lig | n | hit% | avg_odd | ROI_gross | ROI_net |\n")
    rapor.append("|---|---|---|---|---|---|\n")
    for lg, pks in [("T1", build_K1_picks(df, ["T1"])),
                    ("E0", divox_e0),
                    ("D1", divox_d1),
                    ("SP1", build_K1_picks(df, ["SP1"])),
                    ("I1", build_K1_picks(df, ["I1"])),
                    ("F1", build_K1_picks(df, ["F1"]))]:
        s = roi_stats(pks)
        rapor.append(f"| {lg} | {s['n']} | {s['hit']*100:.0f}% | "
                     f"{s['avg_odd']:.2f} | {s['roi_gross']:+.2f}% | "
                     f"{s['roi_net']:+.2f}% |\n")

    out = YAZILIM / "RAPOR" / "Kapi0_T07_intraseason_learning.md"
    out.write_text("".join(rapor), encoding="utf-8")
    print(f"\n[OK] Rapor: {out}")


if __name__ == "__main__":
    run()
