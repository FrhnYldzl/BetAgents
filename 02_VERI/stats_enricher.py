"""
STATS ENRICHER v1.0
====================
iddaa.com statisticsv2 API'dan 5 endpoint'i çekip matches_v2 tablosunu zenginleştirir.

API endpoints (Playwright ile keşfedildi 2026-05-29):
  statisticsv2.iddaa.com/statistics/soccer/match-card/{id}?isLive=true
  statisticsv2.iddaa.com/statistics/soccer/recent-matches/{id}?matchHistoryType=2
  statisticsv2.iddaa.com/statistics/soccer/lineup/{id}
  statisticsv2.iddaa.com/statistics/soccer/card-corners/{id}
  statisticsv2.iddaa.com/statistics/soccer/standings/{id}?standingType=0

Çalıştır:
  python stats_enricher.py               # iddaa_event_id olanları zenginleştir
  python stats_enricher.py --force       # zaten zenginleştirilenleri de yenile
  python stats_enricher.py --event 2975498  # tek maç
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
DB_PATH  = THIS_DIR / "bahis_agent.db"

sys.stdout.reconfigure(encoding="utf-8")

BASE_STATS = "https://statisticsv2.iddaa.com/statistics/soccer"
BASE_BOOK  = "https://sportsbookv2.iddaa.com/sportsbook"

HEADERS = {
    "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept":          "application/json",
    "Accept-Language": "tr-TR,tr;q=0.9",
    "Referer":         "https://www.iddaa.com/",
    "Origin":          "https://www.iddaa.com",
}


# ── HTTP helper ────────────────────────────────────────────────
def _get(url: str, timeout: int = 10) -> dict | None:
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            d = json.loads(r.read().decode("utf-8", errors="replace"))
            if d.get("isSuccess"):
                return d.get("data")
            return None
    except Exception as e:
        print(f"  [WARN] {url.split('/')[-1][:40]}: {e}")
        return None


# ── Endpoint fetchers ──────────────────────────────────────────
def fetch_event(event_id: int) -> dict | None:
    """sportsbookv2: live odds + betradar ID"""
    return _get(f"{BASE_BOOK}/event/{event_id}")


def fetch_match_card(event_id: int) -> dict | None:
    """Canlı istatistik kartı: skor, şut, korner, kart"""
    return _get(f"{BASE_STATS}/match-card/{event_id}?isLive=true")


def fetch_recent_matches(event_id: int) -> dict | None:
    """H2H + son maçlar geçmişi"""
    return _get(
        f"{BASE_STATS}/recent-matches/{event_id}"
        "?matchHistoryType=2&isOnlyCurrentTournament=false"
    )


def fetch_lineup(event_id: int) -> dict | None:
    """Kadro (11'ler, yedekler, antrenör)"""
    return _get(f"{BASE_STATS}/lineup/{event_id}")


def fetch_card_corners(event_id: int) -> dict | None:
    """Son 5-6 maç korner & kart geçmişi"""
    return _get(f"{BASE_STATS}/card-corners/{event_id}")


def fetch_standings(event_id: int) -> dict | None:
    """Lig puan tablosu"""
    return _get(f"{BASE_STATS}/standings/{event_id}?standingType=0&isLive=false")


# ── Parse helpers ──────────────────────────────────────────────
def _parse_card_corners(data: dict, side: str) -> dict:
    """side = 'h' (home) or 'a' (away)"""
    result = {"corners": [], "yc": [], "rc": []}
    matches = (data.get(side) or {}).get("m") or []
    for m in matches[:6]:
        # team stats within each match (the team we're interested in)
        # 'h'/'a' within the match tells us each team's stats
        # We look at both and find our team
        team_name_key = side  # reuse side
        for k in ("h", "a"):
            t = m.get(k, {})
            # corner count key 'c', yc='yc', rc='rc'
            c  = t.get("c", 0)  or 0
            yc = t.get("yc", 0) or 0
            rc = t.get("rc", 0) or 0
            # identify which side this team is (home/away of the match)
            if k == "h":
                result["corners"].append(c)
                result["yc"].append(yc)
                result["rc"].append(rc)
            break
    return result


def _safe_avg(lst: list) -> float | None:
    lst = [x for x in lst if x is not None]
    return round(sum(lst) / len(lst), 2) if lst else None


def parse_card_corners_for_team(data: dict, team_name: str) -> dict:
    """Find matches where team_name played and compute averages."""
    corners, ycs, rcs = [], [], []
    for side_key in ("h", "a"):
        side = data.get(side_key) or {}
        for m in (side.get("m") or [])[:6]:
            for mk in ("h", "a"):
                t = m.get(mk) or {}
                if t.get("n", "").lower() == team_name.lower():
                    corners.append(t.get("c", 0) or 0)
                    ycs.append(t.get("yc", 0) or 0)
                    rcs.append(t.get("rc", 0) or 0)
    return {
        "corners_avg": _safe_avg(corners),
        "yc_avg":      _safe_avg(ycs),
        "rc_avg":      _safe_avg(rcs),
    }


def parse_h2h(data: dict, home_name: str, away_name: str) -> dict:
    """Parse H2H from recent-matches endpoint."""
    matches = data.get("m") or []
    n = len(matches)
    if n == 0:
        return {}
    hw = dw = aw = 0
    goal_totals = []
    btts = []
    for m in matches:
        h = m.get("h") or {}
        a = m.get("a") or {}
        hs = h.get("rs", 0) or 0
        as_ = a.get("rs", 0) or 0
        total = hs + as_
        goal_totals.append(total)
        btts.append(1 if hs > 0 and as_ > 0 else 0)
        if hs > as_:
            hw += 1
        elif hs == as_:
            dw += 1
        else:
            aw += 1
    return {
        "n":          n,
        "home_wins":  hw,
        "draws":      dw,
        "away_wins":  aw,
        "avg_goals":  round(sum(goal_totals) / n, 2) if goal_totals else 0,
        "btts_rate":  round(sum(btts) / n, 2) if btts else 0,
    }


def parse_standings(data: dict, home_name: str, away_name: str) -> dict:
    """Extract home & away team league position + points."""
    result = {}
    groups = data.get("g") or []
    for grp in groups:
        teams = grp.get("t") or []
        n_teams = len(teams)
        leader_pts = teams[0]["pt"] if teams else 0
        # find bottom safe position
        relegation_pts = teams[-4]["pt"] if len(teams) >= 4 else 0
        for t in teams:
            name = t.get("n", "")
            lname = name.lower()
            for prefix, side in [(home_name.lower(), "home"), (away_name.lower(), "away")]:
                if prefix[:6] in lname or lname[:6] in prefix:
                    result[f"{side}_league_pos"]     = t.get("r")
                    result[f"{side}_pts"]             = t.get("pt")
                    result[f"{side}_gd"]              = t.get("gd")
                    result[f"{side}_title_gap"]       = leader_pts - (t.get("pt") or 0)
                    result[f"{side}_relegation_gap"]  = (t.get("pt") or 0) - relegation_pts
                    # Form: last 5 from 'fo' field if available
                    form = t.get("fo") or ""
                    result[f"{side}_form_5g"] = form[:5] if form else None
    return result


def parse_lineup(data: dict, home_name: str, away_name: str) -> dict:
    """Check if key players (1st team starters) are present."""
    result = {}
    for side_key, side_name in (("h", "home"), ("a", "away")):
        side = data.get(side_key) or {}
        players = side.get("p") or []
        # 'r' = True means in starting 11
        starters = [p for p in players if p.get("r")]
        result[f"{side_name}_missing_key"] = 0 if len(starters) >= 10 else 1
    return result


# ── Main enricher ──────────────────────────────────────────────
def enrich_match(conn: sqlite3.Connection, row: sqlite3.Row, force: bool = False) -> bool:
    match_id = row["match_id"]
    event_id = row["iddaa_event_id"]
    home     = row["home_team"] or ""
    away     = row["away_team"] or ""

    if not event_id:
        return False

    print(f"  Enriching [{match_id}] {home} vs {away} (event={event_id})")

    updates: dict = {}

    # 1. sportsbook/event → betradar_id, competition_id, odds movement
    ev = fetch_event(event_id)
    if ev:
        bri = ev.get("bri")
        if bri:
            updates["betradar_id"]   = bri
            updates["competition_id"] = ev.get("ci")
        # Odds movement: compare current vs opening
        markets = ev.get("m") or []
        for m in markets:
            if m.get("st") == 27:  # 1X2
                odds = {o["n"]: o["odd"] for o in (m.get("o") or [])}
                o1 = odds.get("1"); ox = odds.get("0"); o2 = odds.get("2")
                if o1 and row["opening_1"]:
                    updates["odds_move_1"] = round(o1 - (row["opening_1"] or o1), 3)
                if ox and row["opening_X"]:
                    updates["odds_move_x"] = round(ox - (row["opening_X"] or ox), 3)
                if o2 and row["opening_2"]:
                    updates["odds_move_2"] = round(o2 - (row["opening_2"] or o2), 3)
    time.sleep(0.2)

    # 2. card-corners → son 5 maç korner + kart ortalaması
    cc = fetch_card_corners(event_id)
    if cc:
        home_cc = parse_card_corners_for_team(cc, home)
        away_cc = parse_card_corners_for_team(cc, away)
        updates["home_corners_5g_avg"] = home_cc["corners_avg"]
        updates["away_corners_5g_avg"] = away_cc["corners_avg"]
        updates["home_yc_5g_avg"]      = home_cc["yc_avg"]
        updates["away_yc_5g_avg"]      = away_cc["yc_avg"]
        updates["home_rc_5g_avg"]      = home_cc["rc_avg"]
        updates["away_rc_5g_avg"]      = away_cc["rc_avg"]
    time.sleep(0.2)

    # 3. recent-matches → H2H geçmişi
    rm = fetch_recent_matches(event_id)
    if rm:
        h2h = parse_h2h(rm, home, away)
        if h2h:
            updates["h2h_n"]         = h2h.get("n")
            updates["h2h_home_wins"] = h2h.get("home_wins")
            updates["h2h_draws"]     = h2h.get("draws")
            updates["h2h_away_wins"] = h2h.get("away_wins")
            updates["h2h_avg_goals"] = h2h.get("avg_goals")
            updates["h2h_btts_rate"] = h2h.get("btts_rate")
    time.sleep(0.2)

    # 4. standings → lig pozisyonu + motivasyon
    st = fetch_standings(event_id)
    if st:
        sdata = parse_standings(st, home, away)
        updates.update(sdata)
    time.sleep(0.2)

    # 5. lineup → kadro kalitesi (eksik oyuncu kontrolü)
    lu = fetch_lineup(event_id)
    if lu:
        ldata = parse_lineup(lu, home, away)
        updates.update(ldata)
    time.sleep(0.2)

    if not updates:
        print(f"    [SKIP] Veri çekilemedi")
        return False

    updates["stats_enriched_at"] = datetime.now(timezone.utc).isoformat()
    updates["stats_source"]      = "iddaa_statisticsv2"

    # UPDATE matches_v2
    set_clause = ", ".join(f"{k}=?" for k in updates)
    values     = list(updates.values()) + [match_id]
    conn.execute(f"UPDATE matches_v2 SET {set_clause} WHERE match_id=?", values)
    conn.commit()

    fields_updated = len([v for v in updates.values() if v is not None])
    print(f"    ✓ {fields_updated} alan güncellendi")
    return True


# ── CLI ────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="iddaa.com Stats Enricher")
    parser.add_argument("--force",   action="store_true", help="Mevcut kayıtları da yenile")
    parser.add_argument("--event",   type=int,            help="Tek maç event_id")
    parser.add_argument("--limit",   type=int, default=50, help="Max maç sayısı")
    parser.add_argument("--days",    type=int, default=3,   help="Önümüzdeki kaç gün")
    args = parser.parse_args()

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    if args.event:
        # Tek maç modu
        row = conn.execute(
            "SELECT * FROM matches_v2 WHERE iddaa_event_id=? OR external_id_iddaa=?",
            (args.event, args.event)
        ).fetchone()
        if row:
            enrich_match(conn, row, force=True)
        else:
            # Tek seferlik enrichment (DB kaydı olmadan)
            print(f"DB'de bulunamadı. Direkt API çekimi yapılıyor...")
            _direct_enrich(args.event)
        conn.close()
        return

    # Toplu mod: is_settled=0 + iddaa_event_id mevcut
    extra = "" if args.force else "AND stats_enriched_at IS NULL"
    rows = conn.execute(f"""
        SELECT * FROM matches_v2
        WHERE is_settled=0
          AND iddaa_event_id IS NOT NULL
          {extra}
        ORDER BY kickoff_utc ASC
        LIMIT ?
    """, (args.limit,)).fetchall()

    print(f"=== STATS ENRICHER ===")
    print(f"Zenginleştirilecek: {len(rows)} maç")
    print()

    ok = 0
    for i, row in enumerate(rows, 1):
        print(f"[{i}/{len(rows)}]", end=" ")
        if enrich_match(conn, row, force=args.force):
            ok += 1

    conn.close()
    print(f"\n=== TAMAMLANDI: {ok}/{len(rows)} maç güncellendi ===")


def _direct_enrich(event_id: int):
    """DB kaydı olmadan tek maç için tüm veriyi göster."""
    print(f"\n=== EVENT {event_id} DIREKT ENRICHMENT ===")

    ev = fetch_event(event_id)
    if ev:
        print(f"Ev: {ev.get('hn')} | Dep: {ev.get('an')}")
        print(f"BetRadar ID: {ev.get('bri')}")
        sc = ev.get("sc") or {}
        if sc:
            print(f"Dakika: {sc.get('min')} | Stat: {sc.get('s')}")
    print()

    cc = fetch_card_corners(event_id)
    if cc:
        home_name = (ev or {}).get("hn", "?")
        away_name = (ev or {}).get("an", "?")
        print(f"Korner/Kart geçmişi:")
        for side_key, side_name in (("h", home_name), ("a", away_name)):
            side = cc.get(side_key) or {}
            matches = (side.get("m") or [])[:5]
            stats = parse_card_corners_for_team(cc, side_name)
            print(f"  {side_name}: Korner ort={stats['corners_avg']}, YC ort={stats['yc_avg']}, RC ort={stats['rc_avg']}")
            for m in matches:
                for mk in ("h", "a"):
                    t = m.get(mk) or {}
                    if t.get("n", "").lower()[:6] == side_name.lower()[:6]:
                        print(f"    C{t.get('c',0)} Y{t.get('yc',0)} R{t.get('rc',0)}", end=" | ")
            print()
    print()

    rm = fetch_recent_matches(event_id)
    if rm:
        h2h = parse_h2h(rm, (ev or {}).get("hn","?"), (ev or {}).get("an","?"))
        print(f"H2H ({h2h.get('n',0)} maç): {h2h.get('home_wins',0)}G {h2h.get('draws',0)}B {h2h.get('away_wins',0)}K | ort gol={h2h.get('avg_goals',0)} BTTS={h2h.get('btts_rate',0)}")
    print()

    st = fetch_standings(event_id)
    if st:
        groups = st.get("g") or []
        for grp in groups[:1]:
            print(f"Puan Tablosu — {grp.get('n','')}")
            for t in (grp.get("t") or [])[:8]:
                print(f"  {t.get('r',0):2}. {t.get('n','?'):25s} {t.get('pt',0)} pt  GD:{t.get('gd',0):+d}")


if __name__ == "__main__":
    main()
