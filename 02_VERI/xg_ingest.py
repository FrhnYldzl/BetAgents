"""
xG ingest — Understat (soccerdata üzerinden) ile maç-bazlı xG verisini DB'ye yaz.

Hedef ligler: EPL, La Liga, Bundesliga, Serie A, Ligue 1
Sezonlar: 2022, 2023, 2024 (free plan kısıtı yok — bu Understat tarafı)

Çıktı:
    - fixtures tablosuna home_xg / away_xg sütunları
    - Ayrı xg_data tablosu (fixture_id ile join'li, başka ileri istatistikler de
      buraya gelebilir)

CLI:
    python xg_ingest.py init           — xg sütunlarını ekle
    python xg_ingest.py fetch ENG 2024 — bir lig+sezon için xG çek
    python xg_ingest.py fetch_all       — tüm 5 lig × 3 sezon
"""
from __future__ import annotations

import sqlite3
import sys
from datetime import datetime
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS_DIR))

import database as db


# soccerdata lig kodu eşlemesi
SD_TO_OUR = {
    "ENG-Premier League": "E0",
    "ESP-La Liga":         "SP1",
    "GER-Bundesliga":      "D1",
    "ITA-Serie A":         "I1",
    "FRA-Ligue 1":         "F1",
}

OUR_TO_SD = {v: k for k, v in SD_TO_OUR.items()}

# Sezon eşlemesi (Understat: "2024" = 2024-25)
SUPPORTED_SEASONS = [2021, 2022, 2023, 2024]


# ============================================================
# DB SCHEMA EXTENSION
# ============================================================

XG_SCHEMA = """
-- xG datası ayrı tabloda, fixtures ile fixture_id üzerinden join
CREATE TABLE IF NOT EXISTS xg_data (
    fixture_id       INTEGER,                -- api-football fixture_id (eşleşirse)
    league_code      TEXT NOT NULL,
    season           INTEGER NOT NULL,
    match_date       TEXT NOT NULL,           -- YYYY-MM-DD
    home_team        TEXT NOT NULL,
    away_team        TEXT NOT NULL,
    home_xg          REAL,
    away_xg          REAL,
    home_goals       INTEGER,
    away_goals       INTEGER,
    understat_url    TEXT,
    inserted_at      TEXT NOT NULL,
    PRIMARY KEY(league_code, season, match_date, home_team, away_team)
);

CREATE INDEX IF NOT EXISTS idx_xg_league_season ON xg_data(league_code, season);
CREATE INDEX IF NOT EXISTS idx_xg_teams ON xg_data(home_team, away_team);
CREATE INDEX IF NOT EXISTS idx_xg_date ON xg_data(match_date);
"""


def init_xg_schema():
    conn = db.connect()
    try:
        conn.executescript(XG_SCHEMA)
        conn.commit()
        print(f"xG sema hazir.")
    finally:
        conn.close()


# ============================================================
# TAKIM AD NORMALİZASYONU (Understat → api-football)
# ============================================================

# Understat takım adı != api-football takım adı çoğu zaman.
# Bu eşleme tablosu fixture_id match'i için lazım.

UNDERSTAT_TO_AF = {
    # Premier League
    "Manchester United":          "Manchester United",
    "Manchester City":            "Manchester City",
    "Wolverhampton Wanderers":    "Wolves",
    "Tottenham":                  "Tottenham",
    "Newcastle United":           "Newcastle",
    "Nottingham Forest":          "Nottingham Forest",
    "Brighton":                   "Brighton",
    "West Ham":                   "West Ham",
    "Aston Villa":                "Aston Villa",
    "Crystal Palace":             "Crystal Palace",
    "Liverpool":                  "Liverpool",
    "Arsenal":                    "Arsenal",
    "Chelsea":                    "Chelsea",
    "Fulham":                     "Fulham",
    "Everton":                    "Everton",
    "Brentford":                  "Brentford",
    "Bournemouth":                "Bournemouth",
    "Ipswich":                    "Ipswich",
    "Leicester":                  "Leicester",
    "Southampton":                "Southampton",
    # La Liga
    "Real Madrid":                "Real Madrid",
    "Barcelona":                  "Barcelona",
    "Atletico Madrid":            "Atletico Madrid",
    # Bundesliga
    "Bayern Munich":              "Bayern Munich",
    "Borussia Dortmund":          "Borussia Dortmund",
    # ... çok takım var, Understat tarafının adlarıyla
    # Eşleşmezse fixture_id NULL kalır, xG yine kullanılabilir (team+date join'le)
}


# ============================================================
# FETCH
# ============================================================

