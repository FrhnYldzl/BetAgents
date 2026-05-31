"""
SOFASCORE ADAPTER v1 — xG + maç istatistiği zenginleştirme
===========================================================
Kanıtlanmış yöntem: headless Chromium (Cloudflare çerezi) + sayfa-içi fetch().
Düz HTTP 403 alır; gerçek tarayıcı bağlamı 200 döner.

Kullanım (yerel, backfill):
  python sofascore.py --init                         # tabloyu oluştur
  python sofascore.py --backfill T1 --season-min 2023 --limit 40
  python sofascore.py --backfill T1 --season-min 2023            # tüm 2023+
  python sofascore.py --status                       # doluluk özeti

NOT: yalnız yerel/araştırma kullanımı. Nazik çekim (rate-limit'li).
Canlı Railway app bunu import ETMEZ (playwright runtime'da yok).
"""
from __future__ import annotations
import sys, re, json, time, unicodedata
from difflib import SequenceMatcher
from datetime import datetime, timezone
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
VERI_DIR = THIS_DIR.parent
sys.path.insert(0, str(VERI_DIR))
import db  # merkezî bağlantı (SQLite/PG)

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
API = "https://api.sofascore.com/api/v1"
REQUEST_DELAY = 1.2  # saniye — nazik çekim


# ============================================================
# İSİM NORMALİZASYONU + EŞLEME
# ============================================================

def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\b(spor|sk|fk|fc|cs|if|club|kulubu|belediyespor|as|sc)\b", " ", s)
    return re.sub(r"[^a-z0-9]", "", s)


def _sim(a, b):
    return SequenceMatcher(None, a, b).ratio()


# ============================================================
# İSTATİSTİK AYRIŞTIRMA
# ============================================================

