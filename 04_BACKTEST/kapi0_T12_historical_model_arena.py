"""
KAPI 0 — TEST 12: TARİHSEL MODEL ARENA
========================================

Kullanici: "Bizim bu zamana kadar egittigimiz MODELLERI bu acilama gore
            (yeni paradigma) TEST ETMENI de istiyorum"

Tüm tarihsel model versiyonlarımızı tek bir arenaya çıkar:
  - Eski paradigma: Flat ROI (her hafta sabit stake)
  - Yeni paradigma: Q5+agree2 hit rate (selective sniper)

MODELLER:
  M01: TRIVOX v1.0 (T1, FAV_CONFIRMED, min_conf=1, K=3)
  M02: TRIVOX v1.2 (T1, FAV_CONFIRMED, min_conf=2, K=3)
  M03: TRIVOX v1.2-soft (T1, FAV_CONFIRMED, min_conf=2, K=1)  YENİ
  M04: EUVOX v1.0 (6-lig, FAV_CONFIRMED, min_conf=1, K=3)
  M05: EUVOX v1.1 (6-lig adaptive)
  M06: AGREE 2/3 (T1, agree_count>=2, K=3)
  M07: K=3 strict (6-lig, ≥2 confirmers, T07)
  M08: v1.3 sweet-spot (1.30-2.50 odd, T1)
  M09: DUOVOX YENI (E0+SP1, K=1)
  M10: TRIOVOX YENI (E0+SP1+D1, K=1)
  M11: TRIVOX-Q5sniper (T1, K=1, Q5+agree2 only)
  M12: DUOVOX-Q5sniper (E0+SP1, K=1, Q5+agree2 only)
  M13: TRIOVOX-Q5sniper (E0+SP1+D1, K=1, Q5+agree2 only)

Her model için ölç:
  - n (toplam pick)
  - hit rate
  - ROI_gross / ROI_net
  - CLV (matches_v2 ile join)
  - Sezonsal stabilite (5 sezon)
  - Yeni paradigma: Q5+agree2 alt-segment
"""
from __future__ import annotations

import sys
import sqlite3
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
               odd_1, odd_X, odd_2, odd_open_1, odd_open_X, odd_open_2,
               dir_favorite, dir_anomaly, dir_model, dir_xg, dir_form,
               score_v13, agree_count, result_1x2, settled
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


def agree_count_consensus(row, threshold=2):
    """≥N sinyal aynı yöne işaret ediyor mu?"""
    sigs = [row.get("dir_anomaly"), row.get("dir_model"),
            row.get("dir_xg"), row.get("dir_form")]
    counts = {}
    for s in sigs:
        if not s: continue
        n = normalize_dir(s)
        counts[n] = counts.get(n, 0) + 1
    if not counts:
        return None
    best_dir, best_count = max(counts.items(), key=lambda x: x[1])
    return best_dir if best_count >= threshold else None


# ============================================================
# MODEL CONFIGS
# ============================================================

