"""
PAPER TRADER — DB Migration
============================
3 yeni tablo olustur: paper_portfolio, paper_coupons, paper_bets
Ilk portfoyu seed'le: PAPER_V1

Calistir:
    python paper_migration.py
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS_DIR))

import database as db


PAPER_SCHEMA = """
-- ============================================================
-- PAPER_PORTFOLIO — Portfoy tanimi ve ozet istatistikler
-- ============================================================
CREATE TABLE IF NOT EXISTS paper_portfolio (
    portfolio_id        TEXT PRIMARY KEY,
    name                TEXT,
    initial_bankroll    REAL,
    current_bankroll    REAL,
    peak_bankroll       REAL,
    total_bets          INTEGER DEFAULT 0,
    total_wins          INTEGER DEFAULT 0,
    total_coupons       INTEGER DEFAULT 0,
    won_coupons         INTEGER DEFAULT 0,
    total_staked        REAL DEFAULT 0,
    total_return        REAL DEFAULT 0,
    status              TEXT DEFAULT 'active',
    strategy_version    TEXT DEFAULT 'v1',
    notes               TEXT,
    created_at          TEXT,
    updated_at          TEXT
);

-- ============================================================
-- PAPER_COUPONS — Kupon kayitlari
-- ============================================================
CREATE TABLE IF NOT EXISTS paper_coupons (
    coupon_id           TEXT PRIMARY KEY,
    portfolio_id        TEXT,
    session_date        TEXT,
    created_at          TEXT,
    coupon_type         TEXT,
    num_legs            INTEGER,
    combined_odds       REAL,
    stake               REAL,
    potential_return    REAL,
    status              TEXT DEFAULT 'open',
    settled_at          TEXT,
    actual_return       REAL DEFAULT 0,
    pnl                 REAL DEFAULT 0,
    model_version       TEXT,
    reasoning           TEXT,
    FOREIGN KEY (portfolio_id) REFERENCES paper_portfolio(portfolio_id)
);

CREATE INDEX IF NOT EXISTS idx_paper_coupons_portfolio
    ON paper_coupons(portfolio_id, status);
CREATE INDEX IF NOT EXISTS idx_paper_coupons_date
    ON paper_coupons(session_date);

-- ============================================================
-- PAPER_BETS — Kupondaki tekil bahis ayaklari
-- ============================================================
CREATE TABLE IF NOT EXISTS paper_bets (
    bet_id              TEXT PRIMARY KEY,
    coupon_id           TEXT,
    portfolio_id        TEXT,
    match_id            INTEGER,
    iddaa_event_id      TEXT,
    league              TEXT,
    home_team           TEXT,
    away_team           TEXT,
    kickoff_utc         TEXT,
    market              TEXT,
    pick                TEXT,
    odds                REAL,
    implied_prob        REAL,
    model_prob          REAL,
    edge                REAL,
    signal_score        REAL,
    signal_name         TEXT,
    status              TEXT DEFAULT 'open',
    result              TEXT,
    home_score          INTEGER,
    away_score          INTEGER,
    settled_at          TEXT,
    FOREIGN KEY (coupon_id) REFERENCES paper_coupons(coupon_id)
);

CREATE INDEX IF NOT EXISTS idx_paper_bets_coupon
    ON paper_bets(coupon_id);
CREATE INDEX IF NOT EXISTS idx_paper_bets_match
    ON paper_bets(match_id);
CREATE INDEX IF NOT EXISTS idx_paper_bets_status
    ON paper_bets(status);

-- ============================================================
-- PAPER_JOURNAL — Model ogrenme gunlugu
-- ============================================================
CREATE TABLE IF NOT EXISTS paper_journal (
    journal_id      TEXT PRIMARY KEY,
    portfolio_id    TEXT DEFAULT 'PAPER_V1',
    entry_date      TEXT,
    entry_type      TEXT,   -- PICK / RESULT / LESSON / THRESHOLD_UPDATE / SESSION_REVIEW
    title           TEXT,
    content         TEXT,   -- detailed text
    signal_name     TEXT,
    signal_score    REAL,
    market          TEXT,
    pick            TEXT,
    odds            REAL,
    actual_result   TEXT,   -- won/lost/void
    pnl             REAL,
    tags            TEXT,   -- comma-sep: KG_VAR,STRONG_SIGNAL,etc
    model_action    TEXT,   -- what the model should do based on this (e.g. LOWER_THRESHOLD)
    created_at      TEXT
);

