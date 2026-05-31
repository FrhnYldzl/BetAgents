"""
SPRINT 3 — YARATICI FEATURE MÜHENDİSLİĞİ

Kullanıcının fikrinden: "asist yapan adamın sonraki maç oynaması..., gol krallığında
mücadele edenin etkisi..., yaratıcı olmak zorundayız, bilindik şey yapmıyoruz."

api-football endpoints (Free plan ✅ erişim var):
    /players/topscorers      — gol kralı yarışı
    /players/topassists      — asist kralı yarışı
    /players/topyellowcards  — sarı kart kralı (cezalı kalma riski)
    /players/topredcards     — kırmızı kart riski

DB tabloları:
    top_players              — sezon sonu top oyuncular (lig × sezon × tür)

Yaratıcı feature'lar (DC'den ortogonal):
    home_topscorer_goals     — ev sahibinde gol kralı var mı, kaç gol
    home_topscorer_share     — takımın toplam golünün yüzde kaçı bu oyuncudan
    home_topassist_assists   — ev sahibi top asistçi
    home_card_risk           — kart kralı listesinde oyuncu var mı (cezalı risk)
    away_*  (aynısı dep)
    star_battle_score        — iki takımın yıldız oyuncuları yarışta mı (motivasyon)
    home_squad_depth         — top-N oyuncuların toplam katkısı (kadro derinliği)
"""
from __future__ import annotations

import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS_DIR / "api_clients"))
sys.path.insert(0, str(THIS_DIR))

import database as db
from api_football import call, LEAGUE_IDS


PLAYER_SCHEMA = """
CREATE TABLE IF NOT EXISTS top_players (
    league_code   TEXT NOT NULL,
    season        INTEGER NOT NULL,
    rank_type     TEXT NOT NULL,           -- 'scorer','assist','yellow','red'
    rank          INTEGER NOT NULL,
    player_id     INTEGER NOT NULL,
    player_name   TEXT NOT NULL,
    team_id       INTEGER,
    team_name     TEXT,
    value         INTEGER NOT NULL,         -- goller/asistler/kartlar
    appearances   INTEGER,
    minutes       INTEGER,
    inserted_at   TEXT NOT NULL,
    PRIMARY KEY(league_code, season, rank_type, rank)
);

CREATE INDEX IF NOT EXISTS idx_tp_team ON top_players(team_name, league_code, season);
"""


def init_schema():
    conn = db.connect()
    try:
        conn.executescript(PLAYER_SCHEMA)
        conn.commit()
    finally:
        conn.close()


# ============================================================
# INGEST — 3 endpoint × N lig
# ============================================================

RANK_ENDPOINTS = {
    "scorer":  "players/topscorers",
    "assist":  "players/topassists",
    "yellow":  "players/topyellowcards",
    "red":     "players/topredcards",
}


def ingest_top_players(league_code: str, season: int,
                       rank_type: str = "scorer") -> int:
    """Bir lig × sezon × tür için top oyuncuları çek + DB'ye yaz."""
    init_schema()
    lid = LEAGUE_IDS.get(league_code)
    if lid is None:
        raise ValueError(f"Lig bilinmiyor: {league_code}")
    endpoint = RANK_ENDPOINTS.get(rank_type)
    if endpoint is None:
        raise ValueError(f"rank_type: scorer/assist/yellow/red")

    print(f"  [{league_code}/{season}] {rank_type} ingest...")
    r = call(endpoint, {"league": lid, "season": season})
    players = r.get("response", []) or []
    print(f"    {len(players)} oyuncu")

    conn = db.connect()
    try:
        now_iso = datetime.now().isoformat()
        for rank, p in enumerate(players, start=1):
            player = p.get("player", {})
            stats = p.get("statistics", [{}])[0]
            team = stats.get("team", {})
            goals = stats.get("goals", {})
            cards = stats.get("cards", {})
            games = stats.get("games", {})

            if rank_type == "scorer":
                value = goals.get("total") or 0
            elif rank_type == "assist":
                value = goals.get("assists") or 0
            elif rank_type == "yellow":
                value = cards.get("yellow") or 0
            elif rank_type == "red":
                value = cards.get("red") or 0
            else:
                value = 0

            try:
                conn.execute(
                    "INSERT OR REPLACE INTO top_players("
                    "league_code, season, rank_type, rank, player_id, player_name, "
                    "team_id, team_name, value, appearances, minutes, inserted_at"
                    ") VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (league_code, season, rank_type, rank,
                     player.get("id"), player.get("name"),
                     team.get("id"), team.get("name"),
                     int(value) if value is not None else 0,
                     games.get("appearences"), games.get("minutes"),
                     now_iso)
                )
            except Exception as e:
                continue
        conn.commit()
        return len(players)
    finally:
        conn.close()


def ingest_all(leagues: list[str] | None = None, season: int = 2024):
    if leagues is None:
        leagues = ["T1", "E0", "D1", "I1", "SP1", "F1"]
    print(f"\nIngest top players ({season}) for {len(leagues)} ligs × 4 types")
    total = 0
    for lg in leagues:
        for typ in ["scorer", "assist", "yellow", "red"]:
            try:
                n = ingest_top_players(lg, season, typ)
                total += n
            except Exception as e:
                print(f"  [{lg}/{typ}] HATA: {e}")
    print(f"\nToplam: {total} oyuncu kaydı (DB)")


