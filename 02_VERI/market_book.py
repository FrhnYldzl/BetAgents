"""
🎰 PAZAR DEFTERİ — yüksek çarpanlı ve KOMBİNE pazarların toplanması
====================================================================
NEDEN: 1X2 + ÜST/ALT + KG dışındaki pazarları hiç toplamıyorduk; iddaa
zaten aynı yanıtta gönderiyordu, biz atıyorduk. Oysa yüksek çarpan
(8x-35x) oradaydı ve — asıl önemlisi — MAÇ İÇİ KOMBİNE pazarlar
(1X2_OU "1 ve Üst", 1X2_BTTS "1 ve Var") orada.

BULGU (24.612 maç): maçlar ARASI korelasyon sömürülemez (ölçüldü: oran
0.89-1.01), ama maç İÇİ korelasyon devasa:
    "0 ve ALT" gerçek/çarpım = 1.60   ·  "0 ve ÜST" = 0.48
    "1 ve ÜST" = 1.18                 ·  "1 ve ALT" = 0.79
iddaa bu kombineleri TEK seçim olarak sunuyor → tek marj ödenerek
korelasyon oynanabilir. Kombinede marjın üstel çarpılması sorunu YOK.

İZOLASYON (kullanıcı şartı): bu veriler AYRI tabloda (`market_odds`)
durur. matches_v2'ye hiçbir kolon eklenmez, mevcut sinyal motoru bu
tabloyu HİÇ okumaz. Yalnız ÇARPAN ajanı erişir. Diğer ajanların
kafası karışmaz.

MALİYET: sıfır ek API çağrısı (aynı yanıt), yalnız DEĞİŞEN fiyat yazılır.

    python market_book.py --stats
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS_DIR))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import db

# Toplanacak pazarlar — yüksek çarpan ve/veya kombine değeri olanlar.
# (Mevcut 3 pazar zaten matches_v2'de; burada onları da tutuyoruz ki
#  kombine fiyatı bileşenleriyle AYNI ANDA kıyaslanabilsin.)
WANTED = {
    "1X2", "BTTS", "OU2.5", "OU1.5", "OU3.5",
    "1X2_OU", "1X2_BTTS", "OU_BTTS",          # ⭐ maç içi kombineler
    "HT_FT", "HT_1X2", "HT_OU0.5", "HT_OU1.5",
    "TOTAL_GOALS", "CORRECT_SCORE", "DC", "OE",
    "HC+1", "HC-1", "HC+2", "HC-2", "HC+3", "HC-3",
}


def ensure_table(conn) -> None:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS market_odds ("
        "ts TEXT, iddaa_event_id TEXT, league_code TEXT, kickoff_utc TEXT, "
        "home_team TEXT, away_team TEXT, market TEXT, sov TEXT, "
        "selection TEXT, odd REAL, lead_h REAL)")
    conn.commit()
    for stmt in (
        "CREATE INDEX IF NOT EXISTS ix_mo_ev ON market_odds (iddaa_event_id)",
        "CREATE INDEX IF NOT EXISTS ix_mo_mk ON market_odds (market)",
        "CREATE INDEX IF NOT EXISTS ix_mo_ts ON market_odds (ts)",
    ):
        try:
            conn.execute(stmt)
            conn.commit()
        except Exception:
            conn.rollback()


def capture(events: list[dict], league_of=None) -> int:
    """Ham iddaa event listesinden istenen pazarları kaydet.
    Yalnız ÖNCEKİNDEN FARKLI fiyatlar yazılır. Asla exception fırlatmaz."""
    if not events:
        return 0
    try:
        from scrapers.iddaa_odds_scraper import decode_event_markets
    except Exception:
        try:
            sys.path.insert(0, str(THIS_DIR / "scrapers"))
            from iddaa_odds_scraper import decode_event_markets  # type: ignore
        except Exception as e:
            print(f"  (pazar defteri: cozucu yuklenemedi: {e})")
            return 0
    try:
        conn = db.connect()
    except Exception:
        return 0
    n = 0
    try:
        ensure_table(conn)
        # bugünkü son fiyatlar (değişim filtresi)
        last: dict = {}
        try:
            today = datetime.utcnow().date().isoformat()
            for r in conn.execute(
                    "SELECT iddaa_event_id, market, selection, odd FROM market_odds "
                    "WHERE ts >= ? ORDER BY ts", (today + "T00:00:00",)).fetchall():
                last[(str(r[0]), r[1], r[2])] = round(float(r[3] or 0), 3)
        except Exception:
            conn.rollback()
        now = datetime.utcnow().isoformat()
        for ev in events:
            try:
                rows = decode_event_markets(ev)
            except Exception:
                continue
            lg = ev.get("_league_code") or (league_of(ev) if league_of else None) or "ALL"
            ko = None
            try:
                if ev.get("d"):
                    ko = datetime.fromtimestamp(ev["d"]).isoformat()
            except Exception:
                ko = None
            lead = None
            if ko:
                try:
                    lead = (datetime.fromisoformat(ko[:19])
                            - datetime.utcnow()).total_seconds() / 3600.0
                except Exception:
                    lead = None
            for r in rows:
                try:
                    mk = r.get("market")
                    if mk not in WANTED:
                        continue
                    odd = float(r.get("odd") or 0)
                    if odd < 1.01:
                        continue
                    key = (str(r.get("iddaa_match_id")), mk, r.get("selection"))
                    if last.get(key) == round(odd, 3):
                        continue
                    conn.execute(
                        "INSERT INTO market_odds (ts, iddaa_event_id, league_code, "
                        "kickoff_utc, home_team, away_team, market, sov, selection, "
                        "odd, lead_h) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                        (now, key[0], lg, ko, r.get("home_team"), r.get("away_team"),
                         mk, str(r.get("sov") or ""), r.get("selection"), odd, lead))
                    last[key] = round(odd, 3)
                    n += 1
                except Exception:
                    continue
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        try:
            conn.close()
        except Exception:
            pass
    return n


def stats() -> None:
    conn = db.connect()
    try:
        ensure_table(conn)
        r = conn.execute("SELECT COUNT(*) n, COUNT(DISTINCT iddaa_event_id) e, "
                         "MIN(ts) a, MAX(ts) b FROM market_odds").fetchone()
        print(f"🎰 PAZAR DEFTERİ: {r[0] or 0} satır · {r[1] or 0} maç")
        if r[2]:
            print(f"   {str(r[2])[:16]} → {str(r[3])[:16]}")
        for x in conn.execute(
                "SELECT market, COUNT(*) n, COUNT(DISTINCT iddaa_event_id) e "
                "FROM market_odds GROUP BY market ORDER BY 2 DESC LIMIT 25").fetchall():
            print(f"   {str(x[0]):16s} {x[1]:6d} satır · {x[2]:4d} maç")
    finally:
        conn.close()


if __name__ == "__main__":
    stats()
