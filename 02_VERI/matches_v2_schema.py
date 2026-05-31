"""
v2 — matches_v2 Master Schema
==============================

3 yeni tablo:
    matches_v2      — master fact table (her maç = 1 satır)
    team_aliases    — canonical takım ismi mapping
    seasons_meta    — sezon meta verisi (start, end, coverage)

Bu schema v2 modellerin tek girdi noktası olur. Tüm veri kaynakları
matches_v2'ye akar.
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS_DIR))

import database as db


SCHEMA_V2 = """
-- ============================================================
-- MATCHES_V2 — Master fact table
-- ============================================================
CREATE TABLE IF NOT EXISTS matches_v2 (
    match_id            INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Multi-source identifiers
    external_id_fd      TEXT,            -- Football-Data row hash
    external_id_us      TEXT,            -- Understat URL
    external_id_af      INTEGER,         -- api-football fixture_id
    external_id_iddaa   TEXT,            -- iddaa event ID

    -- Canonical meta
    league_code         TEXT NOT NULL,   -- 'T1','E0','D1','SP1','I1','F1'
    season              TEXT NOT NULL,   -- '2021-22', '2022-23', ...
    matchday            TEXT NOT NULL,   -- 'YYYY-MM-DD'
    kickoff_utc         TEXT,            -- ISO datetime
    home_team           TEXT NOT NULL,   -- canonical
    away_team           TEXT NOT NULL,

    -- Result
    status              TEXT,            -- 'NS','LIVE','FT','PST'
    home_score          INTEGER,
    away_score          INTEGER,
    home_score_ht       INTEGER,
    away_score_ht       INTEGER,

    -- Odds — Opening (CLV için)
    opening_1           REAL, opening_X  REAL, opening_2  REAL,
    opening_over25      REAL, opening_under25 REAL,
    opening_source      TEXT,
    opening_fetched_at  TEXT,

    -- Odds — Closing (Pinnacle = referans)
    closing_1           REAL, closing_X  REAL, closing_2  REAL,
    closing_over25      REAL, closing_under25 REAL,
    closing_btts_yes    REAL, closing_btts_no REAL,
    closing_source      TEXT,
    closing_fetched_at  TEXT,

    -- Statistics
    home_xg             REAL,
    away_xg             REAL,
    home_shots          INTEGER,
    away_shots          INTEGER,
    home_possession_pct REAL,
    away_possession_pct REAL,

    -- Injuries / lineup
    home_key_injuries   INTEGER,
    away_key_injuries   INTEGER,
    home_lineup_quality REAL,
    away_lineup_quality REAL,

    -- Quality flags + score
    has_full_odds       INTEGER DEFAULT 0,
    has_opening_odds    INTEGER DEFAULT 0,
    has_xg              INTEGER DEFAULT 0,
    has_result          INTEGER DEFAULT 0,
    is_settled          INTEGER DEFAULT 0,
    quality_score       REAL,

    -- Audit
    ingested_at         TEXT NOT NULL,
    refreshed_at        TEXT,

    UNIQUE(league_code, season, matchday, home_team, away_team)
);

CREATE INDEX IF NOT EXISTS idx_m2_league_season ON matches_v2(league_code, season);
CREATE INDEX IF NOT EXISTS idx_m2_matchday ON matches_v2(matchday);
CREATE INDEX IF NOT EXISTS idx_m2_settled ON matches_v2(is_settled, has_result);
CREATE INDEX IF NOT EXISTS idx_m2_quality ON matches_v2(quality_score);
CREATE INDEX IF NOT EXISTS idx_m2_teams ON matches_v2(home_team, away_team);

-- ============================================================
-- TEAM_ALIASES — Canonical mapping
-- ============================================================
CREATE TABLE IF NOT EXISTS team_aliases (
    alias               TEXT NOT NULL,
    source              TEXT NOT NULL,   -- 'fd','us','af','iddaa'
    league_code         TEXT NOT NULL,
    canonical_name      TEXT NOT NULL,
    notes               TEXT,
    PRIMARY KEY(alias, source, league_code)
);

