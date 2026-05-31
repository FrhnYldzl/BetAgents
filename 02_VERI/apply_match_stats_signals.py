"""
APPLY MATCH STATS SIGNALS to signal_snapshots
==============================================

3 yeni sinyal (s_shots, s_referee, s_cards) tüm 19,198 satıra uygula.

Adımlar:
  1) signal_snapshots'a 6 yeni kolon ekle:
     s_shots, dir_shots, s_referee, dir_referee, s_cards, dir_cards
  2) Her satır için match_stats sinyallerini hesapla
  3) UPDATE et
  4) score_v14 hesapla: score_v13'e 3 yeni sinyal eklenmiş hâli
  5) Yeni Q5+a2 hit rate test
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

THIS_DIR = Path(__file__).resolve().parent
YAZILIM = THIS_DIR.parent
sys.path.insert(0, str(THIS_DIR))
sys.path.insert(0, str(YAZILIM / "03_MODELLER" / "selective"))

import database as db
from match_stats_signals import (
    all_match_stats_signals,
    _load_team_stats_cache,
    _load_referee_cache,
)


SEASON_CONV = {
    "1718":"2017-18","1819":"2018-19","1920":"2019-20","2021":"2020-21",
    "2122":"2021-22","2223":"2022-23","2324":"2023-24","2425":"2024-25","2526":"2025-26",
}


EXTEND_SCHEMA = """
ALTER TABLE signal_snapshots ADD COLUMN s_shots REAL;
ALTER TABLE signal_snapshots ADD COLUMN dir_shots TEXT;
ALTER TABLE signal_snapshots ADD COLUMN s_referee REAL;
ALTER TABLE signal_snapshots ADD COLUMN dir_referee TEXT;
ALTER TABLE signal_snapshots ADD COLUMN s_cards REAL;
ALTER TABLE signal_snapshots ADD COLUMN dir_cards TEXT;
ALTER TABLE signal_snapshots ADD COLUMN score_v14 REAL;
"""


def add_columns():
    conn = db.connect()
    try:
        for stmt in EXTEND_SCHEMA.strip().split(";"):
            stmt = stmt.strip()
            if not stmt: continue
            try:
                conn.execute(stmt)
            except Exception as e:
                if "duplicate column" not in str(e).lower():
                    print(f"  ALTER err: {e}")
        conn.commit()
    finally:
        conn.close()


def get_referee(match_date, home_team, away_team):
    """matches_v2'den hakem bilgisini al."""
    conn = db.connect()
    try:
        r = conn.execute("""
            SELECT referee FROM matches_v2
            WHERE matchday=? AND home_team=? AND away_team=?
            LIMIT 1
        """, (match_date, home_team, away_team)).fetchone()
        return r["referee"] if r else None
    finally:
        conn.close()


