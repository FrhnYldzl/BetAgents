"""
SELECTIVE EDGE v1.2 — Historical Backtest (TUTARLILIK TESTİ)

Soru:
    "selection_score yüksek olan maçlar gerçekten daha iyi outcome veriyor mu?"

Yöntem:
    1. Football-Data.co.uk CSV'lerini yükle (B365 + Pinnacle odds, opening + closing)
    2. Birkaç hafta seç (farklı lig, farklı sezon)
    3. Her maç için SELECTIVE EDGE signal'larını hesapla (FD-uyumlu adaptasyon):
        - odds_anomaly (Check B: μ_OU vs μ_1X2)
        - model_confidence (DC modeli)
        - line_movement (B365 opening → PSC closing)
        - inverse_variance (overround)
    4. selection_score → top-3 seç
    5. Outcome ölç:
        a) Hit rate: signal_direction gerçekleşti mi?
        b) ROI: signal_direction'a Kelly stake (closing odds)
        c) CLV: opening vs closing edge
    6. Top-3 vs Bottom-3 vs Random-3 karşılaştırma

Bu testin sınırlamaları:
    - DC modeli 2024 sezon datasıyla eğitilmiş; backtest 2023-24 veya daha eski yıllarda yap
    - Football-Data BTTS odds yok → Check C atlanıyor
    - Combo markets yok → Check A kısmi
    - Asian Handicap var ama HC -1/+1 değil → Check D farklı
"""
from __future__ import annotations

import json
import math
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

THIS_DIR = Path(__file__).resolve().parent
YAZILIM = THIS_DIR.parent
RAW_DIR = YAZILIM / "02_VERI" / "raw"
MODELS_DIR = YAZILIM / "06_PRODUCTION" / "models"

sys.path.insert(0, str(YAZILIM / "03_MODELLER"))
sys.path.insert(0, str(YAZILIM / "03_MODELLER" / "selective"))

from base.dixon_coles import DCParams, score_matrix
from base.markets import prob_1x2, prob_over_under, prob_btts
from odds_anomaly import (
    implied, fair_probs, overround, lambda_from_ou, poisson_cdf,
)
from team_match import similarity, best_team_match


# ============================================================
# DC MODEL LOAD
# ============================================================

def load_dc(league: str) -> DCParams | None:
    p = MODELS_DIR / f"dc_params_{league}.json"
    if not p.exists():
        return None
    d = json.loads(p.read_text(encoding="utf-8"))
    return DCParams(teams=d["teams"], attack=d["attack"], defence=d["defence"],
                   home_adv=d["home_adv"], rho=d["rho"], xi=d["xi"])


# ============================================================
# DATA LOAD (Football-Data adapt)
# ============================================================

def load_week(league: str, season: str, date_from: str | None = None,
              date_to: str | None = None) -> pd.DataFrame:
    """
    Football-Data CSV yükle. league='E0', season='2324', date='YYYY-MM-DD'.
    """
    fn = RAW_DIR / f"{league}_{season}.csv"
    if not fn.exists():
        raise FileNotFoundError(fn)
    df = pd.read_csv(fn, encoding="latin-1")
    # Date parse: '%d/%m/%Y' veya '%d/%m/%y' (eski sezonlar 2-haneli yıl)
    dt = pd.to_datetime(df["Date"], format="%d/%m/%Y", errors="coerce")
    if dt.isna().sum() > len(df) / 2:
        dt = pd.to_datetime(df["Date"], format="%d/%m/%y", errors="coerce")
    df["Date"] = dt
    df = df.dropna(subset=["Date"])
    if date_from:
        df = df[df["Date"] >= pd.Timestamp(date_from)]
    if date_to:
        df = df[df["Date"] <= pd.Timestamp(date_to)]
    return df.reset_index(drop=True)


# ============================================================
# SIGNAL COMPUTATION (FD-adapted)
# ============================================================

