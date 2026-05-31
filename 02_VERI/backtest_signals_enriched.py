"""
SIGNAL_SNAPSHOTS + ENRICHED BACKTEST
Implied probability filter (Edge65 equivalent) + enriched overlays.
"""
import sqlite3, sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
DB = Path(__file__).resolve().parent / "bahis_agent.db"

conn = sqlite3.connect(str(DB))
conn.row_factory = sqlite3.Row

rows = conn.execute("""
    SELECT ss.league_code, ss.season, ss.kickoff_iso,
           ss.home_team, ss.away_team,
           ss.odd_1, ss.odd_X, ss.odd_2,
           ss.dir_favorite, ss.agree_count,
           ss.score_v14, ss.result_1x2, ss.settled,
           m.h2h_n, m.h2h_home_wins, m.h2h_away_wins,
           m.home_relegation_gap, m.away_relegation_gap,
           m.home_form_5g, m.away_form_5g
    FROM signal_snapshots ss
    LEFT JOIN matches_v2 m
        ON ss.league_code = m.league_code
        AND substr(ss.kickoff_iso,1,10) = substr(m.kickoff_utc,1,10)
        AND lower(replace(ss.home_team,' ','')) = lower(replace(m.home_team,' ',''))
    WHERE ss.settled=1 AND ss.result_1x2 IS NOT NULL AND ss.odd_1 IS NOT NULL
      AND ss.league_code IN ('SP1','T1','D1','E0')
""").fetchall()
conn.close()

print(f"Toplam: {len(rows):,}")
enriched = sum(1 for r in rows if r["h2h_n"] is not None)
print(f"Enriched join: {enriched:,} ({enriched/len(rows)*100:.0f}%)")
print()

def calc_imp(o1, ox, o2):
    r = [1.0/o for o in [o1,ox,o2] if o and o > 0]
    s = sum(r)
    if s <= 0: return 0.0, 0.0, 0.0
    return r[0]/s, r[1]/s, r[2]/s

def h2h_ok(r, d):
    n = r["h2h_n"] or 0
    if n < 3: return True
    hw = r["h2h_home_wins"] or 0
    aw = r["h2h_away_wins"] or 0
    if d == "HOME": return (hw / n) >= 0.45
    return (aw / n) >= 0.40

def stand_ok(r):
    hr = r["home_relegation_gap"]
    ar = r["away_relegation_gap"]
    if hr is not None and hr <= 4: return False
    if ar is not None and ar <= 4: return False
    return True

def form_score(f):
    if not f: return 0.5
    sc = {"W": 1.0, "D": 0.5, "L": 0.0}
    vals = [sc.get(c, 0.5) for c in f[:5]]
    return sum(vals) / len(vals) if vals else 0.5

def form_ok(r, d):
    hs = form_score(r["home_form_5g"])
    as_ = form_score(r["away_form_5g"])
    if d == "HOME": return hs >= 0.50
    return as_ >= 0.50

def run(label, filt_fn):
    picks = wins = 0
    roi = 0.0
    for r in rows:
        o1, ox, o2 = r["odd_1"], r["odd_X"], r["odd_2"]
        if not all([o1, ox, o2]): continue
        ip1, ipx, ip2 = calc_imp(o1, ox, o2)
        fav = r["dir_favorite"]
        if not fav: continue
        d = "HOME" if fav in ("HOME","H","1") else ("AWAY" if fav in ("AWAY","A","2") else "DRAW")
        if d == "DRAW": continue
        imp = ip1 if d == "HOME" else ip2
        odds = o1 if d == "HOME" else o2
        res = r["result_1x2"]
        won = (d == "HOME" and res == "H") or (d == "AWAY" and res == "A")
        if not filt_fn(r, d, imp, odds): continue
        picks += 1
        if won: wins += 1; roi += odds - 1
        else: roi -= 1
    if picks == 0:
        print(f"  {label:<38} {'—':>5} {'—':>5} {'—':>5} {'—':>6}")
        return
    hit = wins / picks * 100
    rp = roi / picks * 100
    marker = " ✅" if rp > 3 else (" ⚠️" if rp > 0 else " ❌")
    print(f"  {label:<38} {picks:>5,} {hit:>4.1f}% {rp:>+5.1f}% {roi*100:>+9.0f} TL{marker}")

print(f"  {'Model':<38} {'Pick':>5} {'Hit%':>5} {'ROI%':>6} {'100TL Kâr':>10}")
print("  " + "─" * 68)

