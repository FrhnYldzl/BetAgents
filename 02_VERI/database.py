"""
SQLite database — api-football'dan çekilen veri lokal kaydedilir.

API çağrı kotası (free plan: 100/gün) ekonomik kullanılır:
    - Bir lig + sezon = 1 çağrı (~380 maç)
    - Üç sezon × üç lig = 9 çağrı → ~3500 maç
    - Sonraki tüm UI/model işleri DB'den okur

Tablolar:
    fixtures        — maç verileri (skor, tarih, takımlar)
    odds            — bookmaker oranları (ilerde, fixture ile join)
    api_calls       — yapılan API çağrılarının logu (kota takibi)
    cache_meta      — son güncelleme tarihleri

CLI:
    python database.py init                    — tabloları oluştur
    python database.py ingest_season E0 2024   — bir ligin tüm sezonu çek
    python database.py stats                   — durum özeti
"""
from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
DB_PATH = THIS_DIR / "bahis_agent.db"


# ============================================================
# SHEMA
# ============================================================

SCHEMA = """
CREATE TABLE IF NOT EXISTS fixtures (
    fixture_id      INTEGER PRIMARY KEY,
    league_code     TEXT NOT NULL,           -- 'T1', 'E0', 'D1', ...
    league_name     TEXT,
    season          INTEGER NOT NULL,         -- 2024 = 2024-25
    kickoff_utc     TEXT NOT NULL,            -- ISO datetime
    status          TEXT,                     -- 'NS','FT','LIVE',...
    home_team       TEXT NOT NULL,
    away_team       TEXT NOT NULL,
    home_score      INTEGER,
    away_score      INTEGER,
    venue           TEXT,
    city            TEXT,
    referee         TEXT,
    raw_json        TEXT,                     -- ham response (debug için)
    inserted_at     TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_fixtures_league_season
    ON fixtures(league_code, season);
CREATE INDEX IF NOT EXISTS idx_fixtures_kickoff
    ON fixtures(kickoff_utc);
CREATE INDEX IF NOT EXISTS idx_fixtures_teams
    ON fixtures(home_team, away_team);

CREATE TABLE IF NOT EXISTS api_calls (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    endpoint        TEXT NOT NULL,
    params          TEXT,
    called_at       TEXT NOT NULL,
    results_count   INTEGER,
    cache_hit       INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_api_calls_day
    ON api_calls(called_at);

CREATE TABLE IF NOT EXISTS odds (
    fixture_id      INTEGER NOT NULL,
    market          TEXT NOT NULL,           -- '1X2','OU2.5','BTTS'
    selection       TEXT NOT NULL,           -- '1','X','2','Over','Under',...
    bookmaker       TEXT NOT NULL,
    odd             REAL NOT NULL,
    fetched_at      TEXT NOT NULL,
    PRIMARY KEY(fixture_id, market, selection, bookmaker)
);

CREATE TABLE IF NOT EXISTS cache_meta (
    key             TEXT PRIMARY KEY,
    value           TEXT,
    updated_at      TEXT NOT NULL
);
"""


# ============================================================
# CONNECT / INIT
# ============================================================

def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = connect()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
        print(f"DB hazir: {DB_PATH}")
    finally:
        conn.close()


# ============================================================
# INGEST
# ============================================================

LEAGUE_IDS = {
    "T1": (203, "Türkiye Süper Lig"),
    "E0": (39, "Premier League"),
    "D1": (78, "Bundesliga"),
    "I1": (135, "Serie A"),
    "SP1": (140, "La Liga"),
    "F1": (61, "Ligue 1"),
}


def log_api_call(conn, endpoint: str, params: dict,
                 results: int, cache_hit: bool) -> None:
    conn.execute(
        "INSERT INTO api_calls(endpoint, params, called_at, results_count, cache_hit) "
        "VALUES(?, ?, ?, ?, ?)",
        (endpoint, json.dumps(params, sort_keys=True),
         datetime.utcnow().isoformat(), results, 1 if cache_hit else 0)
    )