def apply_signals():
    """Tüm signal_snapshots rows için 3 yeni sinyali hesapla ve UPDATE et."""
    print("[1] Caches yukleniyor...")
    _load_team_stats_cache()
    _load_referee_cache()
    print("    OK\n")

    conn = db.connect()
    now = datetime.utcnow().isoformat()

    # Get all rows with referee info via join
    rows = conn.execute("""
        SELECT s.match_uid, s.kickoff_iso, s.home_team, s.away_team,
               s.league_code, s.season,
               m.referee
        FROM signal_snapshots s
        LEFT JOIN matches_v2 m
          ON m.matchday = substr(s.kickoff_iso, 1, 10)
         AND m.home_team = s.home_team
         AND m.away_team = s.away_team
        WHERE s.source='football_data'
    """).fetchall()

    print(f"[2] {len(rows)} satir icin sinyal hesaplama...")
    n_updated = 0
    n_with_shots = 0
    n_with_ref = 0
    n_with_cards = 0

    for i, r in enumerate(rows):
        if i % 1000 == 0 and i > 0:
            print(f"    {i}/{len(rows)} ...")
        try:
            md = r["kickoff_iso"][:10]
            home = r["home_team"]
            away = r["away_team"]
            referee = r["referee"]

            sigs = all_match_stats_signals(home, away, md, referee)

            s_shots = sigs.get("s_shots")
            d_shots = sigs.get("dir_shots")
            s_ref = sigs.get("s_referee")
            d_ref = sigs.get("dir_referee")
            s_cards = sigs.get("s_cards")
            d_cards = sigs.get("dir_cards")

            conn.execute("""
                UPDATE signal_snapshots
                SET s_shots=?, dir_shots=?,
                    s_referee=?, dir_referee=?,
                    s_cards=?, dir_cards=?
                WHERE match_uid=? AND source='football_data'
            """, (s_shots, d_shots, s_ref, d_ref, s_cards, d_cards, r["match_uid"]))

            n_updated += 1
            if s_shots and s_shots > 0: n_with_shots += 1
            if s_ref and s_ref > 0: n_with_ref += 1
            if s_cards and s_cards > 0: n_with_cards += 1
        except Exception as e:
            pass

    conn.commit()

    print(f"\n[3] Sonuç:")
    print(f"    Total updated: {n_updated}")
    print(f"    s_shots > 0:   {n_with_shots} ({n_with_shots/n_updated*100:.0f}%)")
    print(f"    s_referee > 0: {n_with_ref} ({n_with_ref/n_updated*100:.0f}%)")
    print(f"    s_cards > 0:   {n_with_cards} ({n_with_cards/n_updated*100:.0f}%)")

    # === score_v14 hesapla ===
    print(f"\n[4] score_v14 hesaplanıyor (score_v13 + 3 yeni sinyal)...")
    # WEIGHTS: anomaly 0.20 + model 0.18 + sharp 0.08 + invvar 0.08 + xg 0.15 + form 0.12
    #          + shots 0.08 + referee 0.05 + cards 0.06 = 1.00
    rows = conn.execute("""
        SELECT match_uid, s_anomaly, s_model, s_sharp, s_invvar,
               s_xg, s_form, s_shots, s_referee, s_cards
        FROM signal_snapshots WHERE source='football_data'
    """).fetchall()

    n_v14 = 0
    for r in rows:
        d = dict(r)
        parts = []
        # Klasik sinyaller (yukarı ağırlık)
        if d.get("s_anomaly") is not None: parts.append((0.20, d["s_anomaly"]))
        if d.get("s_model") is not None: parts.append((0.18, d["s_model"]))
        if d.get("s_sharp") is not None: parts.append((0.08, d["s_sharp"]))
        if d.get("s_invvar") is not None: parts.append((0.08, d["s_invvar"]))
        if d.get("s_xg") and d["s_xg"] > 0: parts.append((0.15, d["s_xg"]))
        if d.get("s_form") and d["s_form"] > 0: parts.append((0.12, d["s_form"]))
        # Yeni sinyaller
        if d.get("s_shots") and d["s_shots"] > 0: parts.append((0.08, d["s_shots"]))
        if d.get("s_referee") and d["s_referee"] > 0: parts.append((0.05, d["s_referee"]))
        if d.get("s_cards") and d["s_cards"] > 0: parts.append((0.06, d["s_cards"]))

        if not parts:
            score = 0.0
        else:
            w = sum(w for w,_ in parts)
            score = sum(w*v for w,v in parts) / w

        conn.execute(
            "UPDATE signal_snapshots SET score_v14=? WHERE match_uid=? AND source='football_data'",
            (score, d["match_uid"])
        )
        n_v14 += 1

    conn.commit()
    conn.close()

    print(f"    {n_v14} satir score_v14 hesaplandı")


