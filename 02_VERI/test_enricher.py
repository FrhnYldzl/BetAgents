"""Quick test of stats_enricher functions."""
import sys
sys.stdout.reconfigure(encoding="utf-8")

from stats_enricher import (
    fetch_event, fetch_card_corners, fetch_recent_matches,
    fetch_standings, fetch_lineup,
    parse_h2h, parse_standings, parse_lineup, parse_card_corners_for_team
)

EID = 2975498
print("=== ENRICHER TEST ===")

ev = fetch_event(EID)
if ev:
    hn = ev.get("hn", "?")
    an = ev.get("an", "?")
    print(f"event: {hn} vs {an}  bri={ev.get('bri')}")
else:
    print("event: FAIL")
    hn = an = "?"

print()
cc = fetch_card_corners(EID)
if cc:
    h = parse_card_corners_for_team(cc, hn)
    a = parse_card_corners_for_team(cc, an)
    print(f"card-corners HOME ({hn}): corners_avg={h['corners_avg']} yc_avg={h['yc_avg']} rc_avg={h['rc_avg']}")
    print(f"card-corners AWAY ({an}): corners_avg={a['corners_avg']} yc_avg={a['yc_avg']} rc_avg={a['rc_avg']}")
else:
    print("card-corners: FAIL")

print()
rm = fetch_recent_matches(EID)
if rm:
    h2h = parse_h2h(rm, hn, an)
    print(f"H2H: {h2h}")
    mlist = rm.get("m") or []
    print(f"  Son maclar ({len(mlist)}):")
    for m in mlist[:5]:
        h = m.get("h") or {}
        a = m.get("a") or {}
        print(f"  {h.get('n','?'):20s} IY:{h.get('fhs',0)}-{a.get('fhs',0)}  FT:{h.get('rs',0)}-{a.get('rs',0)}  {a.get('n','?')}")
else:
    print("recent-matches: FAIL")

print()
st = fetch_standings(EID)
if st:
    sdata = parse_standings(st, hn, an)
    print(f"Standings parse: {sdata}")
    groups = st.get("g") or []
    for grp in groups[:1]:
        print(f"  Lig tablosu top-4:")
        for t in (grp.get("t") or [])[:4]:
            print(f"    {t.get('r'):2}. {t.get('n','?'):25s} {t.get('pt')} pt")
else:
    print("standings: FAIL")

print()
lu = fetch_lineup(EID)
if lu:
    ldata = parse_lineup(lu, hn, an)
    print(f"Lineup parse: {ldata}")
    hlu = (lu.get("h") or {}).get("p") or []
    starters = [p for p in hlu if p.get("r")]
    print(f"  {hn} 11'i ({len(starters)} starter):")
    for p in starters[:5]:
        print(f"    #{p.get('j',0):2} {p.get('n','?'):20s} [{p.get('p','?')}]")
else:
    print("lineup: FAIL")

print()
print("=== TEST TAMAMLANDI ===")