CREATE INDEX IF NOT EXISTS idx_alias_canonical ON team_aliases(canonical_name, league_code);

-- ============================================================
-- SEASONS_META — Sezon meta
-- ============================================================
CREATE TABLE IF NOT EXISTS seasons_meta (
    league_code         TEXT NOT NULL,
    season              TEXT NOT NULL,
    start_date          TEXT,
    end_date            TEXT,
    n_total_matches     INTEGER,
    n_settled           INTEGER,
    coverage_pct        REAL,
    last_refresh        TEXT,
    PRIMARY KEY(league_code, season)
);

-- ============================================================
-- PICKS_LOG_V2 — Production picks tracking (live shadow)
-- ============================================================
CREATE TABLE IF NOT EXISTS picks_log_v2 (
    pick_id             INTEGER PRIMARY KEY AUTOINCREMENT,
    model               TEXT NOT NULL,   -- 'TRIVOX_v2' or 'EUVOX_v2'
    pick_created_at     TEXT NOT NULL,
    league_code         TEXT NOT NULL,
    matchday            TEXT NOT NULL,
    match_id            INTEGER,         -- FK to matches_v2

    -- Pick details
    K                   INTEGER,         -- combo legs
    leg_no              INTEGER,         -- 1..K
    home_team           TEXT,
    away_team           TEXT,
    direction           TEXT,            -- 'HOME','AWAY','DRAW'
    opening_odd         REAL,            -- alındığı an
    closing_odd         REAL,            -- maç başlarken
    clv_pct             REAL,            -- (open/close - 1) * 100

    -- Pick metadata
    score_v2            REAL,
    confirmers_count    INTEGER,
    signals_used        TEXT,            -- JSON: hangi sinyaller

    -- Stake
    stake_tl            REAL,
    kelly_fraction      REAL,

    -- Outcome
    settled             INTEGER DEFAULT 0,
    won                 INTEGER,
    pnl_gross           REAL,
    pnl_net             REAL,
    settled_at          TEXT,

    FOREIGN KEY(match_id) REFERENCES matches_v2(match_id)
);

CREATE INDEX IF NOT EXISTS idx_picks_model_date ON picks_log_v2(model, pick_created_at);
CREATE INDEX IF NOT EXISTS idx_picks_settled ON picks_log_v2(settled, won);
"""


def init_v2_schema():
    conn = db.connect()
    try:
        conn.executescript(SCHEMA_V2)
        conn.commit()
        print("[OK] v2 schema hazir:")
        for tbl in ("matches_v2", "team_aliases", "seasons_meta", "picks_log_v2"):
            n = conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
            print(f"     {tbl:20s}: {n:>8,} satir")
    finally:
        conn.close()


def stats():
    conn = db.connect()
    try:
        print("=== v2 SCHEMA STATS ===")
        for tbl in ("matches_v2", "team_aliases", "seasons_meta", "picks_log_v2"):
            n = conn.execute(f"SELECTOR COUNT(*) FROM {tbl}".replace("SELECTOR","SELECT")).fetchone()[0]
            print(f"  {tbl:20s}: {n:>8,} satir")
        # matches_v2 details
        n_m2 = conn.execute("SELECT COUNT(*) FROM matches_v2").fetchone()[0]
        if n_m2 > 0:
            print("\n=== matches_v2 dağılım ===")
            for r in conn.execute(
                "SELECT league_code, season, COUNT(*) as n, "
                "AVG(quality_score) as avg_q, "
                "SUM(CASE WHEN is_settled=1 THEN 1 ELSE 0 END) as settled "
                "FROM matches_v2 GROUP BY league_code, season "
                "ORDER BY league_code, season"
            ):
                print(f"  {r[0]:4s}/{r[1]:8s}: n={r[2]:>4} settled={r[3]:>4} "
                      f"avg_q={r[4]:.2f}" if r[4] else f"  {r[0]}/{r[1]}: n={r[2]}")
    finally:
        conn.close()


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "init"
    if cmd == "init":
        init_v2_schema()
    elif cmd == "stats":
        stats()
    else:
        print("Komutlar: init | stats")
