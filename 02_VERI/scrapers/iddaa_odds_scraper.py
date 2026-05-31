"""
SELECTIVE EDGE v1.0 — iddaa.com Odds Scraper

Endpoint keşfi sonucu:
    Base: https://sportsbookv2.iddaa.com
    GET /sportsbook/events?st=1                   → bütün futbol eventleri (özet markets)
    GET /sportsbook/event/{event_id}              → tek event'in TÜM marketleri (~88 pazar)
    GET /sportsbook/get_market_config             → market_subtype → Türkçe ad eşlemesi
    GET /sportsbook/competitions                  → lig listesi
    GET /sportsbook/popular-easy-coupons          → popüler kuponlar

Bir event'in pazar yapısı:
    event['m'] = list of markets
    each market:
        i  : market id
        t  : market type (1=1X2 family, 2=O/U & combos)
        st : market subtype id (1=MS, 101=A/Ü, 89=KG, 92=ÇŞ, ...)
        sov: stake/line value ("2.5", "+1", ...)
        o  : outcomes
            no  : outcome number
            n   : name (Türkçe)
            odd : printed odd
            wodd: web-displayed odd (slightly lower)

SELECTIVE EDGE için kritik 7 pazar:
    (1,1)   Maç Sonucu (1X2)
    (2,101) Alt/Üst sov={1.5, 2.5, 3.5}
    (2,89)  Karşılıklı Gol (KG)
    (2,92)  Çifte Şans
    (2,100) Handikaplı Maç Sonucu
    (2,7)   Maç Sonucu ve Alt/Üst (combo)
    (2,90)  İlk Yarı / Maç Sonucu

Bu pazarlar arasındaki tutarlılık → odds_anomaly_signal.
"""
from __future__ import annotations

import json
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib import request, error

THIS_DIR = Path(__file__).resolve().parent
VERI_DIR = THIS_DIR.parent
sys.path.insert(0, str(VERI_DIR))

import database as db


# ------------------------------------------------------------
# API
# ------------------------------------------------------------

API_BASE = "https://sportsbookv2.iddaa.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.7",
    "Referer": "https://www.iddaa.com/",
    "Origin": "https://www.iddaa.com",
}


def _get(url: str, timeout: int = 20) -> dict:
    req = request.Request(url, headers=HEADERS)
    with request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def fetch_events(sport_type: int = 1) -> list[dict]:
    """Tüm futbol eventleri (1 çağrı = 80-150 maç)."""
    r = _get(f"{API_BASE}/sportsbook/events?st={sport_type}&type=0")
    return r.get("data", {}).get("events", []) or []


def fetch_event_detail(event_id: int) -> dict | None:
    """Bir event'in TAM market detayı (~88 pazar)."""
    try:
        r = _get(f"{API_BASE}/sportsbook/event/{event_id}")
        return r.get("data") or None
    except Exception as e:
        print(f"  event/{event_id} ERR: {e}")
        return None


def fetch_market_config() -> dict:
    """804 market tipi → Türkçe ad."""
    r = _get(f"{API_BASE}/sportsbook/get_market_config")
    return r.get("data", {}).get("m", {}) or {}


def fetch_competitions() -> list[dict]:
    """Lig listesi (Süper Lig, Premier League, vb.)."""
    r = _get(f"{API_BASE}/sportsbook/competitions")
    return r.get("data", []) or []


# ------------------------------------------------------------
# MARKET DECODER
# ------------------------------------------------------------

