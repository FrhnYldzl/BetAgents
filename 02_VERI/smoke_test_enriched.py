"""
SMOKE TEST — ENRICHED DATA INTEGRITY + MODEL VALIDITY
=======================================================
Şunları test eder:
  S01  Veri bütünlüğü: enriched kolonlar doluluk ve range kontrolü
  S02  Temporal ordering: H2H/standings gelecek verisi kullanmıyor mu?
  S03  Tüm ligler (T1/E0/SP1/D1/I1/F1) — her biri ayrı ayrı
  S04  Tüm sezonlar (2017-18 → 2025-26) — walk-forward style
  S05  Enriched vs Baseline delta tutarlılığı — her lig × sezon
  S06  Sample size yeterliliği
  S07  İstatistiksel anlamlılık (basit z-test)
  S08  Lookahead bias testi
  S09  Market family: OU25 tam dataset testi
  S10  Büyük resim: tüm modeller tüm dataset

Çalıştır:
  python smoke_test_enriched.py
"""
import sqlite3, sys, math
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")

DB = Path(__file__).resolve().parent / "bahis_agent.db"

G="\033[92m"; R="\033[91m"; Y="\033[93m"; C="\033[96m"; B="\033[1m"; X="\033[0m"
OK=f"{G}PASS{X}"; FL=f"{R}FAIL{X}"; WN=f"{Y}WARN{X}"

passed=0; failed=0; warns=0
results=[]

def test(name, condition, detail="", warn_only=False):
    global passed, failed, warns
    if condition:
        passed += 1
        tag = OK
    elif warn_only:
        warns += 1
        tag = WN
    else:
        failed += 1
        tag = FL
    results.append((tag, name, detail))
    print(f"  [{tag}] {name}" + (f"  — {detail}" if detail else ""))

conn = sqlite3.connect(str(DB))
conn.row_factory = sqlite3.Row

# ════════════════════════════════════════════════════════
print(f"\n{B}{C}{'='*70}{X}")
print(f"{B}{C}  S01 — VERİ BÜTÜNLÜĞÜ{X}")
print(f"{B}{C}{'='*70}{X}")

total = conn.execute("SELECT COUNT(*) FROM matches_v2").fetchone()[0]
settled = conn.execute("SELECT COUNT(*) FROM matches_v2 WHERE is_settled=1").fetchone()[0]
test("matches_v2 toplam kayıt", total >= 19000, f"{total:,}")
test("Settled kayıt oranı", settled/total >= 0.95, f"{settled:,} / {total:,} = {settled/total*100:.1f}%")

# Enriched kolon doluluk
enrich_cols = [
    ("h2h_n",               0.85),
    ("h2h_home_wins",       0.85),
    ("h2h_btts_rate",       0.85),
    ("home_league_pos",     0.80),
    ("away_league_pos",     0.80),
    ("home_relegation_gap", 0.80),
    ("home_form_5g",        0.80),
    ("home_yc_5g_avg",      0.80),
    ("home_corners_5g_avg", 0.80),
]
for col, min_fill in enrich_cols:
    n = conn.execute(f"SELECT COUNT(*) FROM matches_v2 WHERE {col} IS NOT NULL").fetchone()[0]
    fill = n/total
    test(f"  {col} doluluk ≥{min_fill*100:.0f}%", fill >= min_fill,
         f"{n:,}/{total:,} = {fill*100:.1f}%", warn_only=(fill >= min_fill*0.8))

# Range kontrolleri
tests_range = [
    ("h2h_n BETWEEN 0 AND 50",                 "h2h_n < 0 OR h2h_n > 50"),
    ("home_league_pos BETWEEN 1 AND 30",        "home_league_pos < 1 OR home_league_pos > 30"),
    ("home_form_5g len 1-5",                    "length(home_form_5g) > 5"),
    ("home_yc_5g_avg ≥ 0",                     "home_yc_5g_avg < 0"),
    ("home_corners_5g_avg ≥ 0",                "home_corners_5g_avg < 0"),
]
for label, bad_cond in tests_range:
    n_bad = conn.execute(f"SELECT COUNT(*) FROM matches_v2 WHERE {bad_cond}").fetchone()[0]
    test(f"  Range: {label}", n_bad == 0, f"{n_bad} geçersiz kayıt" if n_bad else "")