def fetch_league_season(our_code: str, season: int) -> int:
    """Bir lig + sezon için tüm xG verisini çek, DB'ye yaz."""
    import soccerdata as sd

    sd_league = OUR_TO_SD.get(our_code)
    if sd_league is None:
        raise ValueError(f"Lig desteklenmiyor: {our_code}. "
                         f"Mevcut: {list(OUR_TO_SD.keys())}")

    sd_season = str(season)  # soccerdata "2024" formatında
    print(f"[{our_code}/{season}] {sd_league} - Understat fetch...")

    us = sd.Understat(leagues=sd_league, seasons=sd_season)
    sched = us.read_schedule()
    print(f"  {len(sched)} mac geldi (xG verili)")

    # Fixture'larla maç tarihi + takım adlarıyla eşleştirmek için DB lookup
    conn = db.connect()
    try:
        existing_fixtures = {
            (r["league_code"], r["season"], r["kickoff_utc"][:10],
             r["home_team"], r["away_team"]): r["fixture_id"]
            for r in conn.execute(
                "SELECT fixture_id, league_code, season, kickoff_utc, home_team, away_team "
                "FROM fixtures WHERE league_code = ? AND season = ?",
                (our_code, season)
            ).fetchall()
        }

        new_count = 0
        matched_count = 0
        now_iso = datetime.now().isoformat()

        # Schedule iterasyonu — MultiIndex, reset_index ile kolay
        sched_reset = sched.reset_index()

        for _, row in sched_reset.iterrows():
            mdate = str(row["date"])[:10]
            home_us = row["home_team"]
            away_us = row["away_team"]
            home_af = UNDERSTAT_TO_AF.get(home_us, home_us)
            away_af = UNDERSTAT_TO_AF.get(away_us, away_us)

            # Fixture id eşleştirmesi
            fid = existing_fixtures.get(
                (our_code, season, mdate, home_af, away_af)
            )
            if fid is not None:
                matched_count += 1

            # xG verisi (None olabilir oynanmamış maçlar için)
            home_xg = float(row["home_xg"]) if row.get("home_xg") is not None and str(row.get("home_xg")) != "nan" else None
            away_xg = float(row["away_xg"]) if row.get("away_xg") is not None and str(row.get("away_xg")) != "nan" else None
            hg = int(row["home_goals"]) if row.get("home_goals") is not None and not (isinstance(row.get("home_goals"), float) and str(row.get("home_goals")) == "nan") else None
            ag = int(row["away_goals"]) if row.get("away_goals") is not None and not (isinstance(row.get("away_goals"), float) and str(row.get("away_goals")) == "nan") else None

            conn.execute(
                "INSERT OR REPLACE INTO xg_data("
                "fixture_id, league_code, season, match_date, home_team, away_team, "
                "home_xg, away_xg, home_goals, away_goals, understat_url, inserted_at"
                ") VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (fid, our_code, season, mdate, home_us, away_us,
                 home_xg, away_xg, hg, ag, row.get("url"), now_iso)
            )
            new_count += 1

        conn.commit()
        print(f"  {new_count} satir yazildi, {matched_count} tanesi api-football fixture_id ile eslesti")
        return new_count
    finally:
        conn.close()


def fetch_all():
    """Tüm desteklenen lig × sezon kombinasyonları."""
    init_xg_schema()
    total = 0
    for our_code in OUR_TO_SD.keys():
        for season in SUPPORTED_SEASONS:
            try:
                n = fetch_league_season(our_code, season)
                total += n
            except Exception as e:
                print(f"  HATA [{our_code}/{season}]: {e}")
    print(f"\nToplam: {total} xG kaydi")


# ============================================================
# STATS / QUERY
# ============================================================

def stats():
    init_xg_schema()
    conn = db.connect()
    try:
        rows = conn.execute(
            "SELECT league_code, season, COUNT(*) as n, "
            "SUM(CASE WHEN home_xg IS NOT NULL THEN 1 ELSE 0 END) as with_xg, "
            "SUM(CASE WHEN fixture_id IS NOT NULL THEN 1 ELSE 0 END) as matched "
            "FROM xg_data GROUP BY league_code, season ORDER BY league_code, season"
        ).fetchall()
        total = conn.execute("SELECT COUNT(*) as n FROM xg_data").fetchone()["n"]
        print(f"\n=== xG DATA STATS ===")
        print(f"Toplam: {total:,} kayıt")
        print(f"\nLig/Sezon:")
        for r in rows:
            r = dict(r)
            print(f"  {r['league_code']} / {r['season']}: "
                  f"{r['n']} mac, {r['with_xg']} xG verili, "
                  f"{r['matched']} fixture eslesmis")
    finally:
        conn.close()


# ============================================================
# CLI
# ============================================================

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "stats"

    if cmd == "init":
        init_xg_schema()
    elif cmd == "fetch":
        league = sys.argv[2]
        season = int(sys.argv[3])
        init_xg_schema()
        fetch_league_season(league, season)
    elif cmd == "fetch_all":
        fetch_all()
        stats()
    elif cmd == "stats":
        stats()
    else:
        print("Komutlar: init | fetch <league> <season> | fetch_all | stats")
        print(f"Ligler: {list(OUR_TO_SD.keys())}")
        print(f"Sezonlar: {SUPPORTED_SEASONS}")
