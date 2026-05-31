"""
APPLY MATCH STATS SIGNALS — FAST BATCH VERSION
================================================

Hızlı batch versiyonu:
  - Tüm hesaplama bellekte
  - Tek seferde batch UPDATE
  - Cache yükleme tek seferde

19K satır için ~30 saniye hedef.
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
    shots_form_signal, referee_bias_signal, cards_pressure_signal,
    _load_team_stats_cache, _load_referee_cache,
)


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
    for stmt in EXTEND_SCHEMA.strip().split(";"):
        stmt = stmt.strip()
        if not stmt: continue
        try:
            conn.execute(stmt)
        except Exception as e:
            if "duplicate column" not in str(e).lower():
                print(f"  ALTER err: {e}")
    conn.commit()
    conn.close()


def run():
    print("=" * 80)
    print("SEÇENEK D (FAST): Match stats sinyalleri")
    print("=" * 80)

    add_columns()

    print("\n[1] Caches yukleniyor...")
    _load_team_stats_cache()
    _load_referee_cache()
    print("    OK")

    # === REFEREE LOOKUP — toplu çek ===
    print("\n[2] Referee lookup batch query...")
    conn = db.connect()
    df_m2 = pd.read_sql_query("""
        SELECT matchday, home_team, away_team, referee
        FROM matches_v2 WHERE referee IS NOT NULL AND referee != ''
    """, conn)
    ref_map = {}
    for _, r in df_m2.iterrows():
        key = (r["matchday"], r["home_team"], r["away_team"])
        ref_map[key] = r["referee"]
    print(f"    {len(ref_map)} maç-referee mapping hazır")

    # === SIGNAL_SNAPSHOTS toplu çek ===
    print("\n[3] signal_snapshots batch read...")
    df_ss = pd.read_sql_query("""
        SELECT match_uid, kickoff_iso, home_team, away_team,
               league_code, season,
               s_anomaly, s_model, s_sharp, s_invvar, s_xg, s_form
        FROM signal_snapshots WHERE source='football_data'
    """, conn)
    print(f"    {len(df_ss)} satir okundu")
    conn.close()

    # === HESAPLAMA in-memory ===
    print(f"\n[4] {len(df_ss)} satir icin sinyal hesaplama...")
    updates = []
    n_shots = 0; n_ref = 0; n_cards = 0
    for i, r in df_ss.iterrows():
        if i % 2000 == 0 and i > 0:
            print(f"    {i}/{len(df_ss)}")
        try:
            md = str(r["kickoff_iso"])[:10]
            home = r["home_team"]; away = r["away_team"]
            referee = ref_map.get((md, home, away))

            s_shots_r = shots_form_signal(home, away, md)
            s_ref_r = referee_bias_signal(referee, md) if referee else {"s_referee": None, "direction": None}
            s_cards_r = cards_pressure_signal(home, away, md)

            ss = s_shots_r.get("s_shots") or 0
            sd = s_shots_r.get("direction")
            sr = s_ref_r.get("s_referee") or 0
            rd = s_ref_r.get("direction")
            sc = s_cards_r.get("s_cards") or 0
            cd = s_cards_r.get("direction")

            if ss > 0: n_shots += 1
            if sr > 0: n_ref += 1
            if sc > 0: n_cards += 1

            # score_v14 hesap
            parts = []
            if pd.notna(r.get("s_anomaly")): parts.append((0.20, r["s_anomaly"]))
            if pd.notna(r.get("s_model")): parts.append((0.18, r["s_model"]))
            if pd.notna(r.get("s_sharp")): parts.append((0.08, r["s_sharp"]))
            if pd.notna(r.get("s_invvar")): parts.append((0.08, r["s_invvar"]))
            if pd.notna(r.get("s_xg")) and r["s_xg"] > 0: parts.append((0.15, r["s_xg"]))
            if pd.notna(r.get("s_form")) and r["s_form"] > 0: parts.append((0.12, r["s_form"]))
            if ss > 0: parts.append((0.08, ss))
            if sr > 0: parts.append((0.05, sr))
            if sc > 0: parts.append((0.06, sc))
            if parts:
                w = sum(w for w,_ in parts)
                score_v14 = sum(w*v for w,v in parts) / w
            else:
                score_v14 = 0.0

            updates.append((ss, sd, sr, rd, sc, cd, score_v14, r["match_uid"]))
        except Exception as e:
            pass

    print(f"\n[5] Batch UPDATE: {len(updates)} satir...")
    conn = db.connect()
    conn.executemany("""
        UPDATE signal_snapshots
        SET s_shots=?, dir_shots=?, s_referee=?, dir_referee=?,
            s_cards=?, dir_cards=?, score_v14=?
        WHERE match_uid=? AND source='football_data'
    """, updates)
    conn.commit()
    conn.close()

    print(f"\n[OK] Tamamlandı!")
    print(f"  s_shots > 0:   {n_shots} ({n_shots/len(df_ss)*100:.0f}%)")
    print(f"  s_referee > 0: {n_ref} ({n_ref/len(df_ss)*100:.0f}%)")
    print(f"  s_cards > 0:   {n_cards} ({n_cards/len(df_ss)*100:.0f}%)")


if __name__ == "__main__":
    run()