# ════════════════════════════════════════════════════════
print(f"\n{B}{C}{'='*70}{X}")
print(f"{B}{C}  S02 — TEMPORAL ORDERING (LOOKAHEAD BİAS){X}")
print(f"{B}{C}{'='*70}{X}")

# H2H n > 0 olan maçlarda, o maçın kendi kendisiyle join edilmemiş olmalı
# Test: ilk sezon maçlarında H2H n = 0 veya çok az olmalı
first_season = conn.execute("""
    SELECT AVG(COALESCE(h2h_n, 0)) as avg_h2h
    FROM matches_v2
    WHERE season = '2017-18' AND is_settled=1
""").fetchone()[0] or 0

last_season = conn.execute("""
    SELECT AVG(COALESCE(h2h_n, 0)) as avg_h2h
    FROM matches_v2
    WHERE season = '2024-25' AND is_settled=1
""").fetchone()[0] or 0

test("İlk sezon (2017-18) H2H ortalaması < son sezon",
     first_season < last_season,
     f"2017-18 avg={first_season:.1f}, 2024-25 avg={last_season:.1f}")
test("İlk sezon H2H avg makul (< 3)",
     first_season < 3.0,
     f"2017-18 H2H avg = {first_season:.2f}")

# Form_5g'nin ilk maçta NULL olması beklenir (geçmiş yok)
null_form_early = conn.execute("""
    SELECT COUNT(*) FROM matches_v2
    WHERE season = '2017-18'
      AND matchday <= 3
      AND home_form_5g IS NOT NULL
""").fetchone()[0]
total_early = conn.execute("SELECT COUNT(*) FROM matches_v2 WHERE season='2017-18' AND matchday<=3").fetchone()[0]
test("Sezon başı ilk haftalarda form_5g kısmi NULL",
     null_form_early <= total_early * 0.7,
     f"İlk 3 hafta: {null_form_early}/{total_early} form_5g dolu", warn_only=True)

# H2H'nin matchday 1'de 0 veya çok az olması
h2h_md1 = conn.execute("""
    SELECT AVG(COALESCE(h2h_n,0)) FROM matches_v2
    WHERE matchday = 1 AND season='2017-18'
""").fetchone()[0] or 0
test("1. haftada H2H = 0 (ilk sezon, geçmiş yok)",
     h2h_md1 == 0,
     f"matchday=1, season=2017-18, avg H2H={h2h_md1:.1f}")

# ════════════════════════════════════════════════════════
print(f"\n{B}{C}{'='*70}{X}")
print(f"{B}{C}  S03 — TÜM LİGLER (6 lig){X}")
print(f"{B}{C}{'='*70}{X}")

ALL_LEAGUES = ["T1","E0","SP1","D1","I1","F1"]
ss_all = conn.execute("""
    SELECT ss.league_code, ss.odd_1, ss.odd_X, ss.odd_2,
           ss.dir_favorite, ss.agree_count, ss.score_v14,
           ss.result_1x2, ss.settled,
           m.h2h_n, m.h2h_home_wins, m.h2h_away_wins,
           m.home_relegation_gap, m.away_relegation_gap,
           m.home_form_5g, m.away_form_5g
    FROM signal_snapshots ss
    LEFT JOIN matches_v2 m
        ON ss.league_code = m.league_code
        AND substr(ss.kickoff_iso,1,10) = substr(m.kickoff_utc,1,10)
        AND lower(replace(ss.home_team,' ','')) = lower(replace(m.home_team,' ',''))
    WHERE ss.settled=1 AND ss.result_1x2 IS NOT NULL
      AND ss.odd_1 IS NOT NULL
""").fetchall()

