"""
13 MODEL ENRICHED BACKTEST
===========================
Model Registry'deki tüm aktif modelleri (11 VALIDATED + PROTOTYPE)
enriched data (H2H + Standings) ile test eder.

Her model için:
  ÖNCE:  Mevcut performans (baseline registry değeri)
  SONRA: H2H + Standings overlay eklendikten sonra
  DELTA: İyileştirme veya bozulma

VOX Family (signal_snapshots):
  TRIVOX, MONOVOX-E0, DUOVOX, TRIOVOX, MONOVOX-SP1

MARKET Family (matches_v2):
  OU25-D1-Over, OU25-E0-Under
  BTTS-D1-Var, BTTS-SP1-Var, BTTS-SP1-Yok, BTTS-I1-Yok
"""
import sqlite3, sys, math
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")

DB = Path(__file__).resolve().parent / "bahis_agent.db"

# ── Renk çıktısı ──────────────────────────────────────────────
G = "\033[92m"; R = "\033[91m"; Y = "\033[93m"
C = "\033[96m"; B = "\033[1m";  X = "\033[0m"

def imp(o1, ox, o2):
    r = [1/o for o in [o1,ox,o2] if o and o>0]
    s = sum(r)
    return (r[0]/s, r[1]/s, r[2]/s) if s>0 else (0,0,0)

def h2h_ok(r, d):
    n = r.get("h2h_n") or 0
    if n < 3: return True
    hw = r.get("h2h_home_wins") or 0
    aw = r.get("h2h_away_wins") or 0
    return (hw/n >= 0.45) if d=="HOME" else (aw/n >= 0.40)

def stand_ok(r):
    hr = r.get("home_relegation_gap")
    ar = r.get("away_relegation_gap")
    if hr is not None and hr <= 4: return False
    if ar is not None and ar <= 4: return False
    return True

def fav_confirmed(r, min_conf=1):
    fav = r.get("dir_favorite","")
    if not fav: return None
    fn = "HOME" if fav in ("HOME","H","1") else ("AWAY" if fav in ("AWAY","A","2") else "DRAW")
    sigs = [r.get("dir_anomaly"), r.get("dir_model"), r.get("dir_xg"), r.get("dir_form")]
    agree = [s for s in sigs if s and (
        ("HOME" if s in ("HOME","H","1") else ("AWAY" if s in ("AWAY","A","2") else "DRAW")) == fn
    )]
    return fn if len(agree) >= min_conf else None

def run_test(rows, pick_fn, baseline_fn=None):
    """rows = list of dicts. pick_fn(r) -> (dir, odds) or None."""
    p = w = 0; roi = 0.0
    pb = wb = 0; roib = 0.0
    for r in rows:
        # Baseline
        if baseline_fn:
            rb = baseline_fn(r)
            if rb:
                d, o = rb
                res = r.get("result_1x2","")
                won = (d=="HOME" and res=="H") or (d=="AWAY" and res=="A") or (d=="DRAW" and res=="D")
                pb += 1
                if won: wb += 1; roib += o-1
                else: roib -= 1
        # Enriched
        result = pick_fn(r)
        if not result: continue
        d, o = result
        if not o or o < 1.10: continue
        res = r.get("result_1x2","")
        won = (d=="HOME" and res=="H") or (d=="AWAY" and res=="A") or (d=="DRAW" and res=="D")
        p += 1
        if won: w += 1; roi += o-1
        else: roi -= 1
    b_hit = wb/pb*100 if pb>0 else 0
    b_roi = roib/pb*100 if pb>0 else 0
    e_hit = w/p*100 if p>0 else 0
    e_roi = roi/p*100 if p>0 else 0
    return {"b_pick":pb,"b_hit":b_hit,"b_roi":b_roi,
            "e_pick":p,"e_hit":e_hit,"e_roi":e_roi,
            "d_hit":e_hit-b_hit,"d_roi":e_roi-b_roi}

def print_row(name, leagues, mkt, r, registry_hit=None, registry_roi=None):
    dh = r["d_hit"]; dr = r["d_roi"]
    dh_col = G if dh >= 0.5 else (R if dh < -0.5 else Y)
    dr_col = G if dr >= 1.0 else (R if dr < -1.0 else Y)
    reg_str = ""
    if registry_hit: reg_str = f"Reg:{registry_hit:.0f}%"
    print(f"  {B}{name:22s}{X} [{'+'.join(leagues):12s}] {mkt:8s} | "
          f"Öncesi:{r['b_pick']:4d} {r['b_hit']:4.1f}% {r['b_roi']:+5.1f}% | "
          f"Sonrası:{r['e_pick']:4d} {r['e_hit']:4.1f}% {r['e_roi']:+5.1f}% | "
          f"Δ Hit:{dh_col}{dh:+4.1f}%{X} Δ ROI:{dr_col}{dr:+5.1f}%{X}"
          + (f"  {Y}[{reg_str}]{X}" if reg_str else ""))

conn = sqlite3.connect(str(DB))
conn.row_factory = sqlite3.Row

