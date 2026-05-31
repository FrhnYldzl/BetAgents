"""
signal_snapshots'a SP1+I1+F1 ekle (DC olmadan, sadece anomaly+xG+form).

DC modeli yoksa: s_model=None, dir_model=None.
FAV_CONFIRMED hala çalışır (favori + xG/form/anomaly'den en az 1 teyit).
"""
from __future__ import annotations

import sys
import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd

THIS_DIR = Path(__file__).resolve().parent
YAZILIM = THIS_DIR.parent
sys.path.insert(0, str(THIS_DIR))
sys.path.insert(0, str(YAZILIM / "03_MODELLER"))
sys.path.insert(0, str(YAZILIM / "03_MODELLER" / "selective"))
sys.path.insert(0, str(YAZILIM / "04_BACKTEST"))

import database as db
from selective_backtest import load_week, fd_signals
from extra_signals import _load_xg_cache, xg_luck_signal, form_signal_from_cache, build_form_cache_from_df


EXTRA_LEAGUES = ["SP1", "I1", "F1"]
SEASONS = ["2122", "2223", "2324", "2425"]


def fav_dir(r):
    psc_h, psc_d, psc_a = r.get("psc_h"), r.get("psc_d"), r.get("psc_a")
    if not (psc_h and psc_d and psc_a and psc_h > 1.01):
        return None
    m = min(psc_h, psc_d, psc_a)
    if m == psc_h: return "H"
    if m == psc_a: return "A"
    return "D"


def make_uid(lg, ss, h, a, d):
    h_clean = h.lower().replace(" ", "_").replace("'", "")
    a_clean = a.lower().replace(" ", "_").replace("'", "")
    return f"{lg}_{ss}_{h_clean}_vs_{a_clean}_{d[:10]}"


def run():
    print(f"[extra_load] {EXTRA_LEAGUES} × {SEASONS} yükleniyor...")
    _load_xg_cache()

    conn = db.connect()
    now = datetime.utcnow().isoformat()
    n_loaded = 0

    for lg in EXTRA_LEAGUES:
        for ss in SEASONS:
            try:
                df = load_week(lg, ss)
            except FileNotFoundError:
                continue
            if df.empty:
                continue
            form_cache = build_form_cache_from_df(df)
            print(f"  [{lg}_{ss}] {len(df)} maç işleniyor...")

            for _, row in df.iterrows():
                try:
                    # fd_signals (params=None → DC yok)
                    sig = fd_signals(row, params=None)
                    date_str = str(sig["date"])[:10]
                    # xG
                    xg = xg_luck_signal(row["HomeTeam"], row["AwayTeam"], date_str)
                    # form
                    fs = form_signal_from_cache(row["HomeTeam"], row["AwayTeam"],
                                                 date_str, form_cache)
                    fav = fav_dir(sig)
                    # AGREE count
                    dirs = [sig.get("signal_direction"), xg.get("direction"),
                            fs.get("direction")]
                    dirs = [d for d in dirs if d and str(d) != "nan"]
                    from collections import Counter
                    cnt = Counter(dirs).most_common(1) if dirs else []
                    agree_count = cnt[0][1] if cnt else 0

                    ftr = row.get("FTR")
                    settled = 1 if ftr in ("H", "D", "A") else 0
                    fthg = row.get("FTHG"); ftag = row.get("FTAG")
                    tg = (fthg or 0) + (ftag or 0) if settled else None
                    bts = 1 if settled and fthg and ftag and fthg >= 1 and ftag >= 1 else 0 if settled else None

                    # score_v13 (DC olmadan adapt)
                    parts = []
                    if sig.get("s_anomaly") is not None:
                        parts.append((0.30, sig["s_anomaly"]))
                    if xg.get("s_xg") and xg["s_xg"] > 0:
                        parts.append((0.25, xg["s_xg"]))
                    if fs.get("s_form") and fs["s_form"] > 0:
                        parts.append((0.20, fs["s_form"]))
                    if sig.get("s_invvar") is not None:
                        parts.append((0.10, sig["s_invvar"]))
                    score_v13 = sum(w*v for w,v in parts) / sum(w for w,_ in parts) if parts else 0

                    uid = make_uid(lg, ss, row["HomeTeam"], row["AwayTeam"], date_str)
                    row_data = {
                        "match_uid": uid, "league_code": lg, "season": ss,
                        "kickoff_iso": date_str,
                        "home_team": row["HomeTeam"], "away_team": row["AwayTeam"],
                        "odd_1": sig.get("psc_h"), "odd_X": sig.get("psc_d"),
                        "odd_2": sig.get("psc_a"),
                        "odd_over25": sig.get("pc_over"), "odd_under25": sig.get("pc_under"),
                        "s_anomaly": sig.get("s_anomaly"),
                        "s_model": None,
                        "s_xg": xg.get("s_xg") or 0,
                        "s_form": fs.get("s_form") or 0,
                        "s_invvar": sig.get("s_invvar"),
                        "dir_anomaly": sig.get("signal_direction"),
                        "dir_model": None,
                        "dir_xg": xg.get("direction"),
                        "dir_form": fs.get("direction"),
                        "dir_favorite": fav,
                        "score_v13": score_v13,
                        "agree_count": agree_count,
                        "signal_count": len(dirs),
                        "result_1x2": ftr if settled else None,
                        "home_score": fthg if settled else None,
                        "away_score": ftag if settled else None,
                        "total_goals": tg, "ft_btts": bts, "settled": settled,
                        "created_at": now,
                    }
                    cols = ",".join(["snapshot_id", "source"] + list(row_data.keys()))
                    placeholders = ",".join(["?"] * (len(row_data) + 2))
                    conn.execute(
                        f"INSERT OR REPLACE INTO signal_snapshots({cols}) VALUES({placeholders})",
                        ("fd_backtest", "football_data", *row_data.values())
                    )
                    n_loaded += 1
                except Exception as e:
                    pass
            conn.commit()

    conn.close()
    print(f"[OK] {n_loaded} ekstra satir yuklendi")

    # Stats
    conn = db.connect()
    for r in conn.execute(
        "SELECT league_code, season, COUNT(*) FROM signal_snapshots "
        "WHERE league_code IN ('SP1','I1','F1') GROUP BY 1,2"
    ):
        print(f"  {r[0]}/{r[1]}: {r[2]}")
    conn.close()


if __name__ == "__main__":
    run()
