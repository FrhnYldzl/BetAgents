"""
CREATIVE EDGE v1.0 — fixtures/statistics ingest

api-football'da her maç için 18 istatistik:
  Shots (on/off/total/blocked/inside/outside), Fouls, Corners, Offsides,
  Ball Possession, Yellow/Red Cards, Saves, Passes (total/accurate/%),
  *** expected_goals, goals_prevented ***

Bu data **gerçek edge** yaratabilir. Mock yok, ortaya karışık yok.

Rate limit: 10 RPM (api-football free plan).
"""
from __future__ import annotations

import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd

THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS_DIR / "api_clients"))
sys.path.insert(0, str(THIS_DIR))

import database as db
from api_football import call, _cache_get


STATS_SCHEMA = """
CREATE TABLE IF NOT EXISTS fixture_statistics (
    fixture_id     INTEGER NOT NULL,
    team_id        INTEGER NOT NULL,
    team_name      TEXT,
    is_home        INTEGER NOT NULL,
    shots_on       INTEGER, shots_off INTEGER, shots_total INTEGER,
    shots_blocked  INTEGER, shots_inside INTEGER, shots_outside INTEGER,
    fouls          INTEGER, corners INTEGER, offsides INTEGER,
    possession_pct INTEGER, yellow INTEGER, red INTEGER,
    saves          INTEGER, passes_total INTEGER, passes_acc INTEGER,
    passes_pct     INTEGER, xg REAL, goals_prevented REAL,
    inserted_at    TEXT NOT NULL,
    PRIMARY KEY(fixture_id, team_id)
);

CREATE INDEX IF NOT EXISTS idx_fs_team ON fixture_statistics(team_id, fixture_id);
"""


def init_schema():
    conn = db.connect()
    try:
        conn.executescript(STATS_SCHEMA)
        conn.commit()
    finally:
        conn.close()


def _to_int(v):
    if v is None: return None
    if isinstance(v, int): return v
    if isinstance(v, str):
        v = v.replace('%','').strip()
        if v == '' or v == 'null': return None
    try:
        return int(float(v))
    except Exception:
        return None


def _to_float(v):
    if v is None: return None
    try:
        return float(str(v).replace('%','').strip())
    except Exception:
        return None


STAT_MAP = {
    "Shots on Goal":     ("shots_on", _to_int),
    "Shots off Goal":    ("shots_off", _to_int),
    "Total Shots":       ("shots_total", _to_int),
    "Blocked Shots":     ("shots_blocked", _to_int),
    "Shots insidebox":   ("shots_inside", _to_int),
    "Shots outsidebox":  ("shots_outside", _to_int),
    "Fouls":             ("fouls", _to_int),
    "Corner Kicks":      ("corners", _to_int),
    "Offsides":          ("offsides", _to_int),
    "Ball Possession":   ("possession_pct", _to_int),
    "Yellow Cards":      ("yellow", _to_int),
    "Red Cards":         ("red", _to_int),
    "Goalkeeper Saves":  ("saves", _to_int),
    "Total passes":      ("passes_total", _to_int),
    "Passes accurate":   ("passes_acc", _to_int),
    "Passes %":          ("passes_pct", _to_int),
    "expected_goals":    ("xg", _to_float),
    "goals_prevented":   ("goals_prevented", _to_float),
}


def ingest_one_fixture(fixture_id: int, conn=None) -> int:
    """Bir fixture için istatistikleri çek + DB'ye yaz. Returns: kaydedilen satır."""
    close_conn = conn is None
    if conn is None:
        conn = db.connect()
    init_schema()
    try:
        r = call("fixtures/statistics", {"fixture": fixture_id})
        teams = r.get("response", []) or []
        if not teams:
            return 0

        # Hangi takım ev/dep? fixtures tablosundan lookup
        fx = conn.execute(
            "SELECT home_team, away_team, kickoff_utc FROM fixtures WHERE fixture_id=?",
            (fixture_id,)
        ).fetchone()
        if not fx:
            home_name, away_name = teams[0]["team"]["name"], teams[1]["team"]["name"] if len(teams) > 1 else ""
        else:
            home_name = fx["home_team"]
            away_name = fx["away_team"]

        for team_data in teams:
            team = team_data["team"]
            stats = team_data.get("statistics", []) or []
            row = {
                "fixture_id": fixture_id,
                "team_id": team["id"],
                "team_name": team["name"],
                "is_home": 1 if team["name"] == home_name else 0,
                "inserted_at": datetime.now().isoformat(),
            }
            for s in stats:
                stype = s.get("type")
                if stype in STAT_MAP:
                    col, conv = STAT_MAP[stype]
                    row[col] = conv(s.get("value"))

            cols = ",".join(row.keys())
            placeholders = ",".join(["?"] * len(row))
            conn.execute(
                f"INSERT OR REPLACE INTO fixture_statistics({cols}) VALUES({placeholders})",
                tuple(row.values())
            )
        conn.commit()
        return len(teams)
    finally:
        if close_conn:
            conn.close()