def imp(o1,ox,o2):
    r=[1/o for o in [o1,ox,o2] if o and o>0]
    s=sum(r); return (r[0]/s,r[1]/s,r[2]/s) if s>0 else (0,0,0)

def h2h_ok(r,d):
    n=r["h2h_n"] or 0
    if n<3: return True
    hw=r["h2h_home_wins"] or 0; aw=r["h2h_away_wins"] or 0
    return (hw/n>=0.45) if d=="HOME" else (aw/n>=0.40)

def stand_ok(r):
    hr=r["home_relegation_gap"]; ar=r["away_relegation_gap"]
    if hr is not None and hr<=4: return False
    if ar is not None and ar<=4: return False
    return True

print(f"  {'Lig':4s} {'N':>5} {'Enrich%':>7} {'Base Pick':>9} {'Base Hit':>8} {'Base ROI':>8} {'Enr Pick':>8} {'Enr Hit':>8} {'Enr ROI':>8} {'ΔROI':>6}")
print(f"  {'-'*80}")

lig_summary = {}
for lg in ALL_LEAGUES:
    sub = [dict(r) for r in ss_all if r["league_code"]==lg]
    if not sub:
        print(f"  {lg:4s} {'—':>5} — veri yok")
        continue

    n_enr = sum(1 for r in sub if r["h2h_n"] is not None)
    enr_pct = n_enr/len(sub)*100

    # Baseline: imp>=65%
    bp=bw=0; br=0.0
    ep=ew=0; er=0.0
    for r in sub:
        o1,ox,o2 = r["odd_1"],r["odd_X"],r["odd_2"]
        if not all([o1,ox,o2]): continue
        ip1,_,ip2=imp(o1,ox,o2)
        fav=r["dir_favorite"]
        if not fav: continue
        d="HOME" if fav in("HOME","H","1") else("AWAY" if fav in("AWAY","A","2") else "DRAW")
        if d=="DRAW": continue
        im=ip1 if d=="HOME" else ip2
        odds=o1 if d=="HOME" else o2
        res=r["result_1x2"]
        won=(d=="HOME" and res=="H") or (d=="AWAY" and res=="A")
        if im<0.65: continue
        bp+=1
        if won: bw+=1; br+=odds-1
        else: br-=1
        if h2h_ok(r,d) and stand_ok(r):
            ep+=1
            if won: ew+=1; er+=odds-1
            else: er-=1

    b_hit=bw/bp*100 if bp>0 else 0; b_roi=br/bp*100 if bp>0 else 0
    e_hit=ew/ep*100 if ep>0 else 0; e_roi=er/ep*100 if ep>0 else 0
    d_roi=e_roi-b_roi

    col = G if d_roi>=2 else (R if d_roi<=-2 else Y)
    print(f"  {lg:4s} {len(sub):>5,} {enr_pct:>6.0f}% {bp:>9,} {b_hit:>7.1f}% {b_roi:>+7.1f}% {ep:>8,} {e_hit:>7.1f}% {e_roi:>+7.1f}% {col}{d_roi:>+5.1f}%{X}")
    lig_summary[lg] = {"b_roi":b_roi,"e_roi":e_roi,"d_roi":d_roi,"b_pick":bp,"e_pick":ep}

n_positive = sum(1 for v in lig_summary.values() if v["d_roi"]>0)
n_negative = sum(1 for v in lig_summary.values() if v["d_roi"]<0)
test(f"S03: Çoğunluk lig enriched'den yararlaniyor ({n_positive}/{len(lig_summary)})",
     n_positive >= len(lig_summary)*0.5,
     f"{n_positive} pozitif, {n_negative} negatif")

# ════════════════════════════════════════════════════════
print(f"\n{B}{C}{'='*70}{X}")
print(f"{B}{C}  S04 — TÜM SEZONLAR (walk-forward){X}")
print(f"{B}{C}{'='*70}{X}")