# t=event_market.t, st=event_market.st için kanonik isim
# Bu eşleştirme odds_anomaly hesabı için kullanılır.
CANONICAL_MARKETS = {
    (1, 1):   "1X2",            # Maç Sonucu
    (2, 101): "OU",             # Alt/Üst — sov ile birleşir → OU2.5
    (2, 60):  "HT_OU",          # İlk Yarı Alt/Üst
    (2, 89):  "BTTS",           # Karşılıklı Gol
    (2, 92):  "DC",             # Çifte Şans
    (2, 100): "HC",             # Handikaplı Maç Sonucu — sov ile birleşir → HC+1
    (2, 7):   "1X2_OU",         # MS+A/Ü combo
    (2, 90):  "HT_FT",          # İlk Yarı/Maç Sonucu
    (2, 88):  "HT_1X2",         # İlk Yarı Sonucu
    (2, 91):  "OE",             # Tek/Çift
    (2, 4):   "TOTAL_GOALS",    # Toplam Gol
    (2, 86):  "CORRECT_SCORE",  # Maç Skoru
    (2, 87):  "FIRST_GOAL",     # İlk Golü Hangi Takım Atar
    (2, 698): "1X2_BTTS",       # MS+KG combo
    (2, 700): "OU_BTTS",        # A/Ü+KG combo
}


def market_key(m: dict) -> str | None:
    """(t, st, sov) → kanonik kısa anahtar (ör. 'OU2.5', 'HC+1')."""
    t, st = m.get("t"), m.get("st")
    canon = CANONICAL_MARKETS.get((t, st))
    if not canon:
        return None
    sov = m.get("sov", "")
    if canon in ("OU", "HT_OU"):
        return f"{canon}{sov}"           # OU2.5
    if canon == "HC":
        # sov ör. "-1.0", "+1.5" — normalize et
        try:
            n = float(sov)
            sign = "+" if n >= 0 else "-"
            return f"HC{sign}{abs(n):g}"  # HC+1.5
        except Exception:
            return f"HC{sov}"
    return canon


def decode_event_markets(event: dict, mkt_cfg: dict | None = None) -> list[dict]:
    """
    Bir event'in markets'ını yapısal kayıtlara çevir.
    Returns: list of dicts {market, selection, odd, wodd, ...}
    """
    rows = []
    home, away = event.get("hn"), event.get("an")
    eid = event.get("i")
    kick = event.get("d")  # genelde 'd' kickoff datetime
    for m in event.get("m", []) or []:
        key = market_key(m)
        if not key:
            continue
        # tutarlı Türkçe ad
        tn = None
        if mkt_cfg is not None:
            cfg = mkt_cfg.get(f"{m.get('t')}_{m.get('st')}")
            if cfg:
                tn = cfg.get("n")
        for o in m.get("o", []) or []:
            sel = (o.get("n") or "").strip()
            odd = o.get("odd")
            wodd = o.get("wodd")
            if not sel or not odd:
                continue
            rows.append({
                "iddaa_match_id": str(eid),
                "home_team": home,
                "away_team": away,
                "kickoff_iso": kick,
                "market": key,
                "market_t": m.get("t"),
                "market_st": m.get("st"),
                "market_name": tn,
                "sov": m.get("sov"),
                "selection_no": o.get("no"),
                "selection": sel,
                "odd": odd,
                "wodd": wodd,
                "implied_prob": (1.0 / odd) if odd else None,
            })
    return rows


# ------------------------------------------------------------
# DB WRITE
# ------------------------------------------------------------

def snapshot_id_now() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d-%H%M")


