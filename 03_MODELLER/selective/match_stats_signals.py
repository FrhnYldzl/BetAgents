"""
MATCH STATS SIGNALS — Pre-match sinyalleri (matches_v2'de %99 coverage)
=========================================================================

3 YENİ ORTOGONAL SİNYAL:

1) SHOTS FORM DIFF SIGNAL (s_shots)
   - Her takımın son 5 maçında shots_for - shots_against avg
   - Home shots_diff vs Away shots_diff karşılaştırma
   - Yön: shots advantage olan taraf

2) REFEREE BIAS SIGNAL (s_referee)
   - Bu hakemin son 20 maçında ev_sahibi_win_rate vs away_win_rate
   - "Ev sahibi-eğilimli" hakemler var (bazıları %55 ev kazandırır, base %46)
   - Yön: hakemin geçmiş eğiliminde olan yön

3) CARDS PRESSURE SIGNAL (s_cards)
   - Maç-spesifik kart yoğunluğu (her iki takımın son 5 maç kart ortalaması)
   - Yüksek kart = gergin maç = beraberlik daha olası
   - Yön: gergin maç (yüksek kart avg) → DRAW yönü

TIMING LEAKAGE GÜVENLİĞİ:
   - Her sinyal sadece PIVOT_DATE'den ÖNCEKİ maçları kullanır (strict <)
   - matches_v2'ye yazılan match stats kullanılır (referee, shots_total, yellows, etc.)
"""
from __future__ import annotations

import sys
import sqlite3
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
YAZILIM = THIS_DIR.parent.parent
sys.path.insert(0, str(YAZILIM / "02_VERI"))

import database as db


# ============================================================
# CACHE — matches_v2 son 5 sezon stats by team
# ============================================================

_TEAM_STATS_CACHE: dict | None = None
_REFEREE_CACHE: dict | None = None


def _load_team_stats_cache():
    """matches_v2'den her takım için tarihsel match stats."""
    global _TEAM_STATS_CACHE
    if _TEAM_STATS_CACHE is not None:
        return _TEAM_STATS_CACHE

    conn = db.connect()
    rows = conn.execute("""
        SELECT league_code, season, matchday, home_team, away_team,
               home_shots_total, away_shots_total,
               home_shots_on, away_shots_on,
               home_corners, away_corners,
               home_yellows, away_yellows,
               home_reds, away_reds,
               referee, home_score, away_score, is_settled
        FROM matches_v2
        WHERE has_match_stats=1 AND is_settled=1
    """).fetchall()
    conn.close()

    cache = {}
    for r in rows:
        d = dict(r)
        # Home team perspective
        cache.setdefault(d["home_team"], []).append({
            "date": d["matchday"],
            "is_home": True,
            "shots_for": d["home_shots_total"],
            "shots_against": d["away_shots_total"],
            "shots_on_for": d["home_shots_on"],
            "shots_on_against": d["away_shots_on"],
            "corners_for": d["home_corners"],
            "corners_against": d["away_corners"],
            "yellows_for": d["home_yellows"],
            "yellows_against": d["away_yellows"],
            "reds_for": d["home_reds"],
            "reds_against": d["away_reds"],
            "goals_for": d["home_score"],
            "goals_against": d["away_score"],
            "referee": d["referee"],
        })
        # Away team perspective (swap)
        cache.setdefault(d["away_team"], []).append({
            "date": d["matchday"],
            "is_home": False,
            "shots_for": d["away_shots_total"],
            "shots_against": d["home_shots_total"],
            "shots_on_for": d["away_shots_on"],
            "shots_on_against": d["home_shots_on"],
            "corners_for": d["away_corners"],
            "corners_against": d["home_corners"],
            "yellows_for": d["away_yellows"],
            "yellows_against": d["home_yellows"],
            "reds_for": d["away_reds"],
            "reds_against": d["home_reds"],
            "goals_for": d["away_score"],
            "goals_against": d["home_score"],
            "referee": d["referee"],
        })
    # Sort each team's list by date
    for k in cache:
        cache[k].sort(key=lambda x: x["date"])
    _TEAM_STATS_CACHE = cache
    return cache


