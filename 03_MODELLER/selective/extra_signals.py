"""
SELECTIVE EDGE v1.3 — Ek Sinyaller (xG luck regression, form trend)

Bookmaker'a "ne biliyorsun ki onun bilmediği?" sorusu için:
    1. xG_luck_signal: takım gerçek gole göre overperform/underperform ediyor mu?
       - xG_for_5 > goals_for_5 → underperforming → bounce-back bekle
       - xG_for_5 < goals_for_5 → overperforming → regression bekle
       - Bookmaker bu mean-reversion'ı eksik fiyatlayabilir
    2. form_signal: son 5 maç W/D/L ağırlıklı
       - 3+ kazanma → güç gösterici
       - 3+ kaybetme → düşüş ivmesi

Bu sinyaller "leaky" değildir: backtest sırasında SADECE pivot maçtan ÖNCE
gerçekleşmiş maçlardan beslenir.
"""
from __future__ import annotations

import sys
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
YAZILIM = THIS_DIR.parent.parent
sys.path.insert(0, str(YAZILIM / "02_VERI"))
sys.path.insert(0, str(THIS_DIR))

from team_match import normalize


# ============================================================
# IN-MEMORY CACHE
# ============================================================

_XG_CACHE: dict | None = None
_FIX_CACHE: dict | None = None


def _load_xg_cache():
    """xg_data tablosunu memory'ye yükle (hızlı erişim için)."""
    global _XG_CACHE
    if _XG_CACHE is not None:
        return _XG_CACHE
    db_path = YAZILIM / "02_VERI" / "bahis_agent.db"
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT league_code, season, match_date, home_team, away_team,
               home_xg, away_xg, home_goals, away_goals
        FROM xg_data
        WHERE home_xg IS NOT NULL AND away_xg IS NOT NULL
    """).fetchall()
    conn.close()
    cache = {}
    for r in rows:
        d = dict(r)
        h_norm = normalize(d["home_team"])
        a_norm = normalize(d["away_team"])
        cache.setdefault(h_norm, []).append({
            **d, "match_date": d["match_date"], "is_home": True,
        })
        cache.setdefault(a_norm, []).append({
            **d, "match_date": d["match_date"], "is_home": False,
        })
    # Sort by date
    for k in cache:
        cache[k].sort(key=lambda x: x["match_date"])
    _XG_CACHE = cache
    return cache


def _load_fix_cache():
    """fixtures tablosundan W/D/L cache (form sinyali için)."""
    global _FIX_CACHE
    if _FIX_CACHE is not None:
        return _FIX_CACHE
    db_path = YAZILIM / "02_VERI" / "bahis_agent.db"
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT league_code, season, kickoff_utc, home_team, away_team,
               home_score, away_score, status
        FROM fixtures
        WHERE status='FT' AND home_score IS NOT NULL
    """).fetchall()
    conn.close()
    cache = {}
    for r in rows:
        d = dict(r)
        h_norm = normalize(d["home_team"])
        a_norm = normalize(d["away_team"])
        result = "D"
        if d["home_score"] > d["away_score"]:
            result = "H"
        elif d["away_score"] > d["home_score"]:
            result = "A"
        cache.setdefault(h_norm, []).append({
            "date": d["kickoff_utc"][:10],
            "team_is_home": True,
            "result": result,
            "gf": d["home_score"], "ga": d["away_score"],
        })
        cache.setdefault(a_norm, []).append({
            "date": d["kickoff_utc"][:10],
            "team_is_home": False,
            "result": result,
            "gf": d["away_score"], "ga": d["home_score"],
        })
    for k in cache:
        cache[k].sort(key=lambda x: x["date"])
    _FIX_CACHE = cache
    return cache


# ============================================================
# xG LUCK SIGNAL
# ============================================================