MODELS = [
    # Adı, lig, min_conf veya agree_thr, K, sweet_spot, q5_only
    {"id":"M01","name":"TRIVOX v1.0","filter":"FAV","leagues":["T1"],"thr":1,"K":3,"sweet":None,"q5":False},
    {"id":"M02","name":"TRIVOX v1.2","filter":"FAV","leagues":["T1"],"thr":2,"K":3,"sweet":None,"q5":False},
    {"id":"M03","name":"TRIVOX v1.2-soft","filter":"FAV","leagues":["T1"],"thr":2,"K":1,"sweet":None,"q5":False},
    {"id":"M04","name":"EUVOX v1.0","filter":"FAV","leagues":["T1","E0","D1","SP1","I1","F1"],"thr":1,"K":3,"sweet":None,"q5":False},
    {"id":"M05","name":"EUVOX v1.1 adaptive","filter":"FAV","leagues":["T1","E0","D1","SP1","I1","F1"],"thr":1,"K":3,"sweet":None,"q5":False},
    {"id":"M06","name":"AGREE 2/3","filter":"AGREE","leagues":["T1"],"thr":2,"K":3,"sweet":None,"q5":False},
    {"id":"M07","name":"K=3 strict","filter":"FAV","leagues":["T1","E0","D1","SP1","I1","F1"],"thr":2,"K":3,"sweet":None,"q5":False},
    {"id":"M08","name":"v1.3 sweet-spot","filter":"FAV","leagues":["T1"],"thr":1,"K":3,"sweet":(1.30, 2.50),"q5":False},
    {"id":"M09","name":"DUOVOX K=1","filter":"FAV","leagues":["E0","SP1"],"thr":1,"K":1,"sweet":None,"q5":False},
    {"id":"M10","name":"TRIOVOX K=1","filter":"FAV","leagues":["E0","SP1","D1"],"thr":1,"K":1,"sweet":None,"q5":False},
    {"id":"M11","name":"TRIVOX Q5+a2","filter":"FAV","leagues":["T1"],"thr":1,"K":1,"sweet":None,"q5":True},
    {"id":"M12","name":"DUOVOX Q5+a2","filter":"FAV","leagues":["E0","SP1"],"thr":1,"K":1,"sweet":None,"q5":True},
    {"id":"M13","name":"TRIOVOX Q5+a2","filter":"FAV","leagues":["E0","SP1","D1"],"thr":1,"K":1,"sweet":None,"q5":True},
    {"id":"M14","name":"MONOVOX-E0 Q5+a2","filter":"FAV","leagues":["E0"],"thr":1,"K":1,"sweet":None,"q5":True},
    {"id":"M15","name":"MONOVOX-SP1 Q5+a2","filter":"FAV","leagues":["SP1"],"thr":1,"K":1,"sweet":None,"q5":True},
]