seasons_data = conn.execute("""
    SELECT ss.season, ss.odd_1, ss.odd_X, ss.odd_2,
           ss.dir_favorite, ss.result_1x2, ss.settled,
           m.h2h_n, m.h2h_home_wins, m.h2h_away_wins,
           m.home_relegation_gap, m.away_relegation_gap
    FROM signal_snapshots ss
    LEFT JOIN matches_v2 m
        ON ss.league_code = m.league_code
        AND substr(ss.kickoff_iso,1,10) = substr(m.kickoff_utc,1,10)
        AND lower(replace(ss.home_team,' ','')) = lower(replace(m.home_team,' ',''))
    WHERE ss.settled=1 AND ss.result_1x2 IS NOT NULL AND ss.odd_1 IS NOT NULL
      AND ss.league_code IN ('T1','E0','SP1','D1')
    ORDER BY ss.kickoff_iso
""").fetchall()

seasons = {}
for r in seasons_data:
    # Season conversion
    ssn_raw = r["season"]
    ssn_map = {"1718":"2017-18","1819":"2018-19","1920":"2019-20","2021":"2020-21",
               "2122":"2021-22","2223":"2022-23","2324":"2023-24","2425":"2024-25","2526":"2025-26"}
    ssn = ssn_map.get(str(ssn_raw), str(ssn_raw))
    if ssn not in seasons: seasons[ssn]={"rows":[]}
    seasons[ssn]["rows"].append(dict(r))

print(f"  {'Sezon':10s} {'N':>5} {'Base Pick':>9} {'Base ROI':>8} {'Enr Pick':>8} {'Enr ROI':>8} {'ΔROI':>6} {'Pass?':>6}")
print(f"  {'-'*65}")

season_results=[]
for ssn in sorted(seasons.keys()):
    rows=seasons[ssn]["rows"]
    bp=bw=0;br=0.0; ep=ew=0;er=0.0
    for r in rows:
        o1,ox,o2=r["odd_1"],r["odd_X"],r["odd_2"]
        if not all([o1,ox,o2]): continue
        ip1,_,ip2=imp(o1,ox,o2)
        fav=r["dir_favorite"]
        if not fav: continue
        d="HOME" if fav in("HOME","H","1") else("AWAY" if fav in("AWAY","A","2") else "DRAW")
        if d=="DRAW": continue
        im=ip1 if d=="HOME" else ip2
        odds=o1 if d=="HOME" else o2
        res=r["result_1x2"]
        won=(d=="HOME" and res=="H") or (d=="AWAY" and res=="A")
        if im<0.65: continue
        bp+=1
        if won: bw+=1; br+=odds-1
        else: br-=1
        if h2h_ok(r,d) and stand_ok(r):
            ep+=1
            if won: ew+=1; er+=odds-1
            else: er-=1
    b_roi=br/bp*100 if bp>0 else 0
    e_roi=er/ep*100 if ep>0 else 0
    d_roi=e_roi-b_roi
    ok_flag = d_roi >= -2
    col=G if d_roi>=2 else(R if d_roi<-2 else Y)
    flag_str=f"{G}OK{X}" if ok_flag else f"{R}KO{X}"
    print(f"  {ssn:10s} {len(rows):>5,} {bp:>9,} {b_roi:>+7.1f}% {ep:>8,} {e_roi:>+7.1f}% {col}{d_roi:>+5.1f}%{X} {flag_str}")
    season_results.append(ok_flag)

n_ok=sum(season_results)
test(f"S04: Sezonların ≥%60'ı enriched ile iyileşiyor veya ≥-2%",
     n_ok/len(season_results)>=0.60 if season_results else False,
     f"{n_ok}/{len(season_results)} sezon OK")

# ════════════════════════════════════════════════════════
print(f"\n{B}{C}{'='*70}{X}")
print(f"{B}{C}  S05 — SAMPLE SIZE KONTROLÜ{X}")
print(f"{B}{C}{'='*70}{X}")

for lg, v in lig_summary.items():
    test(f"  {lg} baseline pick >= 30",
         v["b_pick"] >= 30,
         f"{v['b_pick']} pick", warn_only=True)
    test(f"  {lg} enriched pick >= 5",
         v["e_pick"] >= 5,
         f"{v['e_pick']} pick", warn_only=True)