def xg_luck_signal(home_team: str, away_team: str,
                    match_date: str, lookback: int = 5) -> dict:
    """
    Home ve away takımı için son N maçta xG-goals deltası.

    v1.1: Fuzzy team match fallback (xG cache farklı naming kullanıyorsa).
    """
    from team_match import similarity
    cache = _load_xg_cache()
    h_norm = normalize(home_team)
    a_norm = normalize(away_team)

    # Fuzzy fallback: exact key yoksa similarity ≥0.7 olan key'i bul
    _fuzzy_cache_key = {}  # in-function cache
    def fuzzy_find(team_norm):
        if team_norm in cache:
            return team_norm
        if team_norm in _fuzzy_cache_key:
            return _fuzzy_cache_key[team_norm]
        # Best fuzzy match in cache
        best_key = None; best_score = 0
        for k in cache.keys():
            s = similarity(team_norm, k)
            if s > best_score:
                best_score = s; best_key = k
        if best_score >= 0.70:
            _fuzzy_cache_key[team_norm] = best_key
            return best_key
        _fuzzy_cache_key[team_norm] = None
        return None

    def last_n(team_norm):
        key = fuzzy_find(team_norm)
        if not key:
            return []
        hist = cache.get(key, [])
        relevant = [h for h in hist if h["match_date"] < match_date]
        return relevant[-lookback:]

    home_hist = last_n(h_norm)
    away_hist = last_n(a_norm)

    if not home_hist or not away_hist:
        return {"s_xg": None, "direction": None,
                "home_luck": None, "away_luck": None,
                "home_n": len(home_hist), "away_n": len(away_hist)}

    def luck(hist):
        gf, gA, xgf, xgA = 0, 0, 0.0, 0.0
        for h in hist:
            if h["is_home"]:
                gf += h["home_goals"] or 0
                gA += h["away_goals"] or 0
                xgf += h["home_xg"] or 0
                xgA += h["away_xg"] or 0
            else:
                gf += h["away_goals"] or 0
                gA += h["home_goals"] or 0
                xgf += h["away_xg"] or 0
                xgA += h["home_xg"] or 0
        return (gf - xgf), (gA - xgA)

    h_lucky_attack, h_lucky_defense = luck(home_hist)
    a_lucky_attack, a_lucky_defense = luck(away_hist)

    # Net luck: pozitif = overperforming → bounce-back (kötüleşecek)
    h_net = h_lucky_attack - h_lucky_defense
    a_net = a_lucky_attack - a_lucky_defense

    # Sinyal: en şanslı/şanssız takımı bul
    luck_diff = h_net - a_net  # pozitif = home overperforming
    # |diff| 2+ goal → 1.0 signal
    s_xg = min(1.0, abs(luck_diff) / 4.0)

    # Yön: home overperforming → AWAY safer (regression home down)
    # Wait, mean reversion: lucky team will regress, so opposite team is safer
    if luck_diff > 1.5:
        direction = "AWAY"  # home overperforming → away bounce back
    elif luck_diff < -1.5:
        direction = "HOME"
    else:
        direction = None

    return {
        "s_xg": s_xg if direction else 0,
        "direction": direction,
        "home_luck": h_net,
        "away_luck": a_net,
        "luck_diff": luck_diff,
        "home_n": len(home_hist),
        "away_n": len(away_hist),
    }


# ============================================================
# FORM SIGNAL
# ============================================================

def form_signal_from_cache(home_team: str, away_team: str,
                           match_date: str, cache: dict,
                           lookback: int = 5) -> dict:
    """
    Tek bir CSV/dict cache'inden form hesabı (backtest için).

    cache: {team_norm: [{"date":..., "team_is_home":..., "result": "H/D/A"}, ...]}
    """
    h_norm = normalize(home_team)
    a_norm = normalize(away_team)

    def last_n(team_norm):
        hist = cache.get(team_norm, [])
        relevant = [h for h in hist if h["date"] < match_date]
        return relevant[-lookback:]

    def points(hist):
        pts = 0
        weights = list(range(1, len(hist) + 1))
        total_w = sum(weights) if weights else 1
        for h, w in zip(hist, weights):
            if h["team_is_home"]:
                if h["result"] == "H":
                    pts += 3 * w
                elif h["result"] == "D":
                    pts += 1 * w
            else:
                if h["result"] == "A":
                    pts += 3 * w
                elif h["result"] == "D":
                    pts += 1 * w
        return pts / total_w if total_w > 0 else 0

    home_hist = last_n(h_norm)
    away_hist = last_n(a_norm)

    if len(home_hist) < 3 or len(away_hist) < 3:
        return {"s_form": None, "direction": None,
                "home_pts": None, "away_pts": None}

    home_pts = points(home_hist)
    away_pts = points(away_hist)
    delta = home_pts - away_pts
    s_form = min(1.0, abs(delta) / 2.0)
    direction = None
    if delta > 0.5:
        direction = "HOME"
    elif delta < -0.5:
        direction = "AWAY"

    return {
        "s_form": s_form if direction else 0,
        "direction": direction,
        "home_pts": home_pts,
        "away_pts": away_pts,
        "delta": delta,
    }