def _load_referee_cache():
    """Her hakem için tarihsel maç sonuçları."""
    global _REFEREE_CACHE
    if _REFEREE_CACHE is not None:
        return _REFEREE_CACHE

    conn = db.connect()
    rows = conn.execute("""
        SELECT matchday, referee, home_team, away_team,
               home_score, away_score,
               home_yellows, away_yellows, home_reds, away_reds
        FROM matches_v2
        WHERE has_match_stats=1 AND is_settled=1
          AND referee IS NOT NULL AND referee != ''
    """).fetchall()
    conn.close()

    cache = {}
    for r in rows:
        d = dict(r)
        # Result
        result = "D"
        if d["home_score"] > d["away_score"]:
            result = "H"
        elif d["away_score"] > d["home_score"]:
            result = "A"
        # Total cards
        total_cards = (d["home_yellows"] or 0) + (d["away_yellows"] or 0) + \
                      (d["home_reds"] or 0) + (d["away_reds"] or 0)
        cache.setdefault(d["referee"], []).append({
            "date": d["matchday"],
            "result": result,
            "total_cards": total_cards,
        })
    for k in cache:
        cache[k].sort(key=lambda x: x["date"])
    _REFEREE_CACHE = cache
    return cache


# ============================================================
# SHOTS FORM DIFF SIGNAL
# ============================================================

def shots_form_signal(home_team: str, away_team: str,
                     match_date: str, lookback: int = 5) -> dict:
    """
    Her takımın son N maçındaki shots avantajı.

    Yön:
      Home shots_diff_avg > Away shots_diff_avg + threshold → HOME signal
      Tersi → AWAY signal
      Yakın → None
    """
    cache = _load_team_stats_cache()

    def diff_avg(team):
        hist = cache.get(team, [])
        relevant = [h for h in hist if h["date"] < match_date][-lookback:]
        if len(relevant) < 3:
            return None
        diffs = []
        for h in relevant:
            sf = h.get("shots_for") or 0
            sa = h.get("shots_against") or 0
            diffs.append(sf - sa)
        return sum(diffs) / len(diffs) if diffs else None

    home_d = diff_avg(home_team)
    away_d = diff_avg(away_team)

    if home_d is None or away_d is None:
        return {"s_shots": None, "direction": None,
                "home_shots_diff": home_d, "away_shots_diff": away_d}

    # Net advantage: pozitif = HOME daha çok shots atıyor
    net = home_d - away_d
    # Sinyal gücü: |net| 5+ → 1.0
    s_shots = min(1.0, abs(net) / 5.0)

    direction = None
    if net > 2.0:
        direction = "HOME"
    elif net < -2.0:
        direction = "AWAY"

    return {
        "s_shots": s_shots if direction else 0,
        "direction": direction,
        "home_shots_diff": home_d,
        "away_shots_diff": away_d,
        "net_diff": net,
    }


# ============================================================
# REFEREE BIAS SIGNAL
# ============================================================

def referee_bias_signal(referee: str, match_date: str,
                       lookback: int = 30) -> dict:
    """
    Bu hakemin son N maçındaki sonuç dağılımı (H/D/A).

    Eğer hakem ev sahibi-eğilimli (>%55 ev kazandırıyor) → HOME signal
    Eğer hakem deplasman-eğilimli (>%35 deplasman) → AWAY signal
    Aksi takdirde signal yok.
    """
    if not referee:
        return {"s_referee": None, "direction": None}

    cache = _load_referee_cache()
    hist = cache.get(referee, [])
    relevant = [h for h in hist if h["date"] < match_date][-lookback:]

    if len(relevant) < 10:
        return {"s_referee": None, "direction": None, "n": len(relevant)}

    n = len(relevant)
    n_h = sum(1 for h in relevant if h["result"] == "H")
    n_d = sum(1 for h in relevant if h["result"] == "D")
    n_a = sum(1 for h in relevant if h["result"] == "A")

    p_h = n_h / n
    p_a = n_a / n

    # Genel ortalama (baseline): %46 H, %26 D, %28 A
    home_bias = p_h - 0.46
    away_bias = p_a - 0.28

    s_referee = max(abs(home_bias), abs(away_bias))
    s_referee = min(1.0, s_referee / 0.10)  # 10pp+ bias → 1.0

    direction = None
    if home_bias > 0.05 and abs(home_bias) > abs(away_bias):
        direction = "HOME"
    elif away_bias > 0.05 and abs(away_bias) > abs(home_bias):
        direction = "AWAY"

    return {
        "s_referee": s_referee if direction else 0,
        "direction": direction,
        "n": n,
        "home_rate": p_h,
        "away_rate": p_a,
        "home_bias": home_bias,
        "away_bias": away_bias,
    }