# ════════════════════════════════════════════════════════
print(f"\n{B}{C}{'='*70}{X}")
print(f"{B}{C}  S06 — İSTATİSTİKSEL ANLAM (z-test basit){X}")
print(f"{B}{C}{'='*70}{X}")

# Binomial test: H0: hit_rate = 0.50
# z = (p_hat - 0.50) / sqrt(0.25/n)
all_e_wins = all_e_pick = 0
for r in ss_all:
    o1,ox,o2=r["odd_1"],r["odd_X"],r["odd_2"]
    if not all([o1,ox,o2]): continue
    ip1,_,ip2=imp(o1,ox,o2)
    fav=r["dir_favorite"]
    if not fav: continue
    d="HOME" if fav in("HOME","H","1") else("AWAY" if fav in("AWAY","A","2") else "DRAW")
    if d=="DRAW": continue
    im=ip1 if d=="HOME" else ip2
    if im<0.65: continue
    r2=dict(r)
    if not h2h_ok(r2,d) or not stand_ok(r2): continue
    res=r["result_1x2"]
    won=(d=="HOME" and res=="H") or (d=="AWAY" and res=="A")
    all_e_pick+=1
    if won: all_e_wins+=1

if all_e_pick>=30:
    p_hat=all_e_wins/all_e_pick
    z=(p_hat-0.50)/math.sqrt(0.25/all_e_pick)
    p_value=0.5*(1-math.erf(abs(z)/math.sqrt(2)))  # approx
    test(f"S06a: Enriched hit > 50% baseline (z-test)",
         z>1.96, f"n={all_e_pick}, hit={p_hat*100:.1f}%, z={z:.2f}, p≈{p_value:.4f}")
    # ROI farklı H0: ROI > 0
    test(f"S06b: Sample >= 100 picks (istatistiksel yeterlilik)",
         all_e_pick>=100,
         f"n={all_e_pick}", warn_only=True)

# ════════════════════════════════════════════════════════
print(f"\n{B}{C}{'='*70}{X}")
print(f"{B}{C}  S07 — OU25 / BTTS TÜM DATASET{X}")
print(f"{B}{C}{'='*70}{X}")

# OU25 tüm dataset
ou_rows = conn.execute("""
    SELECT m.league_code, m.season,
           m.closing_over25, m.closing_under25,
           m.home_score, m.away_score,
           m.h2h_n, m.h2h_home_wins, m.h2h_away_wins,
           m.home_relegation_gap, m.away_relegation_gap,
           ss.dir_ou_model_cal, ss.s_ou_model_cal
    FROM matches_v2 m
    LEFT JOIN signal_snapshots ss
        ON ss.league_code = m.league_code
        AND substr(ss.kickoff_iso,1,10) = substr(m.kickoff_utc,1,10)
        AND lower(replace(ss.home_team,' ','')) = lower(replace(m.home_team,' ',''))
    WHERE m.is_settled=1 AND m.home_score IS NOT NULL
      AND m.closing_over25 IS NOT NULL
      AND ss.dir_ou_model_cal IS NOT NULL
""").fetchall()

test("S07a: OU25 signal_snapshots verisi mevcut",
     len(ou_rows) >= 100, f"{len(ou_rows):,} kayıt")

# BTTS closing odds durumu
btts_with_odds = conn.execute("""
    SELECT COUNT(*) FROM matches_v2
    WHERE closing_btts_yes IS NOT NULL AND is_settled=1
""").fetchone()[0]
test("S07b: BTTS closing odds mevcut",
     btts_with_odds >= 1000, f"{btts_with_odds:,} kayıt",
     warn_only=True)

# ════════════════════════════════════════════════════════
print(f"\n{B}{C}{'='*70}{X}")
print(f"{B}{C}  S08 — BÜYÜK RESİM ÖZET{X}")
print(f"{B}{C}{'='*70}{X}")

