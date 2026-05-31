"""
KAPI 0 — TEST 10: Q5 (EN GÜÇLÜ SİNYAL) SEZONSAL STABİLİTE
=============================================================

T09'da bulduk:
  Tum modellerin Q5 quintile'inda hit %67-71, edge +%6.9-8.3pp.

Ama kritik soru: Q5 hit rate her sezonda stabil mi?

Eger 2024-25 ve 2025-26 sezonlarda Q5 hit %50'ye dusuyorsa -> live'da
calismayacak. Trader icin tehlike sinyali.

Eger tum sezonlarda %65+ stabil ise -> trader silahi gercek, V2'ye guvenle gec.

Test edilecek modeller:
  TRIVOX (T1), MONOVOX-E0, DUOVOX (E0+SP1), TRIOVOX (E0+SP1+D1), MONOVOX-SP1

Her biri icin:
  - Q5 hit rate per sezon
  - Q5 edge_pp per sezon
  - Q5 + agree>=2 hit rate per sezon (extreme selective)
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


def build_picks(df: pd.DataFrame, leagues: list) -> pd.DataFrame:
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
                "direction": d, "odd": o, "won": w,
                "score": float(leg["score_v13"]),
                "agree_count": int(leg["agree_count"] or 0),
            })
    return pd.DataFrame(picks)


def assign_global_quintile(picks: pd.DataFrame) -> pd.DataFrame:
    picks = picks.copy()
    picks["quintile"] = pd.qcut(picks["score"], 5, labels=["Q1","Q2","Q3","Q4","Q5"])
    return picks


def hit_stats(sub: pd.DataFrame) -> dict:
    if sub.empty:
        return {"n": 0, "hit": 0, "avg_odd": 0, "edge_pp": 0}
    n = len(sub); n_won = int(sub["won"].sum())
    hit = n_won / n
    avg_odd = sub["odd"].mean()
    breakeven = 1.0 / avg_odd
    edge_pp = (hit - breakeven) * 100
    return {"n": n, "n_won": n_won, "hit": hit, "avg_odd": float(avg_odd),
            "edge_pp": float(edge_pp)}


def seasonal_q5_table(picks: pd.DataFrame, name: str):
    """Her sezon icin Q5 hit rate, Q5+agree2 hit rate."""
    print(f"\n{'-' * 80}")
    print(f">>> {name} — Q5 SEZONSAL STABILITE")
    print(f"{'-' * 80}")
    if picks.empty:
        print("  (boş)")
        return None

    picks = assign_global_quintile(picks)
    q5 = picks[picks["quintile"] == "Q5"]
    q5a2 = picks[(picks["quintile"] == "Q5") & (picks["agree_count"] >= 2)]

    print(f"  Toplam picks: {len(picks)}, Q5: {len(q5)}, Q5+agree>=2: {len(q5a2)}")
    print()
    print(f"  {'Sezon':>8s} | {'Q5 n':>4s} {'Q5 hit':>7s} {'Q5 edge':>8s} | "
          f"{'Q5+a2 n':>7s} {'Q5+a2 hit':>10s} {'Q5+a2 edge':>11s}")
    rows = []
    for ss in sorted(picks["season"].unique()):
        q5_s = q5[q5["season"] == ss]
        q5a2_s = q5a2[q5a2["season"] == ss]
        s5 = hit_stats(q5_s)
        s5a = hit_stats(q5a2_s)
        rows.append({"season": ss, **{f"q5_{k}":v for k,v in s5.items()},
                     **{f"q5a2_{k}":v for k,v in s5a.items()}})
        print(f"  {ss:>8s} | {s5['n']:>4d} {s5['hit']*100:>6.0f}% "
              f"{s5['edge_pp']:>+7.2f}pp | {s5a['n']:>7d} "
              f"{s5a['hit']*100:>9.0f}% {s5a['edge_pp']:>+10.2f}pp")
    # Stabilite
    q5_hits = [r["q5_hit"] for r in rows if r["q5_n"] >= 10]
    q5_edges = [r["q5_edge_pp"] for r in rows if r["q5_n"] >= 10]
    if q5_hits:
        print(f"\n  Q5 STABILITE (sample>=10):")
        print(f"    Hit rate: mean {np.mean(q5_hits)*100:.0f}%, "
              f"std {np.std(q5_hits)*100:.1f}pp, "
              f"min {min(q5_hits)*100:.0f}%, max {max(q5_hits)*100:.0f}%")
        print(f"    Edge_pp: mean {np.mean(q5_edges):+.2f}pp, "
              f"std {np.std(q5_edges):.2f}, "
              f"min {min(q5_edges):+.2f}, max {max(q5_edges):+.2f}")
        # Pozitif sezon
        pos_seasons = sum(1 for h in q5_hits if h > 0.55)  # 55%+ trader threshold
        print(f"    {pos_seasons}/{len(q5_hits)} sezon hit > %55")
        # Son sezon
        last_q5 = next((r for r in rows if r["season"] == "2025-26" and r["q5_n"] >= 5), None)
        prev_q5 = next((r for r in rows if r["season"] == "2024-25" and r["q5_n"] >= 5), None)
        if last_q5 and prev_q5:
            d = (last_q5["q5_hit"] - prev_q5["q5_hit"]) * 100
            print(f"    2024-25 vs 2025-26 hit delta: {d:+.1f}pp")
            if d < -10:
                print(f"    *** RED FLAG: Q5 hit son sezon belirgin dustu ***")
    return rows


def run():
    print("=" * 80)
    print("KAPI 0 - TEST 10: Q5 SEZONSAL STABILITE")
    print("Trader sorusu: 'En guclu sinyal her sezonda %65+ tutturuyor mu?'")
    print("=" * 80)

    df = load_data()
    print(f"signal_snapshots: {len(df)}\n")

    models = [
        ("TRIVOX (T1)", ["T1"]),
        ("MONOVOX-E0", ["E0"]),
        ("DUOVOX (E0+SP1)", ["E0","SP1"]),
        ("TRIOVOX (E0+SP1+D1)", ["E0","SP1","D1"]),
        ("MONOVOX-SP1", ["SP1"]),
    ]

    all_data = {}
    for name, leagues in models:
        picks = build_picks(df, leagues)
        rows = seasonal_q5_table(picks, name)
        all_data[name] = rows

    # === KARSILASTIRMA TABLOSU — SADECE Q5 HIT PER SEZON ===
    print("\n" + "=" * 80)
    print(">>> Q5 HIT RATE — TUM MODELLER PER SEZON")
    print("=" * 80)
    seasons = ["2021-22", "2022-23", "2023-24", "2024-25", "2025-26"]
    print(f"  {'Model':<22s} | " + " ".join(f"{s:>7s}" for s in seasons) + " | mean std")
    summary_data = []
    for name, rows in all_data.items():
        if not rows: continue
        vals = []
        for s in seasons:
            r = next((x for x in rows if x["season"] == s), None)
            if r and r["q5_n"] >= 5:
                vals.append((r["q5_hit"]*100, r["q5_n"]))
            else:
                vals.append((None, 0))
        cells = []
        valid_hits = []
        for h, n in vals:
            if h is None:
                cells.append("   n/a ")
            else:
                marker = "*" if n < 10 else " "
                cells.append(f"{h:>5.0f}%{marker}")
                valid_hits.append(h)
        mean_str = f"{np.mean(valid_hits):.0f}" if valid_hits else "n/a"
        std_str = f"{np.std(valid_hits):.0f}" if len(valid_hits) >= 2 else "n/a"
        print(f"  {name:<22s} | " + " ".join(f"{c:>7s}" for c in cells) +
              f" | {mean_str:>4s} {std_str:>3s}")
        summary_data.append({"model": name, "hits": valid_hits,
                             "mean": np.mean(valid_hits) if valid_hits else None,
                             "std": np.std(valid_hits) if len(valid_hits) >= 2 else None,
                             "rows": rows})
    print("\n  (* = sample n<10, gurultulu)")

    # === Q5 + agree>=2 TABLOSU ===
    print("\n" + "-" * 80)
    print(">>> Q5 + agree>=2 HIT RATE (EXTREME SELECTIVE) PER SEZON")
    print("-" * 80)
    print(f"  {'Model':<22s} | " + " ".join(f"{s:>7s}" for s in seasons) + " | mean")
    for name, rows in all_data.items():
        if not rows: continue
        vals = []
        for s in seasons:
            r = next((x for x in rows if x["season"] == s), None)
            if r and r["q5a2_n"] >= 5:
                vals.append((r["q5a2_hit"]*100, r["q5a2_n"]))
            else:
                vals.append((None, 0))
        cells = []
        valid_hits = []
        for h, n in vals:
            if h is None:
                cells.append("   n/a ")
            else:
                marker = "*" if n < 5 else " "
                cells.append(f"{h:>5.0f}%{marker}")
                valid_hits.append(h)
        mean_str = f"{np.mean(valid_hits):.0f}" if valid_hits else "n/a"
        print(f"  {name:<22s} | " + " ".join(f"{c:>7s}" for c in cells) +
              f" | {mean_str:>4s}")

    # === KARAR ===
    print("\n" + "=" * 80)
    print("TRADER VERDICT")
    print("=" * 80)
    print(f"\nTrader esigi: Q5 hit rate her sezon >%55, std<10pp, son 2 sezon >%60\n")
    for sd in summary_data:
        if not sd["hits"]: continue
        mean = sd["mean"]; std = sd["std"]
        passed_threshold = sum(1 for h in sd["hits"] if h > 55)
        # Son 2 sezon (24-25, 25-26 yarisi)
        rows = sd["rows"]
        last2 = [r for r in rows if r["season"] in ("2024-25","2025-26") and r["q5_n"] >= 5]
        last2_hits = [r["q5_hit"]*100 for r in last2]
        last2_mean = np.mean(last2_hits) if last2_hits else None
        verdict = []
        if mean and mean > 60: verdict.append("MEAN-OK")
        else: verdict.append("MEAN-LOW")
        if std and std < 10: verdict.append("STABIL")
        else: verdict.append("VARYANTLI")
        if last2_mean and last2_mean > 55: verdict.append("LIVE-OK")
        else: verdict.append("LIVE-RISK")
        verdict_str = " / ".join(verdict)
        ls_str = f"{last2_mean:.0f}%" if last2_mean else "n/a"
        print(f"  {sd['model']:<22s}: mean %{mean:.0f}, std {std:.1f}pp, "
              f"son2_mean {ls_str} -> {verdict_str}")

    # Markdown rapor
    rapor = ["# KAPI 0 — TEST 10: Q5 SEZONSAL STABILITE\n"]
    rapor.append(f"**Tarih:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}\n")
    rapor.append("**Trader sorusu:** 'En guclu sinyal her sezonda %65+ tutturuyor mu?'\n\n")

    rapor.append("## Q5 Hit Rate — Tum Modeller Per Sezon\n\n")
    rapor.append("| Model | " + " | ".join(seasons) + " | mean | std |\n")
    rapor.append("|---|" + "|".join(["---" for _ in seasons]) + "|---|---|\n")
    for sd in summary_data:
        rows = sd["rows"]
        cells = []
        for s in seasons:
            r = next((x for x in rows if x["season"] == s), None)
            if r and r["q5_n"] >= 5:
                marker = "*" if r["q5_n"] < 10 else ""
                cells.append(f"{r['q5_hit']*100:.0f}%{marker}")
            else:
                cells.append("n/a")
        mean_str = f"{sd['mean']:.0f}%" if sd["mean"] else "n/a"
        std_str = f"{sd['std']:.1f}" if sd["std"] else "n/a"
        rapor.append(f"| {sd['model']} | " + " | ".join(cells) + f" | {mean_str} | {std_str} |\n")

    rapor.append("\n*(* = sample n<10, gurultulu)*\n\n")
    rapor.append("## Q5 + agree>=2 Hit Rate — Extreme Selective\n\n")
    rapor.append("| Model | " + " | ".join(seasons) + " | mean |\n")
    rapor.append("|---|" + "|".join(["---" for _ in seasons]) + "|---|\n")
    for name, rows in all_data.items():
        if not rows: continue
        cells = []
        valid = []
        for s in seasons:
            r = next((x for x in rows if x["season"] == s), None)
            if r and r["q5a2_n"] >= 5:
                marker = "*" if r["q5a2_n"] < 10 else ""
                cells.append(f"{r['q5a2_hit']*100:.0f}%{marker}")
                valid.append(r["q5a2_hit"]*100)
            else:
                cells.append("n/a")
        mean_str = f"{np.mean(valid):.0f}%" if valid else "n/a"
        rapor.append(f"| {name} | " + " | ".join(cells) + f" | {mean_str} |\n")

    out = YAZILIM / "RAPOR" / "Kapi0_T10_Q5_seasonal_stability.md"
    out.write_text("".join(rapor), encoding="utf-8")
    print(f"\n[OK] Rapor: {out}")


if __name__ == "__main__":
    run()