def fd_signals(row: pd.Series, params: DCParams | None = None) -> dict:
    """
    Bir Football-Data satırı için SELECTIVE EDGE signal'larını hesapla.

    Odds columns:
        B365H/D/A     → opening 1X2
        PSCH/D/A      → closing 1X2 (Pinnacle, en sharp)
        AvgH/D/A      → avg 1X2
        B365>2.5/<2.5 → opening OU
        PC>2.5/PC<2.5 → closing OU (Pinnacle)
    """
    # NaN-safe getter (pandas NaN is truthy!)
    def _v(col):
        v = row.get(col)
        return None if pd.isna(v) else v

    # 1X2 closing (Pinnacle = sharp, fallback: Avg, fallback: B365CH)
    psc_h, psc_d, psc_a = _v("PSCH"), _v("PSCD"), _v("PSCA")
    if not (psc_h and psc_d and psc_a):
        psc_h = psc_h or _v("AvgH") or _v("B365CH")
        psc_d = psc_d or _v("AvgD") or _v("B365CD")
        psc_a = psc_a or _v("AvgA") or _v("B365CA")
    # 1X2 opening (B365) — NaN safe
    b_h, b_d, b_a = _v("B365H"), _v("B365D"), _v("B365A")
    # OU2.5 closing (Pinnacle, fallback)
    pc_over, pc_under = _v("PC>2.5"), _v("PC<2.5")
    if not (pc_over and pc_under):
        pc_over = pc_over or _v("Avg>2.5") or _v("B365C>2.5")
        pc_under = pc_under or _v("Avg<2.5") or _v("B365C<2.5")
    # OU2.5 opening
    b_over, b_under = _v("B365>2.5"), _v("B365<2.5")

    out = {
        "home": row["HomeTeam"], "away": row["AwayTeam"],
        "date": row["Date"],
        "ftr": row.get("FTR"),
        "fthg": row.get("FTHG"), "ftag": row.get("FTAG"),
        "psc_h": psc_h, "psc_d": psc_d, "psc_a": psc_a,
        "pc_over": pc_over, "pc_under": pc_under,
        # B365 opening odds (fallback chain) — YENI EKLEME
        "b_h": b_h, "b_d": b_d, "b_a": b_a,
        "b_over": b_over, "b_under": b_under,
        # Signal placeholders
        "s_anomaly": None, "s_model": None, "s_sharp": None, "s_invvar": None,
        "selection_score": 0.0,
        "signal_direction": None,
        "model_direction": None,
    }

    if not (psc_h and psc_d and psc_a and psc_h > 1.01):
        return out

    fp1, fpx, fp2 = fair_probs([psc_h, psc_d, psc_a])
    or_1x2 = overround([psc_h, psc_d, psc_a])

    fp_under = fp_over = None
    or_ou = None
    if pc_over and pc_under and pc_over > 1.01:
        fp_under, fp_over = fair_probs([pc_under, pc_over])
        or_ou = overround([pc_under, pc_over])

    # === CHECK B: μ_OU vs μ_1X2 ===
    s_anomaly_b = None
    anomaly_dir = None
    if fp_under is not None:
        mu_ou = lambda_from_ou(fp_under, 2.5)
        # 1X2'den μ_1X2 hesabı
        if (fp1 + fp2) > 0.01:
            ratio = fp1 / (fp1 + fp2)
            mu_1x2 = None
            for mu_test in [v / 20 for v in range(16, 120)]:
                lh = mu_test * ratio
                la = mu_test * (1 - ratio)
                pd_draw = sum(
                    (math.exp(-lh) * lh**k / math.factorial(k)) *
                    (math.exp(-la) * la**k / math.factorial(k))
                    for k in range(0, 8)
                )
                if pd_draw <= fpx + 0.001:
                    mu_1x2 = mu_test
                    break
            if mu_ou and mu_1x2:
                delta = abs(mu_ou - mu_1x2)
                s_anomaly_b = min(1.0, delta / 0.6)
                anomaly_dir = "OVER" if mu_ou > mu_1x2 else "UNDER"

    # === CHECK E: overround dispersion ===
    s_invvar = None
    if or_ou is not None:
        # mean & dispersion
        ors = [or_1x2, or_ou]
        mean_or = sum(ors) / 2
        dispersion = abs(or_1x2 - or_ou)
        # inv_var: düşük overround + düşük dispersion = yüksek
        s_invvar = max(0.0, 1.0 - mean_or / 0.10) * max(0.0, 1.0 - dispersion / 0.05)

    out["s_anomaly"] = s_anomaly_b
    out["s_invvar"] = s_invvar
    out["signal_direction"] = anomaly_dir

    # === MODEL CONFIDENCE: DC modeli ===
    s_model = None
    model_dir = None
    if params is not None:
        # Fuzzy match team adı
        home_m, _ = best_team_match(row["HomeTeam"], params.teams, min_score=0.7)
        away_m, _ = best_team_match(row["AwayTeam"], params.teams, min_score=0.7)
        if home_m and away_m:
            lam, mu = params.expected_goals(home_m, away_m)
            M = score_matrix(lam, mu, params.rho, max_goals=10)
            p_mod = prob_1x2(M)
            ou_mod = prob_over_under(M, 2.5)
            edges = {
                "1": p_mod["1"] - fp1,
                "X": p_mod["X"] - fpx,
                "2": p_mod["2"] - fp2,
            }
            if fp_over is not None:
                edges["Over"] = ou_mod["over"] - fp_over
                edges["Under"] = ou_mod["under"] - fp_under
            max_edge = max(edges.values())
            max_edge_key = max(edges, key=lambda k: edges[k])
            # JS divergence yaklaşık ölçü
            js = 0
            for pm, pi in [(p_mod["1"], fp1), (p_mod["X"], fpx), (p_mod["2"], fp2)]:
                if pm > 0 and pi > 0:
                    js += pm * math.log(pm / ((pm + pi) / 2)) / 2
                    js += pi * math.log(pi / ((pm + pi) / 2)) / 2
            agreement = max(0.0, 1.0 - abs(js) / 0.3)
            edge_score = max(0.0, min(1.0, max_edge / 0.10))
            s_model = 0.4 * agreement + 0.6 * edge_score
            model_dir = max_edge_key
            out["model_lam_h"] = lam
            out["model_lam_a"] = mu
            out["model_p1"] = p_mod["1"]
            out["model_pX"] = p_mod["X"]
            out["model_p2"] = p_mod["2"]
            out["model_pover"] = ou_mod["over"]
            out["model_max_edge"] = max_edge

    out["s_model"] = s_model
    out["model_direction"] = model_dir

    # === SHARP MONEY: B365 opening → PSC closing ===
    s_sharp = None
    sharp_dir = None
    if b_h and psc_h:
        deltas = {}
        for sel, opener, closer in [
            ("H", b_h, psc_h), ("D", b_d, psc_d), ("A", b_a, psc_a),
        ]:
            if opener and closer and opener > 1.01:
                pct = (closer / opener - 1) * 100
                deltas[sel] = pct
        if b_over and pc_over:
            for sel, opener, closer in [
                ("Over", b_over, pc_over), ("Under", b_under, pc_under),
            ]:
                if opener and closer and opener > 1.01:
                    deltas[sel] = (closer / opener - 1) * 100
        if deltas:
            sharpest_sel = min(deltas, key=lambda k: deltas[k])
            sharpest_pct = deltas[sharpest_sel]
            if sharpest_pct < -3:
                s_sharp = min(1.0, abs(sharpest_pct) / 15)
                sharp_dir = sharpest_sel
        out["sharp_deltas"] = deltas

    out["s_sharp"] = s_sharp
    out["sharp_direction"] = sharp_dir

    # === COMBINED selection_score ===
    WEIGHTS = {"anomaly": 0.40, "model": 0.30, "sharp": 0.15, "invvar": 0.15}
    parts = []
    if s_anomaly_b is not None:
        parts.append((WEIGHTS["anomaly"], s_anomaly_b))
    if s_model is not None:
        parts.append((WEIGHTS["model"], s_model))
    if s_sharp is not None:
        parts.append((WEIGHTS["sharp"], s_sharp))
    if s_invvar is not None:
        parts.append((WEIGHTS["invvar"], s_invvar))
    if parts:
        w_total = sum(w for w, _ in parts)
        out["selection_score"] = sum(w * v for w, v in parts) / w_total

    return out


