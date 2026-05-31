"""
KAPI 0 — TEST 1: K=1 BASELINE
================================

Komite Raporu madde 32 + madde 60:
> "Eğer K=1 negatif ve K=3 pozitif ise edge **kombin varyansı**ndan
>  geliyor (lottery), gerçek edge değil. Pilot durdur."

Bu test BLOKLAYICI:
  - K=1 ROI > 0 ve K=1 CLV ~ K=3 CLV → edge gerçek, devam
  - K=1 ROI ≤ 0 → edge lottery, MODEL EMEKLİYE

İki model:
  - TRIVOX (T1-only, FAV_CONFIRMED, min_conf=1)
  - EUVOX (6-lig, FAV_CONFIRMED, min_conf=1)

Her biri için K=1, K=2, K=3 ROI + CLV ölçümü.

Output:
  - Console summary
  - RAPOR/Kapi0_T01_K1_baseline.md
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


def load_signal_snapshots() -> pd.DataFrame:
    conn = db.connect()
    df = pd.read_sql_query(
        """SELECT league_code, season, kickoff_iso, home_team, away_team,
               odd_1, odd_X, odd_2, odd_open_1, odd_open_X, odd_open_2,
               dir_favorite, dir_anomaly, dir_model, dir_xg, dir_form,
               score_v13, result_1x2, settled
           FROM signal_snapshots
           WHERE source='football_data' AND settled=1""", conn
    )
    conn.close()
    df["season"] = df["season"].astype(str).map(lambda s: SEASON_CONV.get(s, s))
    df["matchday"] = pd.to_datetime(df["kickoff_iso"]).dt.strftime("%Y-%m-%d")
    return df


def load_matches_v2() -> pd.DataFrame:
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


def get_odd(row, direction, prefix="odd"):
    """row['odd_1']/['odd_X']/['odd_2'] gibi alanları al."""
    d = normalize_dir(direction)
    if d == "HOME": return row.get(f"{prefix}_1")
    if d == "AWAY": return row.get(f"{prefix}_2")
    if d == "DRAW": return row.get(f"{prefix}_X")
    return None


def did_win(row, direction):
    d = normalize_dir(direction)
    if d == "HOME": return row.get("result_1x2") == "H"
    if d == "AWAY": return row.get("result_1x2") == "A"
    if d == "DRAW": return row.get("result_1x2") == "D"
    return False


def build_K_picks(df: pd.DataFrame, leagues: list, K: int,
                  min_conf: int = 1, stake: float = 1000.0,
                  tax_rate: float = 0.10) -> pd.DataFrame:
    """K-leg combo picks oluştur ve ROI hesapla."""
    df = df[df["league_code"].isin(leagues)].copy()
    df["dir_fav_confirmed"] = df.apply(
        lambda r: fav_confirmed(r.to_dict(), min_conf), axis=1
    )
    df = df[df["dir_fav_confirmed"].notna()].copy()
    df = df.sort_values("score_v13", ascending=False)

    kupons = []
    for (md, lg), group in df.groupby(["matchday", "league_code"]):
        topK = group.head(K)
        if len(topK) < K:
            continue
        combo_odd = 1.0
        all_won = True
        leg_data = []
        for _, leg in topK.iterrows():
            d = leg["dir_fav_confirmed"]
            o = get_odd(leg.to_dict(), d, "odd")
            o_open = get_odd(leg.to_dict(), d, "odd_open")
            w = did_win(leg.to_dict(), d)
            if not o or o < 1.01:
                combo_odd = None
                break
            combo_odd *= o
            if not w:
                all_won = False
            leg_data.append({
                "matchday": str(md), "league": lg, "season": leg["season"],
                "home": leg["home_team"], "away": leg["away_team"],
                "direction": d, "closing_odd": o, "opening_odd": o_open,
                "won": w,
            })
        if combo_odd is None:
            continue
        kupons.append({
            "matchday": str(md), "league": lg,
            "K": K, "combo_odd": combo_odd, "won": all_won,
            "stake": stake,
            "pnl_gross": stake * (combo_odd - 1) if all_won else -stake,
            "pnl_net": (
                stake * (combo_odd - 1) * (1 - tax_rate)
                if all_won else -stake
            ),
            "legs": leg_data,
        })
    return pd.DataFrame(kupons)


def summarize(name: str, kupons: pd.DataFrame) -> dict:
    if kupons.empty:
        return {"name": name, "n": 0}
    n = len(kupons); n_won = int(kupons["won"].sum())
    stake_tot = float(kupons["stake"].sum())
    pnl_g = float(kupons["pnl_gross"].sum())
    pnl_n = float(kupons["pnl_net"].sum())
    return {
        "name": name, "n": n, "n_won": n_won,
        "hit_rate": n_won / n,
        "avg_combo": float(kupons["combo_odd"].mean()),
        "stake_tot": stake_tot,
        "pnl_gross": pnl_g, "pnl_net": pnl_n,
        "roi_gross": pnl_g / stake_tot * 100 if stake_tot else 0,
        "roi_net": pnl_n / stake_tot * 100 if stake_tot else 0,
    }


def compute_picks_clv(kupons: pd.DataFrame, df_m2: pd.DataFrame) -> tuple:
    """Tüm leg'lerin CLV'sini matches_v2 üzerinden hesapla."""
    if kupons.empty:
        return None, None, 0
    all_legs = []
    for _, k in kupons.iterrows():
        for leg in k["legs"]:
            all_legs.append(leg)
    legs_df = pd.DataFrame(all_legs)
    if legs_df.empty:
        return None, None, 0
    legs_df = legs_df.rename(columns={
        "home": "home_team", "away": "away_team", "league": "league_code",
    })
    merged = legs_df.merge(
        df_m2,
        on=["league_code", "season", "matchday", "home_team", "away_team"],
        how="left",
    )
    def m2_open(r):
        d = normalize_dir(r["direction"])
        if d == "HOME": return r["opening_1"]
        if d == "AWAY": return r["opening_2"]
        if d == "DRAW": return r["opening_X"]
        return None
    def m2_close(r):
        d = normalize_dir(r["direction"])
        if d == "HOME": return r["closing_1"]
        if d == "AWAY": return r["closing_2"]
        if d == "DRAW": return r["closing_X"]
        return None
    merged["pick_open"] = merged.apply(m2_open, axis=1)
    merged["pick_close"] = merged.apply(m2_close, axis=1)
    merged["pick_clv"] = merged["pick_open"] / merged["pick_close"] - 1
    clv = merged["pick_clv"].dropna()
    return clv.mean() if len(clv) else None, clv.std() if len(clv) else None, len(clv)


def t_stat(mean, std, n):
    if n < 2 or std == 0 or std is None:
        return None, None
    from math import sqrt, erf
    se = std / sqrt(n)
    t = mean / se if se > 0 else 0
    z = abs(t)
    p = 2 * (1 - 0.5 * (1 + erf(z / sqrt(2))))
    return t, p


def run():
    print("=" * 78)
    print("KAPI 0 — TEST 1: K=1 BASELINE")
    print("Komite Madde 32 + 60: 'K=1 negatif, K=3 pozitif -> lottery, edge yok'")
    print("=" * 78)

    df_ss = load_signal_snapshots()
    df_m2 = load_matches_v2()
    print(f"signal_snapshots settled: {len(df_ss)}")
    print(f"matches_v2 settled:       {len(df_m2)}\n")

    results = []

    # === TRIVOX (T1-only) ===
    print("-" * 78)
    print(">>> TRIVOX (T1 only, FAV_CONFIRMED, min_conf=1)")
    print("-" * 78)
    print(f"{'K':>3s} {'n':>4s} {'won':>4s} {'hit':>5s} {'avg_odd':>8s} "
          f"{'ROI_g':>7s} {'ROI_n':>7s} {'CLV_mean':>9s} {'CLV_n':>6s} {'CLV_p':>7s}")
    for K in (1, 2, 3):
        kp = build_K_picks(df_ss, ["T1"], K=K, min_conf=1)
        s = summarize(f"TRIVOX K={K}", kp)
        clv_mean, clv_std, clv_n = compute_picks_clv(kp, df_m2)
        t, p = t_stat(clv_mean, clv_std, clv_n) if clv_mean else (None, None)
        clv_str = f"{clv_mean*100:+.2f}%" if clv_mean is not None else "  n/a"
        p_str = f"{p:.4f}" if p is not None else "  n/a"
        print(f"{K:>3d} {s.get('n',0):>4d} {s.get('n_won',0):>4d} "
              f"{s.get('hit_rate',0)*100:>4.0f}% "
              f"{s.get('avg_combo',0):>7.2f} "
              f"{s.get('roi_gross',0):>+6.1f}% {s.get('roi_net',0):>+6.1f}% "
              f"{clv_str:>9s} {clv_n:>6d} {p_str:>7s}")
        results.append({"model": "TRIVOX", "K": K, **s,
                        "clv_mean": clv_mean, "clv_n": clv_n,
                        "clv_p": p})

    # === EUVOX (6-lig) ===
    print()
    print("-" * 78)
    print(">>> EUVOX (6 lig, FAV_CONFIRMED, min_conf=1)")
    print("-" * 78)
    print(f"{'K':>3s} {'n':>4s} {'won':>4s} {'hit':>5s} {'avg_odd':>8s} "
          f"{'ROI_g':>7s} {'ROI_n':>7s} {'CLV_mean':>9s} {'CLV_n':>6s} {'CLV_p':>7s}")
    for K in (1, 2, 3):
        kp = build_K_picks(df_ss, ["T1","E0","D1","SP1","I1","F1"], K=K, min_conf=1)
        s = summarize(f"EUVOX K={K}", kp)
        clv_mean, clv_std, clv_n = compute_picks_clv(kp, df_m2)
        t, p = t_stat(clv_mean, clv_std, clv_n) if clv_mean else (None, None)
        clv_str = f"{clv_mean*100:+.2f}%" if clv_mean is not None else "  n/a"
        p_str = f"{p:.4f}" if p is not None else "  n/a"
        print(f"{K:>3d} {s.get('n',0):>4d} {s.get('n_won',0):>4d} "
              f"{s.get('hit_rate',0)*100:>4.0f}% "
              f"{s.get('avg_combo',0):>7.2f} "
              f"{s.get('roi_gross',0):>+6.1f}% {s.get('roi_net',0):>+6.1f}% "
              f"{clv_str:>9s} {clv_n:>6d} {p_str:>7s}")
        results.append({"model": "EUVOX", "K": K, **s,
                        "clv_mean": clv_mean, "clv_n": clv_n,
                        "clv_p": p})

    # === KARAR ===
    print()
    print("=" * 78)
    print("KAPI 0 — TEST 1 KARARI")
    print("=" * 78)

    trivox_K1 = next(r for r in results if r["model"]=="TRIVOX" and r["K"]==1)
    trivox_K3 = next(r for r in results if r["model"]=="TRIVOX" and r["K"]==3)
    euvox_K1 = next(r for r in results if r["model"]=="EUVOX" and r["K"]==1)
    euvox_K3 = next(r for r in results if r["model"]=="EUVOX" and r["K"]==3)

    def verdict(K1, K3, name):
        roi1 = K1.get("roi_net", 0)
        roi3 = K3.get("roi_net", 0)
        clv1 = K1.get("clv_mean") or 0
        clv3 = K3.get("clv_mean") or 0
        print(f"\n[{name}]")
        print(f"  K=1 ROI_net: {roi1:+.2f}%   K=3 ROI_net: {roi3:+.2f}%")
        print(f"  K=1 CLV    : {clv1*100:+.2f}%   K=3 CLV    : {clv3*100:+.2f}%")
        if roi1 <= 0 and roi3 > 0:
            print(f"  *** RED FLAG: K=1<=0 and K=3>0 -> LOTTERY edge!")
            return "FAIL_LOTTERY"
        elif roi1 > 0 and clv1 > 0:
            print(f"  PASS: K=1 ROI positive and CLV positive -> real edge")
            return "PASS"
        elif roi1 > 0 and clv1 <= 0:
            print(f"  AMBIGUOUS: ROI positive but CLV negative -> sample variance")
            return "AMBIGUOUS"
        else:
            print(f"  FAIL: K=1 ROI<=0 -> no edge anywhere")
            return "FAIL_NO_EDGE"

    v_trivox = verdict(trivox_K1, trivox_K3, "TRIVOX")
    v_euvox = verdict(euvox_K1, euvox_K3, "EUVOX")

    print()
    print("=" * 78)
    print("OZET")
    print("=" * 78)
    print(f"TRIVOX karari: {v_trivox}")
    print(f"EUVOX  karari: {v_euvox}")

    # Markdown rapor
    rapor = []
    rapor.append("# KAPI 0 — TEST 1: K=1 BASELINE\n")
    rapor.append(f"**Tarih:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}\n")
    rapor.append("**Komite Madde 32 + 60:** \"K=1 ROI ≤ 0 ve K=3 ROI > 0 ise edge **lottery**.\"\n")
    rapor.append("\n## Sonuç Matrisi\n\n")
    rapor.append("| Model | K | n | hit% | avg_odd | ROI_gross | ROI_net | CLV mean | CLV n | CLV p |\n")
    rapor.append("|---|---|---|---|---|---|---|---|---|---|\n")
    for r in results:
        clv_str = f"{r['clv_mean']*100:+.2f}%" if r.get("clv_mean") is not None else "n/a"
        p_str = f"{r['clv_p']:.4f}" if r.get("clv_p") is not None else "n/a"
        rapor.append(
            f"| {r['model']} | {r['K']} | {r.get('n',0)} | "
            f"{r.get('hit_rate',0)*100:.0f}% | {r.get('avg_combo',0):.2f} | "
            f"{r.get('roi_gross',0):+.2f}% | {r.get('roi_net',0):+.2f}% | "
            f"{clv_str} | {r.get('clv_n',0)} | {p_str} |\n"
        )
    rapor.append(f"\n## Karar\n\n- TRIVOX: **{v_trivox}**\n- EUVOX: **{v_euvox}**\n")
    if v_trivox == "FAIL_LOTTERY":
        rapor.append("\n### TRIVOX FAIL_LOTTERY Anlamı\n")
        rapor.append("K=3 ROI pozitif görünüyor ama K=1 ROI ≤ 0 → edge gerçek değil, ")
        rapor.append("kombin varyansından doğan **şanslı outliers**. ")
        rapor.append("Model emekliye, yeni baştan tasarım gerekli.\n")
    if v_trivox == "PASS":
        rapor.append("\n### TRIVOX PASS Anlamı\n")
        rapor.append("K=1 baseline pozitif ve CLV pozitif → edge tek-bahis düzeyinde de var. ")
        rapor.append("V2 retrain için meşru zemin var.\n")

    out = YAZILIM / "RAPOR" / "Kapi0_T01_K1_baseline.md"
    out.write_text("".join(rapor), encoding="utf-8")
    print(f"\n[OK] Rapor: {out}")


if __name__ == "__main__":
    run()