CREATE INDEX IF NOT EXISTS idx_journal_date ON paper_journal(entry_date);
"""


SEED_PORTFOLIO = {
    "portfolio_id":     "PAPER_V1",
    "name":             "AI Paper Trader v1",
    "initial_bankroll": 5000.0,
    "current_bankroll": 5000.0,
    "peak_bankroll":    5000.0,
    "total_bets":       0,
    "total_wins":       0,
    "total_coupons":    0,
    "won_coupons":      0,
    "total_staked":     0.0,
    "total_return":     0.0,
    "status":           "active",
    "strategy_version": "v1-odds-signals",
    "notes": (
        "Yaz 2026 test portfoyu. Ligler agustos basinda baslar, "
        "o zamana kadar odds-bazli sinyal ile calisiyor."
    ),
    "created_at":  datetime.utcnow().isoformat(),
    "updated_at":  datetime.utcnow().isoformat(),
}


def run_migration() -> None:
    conn = db.connect()
    try:
        # 1. Tablolari olustur
        conn.executescript(PAPER_SCHEMA)
        conn.commit()
        print("[OK] paper_portfolio, paper_coupons, paper_bets tablolari hazir.")

        # 2. Seed portfoyu — varsa guncelleme yapma, yoksa ekle
        existing = conn.execute(
            "SELECT portfolio_id FROM paper_portfolio WHERE portfolio_id = ?",
            (SEED_PORTFOLIO["portfolio_id"],),
        ).fetchone()

        if existing:
            print(f"[SKIP] Portfoy zaten var: {SEED_PORTFOLIO['portfolio_id']}")
        else:
            conn.execute(
                """
                INSERT INTO paper_portfolio (
                    portfolio_id, name, initial_bankroll, current_bankroll,
                    peak_bankroll, total_bets, total_wins, total_coupons,
                    won_coupons, total_staked, total_return, status,
                    strategy_version, notes, created_at, updated_at
                ) VALUES (
                    :portfolio_id, :name, :initial_bankroll, :current_bankroll,
                    :peak_bankroll, :total_bets, :total_wins, :total_coupons,
                    :won_coupons, :total_staked, :total_return, :status,
                    :strategy_version, :notes, :created_at, :updated_at
                )
                """,
                SEED_PORTFOLIO,
            )
            conn.commit()
            print(f"[OK] Portfoy seed'lendi: {SEED_PORTFOLIO['portfolio_id']} "
                  f"— {SEED_PORTFOLIO['name']} "
                  f"({SEED_PORTFOLIO['initial_bankroll']:,.0f} TL)")

        # 3. Gunluk ilk girisi seed'le — varsa atla
        existing_journal = conn.execute(
            "SELECT journal_id FROM paper_journal WHERE journal_id = ?",
            ("JOURNAL_INIT",),
        ).fetchone()

        if existing_journal:
            print("[SKIP] Gunluk giris zaten var: JOURNAL_INIT")
        else:
            conn.execute(
                """
                INSERT OR IGNORE INTO paper_journal
                (journal_id, portfolio_id, entry_date, entry_type, title, content, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "JOURNAL_INIT",
                    "PAPER_V1",
                    datetime.utcnow().date().isoformat(),
                    "SESSION_REVIEW",
                    "Paper Trader v1 - Acilis Gunlugu",
                    "AI Paper Trader v1 basladi. 5000 TL baslangic bankrollu. "
                    "Strateji: v1-odds-signals. "
                    "Yaz arasi (Mayis-Agustos 2026) odds-bazli sinyal modeli. "
                    "Ana ligler Agustos'ta baslayinca DC+Platt modelleri devreye girecek. "
                    "Hedef: 3 ayda bankrollu korumak ve metodoloji ogrenmek.",
                    datetime.utcnow().isoformat(),
                ),
            )
            conn.commit()
            print("[OK] Gunluk acilis girisi seed'lendi: JOURNAL_INIT")

        # 4. Dogrulama
        for tbl in ("paper_portfolio", "paper_coupons", "paper_bets", "paper_journal"):
            n = conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
            print(f"    {tbl:20s}: {n:>6,} satir")

    finally:
        conn.close()

    print("\nMigration OK")


if __name__ == "__main__":
    run_migration()