def build_kupons(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Bir modelin tüm kuponlarını oluştur."""
    df = df[df["league_code"].isin(cfg["leagues"])].copy()

    # Filter
    if cfg["filter"] == "FAV":
        df["dir_pick"] = df.apply(
            lambda r: fav_confirmed(r.to_dict(), cfg["thr"]), axis=1
        )
    elif cfg["filter"] == "AGREE":
        df["dir_pick"] = df.apply(
            lambda r: agree_count_consensus(r.to_dict(), cfg["thr"]), axis=1
        )
    df = df[df["dir_pick"].notna()].copy()
    df = df.sort_values("score_v13", ascending=False)

    # Sweet spot filter
    if cfg.get("sweet"):
        lo, hi = cfg["sweet"]
        def in_sweet(r):
            o = get_odd(r.to_dict(), r["dir_pick"])
            return o and lo <= o <= hi
        df = df[df.apply(in_sweet, axis=1)]

    # Build K-leg kupons
    K = cfg["K"]
    kupons = []
    for (md, lg), group in df.groupby(["matchday", "league_code"]):
        topK = group.head(K)
        if len(topK) < K: continue
        combo_odd = 1.0; all_won = True; legs = []
        for _, leg in topK.iterrows():
            d = leg["dir_pick"]
            o = get_odd(leg.to_dict(), d)
            w = did_win(leg.to_dict(), d)
            if not o or o < 1.01: combo_odd = None; break
            combo_odd *= o
            if not w: all_won = False
            legs.append({
                "matchday": str(md), "league": lg, "season": leg["season"],
                "home_team": leg["home_team"], "away_team": leg["away_team"],
                "direction": d, "odd": o, "won": w,
                "score": float(leg["score_v13"]),
                "agree_count": int(leg["agree_count"] or 0),
            })
        if combo_odd is None: continue
        # Q5+agree2 filter (sadece K=1 için, eğer q5=True)
        if cfg.get("q5") and K == 1:
            # legs[0]'da quintile bilgisi yok, global score quintile gerek
            # Geçici: agree_count>=2 mark
            if legs[0]["agree_count"] < 2:
                continue
        kupons.append({
            "matchday": str(md), "league": lg,
            "season": legs[0]["season"] if legs else None,
            "K": K, "combo_odd": combo_odd, "won": all_won,
            "legs": legs,
            "score": legs[0]["score"] if legs else 0,
            "agree_count": legs[0]["agree_count"] if legs else 0,
        })
    return pd.DataFrame(kupons)


def apply_q5_filter(kupons: pd.DataFrame) -> pd.DataFrame:
    """Tüm kuponları global score quintile'a göre Q5 only filtrele."""
    if kupons.empty: return kupons
    kupons = kupons.copy()
    try:
        kupons["q"] = pd.qcut(kupons["score"], 5, labels=["Q1","Q2","Q3","Q4","Q5"])
    except Exception:
        return kupons
    return kupons[kupons["q"] == "Q5"]


def roi_stats(kupons: pd.DataFrame, stake=1000.0, tax=0.10):
    if kupons.empty: return {"n":0,"hit":0,"avg_odd":0,"roi_gross":0,"roi_net":0}
    n = len(kupons); n_won = int(kupons["won"].sum())
    won = kupons[kupons["won"]]
    pnl_g = (stake * (won["combo_odd"] - 1)).sum() - stake * (n - n_won)
    pnl_n = (stake * (won["combo_odd"] - 1) * (1-tax)).sum() - stake * (n - n_won)
    return {
        "n": n, "n_won": n_won, "hit": n_won/n,
        "avg_odd": float(kupons["combo_odd"].mean()),
        "roi_gross": pnl_g/(stake*n)*100,
        "roi_net": pnl_n/(stake*n)*100,
    }


def compute_clv(kupons, df_m2):
    if kupons.empty: return None
    all_legs = []
    for _, k in kupons.iterrows():
        for leg in k["legs"]:
            all_legs.append(leg)
    legs_df = pd.DataFrame(all_legs).rename(
        columns={"league":"league_code"})
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
    return clv.mean() if len(clv) else None


def seasonal_consistency(kupons):
    """Sezonsal pozitif ROI sayısı."""
    if kupons.empty: return (0, 0)
    pos = 0; total = 0
    for ss in sorted(kupons["season"].unique()):
        sub = kupons[kupons["season"] == ss]
        if len(sub) < 5: continue
        total += 1
        s = roi_stats(sub)
        if s["roi_net"] > 0: pos += 1
    return (pos, total)


def run():
    print("=" * 100)
    print("KAPI 0 - TEST 12: TARIHSEL MODEL ARENA")
    print("Tum eski + yeni modellerin yeni paradigma testi")
    print("=" * 100)

    df = load_data()
    df_m2 = load_m2()
    print(f"signal_snapshots: {len(df)}, matches_v2: {len(df_m2)}\n")

    # ESKI PARADIGMA — Tüm modeller flat K=K stake ROI
    print("-" * 100)
    print(">>> ESKI PARADIGMA — Flat 1000 TL/hafta, K=K kupon")
    print("-" * 100)
    print(f"  {'ID':>3s} {'Model':<22s} {'n':>5s} {'hit%':>5s} {'avg_odd':>8s} "
          f"{'ROI_g':>7s} {'ROI_n':>7s} {'CLV':>7s} {'sezon+':>7s}")

    arena = []
    for cfg in MODELS:
        kupons = build_kupons(df, cfg)
        s = roi_stats(kupons)
        clv = compute_clv(kupons, df_m2) if not kupons.empty else None
        pos, total = seasonal_consistency(kupons)
        clv_str = f"{clv*100:+.2f}%" if clv is not None else "n/a"
        sez_str = f"{pos}/{total}" if total else "n/a"
        print(f"  {cfg['id']:>3s} {cfg['name']:<22s} {s['n']:>5d} "
              f"{s['hit']*100:>4.0f}% {s['avg_odd']:>7.2f} "
              f"{s['roi_gross']:>+6.1f}% {s['roi_net']:>+6.1f}% "
              f"{clv_str:>7s} {sez_str:>7s}")
        arena.append({
            "id": cfg["id"], "name": cfg["name"], "leagues": "+".join(cfg["leagues"]),
            "K": cfg["K"], "filter": cfg["filter"], "thr": cfg["thr"],
            "n": s["n"], "hit": s["hit"], "avg_odd": s["avg_odd"],
            "roi_gross": s["roi_gross"], "roi_net": s["roi_net"],
            "clv": clv, "pos_seasons": pos, "n_seasons": total,
        })

    # YENI PARADIGMA — Q5+agree2 filter
    print("\n" + "-" * 100)
    print(">>> YENI PARADIGMA — Q5 (top 20% score) + agree_count>=2 SELECTIVE")
    print(">>> Trader: 'En guclu sinyal anlarinda buyuk oyna, gerisinde pas'")
    print("-" * 100)
    print(f"  {'ID':>3s} {'Model':<22s} {'n':>5s} {'hit%':>5s} {'avg_odd':>8s} "
          f"{'ROI_g':>7s} {'ROI_n':>7s} {'CLV':>7s} {'sezon+':>7s}")

    arena_q5 = []
    for cfg in MODELS:
        kupons = build_kupons(df, cfg)
        # Apply Q5 + agree>=2 filter
        if not kupons.empty:
            kupons = kupons[kupons["agree_count"] >= 2]
            kupons = apply_q5_filter(kupons)
        s = roi_stats(kupons)
        clv = compute_clv(kupons, df_m2) if not kupons.empty else None
        pos, total = seasonal_consistency(kupons)
        clv_str = f"{clv*100:+.2f}%" if clv is not None else "n/a"
        sez_str = f"{pos}/{total}" if total else "n/a"
        print(f"  {cfg['id']:>3s} {cfg['name']:<22s} {s['n']:>5d} "
              f"{s['hit']*100:>4.0f}% {s['avg_odd']:>7.2f} "
              f"{s['roi_gross']:>+6.1f}% {s['roi_net']:>+6.1f}% "
              f"{clv_str:>7s} {sez_str:>7s}")
        arena_q5.append({
            "id": cfg["id"], "name": cfg["name"],
            "n": s["n"], "hit": s["hit"], "roi_net": s["roi_net"],
            "clv": clv,
        })

    # === KAZANANLAR ===
    print("\n" + "=" * 100)
    print(">>> ESKI PARADIGMA — EN IYI 5 (ROI net)")
    print("=" * 100)
    arena_sorted = sorted([a for a in arena if a["n"] >= 30],
                          key=lambda x: x["roi_net"], reverse=True)
    for i, a in enumerate(arena_sorted[:5]):
        clv_str = f"{a['clv']*100:+.2f}%" if a["clv"] else "n/a"
        print(f"  {i+1}. [{a['id']}] {a['name']:<22s}: ROI_n {a['roi_net']:+.2f}%, "
              f"n={a['n']}, hit %{a['hit']*100:.0f}, CLV {clv_str}, "
              f"sezon {a['pos_seasons']}/{a['n_seasons']}")

    print("\n>>> YENI PARADIGMA — EN IYI 5 (Hit rate, Q5+a2)")
    arena_q5_sorted = sorted([a for a in arena_q5 if a["n"] >= 5],
                              key=lambda x: x["hit"], reverse=True)
    for i, a in enumerate(arena_q5_sorted[:5]):
        clv_str = f"{a['clv']*100:+.2f}%" if a["clv"] else "n/a"
        print(f"  {i+1}. [{a['id']}] {a['name']:<22s}: hit %{a['hit']*100:.0f}, "
              f"n={a['n']}, ROI_n {a['roi_net']:+.2f}%, CLV {clv_str}")

    # === ARENA VERDICT ===
    print("\n" + "=" * 100)
    print("ARENA VERDICT")
    print("=" * 100)
    print(f"\n5 KRITIK SORU:")
    # 1. En yüksek ROI (eski)
    best_roi = arena_sorted[0] if arena_sorted else None
    if best_roi:
        print(f"  1. En yuksek ROI_net (eski): [{best_roi['id']}] {best_roi['name']} "
              f"{best_roi['roi_net']:+.2f}%")
    # 2. En yüksek hit (Q5+a2)
    best_hit = arena_q5_sorted[0] if arena_q5_sorted else None
    if best_hit:
        print(f"  2. En yuksek Q5+a2 hit (yeni): [{best_hit['id']}] {best_hit['name']} "
              f"%{best_hit['hit']*100:.0f}")
    # 3. En çok pozitif sezon
    best_sez = max([a for a in arena if a["n_seasons"] >= 3],
                   key=lambda x: x["pos_seasons"]/max(1,x["n_seasons"]), default=None)
    if best_sez:
        print(f"  3. En cok pozitif sezon: [{best_sez['id']}] {best_sez['name']} "
              f"{best_sez['pos_seasons']}/{best_sez['n_seasons']}")
    # 4. En iyi CLV
    arena_with_clv = [a for a in arena if a["clv"] is not None and a["n"] >= 30]
    best_clv = max(arena_with_clv, key=lambda x: x["clv"], default=None)
    if best_clv:
        print(f"  4. En iyi CLV: [{best_clv['id']}] {best_clv['name']} "
              f"{best_clv['clv']*100:+.2f}%")
    # 5. En cok sample
    best_n = max(arena, key=lambda x: x["n"], default=None)
    if best_n:
        print(f"  5. En cok pick: [{best_n['id']}] {best_n['name']} n={best_n['n']}")

    print(f"\n>>> KARSILASTIRMA: ESKI vs YENI PARADIGMA")
    print(f"{'Model':<22s} {'Eski ROI_n':>11s} {'Yeni Q5a2 hit':>15s} {'Verdict':>20s}")
    for cfg in MODELS:
        a_old = next((a for a in arena if a["id"] == cfg["id"]), None)
        a_new = next((a for a in arena_q5 if a["id"] == cfg["id"]), None)
        if not a_old or not a_new: continue
        eski = a_old["roi_net"]; yeni_hit = a_new["hit"]*100
        # Verdict
        if yeni_hit >= 70 and a_new["n"] >= 5:
            verdict = "** YENI PARADIGMA HARIKA"
        elif yeni_hit >= 60 and a_new["n"] >= 5:
            verdict = "* Yeni iyi"
        elif eski > 5:
            verdict = "Eski iyi olabilir"
        else:
            verdict = "Marjinal"
        print(f"{cfg['name']:<22s} {eski:>+9.2f}% {yeni_hit:>13.0f}% {verdict:>20s}")

    # === Markdown rapor ===
    rapor = ["# KAPI 0 — TEST 12: TARIHSEL MODEL ARENA\n"]
    rapor.append(f"**Tarih:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}\n\n")
    rapor.append("## Eski Paradigma — Flat K=K, 1000 TL/hafta\n\n")
    rapor.append("| ID | Model | n | hit% | avg_odd | ROI_g | ROI_n | CLV | sezon+/sezon |\n")
    rapor.append("|---|---|---|---|---|---|---|---|---|\n")
    for a in arena:
        clv_str = f"{a['clv']*100:+.2f}%" if a["clv"] else "n/a"
        rapor.append(f"| {a['id']} | {a['name']} | {a['n']} | {a['hit']*100:.0f}% | "
                     f"{a['avg_odd']:.2f} | {a['roi_gross']:+.2f}% | {a['roi_net']:+.2f}% | "
                     f"{clv_str} | {a['pos_seasons']}/{a['n_seasons']} |\n")
    rapor.append("\n## Yeni Paradigma — Q5 + agree>=2 SELECTIVE\n\n")
    rapor.append("| ID | Model | n | hit% | avg_odd | ROI_n | CLV |\n")
    rapor.append("|---|---|---|---|---|---|---|\n")
    for a in arena_q5:
        clv_str = f"{a['clv']*100:+.2f}%" if a["clv"] else "n/a"
        rapor.append(f"| {a['id']} | {a['name']} | {a['n']} | {a['hit']*100:.0f}% | "
                     f"n/a | {a['roi_net']:+.2f}% | {clv_str} |\n")

    out = YAZILIM / "RAPOR" / "Kapi0_T12_historical_model_arena.md"
    out.write_text("".join(rapor), encoding="utf-8")
    print(f"\n[OK] Rapor: {out}")


if __name__ == "__main__":
    run()