# ============================================================
# OUTCOME EVALUATION
# ============================================================

def evaluate_pick(sig: dict, direction: str | None = None) -> dict:
    """
    Bir maç için tahmin yönünün gerçekleştiğini ölç.

    direction: "OVER", "UNDER", "HOME", "AWAY", "DRAW", veya signal_direction
    """
    if direction is None:
        direction = sig.get("model_direction") or sig.get("signal_direction")
    if not direction:
        return {"placed": False, "won": None, "odd": None, "pnl": 0}

    fthg, ftag = sig.get("fthg"), sig.get("ftag")
    if fthg is None or ftag is None:
        return {"placed": False, "won": None, "odd": None, "pnl": 0}

    total = fthg + ftag
    ftr = sig.get("ftr")
    won = False
    odd = None

    if direction == "OVER" or direction == "Over":
        won = total > 2.5
        odd = sig.get("pc_over")
    elif direction == "UNDER" or direction == "Under":
        won = total < 2.5
        odd = sig.get("pc_under")
    elif direction in ("HOME", "1", "H"):
        won = ftr == "H"
        odd = sig.get("psc_h")
    elif direction in ("AWAY", "2", "A"):
        won = ftr == "A"
        odd = sig.get("psc_a")
    elif direction in ("DRAW", "X", "D"):
        won = ftr == "D"
        odd = sig.get("psc_d")

    if not odd or odd < 1.01:
        return {"placed": False, "won": won, "odd": odd, "pnl": 0, "direction": direction}

    # PnL: 1 birim stake
    pnl = (odd - 1) if won else -1
    return {
        "placed": True, "won": won, "odd": odd, "pnl": pnl,
        "direction": direction,
    }


