"""
KAPI 0 — TEST 8: AVRUPA LİGLERİ YENİ MODEL ARAYIŞI
======================================================

Kullanici: "EUVOX bırakılmıyor — Avrupa liglerinde DIVOX vs. bir şey olarak
            devam edebilir mi bakalım. Yeni sağlam veri setiyle MODEL bile
            değişmiş oluyor sanki. Geliştirelim ikisini de, farklı isim olur."

T07'de keşif:
  T1   +%2.0 ROI ROI_n  (TRIVOX kalıyor, ayrı model)
  E0   +%3.1 ROI_n  [BEST] en güçlü tek lig!
  SP1  +%0.8 ROI_n  marjinal pozitif
  D1   -%2.1 ROI_n
  I1   -%2.5 ROI_n
  F1   -%7.2 ROI_n  [WORST] batırıyor

Bu testte:
  1) Tüm 2^5-1 = 31 lig kombinasyonu için K=1 ROI ölç (E0, SP1, D1, I1, F1)
     (T1 ayrı tutuyoruz — TRIVOX ana ürün)
  2) En iyi 5 kombinasyon için detay analiz:
     - Per-sezon stabilite
     - Sezon-içi patern (T07 stili)
     - CLV ölçümü (matches_v2 join)
     - K=2 ve K=3 ROI
  3) Karar: hangi kombinasyon yatırılabilir Avrupa modeli?
     - Aday isimler: DIVOX (2 lig), TRIOVOX (3 lig), QUADVOX (4 lig)
"""
from __future__ import annotations

import itertools
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

EU_LEAGUES = ["E0", "SP1", "D1", "I1", "F1"]  # T1 ayrı tutuyoruz


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


def load_m2() -> pd.DataFrame:
    conn = db.connect()
    df = pd.read_sql_query(
        """SELECT league_code, season, matchday, home_team, away_team,
               opening_1, opening_X, opening_2,
               closing_1, closing_X, closing_2
           FROM matches_v2 WHERE is_settled=1""", conn
    )
    conn.close()
    df["matchday"] = df["matchday"].astype(str)
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


def build_K_picks(df: pd.DataFrame, leagues: list, K: int = 1,
                  min_conf: int = 1) -> pd.DataFrame:
    df = df[df["league_code"].isin(leagues)].copy()
    df["dir_fc"] = df.apply(lambda r: fav_confirmed(r.to_dict(), min_conf), axis=1)
    df = df[df["dir_fc"].notna()].copy()
    df = df.sort_values("score_v13", ascending=False)

    kupons = []
    for (md, lg), group in df.groupby(["matchday", "league_code"]):
        topK = group.head(K)
        if len(topK) < K:
            continue
        combo_odd = 1.0
        all_won = True
        legs = []
        for _, leg in topK.iterrows():
            d = leg["dir_fc"]
            o = get_odd(leg.to_dict(), d)
            w = did_win(leg.to_dict(), d)
            if not o or o < 1.01:
                combo_odd = None
                break
            combo_odd *= o
            if not w: all_won = False
            legs.append({
                "matchday": str(md), "league": lg, "season": leg["season"],
                "home": leg["home_team"], "away": leg["away_team"],
                "direction": d, "odd": o, "won": w,
            })
        if combo_odd is None: continue
        season_str = legs[0]["season"] if legs else None
        kupons.append({"matchday": str(md), "league": lg, "season": season_str,
                       "K": K, "combo_odd": combo_odd, "won": all_won, "legs": legs})
    return pd.DataFrame(kupons)


def roi_stats(kupons: pd.DataFrame, stake: float = 1000.0, tax: float = 0.10):
    if kupons.empty: return {"n": 0}
    n = len(kupons); n_won = int(kupons["won"].sum())
    won_kupons = kupons[kupons["won"]]
    pnl_gross = (stake * (won_kupons["combo_odd"] - 1)).sum() - stake * (n - n_won)
    pnl_net = (stake * (won_kupons["combo_odd"] - 1) * (1 - tax)).sum() - stake * (n - n_won)
    return {
        "n": n, "n_won": n_won, "hit": n_won/n,
        "avg_combo": float(kupons["combo_odd"].mean()),
        "roi_gross": pnl_gross / (stake * n) * 100,
        "roi_net": pnl_net / (stake * n) * 100,
    }