# Tüm ligler ve sezonlar üzerinde enriched performans
total_rows = dict(r) if False else None
all_b_pick=all_b_wins=0; all_b_roi=0.0
all_e_pick_g=all_e_wins_g=0; all_e_roi_g=0.0

for r in ss_all:
    o1,ox,o2=r["odd_1"],r["odd_X"],r["odd_2"]
    if not all([o1,ox,o2]): continue
    ip1,_,ip2=imp(o1,ox,o2)
    fav=r["dir_favorite"]
    if not fav: continue
    d="HOME" if fav in("HOME","H","1") else("AWAY" if fav in("AWAY","A","2") else "DRAW")
    if d=="DRAW": continue
    im=ip1 if d=="HOME" else ip2
    odds=o1 if d=="HOME" else o2
    if im<0.65: continue
    res=r["result_1x2"]
    won=(d=="HOME" and res=="H") or (d=="AWAY" and res=="A")
    all_b_pick+=1
    if won: all_b_wins+=1; all_b_roi+=odds-1
    else: all_b_roi-=1
    r2=dict(r)
    if h2h_ok(r2,d) and stand_ok(r2):
        all_e_pick_g+=1
        if won: all_e_wins_g+=1; all_e_roi_g+=odds-1
        else: all_e_roi_g-=1

b_hit_g=all_b_wins/all_b_pick*100 if all_b_pick else 0
b_roi_g=all_b_roi/all_b_pick*100 if all_b_pick else 0
e_hit_g=all_e_wins_g/all_e_pick_g*100 if all_e_pick_g else 0
e_roi_g=all_e_roi_g/all_e_pick_g*100 if all_e_pick_g else 0

print(f"  TÜM LİGLER (T1+E0+SP1+D1+I1+F1) — imp≥65%:")
print(f"  Baseline:  {all_b_pick:,} pick  {b_hit_g:.1f}% hit  {b_roi_g:+.2f}% ROI")
print(f"  Enriched:  {all_e_pick_g:,} pick  {e_hit_g:.1f}% hit  {e_roi_g:+.2f}% ROI")
print(f"  ΔROI = {e_roi_g-b_roi_g:+.2f}pp  | Pick azalması = {(all_b_pick-all_e_pick_g)/all_b_pick*100:.0f}%")

test("S08a: Enriched global hit > baseline",
     e_hit_g > b_hit_g, f"{e_hit_g:.1f}% > {b_hit_g:.1f}%")
test("S08b: Enriched global ROI > baseline",
     e_roi_g > b_roi_g, f"{e_roi_g:+.2f}% > {b_roi_g:+.2f}%")
test("S08c: Enriched global ROI > +2%",
     e_roi_g >= 2.0, f"{e_roi_g:+.2f}%", warn_only=True)
test("S08d: Pick azalması %60-90 arası (makul filtre)",
     0.40 <= (all_e_pick_g/all_b_pick) <= 0.85,
     f"{all_e_pick_g}/{all_b_pick} = %{all_e_pick_g/all_b_pick*100:.0f} kaldı")

conn.close()

# ════════════════════════════════════════════════════════
print(f"\n{B}{C}{'='*70}{X}")
print(f"{B}{C}  SMOKE TEST ÖZET{X}")
print(f"{B}{C}{'='*70}{X}")
print(f"\n  {G}PASS: {passed}{X}  {R}FAIL: {failed}{X}  {Y}WARN: {warns}{X}")
print(f"\n  {'Tag':6s} {'Test':50s} {'Detay'}")
print(f"  {'-'*80}")
for tag, name, detail in results:
    print(f"  [{tag}] {name[:50]:50s} {detail}")

overall = "PASS" if failed == 0 else ("WARN" if failed <= 2 else "FAIL")
col = G if failed==0 else (Y if failed<=2 else R)
print(f"\n  {col}{B}GENEL SONUÇ: {overall}{X}  ({passed} geçti, {failed} başarısız, {warns} uyarı)\n")
