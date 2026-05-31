"""
SCORE_V14 vs SCORE_V13 VALIDATION
===================================

Yeni 3 sinyal eklendi (shots/referee/cards) → score_v14.
Score_v14 score_v13'ten iyi mi?

Karşılaştırmalar:
  1) Tek başına yeni 3 sinyalin hit rate ölçümü
  2) score_v13 Q5+a2 vs score_v14 Q5+a2 TRIVOX
  3) Aynı karşılaştırma 5 model için
  4) 9 sezon stabilite hala korunuyor mu?
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
    df = pd.read_sql_query("""
        SELECT league_code, season, kickoff_iso, home_team, away_team,
               odd_1, odd_X, odd_2,
               dir_favorite, dir_anomaly, dir_model, dir_xg, dir_form,
               dir_shots, dir_referee, dir_cards,
               s_shots, s_referee, s_cards,
               score_v13, score_v14, agree_count,
               result_1x2, settled
        FROM signal_snapshots
        WHERE source='football_data' AND settled=1
    """, conn)
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


def fav_confirmed_v14(row, min_conf=1):
    """v14: 7 sinyale göre teyit (anomaly+model+xG+form+shots+referee+cards)."""
    fav = row.get("dir_favorite")
    if not fav: return None
    fav_n = normalize_dir(fav)
    sigs = [row.get("dir_anomaly"), row.get("dir_model"),
            row.get("dir_xg"), row.get("dir_form"),
            row.get("dir_shots"), row.get("dir_referee"),
            row.get("dir_cards")]
    agree = [s for s in sigs if s and normalize_dir(s) == fav_n]
    return fav if len(agree) >= min_conf else None


def build_K1_picks(df, leagues, score_col="score_v13", filter_fn=fav_confirmed):
    df = df[df["league_code"].isin(leagues)].copy()
    df["dir_fc"] = df.apply(lambda r: filter_fn(r.to_dict(), 1), axis=1)
    df = df[df["dir_fc"].notna()].copy()
    df = df.sort_values(score_col, ascending=False)

    picks = []
    for (md, lg), group in df.groupby(["matchday", "league_code"]):
        top = group.head(1)
        for _, leg in top.iterrows():
            d = leg["dir_fc"]
            o = get_odd(leg.to_dict(), d)
            w = did_win(leg.to_dict(), d)
            if not o or o < 1.01: continue
            # v14 agree_count (7 sinyal)
            sigs7 = [leg.get("dir_anomaly"), leg.get("dir_model"),
                     leg.get("dir_xg"), leg.get("dir_form"),
                     leg.get("dir_shots"), leg.get("dir_referee"),
                     leg.get("dir_cards")]
            from collections import Counter
            ds = [normalize_dir(s) for s in sigs7 if s]
            cnt = Counter(ds).most_common(1)
            agree7 = cnt[0][1] if cnt else 0
            picks.append({
                "matchday": str(md), "league": lg, "season": leg["season"],
                "direction": d, "odd": o, "won": w,
                "score": float(leg[score_col]) if pd.notna(leg[score_col]) else 0,
                "agree": int(leg["agree_count"] or 0),
                "agree7": agree7,
            })
    return pd.DataFrame(picks)


def stats(picks):
    if picks.empty: return {"n":0}
    n = len(picks); n_won = int(picks["won"].sum())
    avg_odd = picks["odd"].mean()
    return {"n":n, "won":n_won, "hit":n_won/n, "avg_odd":float(avg_odd),
            "edge_pp":(n_won/n - 1/avg_odd)*100}


def run():
    print("=" * 80)
    print("SCORE_V14 VALIDATION — Yeni 3 sinyal eklenince ne oldu?")
    print("=" * 80)

    df = load_data()
    print(f"\nSample: {len(df)} settled satir")

    # === 1) TEK BAŞINA YENİ SİNYALLER ===
    print("\n" + "-" * 80)
    print(">>> 1) Yeni 3 sinyalin TEK BAŞINA hit rate")
    print("-" * 80)
    print(f"\n{'Sinyal':<12s} {'Dir':<8s} {'n':>5s} {'won':>5s} {'hit%':>6s} {'baseline':>9s}")
    print("-" * 50)
    # s_shots HOME
    for sig_col, dir_col, sigl_threshold, name in [
        ("s_shots", "dir_shots", 0.4, "s_shots"),
        ("s_referee", "dir_referee", 0.4, "s_referee"),
        ("s_cards", "dir_cards", 0.4, "s_cards"),
    ]:
        for dir_val in ["HOME", "AWAY", "DRAW"]:
            sub = df[(df[sig_col] >= sigl_threshold) & (df[dir_col] == dir_val)]
            if len(sub) < 30: continue
            n = len(sub)
            result_letter = {"HOME":"H","AWAY":"A","DRAW":"D"}[dir_val]
            won = (sub["result_1x2"] == result_letter).sum()
            hit = won / n
            # Baseline (avg odd)
            o_col = "odd_1" if dir_val == "HOME" else ("odd_2" if dir_val == "AWAY" else "odd_X")
            avg_odd = sub[o_col].mean()
            baseline = 1 / avg_odd
            print(f"{name:<12s} {dir_val:<8s} {n:>5d} {int(won):>5d} {hit*100:>5.0f}% "
                  f"{baseline*100:>7.1f}%  edge {(hit-baseline)*100:+.2f}pp")

    # === 2) TRIVOX Q5+a2 SCORE_V13 vs SCORE_V14 ===
    print("\n" + "-" * 80)
    print(">>> 2) TRIVOX K=1 Q5+a2 — score_v13 vs score_v14")
    print("-" * 80)

    for ver in ["score_v13", "score_v14"]:
        picks = build_K1_picks(df, ["T1"], score_col=ver)
        if picks.empty: continue
        # Quintile
        picks["q"] = pd.qcut(picks["score"], 5, labels=["Q1","Q2","Q3","Q4","Q5"], duplicates="drop")
        for q in ["Q5", "Q4"]:
            for agree_thr in [1, 2, 3]:
                sub = picks[(picks["q"] == q) & (picks["agree"] >= agree_thr)]
                if len(sub) < 5: continue
                s = stats(sub)
                print(f"  {ver:<10s} TRIVOX {q}+a{agree_thr}: n={s['n']:>3d}, "
                      f"hit %{s['hit']*100:.0f}, edge {s['edge_pp']:+.2f}pp")
        print()

    # === 3) Tüm 5 model: score_v13 vs score_v14 Q5+a2 ===
    print("\n" + "-" * 80)
    print(">>> 3) 5 MODEL Q5+a2 — score_v13 vs score_v14")
    print("-" * 80)
    models = [
        ("TRIVOX (T1)", ["T1"]),
        ("MONOVOX-E0", ["E0"]),
        ("DUOVOX (E0+SP1)", ["E0","SP1"]),
        ("TRIOVOX (E0+SP1+D1)", ["E0","SP1","D1"]),
        ("MONOVOX-SP1", ["SP1"]),
    ]
    print(f"\n{'Model':<22s} | {'v13 n':>5s} {'v13 hit':>8s} | {'v14 n':>5s} {'v14 hit':>8s} | {'Delta':>6s}")
    print("-" * 80)
    for name, leagues in models:
        results = {}
        for ver in ["score_v13", "score_v14"]:
            picks = build_K1_picks(df, leagues, score_col=ver)
            if picks.empty:
                results[ver] = None; continue
            picks["q"] = pd.qcut(picks["score"], 5, labels=["Q1","Q2","Q3","Q4","Q5"], duplicates="drop")
            sub = picks[(picks["q"] == "Q5") & (picks["agree"] >= 2)]
            s = stats(sub) if len(sub) > 0 else {"n":0, "hit":0}
            results[ver] = s
        v13 = results["score_v13"]; v14 = results["score_v14"]
        if v13["n"] > 0 and v14["n"] > 0:
            delta = (v14["hit"] - v13["hit"]) * 100
            print(f"{name:<22s} | {v13['n']:>5d} {v13['hit']*100:>7.0f}% | "
                  f"{v14['n']:>5d} {v14['hit']*100:>7.0f}% | {delta:>+5.1f}pp")

    # === 4) V14 ile YENİ KESHIF — Q5+a3 (3 sinyal teyit) ===
    print("\n" + "-" * 80)
    print(">>> 4) Q5+a3 (3+ sinyal teyit) — Ultra-strict, ne kadar küçük ama ne kadar güçlü?")
    print("-" * 80)
    print(f"\n{'Model':<22s} | {'n':>5s} {'hit':>5s} {'avg_odd':>8s} {'edge':>8s}")
    print("-" * 60)
    for name, leagues in models:
        picks = build_K1_picks(df, leagues, score_col="score_v14")
        if picks.empty: continue
        picks["q"] = pd.qcut(picks["score"], 5, labels=["Q1","Q2","Q3","Q4","Q5"], duplicates="drop")
        sub = picks[(picks["q"] == "Q5") & (picks["agree"] >= 3)]
        if len(sub) > 0:
            s = stats(sub)
            print(f"{name:<22s} | {s['n']:>5d} {s['hit']*100:>4.0f}% "
                  f"{s['avg_odd']:>7.2f} {s['edge_pp']:>+7.2f}pp")

    # === 5) Q5+a2 ile 7-sinyal teyit (yeni sinyaller de dahil agree) ===
    print("\n" + "-" * 80)
    print(">>> 5) Q5 + agree7>=3 (7 sinyalin 3'ü teyit) — VALUE_CONFIRMED proxy")
    print("-" * 80)
    print(f"\n{'Model':<22s} | {'n':>5s} {'hit':>5s} {'avg_odd':>8s} {'edge':>8s}")
    print("-" * 60)
    for name, leagues in models:
        picks = build_K1_picks(df, leagues, score_col="score_v14")
        if picks.empty: continue
        picks["q"] = pd.qcut(picks["score"], 5, labels=["Q1","Q2","Q3","Q4","Q5"], duplicates="drop")
        sub = picks[(picks["q"] == "Q5") & (picks["agree7"] >= 3)]
        if len(sub) > 0:
            s = stats(sub)
            print(f"{name:<22s} | {s['n']:>5d} {s['hit']*100:>4.0f}% "
                  f"{s['avg_odd']:>7.2f} {s['edge_pp']:>+7.2f}pp")

    # === ÖZET ===
    print("\n" + "=" * 80)
    print("VERDICT")
    print("=" * 80)

    # En iyi v14 strategy
    best = None
    for name, leagues in models:
        picks = build_K1_picks(df, leagues, score_col="score_v14")
        if picks.empty: continue
        picks["q"] = pd.qcut(picks["score"], 5, labels=["Q1","Q2","Q3","Q4","Q5"], duplicates="drop")
        for q, a in [("Q5", 2), ("Q5", 3)]:
            sub = picks[(picks["q"] == q) & (picks["agree"] >= a)]
            if len(sub) >= 5:
                s = stats(sub)
                if best is None or s["hit"] > best["hit"]:
                    best = {**s, "name": name, "q": q, "a": a}

    if best:
        print(f"\nEn iyi V2 strateji:")
        print(f"  {best['name']} {best['q']}+a{best['a']}")
        print(f"  n={best['n']}, hit %{best['hit']*100:.0f}, "
              f"avg_odd {best['avg_odd']:.2f}, edge {best['edge_pp']:+.2f}pp")

    # Markdown rapor
    rapor = ["# SCORE_V14 VALIDATION — Match Stats Sinyalleri Etkisi\n"]
    rapor.append(f"**Tarih:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}\n\n")
    rapor.append("## 5 Model Q5+a2 — V13 vs V14\n\n")
    rapor.append("| Model | v13 n | v13 hit | v14 n | v14 hit | Delta |\n")
    rapor.append("|---|---|---|---|---|---|\n")
    for name, leagues in models:
        results = {}
        for ver in ["score_v13", "score_v14"]:
            picks = build_K1_picks(df, leagues, score_col=ver)
            if picks.empty: continue
            picks["q"] = pd.qcut(picks["score"], 5, labels=["Q1","Q2","Q3","Q4","Q5"], duplicates="drop")
            sub = picks[(picks["q"] == "Q5") & (picks["agree"] >= 2)]
            s = stats(sub) if len(sub) > 0 else {"n":0, "hit":0}
            results[ver] = s
        if results.get("score_v13", {}).get("n",0) > 0:
            v13 = results["score_v13"]; v14 = results["score_v14"]
            delta = (v14["hit"] - v13["hit"]) * 100
            rapor.append(f"| {name} | {v13['n']} | {v13['hit']*100:.0f}% | "
                         f"{v14['n']} | {v14['hit']*100:.0f}% | {delta:+.1f}pp |\n")

    out = YAZILIM / "RAPOR" / "V2_SCORE_V14_VALIDATION.md"
    out.write_text("".join(rapor), encoding="utf-8")
    print(f"\n[OK] Rapor: {out}")


if __name__ == "__main__":
    run()