def compute_clv(kupons: pd.DataFrame, df_m2: pd.DataFrame) -> dict:
    if kupons.empty: return {"clv_mean": None, "clv_n": 0}
    all_legs = []
    for _, k in kupons.iterrows():
        for leg in k["legs"]:
            all_legs.append(leg)
    legs_df = pd.DataFrame(all_legs).rename(
        columns={"home":"home_team","away":"away_team","league":"league_code"})
    merged = legs_df.merge(df_m2, on=["league_code","season","matchday",
                                       "home_team","away_team"], how="left")
    def m2_open(r):
        d = normalize_dir(r["direction"])
        return r["opening_1"] if d=="HOME" else (r["opening_2"] if d=="AWAY" else r["opening_X"])
    def m2_close(r):
        d = normalize_dir(r["direction"])
        return r["closing_1"] if d=="HOME" else (r["closing_2"] if d=="AWAY" else r["closing_X"])
    merged["po"] = merged.apply(m2_open, axis=1)
    merged["pc"] = merged.apply(m2_close, axis=1)
    merged["clv"] = merged["po"] / merged["pc"] - 1
    clv = merged["clv"].dropna()
    return {"clv_mean": float(clv.mean()) if len(clv) else None,
            "clv_n": int(len(clv)),
            "clv_pos_pct": float((clv > 0).mean()*100) if len(clv) else 0}


def all_combinations(leagues: list):
    """Tüm non-empty alt kümeler."""
    combos = []
    for r in range(1, len(leagues)+1):
        for c in itertools.combinations(leagues, r):
            combos.append(list(c))
    return combos


