"""
Sprint 2.2 — TRIVOX / EUVOX Picks Historical CLV
=====================================================

Mevcut signal_snapshots tablosundaki picks'leri matches_v2 (yeni standardize
tablo) ile join et. Her pick için CLV (Closing Line Value) hesapla.

CLV(pick) = opening_odd / closing_odd - 1
  opening = B365 (matches_v2.opening_*)
  closing = Pinnacle (matches_v2.closing_*)

Pozitif CLV = model picks "değer" bulmuş (closing düşmüş = doğru taraf)
Negatif CLV = model picks "değersiz" (closing yükselmiş = yanlış taraf)

Bu, modelin gerçekten edge ürettiğinin tek "altın standart" kanıtıdır.
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
from trivox_v1 import TrivoxModel, TrivoxConfig, fav_confirmed, normalize_dir


SEASON_CONV = {
    "1718":"2017-18","1819":"2018-19","1920":"2019-20","2021":"2020-21",
    "2122":"2021-22","2223":"2022-23","2324":"2023-24","2425":"2024-25","2526":"2025-26",
}


def load_signal_snapshots() -> pd.DataFrame:
    conn = db.connect()
    df = pd.read_sql_query(
        """SELECT match_uid, league_code, season, kickoff_iso, home_team, away_team,
               odd_1, odd_X, odd_2, odd_open_1, odd_open_X, odd_open_2,
               dir_favorite, dir_anomaly, dir_model, dir_xg, dir_form,
               score_v13, agree_count, result_1x2,
               settled, home_score, away_score, pnl_top3_v13
           FROM signal_snapshots
           WHERE source='football_data' AND settled=1""", conn
    )
    conn.close()
    # Normalize: season '2122' -> '2021-22', kickoff -> YYYY-MM-DD string
    df["season"] = df["season"].astype(str).map(lambda s: SEASON_CONV.get(s, s))
    df["matchday"] = pd.to_datetime(df["kickoff_iso"]).dt.strftime("%Y-%m-%d")
    return df


def load_matches_v2() -> pd.DataFrame:
    conn = db.connect()
    df = pd.read_sql_query(
        """SELECT league_code, season, matchday, home_team, away_team,
               opening_1, opening_X, opening_2,
               closing_1, closing_X, closing_2,
               clv_home, clv_draw, clv_away, clv_avg_1x2
           FROM matches_v2 WHERE is_settled=1""", conn
    )
    conn.close()
    df["matchday"] = df["matchday"].astype(str)
    return df


def opening_for_dir(row, direction: str):
    if direction in ("HOME", "H", "1"): return row.get("opening_1")
    if direction in ("AWAY", "A", "2"): return row.get("opening_2")
    if direction in ("DRAW", "D", "X"): return row.get("opening_X")
    return None


def closing_for_dir(row, direction: str):
    if direction in ("HOME", "H", "1"): return row.get("closing_1")
    if direction in ("AWAY", "A", "2"): return row.get("closing_2")
    if direction in ("DRAW", "D", "X"): return row.get("closing_X")
    return None


def build_picks_with_clv(df_ss: pd.DataFrame, df_m2: pd.DataFrame,
                         leagues: list, min_conf: int = 1, K: int = 3) -> pd.DataFrame:
    """TRIVOX/EUVOX picks oluştur ve matches_v2 ile join ederek CLV ekle."""
    df = df_ss[df_ss["league_code"].isin(leagues)].copy()

    # FAV_CONFIRMED filter
    df["dir_fav_confirmed"] = df.apply(
        lambda r: fav_confirmed(r.to_dict(), min_conf), axis=1
    )
    df = df[df["dir_fav_confirmed"].notna()].copy()
    df = df.sort_values("score_v13", ascending=False)

    # Top-K per matchday × league
    picks = []
    for (md, lg), group in df.groupby(["matchday", "league_code"]):
        topK = group.head(K)
        if len(topK) < K:
            continue
        for _, leg in topK.iterrows():
            picks.append({
                "matchday": str(md), "league_code": lg, "season": leg["season"],
                "home_team": leg["home_team"], "away_team": leg["away_team"],
                "direction": leg["dir_fav_confirmed"],
                "ss_odd_closing": {
                    "HOME": leg["odd_1"], "AWAY": leg["odd_2"], "DRAW": leg["odd_X"],
                }[normalize_dir(leg["dir_fav_confirmed"])],
                "ss_odd_opening": {
                    "HOME": leg["odd_open_1"], "AWAY": leg["odd_open_2"], "DRAW": leg["odd_open_X"],
                }[normalize_dir(leg["dir_fav_confirmed"])],
                "won": (leg["result_1x2"] == {
                    "HOME": "H", "AWAY": "A", "DRAW": "D"
                }[normalize_dir(leg["dir_fav_confirmed"])]),
            })
    df_picks = pd.DataFrame(picks)
    if df_picks.empty:
        return df_picks

    # matches_v2 ile join (lig+sezon+matchday+home+away)
    df_picks = df_picks.merge(
        df_m2,
        on=["league_code", "season", "matchday", "home_team", "away_team"],
        how="left",
        suffixes=("", "_m2"),
    )
    # CLV from matches_v2 direction-specific
    def m2_opening(r):
        d = normalize_dir(r["direction"])
        if d == "HOME": return r["opening_1"]
        if d == "AWAY": return r["opening_2"]
        if d == "DRAW": return r["opening_X"]
        return None
    def m2_closing(r):
        d = normalize_dir(r["direction"])
        if d == "HOME": return r["closing_1"]
        if d == "AWAY": return r["closing_2"]
        if d == "DRAW": return r["closing_X"]
        return None

    df_picks["pick_open"] = df_picks.apply(m2_opening, axis=1)
    df_picks["pick_close"] = df_picks.apply(m2_closing, axis=1)
    df_picks["pick_clv"] = (df_picks["pick_open"] / df_picks["pick_close"]) - 1
    return df_picks


def report_picks(name: str, df_picks: pd.DataFrame):
    print(f"\n=== {name} ===")
    if df_picks.empty:
        print("  (boş pick set)")
        return
    matched = df_picks["pick_clv"].notna().sum()
    print(f"  Toplam pick: {len(df_picks)}")
    print(f"  matches_v2 join: {matched}/{len(df_picks)} ({matched/len(df_picks)*100:.0f}%)")
    if matched == 0:
        print("  join match yok — takım ismi farkı olabilir")
        return

    clv = df_picks["pick_clv"].dropna()
    print(f"  CLV mean : {clv.mean()*100:+.3f}%")
    print(f"  CLV median: {clv.median()*100:+.3f}%")
    print(f"  CLV > 0  : {(clv > 0).sum()}/{len(clv)} ({(clv>0).mean()*100:.0f}%)")
    print(f"  CLV stdev: {clv.std()*100:.2f}%")

    # t-test on CLV != 0
    n = len(clv); mean = clv.mean(); std = clv.std()
    se = std / np.sqrt(n) if n > 1 else 0
    t = mean / se if se > 0 else 0
    # Two-tailed p with df=n-1
    from math import erf, sqrt
    # crude normal approx (n large)
    z = abs(t)
    p_approx = 2 * (1 - 0.5 * (1 + erf(z / sqrt(2))))
    print(f"  t-stat (vs 0): t={t:.3f}, p~{p_approx:.4f}")

    # Win rate ile CLV korelasyonu
    sub = df_picks.loc[clv.index]
    won_mask = sub["won"].astype(bool)
    if won_mask.any() and (~won_mask).any():
        wr_won = clv[won_mask].mean()
        wr_lost = clv[~won_mask].mean()
        print(f"  CLV won-legs   : {wr_won*100:+.3f}%  (n={won_mask.sum()})")
        print(f"  CLV lost-legs  : {wr_lost*100:+.3f}%  (n={(~won_mask).sum()})")
        print(f"  Win-rate Delta : {(wr_won - wr_lost)*100:+.3f}pp")


def run():
    print("=" * 70)
    print("Sprint 2.2 — TRIVOX / EUVOX Historical Picks CLV")
    print("=" * 70)

    df_ss = load_signal_snapshots()
    df_m2 = load_matches_v2()
    print(f"signal_snapshots settled: {len(df_ss)}")
    print(f"matches_v2 settled:       {len(df_m2)}")

    # TRIVOX picks (T1, K=3, min_conf=1)
    trivox = build_picks_with_clv(df_ss, df_m2, leagues=["T1"], min_conf=1, K=3)
    report_picks("TRIVOX v1.0 picks CLV (T1 only)", trivox)

    # EUVOX picks (6 lig, K=3, min_conf=1)
    euvox = build_picks_with_clv(df_ss, df_m2,
                                 leagues=["T1","E0","D1","SP1","I1","F1"],
                                 min_conf=1, K=3)
    report_picks("EUVOX v1.1 picks CLV (6 lig)", euvox)

    # TRIVOX v1.2 (min_conf=2)
    trivox_v12 = build_picks_with_clv(df_ss, df_m2, leagues=["T1"], min_conf=2, K=3)
    report_picks("TRIVOX v1.2 picks CLV (T1, min_conf=2)", trivox_v12)


if __name__ == "__main__":
    run()
