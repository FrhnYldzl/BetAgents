"""
Sofascore KAPSAM PoC — kendi maçlarımızı Sofascore'da eşleştir, xG var mı ölç.
Odak: T1 (Türkiye) hangi sezondan beri xG'li? + niş 'ALL' ligler zengin mi?

Yöntem: headless Chromium (cf çerezi) → in-page fetch:
  scheduled-events/{date} → takım fuzzy-eşle → event/{id}/statistics → xG
"""
from __future__ import annotations
import sys, sqlite3, unicodedata, re
from difflib import SequenceMatcher
from pathlib import Path
from playwright.sync_api import sync_playwright
try: sys.stdout.reconfigure(encoding="utf-8")
except Exception: pass

DB = Path(__file__).resolve().parent.parent / "bahis_agent.db"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

def norm(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\b(spor|sk|fk|fc|cs|if|club|kulubu|belediyespor|as)\b", " ", s)
    return re.sub(r"[^a-z0-9]", "", s)

def sim(a, b):
    return SequenceMatcher(None, a, b).ratio()

def pick_sample():
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
    rows = []
    for yr in ["2018", "2020", "2021", "2022", "2023", "2024", "2025", "2026"]:
        for r in c.execute("""SELECT league_code,home_team,away_team,substr(kickoff_utc,1,10) d,
              home_score,away_score,home_xg FROM matches_v2
              WHERE league_code='T1' AND substr(kickoff_utc,1,4)=? AND home_score IS NOT NULL
              ORDER BY kickoff_utc DESC LIMIT 2""", (yr,)):
            rows.append(dict(r))
    for r in c.execute("""SELECT league_code,home_team,away_team,substr(kickoff_utc,1,10) d,
          home_score,away_score,home_xg FROM matches_v2
          WHERE league_code='ALL' AND home_score IS NOT NULL ORDER BY kickoff_utc DESC LIMIT 5"""):
        rows.append(dict(r))
    c.close(); return rows

def pf(page, url):
    return page.evaluate("""async (u)=>{try{const r=await fetch(u,{headers:{'Accept':'application/json'}});
        let b=null;try{b=await r.json()}catch(e){}return {s:r.status,b:b}}catch(e){return{s:'ERR',b:null}}}""", url)

def find_event(events, ht, aw):
    th, ta = norm(ht), norm(aw)
    best, bs = None, 0
    for e in events:
        eh = norm(e.get("homeTeam", {}).get("name", ""))
        ea = norm(e.get("awayTeam", {}).get("name", ""))
        sc = (sim(th, eh) + sim(ta, ea)) / 2
        if sc > bs: bs, best = sc, e
    return (best, bs) if bs >= 0.5 else (None, bs)

def xg_of(stat_body):
    if not isinstance(stat_body, dict): return None
    for per in stat_body.get("statistics", []):
        if per.get("period") != "ALL": continue
        for g in per.get("groups", []):
            for it in g.get("statisticsItems", []):
                if "xpected" in (it.get("name") or "") or it.get("key") == "expectedGoals":
                    return (it.get("home"), it.get("away"))
    return None

def run():
    sample = pick_sample()
    print(f"Örnek: {len(sample)} maç (T1 sezonlar + ALL niş)\n")
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        ctx = b.new_context(user_agent=UA, locale="tr-TR"); page = ctx.new_page()
        page.goto("https://www.sofascore.com/", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(4000)
        cache = {}
        rich = found = 0
        print(f"{'LIG/YIL':10} {'MAÇ':40} {'BULUNDU':8} {'xG'}")
        print("-" * 78)
        for m in sample:
            d = m["d"]
            if d not in cache:
                r = pf(page, f"https://api.sofascore.com/api/v1/sport/football/scheduled-events/{d}")
                cache[d] = (r.get("b") or {}).get("events", []) if isinstance(r.get("b"), dict) else []
            ev, score = find_event(cache[d], m["home_team"], m["away_team"])
            tag = f"{m['league_code']}/{d[:4]}"
            mc = f"{m['home_team'][:18]} v {m['away_team'][:17]}"
            if not ev:
                print(f"{tag:10} {mc:40} {'YOK':8} (eşleşme {score:.2f})"); continue
            found += 1
            st = pf(page, f"https://api.sofascore.com/api/v1/event/{ev['id']}/statistics")
            xg = xg_of(st.get("b"))
            if xg and xg[0] is not None:
                rich += 1
                print(f"{tag:10} {mc:40} {'✓':8} xG {xg[0]}-{xg[1]}")
            else:
                print(f"{tag:10} {mc:40} {'✓':8} xG YOK")
        b.close()
        print("-" * 78)
        print(f"ÖZET: {len(sample)} örnekten {found} eşleşti, {rich} tanesinde xG var.")

if __name__ == "__main__":
    run()
