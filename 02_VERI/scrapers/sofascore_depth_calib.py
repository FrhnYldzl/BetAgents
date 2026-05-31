"""
Sofascore VERİ DERİNLİĞİ kalibrasyonu — lig seviyesine göre xG/rating var mı?
Günün maçlarını çeker, farklı turnuvalardan örnekler, statistics derinliğini ölçer.
"""
from __future__ import annotations
import sys, json
from pathlib import Path
from playwright.sync_api import sync_playwright
try: sys.stdout.reconfigure(encoding="utf-8")
except Exception: pass

DATE = sys.argv[1] if len(sys.argv) > 1 else "2026-05-31"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

def pf(page, url):
    return page.evaluate("""async (u)=>{try{const r=await fetch(u,{headers:{'Accept':'application/json'}});
        let b=null; try{b=await r.json()}catch(e){} return {s:r.status,b:b}}catch(e){return {s:'ERR',b:null}}}""", url)

def stat_depth(body):
    """statistics body'sinde hangi metrikler var? xG / rating ipucu."""
    names=set()
    if not isinstance(body,dict): return names
    for per in body.get("statistics",[]):
        for g in per.get("groups",[]):
            for it in g.get("statisticsItems",[]):
                names.add(it.get("name"))
    return names

with sync_playwright() as p:
    b=p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
    ctx=b.new_context(user_agent=UA, locale="tr-TR"); page=ctx.new_page()
    page.goto("https://www.sofascore.com/", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(4000)
    sch=pf(page, f"https://api.sofascore.com/api/v1/sport/football/scheduled-events/{DATE}")
    evs=(sch.get("b") or {}).get("events",[]) if isinstance(sch.get("b"),dict) else []
    print(f"{DATE}: {len(evs)} maç (status {sch.get('s')})")
    # turnuvaya göre grupla, çeşitlilik için her turnuvadan 1 örnek
    by_t={}
    for e in evs:
        t=e.get("tournament",{}).get("name","?")
        by_t.setdefault(t,e)
    print(f"farklı turnuva: {len(by_t)}")
    # finished maçları tercih et (stat dolu olsun), 14 örnek
    sample=[e for e in by_t.values() if e.get("status",{}).get("type")=="finished"][:14]
    print(f"\n=== {len(sample)} maçta statistics derinliği (xG var mı?) ===")
    rich=0
    for e in sample:
        eid=e["id"]; t=e.get("tournament",{}).get("name","?")
        cat=e.get("tournament",{}).get("category",{}).get("name","?")
        r=pf(page, f"https://api.sofascore.com/api/v1/event/{eid}/statistics")
        names=stat_depth(r.get("b"))
        has_xg=any("xpected" in (n or "") or "xG" in (n or "") for n in names)
        if has_xg: rich+=1
        flag="xG VAR ✓" if has_xg else ("DERİN" if len(names)>6 else "SIĞ (sadece "+str(len(names))+" metrik)")
        print(f"  [{cat[:14]:14}] {t[:26]:26} | metrik:{len(names):2} | {flag}")
    print(f"\nÖZET: {len(sample)} maçtan {rich}'inde xG var.")
    b.close()