# ============================================================
# CARDS PRESSURE SIGNAL
# ============================================================

def cards_pressure_signal(home_team: str, away_team: str,
                         match_date: str, lookback: int = 5) -> dict:
    """
    İki takımın son N maçında ortalama kart sayısı.

    Yüksek kart avg = gergin maç patterni.
    Gergin maç → DRAW olasılığı yüksek (her iki taraf kötü, fırsat az).

    Yön: Yüksek pressure → DRAW
    """
    cache = _load_team_stats_cache()

    def total_cards_avg(team):
        hist = cache.get(team, [])
        relevant = [h for h in hist if h["date"] < match_date][-lookback:]
        if len(relevant) < 3:
            return None
        cards = []
        for h in relevant:
            y = (h.get("yellows_for") or 0) + (h.get("yellows_against") or 0)
            r = (h.get("reds_for") or 0) + (h.get("reds_against") or 0)
            cards.append(y + 2*r)  # red 2x weight
        return sum(cards) / len(cards) if cards else None

    home_c = total_cards_avg(home_team)
    away_c = total_cards_avg(away_team)

    if home_c is None or away_c is None:
        return {"s_cards": None, "direction": None,
                "home_cards_avg": home_c, "away_cards_avg": away_c}

    combined = (home_c + away_c) / 2

    # Baseline: avg ~5-6 cards/match
    # Yüksek pressure: 7+ → DRAW signal
    # Düşük pressure: <5 → no signal
    direction = None
    if combined >= 7.0:
        direction = "DRAW"

    # Signal strength: how much over baseline
    s_cards = min(1.0, max(0, combined - 5.0) / 4.0)

    return {
        "s_cards": s_cards if direction else 0,
        "direction": direction,
        "home_cards_avg": home_c,
        "away_cards_avg": away_c,
        "combined": combined,
    }


# ============================================================
# COMBINED — Tüm match stats signals
# ============================================================

def all_match_stats_signals(home_team: str, away_team: str,
                           match_date: str, referee: str = None) -> dict:
    """3 sinyali birden hesapla."""
    s_shots = shots_form_signal(home_team, away_team, match_date)
    s_ref = referee_bias_signal(referee, match_date) if referee else {"s_referee": None, "direction": None}
    s_cards = cards_pressure_signal(home_team, away_team, match_date)
    return {
        "s_shots": s_shots["s_shots"],
        "dir_shots": s_shots["direction"],
        "shots_net_diff": s_shots.get("net_diff"),
        "s_referee": s_ref.get("s_referee"),
        "dir_referee": s_ref.get("direction"),
        "referee_n": s_ref.get("n"),
        "s_cards": s_cards["s_cards"],
        "dir_cards": s_cards["direction"],
        "cards_combined": s_cards.get("combined"),
    }


if __name__ == "__main__":
    # Test
    print("=== TEST ===\n")
    print("[shots_form] Liverpool vs Tottenham 2024-12-01:")
    r = shots_form_signal("Liverpool", "Tottenham", "2024-12-01")
    print(f"  {r}\n")

    print("[referee_bias] Mike Dean 2024-12-01:")
    r = referee_bias_signal("Dean", "2024-12-01")
    print(f"  {r}\n")

    print("[cards_pressure] Galatasaray vs Fenerbahce 2024-12-01:")
    r = cards_pressure_signal("Galatasaray", "Fenerbahce", "2024-12-01")
    print(f"  {r}\n")

    print("[all_signals]:")
    r = all_match_stats_signals("Liverpool", "Tottenham", "2024-12-01", "Dean")
    print(f"  {r}")