# Temel
run("M1  Her favori (baseline)",        lambda r,d,ip,o: True)
run("M2  imp ≥ 60%",                    lambda r,d,ip,o: ip >= 0.60)
run("M3  imp ≥ 65%",                    lambda r,d,ip,o: ip >= 0.65)
run("M4  imp ≥ 65% + agree ≥ 1",       lambda r,d,ip,o: ip >= 0.65 and (r["agree_count"] or 0) >= 1)
run("M5  imp ≥ 65% + agree ≥ 2",       lambda r,d,ip,o: ip >= 0.65 and (r["agree_count"] or 0) >= 2)

# Enriched
print()
run("M6  imp ≥ 65% + H2H",             lambda r,d,ip,o: ip >= 0.65 and h2h_ok(r, d))
run("M7  imp ≥ 65% + Standings",       lambda r,d,ip,o: ip >= 0.65 and stand_ok(r))
run("M8  imp ≥ 65% + Form 5G",         lambda r,d,ip,o: ip >= 0.65 and form_ok(r, d))
run("M9  imp ≥ 65% + H2H + Stand",     lambda r,d,ip,o: ip >= 0.65 and h2h_ok(r,d) and stand_ok(r))

# Sinyal + Enriched
print()
run("M10 ag≥1 + H2H + Stand",          lambda r,d,ip,o: ip >= 0.65 and (r["agree_count"] or 0) >= 1 and h2h_ok(r,d) and stand_ok(r))
run("M11 ag≥2 + H2H + Stand",          lambda r,d,ip,o: ip >= 0.65 and (r["agree_count"] or 0) >= 2 and h2h_ok(r,d) and stand_ok(r))
run("M12 ag≥1 + H2H + Stand + Form",   lambda r,d,ip,o: ip >= 0.65 and (r["agree_count"] or 0) >= 1 and h2h_ok(r,d) and stand_ok(r) and form_ok(r,d))

# T1 özel
print()
print("  ── T1 ONLY ──")
orig = rows[:]
rows_all = rows
rows = [r for r in rows if r["league_code"] == "T1"]

run("T1 M3  imp ≥ 65%",                lambda r,d,ip,o: ip >= 0.65)
run("T1 M4  imp ≥ 65% + agree ≥ 1",   lambda r,d,ip,o: ip >= 0.65 and (r["agree_count"] or 0) >= 1)
run("T1 M10 ag≥1 + H2H + Stand",       lambda r,d,ip,o: ip >= 0.65 and (r["agree_count"] or 0) >= 1 and h2h_ok(r,d) and stand_ok(r))
run("T1 M11 ag≥2 + H2H + Stand",       lambda r,d,ip,o: ip >= 0.65 and (r["agree_count"] or 0) >= 2 and h2h_ok(r,d) and stand_ok(r))

# T1 sezon bazında M10
print()
print("  ── T1 × Sezon (M10: imp65 + agree1 + H2H + Stand) ──")
seasons = {}
for r in rows:
    ssn = r["season"]
    if ssn not in seasons: seasons[ssn] = {"p":0,"w":0,"roi":0.0}
    o1, ox, o2 = r["odd_1"], r["odd_X"], r["odd_2"]
    if not all([o1,ox,o2]): continue
    ip1,_,ip2 = calc_imp(o1,ox,o2)
    fav = r["dir_favorite"]
    if not fav: continue
    d = "HOME" if fav in ("HOME","H","1") else ("AWAY" if fav in ("AWAY","A","2") else "DRAW")
    if d == "DRAW": continue
    imp = ip1 if d == "HOME" else ip2
    odds = o1 if d == "HOME" else o2
    res = r["result_1x2"]
    won = (d=="HOME" and res=="H") or (d=="AWAY" and res=="A")
    if not (imp >= 0.65 and (r["agree_count"] or 0) >= 1 and h2h_ok(r,d) and stand_ok(r)): continue
    seasons[ssn]["p"] += 1
    if won: seasons[ssn]["w"] += 1; seasons[ssn]["roi"] += odds - 1
    else: seasons[ssn]["roi"] -= 1

for ssn, v in sorted(seasons.items()):
    if v["p"] < 3: continue
    hit2 = v["w"]/v["p"]*100
    roi2 = v["roi"]/v["p"]*100
    marker = " ✅" if roi2 > 5 else (" ⚠️" if roi2 > 0 else " ❌")
    print(f"    {ssn:<8} {v['p']:>3} pick  {hit2:>5.1f}%  {roi2:>+6.1f}%{marker}")