def report():
    """Yeni sinyallerin tek başına edge ölçümü."""
    conn = db.connect()
    print("\n" + "=" * 80)
    print(">>> 3 YENİ SİNYAL — Tek başına edge ölçümü (settled only)")
    print("=" * 80)

    # s_shots: HOME yön
    print("\n[s_shots] Shots Form Diff sinyali:")
    for direction in ("HOME", "AWAY"):
        rows = conn.execute("""
            SELECT COUNT(*) as n, SUM(CASE WHEN result_1x2=? THEN 1 ELSE 0 END) as won
            FROM signal_snapshots
            WHERE source='football_data' AND settled=1
              AND s_shots > 0.4 AND dir_shots=?
        """, ("H" if direction=="HOME" else "A", direction)).fetchone()
        n, won = rows["n"], rows["won"]
        if n >= 30:
            hit = won/n
            print(f"  dir={direction:4s}: n={n:>4d}, hit %{hit*100:.1f}")

    print("\n[s_referee] Referee Bias sinyali:")
    for direction in ("HOME", "AWAY"):
        rows = conn.execute("""
            SELECT COUNT(*) as n, SUM(CASE WHEN result_1x2=? THEN 1 ELSE 0 END) as won
            FROM signal_snapshots
            WHERE source='football_data' AND settled=1
              AND s_referee > 0.4 AND dir_referee=?
        """, ("H" if direction=="HOME" else "A", direction)).fetchone()
        n, won = rows["n"], rows["won"]
        if n >= 30:
            hit = won/n
            print(f"  dir={direction:4s}: n={n:>4d}, hit %{hit*100:.1f}")

    print("\n[s_cards] Cards Pressure sinyali (DRAW yönlü):")
    rows = conn.execute("""
        SELECT COUNT(*) as n, SUM(CASE WHEN result_1x2='D' THEN 1 ELSE 0 END) as won
        FROM signal_snapshots
        WHERE source='football_data' AND settled=1
          AND s_cards > 0.4 AND dir_cards='DRAW'
    """).fetchone()
    n, won = rows["n"], rows["won"]
    if n >= 30:
        hit = won/n
        print(f"  dir=DRAW: n={n}, hit %{hit*100:.1f} (baseline ~%26)")

    # score_v14 vs score_v13 Q5 karşılaştırma (TRIVOX örneği)
    print("\n" + "-" * 80)
    print(">>> Q5+a2 (TRIVOX) score_v13 vs score_v14 karşılaştırma")
    print("-" * 80)

    for ver in ("score_v13", "score_v14"):
        rows = conn.execute(f"""
            SELECT match_uid, league_code, kickoff_iso, home_team, away_team,
                   {ver}, agree_count,
                   odd_1, odd_X, odd_2, dir_favorite, dir_anomaly, dir_model,
                   dir_xg, dir_form, dir_shots, dir_cards,
                   result_1x2
            FROM signal_snapshots
            WHERE source='football_data' AND settled=1
              AND league_code='T1' AND {ver} IS NOT NULL
        """).fetchall()

        # FAV_CONFIRMED filter
        from trivox_v1 import fav_confirmed, normalize_dir

        picks = []
        # Group by date, take top-1 by score
        df_rows = [dict(r) for r in rows]
        df = pd.DataFrame(df_rows)
        if df.empty: continue
        df["matchday"] = df["kickoff_iso"].astype(str).str[:10]
        df["dir_fc"] = df.apply(lambda r: fav_confirmed(r.to_dict(), 1), axis=1)
        df = df[df["dir_fc"].notna()].sort_values(ver, ascending=False)

        for md, group in df.groupby("matchday"):
            top = group.head(1)
            for _, r in top.iterrows():
                d = r["dir_fc"]
                d_norm = normalize_dir(d)
                if d_norm == "HOME":
                    odd = r["odd_1"]; won = r["result_1x2"]=='H'
                elif d_norm == "AWAY":
                    odd = r["odd_2"]; won = r["result_1x2"]=='A'
                else:
                    odd = r["odd_X"]; won = r["result_1x2"]=='D'
                if not odd or odd < 1.01: continue
                picks.append({
                    "score": float(r[ver]) if pd.notna(r[ver]) else 0,
                    "agree": int(r["agree_count"] or 0),
                    "odd": odd, "won": won,
                })
        if not picks: continue
        df_picks = pd.DataFrame(picks)
        # Quintile
        df_picks["q"] = pd.qcut(df_picks["score"], 5, labels=["Q1","Q2","Q3","Q4","Q5"], duplicates="drop")
        q5 = df_picks[df_picks["q"]=="Q5"]
        q5_a2 = q5[q5["agree"] >= 2]
        if not q5_a2.empty:
            n = len(q5_a2)
            won = int(q5_a2["won"].sum())
            hit = won/n
            avg_odd = q5_a2["odd"].mean()
            print(f"  {ver}: TRIVOX Q5+a2 n={n}, hit %{hit*100:.0f}, "
                  f"avg_odd {avg_odd:.2f}")

    conn.close()


if __name__ == "__main__":
    print("=" * 80)
    print("SEÇENEK D: Match stats sinyalleri (shots/referee/cards)")
    print("=" * 80)
    add_columns()
    apply_signals()
    report()
