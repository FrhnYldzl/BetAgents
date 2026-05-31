"""
SEÇENEK A — DC retrain + sinyal regen for 2017-2021 sezonları
==============================================================

Yeni 4 sezon (1718, 1819, 1920, 2021) için:
  - DC modeli sinyalleri (mevcut DC parametreleriyle)
  - anomaly + form sinyalleri
  - xG NULL (data yok bu dönem için)
  - score_v13 hesapla
  - signal_snapshots tablosuna INSERT et

Hedef: 19K maç hepsi model-ready, V2 retrain için sample 2x büyür.
"""
from __future__ import annotations

import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

import pandas as pd

THIS_DIR = Path(__file__).resolve().parent
YAZILIM = THIS_DIR.parent
sys.path.insert(0, str(THIS_DIR))
sys.path.insert(0, str(YAZILIM / "04_BACKTEST"))
sys.path.insert(0, str(YAZILIM / "03_MODELLER"))
sys.path.insert(0, str(YAZILIM / "03_MODELLER" / "selective"))

import database as db
import consistency_test_v2


SEASON_CONV = {
    "1718":"2017-18","1819":"2018-19","1920":"2019-20","2021":"2020-21",
}


def normalize_dir(d):
    if d in ("HOME","H","1"): return "HOME"
    if d in ("AWAY","A","2"): return "AWAY"
    if d in ("DRAW","D","X"): return "DRAW"
    return d


def build_match_uid(league, season_code, home, away, date_str):
    """signal_snapshots'taki UID formatına uy."""
    def slug(s):
        return s.lower().replace(" ", "_").replace("'", "")
    return f"{league}_{season_code}_{slug(home)}_vs_{slug(away)}_{date_str[:10]}"


def already_loaded(conn, season_code: str) -> int:
    """Bu sezon için kaç row var?"""
    r = conn.execute(
        "SELECT COUNT(*) FROM signal_snapshots WHERE source='football_data' AND season=?",
        (season_code,)
    ).fetchone()
    return r[0] if r else 0


def insert_row(conn, row_data: dict, now_iso: str):
    """signal_snapshots'a yeni satır ekle (varsa atla)."""
    # Required fields
    if not row_data.get("match_uid"):
        return False
    # Existing check (UPSERT)
    existing = conn.execute(
        "SELECT 1 FROM signal_snapshots WHERE match_uid=? AND source='football_data'",
        (row_data["match_uid"],)
    ).fetchone()
    if existing:
        return False  # skip if exists

    cols = list(row_data.keys())
    placeholders = ", ".join("?" for _ in cols)
    col_list = ", ".join(cols)
    try:
        conn.execute(
            f"INSERT INTO signal_snapshots ({col_list}) VALUES ({placeholders})",
            list(row_data.values())
        )
        return True
    except Exception as e:
        print(f"  INSERT err: {e} | uid={row_data.get('match_uid')}")
        return False