def run():
    print("=" * 80)
    print("KAPI 0 - TEST 8: AVRUPA LIGLERI YENI MODEL ARAYISI")
    print("EUVOX dogusu degil, yeniden tasarim. Hedef: yatirilabilir kombinasyon.")
    print("=" * 80)

    df = load_data()
    df_m2 = load_m2()
    print(f"signal_snapshots: {len(df)}")
    print(f"matches_v2:        {len(df_m2)}\n")

    # === 1) Tüm 31 EU lig kombinasyonu K=1 brute-force ===
    print("-" * 80)
    print(">>> TUM 31 AVRUPA LIG KOMBINASYONU K=1 ROI (brute-force)")
    print(">>> T1 ayri tutuluyor (TRIVOX ana urun)")
    print("-" * 80)
    print(f"{'Combo':<22s} {'n':>5s} {'hit%':>5s} {'avg_odd':>8s} "
          f"{'ROI_g':>7s} {'ROI_n':>7s}")
    combo_results = []
    for combo in all_combinations(EU_LEAGUES):
        picks = build_K_picks(df, combo, K=1)
        s = roi_stats(picks)
        if s["n"] < 100: continue  # Skip too-small samples
        combo_results.append({"combo": combo, "name": "+".join(combo), **s})
    # Sort by ROI_net descending
    combo_results.sort(key=lambda x: x["roi_net"], reverse=True)
    for r in combo_results[:15]:
        print(f"{r['name']:<22s} {r['n']:>5d} {r['hit']*100:>4.0f}% "
              f"{r['avg_combo']:>7.2f} {r['roi_gross']:>+6.1f}% {r['roi_net']:>+6.1f}%")
    print(f"  ... ({len(combo_results)-15} more)" if len(combo_results) > 15 else "")
    print(f"\nEn iyi 3:")
    for r in combo_results[:3]:
        print(f"  [BEST] {r['name']}: ROI_n {r['roi_net']:+.2f}% (n={r['n']})")
    print(f"En kotu 3:")
    for r in combo_results[-3:]:
        print(f"  [WORST] {r['name']}: ROI_n {r['roi_net']:+.2f}% (n={r['n']})")

    # === 2) Top 5 kombinasyon için detay analiz ===
    print("\n" + "-" * 80)
    print(">>> TOP 5 KOMBINASYON DETAY ANALIZI")
    print(">>> Per-sezon stabilite + CLV + K=1/K=2/K=3 ROI")
    print("-" * 80)

    detail_results = []
    for rank, r in enumerate(combo_results[:5]):
        combo = r["combo"]
        name = r["name"]
        candidate_name = {
            1: "MONOVOX",
            2: "DUOVOX",
            3: "TRIOVOX",
            4: "QUADVOX",
            5: "PENTAVOX",
        }.get(len(combo), f"{len(combo)}-VOX")
        print(f"\n[{rank+1}] {name} ({candidate_name} aday) — n={r['n']}, ROI_n {r['roi_net']:+.2f}%")

        # Per-sezon
        picks_K1 = build_K_picks(df, combo, K=1)
        season_rois = []
        print(f"    Per-sezon K=1:")
        for ss in sorted(picks_K1["season"].unique()):
            sub = picks_K1[picks_K1["season"] == ss]
            s = roi_stats(sub)
            season_rois.append(s["roi_net"])
            print(f"      {ss}: n={s['n']:>3d}, ROI_n {s['roi_net']:+.2f}%")
        pos_seasons = sum(1 for x in season_rois if x > 0)
        print(f"      -> {pos_seasons}/{len(season_rois)} sezon pozitif, "
              f"std={np.std(season_rois):.2f}")

        # K=1, K=2, K=3
        roi_by_K = {}
        for K in (1, 2, 3):
            picks_K = build_K_picks(df, combo, K=K)
            sK = roi_stats(picks_K)
            roi_by_K[K] = sK
        print(f"    K seviyeleri:")
        for K in (1, 2, 3):
            sK = roi_by_K[K]
            print(f"      K={K}: n={sK.get('n',0):>5d}, "
                  f"ROI_g {sK.get('roi_gross',0):+.1f}%, "
                  f"ROI_n {sK.get('roi_net',0):+.1f}%, "
                  f"avg_odd {sK.get('avg_combo',0):.2f}")

        # CLV
        clv_K1 = compute_clv(picks_K1, df_m2)
        print(f"    CLV K=1: mean {clv_K1['clv_mean']*100:+.2f}%, "
              f"n={clv_K1['clv_n']}, pos% {clv_K1['clv_pos_pct']:.0f}%")

        detail_results.append({
            **r, "candidate_name": candidate_name,
            "season_rois": season_rois,
            "pos_seasons": pos_seasons,
            "n_seasons": len(season_rois),
            "K_results": roi_by_K,
            "clv": clv_K1,
        })

    # === 3) Karşılaştırma — TRIVOX ile birlikte tablo ===
    print("\n" + "-" * 80)
    print(">>> NIHAI KARSILASTIRMA")
    print("-" * 80)
    # TRIVOX baseline
    trivox = build_K_picks(df, ["T1"], K=1)
    trivox_stats = roi_stats(trivox)
    trivox_clv = compute_clv(trivox, df_m2)
    print(f"\nTRIVOX (T1, K=1):")
    print(f"  n={trivox_stats['n']}, ROI_n {trivox_stats['roi_net']:+.2f}%, "
          f"CLV {trivox_clv['clv_mean']*100:+.2f}%")

    print(f"\nTop 5 Avrupa adaylari:")
    print(f"  {'#':>2s} {'Combo':<18s} {'aday isim':<12s} {'n':>5s} "
          f"{'ROI_n':>7s} {'CLV':>7s} {'sezon+':>6s} {'K=3 ROI_n':>10s}")
    for i, r in enumerate(detail_results):
        roi_K3 = r["K_results"].get(3, {}).get("roi_net", 0)
        clv_str = f"{r['clv']['clv_mean']*100:+.2f}%" if r['clv']['clv_mean'] else "n/a"
        print(f"  {i+1:>2d} {r['name']:<18s} {r['candidate_name']:<12s} "
              f"{r['n']:>5d} {r['roi_net']:>+6.2f}% {clv_str:>7s} "
              f"{r['pos_seasons']:>1d}/{r['n_seasons']:<3d} {roi_K3:>+9.2f}%")

    # === 4) Karar ===
    print("\n" + "=" * 80)
    print("KAPI 0 - TEST 8 VERDICT")
    print("=" * 80)

    # En iyi adayı seç: ROI_n yüksek + sezon stabil + CLV en az ortalama
    best = detail_results[0]
    print(f"\nEn iyi Avrupa modeli adayi: {best['name']} ({best['candidate_name']})")
    print(f"  K=1 ROI_net: {best['roi_net']:+.2f}% (TRIVOX +%{trivox_stats['roi_net']:.2f})")
    print(f"  Sezon pozitif: {best['pos_seasons']}/{best['n_seasons']}")
    print(f"  CLV: {best['clv']['clv_mean']*100:+.2f}%")
    print(f"  K=3 (kombin): {best['K_results'].get(3, {}).get('roi_net', 0):+.2f}%")

    # Markdown rapor
    rapor = ["# KAPI 0 — TEST 8: AVRUPA LIGLERI YENI MODEL ARAYISI\n"]
    rapor.append(f"**Tarih:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}\n")
    rapor.append("**Kullanici:** EUVOX bırakılmıyor, yeni isimde Avrupa modeli olarak yeniden tasarla\n\n")

    rapor.append("## 31 Lig Kombinasyonu — K=1 ROI Brute Force\n\n")
    rapor.append("| # | Combo | n | hit% | avg_odd | ROI_gross | ROI_net |\n")
    rapor.append("|---|---|---|---|---|---|---|\n")
    for i, r in enumerate(combo_results):
        rapor.append(f"| {i+1} | {r['name']} | {r['n']} | {r['hit']*100:.0f}% | "
                     f"{r['avg_combo']:.2f} | {r['roi_gross']:+.2f}% | "
                     f"{r['roi_net']:+.2f}% |\n")

    rapor.append("\n## Top 5 Aday — Detay Analiz\n\n")
    for i, r in enumerate(detail_results):
        rapor.append(f"### {i+1}. {r['name']} ({r['candidate_name']} aday)\n\n")
        rapor.append(f"- K=1 ROI net: **{r['roi_net']:+.2f}%** (n={r['n']})\n")
        rapor.append(f"- Sezon pozitif: {r['pos_seasons']}/{r['n_seasons']}\n")
        clv_str = f"{r['clv']['clv_mean']*100:+.2f}%" if r['clv']['clv_mean'] else "n/a"
        rapor.append(f"- CLV: {clv_str} (n={r['clv']['clv_n']}, pos%{r['clv']['clv_pos_pct']:.0f})\n")
        rapor.append(f"- K=1: {r['K_results'].get(1,{}).get('roi_net',0):+.2f}%\n")
        rapor.append(f"- K=2: {r['K_results'].get(2,{}).get('roi_net',0):+.2f}%\n")
        rapor.append(f"- K=3: {r['K_results'].get(3,{}).get('roi_net',0):+.2f}%\n\n")

    rapor.append(f"\n## En Iyi Aday: {best['name']} ({best['candidate_name']})\n")
    rapor.append(f"\nKesintisiz Avrupa modeli olarak {best['candidate_name']} ismiyle V2 inşaata aday.\n")
    out = YAZILIM / "RAPOR" / "Kapi0_T08_european_model_search.md"
    out.write_text("".join(rapor), encoding="utf-8")
    print(f"\n[OK] Rapor: {out}")


if __name__ == "__main__":
    run()