# ============================================================
# WEEK BACKTEST
# ============================================================

def run_week(league: str, season: str, date_from: str, date_to: str,
             top_n: int = 3, params: DCParams | None = None) -> dict:
    """Bir hafta için top-N seçim + outcome."""
    df = load_week(league, season, date_from, date_to)
    if df.empty:
        return {"matches": 0, "signals": [], "top_n": []}
    if params is None:
        params = load_dc(league)

    signals = [fd_signals(row, params) for _, row in df.iterrows()]
    # Sort by selection_score
    signals.sort(key=lambda s: s["selection_score"], reverse=True)

    # Top-3 (model_direction prefer, fallback signal_direction)
    top_picks = []
    for s in signals[:top_n]:
        ev = evaluate_pick(s)
        top_picks.append({**s, **{"eval_" + k: v for k, v in ev.items()}})

    # Bottom-3
    bottom_picks = []
    for s in signals[-top_n:]:
        ev = evaluate_pick(s)
        bottom_picks.append({**s, **{"eval_" + k: v for k, v in ev.items()}})

    # Random-3 (deterministic seed from date)
    rng = np.random.RandomState(hash(date_from) % (2**31))
    rand_idx = rng.choice(len(signals), size=min(top_n, len(signals)), replace=False)
    random_picks = []
    for i in rand_idx:
        s = signals[i]
        ev = evaluate_pick(s)
        random_picks.append({**s, **{"eval_" + k: v for k, v in ev.items()}})

    return {
        "league": league, "season": season,
        "date_from": date_from, "date_to": date_to,
        "matches": len(df),
        "all_signals": signals,
        "top": top_picks,
        "bottom": bottom_picks,
        "random": random_picks,
    }


def summarize_group(name: str, picks: list[dict]) -> dict:
    placed = [p for p in picks if p.get("eval_placed")]
    won = [p for p in placed if p.get("eval_won")]
    total_pnl = sum(p["eval_pnl"] for p in placed)
    hit_rate = len(won) / len(placed) if placed else None
    roi = total_pnl / len(placed) if placed else None
    return {
        "name": name,
        "n_placed": len(placed),
        "n_won": len(won),
        "hit_rate": hit_rate,
        "total_pnl": total_pnl,
        "roi": roi,
        "avg_odd": sum(p["eval_odd"] or 0 for p in placed) / len(placed) if placed else None,
        "avg_score": sum(p.get("selection_score", 0) for p in picks) / len(picks) if picks else 0,
    }


