"""
Sakatlık verisi ingest — api-football /injuries endpoint'inden.

Tek call ile bir liganın TÜM sezonu (1 league × 1 season = 1 API call).
Free plan'da: 5 lig × 1 sezon = 5 call.

Maç bazında: her takım için maçtan önceki sakat listesi → feature.

Feature kullanımı (Sprint 1.4-v2):
    home_injuries_count        : maç günü sakat oyuncu sayısı (ev)
    away_injuries_count        : maç günü sakat oyuncu sayısı (dep)
    home_injuries_key          : kilit oyuncu sakatsa 1 (büyük etki)
    away_injuries_key          : aynı

Önemli: api-football injury type'ları:
    - 'Missing Fixture'   : maçı kaçıracak (gerçek sakat)
    - 'Questionable'      : şüpheli
    - 'Coach's decision'  : teknik direktör kararı (sakat değil ama oynamayacak)
    - 'Suspended'         : ceza
    - 'Doubtful'          : şüpheli

Hepsi "oynamayacak" demek → maça etki eder.
"""
from __future__ import annotations

import sqlite3
import sys
from datetime import datetime
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS_DIR))
sys.path.insert(0, str(THIS_DIR / "api_clients"))

import database as db
from api_football import call, LEAGUE_IDS


INJURY_SCHEMA = """
CREATE TABLE IF NOT EXISTS injuries (
    fixture_id      INTEGER NOT NULL,
    league_code     TEXT NOT NULL,
    season          INTEGER NOT NULL,
    fixture_date    TEXT NOT NULL,
    team_id         INTEGER NOT NULL,
    team_name       TEXT NOT NULL,
    player_id       INTEGER NOT NULL,
    player_name     TEXT NOT NULL,
    injury_type     TEXT,                    -- 'Missing Fixture','Questionable',...
    injury_reason   TEXT,
    inserted_at     TEXT NOT NULL,
    PRIMARY KEY(fixture_id, team_id, player_id)
);

CREATE INDEX IF NOT EXISTS idx_inj_fixture ON injuries(fixture_id);
CREATE INDEX IF NOT EXISTS idx_inj_team_date ON injuries(team_id, fixture_date);
CREATE INDEX IF NOT EXISTS idx_inj_league ON injuries(league_code, season);
"""


def init_schema():
    conn = db.connect()
    try:
        conn.executescript(INJURY_SCHEMA)
        conn.commit()
        print("Injuries schema hazir.")
    finally:
        conn.close()


def fetch_league_season(league_code: str, season: int) -> int:
    """Bir lig + sezon için tüm sakatlıkları çek."""
    lid_info = LEAGUE_IDS.get(league_code)
    if lid_info is None:
        # Fallback: api_football.LEAGUE_IDS — yeni format (int)
        raise ValueError(f"Lig bilinmiyor: {league_code}")

    # LEAGUE_IDS hem int hem tuple olabilir, normalize et
    lid = lid_info if isinstance(lid_info, int) else lid_info

    print(f"[{league_code}/{season}] /injuries istek...")
    r = call("injuries", {"league": lid, "season": season})
    records = r.get("response", []) or []
    print(f"  {len(records)} kayit geldi")

    if not records:
        return 0

    conn = db.connect()
    try:
        now_iso = datetime.now().isoformat()
        new_count = 0
        for item in records:
            try:
                fx = item.get("fixture", {})
                team = item.get("team", {})
                player = item.get("player", {})
                conn.execute(
                    "INSERT OR REPLACE INTO injuries("
                    "fixture_id, league_code, season, fixture_date, "
                    "team_id, team_name, player_id, player_name, "
                    "injury_type, injury_reason, inserted_at"
                    ") VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        fx.get("id"), league_code, season,
                        (fx.get("date") or "")[:10],
                        team.get("id"), team.get("name"),
                        player.get("id"), player.get("name"),
                        player.get("type"), player.get("reason"),
                        now_iso,
                    )
                )
                new_count += 1
            except Exception as e:
                # Çoğu zaman player_id eksik gibi durumlar
                continue
        conn.commit()
        return new_count
    finally:
        conn.close()


def fetch_all_main_leagues(season: int = 2024):
    """5 büyük Avrupa lig + Türkiye için sakatlık çek."""
    init_schema()
    leagues = ["E0", "SP1", "D1", "I1", "F1", "T1"]
    total = 0
    for lg in leagues:
        try:
            n = fetch_league_season(lg, season)
            total += n
        except Exception as e:
            print(f"  HATA [{lg}]: {e}")
    print(f"\nToplam: {total} sakatlik kaydi")
    return total


def stats():
    init_schema()
    conn = db.connect()
    try:
        total = conn.execute("SELECT COUNT(*) as n FROM injuries").fetchone()["n"]
        print(f"\n=== INJURIES STATS ===")
        print(f"Toplam   : {total:,} kayit")
        rows = conn.execute(
            "SELECT league_code, season, COUNT(*) as n, "
            "COUNT(DISTINCT team_id) as teams, "
            "COUNT(DISTINCT player_id) as players, "
            "COUNT(DISTINCT fixture_id) as fixtures "
            "FROM injuries GROUP BY league_code, season ORDER BY league_code, season"
        ).fetchall()
        print(f"\nLig/Sezon:")
        for r in rows:
            r = dict(r)
            print(f"  {r['league_code']}/{r['season']}: "
                  f"{r['n']:>5} kayit, {r['teams']:>3} takim, "
                  f"{r['players']:>4} oyuncu, {r['fixtures']:>4} fixture")
    finally:
        conn.close()


# ============================================================
# FEATURE: Maç başlangıcında her takımın sakat sayısı
# ============================================================

def injury_counts_for_match(fixture_id: int) -> dict:
    """
    Bir fixture için her iki takımın sakat sayısını döndür.

    Returns: {"home_count": int, "away_count": int} (team_id ile join'le)
    """
    conn = db.connect()
    try:
        rows = conn.execute(
            "SELECT team_id, COUNT(*) as n FROM injuries "
            "WHERE fixture_id = ? GROUP BY team_id",
            (fixture_id,)
        ).fetchall()
        return {r["team_id"]: r["n"] for r in rows}
    finally:
        conn.close()


# ============================================================
# CLI
# ============================================================

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "stats"
    if cmd == "init":
        init_schema()
    elif cmd == "fetch":
        league = sys.argv[2]
        season = int(sys.argv[3])
        init_schema()
        fetch_league_season(league, season)
    elif cmd == "fetch_all":
        season = int(sys.argv[2]) if len(sys.argv) > 2 else 2024
        fetch_all_main_leagues(season)
        stats()
    elif cmd == "stats":
        stats()
    else:
        print("Komutlar: init | fetch <league> <season> | fetch_all [season] | stats")
