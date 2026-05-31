"""
KAPI 0 — TEST 9: TRADER SELECTIVE QUINTILE ANALİZİ
======================================================

Paradigma kayması:
  Eski: "Her hafta 1000 TL flat oyna, ROI hesapla"
  Yeni: "Modelin en güvenli olduğu anlarda oyna, pozisyonu sinyal gücüne göre ayarla"

Kullanici: "TRADER mantigi: 1 kuponu tutarli sekilde tutturmak. Selective olacak.
            Daha buyuk oynayip kazanacak vs. POZISYON bilinmiyor cunku."

TEST:
  Her modelin score_v13 dağılımını 5 dilime (quintile) böl.
    Q5 = top 20% (en güçlü sinyal)
    Q4 = 60-80%
    Q3 = 40-60%
    Q2 = 20-40%
    Q1 = bottom 20% (en zayıf sinyal)

  Her quintile için:
    - Hit rate (en kritik: tutarlı tutturma)
    - n (her hafta kaç kupon var)
    - Ort. odd
    - CLV
    - ROI gross (referans)

  TRADER QUESTION: Q5'te hit rate >%65 ise -> "buyuk oyna" stratejisi makul

Tüm modeller için aynı analiz:
  TRIVOX (T1), MONOVOX-E0, DUOVOX (E0+SP1), TRIOVOX (E0+SP1+D1)
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


def build_K1_with_score(df: pd.DataFrame, leagues: list) -> pd.DataFrame:
    """K=1 picks ama her satıra score_v13 ekle (quintile analizi için)."""
    df = df[df["league_code"].isin(leagues)].copy()
    df["dir_fc"] = df.apply(lambda r: fav_confirmed(r.to_dict(), 1), axis=1)
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
                "home_team": leg["home_team"], "away_team": leg["away_team"],
                "direction": d, "odd": o, "won": w,
                "score": float(leg["score_v13"]),
                "agree_count": int(leg["agree_count"] or 0),
            })
    return pd.DataFrame(picks)


def quintile_analysis(picks: pd.DataFrame, name: str, df_m2: pd.DataFrame):
    """Score quintile'a göre hit rate, CLV, ROI."""
    print(f"\n{'-' * 80}")
    print(f">>> {name} — SCORE QUINTILE TRADER ANALIZI")
    print(f"{'-' * 80}")

    if picks.empty:
        print("  (boş)")
        return None

    # Quintile labels (Q5 = top 20% = highest score)
    picks = picks.copy()
    picks["quintile"] = pd.qcut(picks["score"], 5, labels=["Q1","Q2","Q3","Q4","Q5"])

    # CLV merge
    picks_m = picks.merge(
        df_m2.rename(columns={"league_code":"league"}),
        on=["league","season","matchday","home_team","away_team"], how="left"
    )
    def m2_open(r):
        d = normalize_dir(r["direction"])
        return r["opening_1"] if d=="HOME" else (r["opening_2"] if d=="AWAY" else r["opening_X"])
    def m2_close(r):
        d = normalize_dir(r["direction"])
        return r["closing_1"] if d=="HOME" else (r["closing_2"] if d=="AWAY" else r["closing_X"])
    picks_m["po"] = picks_m.apply(m2_open, axis=1)
    picks_m["pc"] = picks_m.apply(m2_close, axis=1)
    picks_m["clv"] = picks_m["po"] / picks_m["pc"] - 1

    print(f"{'Q':>3s} {'n':>4s} {'won':>4s} {'hit%':>5s} {'avg_odd':>8s} "
          f"{'breakeven%':>10s} {'edge_pp':>8s} {'CLV':>7s} {'avg_score':>9s}")
    results = []
    for q in ["Q5","Q4","Q3","Q2","Q1"]:  # Top first
        sub = picks_m[picks_m["quintile"] == q]
        if sub.empty: continue
        n = len(sub); n_won = sub["won"].sum()
        hit = n_won / n
        avg_odd = sub["odd"].mean()
        breakeven = 1.0 / avg_odd
        edge_pp = (hit - breakeven) * 100
        clv = sub["clv"].dropna()
        clv_str = f"{clv.mean()*100:+.2f}%" if len(clv) else "n/a"
        avg_score = sub["score"].mean()
        print(f"{q:>3s} {n:>4d} {int(n_won):>4d} "
              f"{hit*100:>4.0f}% {avg_odd:>7.2f} "
              f"{breakeven*100:>9.1f}% {edge_pp:>+7.2f} "
              f"{clv_str:>7s} {avg_score:>8.3f}")
        results.append({
            "quintile": q, "n": n, "n_won": int(n_won), "hit": hit,
            "avg_odd": avg_odd, "breakeven": breakeven, "edge_pp": edge_pp,
            "clv_mean": clv.mean() if len(clv) else None,
            "clv_n": len(clv),
            "avg_score": avg_score,
        })

    # Trader Verdict
    if results:
        q5 = next((r for r in results if r["quintile"]=="Q5"), None)
        q1 = next((r for r in results if r["quintile"]=="Q1"), None)
        if q5 and q1:
            print(f"\n  TRADER YORUMU:")
            print(f"    Q5 (en guclu sinyal): hit %{q5['hit']*100:.0f}, edge {q5['edge_pp']:+.2f}pp")
            print(f"    Q1 (en zayif sinyal): hit %{q1['hit']*100:.0f}, edge {q1['edge_pp']:+.2f}pp")
            print(f"    Q5 - Q1 hit delta: {(q5['hit']-q1['hit'])*100:+.1f}pp")
            if q5["edge_pp"] > 5:
                print(f"    -> [STRONG] Q5'te %5+ edge -> 'BUYUK OYNA' stratejisi mantikli")
            elif q5["edge_pp"] > 2:
                print(f"    -> [MILD] Q5'te %2-5 edge -> normal oyna")
            else:
                print(f"    -> [WEAK] Q5'te %2 alti edge -> sinyal ayrismiyor")
            if (q5["hit"] - q1["hit"]) > 0.10:
                print(f"    -> [PASS] Score ayrimi calisiyor (Q5 vs Q1 >10pp)")
            else:
                print(f"    -> [WARN] Score ayrimi zayif (Q5 vs Q1 <10pp)")
    return results