def print_week_report(result: dict):
    print(f"\n{'='*100}")
    print(f"HAFTA: {result['league']}/{result['season']}  "
          f"{result['date_from']} -> {result['date_to']}  "
          f"({result['matches']} mac)")
    print("="*100)

    for group_name in ["top", "random", "bottom"]:
        group = result[group_name]
        if not group:
            continue
        emoji = {"top": "[TOP-3]", "random": "[RND-3]", "bottom": "[BOT-3]"}[group_name]
        print(f"\n{emoji}")
        for p in group:
            score = p.get("selection_score", 0)
            anom = f"{p['s_anomaly']:.2f}" if p.get("s_anomaly") is not None else " -  "
            mod = f"{p['s_model']:.2f}" if p.get("s_model") is not None else " -  "
            sharp = f"{p['s_sharp']:.2f}" if p.get("s_sharp") is not None else " -  "
            dirn = p.get("model_direction") or p.get("signal_direction") or "-"
            ev = p.get("eval_won")
            ev_str = "OK " if ev else ("X  " if ev is False else "?  ")
            odd = p.get("eval_odd") or 0
            pnl = p.get("eval_pnl") or 0
            label = f"{p['home']} {p.get('fthg','?')}-{p.get('ftag','?')} {p['away']}"
            print(f"  score={score:.2f}  a={anom} m={mod} s={sharp}  -> {dirn:6s} @ {odd:.2f}  "
                  f"{ev_str} pnl={pnl:+.2f}  | {label}")