# ════════════════════════════════════════════════════════════════
# VOX FAMILY — signal_snapshots + matches_v2 JOIN
# ════════════════════════════════════════════════════════════════
ss_rows_raw = conn.execute("""
    SELECT ss.*,
           m.h2h_n, m.h2h_home_wins, m.h2h_away_wins,
           m.home_relegation_gap, m.away_relegation_gap,
           m.home_league_pos, m.away_league_pos,
           m.home_form_5g, m.away_form_5g,
           m.home_yc_5g_avg, m.away_yc_5g_avg
    FROM signal_snapshots ss
    LEFT JOIN matches_v2 m
        ON ss.league_code = m.league_code
        AND substr(ss.kickoff_iso,1,10) = substr(m.kickoff_utc,1,10)
        AND lower(replace(ss.home_team,' ','')) = lower(replace(m.home_team,' ',''))
    WHERE ss.settled=1 AND ss.result_1x2 IS NOT NULL AND ss.odd_1 IS NOT NULL
""").fetchall()
ss_rows = [dict(r) for r in ss_rows_raw]

print(f"\n{B}{C}{'='*100}{X}")
print(f"{B}{C}  13 MODEL ENRICHED BACKTEST — H2H + Standings overlay{X}")
print(f"{B}{C}{'='*100}{X}")
print(f"  signal_snapshots: {len(ss_rows):,} kayıt  (enriched join: {sum(1 for r in ss_rows if r['h2h_n'] is not None):,})")
print()
print(f"  {'Model':22s} {'Ligler':12s} {'Pazar':8s} | {'Öncesi Pick Hit% ROI%':30s} | {'Sonrası Pick Hit% ROI%':30s} | Δ")
print(f"  {'-'*96}")

# ── VOX FAMILY ────────────────────────────────────────────────
print(f"\n{B}VOX FAMILY (signal_snapshots · FAV_CONFIRMED + Q5 + agree≥2){X}")

VOX_MODELS = [
    ("TRIVOX v1.2",   ["T1"],            0.82, 16.69),
    ("MONOVOX-E0",    ["E0"],            0.65,  1.31),
    ("DUOVOX",        ["E0","SP1"],      0.62,  0.0),
    ("TRIOVOX",       ["E0","SP1","D1"], 0.60,  0.0),
    ("MONOVOX-SP1",   ["SP1"],           0.55,  0.0),
]

def make_vox_picks(rows, leagues, enriched=False):
    """FAV_CONFIRMED + Q5 + agree>=2 ± enriched filter"""
    sub = [r for r in rows if r["league_code"] in leagues]
    if not sub: return []
    # Score quintile
    scores = sorted([r.get("score_v14") or 0 for r in sub])
    q80 = scores[int(len(scores)*0.80)] if len(scores)>=5 else 0
    result = []
    for r in sub:
        d = fav_confirmed(r, 1)
        if not d: continue
        if (r.get("agree_count") or 0) < 2: continue
        if (r.get("score_v14") or 0) < q80: continue
        if enriched:
            if not h2h_ok(r, d): continue
            if not stand_ok(r): continue
        o1, ox, o2 = r.get("odd_1"), r.get("odd_X"), r.get("odd_2")
        odds = o1 if d=="HOME" else (o2 if d=="AWAY" else ox)
        if not odds: continue
        result.append({**r, "_dir": d, "_odds": odds})
    return result

for name, leagues, reg_hit, reg_roi in VOX_MODELS:
    b_picks = make_vox_picks(ss_rows, leagues, enriched=False)
    e_picks = make_vox_picks(ss_rows, leagues, enriched=True)

    def calc(picks):
        p=w=0; roi=0.0
        for r in picks:
            d=r["_dir"]; o=r["_odds"]
            res=r.get("result_1x2","")
            won=(d=="HOME" and res=="H") or (d=="AWAY" and res=="A")
            p+=1
            if won: w+=1; roi+=o-1
            else: roi-=1
        return {"b_pick":p,"b_hit":w/p*100 if p else 0,"b_roi":roi/p*100 if p else 0,
                "e_pick":p,"e_hit":w/p*100 if p else 0,"e_roi":roi/p*100 if p else 0,
                "d_hit":0,"d_roi":0}

    br = calc(b_picks); er = calc(e_picks)
    result = {"b_pick":br["b_pick"],"b_hit":br["b_hit"],"b_roi":br["b_roi"],
              "e_pick":er["b_pick"],"e_hit":er["b_hit"],"e_roi":er["b_roi"],
              "d_hit":er["b_hit"]-br["b_hit"],"d_roi":er["b_roi"]-br["b_roi"]}
    print_row(name, leagues, "1X2", result, reg_hit*100, reg_roi)

# ── MARKET FAMILY ─────────────────────────────────────────────
print(f"\n{B}MARKET FAMILY (matches_v2 · DC model ihtimalleri){X}")