def agree_count_analysis(picks: pd.DataFrame, name: str):
    """agree_count'a göre hit rate (kaç sinyal aynı yönü gösteriyor)."""
    print(f"\n  agree_count BAZLI:")
    print(f"  {'agr':>3s} {'n':>4s} {'won':>4s} {'hit%':>5s} {'avg_odd':>8s} {'edge_pp':>8s}")
    for ac in sorted(picks["agree_count"].unique()):
        sub = picks[picks["agree_count"] == ac]
        if sub.empty: continue
        n = len(sub); n_won = sub["won"].sum()
        hit = n_won / n
        avg_odd = sub["odd"].mean()
        breakeven = 1.0 / avg_odd
        edge_pp = (hit - breakeven) * 100
        print(f"  {ac:>3d} {n:>4d} {int(n_won):>4d} "
              f"{hit*100:>4.0f}% {avg_odd:>7.2f} {edge_pp:>+7.2f}")


def run():
    print("=" * 80)
    print("KAPI 0 - TEST 9: TRADER SELECTIVE QUINTILE ANALIZI")
    print("Yeni paradigma: Sinyal gucune gore selective bahis")
    print("=" * 80)

    df = load_data()
    df_m2 = load_m2()
    print(f"signal_snapshots: {len(df)}, matches_v2: {len(df_m2)}\n")

    models = [
        ("TRIVOX", ["T1"]),
        ("MONOVOX-E0", ["E0"]),
        ("DUOVOX (E0+SP1)", ["E0","SP1"]),
        ("TRIOVOX (E0+SP1+D1)", ["E0","SP1","D1"]),
        ("MONOVOX-SP1", ["SP1"]),
    ]

    all_results = {}
    for name, leagues in models:
        picks = build_K1_with_score(df, leagues)
        if picks.empty: continue
        results = quintile_analysis(picks, name, df_m2)
        agree_count_analysis(picks, name)
        all_results[name] = results

    # === Karşılaştırma tablosu — sadece Q5 ===
    print("\n" + "=" * 80)
    print(">>> Q5 (en guclu sinyal) KARSILASTIRMA — Trader icin en kritik")
    print("=" * 80)
    print(f"{'Model':<22s} {'n_Q5':>5s} {'hit%':>5s} {'avg_odd':>8s} "
          f"{'edge_pp':>8s} {'CLV':>7s} {'theory_ROI':>10s}")
    for name, results in all_results.items():
        if not results: continue
        q5 = next((r for r in results if r["quintile"]=="Q5"), None)
        if not q5: continue
        # Theoretical ROI (no tax): if hit rate is X% and avg odd is Y -> ROI = X*Y - 1
        theory_roi = (q5["hit"] * q5["avg_odd"] - 1) * 100
        clv_str = f"{q5['clv_mean']*100:+.2f}%" if q5["clv_mean"] is not None else "n/a"
        print(f"{name:<22s} {q5['n']:>5d} {q5['hit']*100:>4.0f}% "
              f"{q5['avg_odd']:>7.2f} {q5['edge_pp']:>+7.2f} "
              f"{clv_str:>7s} {theory_roi:>+9.2f}%")

    # === Karar matrisi ===
    print("\n" + "-" * 80)
    print(">>> TRADER EGITIMI: HANGI MODELE NE ZAMAN GUVENILIR?")
    print("-" * 80)

    # Markdown rapor
    rapor = ["# KAPI 0 — TEST 9: TRADER SELECTIVE QUINTILE\n"]
    rapor.append(f"**Tarih:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}\n")
    rapor.append("**Paradigma:** Trader = selective bahis, sinyal gucune gore pozisyon.\n\n")

    rapor.append("## Tum Modellerde Q5 (En Guclu Sinyal) Karsilastirmasi\n\n")
    rapor.append("| Model | n_Q5 | hit% | avg_odd | edge_pp | CLV | Theory ROI (no tax) |\n")
    rapor.append("|---|---|---|---|---|---|---|\n")
    for name, results in all_results.items():
        if not results: continue
        q5 = next((r for r in results if r["quintile"]=="Q5"), None)
        if not q5: continue
        theory_roi = (q5["hit"] * q5["avg_odd"] - 1) * 100
        clv_str = f"{q5['clv_mean']*100:+.2f}%" if q5["clv_mean"] is not None else "n/a"
        rapor.append(f"| {name} | {q5['n']} | {q5['hit']*100:.0f}% | "
                     f"{q5['avg_odd']:.2f} | {q5['edge_pp']:+.2f}pp | "
                     f"{clv_str} | {theory_roi:+.2f}% |\n")

    rapor.append("\n## Tum Quintile Detaylari\n\n")
    for name, results in all_results.items():
        if not results: continue
        rapor.append(f"### {name}\n\n")
        rapor.append("| Quintile | n | hit% | avg_odd | breakeven | edge_pp | CLV |\n")
        rapor.append("|---|---|---|---|---|---|---|\n")
        for r in results:
            clv_str = f"{r['clv_mean']*100:+.2f}%" if r["clv_mean"] is not None else "n/a"
            rapor.append(f"| {r['quintile']} | {r['n']} | {r['hit']*100:.0f}% | "
                         f"{r['avg_odd']:.2f} | {r['breakeven']*100:.1f}% | "
                         f"{r['edge_pp']:+.2f}pp | {clv_str} |\n")
        rapor.append("\n")

    out = YAZILIM / "RAPOR" / "Kapi0_T09_trader_selective_quintile.md"
    out.write_text("".join(rapor), encoding="utf-8")
    print(f"\n[OK] Rapor: {out}")


if __name__ == "__main__":
    run()
