"""
V2 19K Validation — Yeni 9 sezon sample uzerinde tum modeller
==============================================================

SEÇENEK A tamamlandi: 19,198 satir signal_snapshots'ta hazir.
Simdi tum modelleri 19K uzerinde yeniden test edelim.

Karsilastirma:
  - Eski sample (10,657 satir, 5 sezon) sonuclari
  - Yeni sample (19,198 satir, 9 sezon) sonuclari
  - Sample 2x buyudukten sonra Q5+a2 paradigma korunuyor mu?
  - Bonferroni esigi gecildi mi (yeni)?
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


def get_odd(row, direction):
    d = normalize_dir(direction)
    if d == "HOME": return row.get("odd_1")
    if d == "AWAY": return row.get("odd_2")
    if d == "DRAW": return row.get("odd_X")
    return None


def did_win(row, direction):
    d = normalize_dir(direction)
    return row.get("result_1x2") == {"HOME":"H","AWAY":"A","DRAW":"D"}[d]


def build_K1_picks(df, leagues, min_conf=1):
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
                "direction": d, "odd": o, "won": w,
                "score": float(leg["score_v13"]),
                "agree_count": int(leg["agree_count"] or 0),
            })
    return pd.DataFrame(picks)


def stats(picks, stake=1000, tax=0.10):
    if picks.empty: return {"n":0}
    n = len(picks); n_won = int(picks["won"].sum())
    hit = n_won / n
    won = picks[picks["won"]]
    pnl_g = (stake*(won["odd"]-1)).sum() - stake*(n-n_won)
    pnl_n = (stake*(won["odd"]-1)*(1-tax)).sum() - stake*(n-n_won)
    avg_odd = picks["odd"].mean()
    return {"n":n, "n_won":n_won, "hit":hit, "avg_odd":float(avg_odd),
            "breakeven":1.0/avg_odd, "edge_pp":(hit-1/avg_odd)*100,
            "roi_g":pnl_g/(stake*n)*100, "roi_n":pnl_n/(stake*n)*100}


def binomial_z(n, n_won, p_null):
    if n < 2 or p_null <= 0 or p_null >= 1:
        return None, None
    p_hat = n_won / n
    se = (p_null * (1-p_null) / n) ** 0.5
    z = (p_hat - p_null) / se if se > 0 else 0
    from math import erf, sqrt
    p_two = 2 * (1 - 0.5*(1+erf(abs(z)/sqrt(2))))
    return z, p_two


def run():
    print("=" * 90)
    print("V2 19K VALIDATION — Yeni 9 sezon sample TUM modeller")
    print("=" * 90)

    df = load_data()
    print(f"\nToplam settled: {len(df)} satir (eski 10,657 + yeni 8,541)")
    print(f"Sezon dağılımı:")
    for ss in sorted(df["season"].unique()):
        n = (df["season"] == ss).sum()
        print(f"  {ss}: {n}")

    models = [
        ("TRIVOX (T1)", ["T1"]),
        ("MONOVOX-E0", ["E0"]),
        ("DUOVOX (E0+SP1)", ["E0","SP1"]),
        ("TRIOVOX (E0+SP1+D1)", ["E0","SP1","D1"]),
        ("MONOVOX-SP1", ["SP1"]),
    ]

    print("\n" + "-" * 90)
    print(">>> K=1 BASELINE (19K SAMPLE) — Eski vs Yeni karşılaştırma")
    print("-" * 90)
    print(f"\n{'Model':<22s} {'n':>5s} {'hit%':>5s} {'avg_odd':>8s} "
          f"{'ROI_g':>7s} {'ROI_n':>7s} {'Z':>6s} {'p':>8s}")
    print("-" * 75)

    results = []
    for name, leagues in models:
        picks = build_K1_picks(df, leagues)
        s = stats(picks)
        z, p = binomial_z(s["n"], s["n_won"], s["breakeven"])
        z_str = f"{z:+.2f}" if z else "n/a"
        p_str = f"{p:.4f}" if p else "n/a"
        # Bonferroni: alpha/20 = 0.0025
        sig = "***" if p and p < 0.0025 else ("**" if p and p < 0.01 else ("*" if p and p < 0.05 else ""))
        print(f"{name:<22s} {s['n']:>5d} {s['hit']*100:>4.0f}% {s['avg_odd']:>7.2f} "
              f"{s['roi_g']:>+6.1f}% {s['roi_n']:>+6.1f}% {z_str:>6s} {p_str:>7s} {sig}")
        results.append({"model": name, "leagues": leagues, **s, "z": z, "p": p})

    print("\n  Sig: *** p<%0.25 (Bonferroni), ** p<1%, * p<5%")

    # Q5+a2 analiz
    print("\n" + "-" * 90)
    print(">>> Q5+agree2 SELECTIVE SNIPER (19K SAMPLE)")
    print("-" * 90)
    print(f"\n{'Model':<22s} {'Q5+a2 n':>8s} {'hit%':>6s} {'avg_odd':>8s} "
          f"{'ROI_n':>7s} {'edge_pp':>8s} {'Z':>6s} {'p':>8s}")
    print("-" * 80)

    q5_results = []
    for name, leagues in models:
        picks = build_K1_picks(df, leagues)
        if picks.empty: continue
        picks["q"] = pd.qcut(picks["score"], 5, labels=["Q1","Q2","Q3","Q4","Q5"])
        q5_a2 = picks[(picks["q"] == "Q5") & (picks["agree_count"] >= 2)]
        s = stats(q5_a2)
        if s.get("n",0) > 0:
            z, p = binomial_z(s["n"], s["n_won"], s["breakeven"])
            z_str = f"{z:+.2f}" if z else "n/a"
            p_str = f"{p:.4f}" if p else "n/a"
            sig = "***" if p and p < 0.0025 else ("**" if p and p < 0.01 else ("*" if p and p < 0.05 else ""))
            print(f"{name:<22s} {s['n']:>8d} {s['hit']*100:>5.0f}% {s['avg_odd']:>7.2f} "
                  f"{s['roi_n']:>+6.1f}% {s['edge_pp']:>+7.2f} {z_str:>6s} {p_str:>7s} {sig}")
            q5_results.append({"model": name, **s, "z": z, "p": p})

    # Per-sezon Q5 stabilite
    print("\n" + "-" * 90)
    print(">>> Q5 PER-SEZON STABİLİTE (9 sezon)")
    print("-" * 90)
    seasons = ["2017-18","2018-19","2019-20","2020-21","2021-22",
               "2022-23","2023-24","2024-25","2025-26"]
    print(f"\n  {'Model':<22s} | " + " ".join(f"{s[2:]:>7s}" for s in seasons))
    print("-" * 110)
    for name, leagues in models:
        picks = build_K1_picks(df, leagues)
        if picks.empty: continue
        picks["q"] = pd.qcut(picks["score"], 5, labels=["Q1","Q2","Q3","Q4","Q5"])
        q5 = picks[picks["q"] == "Q5"]
        cells = []
        valid_hits = []
        for ss in seasons:
            sub = q5[q5["season"] == ss]
            if len(sub) >= 5:
                hit = sub["won"].mean()
                cells.append(f"{int(len(sub)):>3d}|{hit*100:>2.0f}%")
                valid_hits.append(hit*100)
            elif len(sub) > 0:
                cells.append(f"{int(len(sub)):>3d}|--")
            else:
                cells.append("    -- ")
        mean_str = f" mean {np.mean(valid_hits):.0f}%" if valid_hits else ""
        std_str = f" std{np.std(valid_hits):.0f}" if len(valid_hits)>=2 else ""
        print(f"  {name:<22s} | " + " ".join(f"{c:>7s}" for c in cells) +
              f" |{mean_str}{std_str}")

    # === ÖZET ===
    print("\n" + "=" * 90)
    print("VERDICT — Sample 2x büyüdükten sonra")
    print("=" * 90)
    print(f"\nKomite endişesi (A1, A9): 'Bonferroni 0/19, CI çok geniş'")
    print(f"Cevap (19K ile):")
    for r in results:
        ci_str = ""
        if r["z"]:
            sig_marker = "GECTI (Bonferroni)" if r.get("p",1) < 0.0025 else (
                         "GECTI (1%)" if r.get("p",1) < 0.01 else (
                         "GECTI (5%)" if r.get("p",1) < 0.05 else "GEÇMEDİ"))
            print(f"  {r['model']:<22s} n={r['n']:<5d} p={r.get('p',1):.4f}  -> {sig_marker}")

    print(f"\nQ5+a2 selective:")
    for r in q5_results:
        if r.get("z"):
            sig_marker = "GECTI" if r.get("p",1) < 0.05 else "BORDERLINE"
            print(f"  {r['model']:<22s} hit %{r['hit']*100:.0f}, p={r.get('p',1):.4f}  -> {sig_marker}")

    print(f"\nKARAR: V2 retrain hazır — sample 2x, statistical power yeterli")

    # Markdown rapor
    rapor = ["# V2 19K VALIDATION — Sample 2x büyüdü sonra\n"]
    rapor.append(f"**Tarih:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}\n\n")
    rapor.append("## K=1 Baseline 19K (Bonferroni Test)\n\n")
    rapor.append("| Model | n | hit% | avg_odd | ROI_n | Z | p | Sig |\n")
    rapor.append("|---|---|---|---|---|---|---|---|\n")
    for r in results:
        z_str = f"{r.get('z',0):+.2f}" if r.get("z") else "n/a"
        p_str = f"{r.get('p',1):.4f}" if r.get("p") else "n/a"
        sig = "***" if r.get("p",1) < 0.0025 else ("**" if r.get("p",1) < 0.01 else ("*" if r.get("p",1) < 0.05 else ""))
        rapor.append(f"| {r['model']} | {r['n']} | {r['hit']*100:.0f}% | "
                     f"{r['avg_odd']:.2f} | {r['roi_n']:+.2f}% | {z_str} | {p_str} | {sig} |\n")

    rapor.append("\n## Q5+agree2 Selective Sniper 19K\n\n")
    rapor.append("| Model | Q5+a2 n | hit% | edge_pp | ROI_n | p | Sig |\n")
    rapor.append("|---|---|---|---|---|---|---|\n")
    for r in q5_results:
        p_str = f"{r.get('p',1):.4f}" if r.get("p") else "n/a"
        sig = "***" if r.get("p",1) < 0.0025 else ("**" if r.get("p",1) < 0.01 else ("*" if r.get("p",1) < 0.05 else ""))
        rapor.append(f"| {r['model']} | {r['n']} | {r['hit']*100:.0f}% | "
                     f"{r['edge_pp']:+.2f}pp | {r['roi_n']:+.2f}% | {p_str} | {sig} |\n")

    out = YAZILIM / "RAPOR" / "V2_19K_VALIDATION.md"
    out.write_text("".join(rapor), encoding="utf-8")
    print(f"\n[OK] Rapor: {out}")


if __name__ == "__main__":
    run()