def run():
    print("=" * 80)
    print("SEÇENEK A: DC retrain + sinyal regen for 2017-2021")
    print("=" * 80)

    # Önce mevcut durumu görelim
    conn = db.connect()
    print("\nMevcut signal_snapshots durumu:")
    for ss_code in ("1718","1819","1920","2021","2122","2223","2324","2425","2526"):
        n = already_loaded(conn, ss_code)
        canon = SEASON_CONV.get(ss_code, ss_code)
        print(f"  {ss_code} ({canon}): {n} satir")
    conn.close()

    # consistency_test_v2'yi yeni 4 sezon icin calistir
    print("\n[1] Yeni 4 sezon için sinyal hesaplama başlatılıyor...")
    consistency_test_v2.SEASONS = ["1718", "1819", "1920", "2021"]
    consistency_test_v2.LEAGUES = ["T1", "E0", "D1", "SP1", "I1", "F1"]

    df = consistency_test_v2.compute_signals_v13(verbose=True)
    print(f"\n  Hesaplanan toplam: {len(df)} satir")

    # signal_snapshots'a ekle
    print("\n[2] signal_snapshots'a INSERT yapiliyor...")
    conn = db.connect()
    now = datetime.utcnow().isoformat()
    n_inserted = 0
    n_skipped = 0
    n_err = 0

    for _, r in df.iterrows():
        try:
            kickoff = str(r['date'])[:10]
            uid = build_match_uid(
                r['league'], r['season'], r['home'], r['away'], kickoff
            )

            # Directions
            dirs = [r.get('model_direction'), r.get('signal_direction'),
                    r.get('xg_direction'), r.get('form_direction')]
            dirs = [d for d in dirs if d and str(d) != 'nan']
            cnt = Counter(dirs).most_common(1)
            agree_count = cnt[0][1] if cnt else 0
            settled = 1 if r.get('ftr') in ('H','D','A') else 0
            home_score = int(r['fthg']) if pd.notna(r.get('fthg')) else None
            away_score = int(r['ftag']) if pd.notna(r.get('ftag')) else None
            total_goals = ((home_score or 0) + (away_score or 0)) if settled else None
            btts = 1 if (home_score and away_score and home_score>0 and away_score>0) else 0

            # Favori (Pinnacle closing)
            psc_h = r.get('psc_h'); psc_d = r.get('psc_d'); psc_a = r.get('psc_a')
            fav = None
            if psc_h and psc_d and psc_a:
                m = min(psc_h, psc_d, psc_a)
                fav = 'H' if m == psc_h else ('A' if m == psc_a else 'D')

            row_data = {
                "snapshot_id": "fd_backtest_2017_2021",
                "match_uid": uid,
                "source": "football_data",
                "league_code": r['league'],
                "season": r['season'],
                "kickoff_iso": kickoff,
                "home_team": r['home'],
                "away_team": r['away'],
                # Odds (closing)
                "odd_1": psc_h, "odd_X": psc_d, "odd_2": psc_a,
                "odd_over25": r.get('pc_over'), "odd_under25": r.get('pc_under'),
                # Odds (opening - B365)
                "odd_open_1": r.get('b_h'), "odd_open_X": r.get('b_d'),
                "odd_open_2": r.get('b_a'),
                "odd_open_over25": r.get('b_over'), "odd_open_under25": r.get('b_under'),
                # Signals
                "s_model": r.get('s_model'),
                "s_anomaly": r.get('s_anomaly'),
                "s_xg": r.get('s_xg'),
                "s_form": r.get('s_form'),
                "s_sharp": r.get('s_sharp'),
                "s_invvar": r.get('s_invvar'),
                # Directions
                "dir_model": r.get('model_direction'),
                "dir_anomaly": r.get('signal_direction'),
                "dir_xg": r.get('xg_direction'),
                "dir_form": r.get('form_direction'),
                "dir_consensus": r.get('consensus_direction'),
                "dir_favorite": fav,
                # Scores
                "score_v12": r.get('score_v12'),
                "score_v13": r.get('score_v13'),
                "agree_count": agree_count,
                "signal_count": len(dirs),
                # Model meta
                "model_lam_h": r.get('model_lam_h'),
                "model_lam_a": r.get('model_lam_a'),
                "model_max_edge": r.get('model_max_edge'),
                "model_league": r['league'],
                "xg_luck_diff": r.get('xg_luck_diff'),
                "form_delta": r.get('form_delta'),
                # Outcome
                "result_1x2": r.get('ftr'),
                "home_score": home_score,
                "away_score": away_score,
                "total_goals": total_goals,
                "ft_btts": btts if settled else None,
                "settled": settled,
                "created_at": now,
            }

            ok = insert_row(conn, row_data, now)
            if ok: n_inserted += 1
            else: n_skipped += 1
        except Exception as e:
            n_err += 1
            if n_err <= 3:
                print(f"  ROW ERR: {e}")

    conn.commit()

    # Verify
    print("\n[3] Verification — son durum:")
    for ss_code in ("1718","1819","1920","2021"):
        n = already_loaded(conn, ss_code)
        canon = SEASON_CONV.get(ss_code, ss_code)
        print(f"  {ss_code} ({canon}): {n} satir")

    n_total = conn.execute(
        "SELECT COUNT(*) FROM signal_snapshots WHERE source='football_data'"
    ).fetchone()[0]
    print(f"\n  TOPLAM signal_snapshots: {n_total} (eski 10,657 + yeni)")

    conn.close()

    print(f"\n[OK] Inserted: {n_inserted}, Skipped: {n_skipped}, Err: {n_err}")
    print(f"\n[+] V2 retrain için tam sample hazır!")


if __name__ == "__main__":
    run()