def ingest_fixtures_batch(fixture_ids: list[int], rate_limit_per_min: int = 9):
    """
    Rate-limited bulk ingest.
    api-football free plan: 10 RPM (margin için 9 kullanıyoruz).
    """
    init_schema()
    conn = db.connect()
    try:
        total = 0
        skipped = 0
        t_window_start = time.time()
        calls_in_window = 0

        for i, fid in enumerate(fixture_ids):
            # Cache check (önce diskte var mı?)
            cached = _cache_get("fixtures/statistics", {"fixture": fid})
            if cached is None:
                # Rate limit
                elapsed = time.time() - t_window_start
                if elapsed < 60 and calls_in_window >= rate_limit_per_min:
                    wait = 60 - elapsed + 1
                    print(f"    [rate limit] {wait:.0f}sn bekleme...")
                    time.sleep(wait)
                    t_window_start = time.time()
                    calls_in_window = 0
                calls_in_window += 1

            try:
                n = ingest_one_fixture(fid, conn)
                total += n
            except Exception as e:
                err_str = str(e).lower()
                if "rate" in err_str or "429" in err_str:
                    print(f"    [{i+1}/{len(fixture_ids)}] rate limit, 60sn bekleyip dene...")
                    time.sleep(60)
                    t_window_start = time.time()
                    calls_in_window = 0
                    try:
                        n = ingest_one_fixture(fid, conn)
                        total += n
                    except Exception:
                        skipped += 1
                else:
                    skipped += 1
            if (i + 1) % 20 == 0:
                print(f"    {i+1}/{len(fixture_ids)} fixture işlendi (total satır: {total}, atlanan: {skipped})")

        print(f"\n  TOPLAM: {total} satır kaydedildi, {skipped} fixture atlandı")
        return total
    finally:
        conn.close()


def get_fixture_ids_for_league(league_code: str, season: int,
                                limit: int | None = None,
                                only_played: bool = True) -> list[int]:
    """DB'den fixture_id listesi al."""
    conn = db.connect()
    try:
        q = "SELECT fixture_id FROM fixtures WHERE league_code=? AND season=?"
        params = [league_code, season]
        if only_played:
            q += " AND status='FT'"
        q += " ORDER BY kickoff_utc DESC"
        if limit:
            q += f" LIMIT {limit}"
        return [r["fixture_id"] for r in conn.execute(q, params).fetchall()]
    finally:
        conn.close()


def stats():
    init_schema()
    conn = db.connect()
    try:
        n = conn.execute("SELECT COUNT(*) FROM fixture_statistics").fetchone()[0]
        nfx = conn.execute("SELECT COUNT(DISTINCT fixture_id) FROM fixture_statistics").fetchone()[0]
        print(f"\n=== FIXTURE STATS ===")
        print(f"Toplam satır     : {n:,}")
        print(f"Toplam fixture   : {nfx:,}")
        print(f"\nLig dağılımı:")
        rows = conn.execute(
            "SELECT f.league_code, COUNT(DISTINCT s.fixture_id) as n "
            "FROM fixture_statistics s "
            "JOIN fixtures f ON s.fixture_id = f.fixture_id "
            "GROUP BY f.league_code"
        ).fetchall()
        for r in rows:
            print(f"  {r['league_code']}: {r['n']} fixture")
    finally:
        conn.close()


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "stats"
    if cmd == "ingest":
        # Default: T1 son 100 maç
        league = sys.argv[2] if len(sys.argv) > 2 else "T1"
        season = int(sys.argv[3]) if len(sys.argv) > 3 else 2024
        limit = int(sys.argv[4]) if len(sys.argv) > 4 else 100
        ids = get_fixture_ids_for_league(league, season, limit=limit)
        print(f"Ingest: {league}/{season}, {len(ids)} fixture")
        ingest_fixtures_batch(ids)
        stats()
    elif cmd == "stats":
        stats()
    else:
        print("Komutlar: ingest <league> <season> <limit> | stats")