def build_form_cache_from_df(df) -> dict:
    """Bir Football-Data DataFrame'inden form cache üret."""
    cache = {}
    for _, r in df.iterrows():
        ftr = r.get("FTR")
        if ftr not in ("H", "D", "A"):
            continue
        h_norm = normalize(r["HomeTeam"])
        a_norm = normalize(r["AwayTeam"])
        date_str = str(r["Date"])[:10]
        cache.setdefault(h_norm, []).append({
            "date": date_str, "team_is_home": True, "result": ftr,
        })
        cache.setdefault(a_norm, []).append({
            "date": date_str, "team_is_home": False, "result": ftr,
        })
    for k in cache:
        cache[k].sort(key=lambda x: x["date"])
    return cache


def form_signal(home_team: str, away_team: str,
                match_date: str, lookback: int = 5) -> dict:
    """fixtures tablosundan form. backtest için form_signal_from_cache kullan."""
    cache = _load_fix_cache()
    h_norm = normalize(home_team)
    a_norm = normalize(away_team)

    def last_n(team_norm):
        hist = cache.get(team_norm, [])
        relevant = [h for h in hist if h["date"] < match_date]
        return relevant[-lookback:]

    def points(hist, team_is_home_test):
        # Verilen team perspective'inden W/D/L
        # Ama cache zaten team perspective tutmaz; bu listede her maç o takım için record
        pts = 0
        weights = list(range(1, len(hist) + 1))  # newer = higher weight
        total_w = sum(weights) if weights else 1
        for h, w in zip(hist, weights):
            # h["result"] global match result (H/D/A)
            # h["team_is_home"] = bu maçta team ev mi?
            if h["team_is_home"]:
                if h["result"] == "H":
                    pts += 3 * w
                elif h["result"] == "D":
                    pts += 1 * w
            else:
                if h["result"] == "A":
                    pts += 3 * w
                elif h["result"] == "D":
                    pts += 1 * w
        return pts / total_w if total_w > 0 else 0

    home_hist = last_n(h_norm)
    away_hist = last_n(a_norm)

    if not home_hist or not away_hist:
        return {"s_form": None, "direction": None,
                "home_pts": None, "away_pts": None}

    home_pts = points(home_hist, True)
    away_pts = points(away_hist, False)

    delta = home_pts - away_pts
    # delta ∈ [-3, +3] üzeri kaydırma; |delta|>=1 anlamlı
    s_form = min(1.0, abs(delta) / 2.0)
    direction = None
    if delta > 0.5:
        direction = "HOME"
    elif delta < -0.5:
        direction = "AWAY"

    return {
        "s_form": s_form if direction else 0,
        "direction": direction,
        "home_pts": home_pts,
        "away_pts": away_pts,
        "delta": delta,
    }


# ============================================================
# COMBINED SIGNAL
# ============================================================

def all_signals(home_team: str, away_team: str, match_date: str) -> dict:
    """xG luck + form'ı birlikte hesapla."""
    xg = xg_luck_signal(home_team, away_team, match_date)
    form = form_signal(home_team, away_team, match_date)
    return {
        "s_xg": xg["s_xg"],
        "xg_direction": xg["direction"],
        "xg_luck_diff": xg.get("luck_diff"),
        "s_form": form["s_form"],
        "form_direction": form["direction"],
        "form_delta": form.get("delta"),
    }


if __name__ == "__main__":
    # Test
    r = xg_luck_signal("Arsenal", "Chelsea", "2023-04-01")
    print("XG Arsenal-Chelsea 2023-04-01:", r)
    f = form_signal("Arsenal", "Chelsea", "2023-04-01")
    print("Form Arsenal-Chelsea 2023-04-01:", f)
    print()
    a = all_signals("Bayern Munich", "Dortmund", "2023-04-01")
    print("All signals Bayern-Dortmund 2023-04-01:", a)