# ============================================================
# FEATURE COMPUTE — maç bazlı
# ============================================================

def get_team_top_player(team_name: str, league_code: str, season: int,
                         rank_type: str = "scorer") -> dict | None:
    """Bir takımın o sezondaki en iyi oyuncusunu döndür (tür bazında)."""
    conn = db.connect()
    try:
        r = conn.execute(
            "SELECT * FROM top_players WHERE team_name = ? AND league_code = ? "
            "AND season = ? AND rank_type = ? ORDER BY rank ASC LIMIT 1",
            (team_name, league_code, season, rank_type)
        ).fetchone()
        return dict(r) if r else None
    finally:
        conn.close()


def get_team_top_n(team_name: str, league_code: str, season: int,
                    rank_type: str, n: int = 3) -> list[dict]:
    conn = db.connect()
    try:
        rs = conn.execute(
            "SELECT * FROM top_players WHERE team_name = ? AND league_code = ? "
            "AND season = ? AND rank_type = ? ORDER BY rank ASC LIMIT ?",
            (team_name, league_code, season, rank_type, n)
        ).fetchall()
        return [dict(r) for r in rs]
    finally:
        conn.close()


def compute_player_features(home_team_af: str, away_team_af: str,
                             league_code: str, season: int) -> dict:
    """
    İki takım için yaratıcı player features.

    api-football team adlarıyla çağrılır (Galatasaray, Manchester City, vs).
    """
    feats = {
        "home_top_scorer_goals": 0,
        "home_top_scorer_share": 0.0,    # gol payı (ileride hesaplanır)
        "home_top_assist_count": 0,
        "home_card_risk": 0,             # bu takımda sarı kart kralı var mı
        "away_top_scorer_goals": 0,
        "away_top_scorer_share": 0.0,
        "away_top_assist_count": 0,
        "away_card_risk": 0,
        "star_battle_score": 0.0,        # iki yıldız da yarıştaysa yüksek
        "home_squad_depth": 0,           # top-3 oyuncunun toplam katkısı
        "away_squad_depth": 0,
    }

    # Top scorer
    h_sc = get_team_top_player(home_team_af, league_code, season, "scorer")
    a_sc = get_team_top_player(away_team_af, league_code, season, "scorer")
    if h_sc:
        feats["home_top_scorer_goals"] = h_sc["value"]
    if a_sc:
        feats["away_top_scorer_goals"] = a_sc["value"]

    # Top assist
    h_as = get_team_top_player(home_team_af, league_code, season, "assist")
    a_as = get_team_top_player(away_team_af, league_code, season, "assist")
    if h_as:
        feats["home_top_assist_count"] = h_as["value"]
    if a_as:
        feats["away_top_assist_count"] = a_as["value"]

    # Card risk (sarı kart kralı listesinde takım var mı?)
    h_yc = get_team_top_player(home_team_af, league_code, season, "yellow")
    a_yc = get_team_top_player(away_team_af, league_code, season, "yellow")
    feats["home_card_risk"] = (h_yc["value"] if h_yc else 0)
    feats["away_card_risk"] = (a_yc["value"] if a_yc else 0)

    # Star battle: iki takımın gol kralları yakınsa (lig sıralamasında)
    if h_sc and a_sc:
        # ranks 1-20 → 1 = en iyi
        diff = abs(h_sc["rank"] - a_sc["rank"])
        # Hem 1-5 arasıysa ve fark az → yüksek battle
        if h_sc["rank"] <= 5 and a_sc["rank"] <= 5:
            feats["star_battle_score"] = 1.0 - diff / 5.0
        elif h_sc["rank"] <= 10 and a_sc["rank"] <= 10:
            feats["star_battle_score"] = 0.5 * (1.0 - diff / 10.0)

    # Squad depth: top-3 oyuncuların gol + asist toplamı
    h_top3 = get_team_top_n(home_team_af, league_code, season, "scorer", 3)
    a_top3 = get_team_top_n(away_team_af, league_code, season, "scorer", 3)
    feats["home_squad_depth"] = sum(p["value"] for p in h_top3)
    feats["away_squad_depth"] = sum(p["value"] for p in a_top3)

    return feats


# ============================================================
# CLI
# ============================================================

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "ingest_all"

    if cmd == "ingest_all":
        season = int(sys.argv[2]) if len(sys.argv) > 2 else 2024
        ingest_all(season=season)
    elif cmd == "stats":
        init_schema()
        conn = db.connect()
        try:
            rs = conn.execute(
                "SELECT league_code, season, rank_type, COUNT(*) as n "
                "FROM top_players GROUP BY league_code, season, rank_type "
                "ORDER BY league_code, season, rank_type"
            ).fetchall()
            print("\n=== TOP PLAYERS STATS ===")
            for r in rs:
                r = dict(r)
                print(f"  {r['league_code']}/{r['season']} {r['rank_type']:7s}: {r['n']}")
        finally:
            conn.close()
    elif cmd == "test":
        # Bir maç için feature hesaplama
        feats = compute_player_features("Galatasaray", "Fenerbahce", "T1", 2024)
        for k, v in feats.items():
            print(f"  {k:24s}: {v}")
    else:
        print("Komutlar: ingest_all [season] | stats | test")