mkt_rows_raw = conn.execute("""
    SELECT m.*,
           ss.fp_ou_model_over_cal, ss.fp_ou_model_under_cal,
           ss.fp_btts_model_yes_cal, ss.fp_btts_model_no_cal,
           ss.dir_ou_model_cal, ss.dir_btts_model_cal,
           ss.s_ou_model_cal, ss.s_btts_model_cal
    FROM matches_v2 m
    LEFT JOIN signal_snapshots ss
        ON ss.league_code = m.league_code
        AND substr(ss.kickoff_iso,1,10) = substr(m.kickoff_utc,1,10)
        AND lower(replace(ss.home_team,' ','')) = lower(replace(m.home_team,' ',''))
    WHERE m.is_settled=1
      AND m.home_score IS NOT NULL
      AND m.closing_over25 IS NOT NULL
""").fetchall()
mkt_rows = [dict(r) for r in mkt_rows_raw]
conn.close()

print(f"  matches_v2: {len(mkt_rows):,} kayıt")

MARKET_MODELS = [
    # (name, leagues, market, direction, pick_fn_base, pick_fn_enriched, reg_hit)
    ("OU25-D1-Over",  ["D1"], "A/U 2.5", "Over",  0.61),
    ("OU25-E0-Under", ["E0"], "A/U 2.5", "Under", 0.43),
    ("BTTS-D1-Var",   ["D1"], "KG",      "Var",   0.61),
    ("BTTS-SP1-Var",  ["SP1"],"KG",      "Var",   0.58),
    ("BTTS-SP1-Yok",  ["SP1"],"KG",      "Yok",   0.55),
    ("BTTS-I1-Yok",   ["I1"], "KG",      "Yok",   0.47),
]

for name, leagues, mkt, direction, reg_hit in MARKET_MODELS:
    sub = [r for r in mkt_rows if r["league_code"] in leagues]
    bp=bw=0; br=0.0
    ep=ew=0; er_=0.0

    for r in sub:
        # Determine pick signal
        if mkt == "A/U 2.5":
            d = r.get("dir_ou_model_cal")
            if not d: continue
            if d != direction: continue
            o_over = r.get("closing_over25")
            o_under = r.get("closing_under25")
            if not o_over or not o_under: continue
            odds = o_over if direction=="Over" else o_under
            total_g = (r.get("home_score") or 0) + (r.get("away_score") or 0)
            actual_over = total_g > 2
            won = (direction=="Over" and actual_over) or (direction=="Under" and not actual_over)
        else:  # KG
            d = r.get("dir_btts_model_cal")
            if not d: continue
            if direction == "Var" and d != "Var": continue
            if direction == "Yok" and d not in ("Yok","YOK","No"): continue
            o_yes = r.get("closing_btts_yes")
            o_no  = r.get("closing_btts_no")
            if not o_yes and not o_no: continue
            odds = o_yes if direction=="Var" else o_no
            if not odds: continue
            hs = r.get("home_score") or 0
            as_ = r.get("away_score") or 0
            actual_btts = hs > 0 and as_ > 0
            won = (direction=="Var" and actual_btts) or (direction=="Yok" and not actual_btts)

        # Baseline
        bp += 1
        if won: bw += 1; br += odds - 1
        else: br -= 1

        # Enriched: + H2H + Standings
        if not h2h_ok(r, "HOME"): continue  # conservative — if H2H uncertain, skip
        if not stand_ok(r): continue
        ep += 1
        if won: ew += 1; er_ += odds - 1
        else: er_ -= 1

    b_hit = bw/bp*100 if bp>0 else 0; b_roi = br/bp*100 if bp>0 else 0
    e_hit = ew/ep*100 if ep>0 else 0; e_roi = er_/ep*100 if ep>0 else 0
    result = {"b_pick":bp,"b_hit":b_hit,"b_roi":b_roi,
              "e_pick":ep,"e_hit":e_hit,"e_roi":e_roi,
              "d_hit":e_hit-b_hit,"d_roi":e_roi-b_roi}
    print_row(name, leagues, mkt, result, reg_hit)

# ── ÖZET ──────────────────────────────────────────────────────
print(f"\n{B}{C}{'='*100}{X}")
print(f"{B}  ÖZET — Enriched Overlay Genel Etkisi{X}")
print(f"""
  VOX Family (FAV_CONFIRMED + Q5 + agree≥2):
    H2H + Standings overlay → Gereksiz pick'leri eler, kalitelileri bırakır
    Beklenen: Pick %20-40 azalır, Hit +1-3%, ROI +2-5 puan

  Market Family (DC model → OU25 / BTTS):
    H2H + Standings overlay → Motivasyon riski yüksek maçları eler
    Beklenen: BTTS modellerinde etkisi daha az (farklı mekanizma)
    KG Yok modeli için Standings özellikle güçlü (düşme baskısı = savunmacı oyun)

  Dikkat: Market modellerinde H2H "HOME" bazlı uygulandı — gerçek
  analizde her market için özel H2H mantığı gerekir.
""")
print(f"{B}{C}{'='*100}{X}")
