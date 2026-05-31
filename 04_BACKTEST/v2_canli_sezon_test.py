"""
GUNCEL DATA TESTI — 2025-26 sezonu yari sample uzerinde tum 10 silah
======================================================================

V2 sistemimizin 9 model + multi-market (A/U + KG) gucunu canli test et.
2025-26 sezonu yarisinda (mevcut sample) sinyal yogunlugu + hit rate olc.

Amaç:
  - Haftalik kac Q5+a2 sinyali geliyor?
  - Hangi pazar + lig kombinasyonu canli'da en cok aktif?
  - Trader haftalik frekans beklentisi
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


def load_2526():
    conn = db.connect()
    df = pd.read_sql_query("""
        SELECT * FROM signal_snapshots
        WHERE source='football_data' AND season='2526' AND settled=1
    """, conn)
    conn.close()
    df["matchday"] = pd.to_datetime(df["kickoff_iso"]).dt.strftime("%Y-%m-%d")
    return df


def get_odd_1x2(row, direction):
    d = normalize_dir(direction)
    if d == "HOME": return row.get("odd_1")
    if d == "AWAY": return row.get("odd_2")
    if d == "DRAW": return row.get("odd_X")
    return None


def did_win_1x2(row, direction):
    d = normalize_dir(direction)
    return row.get("result_1x2") == {"HOME":"H","AWAY":"A","DRAW":"D"}[d]


def build_1x2_q5a2(df, leagues):
    sub = df[df["league_code"].isin(leagues)].copy()
    sub["dir_fc"] = sub.apply(lambda r: fav_confirmed(r.to_dict(), 1), axis=1)
    sub = sub[sub["dir_fc"].notna()].copy()
    sub = sub.sort_values("score_v14", ascending=False)
    picks = []
    for (md, lg), grp in sub.groupby(["matchday","league_code"]):
        top = grp.head(1)
        for _, leg in top.iterrows():
            d = leg["dir_fc"]
            o = get_odd_1x2(leg.to_dict(), d)
            if not o or o < 1.01: continue
            won = did_win_1x2(leg.to_dict(), d)
            picks.append({
                "matchday": md, "league": lg,
                "home": leg["home_team"], "away": leg["away_team"],
                "direction": d, "odd": o, "won": won,
                "score": float(leg["score_v14"]) if pd.notna(leg["score_v14"]) else 0,
                "agree": int(leg["agree_count"] or 0),
            })
    if not picks: return pd.DataFrame()
    df_p = pd.DataFrame(picks)
    if len(df_p) < 5: return df_p
    df_p["q"] = pd.qcut(df_p["score"], 5, labels=["Q1","Q2","Q3","Q4","Q5"], duplicates="drop")
    return df_p


def run():
    print("=" * 90)
    print("GUNCEL DATA TESTI — 2025-26 sezonu yari sample, tum 10 silah")
    print("=" * 90)

    df = load_2526()
    print(f"\nSample: {len(df)} settled mac (2025-26 sezonu yarisi)")

    if df.empty:
        print("Sample yok.")
        return

    # Tarihsel: kac hafta?
    dates = pd.to_datetime(df["matchday"])
    n_weeks = (dates.max() - dates.min()).days / 7
    print(f"Tarih araligi: {dates.min().strftime('%Y-%m-%d')} -> "
          f"{dates.max().strftime('%Y-%m-%d')} (~{n_weeks:.1f} hafta)")

    # 1X2 PICKS — 5 model
    print("\n" + "-" * 90)
    print(">>> 1X2 — 5 model Q5+a2 (2025-26 canli)")
    print("-" * 90)

    models_1x2 = [
        ("TRIVOX", ["T1"]),
        ("MONOVOX-E0", ["E0"]),
        ("DUOVOX", ["E0","SP1"]),
        ("TRIOVOX", ["E0","SP1","D1"]),
        ("MONOVOX-SP1", ["SP1"]),
    ]
    print(f"{'Model':<14s} {'Q5+a2 n':>8s} {'hit%':>6s} {'avg_odd':>8s} {'per_week':>9s}")
    print("-" * 50)
    total_1x2_picks = 0
    for name, leagues in models_1x2:
        df_p = build_1x2_q5a2(df, leagues)
        if df_p.empty or "q" not in df_p.columns: continue
        q5a2 = df_p[(df_p["q"]=="Q5") & (df_p["agree"]>=2)]
        n = len(q5a2)
        total_1x2_picks += n
        if n > 0:
            hit = q5a2["won"].mean()*100
            avg_odd = q5a2["odd"].mean()
            per_week = n/n_weeks if n_weeks > 0 else 0
            print(f"{name:<14s} {n:>8d} {hit:>5.0f}% {avg_odd:>7.2f} {per_week:>8.1f}")

    print(f"\n1X2 toplam: {total_1x2_picks} pick (~{total_1x2_picks/n_weeks:.1f}/hafta)")

    # MULTI-MARKET PICKS — A/Ü 2.5
    print("\n" + "-" * 90)
    print(">>> A/Ü 2.5 — Lig × yön kombinasyonları (2025-26 canli)")
    print("-" * 90)

    df_ou = df[df["dir_ou_model"].notna() & df["odd_over25"].notna() &
               df["odd_under25"].notna()].copy()
    df_ou["total_goals"] = df_ou["home_score"] + df_ou["away_score"]
    df_ou["over_actual"] = (df_ou["total_goals"] > 2).astype(int)
    df_ou["odd_used"] = df_ou.apply(
        lambda r: r["odd_over25"] if r["dir_ou_model"]=="Over" else r["odd_under25"],
        axis=1
    )
    df_ou["won"] = df_ou.apply(
        lambda r: (r["dir_ou_model"]=="Over" and r["over_actual"]==1)
                or (r["dir_ou_model"]=="Under" and r["over_actual"]==0),
        axis=1
    )

    # Edge filter — sadece tarihsel pozitif kombinasyonlar
    HISTORICAL_POSITIVE = [
        ("D1", "Over"),
        ("E0", "Under"),
        ("F1", "Over"),
        ("SP1", "Under"),
        ("T1", "Over"),
    ]
    print(f"{'Lig':<5s} {'Yon':<7s} {'n':>4s} {'hit%':>6s} {'avg_odd':>8s} {'per_week':>9s}")
    print("-" * 50)
    total_ou_picks = 0
    for lg, dir_val in HISTORICAL_POSITIVE:
        sub = df_ou[(df_ou["league_code"]==lg) & (df_ou["dir_ou_model"]==dir_val)]
        if sub.empty: continue
        n = len(sub)
        total_ou_picks += n
        won = sub["won"].sum()
        hit = won/n*100 if n else 0
        avg_odd = sub["odd_used"].mean()
        per_week = n/n_weeks if n_weeks > 0 else 0
        print(f"{lg:<5s} {dir_val:<7s} {n:>4d} {hit:>5.0f}% {avg_odd:>7.2f} {per_week:>8.1f}")

    print(f"\nA/Ü toplam: {total_ou_picks} pick (~{total_ou_picks/n_weeks:.1f}/hafta)")

    # MULTI-MARKET PICKS — KG
    print("\n" + "-" * 90)
    print(">>> KG (Karşılıklı Gol) — Lig × yön kombinasyonları (2025-26 canli)")
    print("-" * 90)

    df_kg = df[df["dir_btts_model"].notna()].copy()
    df_kg["btts_actual"] = (
        (df_kg["home_score"] > 0) & (df_kg["away_score"] > 0)
    ).astype(int)
    df_kg["won"] = df_kg.apply(
        lambda r: (r["dir_btts_model"]=="Var" and r["btts_actual"]==1)
                or (r["dir_btts_model"]=="Yok" and r["btts_actual"]==0),
        axis=1
    )

    KG_POSITIVE = [
        ("D1", "Var"),
        ("SP1", "Var"),
        ("SP1", "Yok"),
        ("I1", "Yok"),
        ("T1", "Var"),
    ]
    print(f"{'Lig':<5s} {'Yon':<6s} {'n':>4s} {'hit%':>6s} {'per_week':>9s}")
    print("-" * 40)
    total_kg_picks = 0
    for lg, dir_val in KG_POSITIVE:
        sub = df_kg[(df_kg["league_code"]==lg) & (df_kg["dir_btts_model"]==dir_val)]
        if sub.empty: continue
        n = len(sub)
        total_kg_picks += n
        won = sub["won"].sum()
        hit = won/n*100 if n else 0
        per_week = n/n_weeks if n_weeks > 0 else 0
        print(f"{lg:<5s} {dir_val:<6s} {n:>4d} {hit:>5.0f}% {per_week:>8.1f}")

    print(f"\nKG toplam: {total_kg_picks} pick (~{total_kg_picks/n_weeks:.1f}/hafta)")

    # === GENEL ÖZET ===
    print("\n" + "=" * 90)
    print(">>> 2025-26 CANLI ÖZET")
    print("=" * 90)
    total = total_1x2_picks + total_ou_picks + total_kg_picks
    print(f"Toplam pick (yarı sezon): {total}")
    print(f"Haftalık ortalama: {total/n_weeks:.1f} pick")
    print(f"  - 1X2 Q5+a2:       {total_1x2_picks/n_weeks:.1f}/hafta")
    print(f"  - A/Ü 2.5:         {total_ou_picks/n_weeks:.1f}/hafta")
    print(f"  - KG:              {total_kg_picks/n_weeks:.1f}/hafta")

    # Markdown rapor
    rapor = ["# GUNCEL DATA TESTI — 2025-26 Sezonu Yari Sample\n"]
    rapor.append(f"**Tarih:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}\n")
    rapor.append(f"**Sample:** {len(df)} settled mac, ~{n_weeks:.1f} hafta\n\n")
    rapor.append(f"## Haftalık Pick Beklentisi\n\n")
    rapor.append(f"- 1X2 Q5+a2: ~{total_1x2_picks/n_weeks:.1f} pick/hafta\n")
    rapor.append(f"- A/Ü 2.5:  ~{total_ou_picks/n_weeks:.1f} pick/hafta\n")
    rapor.append(f"- KG:       ~{total_kg_picks/n_weeks:.1f} pick/hafta\n")
    rapor.append(f"- **TOPLAM: ~{total/n_weeks:.1f} pick/hafta**\n\n")

    out = YAZILIM / "RAPOR" / "V2_CANLI_2526_SEZON_TEST.md"
    out.write_text("".join(rapor), encoding="utf-8")
    print(f"\n[OK] Rapor: {out}")


if __name__ == "__main__":
    run()