def _num(v):
    """'55%' / '12/18 (67%)' / 12 → float (ilk anlamlı sayı)."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    m = re.search(r"-?\d+(\.\d+)?", str(v))
    return float(m.group()) if m else None


def parse_statistics(body: dict) -> dict:
    """statistics body → düz metrik sözlüğü (home_*/away_*). xG dahil."""
    out = {}
    if not isinstance(body, dict):
        return out
    KEYMAP = {
        "expectedgoals": "xg", "expected_goals": "xg",
        "totalshotsongoal": "shots", "totalshots": "shots", "shotsontarget": "shots_ot",
        "bigchances": "big_chances", "ballpossession": "possession",
        "cornerkicks": "corners", "goalkeepersaves": "saves",
        "fouls": "fouls", "offsides": "offsides",
        "accuratepasses": "pass_acc",
    }
    for per in body.get("statistics", []):
        if per.get("period") != "ALL":
            continue
        for g in per.get("groups", []):
            for it in g.get("statisticsItems", []):
                key = (it.get("key") or "").lower()
                name = re.sub(r"[^a-z]", "", (it.get("name") or "").lower())
                col = KEYMAP.get(key) or KEYMAP.get(name)
                if not col:
                    continue
                out[f"home_{col}"] = _num(it.get("home"))
                out[f"away_{col}"] = _num(it.get("away"))
    return out


def parse_votes(body: dict) -> dict:
    v = (body or {}).get("vote") or {}
    h, d, a = v.get("vote1"), v.get("voteX"), v.get("vote2")
    tot = sum(x for x in (h, d, a) if x) or 0
    if tot:
        return {"vote_home": round(100 * (h or 0) / tot, 1),
                "vote_draw": round(100 * (d or 0) / tot, 1),
                "vote_away": round(100 * (a or 0) / tot, 1)}
    return {}


# ============================================================
# CLIENT (Playwright)
# ============================================================

class SofascoreClient:
    def __init__(self, headless=True):
        self.headless = headless
        self._p = self._b = self._page = None
        self._sched_cache = {}

    def __enter__(self):
        from playwright.sync_api import sync_playwright
        self._p = sync_playwright().start()
        self._b = self._p.chromium.launch(
            headless=self.headless, args=["--disable-blink-features=AutomationControlled"])
        ctx = self._b.new_context(user_agent=UA, locale="tr-TR",
                                  viewport={"width": 1366, "height": 768})
        self._page = ctx.new_page()
        self._page.goto("https://www.sofascore.com/", wait_until="domcontentloaded", timeout=60000)
        self._page.wait_for_timeout(4000)  # cf çerezi otursun
        return self

    def __exit__(self, *a):
        try: self._b.close()
        except Exception: pass
        try: self._p.stop()
        except Exception: pass

    def _fetch(self, url):
        return self._page.evaluate(
            """async (u) => { try {
                const r = await fetch(u, {headers:{'Accept':'application/json'}});
                let b=null; try{b=await r.json()}catch(e){}
                return {status:r.status, body:b};
            } catch(e){ return {status:'ERR', body:null}; } }""", url)

    def scheduled(self, date: str):
        if date not in self._sched_cache:
            r = self._fetch(f"{API}/sport/football/scheduled-events/{date}")
            self._sched_cache[date] = (r.get("body") or {}).get("events", []) \
                if isinstance(r.get("body"), dict) else []
            time.sleep(REQUEST_DELAY)
        return self._sched_cache[date]

    def resolve_event(self, date, home, away, min_sim=0.5):
        th, ta = norm(home), norm(away)
        best, bs = None, 0.0
        for e in self.scheduled(date):
            sc = (_sim(th, norm(e.get("homeTeam", {}).get("name", "")))
                  + _sim(ta, norm(e.get("awayTeam", {}).get("name", "")))) / 2
            if sc > bs:
                bs, best = sc, e
        return (best, bs) if bs >= min_sim else (None, bs)

    def statistics(self, event_id):
        r = self._fetch(f"{API}/event/{event_id}/statistics")
        time.sleep(REQUEST_DELAY)
        return r.get("body") if r.get("status") == 200 else None

    def votes(self, event_id):
        r = self._fetch(f"{API}/event/{event_id}/votes")
        time.sleep(REQUEST_DELAY)
        return r.get("body") if r.get("status") == 200 else None


# ============================================================
# TABLO
# ============================================================

DDL = """
CREATE TABLE IF NOT EXISTS sofascore_stats (
  match_id          INTEGER PRIMARY KEY,
  sofa_event_id     INTEGER,
  sofa_home         TEXT,
  sofa_away         TEXT,
  match_sim         REAL,
  home_xg           REAL, away_xg          REAL,
  home_shots        REAL, away_shots       REAL,
  home_shots_ot     REAL, away_shots_ot    REAL,
  home_big_chances  REAL, away_big_chances REAL,
  home_possession   REAL, away_possession  REAL,
  home_corners      REAL, away_corners     REAL,
  home_saves        REAL, away_saves       REAL,
  home_pass_acc     REAL, away_pass_acc    REAL,
  vote_home         REAL, vote_draw        REAL, vote_away REAL,
  fetched_at        TEXT,
  raw_stats_json    TEXT
)
"""

COLS = ["match_id", "sofa_event_id", "sofa_home", "sofa_away", "match_sim",
        "home_xg", "away_xg", "home_shots", "away_shots", "home_shots_ot", "away_shots_ot",
        "home_big_chances", "away_big_chances", "home_possession", "away_possession",
        "home_corners", "away_corners", "home_saves", "away_saves",
        "home_pass_acc", "away_pass_acc", "vote_home", "vote_draw", "vote_away",
        "fetched_at", "raw_stats_json"]


def init_table():
    c = db.connect()
    c.execute(DDL); c.commit(); c.close()
    print("sofascore_stats tablosu hazir.")


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat()


# ============================================================
# BACKFILL
# ============================================================

def backfill(league="T1", season_min=2023, limit=None, headless=True):
    c = db.connect()
    c.execute(DDL); c.commit()
    q = """SELECT match_id, home_team, away_team, substr(kickoff_utc,1,10) d,
                  substr(kickoff_utc,1,4) yr
           FROM matches_v2
           WHERE league_code=? AND home_score IS NOT NULL
             AND CAST(substr(kickoff_utc,1,4) AS INTEGER) >= ?
             AND match_id NOT IN (SELECT match_id FROM sofascore_stats)
           ORDER BY kickoff_utc DESC"""
    rows = c.execute(q, (league, season_min)).fetchall()
    rows = [dict(r) for r in rows]
    if limit:
        rows = rows[:limit]
    print(f"Backfill: {league} {season_min}+ | işlenecek {len(rows)} maç (nazik ~{REQUEST_DELAY}s/çağrı)")
    if not rows:
        c.close(); return

    matched = with_xg = 0
    with SofascoreClient(headless=headless) as sf:
        for i, m in enumerate(rows, 1):
            ev, sim = sf.resolve_event(m["d"], m["home_team"], m["away_team"])
            if not ev:
                print(f"  [{i}/{len(rows)}] {m['home_team']} v {m['away_team']} — eşleşme YOK ({sim:.2f})")
                continue
            matched += 1
            stat = parse_statistics(sf.statistics(ev["id"]))
            vt = parse_votes(sf.votes(ev["id"]))
            rec = {k: None for k in COLS}
            rec.update({
                "match_id": m["match_id"], "sofa_event_id": ev["id"],
                "sofa_home": ev.get("homeTeam", {}).get("name"),
                "sofa_away": ev.get("awayTeam", {}).get("name"),
                "match_sim": round(sim, 3), "fetched_at": _now(),
                "raw_stats_json": json.dumps(stat, ensure_ascii=False),
            })
            rec.update({k: v for k, v in stat.items() if k in rec})
            rec.update({k: v for k, v in vt.items() if k in rec})
            if rec.get("home_xg") is not None:
                with_xg += 1
            ph = ",".join("?" * len(COLS))
            c.execute(f"INSERT OR REPLACE INTO sofascore_stats ({','.join(COLS)}) VALUES ({ph})",
                      tuple(rec[k] for k in COLS))
            c.commit()
            xg = f"xG {rec['home_xg']}-{rec['away_xg']}" if rec.get("home_xg") is not None else "xG yok"
            print(f"  [{i}/{len(rows)}] {m['home_team'][:16]} v {m['away_team'][:16]} ({m['yr']}) -> {xg}")
    c.close()
    print(f"\nBitti: {len(rows)} maçtan {matched} eşleşti, {with_xg} tanesinde xG dolduruldu.")


def status():
    c = db.connect()
    try:
        n = c.execute("SELECT COUNT(*) FROM sofascore_stats").fetchone()[0]
        nx = c.execute("SELECT COUNT(*) FROM sofascore_stats WHERE home_xg IS NOT NULL").fetchone()[0]
        print(f"sofascore_stats: {n} satır | xG dolu: {nx}")
    except Exception as e:
        print("tablo yok / hata:", e)
    c.close()


if __name__ == "__main__":
    import argparse
    try: sys.stdout.reconfigure(encoding="utf-8")
    except Exception: pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--init", action="store_true")
    ap.add_argument("--backfill", metavar="LEAGUE")
    ap.add_argument("--season-min", type=int, default=2023)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--headed", action="store_true")
    ap.add_argument("--status", action="store_true")
    a = ap.parse_args()
    if a.init:
        init_table()
    elif a.status:
        status()
    elif a.backfill:
        backfill(a.backfill, a.season_min, a.limit, headless=not a.headed)
    else:
        ap.print_help()
