"""
SELECTIVE EDGE v1.4 — Standardize Sinyal Veritabanı

TEK MASTER TABLO: signal_snapshots
    Tüm sinyaller (anomaly, model, xG, form, sharp, line movement, tipster, ...)
    + tüm odds (1X2, OU, BTTS, HC, ...) + outcome + meta
    her maç-snapshot tek satır.

UI'da bu tablo üzerinde:
    - Pivot, filtre, sort
    - Strateji deneme (live what-if)
    - Backtest replay
    - Bulgu replikasyonu

Şema:
    snapshot_id, match_uid (lig+sezon+home+away+date)
    source (iddaa | football_data | manual)
    home_team, away_team, league_code, season, kickoff
    Odds:
        odd_1, odd_X, odd_2, odd_over25, odd_under25, odd_btts_yes, odd_btts_no
        odd_open_1, odd_open_X, ... (varsa)
    Signals:
        s_anomaly, s_model, s_xg, s_form, s_sharp, s_invvar, s_tipster
    Directions:
        dir_anomaly, dir_model, dir_xg, dir_form, dir_consensus
    Scores:
        score_v12, score_v13
    Outcome (varsa):
        result_1x2 (H/D/A), total_goals, ft_btts, settled
"""
from __future__ import annotations

import sys
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS_DIR))

import database as db


SCHEMA = """
CREATE TABLE IF NOT EXISTS signal_snapshots (
    -- Identification
    snapshot_id     TEXT NOT NULL,            -- 'YYYY-MM-DD-HHMM' veya 'fd_backtest'
    match_uid       TEXT NOT NULL,            -- 'E0_2223_arsenal_vs_chelsea_2023-04-01'
    source          TEXT NOT NULL,            -- 'iddaa', 'football_data', 'manual'
    iddaa_match_id  TEXT,                     -- iddaa.com event id (varsa)
    fixture_id      INTEGER,                  -- api-football fixture id (varsa)

    -- Meta
    league_code     TEXT,
    season          TEXT,
    kickoff_iso     TEXT,
    home_team       TEXT NOT NULL,
    away_team       TEXT NOT NULL,

    -- Odds (closing varsa)
    odd_1           REAL,
    odd_X           REAL,
    odd_2           REAL,
    odd_over25      REAL,
    odd_under25     REAL,
    odd_btts_yes    REAL,
    odd_btts_no     REAL,

    -- Odds (opening, line movement için)
    odd_open_1      REAL,
    odd_open_X      REAL,
    odd_open_2      REAL,
    odd_open_over25 REAL,
    odd_open_under25 REAL,

    -- Derived stats
    fp_1            REAL,        -- fair prob (vig stripped)
    fp_X            REAL,
    fp_2            REAL,
    fp_over25       REAL,
    fp_under25      REAL,
    fp_btts_yes     REAL,
    fp_btts_no      REAL,
    overround_1x2   REAL,
    overround_ou    REAL,
    overround_btts  REAL,

    -- Signals (0-1 range, NULL = data yok)
    s_anomaly       REAL,
    s_model         REAL,
    s_xg            REAL,
    s_form          REAL,
    s_sharp         REAL,
    s_invvar        REAL,
    s_tipster       REAL,

    -- Directions ('HOME', 'AWAY', 'DRAW', 'Over', 'Under', 'BTTS_YES', 'BTTS_NO')
    dir_anomaly     TEXT,
    dir_model       TEXT,
    dir_xg          TEXT,
    dir_form        TEXT,
    dir_sharp       TEXT,
    dir_tipster     TEXT,
    dir_consensus   TEXT,
    dir_favorite    TEXT,

    -- Scores
    score_v12       REAL,
    score_v13       REAL,

    -- AGREE counts (consensus rapor için)
    agree_count     INTEGER,             -- aynı yöne işaret eden sinyal sayısı
    signal_count    INTEGER,             -- toplam sinyal (None olmayan)

    -- DC model details
    model_lam_h     REAL,
    model_lam_a     REAL,
    model_league    TEXT,
    model_max_edge  REAL,

    -- xG details
    xg_luck_diff    REAL,

    -- Form details
    form_delta      REAL,

    -- Outcome (sonradan settle edilir, başta NULL)
    result_1x2      TEXT,                -- 'H','D','A'
    home_score      INTEGER,
    away_score      INTEGER,
    total_goals     INTEGER,
    ft_btts         INTEGER,             -- 1=both teams scored
    settled         INTEGER DEFAULT 0,   -- 1=match finished

    -- PnL tracking (her snapshot için çoklu strateji)
    pnl_top3_v13    REAL,
    pnl_agree23     REAL,
    pnl_fav         REAL,
    pnl_xg_fav      REAL,

    -- Audit
    created_at      TEXT NOT NULL,

    PRIMARY KEY (snapshot_id, match_uid)
);

CREATE INDEX IF NOT EXISTS idx_signal_snap_league ON signal_snapshots(league_code, season);
CREATE INDEX IF NOT EXISTS idx_signal_snap_date ON signal_snapshots(kickoff_iso);
CREATE INDEX IF NOT EXISTS idx_signal_snap_score ON signal_snapshots(score_v13 DESC);
CREATE INDEX IF NOT EXISTS idx_signal_snap_settled ON signal_snapshots(settled, result_1x2);
CREATE INDEX IF NOT EXISTS idx_signal_snap_source ON signal_snapshots(source, snapshot_id);
"""