def write_odds(rows: list[dict], snapshot_id: str | None = None,
               league_code: str | None = None) -> int:
    if not rows:
        return 0
    snap = snapshot_id or snapshot_id_now()
    conn = db.connect()
    try:
        now = datetime.utcnow().isoformat()
        n = 0
        for r in rows:
            try:
                conn.execute("""
                    INSERT OR REPLACE INTO iddaa_odds(
                        snapshot_id, fixture_id, iddaa_match_id, league_code,
                        kickoff_iso, home_team, away_team,
                        market, selection, odd, implied_prob, fetched_at, raw_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    snap, None, r["iddaa_match_id"], league_code,
                    r.get("kickoff_iso") or "", r["home_team"], r["away_team"],
                    r["market"], r["selection"], r["odd"], r["implied_prob"],
                    now, json.dumps({k: r.get(k) for k in ("market_t","market_st","market_name","sov","wodd","selection_no")}, ensure_ascii=False)
                ))
                n += 1
            except Exception as e:
                # tek satır hatası akışı durdurmasın
                pass
        conn.commit()
        return n
    finally:
        conn.close()


# ------------------------------------------------------------
# CLI
# ------------------------------------------------------------

def ingest_all(detail: bool = False, limit: int | None = None,
               sport_type: int = 1, delay: float = 0.4):
    """
    detail=False → events endpoint'in özet pazarları (~15 pazar/maç)
    detail=True  → her event için ayrı /event/{id} çağrısı (~88 pazar/maç)
                   ama API'yi YORARSIN, dikkatli kullan.
    """
    print(f"[iddaa_odds] events fetch (st={sport_type})...")
    evts = fetch_events(sport_type)
    print(f"  {len(evts)} event bulundu")
    mkt_cfg = fetch_market_config()
    print(f"  market_config: {len(mkt_cfg)} tip")
    snap = snapshot_id_now()
    print(f"  snapshot_id: {snap}")

    total_rows = 0
    written = 0
    if limit:
        evts = evts[:limit]

    for i, evt in enumerate(evts):
        full = evt
        if detail:
            d = fetch_event_detail(evt.get("i"))
            if d:
                full = d
            time.sleep(delay)

        rows = decode_event_markets(full, mkt_cfg)
        n = write_odds(rows, snapshot_id=snap)
        total_rows += len(rows)
        written += n

        if (i + 1) % 20 == 0:
            print(f"  [{i+1}/{len(evts)}] {full.get('hn','?')} - {full.get('an','?')}: {len(rows)} odds")

    print(f"\n[OK] {len(evts)} event islendi")
    print(f"     Decode edilen odds satiri: {total_rows}")
    print(f"     DB'ye yazilan: {written}")
    return written


def stats():
    conn = db.connect()
    try:
        n = conn.execute("SELECT COUNT(*) FROM iddaa_odds").fetchone()[0]
        nm = conn.execute("SELECT COUNT(DISTINCT iddaa_match_id) FROM iddaa_odds").fetchone()[0]
        nsnap = conn.execute("SELECT COUNT(DISTINCT snapshot_id) FROM iddaa_odds").fetchone()[0]
        print("=== IDDAA ODDS STATS ===")
        print(f"  Toplam satir   : {n:>8,}")
        print(f"  Mac sayisi     : {nm:>8,}")
        print(f"  Snapshot sayisi: {nsnap:>8,}")
        if n > 0:
            print(f"\n  En cok ceken pazarlar:")
            for r in conn.execute(
                "SELECT market, COUNT(*) as n FROM iddaa_odds GROUP BY market "
                "ORDER BY n DESC LIMIT 15"
            ).fetchall():
                print(f"    {r['market']:18s} {r['n']:>6,} satir")
            print(f"\n  En son snapshot:")
            for r in conn.execute(
                "SELECT snapshot_id, COUNT(*) as n, COUNT(DISTINCT iddaa_match_id) as m "
                "FROM iddaa_odds GROUP BY snapshot_id ORDER BY snapshot_id DESC LIMIT 5"
            ).fetchall():
                print(f"    {r['snapshot_id']}  : {r['n']:>6,} satir, {r['m']:>4} mac")
    finally:
        conn.close()


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "fetch"
    if cmd == "fetch":
        # quick fetch (özet markets, default)
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else None
        ingest_all(detail=False, limit=limit)
        stats()
    elif cmd == "fetch_detail":
        # tüm markets (per-event /event/{id} çağrısı) — yavaş
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else None
        delay = float(sys.argv[3]) if len(sys.argv) > 3 else 0.4
        ingest_all(detail=True, limit=limit, delay=delay)
        stats()
    elif cmd == "stats":
        stats()
    elif cmd == "prune":
        # convenience: retention apply
        import iddaa_retention
        iddaa_retention.prune()
    elif cmd == "config":
        cfg = fetch_market_config()
        print(f"Market config: {len(cfg)} tip")
        for k in list(cfg.keys())[:20]:
            print(f"  {k}: {cfg[k].get('n','?')}")
    else:
        print("Komutlar: fetch [limit] [detail] | stats | config")