def run_multi_week():
    """Birkaç farklı (lig, sezon, hafta) çalıştır."""
    weeks = [
        # (league, season, date_from, date_to)
        # 2023-24 sezonu (multi-league)
        ("E0", "2324", "2023-10-20", "2023-10-22"),
        ("E0", "2324", "2024-01-12", "2024-01-14"),
        ("E0", "2324", "2024-04-13", "2024-04-15"),
        ("D1", "2324", "2023-11-03", "2023-11-05"),
        ("D1", "2324", "2024-02-23", "2024-02-25"),
        ("D1", "2324", "2024-04-13", "2024-04-15"),
        ("T1", "2324", "2023-12-08", "2023-12-10"),
        ("T1", "2324", "2024-03-08", "2024-03-10"),
        ("T1", "2324", "2024-04-19", "2024-04-21"),
        # 2024-25 sezonu
        ("E0", "2425", "2024-10-25", "2024-10-27"),
        ("E0", "2425", "2024-12-14", "2024-12-16"),
        ("D1", "2425", "2024-11-08", "2024-11-10"),
        ("D1", "2425", "2025-01-25", "2025-01-27"),
        ("T1", "2425", "2024-12-13", "2024-12-15"),
        ("T1", "2425", "2025-02-21", "2025-02-23"),
    ]

    all_groups = {"top": [], "random": [], "bottom": []}
    week_results = []
    verbose = "--verbose" in sys.argv
    for league, season, df_, dt_ in weeks:
        result = run_week(league, season, df_, dt_)
        week_results.append(result)
        if verbose:
            print_week_report(result)
        for g in ("top", "random", "bottom"):
            all_groups[g].extend(result.get(g, []))

    print("\n" + "="*100)
    print("AGGREGATED RESULTS  (n_weeks={})".format(len(weeks)))
    print("="*100)
    print(f"{'Group':12s} {'n_placed':>8s} {'won':>4s} {'hit%':>6s} {'tot_pnl':>9s} {'ROI%':>7s} {'avg_odd':>8s} {'avg_score':>10s}")
    print("-"*100)
    summaries = {}
    for g in ("top", "random", "bottom"):
        s = summarize_group(g, all_groups[g])
        summaries[g] = s
        hr = f"{s['hit_rate']*100:.0f}" if s['hit_rate'] is not None else "-"
        roi = f"{s['roi']*100:+.1f}" if s['roi'] is not None else "-"
        odd = f"{s['avg_odd']:.2f}" if s['avg_odd'] else "-"
        print(f"{s['name']:12s} {s['n_placed']:>8d} {s['n_won']:>4d} {hr:>6s} "
              f"{s['total_pnl']:>+9.2f} {roi:>7s} {odd:>8s} {s['avg_score']:>10.3f}")

    # === ISTATISTIKSEL ANLAMLILIK ===
    print("\n" + "="*100)
    print("ISTATISTIKSEL ANLAMLILIK (Welch t-test, top vs bottom)")
    print("="*100)
    top_pnl = [p["eval_pnl"] for p in all_groups["top"] if p.get("eval_placed")]
    bot_pnl = [p["eval_pnl"] for p in all_groups["bottom"] if p.get("eval_placed")]
    rnd_pnl = [p["eval_pnl"] for p in all_groups["random"] if p.get("eval_placed")]
    if top_pnl and bot_pnl:
        # Welch t-test (eşit olmayan varyans için)
        def welch_t(a, b):
            ma, mb = sum(a)/len(a), sum(b)/len(b)
            va = sum((x - ma)**2 for x in a) / (len(a) - 1) if len(a) > 1 else 0
            vb = sum((x - mb)**2 for x in b) / (len(b) - 1) if len(b) > 1 else 0
            se = (va/len(a) + vb/len(b)) ** 0.5 if (va/len(a) + vb/len(b)) > 0 else 1e-9
            return (ma - mb) / se
        t_tb = welch_t(top_pnl, bot_pnl)
        t_tr = welch_t(top_pnl, rnd_pnl)
        # Approx p-value (two-tail, normal approx for df~30)
        def approx_p(t):
            # cumulative normal yaklaşımı
            import math
            return 2 * (1 - 0.5 * (1 + math.erf(abs(t) / math.sqrt(2))))
        p_tb = approx_p(t_tb)
        p_tr = approx_p(t_tr)
        print(f"  TOP vs BOTTOM: t={t_tb:+.3f}  p~{p_tb:.3f}  "
              f"({'ANLAMLI' if p_tb < 0.05 else 'anlamsiz'})")
        print(f"  TOP vs RANDOM: t={t_tr:+.3f}  p~{p_tr:.3f}  "
              f"({'ANLAMLI' if p_tr < 0.05 else 'anlamsiz'})")

    # === CORRELATION: selection_score vs PnL ===
    print("\n" + "="*100)
    print("KORELASYON: selection_score <-> PnL (tum hafta tum mac)")
    print("="*100)
    all_signals_flat = []
    for w in week_results:
        for s in w["all_signals"]:
            ev = evaluate_pick(s)
            if ev.get("placed"):
                all_signals_flat.append({
                    "score": s["selection_score"],
                    "pnl": ev["pnl"],
                    "won": 1 if ev["won"] else 0,
                })
    if all_signals_flat:
        scores = [x["score"] for x in all_signals_flat]
        pnls = [x["pnl"] for x in all_signals_flat]
        wons = [x["won"] for x in all_signals_flat]
        ms, mp, mw = sum(scores)/len(scores), sum(pnls)/len(pnls), sum(wons)/len(wons)
        def pearson(xs, ys):
            mx = sum(xs)/len(xs); my = sum(ys)/len(ys)
            num = sum((x-mx)*(y-my) for x,y in zip(xs,ys))
            dx = (sum((x-mx)**2 for x in xs))**0.5
            dy = (sum((y-my)**2 for y in ys))**0.5
            return num/(dx*dy) if dx*dy > 0 else 0
        r_pnl = pearson(scores, pnls)
        r_won = pearson(scores, wons)
        print(f"  n={len(all_signals_flat)} bet placed")
        print(f"  Pearson(score, PnL) = {r_pnl:+.4f}  (yuksek=score bilgilendirici)")
        print(f"  Pearson(score, Won) = {r_won:+.4f}")

        # Quintile analysis
        sorted_by_score = sorted(all_signals_flat, key=lambda x: x["score"])
        n = len(sorted_by_score)
        print(f"\n  QUINTILE ANALYSIS:")
        print(f"  {'Q':>3s} {'n':>4s} {'hit%':>6s} {'ROI%':>7s} {'avg_score':>10s}")
        for q in range(5):
            chunk = sorted_by_score[int(q*n/5):int((q+1)*n/5)]
            if not chunk: continue
            hr = sum(x["won"] for x in chunk) / len(chunk) * 100
            roi = sum(x["pnl"] for x in chunk) / len(chunk) * 100
            asc = sum(x["score"] for x in chunk) / len(chunk)
            print(f"  Q{q+1:>2d} {len(chunk):>4d} {hr:>6.0f} {roi:>+7.1f} {asc:>10.3f}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "multi"
    if cmd == "multi":
        run_multi_week()
    elif cmd == "week":
        # python selective_backtest.py week E0 2324 2024-04-13 2024-04-15
        result = run_week(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5])
        print_week_report(result)
    else:
        print("Komutlar: multi | week <league> <season> <date_from> <date_to>")