def init_schema():
    conn = db.connect()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
        print("[OK] signal_snapshots schema hazir")
    finally:
        conn.close()


def make_match_uid(league: str, season: str, home: str, away: str, date: str) -> str:
    h = home.lower().replace(" ", "_").replace("'", "")
    a = away.lower().replace(" ", "_").replace("'", "")
    return f"{league}_{season}_{h}_vs_{a}_{date[:10]}"


def upsert_snapshot(snapshot_id: str, source: str, **fields) -> None:
    """Bir snapshot satırı yaz/güncelle."""
    from datetime import datetime
    conn = db.connect()
    try:
        cols = ["snapshot_id", "source", "created_at"]
        vals = [snapshot_id, source, datetime.utcnow().isoformat()]
        for k, v in fields.items():
            cols.append(k)
            vals.append(v)
        placeholders = ",".join(["?"] * len(vals))
        col_str = ",".join(cols)
        try:
            conn.execute(
                f"INSERT OR REPLACE INTO signal_snapshots({col_str}) VALUES({placeholders})",
                tuple(vals)
            )
            conn.commit()
        except Exception as e:
            print(f"upsert err: {e}")
    finally:
        conn.close()


def bulk_load_from_backtest():
    """4-sezon backtest verisini signal_snapshots'a yükle."""
    import sys
    sys.path.insert(0, str(THIS_DIR.parent / "03_MODELLER"))
    sys.path.insert(0, str(THIS_DIR.parent / "03_MODELLER" / "selective"))
    sys.path.insert(0, str(THIS_DIR.parent / "04_BACKTEST"))

    from consistency_test_v2 import compute_signals_v13
    import consistency_test_v2

    consistency_test_v2.SEASONS = ["2122", "2223", "2324", "2425"]
    consistency_test_v2.LEAGUES = ["E0", "D1", "T1"]

    print("[bulk_load] Sinyalleri 4 sezon × 3 lig için hesaplıyor...")
    df = compute_signals_v13(verbose=False)
    print(f"[bulk_load] {len(df)} mac")

    conn = db.connect()
    init_schema()
    from datetime import datetime
    now = datetime.utcnow().isoformat()

    def fav_dir(r):
        odds = [r.get("psc_h"), r.get("psc_d"), r.get("psc_a")]
        if not all(o and o > 1.01 for o in odds):
            return None
        m = min(odds)
        if m == odds[0]: return "H"
        if m == odds[2]: return "A"
        return "D"

    n_loaded = 0
    for _, r in df.iterrows():
        try:
            kickoff = str(r["date"])[:10]
            uid = make_match_uid(r["league"], r["season"], r["home"], r["away"], kickoff)
            # AGREE count
            dirs = [r.get("model_direction"), r.get("signal_direction"),
                    r.get("xg_direction"), r.get("form_direction")]
            dirs = [d for d in dirs if d and str(d) != "nan"]
            from collections import Counter
            cnt = Counter(dirs).most_common(1)
            agree_count = cnt[0][1] if cnt else 0

            # Outcome
            settled = 1 if r.get("ftr") in ("H", "D", "A") else 0
            total_goals = (r.get("fthg") or 0) + (r.get("ftag") or 0) if settled else None
            ft_btts = 1 if (r.get("fthg",0) >= 1 and r.get("ftag",0) >= 1) else 0

            # PnL hesabı (her strateji için)
            def pnl_for(dir_, odd):
                if not dir_ or not odd or not settled:
                    return None
                won = False
                if dir_ in ("HOME", "H", "1"): won = r["ftr"] == "H"
                elif dir_ in ("AWAY", "A", "2"): won = r["ftr"] == "A"
                elif dir_ in ("DRAW", "D", "X"): won = r["ftr"] == "D"
                elif dir_ == "Over": won = total_goals and total_goals > 2.5
                elif dir_ == "Under": won = total_goals is not None and total_goals < 2.5
                return (odd - 1) if won else -1

            fav = fav_dir(r)
            fav_odd = r.get(f"psc_{fav.lower()}") if fav else None
            # actually columns are psc_h, psc_d, psc_a
            if fav == "H": fav_odd = r.get("psc_h")
            elif fav == "A": fav_odd = r.get("psc_a")
            elif fav == "D": fav_odd = r.get("psc_d")

            pnl_fav = pnl_for(fav, fav_odd)

            # Top3 v1.3 picks: model_direction with its odd
            model_d = r.get("model_direction")
            model_odd = None
            if model_d in ("1","H","HOME"): model_odd = r.get("psc_h")
            elif model_d in ("2","A","AWAY"): model_odd = r.get("psc_a")
            elif model_d in ("X","D","DRAW"): model_odd = r.get("psc_d")
            elif model_d == "Over": model_odd = r.get("pc_over")
            elif model_d == "Under": model_odd = r.get("pc_under")
            pnl_top3 = pnl_for(model_d, model_odd) if r.get("score_v13", 0) >= 0.85 else None

            row = {
                "match_uid": uid,
                "iddaa_match_id": None,
                "league_code": r["league"],
                "season": r["season"],
                "kickoff_iso": kickoff,
                "home_team": r["home"],
                "away_team": r["away"],
                "odd_1": r.get("psc_h"),
                "odd_X": r.get("psc_d"),
                "odd_2": r.get("psc_a"),
                "odd_over25": r.get("pc_over"),
                "odd_under25": r.get("pc_under"),
                "s_anomaly": r.get("s_anomaly"),
                "s_model": r.get("s_model"),
                "s_xg": r.get("s_xg"),
                "s_form": r.get("s_form"),
                "s_sharp": r.get("s_sharp"),
                "s_invvar": r.get("s_invvar"),
                "dir_anomaly": r.get("signal_direction"),
                "dir_model": r.get("model_direction"),
                "dir_xg": r.get("xg_direction"),
                "dir_form": r.get("form_direction"),
                "dir_sharp": r.get("sharp_direction"),
                "dir_consensus": r.get("consensus_direction"),
                "dir_favorite": fav,
                "score_v12": r.get("score_v12"),
                "score_v13": r.get("score_v13"),
                "agree_count": agree_count,
                "signal_count": len(dirs),
                "model_lam_h": r.get("model_lam_h"),
                "model_lam_a": r.get("model_lam_a"),
                "model_max_edge": r.get("model_max_edge"),
                "xg_luck_diff": r.get("xg_luck_diff"),
                "form_delta": r.get("form_delta"),
                "result_1x2": r.get("ftr") if settled else None,
                "home_score": r.get("fthg") if settled else None,
                "away_score": r.get("ftag") if settled else None,
                "total_goals": total_goals,
                "ft_btts": ft_btts if settled else None,
                "settled": settled,
                "pnl_fav": pnl_fav,
                "pnl_top3_v13": pnl_top3,
                "created_at": now,
            }
            cols = ",".join(["snapshot_id", "source"] + list(row.keys()))
            placeholders = ",".join(["?"] * (len(row) + 2))
            conn.execute(
                f"INSERT OR REPLACE INTO signal_snapshots({cols}) VALUES({placeholders})",
                ("fd_backtest", "football_data", *row.values())
            )
            n_loaded += 1
        except Exception as e:
            # bir satır hatası akışı durdurmasın
            pass
    conn.commit()
    conn.close()
    print(f"[OK] {n_loaded} satir yuklendi (kaynak: football_data backtest)")


def stats():
    conn = db.connect()
    try:
        n = conn.execute("SELECT COUNT(*) FROM signal_snapshots").fetchone()[0]
        n_set = conn.execute("SELECT COUNT(*) FROM signal_snapshots WHERE settled=1").fetchone()[0]
        print(f"=== signal_snapshots ===")
        print(f"  Toplam: {n:,}")
        print(f"  Settled: {n_set:,}")
        for r in conn.execute(
            "SELECT source, league_code, season, COUNT(*) as n "
            "FROM signal_snapshots GROUP BY source, league_code, season ORDER BY 1,2,3"
        ).fetchall():
            print(f"  {r['source']:15s} {r['league_code']}/{r['season']}: {r['n']}")
    finally:
        conn.close()


if __name__ == "__main__":
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "init"
    if cmd == "init":
        init_schema()
    elif cmd == "load":
        init_schema()
        bulk_load_from_backtest()
        stats()
    elif cmd == "stats":
        stats()
    else:
        print("Komutlar: init | load | stats")
