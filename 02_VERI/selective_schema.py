"""
SELECTIVE EDGE v1.0 — Database schema extensions.

3 yeni tablo:
    iddaa_odds      — iddaa.com'dan çekilen TÜM pazar oranları (1X2, A/Ü, KG, Hcp, Çifte Şans, ...)
                      Bir maç için 7+ pazar aynı anda → odds_anomaly hesabı için
    tipster_picks   — Türk + dünya yorumcuların kuponları (iddaa yazar, Mackolik, OLBG, Tipstrr, BlogAbet)
    tipster_stats   — Her yorumcunun toplam track-record skoru

Tasarım kararı:
    iddaa_odds.market = '1X2' | 'OU2.5' | 'BTTS' | 'HC+1' | 'HC-1' | 'DC' | 'HT_FT' ...
    iddaa_odds.selection = '1' | 'X' | '2' | 'Over' | 'Under' | 'Yes' | 'No' | '1X' | '12' | 'X2' | ...

    Bir fixture için tüm market+selection kombinasyonlarını çekiyoruz → snapshot.
    snapshot_id ile zaman boyunca odds değişimini takip edebiliriz (line movement = sharp signal).
"""
from __future__ import annotations

import sys
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS_DIR))

import database as db


SELECTIVE_SCHEMA = """
-- ============================================================
-- IDDAA ODDS — Tüm pazar oranları (snapshot bazlı)
-- ============================================================
CREATE TABLE IF NOT EXISTS iddaa_odds (
    snapshot_id     TEXT NOT NULL,           -- 'YYYY-MM-DD-HHMM' bazlı çekim anı
    fixture_id      INTEGER,                  -- (varsa) api-football fixture eşleşmesi
    iddaa_match_id  TEXT NOT NULL,            -- iddaa'nın kendi maç ID'si
    league_code     TEXT,
    kickoff_iso     TEXT NOT NULL,
    home_team       TEXT NOT NULL,
    away_team       TEXT NOT NULL,
    market          TEXT NOT NULL,            -- '1X2','OU2.5','BTTS','HC+1','DC','HT_FT',...
    selection       TEXT NOT NULL,            -- '1','X','2','Over','Under','Yes','No','1X',...
    odd             REAL NOT NULL,
    implied_prob    REAL,                     -- 1/odd
    fetched_at      TEXT NOT NULL,
    raw_json        TEXT,
    PRIMARY KEY(snapshot_id, iddaa_match_id, market, selection)
);

CREATE INDEX IF NOT EXISTS idx_iddaa_odds_match
    ON iddaa_odds(iddaa_match_id, market);
CREATE INDEX IF NOT EXISTS idx_iddaa_odds_kickoff
    ON iddaa_odds(kickoff_iso);
CREATE INDEX IF NOT EXISTS idx_iddaa_odds_fixture
    ON iddaa_odds(fixture_id);

-- ============================================================
-- TIPSTER PICKS — Yorumcuların kuponları
-- ============================================================
CREATE TABLE IF NOT EXISTS tipster_picks (
    pick_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    tipster_id      TEXT NOT NULL,            -- 'iddaa:hasanyildirim', 'olbg:user123'
    tipster_name    TEXT,
    source          TEXT NOT NULL,            -- 'iddaa','mackolik','olbg','tipstrr','blogabet'
    posted_at       TEXT,                     -- kupon yazılma zamanı
    kickoff_iso     TEXT,                     -- maç zamanı
    home_team       TEXT NOT NULL,
    away_team       TEXT NOT NULL,
    market          TEXT NOT NULL,
    selection       TEXT NOT NULL,
    pick_odd        REAL,                     -- yorumcunun gördüğü oran
    stake_units     REAL,                     -- birimi (varsa)
    confidence      REAL,                     -- yorumcunun güveni (varsa) 0-1
    -- Sonuç tracking
    settled         INTEGER NOT NULL DEFAULT 0,
    won             INTEGER,                  -- 1=tuttu, 0=tutmadı, NULL=henüz oynanmadı
    inserted_at     TEXT NOT NULL,
    raw_json        TEXT
);

CREATE INDEX IF NOT EXISTS idx_tip_picks_tipster
    ON tipster_picks(tipster_id, posted_at);
CREATE INDEX IF NOT EXISTS idx_tip_picks_match
    ON tipster_picks(home_team, away_team, kickoff_iso);
CREATE INDEX IF NOT EXISTS idx_tip_picks_settled
    ON tipster_picks(settled, won);

-- ============================================================
-- TIPSTER STATS — Track record agregat skoru
-- ============================================================
CREATE TABLE IF NOT EXISTS tipster_stats (
    tipster_id      TEXT PRIMARY KEY,
    tipster_name    TEXT,
    source          TEXT NOT NULL,
    total_picks     INTEGER NOT NULL DEFAULT 0,
    settled_picks   INTEGER NOT NULL DEFAULT 0,
    wins            INTEGER NOT NULL DEFAULT 0,
    win_rate        REAL,                     -- wins/settled_picks
    avg_odd         REAL,                     -- ortalama oran
    roi             REAL,                     -- (won_returns - total_stake) / total_stake
    recent_form_50  REAL,                     -- son 50 picks win rate
    variance        REAL,                     -- ROI varyansı
    score           REAL,                     -- composite score (üst formül)
    last_pick_at    TEXT,
    updated_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_tip_stats_score
    ON tipster_stats(score DESC);
CREATE INDEX IF NOT EXISTS idx_tip_stats_source
    ON tipster_stats(source);

-- ============================================================
-- ODDS ANOMALY CACHE — Hesaplanan sinyal kayıtları (opsiyonel cache)
-- ============================================================
CREATE TABLE IF NOT EXISTS odds_anomaly_signals (
    fixture_id      INTEGER,
    iddaa_match_id  TEXT NOT NULL,
    snapshot_id     TEXT NOT NULL,
    -- Implied prob'lardan türetilen sinyaller
    overround_1x2   REAL,                     -- 1+1+1 - 1
    overround_ou    REAL,                     -- Over+Under - 1
    overround_btts  REAL,                     -- KG var+yok - 1
    -- Pazar tutarlılığı kontrolleri
    consistency_score    REAL,               -- 0-1, pazarlar birbiri ile ne kadar tutarlı
    structural_signal    TEXT,                -- 'home_low_score','away_attack','draw_likely',...
    anomaly_direction    TEXT,                -- 'OVER','UNDER','HOME','AWAY','DRAW','BTTS_YES','BTTS_NO'
    anomaly_strength     REAL,                -- 0-1
    computed_at     TEXT NOT NULL,
    PRIMARY KEY(snapshot_id, iddaa_match_id)
);
"""


def init_selective_schema():
    conn = db.connect()
    try:
        conn.executescript(SELECTIVE_SCHEMA)
        conn.commit()
        print("[OK] SELECTIVE EDGE tablolari hazir:")
        print("     - iddaa_odds")
        print("     - tipster_picks")
        print("     - tipster_stats")
        print("     - odds_anomaly_signals")
    finally:
        conn.close()


def schema_stats():
    conn = db.connect()
    try:
        for tbl in ("iddaa_odds", "tipster_picks", "tipster_stats", "odds_anomaly_signals"):
            try:
                n = conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
                print(f"  {tbl:30s}: {n:>8,} satir")
            except Exception as e:
                print(f"  {tbl:30s}: HENUZ YOK ({e})")
    finally:
        conn.close()


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "init"
    if cmd == "init":
        init_selective_schema()
        schema_stats()
    elif cmd == "stats":
        schema_stats()
    else:
        print("Komutlar: init | stats")