def ingest_season(league_code: str, season: int) -> int:
    """
    api-football'dan tek call ile bir ligin tüm sezonunu çek, DB'ye yaz.

    Returns: kaydedilen yeni maç sayısı.
    """
    sys.path.insert(0, str(THIS_DIR / "api_clients"))
    from api_football import call as api_call, _cache_get

    if league_code not in LEAGUE_IDS:
        raise ValueError(f"Lig bilinmiyor: {league_code}")
    lid, lname = LEAGUE_IDS[league_code]

    params = {"league": lid, "season": season}
    cache_hit = _cache_get("fixtures", params) is not None

    print(f"[{league_code}/{season}] {lname} — istek atiliyor"
          f"{' (cache hit)' if cache_hit else ' (yeni API call)'}...")

    raw = api_call("fixtures", params)
    matches = raw.get("response", []) or []
    print(f"  {len(matches)} mac geldi")

    conn = connect()
    try:
        log_api_call(conn, "fixtures", params, len(matches), cache_hit)
        new_count = 0
        for item in matches:
            f = item.get("fixture", {})
            t = item.get("teams", {})
            g = item.get("goals", {})
            v = f.get("venue", {}) or {}
            league = item.get("league", {})

            row = (
                f.get("id"),
                league_code,
                league.get("name") or lname,
                season,
                f.get("date"),
                f.get("status", {}).get("short"),
                t.get("home", {}).get("name"),
                t.get("away", {}).get("name"),
                g.get("home"),
                g.get("away"),
                v.get("name") if isinstance(v, dict) else None,
                v.get("city") if isinstance(v, dict) else None,
                f.get("referee"),
                json.dumps(item, ensure_ascii=False),
                datetime.utcnow().isoformat(),
            )
            try:
                conn.execute(
                    "INSERT INTO fixtures("
                    "fixture_id, league_code, league_name, season, kickoff_utc, "
                    "status, home_team, away_team, home_score, away_score, "
                    "venue, city, referee, raw_json, inserted_at"
                    ") VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    row,
                )
                new_count += 1
            except sqlite3.IntegrityError:
                # Zaten var, skor güncelle
                conn.execute(
                    "UPDATE fixtures SET status=?, home_score=?, away_score=?, "
                    "raw_json=?, inserted_at=? WHERE fixture_id=?",
                    (row[5], row[8], row[9], row[13], row[14], row[0]),
                )
        conn.commit()
        return new_count
    finally:
        conn.close()


# ============================================================
# QUERY HELPERS (UI bunu kullanır)
# ============================================================

def fixtures_for_week(league_code: str, week_anchor: str,
                     days_before: int = 0, days_after: int = 7) -> list[dict]:
    """
    Belli tarih çevresinde maç listesi.

    Args:
        league_code: 'T1','E0',...
        week_anchor: 'YYYY-MM-DD' (genelde Pazartesi)
        days_before, days_after: aralık
    """
    from datetime import datetime as dt, timedelta
    anchor = dt.fromisoformat(week_anchor)
    start = (anchor - timedelta(days=days_before)).isoformat()
    end = (anchor + timedelta(days=days_after)).isoformat()

    conn = connect()
    try:
        rows = conn.execute(
            "SELECT * FROM fixtures WHERE league_code=? "
            "AND kickoff_utc >= ? AND kickoff_utc <= ? "
            "ORDER BY kickoff_utc",
            (league_code, start, end),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def stats_summary() -> dict:
    conn = connect()
    try:
        leagues = {}
        for r in conn.execute(
            "SELECT league_code, season, COUNT(*) as n, "
            "SUM(CASE WHEN status='FT' THEN 1 ELSE 0 END) as ft, "
            "MIN(kickoff_utc) as first_match, "
            "MAX(kickoff_utc) as last_match "
            "FROM fixtures GROUP BY league_code, season "
            "ORDER BY league_code, season"
        ).fetchall():
            r = dict(r)
            leagues.setdefault(r["league_code"], []).append({
                "season": r["season"], "total": r["n"], "finished": r["ft"],
                "first": r["first_match"][:10] if r["first_match"] else None,
                "last":  r["last_match"][:10] if r["last_match"] else None,
            })

        # API kullanım
        api = conn.execute(
            "SELECT COUNT(*) as n, "
            "SUM(CASE WHEN cache_hit=0 THEN 1 ELSE 0 END) as fresh "
            "FROM api_calls WHERE substr(called_at,1,10) = ?",
            (datetime.utcnow().date().isoformat(),),
        ).fetchone()

        total = conn.execute("SELECT COUNT(*) as n FROM fixtures").fetchone()["n"]
        return {
            "leagues": leagues,
            "api_today": dict(api) if api else {"n": 0, "fresh": 0},
            "total_fixtures": total,
        }
    finally:
        conn.close()


# ============================================================
# CLI
# ============================================================

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "stats"

    if cmd == "init":
        init_db()

    elif cmd == "ingest_season":
        league = sys.argv[2]
        season = int(sys.argv[3])
        init_db()
        n = ingest_season(league, season)
        print(f"  Yeni eklenen: {n}")

    elif cmd == "stats":
        init_db()
        s = stats_summary()
        print(f"\n=== BAHIS AGENT DB STATS ===")
        print(f"DB        : {DB_PATH}")
        print(f"Toplam mac: {s['total_fixtures']:,}")
        print(f"Bugun API : {s['api_today']['n'] or 0} cagrı "
              f"({s['api_today']['fresh'] or 0} fresh, "
              f"{(s['api_today']['n'] or 0) - (s['api_today']['fresh'] or 0)} cache)")
        print(f"\nLig/Sezon:")
        for lg, seasons in s["leagues"].items():
            for ss in seasons:
                print(f"  {lg} / {ss['season']:>4}: "
                      f"{ss['total']:>4} mac ({ss['finished']} oynanmis) "
                      f"[{ss['first']} - {ss['last']}]")

    else:
        print("Komutlar: init | ingest_season <league> <season> | stats")
        print("Lig kodlari:", ", ".join(LEAGUE_IDS.keys()))
